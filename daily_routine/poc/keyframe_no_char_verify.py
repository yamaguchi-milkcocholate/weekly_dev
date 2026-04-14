"""キーフレーム生成: キャラクター不在カットの動作検証.

既存プロジェクト coffee-cm-001 のデータを使い、has_character=False のカットで
キャラクター画像が注入されず、オブジェクト単体の画像が正しく生成されることを確認する。

検証パターン:
  - scene_03: コーヒー豆が宙に舞うスローモーション（黒背景 + 商品ショット）
  - scene_04: ドリップポットからお湯を注ぐクローズアップ（ASMR 系プロダクトショット）

Usage:
    uv run python poc/keyframe_no_char_verify.py
    uv run python poc/keyframe_no_char_verify.py --dry-run
"""

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv

_REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO_ROOT / "src"))
load_dotenv(_REPO_ROOT / ".env")

from daily_routine.keyframe.client import GeminiKeyframeClient  # noqa: E402
from daily_routine.keyframe.engine import GeminiKeyframeEngine  # noqa: E402
from daily_routine.schemas.asset import AssetSet  # noqa: E402
from daily_routine.schemas.storyboard import CutSpec, MotionIntensity, SceneStoryboard, Storyboard, Transition  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_DIR = _REPO_ROOT / "outputs" / "projects" / "coffee-cm-001"


def load_asset_set() -> AssetSet:
    """プロジェクトの AssetSet を読み込む."""
    asset_path = PROJECT_DIR / "assets" / "asset_set.json"
    return AssetSet.model_validate_json(asset_path.read_text())


def build_test_storyboard() -> Storyboard:
    """検証用の Storyboard を構築する（scene_03, scene_04 のみ）."""
    return Storyboard(
        title="キャラクター不在検証",
        total_duration_sec=4.0,
        total_cuts=2,
        scenes=[
            SceneStoryboard(
                scene_number=3,
                scene_duration_sec=2.0,
                cuts=[
                    CutSpec(
                        cut_id="scene_03_cut_01",
                        scene_number=3,
                        cut_number=1,
                        duration_sec=2.0,
                        motion_intensity=MotionIntensity.DYNAMIC,
                        camera_work="slow motion capture, slight upward tilt",
                        action_description="コーヒー豆が宙に舞うスローモーション",
                        motion_prompt="Roasted coffee beans tumbling in slow motion",
                        keyframe_prompt=(
                            "Roasted coffee beans suspended in mid-air against pure black background, "
                            "dramatic side lighting, high contrast, commercial photography"
                        ),
                        transition=Transition.CUT,
                        has_character=False,
                    ),
                ],
            ),
            SceneStoryboard(
                scene_number=4,
                scene_duration_sec=2.0,
                cuts=[
                    CutSpec(
                        cut_id="scene_04_cut_01",
                        scene_number=4,
                        cut_number=1,
                        duration_sec=2.0,
                        motion_intensity=MotionIntensity.SUBTLE,
                        camera_work="extreme close-up, static with slight drift",
                        action_description="ドリップポットからお湯を注ぐクローズアップ",
                        motion_prompt="Hot water pours from gooseneck kettle into dripper",
                        keyframe_prompt=(
                            "Extreme close-up of gooseneck kettle pouring hot water into pour-over coffee dripper, "
                            "steam rising, warm amber lighting, ASMR aesthetic"
                        ),
                        transition=Transition.CROSS_FADE,
                        has_character=False,
                    ),
                ],
            ),
        ],
    )


async def run_verification(dry_run: bool = False) -> None:
    """検証を実行する."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = _REPO_ROOT / "poc" / "keyframe_no_char_verify_output" / timestamp

    # データ読み込み
    assets = load_asset_set()
    storyboard = build_test_storyboard()

    logger.info("=== キャラクター不在キーフレーム生成 検証 ===")
    logger.info("プロジェクト: %s", PROJECT_DIR)
    logger.info("出力先: %s", output_dir)
    logger.info("検証カット数: %d", storyboard.total_cuts)
    logger.info("キャラクターアセット数: %d", len(assets.characters))

    # エンジン解決の検証（dry_run でも実行）
    from daily_routine.keyframe.engine import GeminiKeyframeEngine

    engine = GeminiKeyframeEngine(api_key="")

    for scene in storyboard.scenes:
        for cut in scene.cuts:
            spec = None  # マッピングなし
            resolved = engine._resolve_components(assets, spec, require_character=cut.has_character)
            logger.info(
                "  [%s] has_character=%s → char_images=%d, identity_blocks=%d, ref_images=%d",
                cut.cut_id,
                cut.has_character,
                len(resolved.char_images),
                len(resolved.identity_blocks),
                len(resolved.reference_images),
            )
            if cut.has_character:
                assert len(resolved.char_images) > 0, "has_character=True なのに char_images が空"
            else:
                assert len(resolved.char_images) == 0, "has_character=False なのに char_images が存在"
                assert len(resolved.identity_blocks) == 0, "has_character=False なのに identity_blocks が存在"

    logger.info("コンポーネント解決: OK（キャラクター注入なし確認済み）")

    # プロンプト生成の検証
    from daily_routine.keyframe.prompt import build_flash_meta_prompt, build_generation_prompt

    flash_prompt = build_flash_meta_prompt(
        identity_blocks=[],
        pose_instruction="",
        num_char_images=0,
        has_env_image=True,
    )
    logger.info("Flash meta prompt (no char):\n%s", flash_prompt)
    assert "character" not in flash_prompt.lower(), "identity_blocks 空なのに character が含まれている"

    gen_prompt = build_generation_prompt(
        flash_prompt="Coffee beans on table",
        num_char_images=0,
        has_env_image=True,
    )
    logger.info("Generation prompt (no char):\n%s", gen_prompt)
    assert "No people" in gen_prompt, "num_char_images=0 なのに 'No people' が含まれていない"

    logger.info("プロンプト生成: OK（キャラクター関連なし確認済み）")

    if dry_run:
        logger.info("=== dry-run モード: API 呼び出しはスキップ ===")
        return

    # 実際の画像生成
    api_key = os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI", "")
    if not api_key:
        logger.error("DAILY_ROUTINE_API_KEY_GOOGLE_AI が設定されていません")
        sys.exit(1)

    client = GeminiKeyframeClient(api_key=api_key)
    engine = GeminiKeyframeEngine.from_components(client)

    # scenario はダミー（generate_keyframes 内では直接使われない）
    from daily_routine.schemas.scenario import CameraWork, CharacterSpec, Scenario, SceneSpec

    scenario = Scenario(
        title="ダミー",
        total_duration_sec=4.0,
        characters=[
            CharacterSpec(
                name="Aoi",
                appearance="",
                outfit="",
                reference_prompt="",
            )
        ],
        scenes=[
            SceneSpec(
                scene_number=3,
                duration_sec=2.0,
                situation="",
                camera_work=CameraWork(type="close-up", description=""),
                caption_text="",
                image_prompt="",
            ),
            SceneSpec(
                scene_number=4,
                duration_sec=2.0,
                situation="",
                camera_work=CameraWork(type="close-up", description=""),
                caption_text="",
                image_prompt="",
            ),
        ],
        bgm_direction="",
    )

    result = await engine.generate_keyframes(
        scenario=scenario,
        storyboard=storyboard,
        assets=assets,
        output_dir=output_dir,
    )

    logger.info("=== 生成完了 ===")
    for kf in result.keyframes:
        logger.info("  %s: %s (%d bytes)", kf.cut_id, kf.image_path, kf.image_path.stat().st_size)
        logger.info("  prompt: %s", kf.prompt[:150])

    # 結果サマリを JSON 保存
    summary = {
        "timestamp": timestamp,
        "keyframes": [
            {
                "cut_id": kf.cut_id,
                "image_path": str(kf.image_path),
                "prompt": kf.prompt,
                "file_size": kf.image_path.stat().st_size,
            }
            for kf in result.keyframes
        ],
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))
    logger.info("サマリ: %s", summary_path)


def main() -> None:
    parser = argparse.ArgumentParser(description="キャラクター不在キーフレーム生成の検証")
    parser.add_argument("--dry-run", action="store_true", help="API 呼び出しをスキップ")
    args = parser.parse_args()
    asyncio.run(run_verification(dry_run=args.dry_run))


if __name__ == "__main__":
    main()
