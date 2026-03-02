"""Phase B-1: 複合編集 — 段階的パイプライン検証スクリプト.

A1〜A5 のベストプラクティスを統合した 4 ステップパイプラインを実行する。

パイプライン v3（seed 1枚あたり）:
  Step 0: 背景変更               — Pro I2I（キャラ参照 + 元seed + 背景参照）※実写を直接入力
  Step 1: テキスト除去           — Pro I2I（Step 0 出力 1枚入力）
  Step 2a: Flash 分析            — Flash テキスト生成（Step 1 出力 1枚入力）
  Step 2b: 人物差し替え+ポーズ   — Pro I2I（キャラ参照 + Step 1 出力 + Step 2a プロンプト）

背景変更は画質劣化に最も敏感なため、実写画像を直接入力する最上流に配置。

3 seed × 4 ステップ = 12 API コール（うち画像生成 9、テキスト生成 3）

Usage:
    uv run python poc/seamless/run_phase_b1.py --dry-run
    uv run python poc/seamless/run_phase_b1.py --seeds 1.png,4.png
    uv run python poc/seamless/run_phase_b1.py
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from config_b1 import (
    ASPECT_RATIO,
    BACKGROUND_REF,
    BG_CHANGE_PROMPT,
    CHARACTER_REF,
    GENERATED_DIR,
    SEED_CAPTURE_DIR,
    SEED_IMAGES,
    STEP0_MODEL,
    STEP0_PROMPT,
    STEP1A_MODEL,
    STEP1B_MODEL,
    STEP2_MODEL,
    build_step1a_meta_prompt,
    estimate_cost_per_seed,
    estimate_total_cost,
)
from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, ImageConfig, Part

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
    parser = argparse.ArgumentParser(
        description="Phase B-1: 複合編集 — 段階的パイプライン検証",
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
        help="パイプライン構成・コスト見積もりのみ（API 呼び出しなし）",
    )
    return parser.parse_args()


def load_image_part(image_path: Path) -> Part:
    """画像ファイルを SDK の Part に変換する."""
    data = image_path.read_bytes()
    suffix = image_path.suffix.lstrip(".")
    mime = f"image/{suffix}" if suffix not in ("jpg", "jpeg") else "image/jpeg"
    return Part.from_bytes(data=data, mime_type=mime)


def sdk_generate_image(
    client: genai.Client,
    model: str,
    contents: list,
    output_path: Path,
    step_name: str,
) -> dict:
    """SDK で画像を生成する（リトライ付き）."""
    config = GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=ImageConfig(aspect_ratio=ASPECT_RATIO),
    )

    max_retries = 3
    last_error = None
    for attempt in range(1, max_retries + 1):
        logger.info(
            "      SDK リクエスト送信中... (model: %s, attempt %d/%d)",
            model, attempt, max_retries,
        )
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            break
        except Exception as e:
            last_error = e
            error_str = str(e)
            if "500" in error_str or "503" in error_str or "timeout" in error_str.lower():
                logger.warning(
                    "      サーバーエラー/タイムアウト: %s, %d秒後にリトライ...",
                    error_str[:200], 10 * attempt,
                )
                time.sleep(10 * attempt)
            else:
                logger.error("      API エラー: %s", error_str[:500])
                return {"status": "failed", "error": error_str[:200], "step": step_name}
    else:
        return {
            "status": "failed",
            "error": f"All retries failed: {last_error}",
            "step": step_name,
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
        logger.info("      テキスト応答: %s", text_response[:200])

    if image_data is None:
        logger.error("      画像が生成されませんでした")
        return {
            "status": "failed",
            "error": "No image in response",
            "step": step_name,
            "text_response": text_response,
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_data)
    logger.info("      画像を保存しました: %s (%d bytes)", output_path, len(image_data))

    return {
        "status": "success",
        "output_path": str(output_path),
        "step": step_name,
        "text_response": text_response,
        "image_size_bytes": len(image_data),
    }


def sdk_generate_text(
    client: genai.Client,
    model: str,
    contents: list,
    step_name: str,
) -> dict:
    """SDK でテキストを生成する（リトライ付き）."""
    config = GenerateContentConfig(
        response_modalities=["TEXT"],
    )

    max_retries = 3
    last_error = None
    for attempt in range(1, max_retries + 1):
        logger.info(
            "      SDK リクエスト送信中... (model: %s, attempt %d/%d)",
            model, attempt, max_retries,
        )
        try:
            response = client.models.generate_content(
                model=model,
                contents=contents,
                config=config,
            )
            break
        except Exception as e:
            last_error = e
            error_str = str(e)
            if "500" in error_str or "503" in error_str or "timeout" in error_str.lower():
                logger.warning(
                    "      サーバーエラー/タイムアウト: %s, %d秒後にリトライ...",
                    error_str[:200], 10 * attempt,
                )
                time.sleep(10 * attempt)
            else:
                logger.error("      API エラー: %s", error_str[:500])
                return {"status": "failed", "error": error_str[:200], "step": step_name}
    else:
        return {
            "status": "failed",
            "error": f"All retries failed: {last_error}",
            "step": step_name,
        }

    # テキスト抽出
    text_response = ""
    for part in response.candidates[0].content.parts:
        if part.text:
            text_response += part.text

    if not text_response.strip():
        logger.error("      テキストが生成されませんでした")
        return {"status": "failed", "error": "No text in response", "step": step_name}

    return {
        "status": "success",
        "step": step_name,
        "generated_text": text_response.strip(),
    }


def run_pipeline(
    client: genai.Client,
    seed_name: str,
    seed_path: Path,
) -> dict:
    """1枚の seed に対してフルパイプラインを実行する（v3: 背景変更を最上流に配置）."""
    seed_stem = Path(seed_name).stem
    output_dir = GENERATED_DIR / f"seed_{seed_stem}"
    pipeline_result = {
        "seed": seed_name,
        "steps": {},
        "status": "success",
        "cost_usd": 0.0,
    }

    # =========================================================================
    # Step 0: 背景変更（元 seed + 背景参照の2枚のみ。キャラ参照は渡さない）
    # =========================================================================
    logger.info("    --- Step 0: 背景変更 (model: %s) ---", STEP2_MODEL)
    step0_output = output_dir / "step0_background.png"
    step0_result = sdk_generate_image(
        client,
        model=STEP2_MODEL,
        contents=[
            load_image_part(seed_path),  # image 1: 元 seed（実写）
            load_image_part(BACKGROUND_REF),  # image 2: 背景参照
            BG_CHANGE_PROMPT,
        ],
        output_path=step0_output,
        step_name="step0_background_change",
    )
    pipeline_result["steps"]["step0"] = step0_result

    if step0_result["status"] != "success":
        pipeline_result["status"] = "failed_at_step0"
        return pipeline_result
    pipeline_result["cost_usd"] += 0.04

    # =========================================================================
    # Step 1: テキスト除去（背景変更後の画像からテキストオーバーレイを除去）
    # =========================================================================
    logger.info("    --- Step 1: テキスト除去 (model: %s) ---", STEP0_MODEL)
    step1_output = output_dir / "step1_text_removed.png"
    step1_result = sdk_generate_image(
        client,
        model=STEP0_MODEL,
        contents=[load_image_part(step0_output), STEP0_PROMPT],
        output_path=step1_output,
        step_name="step1_text_removal",
    )
    pipeline_result["steps"]["step1"] = step1_result

    if step1_result["status"] != "success":
        pipeline_result["status"] = "failed_at_step1"
        return pipeline_result
    pipeline_result["cost_usd"] += 0.04

    # =========================================================================
    # Step 2a: Flash 分析 → プロンプト生成（背景変更+テキスト除去済み画像を分析）
    # =========================================================================
    logger.info("    --- Step 2a: Flash 分析 (model: %s) ---", STEP1A_MODEL)
    meta_prompt = build_step1a_meta_prompt()
    step2a_result = sdk_generate_text(
        client,
        model=STEP1A_MODEL,
        contents=[load_image_part(step1_output), meta_prompt],
        step_name="step2a_flash_analysis",
    )
    pipeline_result["steps"]["step2a"] = step2a_result

    if step2a_result["status"] != "success":
        pipeline_result["status"] = "failed_at_step2a"
        return pipeline_result
    pipeline_result["cost_usd"] += 0.01

    generated_prompt = step2a_result["generated_text"]
    logger.info("      生成プロンプト:\n%s", generated_prompt)

    # Step 2a の出力プロンプトを保存
    prompt_path = output_dir / "step2a_generated_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(generated_prompt, encoding="utf-8")

    # =========================================================================
    # Step 2b: 人物差し替え + ポーズ変更（背景変更+テキスト除去済み画像に対して）
    # =========================================================================
    logger.info("    --- Step 2b: 人物差し替え+ポーズ変更 (model: %s) ---", STEP1B_MODEL)
    step2b_output = output_dir / "step2b_final.png"
    step2b_result = sdk_generate_image(
        client,
        model=STEP1B_MODEL,
        contents=[
            load_image_part(CHARACTER_REF),  # image 1: キャラ参照
            load_image_part(step1_output),  # image 2: 背景変更+テキスト除去済み画像
            generated_prompt,  # Step 2a で生成されたプロンプト
        ],
        output_path=step2b_output,
        step_name="step2b_character_pose",
    )
    pipeline_result["steps"]["step2b"] = step2b_result

    if step2b_result["status"] != "success":
        pipeline_result["status"] = "failed_at_step2b"
        return pipeline_result
    pipeline_result["cost_usd"] += 0.04

    return pipeline_result


def print_dry_run(seed_images: list[str]) -> None:
    """ドライラン: パイプライン構成・コスト見積もりを表示する."""
    logger.info("=" * 80)
    logger.info("Phase B-1 v3: 複合編集 — 段階的パイプライン検証 — ドライラン")
    logger.info("=" * 80)
    logger.info("")
    logger.info("パイプライン構成（v3: 背景変更を最上流に配置）:")
    logger.info("  Step 0: 背景変更               — %s", STEP2_MODEL)
    logger.info("    プロンプト: %s", BG_CHANGE_PROMPT)
    logger.info("    入力: 元seed（実写） + 背景参照（2枚のみ）")
    logger.info("")
    logger.info("  Step 1: テキスト除去           — %s", STEP0_MODEL)
    logger.info("    プロンプト: %s", STEP0_PROMPT)
    logger.info("    入力: Step 0 出力 1枚")
    logger.info("")
    logger.info("  Step 2a: Flash 分析            — %s", STEP1A_MODEL)
    logger.info("    メタプロンプト:")
    for line in build_step1a_meta_prompt().split("\n"):
        logger.info("      %s", line)
    logger.info("    入力: Step 1 出力 1枚")
    logger.info("")
    logger.info("  Step 2b: 人物差し替え+ポーズ   — %s", STEP1B_MODEL)
    logger.info("    プロンプト: (Step 2a で動的生成)")
    logger.info("    入力: キャラ参照 + Step 1 出力 + Step 2a プロンプト")
    logger.info("")
    logger.info("-" * 60)
    logger.info("参照画像:")
    logger.info("  キャラ参照: %s", CHARACTER_REF)
    logger.info("  背景参照:   %s", BACKGROUND_REF)
    logger.info("Seed 画像: %s", [str(SEED_CAPTURE_DIR / s) for s in seed_images])
    logger.info("")
    logger.info("コスト:")
    logger.info("  seed 1枚あたり: $%.2f", estimate_cost_per_seed())
    logger.info("  合計 (%d seed): $%.2f", len(seed_images), estimate_cost_per_seed() * len(seed_images))
    logger.info("=" * 80)


def main() -> None:
    args = parse_args()

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
        print_dry_run(seed_images)
        return

    # API キー取得 & クライアント作成
    api_key = get_gemini_api_key()
    client = genai.Client(api_key=api_key)

    total_cost = estimate_cost_per_seed() * len(seed_images)
    logger.info("=" * 80)
    logger.info(
        "Phase B-1 実験開始: %d seed, 推定コスト: $%.2f",
        len(seed_images), total_cost,
    )
    logger.info("=" * 80)

    all_results: list[dict] = []

    for i, seed_name in enumerate(seed_images, 1):
        seed_path = SEED_CAPTURE_DIR / seed_name
        logger.info("")
        logger.info("=" * 60)
        logger.info("[%d/%d] seed=%s", i, len(seed_images), seed_name)
        logger.info("=" * 60)

        try:
            result = run_pipeline(client, seed_name, seed_path)
        except Exception:
            logger.exception("    予期しないエラー")
            result = {
                "seed": seed_name,
                "status": "failed",
                "error": "unexpected exception",
                "steps": {},
                "cost_usd": 0.0,
            }

        all_results.append(result)

    # 実験ログ保存
    log_path = GENERATED_DIR / "experiment_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "experiment": "phase_b1_composite_editing_pipeline",
        "pipeline": [
            {"step": "step0", "task": "background_change", "model": STEP2_MODEL},
            {"step": "step1", "task": "text_removal", "model": STEP0_MODEL},
            {"step": "step2a", "task": "flash_analysis", "model": STEP1A_MODEL},
            {"step": "step2b", "task": "character_swap_pose_change", "model": STEP1B_MODEL},
        ],
        "aspect_ratio": ASPECT_RATIO,
        "sdk": "google-genai",
        "timestamp": datetime.now().isoformat(),
        "seed_images": seed_images,
        "character_ref": str(CHARACTER_REF),
        "background_ref": str(BACKGROUND_REF),
        "prompts": {
            "step0_bg_change": BG_CHANGE_PROMPT,
            "step1_text_removal": STEP0_PROMPT,
            "step2a_meta": build_step1a_meta_prompt(),
        },
        "results": all_results,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    logger.info("")
    logger.info("実験ログを保存しました: %s", log_path)

    # サマリ
    logger.info("=" * 80)
    logger.info("Phase B-1 実験結果サマリ:")
    success = sum(1 for r in all_results if r["status"] == "success")
    failed = sum(1 for r in all_results if r["status"] != "success")
    actual_cost = sum(r.get("cost_usd", 0) for r in all_results)
    logger.info("  パイプライン完走: %d/%d", success, len(all_results))
    logger.info("  失敗: %d", failed)
    logger.info("  実コスト: $%.2f", actual_cost)

    # seed 別サマリ
    logger.info("")
    logger.info("seed 別:")
    for r in all_results:
        status_icon = "OK" if r["status"] == "success" else "NG"
        logger.info(
            "  [%s] %s — ステータス: %s, コスト: $%.2f",
            status_icon, r["seed"], r["status"], r.get("cost_usd", 0),
        )
        if r["status"] != "success":
            logger.info("    失敗ステップ: %s", r["status"])

    # Step 2a 生成プロンプト一覧
    logger.info("")
    logger.info("Step 2a 生成プロンプト一覧:")
    for r in all_results:
        step2a = r.get("steps", {}).get("step2a", {})
        logger.info("  [%s]:", r["seed"])
        if step2a.get("generated_text"):
            for line in step2a["generated_text"].split("\n"):
                logger.info("    %s", line)
        else:
            logger.info("    (生成なし)")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
