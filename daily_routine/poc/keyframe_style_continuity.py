"""PoC: キーフレーム前カット参照によるスタイル連続性検証.

前カットの生成済みキーフレームを atmosphere reference として渡すことで、
同一ロケーションの連続シーンで色味・トーン・スタイルの一貫性が向上するかを検証する。

デフォルト対象: coffee-pr-001 キッチングループ（Scene 6, 7, 8 — 同一 environment）
  - Scene 6 → アンカー生成（参照なし）
  - Scene 7 → Scene 6 の生成画像を atmosphere reference として渡す
  - Scene 8 → Scene 7 の生成画像を atmosphere reference として渡す

Usage:
    uv run python poc/keyframe_style_continuity.py              # 実行
    uv run python poc/keyframe_style_continuity.py --dry-run     # API スキップ（ロジック確認のみ）
    uv run python poc/keyframe_style_continuity.py --scenes 1 2 9 10  # 別グループで検証
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
from daily_routine.keyframe.prompt import ReferenceInfo  # noqa: E402
from daily_routine.schemas.asset import AssetSet  # noqa: E402
from daily_routine.schemas.keyframe_mapping import KeyframeMapping  # noqa: E402
from daily_routine.schemas.storyboard import Storyboard  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

PROJECT_DIR = _REPO_ROOT / "outputs" / "projects" / "coffee-pr-001"

STYLE_REF_INFO = ReferenceInfo(
    purpose="atmosphere",
    text="Previous cut from the same location. Match the color palette, lighting tone, and overall visual atmosphere.",
    has_image=True,
)


def load_project_data() -> tuple[AssetSet, Storyboard, KeyframeMapping]:
    """プロジェクトの AssetSet, Storyboard, KeyframeMapping を読み込む."""
    asset_path = PROJECT_DIR / "assets" / "asset_set.json"
    assets = AssetSet.model_validate_json(asset_path.read_text())

    storyboard_path = PROJECT_DIR / "storyboard" / "storyboard.json"
    storyboard = Storyboard.model_validate_json(storyboard_path.read_text())

    import yaml

    mapping_path = PROJECT_DIR / "storyboard" / "keyframe_mapping.yaml"
    mapping_data = yaml.safe_load(mapping_path.read_text())
    keyframe_mapping = KeyframeMapping.model_validate(mapping_data)

    return assets, storyboard, keyframe_mapping


def extract_target_cuts(storyboard: Storyboard, scene_numbers: list[int]) -> list:
    """対象シーン番号のカットを順序付きで抽出する."""
    cuts = []
    for scene in storyboard.scenes:
        if scene.scene_number in scene_numbers:
            cuts.extend(scene.cuts)
    return cuts


async def run_verification(dry_run: bool = False, scene_numbers: list[int] | None = None) -> None:
    """検証を実行する."""
    if scene_numbers is None:
        scene_numbers = [6, 7, 8]

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = _REPO_ROOT / "poc" / "keyframe_style_continuity_output" / timestamp

    # データ読み込み
    assets, storyboard, keyframe_mapping = load_project_data()
    target_cuts = extract_target_cuts(storyboard, scene_numbers)

    if not target_cuts:
        logger.error("対象カットが見つかりません: scenes=%s", scene_numbers)
        sys.exit(1)

    logger.info("=== キーフレーム前カット参照 スタイル連続性検証 ===")
    logger.info("プロジェクト: %s", PROJECT_DIR)
    logger.info("出力先: %s", output_dir)
    logger.info("対象シーン: %s", scene_numbers)
    logger.info("対象カット数: %d", len(target_cuts))

    # エンジン（コンポーネント解決用）
    engine = GeminiKeyframeEngine(api_key="")

    # dry-run: コンポーネント解決とプロンプト構築の検証
    logger.info("--- コンポーネント解決・プロンプト検証 ---")
    from daily_routine.keyframe.prompt import build_flash_meta_prompt, build_generation_prompt

    prev_keyframe_path: Path | None = None

    for i, cut in enumerate(target_cuts):
        spec = keyframe_mapping.get_spec(cut.scene_number)
        resolved = engine._resolve_components(assets, spec, require_character=cut.has_character)
        env_image = engine._resolve_environment(assets, cut.scene_number, spec)

        # 前カット参照の注入
        is_anchor = prev_keyframe_path is None
        if prev_keyframe_path is not None:
            resolved.reference_images.append(prev_keyframe_path)
            resolved.reference_infos.append(STYLE_REF_INFO)

        logger.info(
            "  [%s] scene=%d, has_character=%s, char_images=%d, ref_images=%d, env=%s, anchor=%s",
            cut.cut_id,
            cut.scene_number,
            cut.has_character,
            len(resolved.char_images),
            len(resolved.reference_images),
            env_image is not None,
            is_anchor,
        )

        if not is_anchor:
            logger.info("    → 前カット参照: %s", prev_keyframe_path)

        # ポーズ取得
        pose_instruction = cut.pose_instruction
        if spec and spec.pose and not pose_instruction:
            pose_instruction = spec.pose

        # Flash メタプロンプト生成（検証）
        has_env = env_image is not None and env_image.exists()
        flash_meta = build_flash_meta_prompt(
            identity_blocks=resolved.identity_blocks,
            pose_instruction=pose_instruction,
            num_char_images=len(resolved.char_images),
            has_env_image=has_env,
            reference_infos=resolved.reference_infos,
        )
        logger.info("    Flash meta prompt:\n%s", flash_meta)

        # 生成プロンプト検証（ダミーの flash_prompt を使用）
        gen_prompt = build_generation_prompt(
            flash_prompt="[Flash output placeholder]",
            num_char_images=len(resolved.char_images),
            has_env_image=has_env,
            reference_infos=resolved.reference_infos,
        )
        logger.info("    Generation prompt:\n%s", gen_prompt)

        if not is_anchor:
            assert any(info.purpose == "atmosphere" for info in resolved.reference_infos), (
                "atmosphere reference が reference_infos に含まれていない"
            )
            assert "atmosphere" in gen_prompt.lower(), "generation prompt に atmosphere 参照が含まれていない"

        # dry-run 時はダミーパスを設定して次のカットに渡す
        prev_keyframe_path = output_dir / f"{cut.cut_id}.png"

    logger.info("コンポーネント解決・プロンプト構築: OK")

    if dry_run:
        logger.info("=== dry-run モード: API 呼び出しはスキップ ===")
        return

    # 実際の画像生成
    api_key = os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI", "")
    if not api_key:
        logger.error("DAILY_ROUTINE_API_KEY_GOOGLE_AI が設定されていません")
        sys.exit(1)

    client = GeminiKeyframeClient(api_key=api_key)
    output_dir.mkdir(parents=True, exist_ok=True)

    results: list[dict] = []
    prev_keyframe_path = None

    for i, cut in enumerate(target_cuts):
        logger.info("=== カット %d/%d: %s ===", i + 1, len(target_cuts), cut.cut_id)

        spec = keyframe_mapping.get_spec(cut.scene_number)
        resolved = engine._resolve_components(assets, spec, require_character=cut.has_character)
        env_image = engine._resolve_environment(assets, cut.scene_number, spec)

        # 前カット参照の注入
        is_anchor = prev_keyframe_path is None
        if prev_keyframe_path is not None and prev_keyframe_path.exists():
            resolved.reference_images.append(prev_keyframe_path)
            resolved.reference_infos.append(STYLE_REF_INFO)
            logger.info("  前カット参照を注入: %s", prev_keyframe_path)
        elif prev_keyframe_path is not None:
            logger.warning("  前カット画像が存在しません（スキップ）: %s", prev_keyframe_path)

        # ポーズ取得
        pose_instruction = cut.pose_instruction
        if spec and spec.pose and not pose_instruction:
            pose_instruction = spec.pose

        # Step 1: Flash シーン分析
        logger.info("  Step 1: Flash シーン分析")
        flash_prompt = await client.analyze_scene(
            char_images=resolved.char_images,
            env_image=env_image,
            identity_blocks=resolved.identity_blocks,
            pose_instruction=pose_instruction,
            reference_images=resolved.reference_images,
            reference_infos=resolved.reference_infos,
        )
        logger.info("  Flash 生成プロンプト: %s", flash_prompt[:200])

        # Step 2: Pro シーン画像生成
        keyframe_path = output_dir / f"{cut.cut_id}.png"
        logger.info("  Step 2: Pro シーン画像生成")
        result_path = await client.generate_keyframe(
            char_images=resolved.char_images,
            env_image=env_image,
            flash_prompt=flash_prompt,
            reference_images=resolved.reference_images,
            reference_infos=resolved.reference_infos,
            output_path=keyframe_path,
        )

        file_size = result_path.stat().st_size
        logger.info("  生成完了: %s (%d bytes)", result_path, file_size)

        results.append(
            {
                "cut_id": cut.cut_id,
                "scene_number": cut.scene_number,
                "image_path": str(result_path),
                "prompt": flash_prompt,
                "file_size": file_size,
                "is_anchor": is_anchor,
                "previous_cut_ref": str(prev_keyframe_path) if prev_keyframe_path else None,
            }
        )

        prev_keyframe_path = result_path

    # サマリ保存
    summary = {
        "timestamp": timestamp,
        "scene_numbers": scene_numbers,
        "style_reference_info": {
            "purpose": STYLE_REF_INFO.purpose,
            "text": STYLE_REF_INFO.text,
        },
        "keyframes": results,
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, ensure_ascii=False))

    logger.info("=== 検証完了 ===")
    logger.info("サマリ: %s", summary_path)
    for r in results:
        ref_info = f"← {r['previous_cut_ref']}" if r["previous_cut_ref"] else "(anchor)"
        logger.info("  %s: %s %s", r["cut_id"], r["image_path"], ref_info)


def main() -> None:
    parser = argparse.ArgumentParser(description="キーフレーム前カット参照によるスタイル連続性検証")
    parser.add_argument("--dry-run", action="store_true", help="API 呼び出しをスキップ")
    parser.add_argument(
        "--scenes",
        nargs="+",
        type=int,
        default=None,
        help="検証対象のシーン番号（デフォルト: 6 7 8）",
    )
    args = parser.parse_args()
    asyncio.run(run_verification(dry_run=args.dry_run, scene_numbers=args.scenes))


if __name__ == "__main__":
    main()
