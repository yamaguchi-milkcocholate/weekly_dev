"""Visual Core 統合検証スクリプト（シーン1のみ）.

Usage:
    uv run python poc/visual_core_verify.py
"""

import asyncio
import json
import logging
import sys
from pathlib import Path

# リポジトリルートをパスに追加
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from daily_routine.config.manager import load_global_config
from daily_routine.schemas.asset import AssetSet
from daily_routine.schemas.scenario import Scenario
from daily_routine.visual.engine import create_visual_engine

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_DIR = REPO_ROOT / "outputs" / "projects" / "OLの一日_20260224_173216"


async def main() -> None:
    """シーン1のみの動画生成検証."""
    # 1. 設定読み込み
    config = load_global_config()
    logger.info("設定読み込み完了: provider=%s, bucket=%s", config.visual.provider, config.visual.runway.gcs_bucket)

    # 2. Scenario / AssetSet 読み込み
    scenario_path = PROJECT_DIR / "scenario" / "scenario.json"
    asset_path = PROJECT_DIR / "assets" / "asset_set.json"

    scenario = Scenario(**json.loads(scenario_path.read_text()))
    assets = AssetSet(**json.loads(asset_path.read_text()))

    logger.info("Scenario: %d シーン, キャラ: %s", len(scenario.scenes), scenario.characters[0].name)
    logger.info("リファレンス画像: %s", assets.characters[0].front_view)

    # front_view のパスがリポジトリルートからの相対パスの場合、絶対パスに変換
    front_view = assets.characters[0].front_view
    if not front_view.is_absolute():
        front_view = REPO_ROOT / front_view
    if not front_view.exists():
        logger.error("リファレンス画像が存在しません: %s", front_view)
        return

    logger.info("リファレンス画像を確認しました: %s (%d bytes)", front_view, front_view.stat().st_size)

    # 3. エンジン生成
    engine = create_visual_engine(config)
    logger.info("VisualEngine 生成完了")

    # 4. シーン1のみ生成
    scene = scenario.scenes[0]
    output_dir = PROJECT_DIR / "clips"
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / "scene_01.mp4"

    logger.info("=== シーン1 動画生成開始 ===")
    logger.info("prompt: %s", scene.video_prompt)
    logger.info("duration: %.1f秒", scene.duration_sec)
    logger.info("output: %s", output_path)

    clip_path = await engine.generate_scene_clip(
        scene_number=scene.scene_number,
        prompt=scene.video_prompt,
        reference_image=front_view,
        output_path=output_path,
    )

    result = engine._last_result
    logger.info("=== シーン1 動画生成完了 ===")
    logger.info("動画パス: %s", clip_path)
    logger.info("ファイルサイズ: %d bytes", clip_path.stat().st_size)
    logger.info("生成時間: %.1f秒", result.generation_time_sec)
    logger.info("モデル: %s", result.model_name)
    logger.info("コスト: $%.2f", result.cost_usd or 0)


if __name__ == "__main__":
    asyncio.run(main())
