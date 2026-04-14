"""Phase A-3: 背景変更（B3）精度向上 — Python SDK 版実験スクリプト.

全パターンでキャラ参照画像 + seed画像 + 背景参照画像の3枚入力。
google-genai SDK を使用し、ImageConfig(aspect_ratio="9:16") でアスペクト比を制御する。

8パターン × 3seed = 24生成を実行する。

Usage:
    uv run python poc/seamless/run_phase_a3.py --dry-run
    uv run python poc/seamless/run_phase_a3.py --patterns B1,B4,B8
    uv run python poc/seamless/run_phase_a3.py --seeds 1.png,4.png
    uv run python poc/seamless/run_phase_a3.py
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, ImageConfig, Part

from config_a3 import (
    ALL_PATTERNS,
    ASPECT_RATIO,
    BACKGROUND_REF,
    CHARACTER_REF,
    COST_PER_IMAGE,
    GEMINI_MODEL,
    GENERATED_DIR,
    SEED_CAPTURE_DIR,
    SEED_IMAGES,
    A3Pattern,
    get_patterns_by_ids,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def get_gemini_api_key() -> str:
    """環境変数から Google AI API キーを取得する."""
    load_dotenv()
    key = os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI")
    if not key:
        logger.error("DAILY_ROUTINE_API_KEY_GOOGLE_AI が環境変数に設定されていません")
        sys.exit(1)
    return key


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Phase A-3: 背景変更精度向上検証")
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="実行パターンをカンマ区切りで指定 (例: B1,B4,B8)。指定なしで全パターン",
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


def load_image_part(image_path: Path) -> Part:
    """画像ファイルを SDK の Part に変換する."""
    data = image_path.read_bytes()
    suffix = image_path.suffix.lstrip(".")
    mime = f"image/{suffix}" if suffix not in ("jpg", "jpeg") else "image/jpeg"
    return Part.from_bytes(data=data, mime_type=mime)


def gemini_generate_sdk(
    client: genai.Client,
    pattern: A3Pattern,
    char_ref_path: Path,
    seed_image_path: Path,
    bg_ref_path: Path,
    output_path: Path,
) -> dict:
    """Gemini SDK で画像を生成する（3枚入力）."""
    # contents: [キャラ参照(image 1), seed画像(image 2), 背景参照(image 3), テキスト]
    contents = [
        load_image_part(char_ref_path),
        load_image_part(seed_image_path),
        load_image_part(bg_ref_path),
        pattern.prompt,
    ]

    config = GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=ImageConfig(
            aspect_ratio=ASPECT_RATIO,
        ),
    )

    # リトライロジック
    max_retries = 3
    last_error = None
    for attempt in range(1, max_retries + 1):
        logger.info(
            "    SDK リクエスト送信中... (model: %s, aspect_ratio: %s, attempt %d/%d)",
            GEMINI_MODEL, ASPECT_RATIO, attempt, max_retries,
        )
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=contents,
                config=config,
            )
            break
        except Exception as e:
            last_error = e
            error_str = str(e)
            if "500" in error_str or "503" in error_str or "timeout" in error_str.lower():
                logger.warning(
                    "    サーバーエラー/タイムアウト: %s, %d秒後にリトライ...",
                    error_str[:200], 10 * attempt,
                )
                time.sleep(10 * attempt)
            else:
                logger.error("    API エラー: %s", error_str[:500])
                return {
                    "status": "failed",
                    "error": error_str[:200],
                }
    else:
        return {
            "status": "failed",
            "error": f"All retries failed: {last_error}",
        }

    # レスポンス解析
    text_response = ""
    image_data = None

    for part in response.candidates[0].content.parts:
        if part.text:
            text_response += part.text
        if part.inline_data:
            image_data = part.inline_data.data

    if text_response:
        logger.info("    Gemini テキスト応答: %s", text_response[:200])

    if image_data is None:
        logger.error("    Gemini: 画像が生成されませんでした")
        return {
            "status": "failed",
            "error": "No image in response",
            "text_response": text_response,
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_data)
    logger.info("    画像を保存しました: %s (%d bytes)", output_path, len(image_data))

    return {
        "status": "success",
        "output_path": str(output_path),
        "cost_usd": COST_PER_IMAGE,
        "text_response": text_response,
        "image_size_bytes": len(image_data),
    }


def print_dry_run(patterns: list[A3Pattern], seed_images: list[str]) -> None:
    """ドライラン: プロンプト・コスト見積もりを表示する."""
    logger.info("=" * 80)
    logger.info("Phase A-3: 背景変更精度向上 — ドライラン")
    logger.info("=" * 80)
    logger.info("モデル: %s", GEMINI_MODEL)
    logger.info("アスペクト比: %s", ASPECT_RATIO)
    logger.info("キャラクター参照: %s", CHARACTER_REF)
    logger.info("背景参照: %s", BACKGROUND_REF)
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

    # パターン解決
    if args.patterns:
        patterns = get_patterns_by_ids(args.patterns.split(","))
        if not patterns:
            logger.error("指定されたパターンが見つかりません: %s", args.patterns)
            sys.exit(1)
    else:
        patterns = ALL_PATTERNS

    # seed 画像解決
    if args.seeds:
        seed_images = [s.strip() for s in args.seeds.split(",")]
    else:
        seed_images = SEED_IMAGES

    # 入力ファイル存在確認
    for seed_name in seed_images:
        seed_path = SEED_CAPTURE_DIR / seed_name
        if not seed_path.exists():
            logger.error("Seed 画像が見つかりません: %s", seed_path)
            sys.exit(1)

    if not CHARACTER_REF.exists():
        logger.error("キャラクター参照画像が見つかりません: %s", CHARACTER_REF)
        sys.exit(1)

    if not BACKGROUND_REF.exists():
        logger.error("背景参照画像が見つかりません: %s", BACKGROUND_REF)
        sys.exit(1)

    # ドライラン
    if args.dry_run:
        print_dry_run(patterns, seed_images)
        return

    # API キー取得 & クライアント作成
    api_key = get_gemini_api_key()
    client = genai.Client(api_key=api_key)

    total = len(patterns) * len(seed_images)
    total_cost = total * COST_PER_IMAGE
    logger.info("=" * 80)
    logger.info(
        "Phase A-3 実験開始: %d パターン × %d seed = %d 生成, 推定コスト: $%.2f",
        len(patterns), len(seed_images), total, total_cost,
    )
    logger.info("キャラクター参照: %s", CHARACTER_REF)
    logger.info("背景参照: %s", BACKGROUND_REF)

    all_results: list[dict] = []
    generated = 0

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
                result = gemini_generate_sdk(
                    client, pattern, CHARACTER_REF, seed_path, BACKGROUND_REF, output_path,
                )
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

    # 実験ログ保存
    log_path = GENERATED_DIR / "experiment_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "experiment": "phase_a3_background_change",
        "model": GEMINI_MODEL,
        "aspect_ratio": ASPECT_RATIO,
        "sdk": "google-genai",
        "timestamp": datetime.now().isoformat(),
        "seed_images": seed_images,
        "character_ref": str(CHARACTER_REF),
        "background_ref": str(BACKGROUND_REF),
        "patterns": [
            {"id": p.id, "name": p.name, "description": p.description}
            for p in patterns
        ],
        "results": all_results,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    logger.info("")
    logger.info("実験ログを保存しました: %s", log_path)

    # サマリ
    logger.info("=" * 80)
    logger.info("Phase A-3 実験結果サマリ:")
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
