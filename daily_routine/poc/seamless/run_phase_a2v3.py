"""Phase A-2v3: ポーズ変更 — 2段階AIワークフローの Step 1 検証スクリプト.

2段階ワークフロー:
  Step 1: Gemini (gemini-3-flash-preview) が seed 画像を分析 → 画像加工プロンプトを生成
  Step 2: Gemini (gemini-3-pro-image-preview) がプロンプトで seed 画像を加工

4メタプロンプト × 3seed = 12組を実行する。

Usage:
    uv run python poc/seamless/run_phase_a2v3.py --dry-run
    uv run python poc/seamless/run_phase_a2v3.py --patterns M1,M3
    uv run python poc/seamless/run_phase_a2v3.py
"""

import argparse
import base64
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

import httpx
from dotenv import load_dotenv

from config_a2v3 import (
    ALL_META_PROMPTS,
    GENERATED_DIR,
    SEED_IMAGES,
    STEP1_MODEL,
    STEP2_MODEL,
    A2v3MetaPrompt,
    get_meta_prompts_by_ids,
    get_seed_path,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def get_gemini_api_key() -> str:
    """環境変数から Google AI API キーを取得する."""
    load_dotenv()
    key = os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI")
    if not key:
        logger.error("DAILY_ROUTINE_API_KEY_GOOGLE_AI が環境変数に設定されていません")
        sys.exit(1)
    return key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Phase A-2v3: 2段階AIワークフロー Step 1 検証",
    )
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="実行パターンをカンマ区切りで指定 (例: M1,M3)。指定なしで全パターン",
    )
    parser.add_argument(
        "--seeds",
        type=str,
        default=None,
        help="使用する seed をラベルで指定 (例: mimirun_1,tamachan_2)。指定なしで全3枚",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="メタプロンプト確認・コスト見積もりのみ（API 呼び出しなし）",
    )
    return parser.parse_args()


def encode_image_for_gemini(image_path: Path) -> dict:
    """画像を Gemini API のインラインデータ形式にエンコードする."""
    data = image_path.read_bytes()
    suffix = image_path.suffix.lstrip(".")
    mime_map = {"jpg": "image/jpeg", "jpeg": "image/jpeg"}
    mime = mime_map.get(suffix, f"image/{suffix}")
    return {
        "inline_data": {
            "mime_type": mime,
            "data": base64.b64encode(data).decode("utf-8"),
        }
    }


def extract_gemini_text(result: dict) -> str:
    """Gemini API レスポンスからテキストを抽出する."""
    candidates = result.get("candidates", [])
    texts = []
    for candidate in candidates:
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        for part in parts:
            if "text" in part:
                texts.append(part["text"])
    return "\n".join(texts)


def extract_gemini_image(result: dict) -> bytes | None:
    """Gemini API レスポンスから画像データを抽出する."""
    candidates = result.get("candidates", [])
    for candidate in candidates:
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        for part in parts:
            if "inlineData" in part:
                return base64.b64decode(part["inlineData"]["data"])
    return None


def gemini_request(
    client: httpx.Client,
    api_key: str,
    model: str,
    payload: dict,
) -> dict | None:
    """Gemini API にリクエストを送信する（リトライ付き）."""
    url = f"{GEMINI_BASE_URL}/models/{model}:generateContent"
    max_retries = 3
    resp = None

    for attempt in range(1, max_retries + 1):
        logger.info(
            "    API リクエスト送信中... (model: %s, attempt %d/%d)",
            model, attempt, max_retries,
        )
        try:
            resp = client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": api_key},
            )
            if resp.status_code < 500:
                break
            logger.warning(
                "    サーバーエラー (status=%d), %d秒後にリトライ...",
                resp.status_code, 10 * attempt,
            )
            time.sleep(10 * attempt)
        except httpx.ReadTimeout:
            logger.warning(
                "    タイムアウト, %d秒後にリトライ...", 10 * attempt,
            )
            time.sleep(10 * attempt)

    if resp is None:
        return None

    if resp.status_code >= 400:
        logger.error(
            "    API エラー: status=%d, body=%s",
            resp.status_code, resp.text[:500],
        )
        return None

    return resp.json()


def run_step1(
    client: httpx.Client,
    api_key: str,
    meta_prompt: A2v3MetaPrompt,
    seed_image_path: Path,
) -> str | None:
    """Step 1: seed 画像を分析し、画像加工プロンプトを生成する."""
    prompt_text = meta_prompt.build_meta_prompt()

    payload = {
        "contents": [{
            "parts": [
                encode_image_for_gemini(seed_image_path),
                {"text": prompt_text},
            ],
        }],
        "generationConfig": {
            "responseModalities": ["TEXT"],
        },
    }

    result = gemini_request(client, api_key, STEP1_MODEL, payload)
    if result is None:
        return None

    generated_prompt = extract_gemini_text(result).strip()
    if not generated_prompt:
        logger.error("    Step 1: テキストが生成されませんでした")
        return None

    return generated_prompt


def run_step2(
    client: httpx.Client,
    api_key: str,
    generated_prompt: str,
    seed_image_path: Path,
    output_path: Path,
) -> bytes | None:
    """Step 2: Step 1 で生成されたプロンプトで seed 画像を加工する."""
    payload = {
        "contents": [{
            "parts": [
                encode_image_for_gemini(seed_image_path),
                {"text": generated_prompt},
            ],
        }],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    result = gemini_request(client, api_key, STEP2_MODEL, payload)
    if result is None:
        return None

    text_response = extract_gemini_text(result)
    if text_response:
        logger.info("    Step 2 テキスト応答: %s", text_response[:200])

    image_data = extract_gemini_image(result)
    if image_data is None:
        logger.error("    Step 2: 画像が生成されませんでした")
        return None

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_data)
    logger.info("    画像を保存しました: %s", output_path)

    return image_data


def run_two_step(
    client: httpx.Client,
    api_key: str,
    meta_prompt: A2v3MetaPrompt,
    seed: dict,
    seed_image_path: Path,
) -> dict:
    """2段階ワークフローを実行する."""
    output_path = GENERATED_DIR / meta_prompt.id / f"{seed['label']}.png"

    # Step 1: テキスト生成
    logger.info("    === Step 1: プロンプト生成 (%s) ===", STEP1_MODEL)
    generated_prompt = run_step1(client, api_key, meta_prompt, seed_image_path)

    if generated_prompt is None:
        return {
            "status": "failed",
            "error": "Step 1 failed: no prompt generated",
            "step1_prompt": None,
        }

    logger.info("    Step 1 生成プロンプト:\n    %s", generated_prompt[:300])

    # Step 1 の出力プロンプトを保存
    prompt_path = GENERATED_DIR / meta_prompt.id / f"{seed['label']}_step1_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(generated_prompt, encoding="utf-8")

    # Step 2: 画像生成
    logger.info("    === Step 2: 画像生成 (%s) ===", STEP2_MODEL)
    image_data = run_step2(
        client, api_key, generated_prompt, seed_image_path, output_path,
    )

    if image_data is None:
        return {
            "status": "partial",
            "error": "Step 2 failed: no image generated",
            "step1_prompt": generated_prompt,
            "cost_usd": meta_prompt.cost_step1,
        }

    return {
        "status": "success",
        "output_path": str(output_path),
        "step1_prompt": generated_prompt,
        "cost_usd": meta_prompt.cost_total,
    }


def print_dry_run(
    meta_prompts: list[A2v3MetaPrompt],
    seeds: list[dict],
) -> None:
    """ドライラン: メタプロンプト・コスト見積もりを表示する."""
    logger.info("=" * 80)
    logger.info("Phase A-2v3: 2段階AIワークフロー Step 1 検証 — ドライラン")
    logger.info("=" * 80)
    logger.info("Step 1 モデル: %s", STEP1_MODEL)
    logger.info("Step 2 モデル: %s", STEP2_MODEL)
    logger.info("Seed 画像: %s", [s["label"] for s in seeds])
    logger.info("")

    for mp in meta_prompts:
        logger.info("-" * 60)
        logger.info("[%s] %s", mp.id, mp.name)
        logger.info("  説明: %s", mp.description)
        logger.info("  コスト/組: $%.3f (Step1: $%.3f + Step2: $%.3f)",
                     mp.cost_total, mp.cost_step1, mp.cost_step2)
        logger.info("  メタプロンプト:")
        for line in mp.build_meta_prompt().split("\n"):
            logger.info("    %s", line)

    logger.info("")
    logger.info("=" * 80)
    total = len(meta_prompts) * len(seeds)
    total_cost = sum(mp.cost_total for mp in meta_prompts) * len(seeds)
    logger.info(
        "合計: %d パターン × %d seed = %d 組, 推定コスト: $%.2f",
        len(meta_prompts), len(seeds), total, total_cost,
    )
    logger.info("=" * 80)


def resolve_seeds(seed_labels: str | None) -> list[dict]:
    """seed ラベルから seed 定義を解決する."""
    if seed_labels is None:
        return SEED_IMAGES

    labels = {s.strip() for s in seed_labels.split(",")}
    seeds = [s for s in SEED_IMAGES if s["label"] in labels]
    if not seeds:
        logger.error("指定された seed が見つかりません: %s", seed_labels)
        sys.exit(1)
    return seeds


def main() -> None:
    args = parse_args()

    # メタプロンプト解決
    if args.patterns:
        meta_prompts = get_meta_prompts_by_ids(args.patterns.split(","))
        if not meta_prompts:
            logger.error("指定されたパターンが見つかりません: %s", args.patterns)
            sys.exit(1)
    else:
        meta_prompts = ALL_META_PROMPTS

    # seed 解決
    seeds = resolve_seeds(args.seeds)

    # seed 画像の存在確認
    for seed in seeds:
        seed_path = get_seed_path(seed)
        if not seed_path.exists():
            logger.error("Seed 画像が見つかりません: %s", seed_path)
            sys.exit(1)

    # ドライラン
    if args.dry_run:
        print_dry_run(meta_prompts, seeds)
        return

    # API キー取得
    api_key = get_gemini_api_key()
    client = httpx.Client(timeout=httpx.Timeout(30.0, read=300.0))

    total = len(meta_prompts) * len(seeds)
    total_cost = sum(mp.cost_total for mp in meta_prompts) * len(seeds)
    logger.info("=" * 80)
    logger.info(
        "Phase A-2v3 実験開始: %d パターン × %d seed = %d 組, 推定コスト: $%.2f",
        len(meta_prompts), len(seeds), total, total_cost,
    )

    all_results: list[dict] = []
    generated = 0

    try:
        for mp in meta_prompts:
            logger.info("")
            logger.info("-" * 60)
            logger.info("[%s] %s", mp.id, mp.name)

            for seed in seeds:
                generated += 1
                seed_path = get_seed_path(seed)

                logger.info("")
                logger.info(
                    "  [%d/%d] seed=%s, pattern=%s",
                    generated, total, seed["label"], mp.id,
                )

                try:
                    result = run_two_step(
                        client, api_key, mp, seed, seed_path,
                    )
                except Exception:
                    logger.exception("    予期しないエラー")
                    result = {
                        "status": "failed",
                        "error": "unexpected exception",
                        "step1_prompt": None,
                    }
                result.update({
                    "meta_prompt_id": mp.id,
                    "meta_prompt_name": mp.name,
                    "seed_label": seed["label"],
                    "seed_file": seed["file"],
                })
                all_results.append(result)

    finally:
        client.close()

    # 実験ログ保存
    log_path = GENERATED_DIR / "experiment_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "experiment": "phase_a2v3_two_step_workflow",
        "step1_model": STEP1_MODEL,
        "step2_model": STEP2_MODEL,
        "timestamp": datetime.now().isoformat(),
        "seeds": seeds,
        "meta_prompts": [
            {"id": mp.id, "name": mp.name, "description": mp.description}
            for mp in meta_prompts
        ],
        "results": all_results,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    logger.info("")
    logger.info("実験ログを保存しました: %s", log_path)

    # サマリ
    logger.info("=" * 80)
    logger.info("Phase A-2v3 実験結果サマリ:")
    success = sum(1 for r in all_results if r["status"] == "success")
    partial = sum(1 for r in all_results if r["status"] == "partial")
    failed = sum(1 for r in all_results if r["status"] == "failed")
    actual_cost = sum(r.get("cost_usd", 0) for r in all_results)
    logger.info("  成功: %d, 部分成功(Step1のみ): %d, 失敗: %d", success, partial, failed)
    logger.info("  実コスト: $%.2f", actual_cost)

    # パターン別サマリ
    logger.info("")
    logger.info("パターン別:")
    for mp in meta_prompts:
        mp_results = [r for r in all_results if r["meta_prompt_id"] == mp.id]
        mp_success = sum(1 for r in mp_results if r["status"] == "success")
        logger.info("  [%s] %s: %d/%d 成功", mp.id, mp.name, mp_success, len(mp_results))

    # Step 1 生成プロンプト一覧
    logger.info("")
    logger.info("Step 1 生成プロンプト一覧:")
    for r in all_results:
        logger.info("  [%s × %s]:", r["meta_prompt_id"], r["seed_label"])
        if r.get("step1_prompt"):
            for line in r["step1_prompt"].split("\n"):
                logger.info("    %s", line)
        else:
            logger.info("    (生成なし)")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
