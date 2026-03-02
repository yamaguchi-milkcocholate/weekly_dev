"""Phase C-2: 環境生成 — 検証スクリプト.

参照写真（人物入り）から環境の雰囲気を取り出し、
人物不在・C3人物配置向きの環境画像を生成する検証。

検証パターン:
  C2-R1: Flash分析 → テキストのみPro生成
  C2-R2: 参照画像 + 環境再現指示（直接編集型）
  C2-R3: 参照画像 + 構図テンプレート指示
  C2-ED: 環境記述テキスト自動生成

Usage:
    uv run python poc/seamless/run_phase_c2.py --dry-run
    uv run python poc/seamless/run_phase_c2.py --patterns C2-R1,C2-R2,C2-R3
    uv run python poc/seamless/run_phase_c2.py --patterns C2-R2 --env 1
    uv run python poc/seamless/run_phase_c2.py --patterns C2-ED --ed-source path/to/env.png
    uv run python poc/seamless/run_phase_c2.py
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
    C2ED_ANALYSIS_PROMPT,
    C2R1_FLASH_ANALYSIS_PROMPT,
    C2R1_GENERATION_TEMPLATE,
    C2R2_PROMPT,
    C2R3_PROMPT,
    ENV_IMAGES,
    GENERATED_DIR,
    PATTERNS,
    PRO_IMAGE_MODEL,
    estimate_cost_per_pattern,
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
        description="Phase C-2: 環境生成 — 検証",
    )
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="実行するパターンをカンマ区切りで指定 (例: C2-R1,C2-R2)。指定なしでC2-ED以外の全パターン",
    )
    parser.add_argument(
        "--env",
        type=str,
        default=None,
        help="使用する env 番号をカンマ区切りで指定 (例: 1,2)。指定なしで全env",
    )
    parser.add_argument(
        "--ed-source",
        type=str,
        default=None,
        help="C2-ED の入力画像パス。指定なしの場合 C2-ED はスキップ",
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


def run_c2r1(
    client: genai.Client,
    env_path: Path,
    output_dir: Path,
) -> dict:
    """C2-R1: Flash分析 → テキストのみPro生成."""
    env_name = env_path.stem
    steps = {}

    # Step 1: Flash が参照写真の環境を分析
    logger.info("    --- C2-R1 Step 1: Flash 環境分析 [%s] ---", env_name)
    flash_result = sdk_generate_text(
        client,
        model=PATTERNS["C2-R1"]["steps"][0]["model"],
        contents=[
            load_image_part(env_path),
            C2R1_FLASH_ANALYSIS_PROMPT,
        ],
        step_name=f"c2r1_flash_analysis_{env_name}",
    )
    steps["flash_analysis"] = flash_result

    if flash_result["status"] != "success":
        return {"steps": steps, "status": "failed_at_flash_analysis", "cost_usd": 0.0, "env": env_name}

    flash_description = flash_result["generated_text"]
    logger.info("      Flash 生成記述:\n%s", flash_description)

    # テキスト保存
    prompt_path = output_dir / f"c2r1_{env_name}_flash_description.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(flash_description, encoding="utf-8")

    # Step 2: Pro がテキストのみで画像生成（参照画像なし）
    generation_prompt = C2R1_GENERATION_TEMPLATE.replace(
        "{{flash_description}}", flash_description
    )
    logger.info("    --- C2-R1 Step 2: Pro テキストベース画像生成 [%s] ---", env_name)

    gen_prompt_path = output_dir / f"c2r1_{env_name}_generation_prompt.txt"
    gen_prompt_path.write_text(generation_prompt, encoding="utf-8")

    image_result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[generation_prompt],
        output_path=output_dir / f"c2r1_{env_name}.png",
        step_name=f"c2r1_text_generation_{env_name}",
    )
    steps["text_generation"] = image_result

    cost = PATTERNS["C2-R1"]["steps"][0]["cost"]
    if image_result["status"] == "success":
        cost += PATTERNS["C2-R1"]["steps"][1]["cost"]

    return {
        "steps": steps,
        "status": image_result["status"],
        "cost_usd": cost,
        "env": env_name,
        "flash_description": flash_description,
    }


def run_c2r2(
    client: genai.Client,
    env_path: Path,
    output_dir: Path,
) -> dict:
    """C2-R2: 参照画像 + 環境再現指示（直接編集型）."""
    env_name = env_path.stem
    logger.info("    --- C2-R2: 環境再現（直接編集型）[%s] ---", env_name)

    # プロンプト保存
    prompt_path = output_dir / f"c2r2_{env_name}_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(C2R2_PROMPT, encoding="utf-8")

    result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(env_path),
            C2R2_PROMPT,
        ],
        output_path=output_dir / f"c2r2_{env_name}.png",
        step_name=f"c2r2_recreation_{env_name}",
    )

    return {
        "steps": {"recreation_generation": result},
        "status": result["status"],
        "cost_usd": PATTERNS["C2-R2"]["steps"][0]["cost"] if result["status"] == "success" else 0.0,
        "env": env_name,
    }


def run_c2r3(
    client: genai.Client,
    env_path: Path,
    output_dir: Path,
) -> dict:
    """C2-R3: 参照画像 + 構図テンプレート指示."""
    env_name = env_path.stem
    logger.info("    --- C2-R3: 構図テンプレート [%s] ---", env_name)

    # プロンプト保存
    prompt_path = output_dir / f"c2r3_{env_name}_prompt.txt"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(C2R3_PROMPT, encoding="utf-8")

    result = sdk_generate_image(
        client,
        model=PRO_IMAGE_MODEL,
        contents=[
            load_image_part(env_path),
            C2R3_PROMPT,
        ],
        output_path=output_dir / f"c2r3_{env_name}.png",
        step_name=f"c2r3_composition_{env_name}",
    )

    return {
        "steps": {"composition_generation": result},
        "status": result["status"],
        "cost_usd": PATTERNS["C2-R3"]["steps"][0]["cost"] if result["status"] == "success" else 0.0,
        "env": env_name,
    }


def run_c2ed(
    client: genai.Client,
    source_image_path: Path,
    output_dir: Path,
) -> dict:
    """C2-ED: 環境記述テキスト自動生成."""
    source_name = source_image_path.stem
    logger.info("    --- C2-ED: 環境記述テキスト自動生成 [%s] ---", source_name)

    flash_result = sdk_generate_text(
        client,
        model=PATTERNS["C2-ED"]["steps"][0]["model"],
        contents=[
            load_image_part(source_image_path),
            C2ED_ANALYSIS_PROMPT,
        ],
        step_name=f"c2ed_description_{source_name}",
    )

    if flash_result["status"] == "success":
        env_description = flash_result["generated_text"]
        logger.info("      環境記述:\n%s", env_description)

        # テキスト保存
        desc_path = output_dir / f"c2ed_{source_name}_description.txt"
        desc_path.parent.mkdir(parents=True, exist_ok=True)
        desc_path.write_text(env_description, encoding="utf-8")

        return {
            "steps": {"environment_description": flash_result},
            "status": "success",
            "cost_usd": PATTERNS["C2-ED"]["steps"][0]["cost"],
            "environment_description": env_description,
            "source_image": str(source_image_path),
        }

    return {
        "steps": {"environment_description": flash_result},
        "status": "failed",
        "cost_usd": 0.0,
        "source_image": str(source_image_path),
    }


# =============================================================================
# ドライラン
# =============================================================================


def print_dry_run(pattern_keys: list[str], env_indices: list[int]) -> None:
    """ドライラン: パターン構成・コスト見積もりを表示する."""
    logger.info("=" * 80)
    logger.info("Phase C-2: 環境生成 — ドライラン")
    logger.info("=" * 80)
    logger.info("")

    for key in pattern_keys:
        pattern = PATTERNS[key]
        logger.info("パターン %s: %s", key, pattern["name"])
        logger.info("  %s", pattern["description"])
        for i, step in enumerate(pattern["steps"]):
            logger.info("  Step %d: %s — %s (%s)", i + 1, step["task"], step["model"], step["type"])
        cost = estimate_cost_per_pattern(key)
        logger.info(
            "  コスト: $%.2f/env × %d env = $%.2f",
            cost, len(env_indices), cost * len(env_indices),
        )
        logger.info("")

    logger.info("-" * 60)
    logger.info("入力画像:")
    for idx in env_indices:
        logger.info("  env_%d: %s", idx + 1, ENV_IMAGES[idx])
    logger.info("")

    # コスト合計
    total_cost = 0.0
    total_calls = 0
    for key in pattern_keys:
        base_cost = estimate_cost_per_pattern(key)
        base_calls = len(PATTERNS[key]["steps"])
        total_cost += base_cost * len(env_indices)
        total_calls += base_calls * len(env_indices)

    logger.info("コスト合計:")
    logger.info(
        "  %d パターン × %d env = %d API コール, 推定 $%.2f",
        len(pattern_keys), len(env_indices), total_calls, total_cost,
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
        # デフォルト: C2-ED 以外の全パターン
        pattern_keys = [k for k in PATTERNS if k != "C2-ED"]

    # Env 解決
    if args.env:
        env_indices = [int(e.strip()) - 1 for e in args.env.split(",")]
        for idx in env_indices:
            if idx < 0 or idx >= len(ENV_IMAGES):
                logger.error(
                    "env 番号が範囲外: %d (1〜%d)", idx + 1, len(ENV_IMAGES),
                )
                sys.exit(1)
    else:
        env_indices = list(range(len(ENV_IMAGES)))

    # 入力ファイル存在確認
    for idx in env_indices:
        if not ENV_IMAGES[idx].exists():
            logger.error("環境参照画像が見つかりません: %s", ENV_IMAGES[idx])
            sys.exit(1)

    # ドライラン
    if args.dry_run:
        print_dry_run(pattern_keys, env_indices)
        return

    # API キー取得 & クライアント作成
    api_key = get_gemini_api_key()
    client = genai.Client(api_key=api_key)

    # コスト見積もり
    total_cost_estimate = sum(
        estimate_cost_per_pattern(k) * len(env_indices)
        for k in pattern_keys
    )

    logger.info("=" * 80)
    logger.info(
        "Phase C-2: 環境生成 — %d パターン × %d env, 推定コスト: $%.2f",
        len(pattern_keys), len(env_indices), total_cost_estimate,
    )
    logger.info("=" * 80)

    all_results: list[dict] = []

    for pattern_key in pattern_keys:
        logger.info("")
        logger.info("=" * 60)
        logger.info("[%s] %s", pattern_key, PATTERNS[pattern_key]["name"])
        logger.info("=" * 60)

        output_dir = GENERATED_DIR / pattern_key.lower()

        if pattern_key == "C2-ED":
            if not args.ed_source:
                logger.warning("C2-ED: --ed-source が指定されていないためスキップ")
                continue
            source_path = Path(args.ed_source)
            if not source_path.exists():
                logger.error("C2-ED: 入力画像が見つかりません: %s", source_path)
                continue
            result = run_c2ed(client, source_path, output_dir)
            result["pattern"] = pattern_key
            all_results.append(result)
            continue

        for idx in env_indices:
            env_path = ENV_IMAGES[idx]

            if pattern_key == "C2-R1":
                result = run_c2r1(client, env_path, output_dir)
            elif pattern_key == "C2-R2":
                result = run_c2r2(client, env_path, output_dir)
            elif pattern_key == "C2-R3":
                result = run_c2r3(client, env_path, output_dir)
            else:
                logger.error("未知のパターン: %s", pattern_key)
                continue

            result["pattern"] = pattern_key
            all_results.append(result)

    # 実験ログ保存
    log_path = GENERATED_DIR / "experiment_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "experiment": "phase_c2_environment_generation",
        "description": "参照写真から環境画像を生成する検証",
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
        "env_images": [str(ENV_IMAGES[i]) for i in env_indices],
        "results": all_results,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    logger.info("")
    logger.info("実験ログを保存しました: %s", log_path)

    # サマリ
    logger.info("=" * 80)
    logger.info("Phase C-2: 環境生成 — 結果サマリ:")
    success = sum(1 for r in all_results if r["status"] == "success")
    actual_cost = sum(r.get("cost_usd", 0) for r in all_results)
    logger.info("  成功: %d/%d", success, len(all_results))
    logger.info("  実コスト: $%.2f", actual_cost)
    logger.info("")

    for r in all_results:
        status_icon = "OK" if r["status"] == "success" else "NG"
        env_info = f" [{r['env']}]" if "env" in r else ""
        logger.info(
            "  [%s] %s%s — %s, $%.2f",
            status_icon, r["pattern"], env_info, r["status"], r.get("cost_usd", 0),
        )
        for key in ("flash_description", "environment_description"):
            if r.get(key):
                logger.info("    %s:", key)
                for line in r[key].split("\n")[:5]:
                    logger.info("      %s", line)
                if len(r[key].split("\n")) > 5:
                    logger.info("      ... (以下略)")

    logger.info("=" * 80)


if __name__ == "__main__":
    main()
