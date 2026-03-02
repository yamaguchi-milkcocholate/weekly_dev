"""Phase C-3: キャラ × 環境融合 — 検証スクリプト.

C-1で生成したキャラクターとC-2で生成した環境を融合し、
キャラクターが環境に自然に存在するシーン（keyframe）を生成する検証。

検証パターン:
  C3-I1: S3M踏襲（最小指示Flash分析 → Pro生成）— 画像入力型
  C3-I2: テキストリッチ型（コンテキスト付きFlash分析 → Pro生成）— 画像入力型
  C3-T:  テキスト環境型（環境画像なし、テキスト記述のみ）

Usage:
    uv run python poc/seamless/run_phase_c3.py --dry-run
    uv run python poc/seamless/run_phase_c3.py --patterns C3-I1,C3-I2,C3-T
    uv run python poc/seamless/run_phase_c3.py --patterns C3-I1 --env env_1 --pose standing_confident
    uv run python poc/seamless/run_phase_c3.py
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from config_c3 import (
    ASPECT_RATIO,
    C3I1_FLASH_META_PROMPT,
    C3I1_GENERATION_TEMPLATE,
    C3I2_FLASH_META_PROMPT,
    C3I2_GENERATION_TEMPLATE,
    C3T_PROMPT,
    CHARACTER_IMAGE_FRONT,
    ENV_DESCRIPTIONS,
    ENV_IMAGES,
    FLASH_TEXT_MODEL,
    GENERATED_DIR,
    IDENTITY_BLOCK,
    PATTERNS,
    POSES,
    PRO_IMAGE_MODEL,
    SCENARIO_CONTEXTS,
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
        description="Phase C-3: キャラ × 環境融合 — 検証",
    )
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="実行するパターンをカンマ区切りで指定 (例: C3-I1,C3-I2,C3-T)。指定なしで全パターン",
    )
    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help="使用する環境をカンマ区切りで指定 (例: env_1,env_2)。指定なしで全環境",
    )
    parser.add_argument(
        "--pose",
        type=str,
        default=None,
        help="使用するポーズをカンマ区切りで指定 (例: standing_confident,walking)。指定なしで全ポーズ",
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


def run_c3i1(
    client: genai.Client,
    env_key: str,
    pose_key: str,
    output_dir: Path,
) -> dict:
    """C3-I1: S3M踏襲（最小指示Flash分析 → Pro生成）."""
    prefix = f"c3i1_{env_key}_{pose_key}"
    steps = {}

    env_path = ENV_IMAGES[env_key]
    pose_instruction = POSES[pose_key]

    # Step 1: Flash がキャラ画像 + 環境画像を分析 → シーンプロンプト
    logger.info("    --- C3-I1 Step 1: Flash シーン分析 [%s / %s] ---", env_key, pose_key)

    meta_prompt = (
        C3I1_FLASH_META_PROMPT
        .replace("{{identity_block}}", IDENTITY_BLOCK)
        .replace("{{pose_instruction}}", pose_instruction)
    )

    flash_result = sdk_generate_text(
        client,
        model=FLASH_TEXT_MODEL,
        contents=[
            load_image_part(CHARACTER_IMAGE_FRONT),
            load_image_part(env_path),
            meta_prompt,
        ],
        step_name=f"{prefix}_flash_analysis",
    )
    steps["flash_analysis"] = flash_result

    if flash_result["status"] != "success":
        return {
            "steps": steps,
            "status": "failed_at_flash_analysis",
            "cost_usd": 0.0,
            "env": env_key,
            "pose": pose_key,
        }

    flash_prompt = flash_result["generated_text"]
    logger.info("      Flash 生成プロンプト:\n%s", flash_prompt)

    # テキスト保存
    flash_path = output_dir / f"{prefix}_flash_prompt.txt"
    flash_path.parent.mkdir(parents=True, exist_ok=True)
    flash_path.write_text(flash_prompt, encoding="utf-8")

    # Step 2: Pro がキャラ画像 + 環境画像 + Flash生成プロンプト で生成
    logger.info("    --- C3-I1 Step 2: Pro シーン画像生成 [%s / %s] ---", env_key, pose_key)

    generation_prompt = C3I1_GENERATION_TEMPLATE.replace("{{flash_prompt}}", flash_prompt)

    gen_prompt_path = output_dir / f"{prefix}_generation_prompt.txt"
    gen_prompt_path.write_text(generation_prompt, encoding="utf-8")

    image_result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(CHARACTER_IMAGE_FRONT),
            load_image_part(env_path),
            generation_prompt,
        ],
        output_path=output_dir / f"{prefix}.png",
        step_name=f"{prefix}_scene_generation",
    )
    steps["scene_generation"] = image_result

    cost = PATTERNS["C3-I1"]["steps"][0]["cost"]
    if image_result["status"] == "success":
        cost += PATTERNS["C3-I1"]["steps"][1]["cost"]

    return {
        "steps": steps,
        "status": image_result["status"],
        "cost_usd": cost,
        "env": env_key,
        "pose": pose_key,
        "flash_prompt": flash_prompt,
    }


def run_c3i2(
    client: genai.Client,
    env_key: str,
    pose_key: str,
    output_dir: Path,
) -> dict:
    """C3-I2: テキストリッチ型（コンテキスト付きFlash分析 → Pro生成）."""
    prefix = f"c3i2_{env_key}_{pose_key}"
    steps = {}

    env_path = ENV_IMAGES[env_key]
    env_description = ENV_DESCRIPTIONS[env_key]
    pose_instruction = POSES[pose_key]
    scenario_context = SCENARIO_CONTEXTS[env_key]

    # Step 1: Flash がキャラ画像 + 環境画像 + コンテキスト を分析
    logger.info("    --- C3-I2 Step 1: Flash コンテキスト付きシーン分析 [%s / %s] ---", env_key, pose_key)

    meta_prompt = (
        C3I2_FLASH_META_PROMPT
        .replace("{{identity_block}}", IDENTITY_BLOCK)
        .replace("{{env_description}}", env_description)
        .replace("{{scenario_context}}", scenario_context)
        .replace("{{pose_instruction}}", pose_instruction)
    )

    flash_result = sdk_generate_text(
        client,
        model=FLASH_TEXT_MODEL,
        contents=[
            load_image_part(CHARACTER_IMAGE_FRONT),
            load_image_part(env_path),
            meta_prompt,
        ],
        step_name=f"{prefix}_flash_analysis",
    )
    steps["flash_analysis"] = flash_result

    if flash_result["status"] != "success":
        return {
            "steps": steps,
            "status": "failed_at_flash_analysis",
            "cost_usd": 0.0,
            "env": env_key,
            "pose": pose_key,
        }

    flash_prompt = flash_result["generated_text"]
    logger.info("      Flash 生成プロンプト:\n%s", flash_prompt)

    # テキスト保存
    flash_path = output_dir / f"{prefix}_flash_prompt.txt"
    flash_path.parent.mkdir(parents=True, exist_ok=True)
    flash_path.write_text(flash_prompt, encoding="utf-8")

    # Step 2: Pro がキャラ画像 + 環境画像 + Flash生成プロンプト で生成
    logger.info("    --- C3-I2 Step 2: Pro シーン画像生成 [%s / %s] ---", env_key, pose_key)

    generation_prompt = C3I2_GENERATION_TEMPLATE.replace("{{flash_prompt}}", flash_prompt)

    gen_prompt_path = output_dir / f"{prefix}_generation_prompt.txt"
    gen_prompt_path.write_text(generation_prompt, encoding="utf-8")

    image_result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(CHARACTER_IMAGE_FRONT),
            load_image_part(env_path),
            generation_prompt,
        ],
        output_path=output_dir / f"{prefix}.png",
        step_name=f"{prefix}_scene_generation",
    )
    steps["scene_generation"] = image_result

    cost = PATTERNS["C3-I2"]["steps"][0]["cost"]
    if image_result["status"] == "success":
        cost += PATTERNS["C3-I2"]["steps"][1]["cost"]

    return {
        "steps": steps,
        "status": image_result["status"],
        "cost_usd": cost,
        "env": env_key,
        "pose": pose_key,
        "flash_prompt": flash_prompt,
    }


def run_c3t(
    client: genai.Client,
    env_key: str,
    pose_key: str,
    output_dir: Path,
) -> dict:
    """C3-T: テキスト環境型（環境画像なし、テキスト記述のみ）."""
    prefix = f"c3t_{env_key}_{pose_key}"

    env_description = ENV_DESCRIPTIONS[env_key]
    pose_instruction = POSES[pose_key]

    logger.info("    --- C3-T: テキスト環境シーン生成 [%s / %s] ---", env_key, pose_key)

    prompt = (
        C3T_PROMPT
        .replace("{{identity_block}}", IDENTITY_BLOCK)
        .replace("{{env_description}}", env_description)
        .replace("{{pose_instruction}}", pose_instruction)
    )

    # プロンプト保存
    prompt_path = output_dir / f"{prefix}_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(prompt, encoding="utf-8")

    image_result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(CHARACTER_IMAGE_FRONT),
            prompt,
        ],
        output_path=output_dir / f"{prefix}.png",
        step_name=f"{prefix}_scene_generation",
    )

    return {
        "steps": {"scene_generation": image_result},
        "status": image_result["status"],
        "cost_usd": PATTERNS["C3-T"]["steps"][0]["cost"] if image_result["status"] == "success" else 0.0,
        "env": env_key,
        "pose": pose_key,
    }


# =============================================================================
# ドライラン
# =============================================================================


def print_dry_run(
    pattern_keys: list[str],
    env_keys: list[str],
    pose_keys: list[str],
) -> None:
    """ドライラン: パターン構成・コスト見積もりを表示する."""
    logger.info("=" * 80)
    logger.info("Phase C-3: キャラ × 環境融合 — ドライラン")
    logger.info("=" * 80)
    logger.info("")

    for key in pattern_keys:
        pattern = PATTERNS[key]
        logger.info("パターン %s: %s", key, pattern["name"])
        logger.info("  %s", pattern["description"])
        for i, step in enumerate(pattern["steps"]):
            logger.info("  Step %d: %s — %s (%s)", i + 1, step["task"], step["model"], step["type"])
        cost = estimate_cost_per_pattern(key)
        combo_count = len(env_keys) * len(pose_keys)
        logger.info(
            "  コスト: $%.2f/組み合わせ × %d env × %d pose = $%.2f",
            cost, len(env_keys), len(pose_keys), cost * combo_count,
        )
        logger.info("")

    logger.info("-" * 60)
    logger.info("入力:")
    logger.info("  キャラ画像: %s", CHARACTER_IMAGE_FRONT)
    logger.info("  Identity Block: %s...（%d chars）", IDENTITY_BLOCK[:80], len(IDENTITY_BLOCK))
    logger.info("")
    for env_key in env_keys:
        logger.info("  環境 [%s]: %s", env_key, ENV_IMAGES[env_key])
        logger.info("    記述: %s...", ENV_DESCRIPTIONS[env_key][:80])
    logger.info("")
    for pose_key in pose_keys:
        logger.info("  ポーズ [%s]: %s", pose_key, POSES[pose_key])
    logger.info("")

    # コスト合計
    total_cost = estimate_total_cost(pattern_keys, len(env_keys), len(pose_keys))
    total_calls = sum(
        len(PATTERNS[k]["steps"]) * len(env_keys) * len(pose_keys)
        for k in pattern_keys
    )

    logger.info("コスト合計:")
    logger.info(
        "  %d パターン × %d env × %d pose = %d API コール, 推定 $%.2f",
        len(pattern_keys), len(env_keys), len(pose_keys), total_calls, total_cost,
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
        pattern_keys = list(PATTERNS.keys())

    # 環境解決
    if args.env:
        env_keys = [e.strip() for e in args.env.split(",")]
        for key in env_keys:
            if key not in ENV_IMAGES:
                logger.error("未定義の環境: %s (利用可能: %s)", key, list(ENV_IMAGES.keys()))
                sys.exit(1)
    else:
        env_keys = list(ENV_IMAGES.keys())

    # ポーズ解決
    if args.pose:
        pose_keys = [p.strip() for p in args.pose.split(",")]
        for key in pose_keys:
            if key not in POSES:
                logger.error("未定義のポーズ: %s (利用可能: %s)", key, list(POSES.keys()))
                sys.exit(1)
    else:
        pose_keys = list(POSES.keys())

    # 入力ファイル存在確認
    if not CHARACTER_IMAGE_FRONT.exists():
        logger.error("キャラクター画像が見つかりません: %s", CHARACTER_IMAGE_FRONT)
        sys.exit(1)

    for env_key in env_keys:
        env_path = ENV_IMAGES[env_key]
        if not env_path.exists():
            logger.error("環境画像が見つかりません: %s", env_path)
            sys.exit(1)

    # ドライラン
    if args.dry_run:
        print_dry_run(pattern_keys, env_keys, pose_keys)
        return

    # API キー取得 & クライアント作成
    api_key = get_gemini_api_key()
    client = genai.Client(api_key=api_key)

    # コスト見積もり
    total_cost_estimate = estimate_total_cost(pattern_keys, len(env_keys), len(pose_keys))

    logger.info("=" * 80)
    logger.info(
        "Phase C-3: キャラ × 環境融合 — %d パターン × %d env × %d pose, 推定コスト: $%.2f",
        len(pattern_keys), len(env_keys), len(pose_keys), total_cost_estimate,
    )
    logger.info("=" * 80)

    all_results: list[dict] = []

    for pattern_key in pattern_keys:
        logger.info("")
        logger.info("=" * 60)
        logger.info("[%s] %s", pattern_key, PATTERNS[pattern_key]["name"])
        logger.info("=" * 60)

        output_dir = GENERATED_DIR / pattern_key.lower()

        for env_key in env_keys:
            for pose_key in pose_keys:
                logger.info("")
                logger.info("  --- %s × %s × %s ---", pattern_key, env_key, pose_key)

                if pattern_key == "C3-I1":
                    result = run_c3i1(client, env_key, pose_key, output_dir)
                elif pattern_key == "C3-I2":
                    result = run_c3i2(client, env_key, pose_key, output_dir)
                elif pattern_key == "C3-T":
                    result = run_c3t(client, env_key, pose_key, output_dir)
                else:
                    logger.error("未知のパターン: %s", pattern_key)
                    continue

                result["pattern"] = pattern_key
                all_results.append(result)

    # 実験ログ保存
    log_path = GENERATED_DIR / "experiment_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "experiment": "phase_c3_scene_fusion",
        "description": "キャラクター × 環境融合シーン生成の検証",
        "patterns": {
            k: {
                "name": PATTERNS[k]["name"],
                "description": PATTERNS[k]["description"],
                "steps": [s["task"] for s in PATTERNS[k]["steps"]],
            }
            for k in pattern_keys
        },
        "inputs": {
            "character_image": str(CHARACTER_IMAGE_FRONT),
            "identity_block": IDENTITY_BLOCK,
            "env_images": {k: str(ENV_IMAGES[k]) for k in env_keys},
            "env_descriptions": {k: ENV_DESCRIPTIONS[k] for k in env_keys},
            "poses": {k: POSES[k] for k in pose_keys},
        },
        "aspect_ratio": ASPECT_RATIO,
        "sdk": "google-genai",
        "timestamp": datetime.now().isoformat(),
        "results": all_results,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    logger.info("")
    logger.info("実験ログを保存しました: %s", log_path)

    # サマリ
    logger.info("=" * 80)
    logger.info("Phase C-3: キャラ × 環境融合 — 結果サマリ:")
    success = sum(1 for r in all_results if r["status"] == "success")
    actual_cost = sum(r.get("cost_usd", 0) for r in all_results)
    logger.info("  成功: %d/%d", success, len(all_results))
    logger.info("  実コスト: $%.2f", actual_cost)
    logger.info("")

    for r in all_results:
        status_icon = "OK" if r["status"] == "success" else "NG"
        logger.info(
            "  [%s] %s × %s × %s — %s, $%.2f",
            status_icon, r["pattern"], r["env"], r["pose"],
            r["status"], r.get("cost_usd", 0),
        )
        if r.get("flash_prompt"):
            logger.info("    Flash生成プロンプト:")
            for line in r["flash_prompt"].split("\n")[:3]:
                logger.info("      %s", line)
            if len(r["flash_prompt"].split("\n")) > 3:
                logger.info("      ... (以下略)")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
