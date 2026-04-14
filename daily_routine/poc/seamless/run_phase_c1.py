"""Phase C-1: キャラクター生成 — 検証スクリプト.

オリジナルキャラクターを生成する検証。

検証パターン:
  C1-T:  テキストのみ生成（Flash分析 → Pro画像生成、参照画像なし）
  C1-R1: 参照画像 + 摂動指示（直接編集型）
  C1-R2: 2段階（Flash分析 → 参照画像付きPro生成）
  C1-F1: 複数画像 + 融合指示（直接編集型）— clothing別
  C1-F2: 2段階（Flash分析 → 複数画像付きPro生成）— clothing別
  C1-ID: Identity Block 自動生成 + 再現テスト

Usage:
    uv run python poc/seamless/run_phase_c1.py --dry-run
    uv run python poc/seamless/run_phase_c1.py --patterns C1-T,C1-R1
    uv run python poc/seamless/run_phase_c1.py --patterns C1-F1 --clothing 1,2
    uv run python poc/seamless/run_phase_c1.py --patterns C1-ID --id-source generated/phase_c1/c1-r1/character.png
    uv run python poc/seamless/run_phase_c1.py --multiangle --clothing 4
    uv run python poc/seamless/run_phase_c1.py
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from config_c1 import (
    ANGLE_DEFINITIONS,
    ASPECT_RATIO,
    C1F1_PROMPT,
    C1F2_GENERATION_TEMPLATE,
    C1F2_META_PROMPT,
    C1F2MA_GENERATION_TEMPLATE,
    C1ID_ANALYSIS_PROMPT,
    C1ID_REPRODUCTION_TEMPLATE,
    C1R1_PROMPT,
    C1R2_GENERATION_TEMPLATE,
    C1R2_META_PROMPT,
    C1T_FLASH_ANALYSIS_PROMPT,
    C1T_GENERATION_TEMPLATE,
    CLOTHING_IMAGES,
    GENERATED_DIR,
    MODEL_REF,
    PATTERNS,
    PRO_IMAGE_MODEL,
    estimate_cost_per_pattern,
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
        description="Phase C-1: キャラクター生成 — 検証",
    )
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="実行するパターンをカンマ区切りで指定 (例: C1-T,C1-R1)。指定なしでC1-ID以外の全パターン",
    )
    parser.add_argument(
        "--clothing",
        type=str,
        default=None,
        help="C1-F1/F2 で使用する clothing 番号をカンマ区切りで指定 (例: 1,2)。指定なしで全clothing",
    )
    parser.add_argument(
        "--id-source",
        type=str,
        default=None,
        help="C1-ID の入力画像パス。指定なしの場合 C1-ID はスキップ",
    )
    parser.add_argument(
        "--multiangle",
        action="store_true",
        help="C1-F2 マルチアングル生成モード（正面・側面・背面）。--clothing と組み合わせ",
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
    """SDK でテキストを生成する（リトライ付き、temperature=0 で決定的出力）."""
    config = GenerateContentConfig(
        response_modalities=["TEXT"],
        temperature=0.0,
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


# =============================================================================
# パターン別実行関数
# =============================================================================


def run_c1t(
    client: genai.Client,
    output_dir: Path,
) -> dict:
    """C1-T: テキストのみ生成（Flash分析 → Pro画像生成）."""
    steps = {}

    # Step 0: Flash が model_1.png を分析してキャラクター記述を生成
    logger.info("    --- C1-T Step 0: Flash キャラクター分析 ---")
    flash_result = sdk_generate_text(
        client,
        model=PATTERNS["C1-T"]["steps"][0]["model"],
        contents=[
            load_image_part(MODEL_REF),
            C1T_FLASH_ANALYSIS_PROMPT,
        ],
        step_name="c1t_flash_analysis",
    )
    steps["flash_analysis"] = flash_result

    if flash_result["status"] != "success":
        return {"steps": steps, "status": "failed_at_flash_analysis", "cost_usd": 0.0}

    character_description = flash_result["generated_text"]
    logger.info("      Flash キャラ記述:\n%s", character_description)

    # テキスト保存
    prompt_path = output_dir / "c1t_character_description.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(character_description, encoding="utf-8")

    # Step 1: Pro がテキストのみで画像生成（参照画像なし）
    generation_prompt = C1T_GENERATION_TEMPLATE.replace(
        "{{character_description}}", character_description
    )
    logger.info("    --- C1-T Step 1: Pro テキストベース画像生成 ---")

    # 生成プロンプト保存
    gen_prompt_path = output_dir / "c1t_generation_prompt.txt"
    gen_prompt_path.write_text(generation_prompt, encoding="utf-8")

    image_result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[generation_prompt],  # テキストのみ、参照画像なし
        output_path=output_dir / "c1t_character.png",
        step_name="c1t_text_generation",
    )
    steps["text_generation"] = image_result

    cost = PATTERNS["C1-T"]["steps"][0]["cost"]
    if image_result["status"] == "success":
        cost += PATTERNS["C1-T"]["steps"][1]["cost"]

    return {
        "steps": steps,
        "status": image_result["status"],
        "cost_usd": cost,
        "character_description": character_description,
    }


def run_c1r1(
    client: genai.Client,
    output_dir: Path,
) -> dict:
    """C1-R1: 参照画像 + 摂動指示（直接編集型、1パス）."""
    logger.info("    --- C1-R1: 参照画像 + 摂動指示（直接編集型） ---")

    result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(MODEL_REF),  # image 1: 参照キャラクター
            C1R1_PROMPT,
        ],
        output_path=output_dir / "c1r1_character.png",
        step_name="c1r1_perturbation_generation",
    )

    return {
        "steps": {"perturbation_generation": result},
        "status": result["status"],
        "cost_usd": PATTERNS["C1-R1"]["steps"][0]["cost"] if result["status"] == "success" else 0.0,
    }


def run_c1r2(
    client: genai.Client,
    output_dir: Path,
) -> dict:
    """C1-R2: 2段階（Flash分析 → 参照画像付きPro生成）."""
    steps = {}

    # Step 1: Flash が参照画像を分析
    logger.info("    --- C1-R2 Step 1: Flash キャラクター分析 ---")
    flash_result = sdk_generate_text(
        client,
        model=PATTERNS["C1-R2"]["steps"][0]["model"],
        contents=[
            load_image_part(MODEL_REF),
            C1R2_META_PROMPT,
        ],
        step_name="c1r2_flash_analysis",
    )
    steps["flash_analysis"] = flash_result

    if flash_result["status"] != "success":
        return {"steps": steps, "status": "failed_at_flash_analysis", "cost_usd": 0.0}

    flash_description = flash_result["generated_text"]
    logger.info("      Flash 生成記述:\n%s", flash_description)

    # テキスト保存
    prompt_path = output_dir / "c1r2_flash_description.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(flash_description, encoding="utf-8")

    # Step 2: Pro が参照画像 + Flash記述で生成
    generation_prompt = C1R2_GENERATION_TEMPLATE.replace(
        "{{flash_description}}", flash_description
    )
    logger.info("    --- C1-R2 Step 2: Pro 参照画像付き生成 ---")

    gen_prompt_path = output_dir / "c1r2_generation_prompt.txt"
    gen_prompt_path.write_text(generation_prompt, encoding="utf-8")

    image_result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(MODEL_REF),  # image 1: 参照画像
            generation_prompt,
        ],
        output_path=output_dir / "c1r2_character.png",
        step_name="c1r2_reference_generation",
    )
    steps["reference_generation"] = image_result

    cost = PATTERNS["C1-R2"]["steps"][0]["cost"]
    if image_result["status"] == "success":
        cost += PATTERNS["C1-R2"]["steps"][1]["cost"]

    return {
        "steps": steps,
        "status": image_result["status"],
        "cost_usd": cost,
        "flash_description": flash_description,
    }


def run_c1f1(
    client: genai.Client,
    clothing_path: Path,
    output_dir: Path,
) -> dict:
    """C1-F1: 複数画像 + 融合指示（直接編集型、1パス）."""
    clothing_name = clothing_path.stem
    logger.info("    --- C1-F1: 融合生成（直接編集型）[%s] ---", clothing_name)

    result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(MODEL_REF),       # image 1: 人物参照
            load_image_part(clothing_path),    # image 2: 服装参照
            C1F1_PROMPT,
        ],
        output_path=output_dir / f"c1f1_{clothing_name}.png",
        step_name=f"c1f1_fusion_{clothing_name}",
    )

    return {
        "steps": {"fusion_generation": result},
        "status": result["status"],
        "cost_usd": PATTERNS["C1-F1"]["steps"][0]["cost"] if result["status"] == "success" else 0.0,
        "clothing": clothing_name,
    }


def run_c1f2(
    client: genai.Client,
    clothing_path: Path,
    output_dir: Path,
) -> dict:
    """C1-F2: 2段階（Flash分析 → 複数画像付きPro生成）."""
    clothing_name = clothing_path.stem
    steps = {}

    # Step 1: Flash が全画像を分析
    logger.info("    --- C1-F2 Step 1: Flash 融合分析 [%s] ---", clothing_name)
    flash_result = sdk_generate_text(
        client,
        model=PATTERNS["C1-F2"]["steps"][0]["model"],
        contents=[
            load_image_part(MODEL_REF),       # image 1: 人物参照
            load_image_part(clothing_path),    # image 2: 服装参照
            C1F2_META_PROMPT,
        ],
        step_name=f"c1f2_flash_analysis_{clothing_name}",
    )
    steps["flash_analysis"] = flash_result

    if flash_result["status"] != "success":
        return {
            "steps": steps,
            "status": "failed_at_flash_analysis",
            "cost_usd": 0.0,
            "clothing": clothing_name,
        }

    flash_description = flash_result["generated_text"]
    logger.info("      Flash 生成記述:\n%s", flash_description)

    # テキスト保存
    prompt_path = output_dir / f"c1f2_{clothing_name}_flash_description.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(flash_description, encoding="utf-8")

    # Step 2: Pro が参照画像 + Flash記述で生成
    generation_prompt = C1F2_GENERATION_TEMPLATE.replace(
        "{{flash_description}}", flash_description
    )

    gen_prompt_path = output_dir / f"c1f2_{clothing_name}_generation_prompt.txt"
    gen_prompt_path.write_text(generation_prompt, encoding="utf-8")

    logger.info("    --- C1-F2 Step 2: Pro 融合生成 [%s] ---", clothing_name)
    image_result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(MODEL_REF),       # image 1: 人物参照
            load_image_part(clothing_path),    # image 2: 服装参照
            generation_prompt,
        ],
        output_path=output_dir / f"c1f2_{clothing_name}.png",
        step_name=f"c1f2_fusion_{clothing_name}",
    )
    steps["fusion_generation"] = image_result

    cost = PATTERNS["C1-F2"]["steps"][0]["cost"]
    if image_result["status"] == "success":
        cost += PATTERNS["C1-F2"]["steps"][1]["cost"]

    return {
        "steps": steps,
        "status": image_result["status"],
        "cost_usd": cost,
        "clothing": clothing_name,
        "flash_description": flash_description,
    }


def run_c1f2_multiangle(
    client: genai.Client,
    clothing_path: Path,
    output_dir: Path,
) -> dict:
    """C1-F2-MA: マルチアングル生成（Flash分析1回 → Pro正面/側面/背面）."""
    clothing_name = clothing_path.stem
    steps = {}
    cost = 0.0

    # Step 1: Flash 融合分析（1回のみ、全アングル共通）
    logger.info("    --- C1-F2-MA Step 1: Flash 融合分析 [%s] ---", clothing_name)
    flash_result = sdk_generate_text(
        client,
        model=PATTERNS["C1-F2"]["steps"][0]["model"],
        contents=[
            load_image_part(MODEL_REF),
            load_image_part(clothing_path),
            C1F2_META_PROMPT,
        ],
        step_name=f"c1f2ma_flash_analysis_{clothing_name}",
    )
    steps["flash_analysis"] = flash_result

    if flash_result["status"] != "success":
        return {
            "steps": steps,
            "status": "failed_at_flash_analysis",
            "cost_usd": 0.0,
            "clothing": clothing_name,
        }

    flash_description = flash_result["generated_text"]
    cost += PATTERNS["C1-F2"]["steps"][0]["cost"]
    logger.info("      Flash 生成記述:\n%s", flash_description)

    prompt_path = output_dir / f"c1f2ma_{clothing_name}_flash_description.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(flash_description, encoding="utf-8")

    # Step 2: 各アングルで Pro 画像生成
    angle_results = {}
    for angle_key, angle_def in ANGLE_DEFINITIONS.items():
        generation_prompt = (
            C1F2MA_GENERATION_TEMPLATE
            .replace("{{flash_description}}", flash_description)
            .replace("{{angle_pose}}", angle_def["pose"])
        )

        logger.info(
            "    --- C1-F2-MA Step 2: Pro %s生成 [%s] ---",
            angle_def["name"], clothing_name,
        )

        gen_prompt_path = output_dir / f"c1f2ma_{clothing_name}_{angle_key}_prompt.txt"
        gen_prompt_path.write_text(generation_prompt, encoding="utf-8")

        image_result = sdk_generate_image(
            client,
            model=PRO_IMAGE_MODEL,
            contents=[
                load_image_part(MODEL_REF),
                load_image_part(clothing_path),
                generation_prompt,
            ],
            output_path=output_dir / f"c1f2ma_{clothing_name}_{angle_key}.png",
            step_name=f"c1f2ma_{angle_key}_{clothing_name}",
        )
        angle_results[angle_key] = image_result
        if image_result["status"] == "success":
            cost += PATTERNS["C1-F2"]["steps"][1]["cost"]

    steps["angle_results"] = angle_results

    # 全アングル成功判定
    success_count = sum(1 for r in angle_results.values() if r["status"] == "success")
    if success_count == len(ANGLE_DEFINITIONS):
        status = "success"
    elif success_count > 0:
        status = f"partial_{success_count}/{len(ANGLE_DEFINITIONS)}"
    else:
        status = "failed"

    return {
        "steps": steps,
        "status": status,
        "cost_usd": cost,
        "clothing": clothing_name,
        "flash_description": flash_description,
        "angles": list(ANGLE_DEFINITIONS.keys()),
    }


def run_c1id(
    client: genai.Client,
    source_image_path: Path,
    output_dir: Path,
) -> dict:
    """C1-ID: Identity Block 自動生成 + 再現テスト."""
    steps = {}

    # Step 1: Flash がキャラ画像を分析 → Identity Block
    logger.info("    --- C1-ID Step 1: Flash Identity Block 抽出 ---")
    flash_result = sdk_generate_text(
        client,
        model=PATTERNS["C1-ID"]["steps"][0]["model"],
        contents=[
            load_image_part(source_image_path),
            C1ID_ANALYSIS_PROMPT,
        ],
        step_name="c1id_identity_extraction",
    )
    steps["identity_extraction"] = flash_result

    if flash_result["status"] != "success":
        return {"steps": steps, "status": "failed_at_identity_extraction", "cost_usd": 0.0}

    identity_block = flash_result["generated_text"]
    logger.info("      Identity Block:\n%s", identity_block)

    # テキスト保存
    id_path = output_dir / "c1id_identity_block.txt"
    id_path.parent.mkdir(parents=True, exist_ok=True)
    id_path.write_text(identity_block, encoding="utf-8")

    # Step 2: Pro が Identity Block + 別ポーズで再現テスト
    reproduction_prompt = C1ID_REPRODUCTION_TEMPLATE.replace(
        "{{identity_block}}", identity_block
    )
    logger.info("    --- C1-ID Step 2: Pro 再現テスト ---")

    gen_prompt_path = output_dir / "c1id_reproduction_prompt.txt"
    gen_prompt_path.write_text(reproduction_prompt, encoding="utf-8")

    image_result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(source_image_path),  # image 1: 元キャラ画像
            reproduction_prompt,
        ],
        output_path=output_dir / "c1id_reproduction.png",
        step_name="c1id_reproduction_test",
    )
    steps["reproduction_test"] = image_result

    cost = PATTERNS["C1-ID"]["steps"][0]["cost"]
    if image_result["status"] == "success":
        cost += PATTERNS["C1-ID"]["steps"][1]["cost"]

    return {
        "steps": steps,
        "status": image_result["status"],
        "cost_usd": cost,
        "identity_block": identity_block,
        "source_image": str(source_image_path),
    }


# =============================================================================
# ドライラン
# =============================================================================


def print_dry_run(pattern_keys: list[str], clothing_indices: list[int]) -> None:
    """ドライラン: パターン構成・コスト見積もりを表示する."""
    logger.info("=" * 80)
    logger.info("Phase C-1: キャラクター生成 — ドライラン")
    logger.info("=" * 80)
    logger.info("")

    for key in pattern_keys:
        pattern = PATTERNS[key]
        logger.info("パターン %s: %s", key, pattern["name"])
        logger.info("  %s", pattern["description"])
        for i, step in enumerate(pattern["steps"]):
            logger.info("  Step %d: %s — %s (%s)", i + 1, step["task"], step["model"], step["type"])
        cost = estimate_cost_per_pattern(key)
        if key in ("C1-F1", "C1-F2"):
            logger.info(
                "  コスト: $%.2f/clothing × %d clothing = $%.2f",
                cost, len(clothing_indices), cost * len(clothing_indices),
            )
        else:
            logger.info("  コスト: $%.2f", cost)
        logger.info("")

    logger.info("-" * 60)
    logger.info("入力画像:")
    logger.info("  人物参照: %s", MODEL_REF)
    logger.info("  服装参照: %s", [str(CLOTHING_IMAGES[i]) for i in clothing_indices])
    logger.info("")

    # コスト合計
    total_cost = 0.0
    total_calls = 0
    for key in pattern_keys:
        base_cost = estimate_cost_per_pattern(key)
        base_calls = len(PATTERNS[key]["steps"])
        if key in ("C1-F1", "C1-F2"):
            total_cost += base_cost * len(clothing_indices)
            total_calls += base_calls * len(clothing_indices)
        else:
            total_cost += base_cost
            total_calls += base_calls

    logger.info("コスト合計:")
    logger.info(
        "  %d パターン, %d API コール, 推定 $%.2f",
        len(pattern_keys), total_calls, total_cost,
    )
    logger.info("=" * 80)


# =============================================================================
# メイン
# =============================================================================


def main() -> None:
    args = parse_args()

    # パターン解決
    if args.patterns:
        pattern_keys = [p.strip().upper() for p in args.patterns.split(",")]
        for key in pattern_keys:
            if key not in PATTERNS:
                logger.error("未定義のパターン: %s (利用可能: %s)", key, list(PATTERNS.keys()))
                sys.exit(1)
    else:
        # デフォルト: C1-ID 以外の全パターン
        pattern_keys = [k for k in PATTERNS if k != "C1-ID"]

    # Clothing 解決
    if args.clothing:
        clothing_indices = [int(c.strip()) - 1 for c in args.clothing.split(",")]
        for idx in clothing_indices:
            if idx < 0 or idx >= len(CLOTHING_IMAGES):
                logger.error(
                    "clothing 番号が範囲外: %d (1〜%d)", idx + 1, len(CLOTHING_IMAGES),
                )
                sys.exit(1)
    else:
        clothing_indices = list(range(len(CLOTHING_IMAGES)))

    # 入力ファイル存在確認
    if not MODEL_REF.exists():
        logger.error("人物参照画像が見つかりません: %s", MODEL_REF)
        sys.exit(1)

    for key in pattern_keys:
        if key in ("C1-F1", "C1-F2"):
            for idx in clothing_indices:
                if not CLOTHING_IMAGES[idx].exists():
                    logger.error("服装画像が見つかりません: %s", CLOTHING_IMAGES[idx])
                    sys.exit(1)

    # ドライラン
    if args.dry_run:
        if args.multiangle:
            n_clothing = len(clothing_indices)
            n_angles = len(ANGLE_DEFINITIONS)
            # Flash 1回 + Pro × アングル数 per clothing
            cost = n_clothing * (0.01 + 0.04 * n_angles)
            calls = n_clothing * (1 + n_angles)
            logger.info("=" * 80)
            logger.info("C1-F2-MA マルチアングル生成 — ドライラン")
            logger.info("  clothing: %s", [str(CLOTHING_IMAGES[i].name) for i in clothing_indices])
            logger.info("  アングル: %s", list(ANGLE_DEFINITIONS.keys()))
            logger.info("  %d clothing × (Flash 1回 + Pro %d回) = %d API コール, $%.2f",
                        n_clothing, n_angles, calls, cost)
            logger.info("=" * 80)
        else:
            print_dry_run(pattern_keys, clothing_indices)
        return

    # API キー取得 & クライアント作成
    api_key = get_gemini_api_key()
    client = genai.Client(api_key=api_key)

    # --- マルチアングルモード ---
    if args.multiangle:
        for idx in clothing_indices:
            if not CLOTHING_IMAGES[idx].exists():
                logger.error("服装画像が見つかりません: %s", CLOTHING_IMAGES[idx])
                sys.exit(1)

        n_clothing = len(clothing_indices)
        n_angles = len(ANGLE_DEFINITIONS)
        cost_est = n_clothing * (0.01 + 0.04 * n_angles)
        logger.info("=" * 80)
        logger.info(
            "C1-F2-MA マルチアングル生成 — %d clothing × %d angles, 推定: $%.2f",
            n_clothing, n_angles, cost_est,
        )
        logger.info("=" * 80)

        all_results: list[dict] = []
        for idx in clothing_indices:
            clothing_path = CLOTHING_IMAGES[idx]
            output_dir = GENERATED_DIR / "c1-f2-ma"
            result = run_c1f2_multiangle(client, clothing_path, output_dir)
            result["pattern"] = "C1-F2-MA"
            all_results.append(result)

        # ログ保存
        log_path = GENERATED_DIR / "experiment_log_multiangle.json"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        log_data = {
            "experiment": "phase_c1_multiangle",
            "description": "C1-F2 マルチアングル生成（正面・側面・背面）",
            "angles": {k: v for k, v in ANGLE_DEFINITIONS.items()},
            "timestamp": datetime.now().isoformat(),
            "model_ref": str(MODEL_REF),
            "clothing_images": [str(CLOTHING_IMAGES[i]) for i in clothing_indices],
            "results": all_results,
        }
        log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
        logger.info("")
        logger.info("実験ログを保存しました: %s", log_path)

        # サマリ
        logger.info("=" * 80)
        logger.info("C1-F2-MA マルチアングル — 結果サマリ:")
        actual_cost = sum(r.get("cost_usd", 0) for r in all_results)
        logger.info("  実コスト: $%.2f", actual_cost)
        for r in all_results:
            status_icon = "OK" if r["status"] == "success" else "NG"
            logger.info("  [%s] %s — %s, $%.2f", status_icon, r.get("clothing", "?"), r["status"], r.get("cost_usd", 0))
        logger.info("=" * 80)
        return

    # コスト見積もり
    total_cost_estimate = 0.0
    for key in pattern_keys:
        base_cost = estimate_cost_per_pattern(key)
        if key in ("C1-F1", "C1-F2"):
            total_cost_estimate += base_cost * len(clothing_indices)
        else:
            total_cost_estimate += base_cost

    logger.info("=" * 80)
    logger.info(
        "Phase C-1: キャラクター生成 — %d パターン, 推定コスト: $%.2f",
        len(pattern_keys), total_cost_estimate,
    )
    logger.info("=" * 80)

    all_results: list[dict] = []

    for pattern_key in pattern_keys:
        logger.info("")
        logger.info("=" * 60)
        logger.info("[%s] %s", pattern_key, PATTERNS[pattern_key]["name"])
        logger.info("=" * 60)

        output_dir = GENERATED_DIR / pattern_key.lower()

        if pattern_key == "C1-T":
            result = run_c1t(client, output_dir)
            result["pattern"] = pattern_key
            all_results.append(result)

        elif pattern_key == "C1-R1":
            result = run_c1r1(client, output_dir)
            result["pattern"] = pattern_key
            all_results.append(result)

        elif pattern_key == "C1-R2":
            result = run_c1r2(client, output_dir)
            result["pattern"] = pattern_key
            all_results.append(result)

        elif pattern_key == "C1-F1":
            for idx in clothing_indices:
                clothing_path = CLOTHING_IMAGES[idx]
                result = run_c1f1(client, clothing_path, output_dir)
                result["pattern"] = pattern_key
                all_results.append(result)

        elif pattern_key == "C1-F2":
            for idx in clothing_indices:
                clothing_path = CLOTHING_IMAGES[idx]
                result = run_c1f2(client, clothing_path, output_dir)
                result["pattern"] = pattern_key
                all_results.append(result)

        elif pattern_key == "C1-ID":
            if not args.id_source:
                logger.warning("C1-ID: --id-source が指定されていないためスキップ")
                continue
            source_path = Path(args.id_source)
            if not source_path.exists():
                logger.error("C1-ID: 入力画像が見つかりません: %s", source_path)
                continue
            result = run_c1id(client, source_path, output_dir)
            result["pattern"] = pattern_key
            all_results.append(result)

    # 実験ログ保存
    log_path = GENERATED_DIR / "experiment_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "experiment": "phase_c1_character_generation",
        "description": "オリジナルキャラクター生成の検証",
        "patterns": {
            k: {
                "name": PATTERNS[k]["name"],
                "description": PATTERNS[k]["description"],
                "steps": [s["task"] for s in PATTERNS[k]["steps"]],
            }
            for k in pattern_keys
        },
        "aspect_ratio": ASPECT_RATIO,
        "sdk": "google-genai",
        "timestamp": datetime.now().isoformat(),
        "model_ref": str(MODEL_REF),
        "clothing_images": [str(CLOTHING_IMAGES[i]) for i in clothing_indices],
        "results": all_results,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    logger.info("")
    logger.info("実験ログを保存しました: %s", log_path)

    # サマリ
    logger.info("=" * 80)
    logger.info("Phase C-1: キャラクター生成 — 結果サマリ:")
    success = sum(1 for r in all_results if r["status"] == "success")
    actual_cost = sum(r.get("cost_usd", 0) for r in all_results)
    logger.info("  成功: %d/%d", success, len(all_results))
    logger.info("  実コスト: $%.2f", actual_cost)
    logger.info("")

    for r in all_results:
        status_icon = "OK" if r["status"] == "success" else "NG"
        clothing_info = f" [{r['clothing']}]" if "clothing" in r else ""
        logger.info(
            "  [%s] %s%s — %s, $%.2f",
            status_icon, r["pattern"], clothing_info, r["status"], r.get("cost_usd", 0),
        )
        # Flash 生成テキストがあれば表示
        for key in ("character_description", "flash_description", "identity_block"):
            if r.get(key):
                logger.info("    %s:", key)
                for line in r[key].split("\n")[:5]:
                    logger.info("      %s", line)
                if len(r[key].split("\n")) > 5:
                    logger.info("      ... (以下略)")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
