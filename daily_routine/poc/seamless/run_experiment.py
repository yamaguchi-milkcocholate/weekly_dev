"""Seamless Keyframe PoC: 実験実行スクリプト.

BFL API（FLUX Kontext）で Seamless キーフレーム生成の実験を実行する。

Usage:
    uv run python poc/seamless/run_experiment.py --dry-run
    uv run python poc/seamless/run_experiment.py --experiment exp1 --dry-run
    uv run python poc/seamless/run_experiment.py --patterns D-A,I-B
    uv run python poc/seamless/run_experiment.py
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
from urllib.request import urlretrieve

import httpx
from dotenv import load_dotenv

from config import (
    ALL_PATTERNS,
    CHARACTER_REF,
    DEFAULT_SCENE_IMAGE,
    GENERATED_DIR,
    SEED_CAPTURE_DIR,
    Endpoint,
    ExperimentPattern,
    GenerationStep,
    count_images,
    estimate_cost,
    get_patterns_by_experiment,
    get_patterns_by_ids,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BFL_API_BASE = "https://api.bfl.ai"
POLL_INTERVAL = 1.0
POLL_TIMEOUT = 300.0


def get_api_key() -> str:
    """環境変数から BFL API キーを取得する."""
    load_dotenv()
    key = os.environ.get("DAILY_ROUTINE_API_KEY_BFL")
    if not key:
        logger.error("DAILY_ROUTINE_API_KEY_BFL が環境変数に設定されていません")
        sys.exit(1)
    return key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seamless Keyframe PoC: FLUX Kontext 実験")
    parser.add_argument(
        "--experiment",
        type=str,
        default=None,
        help="実行する実験 (exp1 / exp2 / exp3)。指定なしで全実験",
    )
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="実行パターンをカンマ区切りで指定 (例: D-A,I-B)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="プロンプト確認・コスト見積もりのみ（API呼び出しなし）",
    )
    parser.add_argument(
        "--seed-image",
        type=Path,
        default=None,
        help=f"Seed キャプチャのパス (デフォルト: {SEED_CAPTURE_DIR / DEFAULT_SCENE_IMAGE})",
    )
    parser.add_argument(
        "--character-ref",
        type=Path,
        default=None,
        help=f"キャラクター参照画像のパス (デフォルト: {CHARACTER_REF})",
    )
    return parser.parse_args()


def resolve_patterns(args: argparse.Namespace) -> list[ExperimentPattern]:
    """引数からパターンリストを解決する."""
    if args.patterns:
        patterns = get_patterns_by_ids(args.patterns.split(","))
        if not patterns:
            logger.error("指定されたパターンが見つかりません: %s", args.patterns)
            sys.exit(1)
        return patterns

    if args.experiment:
        patterns = get_patterns_by_experiment(args.experiment)
        if not patterns:
            logger.error("指定された実験が見つかりません: %s", args.experiment)
            sys.exit(1)
        return patterns

    return ALL_PATTERNS


def encode_image_base64(file_path: Path) -> str:
    """ローカル画像を Base64 エンコードする."""
    logger.info("画像を Base64 エンコード中: %s", file_path.name)
    data = file_path.read_bytes()
    return base64.b64encode(data).decode("utf-8")


def download_image(url: str, output_path: Path) -> None:
    """URL から画像をダウンロードしてローカルに保存する."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    urlretrieve(url, output_path)
    logger.info("画像を保存しました: %s", output_path)


def submit_generation(client: httpx.Client, endpoint: str, payload: dict) -> str:
    """BFL API にリクエストを送信し、polling_url を返す."""
    url = f"{BFL_API_BASE}/{endpoint}"
    response = client.post(url, json=payload)
    response.raise_for_status()
    result = response.json()
    logger.info("  リクエスト送信完了 (id: %s)", result.get("id", "unknown"))
    return result["polling_url"]


def poll_result(client: httpx.Client, polling_url: str) -> dict:
    """ポーリングで生成結果を取得する."""
    start = time.monotonic()
    while time.monotonic() - start < POLL_TIMEOUT:
        response = client.get(polling_url)
        response.raise_for_status()
        data = response.json()
        status = data.get("status")

        if status == "Ready":
            return data["result"]
        if status in ("Error", "Failed", "Request Moderated"):
            raise RuntimeError(f"BFL API エラー: {data}")

        logger.info("  ポーリング中... (status: %s)", status)
        time.sleep(POLL_INTERVAL)

    raise TimeoutError(f"BFL API タイムアウト ({POLL_TIMEOUT}s)")


def build_bfl_payload(
    step: GenerationStep,
    seed_image_b64: str,
    character_ref_b64: str,
    previous_output_url: str | None,
) -> dict:
    """GenerationStep から BFL API のペイロードを構築する."""
    payload: dict = {"prompt": step.prompt}

    if step.seed is not None:
        payload["seed"] = step.seed

    if step.aspect_ratio is not None:
        payload["aspect_ratio"] = step.aspect_ratio

    if step.endpoint == Endpoint.MAX:
        # Max: 複数画像入力（input_image + input_image_2）
        if step.use_seed_capture:
            payload["input_image"] = seed_image_b64
        if step.use_character_ref:
            payload["input_image_2"] = character_ref_b64
    else:
        # Pro: 単一画像入力
        if step.use_previous_output and previous_output_url:
            payload["input_image"] = previous_output_url
        elif step.use_seed_capture:
            payload["input_image"] = seed_image_b64

    return payload


def print_dry_run(patterns: list[ExperimentPattern], seed_image: Path, character_ref: Path) -> None:
    """ドライラン: プロンプトとコスト見積もりを表示する."""
    logger.info("=" * 80)
    logger.info("ドライラン: プロンプト確認・コスト見積もり")
    logger.info("=" * 80)
    logger.info("Seed キャプチャ: %s", seed_image)
    logger.info("キャラクター参照: %s", character_ref)
    logger.info("")

    for pattern in patterns:
        logger.info("-" * 60)
        logger.info("[%s] %s (実験: %s)", pattern.id, pattern.name, pattern.experiment_group)
        logger.info("  説明: %s", pattern.description)
        logger.info(
            "  ステップ数: %d, 画像数: %d, コスト: $%.2f", len(pattern.steps), pattern.image_count, pattern.cost
        )

        for i, step in enumerate(pattern.steps, 1):
            input_sources = []
            if step.use_seed_capture:
                input_sources.append("seed キャプチャ")
            if step.use_character_ref:
                input_sources.append("キャラクター参照")
            if step.use_previous_output:
                input_sources.append("前ステップ出力")

            logger.info("")
            logger.info("  Step %d/%d: %s", i, len(pattern.steps), step.step_id)
            logger.info("    Endpoint: %s", step.endpoint.value)
            logger.info("    入力: %s", " + ".join(input_sources))
            logger.info("    seed: %s", step.seed)
            logger.info("    出力: %s", step.output_filename)
            logger.info("    プロンプト: %s", step.prompt)

    logger.info("")
    logger.info("=" * 80)
    total_images = count_images(patterns)
    total_cost = estimate_cost(patterns)
    logger.info("合計: %d パターン, %d 画像, 推定コスト: $%.2f", len(patterns), total_images, total_cost)
    logger.info("=" * 80)


def run_step(
    step: GenerationStep,
    client: httpx.Client,
    seed_image_b64: str,
    character_ref_b64: str,
    previous_output_url: str | None,
    output_dir: Path,
) -> dict:
    """1ステップを実行し、結果を返す."""
    payload = build_bfl_payload(step, seed_image_b64, character_ref_b64, previous_output_url)
    output_path = output_dir / step.output_filename

    logger.info("  API 呼び出し中: %s (endpoint: %s)", step.step_id, step.endpoint.value)
    logger.info(
        "  プロンプト: %s", step.prompt[:100] + "..." if len(step.prompt) > 100 else step.prompt
    )

    # リクエスト送信 → ポーリング
    polling_url = submit_generation(client, step.endpoint.value, payload)
    result = poll_result(client, polling_url)

    # 出力画像を取得
    output_url = result.get("sample")
    if not output_url:
        raise RuntimeError(f"API から画像 URL が返されませんでした: {step.step_id}")

    download_image(output_url, output_path)

    return {
        "step_id": step.step_id,
        "endpoint": step.endpoint.value,
        "prompt": step.prompt,
        "seed": step.seed,
        "output_url": output_url,
        "output_path": str(output_path),
        "cost_usd": step.cost,
        "status": "success",
    }


def run_pattern(
    pattern: ExperimentPattern,
    client: httpx.Client,
    seed_image_b64: str,
    character_ref_b64: str,
) -> dict:
    """1パターン（複数ステップ）を実行し、結果を返す."""
    output_dir = GENERATED_DIR / pattern.experiment_group / pattern.id

    logger.info("-" * 60)
    logger.info("[%s] %s を実行中...", pattern.id, pattern.name)

    step_results = []
    previous_output_url: str | None = None

    for i, step in enumerate(pattern.steps, 1):
        logger.info("  Step %d/%d: %s", i, len(pattern.steps), step.step_id)

        try:
            step_result = run_step(
                step, client, seed_image_b64, character_ref_b64, previous_output_url, output_dir
            )
            step_results.append(step_result)
            previous_output_url = step_result["output_url"]
            logger.info("  Step %d 完了: %s", i, step_result["output_path"])
        except Exception:
            logger.exception("  Step %d 失敗: %s", i, step.step_id)
            step_results.append({
                "step_id": step.step_id,
                "endpoint": step.endpoint.value,
                "prompt": step.prompt,
                "status": "failed",
            })
            # 連鎖ステップの場合、後続をスキップ
            remaining = len(pattern.steps) - i
            if remaining > 0:
                logger.warning(
                    "  連鎖ステップが失敗したため、残り %d ステップをスキップします", remaining
                )
                for skip_step in pattern.steps[i:]:
                    step_results.append({
                        "step_id": skip_step.step_id,
                        "endpoint": skip_step.endpoint.value,
                        "prompt": skip_step.prompt,
                        "status": "skipped",
                    })
            break

    return {
        "pattern_id": pattern.id,
        "pattern_name": pattern.name,
        "experiment_group": pattern.experiment_group,
        "description": pattern.description,
        "steps": step_results,
    }


def run_experiment(args: argparse.Namespace) -> None:
    """実験を実行する."""
    patterns = resolve_patterns(args)
    seed_image = args.seed_image or (SEED_CAPTURE_DIR / DEFAULT_SCENE_IMAGE)
    character_ref = args.character_ref or CHARACTER_REF

    # 参照画像の存在確認
    if not seed_image.exists():
        logger.error("Seed キャプチャが見つかりません: %s", seed_image)
        sys.exit(1)
    if not character_ref.exists():
        logger.error("キャラクター参照画像が見つかりません: %s", character_ref)
        sys.exit(1)

    # ドライラン
    if args.dry_run:
        print_dry_run(patterns, seed_image, character_ref)
        return

    # API キー取得
    api_key = get_api_key()

    # 参照画像を Base64 エンコード
    logger.info("=" * 80)
    logger.info("参照画像を Base64 エンコード中...")
    seed_image_b64 = encode_image_base64(seed_image)
    character_ref_b64 = encode_image_base64(character_ref)

    # httpx クライアント作成
    client = httpx.Client(
        headers={"x-key": api_key},
        timeout=httpx.Timeout(30.0, read=60.0),
    )

    # パターンごとに実行
    logger.info("=" * 80)
    total_images = count_images(patterns)
    total_cost = estimate_cost(patterns)
    logger.info(
        "実験開始: %d パターン, %d 画像, 推定コスト: $%.2f", len(patterns), total_images, total_cost
    )

    pattern_results = []
    try:
        for pattern in patterns:
            result = run_pattern(pattern, client, seed_image_b64, character_ref_b64)
            pattern_results.append(result)
    finally:
        client.close()

    # experiment_log.json に保存
    log_path = GENERATED_DIR / "experiment_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "experiment": "seamless_keyframe_poc",
        "timestamp": datetime.now().isoformat(),
        "seed_image": str(seed_image),
        "character_ref": str(character_ref),
        "patterns": pattern_results,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    logger.info("実験ログを保存しました: %s", log_path)

    # サマリ表示
    logger.info("=" * 80)
    logger.info("実験結果サマリ:")
    total_success = 0
    total_failed = 0
    total_skipped = 0
    actual_cost = 0.0

    for pr in pattern_results:
        for sr in pr["steps"]:
            if sr["status"] == "success":
                total_success += 1
                actual_cost += sr.get("cost_usd", 0)
            elif sr["status"] == "failed":
                total_failed += 1
            elif sr["status"] == "skipped":
                total_skipped += 1

    logger.info("  成功: %d, 失敗: %d, スキップ: %d", total_success, total_failed, total_skipped)
    logger.info("  実コスト: $%.2f", actual_cost)
    logger.info("=" * 80)


def main() -> None:
    args = parse_args()
    run_experiment(args)


if __name__ == "__main__":
    main()
