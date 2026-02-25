"""キーフレーム画像生成PoC: 実験実行スクリプト.

プロンプトパターン × シーンの全組み合わせで画像を生成し、
結果を generated/ に保存する。

Usage:
    uv run python poc/keyframe_gen/run_experiment.py --dry-run
    uv run python poc/keyframe_gen/run_experiment.py --reference-dir outputs/projects/test-verify/assets/character/彩香
    uv run python poc/keyframe_gen/run_experiment.py --patterns A,B --scenes bed,desk
"""

import argparse
import asyncio
import json
import logging
import sys
from datetime import datetime
from pathlib import Path

# プロジェクトルートをsys.pathに追加
_REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_REPO_ROOT / "src"))

from config import (  # noqa: E402
    CHAR_TAG,
    DEFAULT_REFERENCE_DIR,
    GENERATED_DIR,
    LOCATION_TAG,
    PROMPT_PATTERNS,
    SCENES,
    build_prompt,
    find_location_ref,
    get_patterns_by_ids,
    get_scenes_by_ids,
)

from daily_routine.config.manager import load_global_config  # noqa: E402
from daily_routine.utils.uploader import GcsUploader  # noqa: E402
from daily_routine.visual.clients.gen4_image import ImageGenerationRequest, RunwayImageClient  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="キーフレーム画像生成PoC: キャラクター分裂検証")
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="実行パターンをカンマ区切りで指定 (例: A,B,C,D)",
    )
    parser.add_argument(
        "--scenes",
        type=str,
        default=None,
        help="実行シーンをカンマ区切りで指定 (例: bed,cafe,desk,walk)",
    )
    parser.add_argument(
        "--reference-dir",
        type=Path,
        default=None,
        help=f"参照画像ディレクトリ (デフォルト: {DEFAULT_REFERENCE_DIR})",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="プロンプト生成のみ、API呼び出しなし",
    )
    return parser.parse_args()


async def run_experiment(args: argparse.Namespace) -> None:
    patterns = get_patterns_by_ids(args.patterns.split(",")) if args.patterns else PROMPT_PATTERNS
    scenes = get_scenes_by_ids(args.scenes.split(",")) if args.scenes else SCENES
    reference_dir = args.reference_dir or DEFAULT_REFERENCE_DIR
    reference_image = reference_dir / "front.png"

    if not reference_image.exists():
        logger.error("参照画像が見つかりません: %s", reference_image)
        sys.exit(1)

    # Location 参照パターンの場合、背景画像の存在チェック
    has_location_patterns = any(p.use_location_tag for p in patterns)
    if has_location_patterns:
        for scene in scenes:
            loc_ref = find_location_ref(scene.id)
            if loc_ref:
                logger.info("背景参照画像: %s -> %s", scene.id, loc_ref)
            else:
                logger.warning("背景参照画像が見つかりません: %s（Location参照パターンはスキップされます）", scene.id)

    total = len(patterns) * len(scenes)
    logger.info("実験開始: %d パターン × %d シーン = %d 画像", len(patterns), len(scenes), total)
    logger.info("キャラクター参照画像: %s", reference_image)

    # 全組み合わせのプロンプトを表示
    for pattern in patterns:
        for scene in scenes:
            prompt = build_prompt(pattern, scene)
            tags = []
            if pattern.use_char_tag:
                tags.append("@char")
            if pattern.use_location_tag:
                tags.append("@location")
            if not tags:
                tags.append("代名詞（referenceImages のみ）")
            tag_mode = " + ".join(tags)
            logger.info(
                "[%s-%s] %s / %s (分裂リスク: %s)\n  モード: %s\n  プロンプト: %s",
                pattern.id,
                scene.id,
                pattern.name,
                scene.name,
                scene.split_risk,
                tag_mode,
                prompt,
            )

    if args.dry_run:
        logger.info("ドライラン完了。API呼び出しはスキップされました。")
        estimated_cost = total * 0.02
        logger.info("推定コスト: $%.2f (%d 画像 × $0.02)", estimated_cost, total)
        return

    # 設定読み込み・クライアント初期化
    global_config = load_global_config()
    uploader = GcsUploader(
        bucket_name=global_config.visual.runway.gcs_bucket,
        prefix="poc/keyframe_gen/",
    )
    client = RunwayImageClient(
        api_key=global_config.api_keys.runway,
        uploader=uploader,
        model=global_config.visual.runway.image_model,
    )

    experiment_log: list[dict] = []
    completed = 0

    for pattern in patterns:
        for scene in scenes:
            prompt = build_prompt(pattern, scene)
            output_path = GENERATED_DIR / pattern.id / f"{scene.id}.png"

            # 参照画像の設定
            reference_images: dict[str, Path] = {}
            location_ref_path: Path | None = None

            if pattern.use_char_tag:
                reference_images[CHAR_TAG] = reference_image
            else:
                # パターンC: @tag なしだが referenceImages は送信
                reference_images["subject"] = reference_image

            if pattern.use_location_tag:
                location_ref_path = find_location_ref(scene.id)
                if location_ref_path:
                    reference_images[LOCATION_TAG] = location_ref_path
                else:
                    logger.warning(
                        "[%s-%s] 背景参照画像なし、スキップします",
                        pattern.id,
                        scene.id,
                    )
                    completed += 1
                    continue

            request = ImageGenerationRequest(
                prompt=prompt,
                reference_images=reference_images,
            )

            ref_info = f"char={reference_image.name}"
            if location_ref_path:
                ref_info += f", location={location_ref_path.name}"

            try:
                logger.info(
                    "[%d/%d] 生成中: %s-%s (%s / %s) refs=[%s]",
                    completed + 1,
                    total,
                    pattern.id,
                    scene.id,
                    pattern.name,
                    scene.name,
                    ref_info,
                )
                result = await client.generate(request, output_path)

                entry = {
                    "pattern_id": pattern.id,
                    "pattern_name": pattern.name,
                    "scene_id": scene.id,
                    "scene_name": scene.name,
                    "split_risk": scene.split_risk,
                    "prompt": prompt,
                    "use_char_tag": pattern.use_char_tag,
                    "use_location_tag": pattern.use_location_tag,
                    "reference_image": str(reference_image),
                    "location_ref_image": str(location_ref_path) if location_ref_path else None,
                    "output_path": str(result.image_path),
                    "model_name": result.model_name,
                    "cost_usd": result.cost_usd,
                    "status": "success",
                }
            except Exception:
                logger.exception("生成失敗: %s-%s", pattern.id, scene.id)
                entry = {
                    "pattern_id": pattern.id,
                    "pattern_name": pattern.name,
                    "scene_id": scene.id,
                    "scene_name": scene.name,
                    "split_risk": scene.split_risk,
                    "prompt": prompt,
                    "use_char_tag": pattern.use_char_tag,
                    "use_location_tag": pattern.use_location_tag,
                    "reference_image": str(reference_image),
                    "location_ref_image": str(location_ref_path) if location_ref_path else None,
                    "output_path": str(output_path),
                    "status": "failed",
                }

            experiment_log.append(entry)
            completed += 1

    # ログ保存
    log_path = GENERATED_DIR / "experiment_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "experiment": "keyframe_gen_split_test",
        "timestamp": datetime.now().isoformat(),
        "reference_image": str(reference_image),
        "total_combinations": total,
        "results": experiment_log,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    logger.info("実験ログを保存しました: %s", log_path)

    # サマリ表示
    success_count = sum(1 for e in experiment_log if e["status"] == "success")
    failed_count = total - success_count
    total_cost = sum(e.get("cost_usd", 0) or 0 for e in experiment_log)
    logger.info("完了: 成功=%d, 失敗=%d, コスト=$%.2f", success_count, failed_count, total_cost)


def main() -> None:
    args = parse_args()
    asyncio.run(run_experiment(args))


if __name__ == "__main__":
    main()
