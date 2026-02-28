"""Phase A-2v2: ポーズ変更 — 制約設計によるプロンプト構築フロー検証スクリプト.

8パターン × 3seed = 24生成を実行する。

Usage:
    uv run python poc/seamless/run_phase_a2v2.py --dry-run
    uv run python poc/seamless/run_phase_a2v2.py --patterns P1,P4,P8
    uv run python poc/seamless/run_phase_a2v2.py
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

from config_a2v2 import (
    ALL_PATTERNS,
    COST_PER_IMAGE,
    GEMINI_MODEL,
    GENERATED_DIR,
    SEED_CAPTURE_DIR,
    SEED_IMAGES,
    A2v2Pattern,
    get_patterns_by_ids,
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
    parser = argparse.ArgumentParser(description="Phase A-2v2: ポーズ変更・制約設計検証")
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="実行パターンをカンマ区切りで指定 (例: P1,P4,P8)。指定なしで全パターン",
    )
    parser.add_argument(
        "--seeds",
        type=str,
        default=None,
        help="使用する seed 画像をカンマ区切りで指定 (例: 1.png,4.png)。指定なしで全3枚",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="プロンプト確認・コスト見積もりのみ（API 呼び出しなし）",
    )
    return parser.parse_args()


def encode_image_for_gemini(image_path: Path) -> dict:
    """画像を Gemini API のインラインデータ形式にエンコードする."""
    data = image_path.read_bytes()
    suffix = image_path.suffix.lstrip(".")
    mime = f"image/{suffix}" if suffix != "jpg" else "image/jpeg"
    return {
        "inline_data": {
            "mime_type": mime,
            "data": base64.b64encode(data).decode("utf-8"),
        }
    }


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


def gemini_generate(
    client: httpx.Client,
    api_key: str,
    pattern: A2v2Pattern,
    seed_image_path: Path,
    output_path: Path,
) -> dict:
    """Gemini API で画像を生成する."""
    parts: list[dict] = []
    parts.append(encode_image_for_gemini(seed_image_path))
    logger.info("    seed 画像を入力")
    parts.append({"text": pattern.prompt})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    url = f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent"

    max_retries = 3
    resp = None
    for attempt in range(1, max_retries + 1):
        logger.info(
            "    Gemini API リクエスト送信中... (model: %s, attempt %d/%d)",
            GEMINI_MODEL, attempt, max_retries,
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
        return {"status": "failed", "error": "All retries timed out"}

    if resp.status_code >= 400:
        logger.error("    Gemini API エラー: status=%d, body=%s", resp.status_code, resp.text[:500])
        return {"status": "failed", "error": f"HTTP {resp.status_code}: {resp.text[:200]}"}

    result = resp.json()

    text_response = extract_gemini_text(result)
    if text_response:
        logger.info("    Gemini テキスト応答: %s", text_response[:200])

    image_data = extract_gemini_image(result)
    if image_data is None:
        logger.error("    Gemini: 画像が生成されませんでした")
        return {"status": "failed", "error": "No image in response", "text_response": text_response}

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_data)
    logger.info("    画像を保存しました: %s", output_path)

    return {
        "status": "success",
        "output_path": str(output_path),
        "cost_usd": COST_PER_IMAGE,
        "text_response": text_response,
    }


def print_dry_run(patterns: list[A2v2Pattern], seed_images: list[str]) -> None:
    """ドライラン: プロンプト・コスト見積もりを表示する."""
    logger.info("=" * 80)
    logger.info("Phase A-2v2: ポーズ変更・制約設計検証 — ドライラン")
    logger.info("=" * 80)
    logger.info("モデル: %s", GEMINI_MODEL)
    logger.info("Seed 画像: %s", [str(SEED_CAPTURE_DIR / s) for s in seed_images])
    logger.info("")

    for pattern in patterns:
        logger.info("-" * 60)
        logger.info("[%s] %s", pattern.id, pattern.name)
        logger.info("  説明: %s", pattern.description)
        logger.info("  コスト/枚: $%.3f", pattern.cost)
        logger.info("  プロンプト:")
        logger.info("    %s", pattern.prompt)

    logger.info("")
    logger.info("=" * 80)
    total = len(patterns) * len(seed_images)
    total_cost = total * COST_PER_IMAGE
    logger.info(
        "合計: %d パターン × %d seed = %d 生成, 推定コスト: $%.2f",
        len(patterns), len(seed_images), total, total_cost,
    )
    logger.info("=" * 80)


def main() -> None:
    args = parse_args()

    if args.patterns:
        patterns = get_patterns_by_ids(args.patterns.split(","))
        if not patterns:
            logger.error("指定されたパターンが見つかりません: %s", args.patterns)
            sys.exit(1)
    else:
        patterns = ALL_PATTERNS

    if args.seeds:
        seed_images = [s.strip() for s in args.seeds.split(",")]
    else:
        seed_images = SEED_IMAGES

    for seed_name in seed_images:
        seed_path = SEED_CAPTURE_DIR / seed_name
        if not seed_path.exists():
            logger.error("Seed 画像が見つかりません: %s", seed_path)
            sys.exit(1)

    if args.dry_run:
        print_dry_run(patterns, seed_images)
        return

    api_key = get_gemini_api_key()
    client = httpx.Client(timeout=httpx.Timeout(30.0, read=300.0))

    total = len(patterns) * len(seed_images)
    total_cost = total * COST_PER_IMAGE
    logger.info("=" * 80)
    logger.info(
        "Phase A-2v2 実験開始: %d パターン × %d seed = %d 生成, 推定コスト: $%.2f",
        len(patterns), len(seed_images), total, total_cost,
    )

    all_results: list[dict] = []
    generated = 0

    try:
        for pattern in patterns:
            logger.info("")
            logger.info("-" * 60)
            logger.info("[%s] %s", pattern.id, pattern.name)

            for seed_name in seed_images:
                generated += 1
                seed_path = SEED_CAPTURE_DIR / seed_name
                seed_stem = Path(seed_name).stem
                output_path = GENERATED_DIR / pattern.id / f"seed_{seed_stem}.png"

                logger.info("")
                logger.info(
                    "  [%d/%d] seed=%s, pattern=%s",
                    generated, total, seed_name, pattern.id,
                )

                try:
                    result = gemini_generate(client, api_key, pattern, seed_path, output_path)
                except Exception:
                    logger.exception("    予期しないエラー")
                    result = {"status": "failed", "error": "unexpected exception"}
                result.update({
                    "pattern_id": pattern.id,
                    "pattern_name": pattern.name,
                    "seed_image": seed_name,
                    "prompt": pattern.prompt,
                })
                all_results.append(result)

    finally:
        client.close()

    log_path = GENERATED_DIR / "experiment_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "experiment": "phase_a2v2_pose_constraint_design",
        "model": GEMINI_MODEL,
        "timestamp": datetime.now().isoformat(),
        "seed_images": seed_images,
        "patterns": [
            {"id": p.id, "name": p.name, "description": p.description}
            for p in patterns
        ],
        "results": all_results,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    logger.info("")
    logger.info("実験ログを保存しました: %s", log_path)

    logger.info("=" * 80)
    logger.info("Phase A-2v2 実験結果サマリ:")
    success = sum(1 for r in all_results if r["status"] == "success")
    failed = sum(1 for r in all_results if r["status"] == "failed")
    actual_cost = sum(r.get("cost_usd", 0) for r in all_results if r["status"] == "success")
    logger.info("  成功: %d, 失敗: %d", success, failed)
    logger.info("  実コスト: $%.2f", actual_cost)

    logger.info("")
    logger.info("パターン別:")
    for pattern in patterns:
        p_results = [r for r in all_results if r["pattern_id"] == pattern.id]
        p_success = sum(1 for r in p_results if r["status"] == "success")
        logger.info("  [%s] %s: %d/%d 成功", pattern.id, pattern.name, p_success, len(p_results))

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
