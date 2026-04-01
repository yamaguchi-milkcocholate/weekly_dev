"""PoC Step 6: 3Dレンダリング → AI画像生成（テキストスタイル方式）.

Gemini 3.0 Pro Imageで、レンダリング画像+テキストスタイルから
フォトリアリスティックなインテリア画像を生成する。

Usage:
    uv run python poc/3dcg_poc6/run_experiment.py --dry-run \
        --style-text "Bright, airy natural interior with warm wood tones..."
    uv run python poc/3dcg_poc6/run_experiment.py \
        --style-text "Industrial loft with exposed concrete..." \
        --cameras カメラ4
    uv run python poc/3dcg_poc6/run_experiment.py --evaluate-only
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

from config import (
    CAMERA_ANGLES,
    EVALUATION_DIR,
    GENERATED_DIR,
    INPUT_DIR,
    build_prompt,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


# --- 入力検証 ---


def validate_inputs(camera_ids: list[str]) -> None:
    """入力ファイルの存在を検証する."""
    for cam in CAMERA_ANGLES:
        if cam.id not in camera_ids:
            continue
        render_path = INPUT_DIR / cam.filename
        if not render_path.exists():
            logger.error("レンダリング画像が見つかりません: %s", render_path)
            sys.exit(1)

    logger.info("入力検証完了: %d カメラ", len(camera_ids))


# --- Phase 1: 画像生成 ---


async def run_generation(style_text: str, camera_ids: list[str]) -> list[dict]:
    """各カメラで画像を生成する."""
    from clients.base import RenderToImageRequest
    from clients.gemini import GeminiRenderClient

    client = GeminiRenderClient()
    prompt = build_prompt(style_text)
    results = []

    for cam in CAMERA_ANGLES:
        if cam.id not in camera_ids:
            continue

        render_path = INPUT_DIR / cam.filename
        output_path = GENERATED_DIR / cam.filename

        request = RenderToImageRequest(
            render_image_path=render_path,
            style_text=style_text,
            prompt=prompt,
            camera_id=cam.id,
        )

        try:
            result = await client.generate(request, output_path)
            results.append({
                "camera_id": result.camera_id,
                "image_path": str(result.image_path),
                "generation_time_sec": result.generation_time_sec,
                "cost_usd": result.cost_usd,
                "model_name": result.model_name,
                "status": "success",
            })
        except Exception:
            logger.exception("%s で生成エラー", cam.id)
            results.append({
                "camera_id": cam.id,
                "status": "error",
            })

    return results


# --- Phase 1: 評価 ---


def run_phase1_evaluation(camera_ids: list[str]) -> list[dict]:
    """Phase 1: 各生成画像を個別に評価する."""
    from evaluate import evaluate_phase1

    results = []

    for cam in CAMERA_ANGLES:
        if cam.id not in camera_ids:
            continue

        generated_path = GENERATED_DIR / cam.filename
        if not generated_path.exists():
            logger.warning("生成画像が見つかりません: %s", generated_path)
            continue

        render_path = INPUT_DIR / cam.filename

        try:
            result = evaluate_phase1(
                camera_id=cam.id,
                render_image=render_path,
                generated_image=generated_path,
            )
            results.append(result.model_dump())
        except Exception:
            logger.exception("%s の評価エラー", cam.id)

    return results


# --- Phase 2: 一貫性評価 ---


def run_phase2_evaluation(camera_ids: list[str]) -> dict | None:
    """Phase 2: 全カメラ画像の一貫性を評価する."""
    from evaluate import evaluate_phase2

    generated_images = []
    for cam in CAMERA_ANGLES:
        if cam.id not in camera_ids:
            continue
        path = GENERATED_DIR / cam.filename
        if path.exists():
            generated_images.append(path)

    if len(generated_images) < 2:
        logger.warning("一貫性評価には2枚以上の画像が必要（%d枚）", len(generated_images))
        return None

    try:
        result = evaluate_phase2(generated_images=generated_images)
        return result.model_dump()
    except Exception:
        logger.exception("一貫性評価エラー")
        return None


# --- レポート生成 ---


def generate_report(
    generation_results: list[dict],
    phase1_scores: list[dict],
    phase2_score: dict | None,
    style_text: str,
) -> dict:
    """最終レポートを生成する."""
    # Phase 1 平均スコア
    if phase1_scores:
        avg = {
            "structure_preservation": sum(s["score"]["structure_preservation"] for s in phase1_scores) / len(phase1_scores),
            "style_reflection": sum(s["score"]["style_reflection"] for s in phase1_scores) / len(phase1_scores),
            "generation_quality": sum(s["score"]["generation_quality"] for s in phase1_scores) / len(phase1_scores),
        }
        avg["weighted_average"] = (
            avg["structure_preservation"] * 0.4
            + avg["style_reflection"] * 0.3
            + avg["generation_quality"] * 0.3
        )
    else:
        avg = {}

    return {
        "timestamp": datetime.now().isoformat(),
        "model": "gemini-3-pro-image-preview",
        "style_text": style_text,
        "generation_results": generation_results,
        "phase1_scores": phase1_scores,
        "phase1_average": avg,
        "phase2_score": phase2_score,
    }


# --- Dry Run ---


def print_dry_run(style_text: str, camera_ids: list[str]) -> None:
    """プロンプトとコスト見積もりを表示する."""
    prompt = build_prompt(style_text)
    n = len(camera_ids)
    cost = 0.134 * n

    print(f"\n{'=' * 60}")
    print("  Gemini 3.0 Pro Image（テキストスタイル方式）")
    print(f"{'=' * 60}")
    print(f"  カメラ数: {n}")
    print(f"  コスト見積もり: ${cost:.3f}")
    print(f"\n  プロンプト:\n{prompt}")
    print(f"\n{'=' * 60}")
    print(f"  合計: {n}枚, ${cost:.3f}")
    print(f"{'=' * 60}")


# --- メイン ---


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="PoC Step 6: 3Dレンダリング→AI画像生成（テキストスタイル方式）")
    parser.add_argument("--style-text", type=str, default=None, help="スタイル記述テキスト（生成時は必須）")
    parser.add_argument("--cameras", type=str, default=None, help="対象カメラをカンマ区切りで指定（例: カメラ1,カメラ3）")
    parser.add_argument("--evaluate-only", action="store_true", help="評価のみ実行（生成済みの画像を使用）")
    parser.add_argument("--dry-run", action="store_true", help="プロンプト確認・コスト見積もりのみ")
    return parser.parse_args()


def main() -> None:
    load_dotenv()
    args = parse_args()

    camera_ids = args.cameras.split(",") if args.cameras else [c.id for c in CAMERA_ANGLES]
    style_text = args.style_text or ""

    if not args.evaluate_only and not style_text:
        logger.error("--style-text は生成時に必須です")
        sys.exit(1)

    if args.dry_run:
        print_dry_run(style_text, camera_ids)
        return

    validate_inputs(camera_ids)

    generation_results = []
    phase1_scores = []
    phase2_score = None

    # Phase 1: 生成
    if not args.evaluate_only:
        logger.info("===== 画像生成 =====")
        generation_results = asyncio.run(run_generation(style_text, camera_ids))

    # Phase 1: 評価
    logger.info("===== Phase 1: 評価 =====")
    phase1_scores = run_phase1_evaluation(camera_ids)

    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    phase1_path = EVALUATION_DIR / "phase1_scores.json"
    phase1_path.write_text(json.dumps(phase1_scores, ensure_ascii=False, indent=2))
    logger.info("Phase 1 評価結果: %s", phase1_path)

    # Phase 2: 一貫性評価
    logger.info("===== Phase 2: 一貫性評価 =====")
    phase2_score = run_phase2_evaluation(camera_ids)

    if phase2_score:
        phase2_path = EVALUATION_DIR / "phase2_scores.json"
        phase2_path.write_text(json.dumps(phase2_score, ensure_ascii=False, indent=2))
        logger.info("Phase 2 評価結果: %s", phase2_path)

    # レポート生成
    report = generate_report(generation_results, phase1_scores, phase2_score, style_text)
    report_path = EVALUATION_DIR / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    logger.info("最終レポート: %s", report_path)

    # スコア表示
    if report.get("phase1_average"):
        avg = report["phase1_average"]
        print(f"\n===== Phase 1 平均スコア =====")
        print(f"  構造維持: {avg['structure_preservation']:.1f}")
        print(f"  スタイル反映: {avg['style_reflection']:.1f}")
        print(f"  生成品質: {avg['generation_quality']:.1f}")
        print(f"  加重平均: {avg['weighted_average']:.1f}")

    if phase2_score:
        s = phase2_score["score"]
        print(f"\n===== Phase 2 一貫性スコア =====")
        print(f"  マテリアル: {s['material_consistency']}")
        print(f"  照明: {s['lighting_consistency']}")
        print(f"  色調: {s['color_consistency']}")
        print(f"  総合: {s['overall_consistency']}")


if __name__ == "__main__":
    main()
