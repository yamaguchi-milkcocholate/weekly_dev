"""Phase B-1 改訂: シーン統合生成 — 検証スクリプト.

レイヤー合成パイプラインに代わるシーン統合生成アプローチを検証する。

検証パターン（1回目）:
  S1: 統合1パス — キャラ参照 + seed + 背景参照 → Pro 1回で生成
  S3: Flash統合分析 → Pro生成 — Flash が seed+背景を分析 → Pro が生成
  S5: 精度維持型分割 — 背景変更(Pro) → キャラ差替(Pro)

Usage:
    uv run python poc/seamless/run_phase_b1_scene.py --dry-run
    uv run python poc/seamless/run_phase_b1_scene.py --patterns S1,S3
    uv run python poc/seamless/run_phase_b1_scene.py --seeds 4.png
    uv run python poc/seamless/run_phase_b1_scene.py
"""

import argparse
import json
import logging
import os
import sys
import time
from datetime import datetime
from pathlib import Path

from config_b1_scene import (
    ASPECT_RATIO,
    BACKGROUND_REF,
    CHARACTER_REF,
    GENERATED_DIR,
    PATTERNS,
    PRO_IMAGE_MODEL,
    S1_PROMPT,
    S3_META_PROMPT,
    S3M_META_PROMPT,
    S5_STEP1_PROMPT,
    S5_STEP2_PROMPT,
    SEED_CAPTURE_DIR,
    SEED_IMAGES,
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
        description="Phase B-1 改訂: シーン統合生成 — 検証",
    )
    parser.add_argument(
        "--seeds",
        type=str,
        default=None,
        help="使用する seed 画像をカンマ区切りで指定 (例: 4.png)。指定なしでデフォルト",
    )
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="実行するパターンをカンマ区切りで指定 (例: S1,S3)。指定なしで全パターン",
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


def run_s1(
    client: genai.Client,
    seed_path: Path,
    output_dir: Path,
) -> dict:
    """S1: 統合1パス（3画像入力: キャラ参照 + seed + 背景参照）."""
    logger.info("    --- S1: 統合1パス生成 (model: %s) ---", PRO_IMAGE_MODEL)

    result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(CHARACTER_REF),    # image 1: キャラ参照
            load_image_part(seed_path),         # image 2: seed（構図参照）
            load_image_part(BACKGROUND_REF),    # image 3: 背景参照
            S1_PROMPT,
        ],
        output_path=output_dir / "s1_scene.png",
        step_name="s1_scene_generation",
    )
    return {
        "steps": {"scene_generation": result},
        "status": result["status"],
        "cost_usd": PATTERNS["S1"]["steps"][0]["cost"] if result["status"] == "success" else 0.0,
    }


def run_s3(
    client: genai.Client,
    seed_path: Path,
    output_dir: Path,
) -> dict:
    """S3: Flash統合分析 → Pro生成（3画像入力）."""
    steps = {}

    # Step 1: Flash 統合分析
    logger.info("    --- S3 Step 1: Flash 統合分析 (model: %s) ---", PATTERNS["S3"]["steps"][0]["model"])
    flash_result = sdk_generate_text(
        client,
        model=PATTERNS["S3"]["steps"][0]["model"],
        contents=[
            load_image_part(seed_path),         # image 1: seed（構図参照）
            load_image_part(BACKGROUND_REF),    # image 2: 背景参照
            S3_META_PROMPT,
        ],
        step_name="s3_flash_analysis",
    )
    steps["flash_analysis"] = flash_result

    if flash_result["status"] != "success":
        return {"steps": steps, "status": "failed_at_flash_analysis", "cost_usd": 0.0}

    generated_prompt = flash_result["generated_text"]
    logger.info("      Flash 生成プロンプト:\n%s", generated_prompt)

    # Flash 生成プロンプトを保存
    prompt_path = output_dir / "s3_flash_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(generated_prompt, encoding="utf-8")

    # Step 2: Pro シーン生成（キャラ参照 + 背景参照 + Flash生成プロンプト）
    logger.info("    --- S3 Step 2: Pro シーン生成 (model: %s) ---", PRO_IMAGE_MODEL)
    scene_result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(CHARACTER_REF),    # image 1: キャラ参照
            load_image_part(BACKGROUND_REF),   # image 2: 背景参照
            generated_prompt,
        ],
        output_path=output_dir / "s3_scene.png",
        step_name="s3_scene_generation",
    )
    steps["scene_generation"] = scene_result

    cost = PATTERNS["S3"]["steps"][0]["cost"]
    if scene_result["status"] == "success":
        cost += PATTERNS["S3"]["steps"][1]["cost"]

    return {
        "steps": steps,
        "status": scene_result["status"],
        "cost_usd": cost,
    }


def run_s5(
    client: genai.Client,
    seed_path: Path,
    output_dir: Path,
) -> dict:
    """S5: 精度維持型分割（シーン先行生成 → キャラ差替）."""
    steps = {}

    # Step 1: シーン生成（背景変更、元 seed の人物は保持）
    logger.info("    --- S5 Step 1: シーン生成/背景変更 (model: %s) ---", PRO_IMAGE_MODEL)
    scene_result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(seed_path),         # image 1: seed
            load_image_part(BACKGROUND_REF),    # image 2: 背景参照
            S5_STEP1_PROMPT,
        ],
        output_path=output_dir / "s5_step1_scene.png",
        step_name="s5_scene_generation",
    )
    steps["scene_generation"] = scene_result

    if scene_result["status"] != "success":
        return {"steps": steps, "status": "failed_at_scene_generation", "cost_usd": 0.0}

    # Step 2: キャラクター差替（A-1 全部入りプロンプト）
    step1_output = output_dir / "s5_step1_scene.png"
    logger.info("    --- S5 Step 2: キャラクター差替 (model: %s) ---", PRO_IMAGE_MODEL)
    swap_result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(CHARACTER_REF),    # image 1: キャラ参照
            load_image_part(step1_output),     # image 2: Step 1 出力
            S5_STEP2_PROMPT,
        ],
        output_path=output_dir / "s5_step2_final.png",
        step_name="s5_character_swap",
    )
    steps["character_swap"] = swap_result

    cost = PATTERNS["S5"]["steps"][0]["cost"]
    if swap_result["status"] == "success":
        cost += PATTERNS["S5"]["steps"][1]["cost"]

    return {
        "steps": steps,
        "status": swap_result["status"],
        "cost_usd": cost,
    }


def run_s4(
    client: genai.Client,
    seed_path: Path,
    output_dir: Path,
) -> dict:
    """S4: Flash統合分析 → Pro生成（seed も Pro に入力して構図保持を強化）."""
    steps = {}

    # Step 1: Flash 統合分析（S3 と同じメタプロンプト）
    logger.info("    --- S4 Step 1: Flash 統合分析 (model: %s) ---", PATTERNS["S4"]["steps"][0]["model"])
    flash_result = sdk_generate_text(
        client,
        model=PATTERNS["S4"]["steps"][0]["model"],
        contents=[
            load_image_part(seed_path),         # image 1: seed（構図参照）
            load_image_part(BACKGROUND_REF),    # image 2: 背景参照
            S3_META_PROMPT,
        ],
        step_name="s4_flash_analysis",
    )
    steps["flash_analysis"] = flash_result

    if flash_result["status"] != "success":
        return {"steps": steps, "status": "failed_at_flash_analysis", "cost_usd": 0.0}

    generated_prompt = flash_result["generated_text"]
    logger.info("      Flash 生成プロンプト:\n%s", generated_prompt)

    prompt_path = output_dir / "s4_flash_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(generated_prompt, encoding="utf-8")

    # Step 2: Pro シーン生成（キャラ参照 + seed + 背景参照 + Flash生成プロンプト）
    # S3 との差分: seed 画像も Pro に渡す → 構図参照の強化
    logger.info("    --- S4 Step 2: Pro シーン生成 + seed入力 (model: %s) ---", PRO_IMAGE_MODEL)
    scene_result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(CHARACTER_REF),    # image 1: キャラ参照
            load_image_part(seed_path),         # image 2: seed（構図参照）
            load_image_part(BACKGROUND_REF),   # image 3: 背景参照
            generated_prompt,
        ],
        output_path=output_dir / "s4_scene.png",
        step_name="s4_scene_generation",
    )
    steps["scene_generation"] = scene_result

    cost = PATTERNS["S4"]["steps"][0]["cost"]
    if scene_result["status"] == "success":
        cost += PATTERNS["S4"]["steps"][1]["cost"]

    return {
        "steps": steps,
        "status": scene_result["status"],
        "cost_usd": cost,
    }


def run_s3m_cmp(
    client: genai.Client,
    seed_path: Path,
    output_dir: Path,
) -> dict:
    """S3M_CMP: Flash分析1回 → 同一プロンプトで Pro/Flash 画像生成を比較."""
    pattern = PATTERNS["S3M_CMP"]
    steps = {}
    cost = 0.0

    # Step 1: Flash 統合分析（1回のみ実行）
    flash_model = pattern["steps"][0]["model"]
    logger.info("    --- S3M_CMP Step 1: Flash 統合分析/最小指示 (model: %s) ---", flash_model)
    flash_result = sdk_generate_text(
        client,
        model=flash_model,
        contents=[
            load_image_part(seed_path),
            load_image_part(BACKGROUND_REF),
            S3M_META_PROMPT,
        ],
        step_name="s3m_cmp_flash_analysis",
    )
    steps["flash_analysis"] = flash_result

    if flash_result["status"] != "success":
        return {"steps": steps, "status": "failed_at_flash_analysis", "cost_usd": 0.0}

    generated_prompt = flash_result["generated_text"]
    cost += pattern["steps"][0]["cost"]
    logger.info("      Flash 生成プロンプト:\n%s", generated_prompt)

    prompt_path = output_dir / "s3m_cmp_flash_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(generated_prompt, encoding="utf-8")

    # 共通の contents（同一プロンプトを両モデルに渡す）
    image_contents = [
        load_image_part(CHARACTER_REF),
        load_image_part(BACKGROUND_REF),
        generated_prompt,
    ]

    # Step 2a: Pro 画像生成
    pro_model = pattern["steps"][1]["model"]
    logger.info("    --- S3M_CMP Step 2a: Pro 画像生成 (model: %s) ---", pro_model)
    pro_result = sdk_generate_image(
        client,
        model=pro_model,
        contents=image_contents,
        output_path=output_dir / "s3m_cmp_pro.png",
        step_name="s3m_cmp_pro_generation",
    )
    steps["scene_generation_pro"] = pro_result
    if pro_result["status"] == "success":
        cost += pattern["steps"][1]["cost"]

    # Step 2b: Flash 画像生成
    flash_img_model = pattern["steps"][2]["model"]
    logger.info("    --- S3M_CMP Step 2b: Flash 画像生成 (model: %s) ---", flash_img_model)
    flash_img_result = sdk_generate_image(
        client,
        model=flash_img_model,
        contents=image_contents,
        output_path=output_dir / "s3m_cmp_flash.png",
        step_name="s3m_cmp_flash_generation",
    )
    steps["scene_generation_flash"] = flash_img_result
    if flash_img_result["status"] == "success":
        cost += pattern["steps"][2]["cost"]

    # 両方の結果でステータス判定
    if pro_result["status"] == "success" and flash_img_result["status"] == "success":
        status = "success"
    elif pro_result["status"] == "success":
        status = "partial_flash_failed"
    elif flash_img_result["status"] == "success":
        status = "partial_pro_failed"
    else:
        status = "failed"

    return {
        "steps": steps,
        "status": status,
        "cost_usd": cost,
    }


# パターンキーと実行関数の対応
PATTERN_RUNNERS = {
    "S1": run_s1,
    "S3": run_s3,
    "S4": run_s4,
    "S3M_CMP": run_s3m_cmp,
    "S5": run_s5,
}


def print_dry_run(pattern_keys: list[str], seed_images: list[str]) -> None:
    """ドライラン: パターン構成・コスト見積もりを表示する."""
    logger.info("=" * 80)
    logger.info("Phase B-1 改訂: シーン統合生成 — ドライラン")
    logger.info("=" * 80)
    logger.info("")

    for key in pattern_keys:
        pattern = PATTERNS[key]
        logger.info("パターン %s: %s（方針: %s）", key, pattern["name"], pattern["approach"])
        for i, step in enumerate(pattern["steps"]):
            logger.info("  Step %d: %s — %s (%s)", i + 1, step["task"], step["model"], step["type"])
        logger.info("  コスト/seed: $%.2f", estimate_cost_per_pattern(key))
        logger.info("")

    logger.info("-" * 60)
    logger.info("参照画像:")
    logger.info("  キャラ参照: %s", CHARACTER_REF)
    logger.info("  背景参照:   %s", BACKGROUND_REF)
    logger.info("Seed 画像: %s", [str(SEED_CAPTURE_DIR / s) for s in seed_images])
    logger.info("")

    logger.info("プロンプト:")
    logger.info("  S1 プロンプト:")
    for line in S1_PROMPT.split("\n"):
        logger.info("    %s", line)
    logger.info("")
    logger.info("  S3 メタプロンプト:")
    for line in S3_META_PROMPT.split("\n"):
        logger.info("    %s", line)
    logger.info("")
    logger.info("  S5 Step 1 プロンプト:")
    for line in S5_STEP1_PROMPT.split("\n"):
        logger.info("    %s", line)
    logger.info("  S5 Step 2 プロンプト:")
    for line in S5_STEP2_PROMPT.split("\n"):
        logger.info("    %s", line)
    logger.info("")

    total_cost = sum(
        estimate_cost_per_pattern(k) * len(seed_images) for k in pattern_keys
    )
    total_calls = sum(len(PATTERNS[k]["steps"]) * len(seed_images) for k in pattern_keys)
    logger.info("コスト合計:")
    logger.info(
        "  %d パターン × %d seed = %d API コール, 推定 $%.2f",
        len(pattern_keys), len(seed_images), total_calls, total_cost,
    )
    logger.info("=" * 80)


def main() -> None:
    args = parse_args()

    # seed 画像解決
    if args.seeds:
        seed_images = [s.strip() for s in args.seeds.split(",")]
    else:
        seed_images = SEED_IMAGES

    # パターン解決
    if args.patterns:
        pattern_keys = [p.strip().upper() for p in args.patterns.split(",")]
        for key in pattern_keys:
            if key not in PATTERNS:
                logger.error("未定義のパターン: %s (利用可能: %s)", key, list(PATTERNS.keys()))
                sys.exit(1)
    else:
        pattern_keys = list(PATTERNS.keys())

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
        print_dry_run(pattern_keys, seed_images)
        return

    # API キー取得 & クライアント作成
    api_key = get_gemini_api_key()
    client = genai.Client(api_key=api_key)

    total_cost = sum(
        estimate_cost_per_pattern(k) * len(seed_images) for k in pattern_keys
    )
    logger.info("=" * 80)
    logger.info(
        "Phase B-1 改訂: シーン統合生成 — %d パターン × %d seed, 推定コスト: $%.2f",
        len(pattern_keys), len(seed_images), total_cost,
    )
    logger.info("=" * 80)

    all_results: list[dict] = []

    for seed_name in seed_images:
        seed_path = SEED_CAPTURE_DIR / seed_name
        seed_stem = Path(seed_name).stem

        for pattern_key in pattern_keys:
            logger.info("")
            logger.info("=" * 60)
            logger.info(
                "[%s] seed=%s — %s",
                pattern_key, seed_name, PATTERNS[pattern_key]["name"],
            )
            logger.info("=" * 60)

            output_dir = GENERATED_DIR / f"seed_{seed_stem}" / pattern_key.lower()

            try:
                runner = PATTERN_RUNNERS[pattern_key]
                result = runner(client, seed_path, output_dir)
                result["pattern"] = pattern_key
                result["seed"] = seed_name
            except Exception:
                logger.exception("    予期しないエラー")
                result = {
                    "pattern": pattern_key,
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
        "experiment": "phase_b1_scene_generation",
        "description": "シーン統合生成アプローチの検証（レイヤー合成からのパラダイムシフト）",
        "patterns": {
            k: {
                "name": PATTERNS[k]["name"],
                "approach": PATTERNS[k]["approach"],
                "steps": [s["task"] for s in PATTERNS[k]["steps"]],
            }
            for k in pattern_keys
        },
        "aspect_ratio": ASPECT_RATIO,
        "sdk": "google-genai",
        "timestamp": datetime.now().isoformat(),
        "seed_images": seed_images,
        "character_ref": str(CHARACTER_REF),
        "background_ref": str(BACKGROUND_REF),
        "prompts": {
            "S1": S1_PROMPT,
            "S3_meta": S3_META_PROMPT,
            "S5_step1": S5_STEP1_PROMPT,
            "S5_step2": S5_STEP2_PROMPT,
        },
        "results": all_results,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    logger.info("")
    logger.info("実験ログを保存しました: %s", log_path)

    # サマリ
    logger.info("=" * 80)
    logger.info("Phase B-1 改訂: シーン統合生成 — 結果サマリ:")
    success = sum(1 for r in all_results if r["status"] == "success")
    actual_cost = sum(r.get("cost_usd", 0) for r in all_results)
    logger.info("  成功: %d/%d", success, len(all_results))
    logger.info("  実コスト: $%.2f", actual_cost)
    logger.info("")

    for r in all_results:
        status_icon = "OK" if r["status"] == "success" else "NG"
        logger.info(
            "  [%s] %s / %s — %s, $%.2f",
            status_icon, r["pattern"], r["seed"], r["status"], r.get("cost_usd", 0),
        )
        # Flash 生成プロンプトがあれば表示
        flash = r.get("steps", {}).get("flash_analysis", {})
        if flash.get("generated_text"):
            logger.info("    Flash 生成プロンプト:")
            for line in flash["generated_text"].split("\n"):
                logger.info("      %s", line)

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
