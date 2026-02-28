"""Phase A-4: スタイル転写 — Python SDK 版実験スクリプト.

seed 画像の色味・照明・雰囲気を参考にしつつ、独自キャラクター＋独自シーンで
新規画像を生成するベストプラクティスを確立する。

パターンごとに入力構成が異なる:
- S1, S2: キャラクター参照のみ（seed 画像なし）
- S3〜S5, S7: seed 画像 + キャラクター参照
- S6: 2段階（Visual DNA 抽出 → テキストのみ生成）
- S8: seed 画像 + 環境参照 + キャラクター参照（3枚入力）

Usage:
    uv run python poc/seamless/run_phase_a4.py --dry-run
    uv run python poc/seamless/run_phase_a4.py --patterns S1,S2
    uv run python poc/seamless/run_phase_a4.py --seeds 1.png,4.png
    uv run python poc/seamless/run_phase_a4.py
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

from config_a4 import (
    ALL_PATTERNS,
    ASPECT_RATIO,
    CHARACTER_REF,
    COST_PER_IMAGE,
    GEMINI_MODEL,
    GENERATED_DIR,
    SEED_CAPTURE_DIR,
    SEED_IMAGES,
    StylePattern,
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
    parser = argparse.ArgumentParser(description="Phase A-4: スタイル転写検証")
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="実行パターンをカンマ区切りで指定 (例: S1,S2,S5)。指定なしで全パターン",
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


def _resolve_mime(path: Path) -> str:
    """ファイル拡張子から MIME タイプを解決する."""
    suffix = path.suffix.lstrip(".")
    return "image/jpeg" if suffix == "jpg" else f"image/{suffix}"


def _api_call_with_retry(
    client: genai.Client,
    contents: list,
    config: GenerateContentConfig,
    max_retries: int = 3,
) -> tuple[str, bytes | None]:
    """Gemini SDK API 呼び出し（リトライ付き）.

    Returns:
        (text_response, image_data) のタプル。画像がない場合 image_data は None。
    """
    last_error = None
    for attempt in range(1, max_retries + 1):
        logger.info(
            "    SDK リクエスト送信中... (model: %s, attempt %d/%d)",
            GEMINI_MODEL, attempt, max_retries,
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
                wait = 10 * attempt
                logger.warning("    サーバーエラー/タイムアウト: %s, %d秒後にリトライ...", error_str[:200], wait)
                time.sleep(wait)
            else:
                raise
    else:
        msg = f"All retries failed: {last_error}"
        raise RuntimeError(msg)

    text_response = ""
    image_data = None
    for part in response.candidates[0].content.parts:
        if part.text:
            text_response += part.text
        if part.inline_data:
            image_data = part.inline_data.data

    return text_response, image_data


def extract_visual_dna(
    client: genai.Client,
    seed_image_path: Path,
    extraction_prompt: str,
) -> str:
    """Step 1: seed 画像からスタイル記述を抽出する（テキスト応答のみ）."""
    seed_bytes = seed_image_path.read_bytes()
    seed_mime = _resolve_mime(seed_image_path)

    contents = [
        Part.from_bytes(data=seed_bytes, mime_type=seed_mime),
        extraction_prompt,
    ]

    config = GenerateContentConfig(
        response_modalities=["TEXT"],
    )

    text_response, _ = _api_call_with_retry(client, contents, config)
    logger.info("    Visual DNA 抽出結果: %s", text_response[:300])
    return text_response


def generate_style_transfer(
    client: genai.Client,
    pattern: StylePattern,
    seed_image_path: Path | None,
    char_ref_path: Path,
    output_path: Path,
    extra_ref_paths: list[Path] | None = None,
    extracted_style: str | None = None,
) -> dict:
    """スタイル転写画像を生成する.

    パターンの設定に応じて入力構成を切り替える:
    - seed なし: [キャラ参照, プロンプト]
    - seed あり: [seed(スタイル参照), キャラ参照, プロンプト]
    - 3枚入力: [seed(スタイル参照), 環境参照, キャラ参照, プロンプト]
    """
    contents: list = []

    # seed 画像（スタイル参照）
    if seed_image_path and pattern.uses_seed_image:
        seed_bytes = seed_image_path.read_bytes()
        contents.append(Part.from_bytes(data=seed_bytes, mime_type=_resolve_mime(seed_image_path)))

    # 追加の環境参照画像
    if extra_ref_paths and pattern.uses_extra_ref:
        for ref_path in extra_ref_paths:
            ref_bytes = ref_path.read_bytes()
            contents.append(Part.from_bytes(data=ref_bytes, mime_type=_resolve_mime(ref_path)))

    # キャラクター参照画像
    char_bytes = char_ref_path.read_bytes()
    contents.append(Part.from_bytes(data=char_bytes, mime_type=_resolve_mime(char_ref_path)))

    # プロンプト（Visual DNA の場合はスタイル記述を埋め込み）
    prompt = pattern.prompt
    if pattern.is_two_stage and extracted_style:
        prompt = prompt.replace("{extracted_style}", extracted_style)
    contents.append(prompt)

    config = GenerateContentConfig(
        response_modalities=["TEXT", "IMAGE"],
        image_config=ImageConfig(
            aspect_ratio=ASPECT_RATIO,
        ),
    )

    try:
        text_response, image_data = _api_call_with_retry(client, contents, config)
    except RuntimeError as e:
        return {"status": "failed", "error": str(e)}
    except Exception as e:
        logger.error("    API エラー: %s", str(e)[:500])
        return {"status": "failed", "error": str(e)[:200]}

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


def print_dry_run(patterns: list[StylePattern], seed_images: list[str]) -> None:
    """ドライラン: プロンプト・コスト見積もりを表示する."""
    logger.info("=" * 80)
    logger.info("Phase A-4: スタイル転写 — ドライラン")
    logger.info("=" * 80)
    logger.info("モデル: %s", GEMINI_MODEL)
    logger.info("アスペクト比: %s", ASPECT_RATIO)
    logger.info("キャラクター参照: %s", CHARACTER_REF)
    logger.info("Seed 画像: %s", [str(SEED_CAPTURE_DIR / s) for s in seed_images])
    logger.info("")

    for pattern in patterns:
        logger.info("-" * 60)
        logger.info("[%s] %s", pattern.id, pattern.name)
        logger.info("  説明: %s", pattern.description)
        logger.info("  seed 画像使用: %s", pattern.uses_seed_image)
        logger.info("  追加参照画像: %s", pattern.uses_extra_ref)
        logger.info("  2段階手法: %s", pattern.is_two_stage)
        if pattern.is_two_stage:
            logger.info("  抽出プロンプト:")
            logger.info("    %s", pattern.visual_dna_extraction_prompt[:200])
        logger.info("  生成プロンプト:")
        logger.info("    %s", pattern.prompt[:300])

    logger.info("")
    logger.info("=" * 80)
    total = len(patterns) * len(seed_images)
    total_cost = total * COST_PER_IMAGE
    # S6 の Visual DNA 抽出分を加算
    two_stage_count = sum(1 for p in patterns if p.is_two_stage) * len(seed_images)
    if two_stage_count > 0:
        logger.info(
            "合計: %d パターン × %d seed = %d 生成 + %d 抽出, 推定コスト: $%.2f",
            len(patterns), len(seed_images), total, two_stage_count,
            total_cost + two_stage_count * 0.01,
        )
    else:
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

    # seed 画像の存在確認
    for seed_name in seed_images:
        seed_path = SEED_CAPTURE_DIR / seed_name
        if not seed_path.exists():
            logger.error("Seed 画像が見つかりません: %s", seed_path)
            sys.exit(1)

    # 参照画像の存在確認
    if not CHARACTER_REF.exists():
        logger.error("キャラクター参照画像が見つかりません: %s", CHARACTER_REF)
        sys.exit(1)

    # S8 用の追加参照画像の存在確認
    for pattern in patterns:
        if pattern.uses_extra_ref:
            for extra_name in pattern.extra_ref_images:
                extra_path = SEED_CAPTURE_DIR / extra_name
                if not extra_path.exists():
                    logger.error("追加参照画像が見つかりません: %s", extra_path)
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
        "Phase A-4 スタイル転写 開始: %d パターン × %d seed = %d 生成, 推定コスト: $%.2f",
        len(patterns), len(seed_images), total, total_cost,
    )

    all_results: list[dict] = []
    generated = 0

    # Visual DNA キャッシュ（S6 用: seed ごとに1回だけ抽出）
    visual_dna_cache: dict[str, str] = {}

    for pattern in patterns:
        logger.info("")
        logger.info("-" * 60)
        logger.info("[%s] %s", pattern.id, pattern.name)
        logger.info("  %s", pattern.description)

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

            extracted_style = None

            # Visual DNA 抽出（2段階パターンの場合）
            if pattern.is_two_stage:
                if seed_name in visual_dna_cache:
                    extracted_style = visual_dna_cache[seed_name]
                    logger.info("    Visual DNA キャッシュヒット: seed=%s", seed_name)
                else:
                    logger.info("    Step 1: Visual DNA 抽出中...")
                    try:
                        extracted_style = extract_visual_dna(
                            client, seed_path, pattern.visual_dna_extraction_prompt,
                        )
                        visual_dna_cache[seed_name] = extracted_style
                    except Exception:
                        logger.exception("    Visual DNA 抽出失敗")
                        result = {"status": "failed", "error": "Visual DNA extraction failed"}
                        result.update({
                            "pattern_id": pattern.id,
                            "pattern_name": pattern.name,
                            "seed_image": seed_name,
                            "prompt": pattern.prompt,
                        })
                        all_results.append(result)
                        continue

                logger.info("    Step 2: スタイル適用画像生成中...")

            # 追加参照画像の解決
            extra_ref_paths = None
            if pattern.uses_extra_ref and pattern.extra_ref_images:
                extra_ref_paths = [SEED_CAPTURE_DIR / name for name in pattern.extra_ref_images]

            try:
                result = generate_style_transfer(
                    client=client,
                    pattern=pattern,
                    seed_image_path=seed_path if pattern.uses_seed_image else None,
                    char_ref_path=CHARACTER_REF,
                    output_path=output_path,
                    extra_ref_paths=extra_ref_paths,
                    extracted_style=extracted_style,
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
            if extracted_style:
                result["extracted_style"] = extracted_style
            all_results.append(result)

    # Visual DNA キャッシュの保存
    if visual_dna_cache:
        dna_path = GENERATED_DIR / "visual_dna_cache.json"
        dna_path.parent.mkdir(parents=True, exist_ok=True)
        dna_path.write_text(json.dumps(visual_dna_cache, ensure_ascii=False, indent=2))
        logger.info("Visual DNA キャッシュを保存: %s", dna_path)

    # 実験ログ保存
    log_path = GENERATED_DIR / "experiment_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "experiment": "phase_a4_style_transfer",
        "model": GEMINI_MODEL,
        "aspect_ratio": ASPECT_RATIO,
        "sdk": "google-genai",
        "timestamp": datetime.now().isoformat(),
        "seed_images": seed_images,
        "character_ref": str(CHARACTER_REF),
        "patterns": [
            {
                "id": p.id,
                "name": p.name,
                "description": p.description,
                "uses_seed_image": p.uses_seed_image,
                "uses_extra_ref": p.uses_extra_ref,
                "is_two_stage": p.is_two_stage,
            }
            for p in patterns
        ],
        "results": all_results,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    logger.info("")
    logger.info("実験ログを保存しました: %s", log_path)

    # サマリ
    logger.info("=" * 80)
    logger.info("Phase A-4 スタイル転写 結果サマリ:")
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
