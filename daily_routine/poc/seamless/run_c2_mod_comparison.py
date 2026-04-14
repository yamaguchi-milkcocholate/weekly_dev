"""C2-R2-MOD 改善検証 — modification 反映度の比較.

現行 C2-R2-MOD v1 vs 案A (v2) vs 案B (2パス) を
3種類の modification（画角変更・雰囲気変更・オブジェクト追加）で比較する。

検証パターン: 3方式 × 3 modification = 9パターン

Usage:
    uv run python poc/seamless/run_c2_mod_comparison.py --dry-run
    uv run python poc/seamless/run_c2_mod_comparison.py
    uv run python poc/seamless/run_c2_mod_comparison.py --methods v1,v2
    uv run python poc/seamless/run_c2_mod_comparison.py --mods angle
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from config_c2 import (
    ASPECT_RATIO,
    C2R2_PROMPT,
    PRO_IMAGE_MODEL,
)
from dotenv import load_dotenv
from google import genai
from google.genai.types import GenerateContentConfig, ImageConfig, Part

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "c2_mod_comparison"
COST_PER_IMAGE_GEN = 0.04

# --- 入力画像 ---
REFERENCE_IMAGE = (
    Path(__file__).parent.parent.parent
    / "outputs" / "projects" / "coffee-pr" / "assets" / "reference"
    / "environments" / "workspace.png"
)

# =============================================================================
# Modification 定義
# =============================================================================

MODIFICATIONS: dict[str, str] = {
    "angle": (
        "View the workspace from the back sofa, looking toward the desk and "
        "monitor from behind. The camera is positioned at the sofa seating level, "
        "showing the back of the desk chair and the monitor screen from a distance. "
        "Keep the moody, dark-toned atmosphere."
    ),
    "mood": (
        "Change the lighting to bright morning sunlight streaming through the "
        "window blinds. Warm golden light fills the room, creating long soft "
        "shadows across the desk. The overall mood shifts from dark and moody "
        "to bright and energetic."
    ),
    "object": (
        "Add a second curved monitor on the desk, a professional studio "
        "microphone on a boom arm to the left, and a ring light behind the "
        "monitors. Keep the same dark moody workspace atmosphere."
    ),
}

# =============================================================================
# プロンプトテンプレート
# =============================================================================


def build_v1_prompt(modification: str) -> str:
    """現行 C2-R2-MOD v1: ベースプロンプト末尾に modification を追加."""
    return f"{C2R2_PROMPT}\n{modification}"


def build_v2_prompt(modification: str) -> str:
    """案A: C2-R2-MOD v2: modification 優先のベースプロンプト."""
    return (
        "Image 1 shows a reference photo of an environment (ignore any people in it).\n"
        "Using this as reference, generate a new image of the same type of environment\n"
        "with the following modifications applied:\n"
        f"{modification}\n"
        "Base requirements:\n"
        "- Remove all people. The scene must have NO people, completely empty.\n"
        "- Unless the modification specifies otherwise, keep the same color palette,\n"
        "  atmosphere, and lighting mood as the reference.\n"
        "- Photo-realistic, natural lighting."
    )


# =============================================================================
# SDK ユーティリティ (run_phase_c2.py と同構造)
# =============================================================================


def load_image_part(image_path: Path) -> Part:
    """画像ファイルを SDK の Part に変換する."""
    data = image_path.read_bytes()
    suffix = image_path.suffix.lstrip(".")
    mime = f"image/{suffix}" if suffix not in ("jpg", "jpeg") else "image/jpeg"
    return Part.from_bytes(data=data, mime_type=mime)


def sdk_generate_image(
    client: genai.Client,
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
            "  SDK リクエスト送信中... (attempt %d/%d)",
            attempt, max_retries,
        )
        try:
            response = client.models.generate_content(
                model=PRO_IMAGE_MODEL,
                contents=contents,
                config=config,
            )
            break
        except Exception as e:
            last_error = e
            error_str = str(e)
            if "500" in error_str or "503" in error_str or "timeout" in error_str.lower():
                logger.warning(
                    "  サーバーエラー/タイムアウト: %s, %d秒後にリトライ...",
                    error_str[:200], 10 * attempt,
                )
                time.sleep(10 * attempt)
            else:
                logger.error("  API エラー: %s", error_str[:500])
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
        logger.info("  テキスト応答: %s", text_response[:200])

    if image_data is None:
        logger.error("  画像が生成されませんでした")
        return {
            "status": "failed",
            "error": "No image in response",
            "step": step_name,
            "text_response": text_response,
        }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_data)
    logger.info("  画像を保存しました: %s (%d bytes)", output_path, len(image_data))

    return {
        "status": "success",
        "output_path": str(output_path),
        "step": step_name,
        "text_response": text_response,
        "image_size_bytes": len(image_data),
    }


# =============================================================================
# 検証メソッド
# =============================================================================


def run_v1(
    client: genai.Client,
    mod_key: str,
    modification: str,
    output_dir: Path,
) -> dict:
    """現行 C2-R2-MOD v1."""
    prompt = build_v1_prompt(modification)
    label = f"v1_{mod_key}"
    logger.info("--- [v1] %s ---", mod_key)

    # プロンプト保存
    (output_dir / f"{label}_prompt.txt").write_text(prompt, encoding="utf-8")

    result = sdk_generate_image(
        client,
        contents=[load_image_part(REFERENCE_IMAGE), prompt],
        output_path=output_dir / f"{label}.png",
        step_name=label,
    )
    return {
        "method": "v1",
        "modification": mod_key,
        "result": result,
        "cost_usd": COST_PER_IMAGE_GEN if result["status"] == "success" else 0.0,
    }


def run_v2(
    client: genai.Client,
    mod_key: str,
    modification: str,
    output_dir: Path,
) -> dict:
    """案A: C2-R2-MOD v2."""
    prompt = build_v2_prompt(modification)
    label = f"v2_{mod_key}"
    logger.info("--- [v2] %s ---", mod_key)

    (output_dir / f"{label}_prompt.txt").write_text(prompt, encoding="utf-8")

    result = sdk_generate_image(
        client,
        contents=[load_image_part(REFERENCE_IMAGE), prompt],
        output_path=output_dir / f"{label}.png",
        step_name=label,
    )
    return {
        "method": "v2",
        "modification": mod_key,
        "result": result,
        "cost_usd": COST_PER_IMAGE_GEN if result["status"] == "success" else 0.0,
    }


def run_2pass(
    client: genai.Client,
    mod_key: str,
    modification: str,
    output_dir: Path,
) -> dict:
    """案B: 2パス（環境抽出 → modification 適用）."""
    label = f"2pass_{mod_key}"
    logger.info("--- [2pass] %s ---", mod_key)

    # Step 1: C2-R2 通常（人物除去のみ）
    logger.info("  Step 1: C2-R2 通常（人物除去）")
    step1_path = output_dir / f"{label}_step1_clean.png"

    # Step 1 の出力が既にあればスキップ（他の mod で既に生成済みの場合）
    clean_path = output_dir / "2pass_step1_clean.png"
    if clean_path.exists():
        logger.info("  Step 1 スキップ（既存の clean 画像を再利用）: %s", clean_path)
        step1_result = {"status": "success", "output_path": str(clean_path), "reused": True}
        step1_cost = 0.0
    else:
        step1_prompt = C2R2_PROMPT
        (output_dir / "2pass_step1_prompt.txt").write_text(step1_prompt, encoding="utf-8")

        step1_result = sdk_generate_image(
            client,
            contents=[load_image_part(REFERENCE_IMAGE), step1_prompt],
            output_path=clean_path,
            step_name=f"{label}_step1",
        )
        step1_cost = COST_PER_IMAGE_GEN if step1_result["status"] == "success" else 0.0

    if step1_result["status"] != "success":
        return {
            "method": "2pass",
            "modification": mod_key,
            "result": step1_result,
            "cost_usd": step1_cost,
        }

    # Step 2: modification 適用
    logger.info("  Step 2: modification 適用")
    step2_prompt = (
        "Image 1 shows an environment.\n"
        "Generate a modified version of this environment with the following changes:\n"
        f"{modification}\n"
        "Keep all other aspects of the environment unchanged.\n"
        "The scene must have NO people, completely empty.\n"
        "Photo-realistic, natural lighting."
    )
    (output_dir / f"{label}_step2_prompt.txt").write_text(step2_prompt, encoding="utf-8")

    step2_result = sdk_generate_image(
        client,
        contents=[load_image_part(clean_path), step2_prompt],
        output_path=output_dir / f"{label}.png",
        step_name=f"{label}_step2",
    )
    step2_cost = COST_PER_IMAGE_GEN if step2_result["status"] == "success" else 0.0

    return {
        "method": "2pass",
        "modification": mod_key,
        "result": step2_result,
        "step1": step1_result,
        "cost_usd": step1_cost + step2_cost,
    }


# =============================================================================
# メイン
# =============================================================================

METHOD_RUNNERS = {
    "v1": run_v1,
    "v2": run_v2,
    "2pass": run_2pass,
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="C2-R2-MOD 改善検証")
    parser.add_argument(
        "--methods",
        type=str,
        default=None,
        help="実行する方式をカンマ区切りで指定 (v1,v2,2pass)。指定なしで全方式",
    )
    parser.add_argument(
        "--mods",
        type=str,
        default=None,
        help="実行する modification をカンマ区切りで指定 (angle,mood,object)。指定なしで全種類",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="コスト見積もりのみ（API 呼び出しなし）",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    # 方式の解決
    if args.methods:
        methods = [m.strip().lower() for m in args.methods.split(",")]
        for m in methods:
            if m not in METHOD_RUNNERS:
                logger.error("未定義の方式: %s (利用可能: %s)", m, list(METHOD_RUNNERS.keys()))
                sys.exit(1)
    else:
        methods = list(METHOD_RUNNERS.keys())

    # modification の解決
    if args.mods:
        mod_keys = [m.strip().lower() for m in args.mods.split(",")]
        for m in mod_keys:
            if m not in MODIFICATIONS:
                logger.error("未定義の modification: %s (利用可能: %s)", m, list(MODIFICATIONS.keys()))
                sys.exit(1)
    else:
        mod_keys = list(MODIFICATIONS.keys())

    # 参照画像の存在確認
    if not REFERENCE_IMAGE.exists():
        logger.error("参照画像が見つかりません: %s", REFERENCE_IMAGE)
        sys.exit(1)

    # コスト見積もり
    n_patterns = len(methods) * len(mod_keys)
    # 2pass の Step 1 は1回のみ（再利用）
    n_api_calls = 0
    for m in methods:
        if m == "2pass":
            n_api_calls += 1 + len(mod_keys)  # Step1(1回) + Step2(mod数)
        else:
            n_api_calls += len(mod_keys)
    estimated_cost = n_api_calls * COST_PER_IMAGE_GEN

    logger.info("=" * 70)
    logger.info("C2-R2-MOD 改善検証")
    logger.info("=" * 70)
    logger.info("参照画像: %s", REFERENCE_IMAGE)
    logger.info("方式: %s", methods)
    logger.info("modification: %s", mod_keys)
    logger.info("パターン数: %d", n_patterns)
    logger.info("API コール数: %d", n_api_calls)
    logger.info("推定コスト: $%.2f", estimated_cost)
    logger.info("=" * 70)

    if args.dry_run:
        logger.info("ドライラン完了")
        # プロンプトプレビュー
        for mod_key in mod_keys:
            modification = MODIFICATIONS[mod_key]
            logger.info("")
            logger.info("--- modification: %s ---", mod_key)
            if "v1" in methods:
                logger.info("[v1] プロンプト:")
                logger.info("  %s", build_v1_prompt(modification).replace("\n", "\n  "))
            if "v2" in methods:
                logger.info("[v2] プロンプト:")
                logger.info("  %s", build_v2_prompt(modification).replace("\n", "\n  "))
        return

    # API クライアント初期化
    load_dotenv()
    api_key = os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI")
    if not api_key:
        logger.error("DAILY_ROUTINE_API_KEY_GOOGLE_AI が環境変数に設定されていません")
        sys.exit(1)
    client = genai.Client(api_key=api_key)

    # 出力ディレクトリ
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = GENERATED_DIR / timestamp
    output_dir.mkdir(parents=True, exist_ok=True)
    logger.info("出力先: %s", output_dir)

    # 実行
    results = []
    total_cost = 0.0

    for method in methods:
        runner = METHOD_RUNNERS[method]
        for mod_key in mod_keys:
            modification = MODIFICATIONS[mod_key]
            logger.info("")
            logger.info("=== %s × %s ===", method, mod_key)

            result = runner(client, mod_key, modification, output_dir)
            results.append(result)
            total_cost += result["cost_usd"]

            status = result["result"]["status"] if "result" in result else "unknown"
            logger.info("  → %s (cost: $%.2f)", status, result["cost_usd"])

            # API レート制限対策
            time.sleep(2)

    # サマリ
    logger.info("")
    logger.info("=" * 70)
    logger.info("検証完了")
    logger.info("=" * 70)

    success_count = sum(
        1 for r in results
        if r.get("result", {}).get("status") == "success"
    )
    logger.info("成功: %d / %d", success_count, len(results))
    logger.info("合計コスト: $%.2f", total_cost)
    logger.info("出力先: %s", output_dir)

    # 結果をまとめて表示
    logger.info("")
    logger.info("--- 結果一覧 ---")
    for r in results:
        status = r.get("result", {}).get("status", "unknown")
        output = r.get("result", {}).get("output_path", "-")
        logger.info(
            "  [%s] %s: %s → %s",
            r["method"], r["modification"], status, Path(output).name if output != "-" else "-",
        )

    # ログ保存
    log_path = output_dir / "experiment_log.json"
    log_data = {
        "timestamp": timestamp,
        "reference_image": str(REFERENCE_IMAGE),
        "methods": methods,
        "modifications": mod_keys,
        "total_cost_usd": total_cost,
        "results": results,
    }
    log_path.write_text(json.dumps(log_data, indent=2, default=str), encoding="utf-8")
    logger.info("ログ保存: %s", log_path)


if __name__ == "__main__":
    main()
