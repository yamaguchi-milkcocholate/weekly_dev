"""keyframe_mapping.yaml コンポーネント化の動作検証スクリプト.

検証内容:
  1. 旧フォーマット YAML の後方互換（自動変換）
  2. 新フォーマット YAML（components リスト）のパース
  3. 単独キャラクターシーン（シーン1: Yui casual）のキーフレーム生成
  4. ツーショットシーン（シーン2: Yui casual + Saki casual）のキーフレーム生成

コスト: Flash 2回 + Pro 2回 = 4 API コール

Usage:
  uv run python poc/keyframe_gen/verify_components.py
  uv run python poc/keyframe_gen/verify_components.py --dry-run   # API コールなし
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# --- パス解決 ---
REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "src"))

load_dotenv(REPO_ROOT / ".env")

from daily_routine.keyframe.client import GeminiKeyframeClient  # noqa: E402
from daily_routine.keyframe.engine import GeminiKeyframeEngine  # noqa: E402
from daily_routine.keyframe.prompt import ReferenceInfo, build_flash_meta_prompt, build_generation_prompt  # noqa: E402
from daily_routine.schemas.asset import AssetSet  # noqa: E402
from daily_routine.schemas.keyframe_mapping import (  # noqa: E402
    CharacterComponent,
    KeyframeMapping,
    ReferenceComponent,
    ReferencePurpose,
    SceneKeyframeSpec,
)
from daily_routine.schemas.scenario import Scenario  # noqa: E402
from daily_routine.schemas.storyboard import Storyboard  # noqa: E402

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)

# --- プロジェクトパス ---
PROJECT_DIR = REPO_ROOT / "outputs" / "projects" / "ダイビングOLの休日_tmp"
ASSET_SET_PATH = PROJECT_DIR / "assets" / "asset_set.json"
STORYBOARD_PATH = PROJECT_DIR / "storyboard" / "storyboard.json"
SCENARIO_PATH = PROJECT_DIR / "scenario" / "scenario.json"
OLD_MAPPING_PATH = PROJECT_DIR / "storyboard" / "keyframe_mapping.yaml"
OUTPUT_DIR = REPO_ROOT / "poc" / "keyframe_gen" / "generated" / "verify_components"


def verify_backward_compat() -> None:
    """検証1: 旧フォーマット YAML の後方互換."""
    import yaml

    print("\n" + "=" * 60)
    print("検証1: 旧フォーマット YAML の後方互換")
    print("=" * 60)

    raw = yaml.safe_load(OLD_MAPPING_PATH.read_text(encoding="utf-8"))
    mapping = KeyframeMapping.model_validate(raw)

    for spec in mapping.scenes:
        print(f"\n  scene {spec.scene_number}:")
        print(f"    旧 character: {spec.character!r}")
        print(f"    旧 variant_id: {spec.variant_id!r}")
        print(f"    旧 reference_image: {spec.reference_image}")
        print(f"    旧 reference_text: {spec.reference_text!r}")
        print(f"    → components ({len(spec.components)} 件):")
        for i, comp in enumerate(spec.components):
            if isinstance(comp, CharacterComponent):
                print(f"      [{i}] type=character, char={comp.character!r}, variant={comp.variant_id!r}")
            elif isinstance(comp, ReferenceComponent):
                print(f"      [{i}] type=reference, image={comp.image}, text={comp.text!r}")
        print(f"    primary_character: {spec.primary_character}")
        print(f"    character_components: {len(spec.character_components)}")
        print(f"    reference_components: {len(spec.reference_components)}")

    print("\n  ✓ 旧フォーマットの自動変換が正常に動作")


def verify_new_format_parse() -> None:
    """検証2: 新フォーマットのパース."""
    print("\n" + "=" * 60)
    print("検証2: 新フォーマット YAML のパース")
    print("=" * 60)

    new_mapping = KeyframeMapping(
        scenes=[
            SceneKeyframeSpec(
                scene_number=1,
                environment="ダイビング船デッキ",
                pose="フルフェイスマスクを装着している最中のポーズ",
                components=[
                    CharacterComponent(character="Yui", variant_id="drysuits"),
                    ReferenceComponent(
                        image=PROJECT_DIR / "assets" / "items" / "full_face_mask.png",
                        text="フルフェイスマスク",
                    ),
                ],
            ),
            SceneKeyframeSpec(
                scene_number=2,
                environment="水中シーン",
                pose="カメラに向かって手を振る",
                components=[
                    CharacterComponent(character="Yui", variant_id="drysuits"),
                    CharacterComponent(character="Saki", variant_id="drysuits"),
                    ReferenceComponent(text="ダイビング機材を装着した二人が、カメラに向かって自然に手を振る"),
                ],
            ),
        ]
    )

    for spec in new_mapping.scenes:
        print(f"\n  scene {spec.scene_number}:")
        print(f"    components: {len(spec.components)} 件")
        print(f"    character_components: {len(spec.character_components)}")
        print(f"    reference_components: {len(spec.reference_components)}")
        if spec.primary_character:
            print(f"    primary_character: {spec.primary_character.character} ({spec.primary_character.variant_id})")

    # JSON ラウンドトリップ
    dumped = new_mapping.model_dump(mode="json")
    restored = KeyframeMapping.model_validate(dumped)
    assert len(restored.scenes) == 2
    assert len(restored.scenes[1].character_components) == 2
    print("\n  ✓ 新フォーマットのパース・ラウンドトリップが正常")


def verify_prompt_generation() -> None:
    """検証3: プロンプト生成の確認（purpose 対応）."""
    print("\n" + "=" * 60)
    print("検証3: プロンプト生成（purpose 対応）")
    print("=" * 60)

    # 単独キャラ（参照なし）
    flash_single = build_flash_meta_prompt(
        identity_blocks=["Young adult female, dark brown hair"],
        pose_instruction="右手でカップを口元へ",
        num_char_images=1,
        has_env_image=True,
    )
    gen_single = build_generation_prompt(
        flash_prompt="A young woman in a cafe...",
        num_char_images=1,
        has_env_image=True,
    )
    print("\n  [単独キャラ・参照なし] Flash meta prompt:")
    for line in flash_single.split("\n"):
        print(f"    {line}")
    print("\n  [単独キャラ・参照なし] Generation prompt:")
    for line in gen_single.split("\n"):
        print(f"    {line}")
    assert "Single person only, solo" in gen_single

    # wearing 参照付き
    wearing_infos = [ReferenceInfo(purpose="wearing", text="フルフェイスマスク", has_image=True)]
    flash_wearing = build_flash_meta_prompt(
        identity_blocks=["Young adult female, dark brown hair"],
        pose_instruction="フルフェイスマスクを装着している最中",
        num_char_images=1,
        has_env_image=True,
        reference_infos=wearing_infos,
    )
    gen_wearing = build_generation_prompt(
        flash_prompt="A young woman putting on a full face mask...",
        num_char_images=1,
        has_env_image=True,
        reference_infos=wearing_infos,
    )
    print("\n  [wearing 参照] Flash meta prompt:")
    for line in flash_wearing.split("\n"):
        print(f"    {line}")
    print("\n  [wearing 参照] Generation prompt:")
    for line in gen_wearing.split("\n"):
        print(f"    {line}")
    assert "wearing/putting on" in flash_wearing
    assert "IMPORTANT reference instructions:" in flash_wearing

    # atmosphere 参照付き（画像なし）
    atmosphere_infos = [ReferenceInfo(purpose="atmosphere", text="ダイビング船上の爽やかな雰囲気", has_image=False)]
    flash_atmosphere = build_flash_meta_prompt(
        identity_blocks=["Young adult female, dark brown hair"],
        pose_instruction="船のデッキに立つ",
        num_char_images=1,
        has_env_image=True,
        reference_infos=atmosphere_infos,
    )
    print("\n  [atmosphere 参照・画像なし] Flash meta prompt:")
    for line in flash_atmosphere.split("\n"):
        print(f"    {line}")
    assert "IMPORTANT reference instructions:" in flash_atmosphere
    # 画像なしなので Image 番号はキャラ+環境の2つのみ
    assert "Image 3" not in flash_atmosphere

    # ツーショット + 複数参照
    multi_infos = [
        ReferenceInfo(purpose="wearing", text="ダイビングスーツ", has_image=True),
        ReferenceInfo(purpose="general", text="友人同士の自然な距離感", has_image=False),
    ]
    flash_multi = build_flash_meta_prompt(
        identity_blocks=["Young adult female, dark brown hair", "Young adult female, blonde hair"],
        pose_instruction="向かい合って手を振る",
        num_char_images=2,
        has_env_image=True,
        reference_infos=multi_infos,
    )
    gen_multi = build_generation_prompt(
        flash_prompt="Two young women at ocean...",
        num_char_images=2,
        has_env_image=True,
        reference_infos=multi_infos,
    )
    print("\n  [ツーショット + 複数参照] Flash meta prompt:")
    for line in flash_multi.split("\n"):
        print(f"    {line}")
    print("\n  [ツーショット + 複数参照] Generation prompt:")
    for line in gen_multi.split("\n"):
        print(f"    {line}")
    assert "Single person only, solo" not in gen_multi
    assert "Character 1 is:" in flash_multi
    assert "Character 2 is:" in flash_multi

    print("\n  ✓ purpose 別プロンプト生成が正常")


def verify_component_resolution() -> None:
    """検証4: コンポーネント解決の確認."""
    print("\n" + "=" * 60)
    print("検証4: コンポーネント解決")
    print("=" * 60)

    assets = AssetSet.model_validate_json(ASSET_SET_PATH.read_text())

    # 単独キャラ
    spec_single = SceneKeyframeSpec(
        scene_number=1,
        components=[CharacterComponent(character="Yui", variant_id="casual")],
    )
    resolved_single = GeminiKeyframeEngine._resolve_components(assets, spec_single)
    print(f"\n  [単独] char_images: {len(resolved_single.char_images)}")
    print(f"  [単独] identity_blocks: {len(resolved_single.identity_blocks)}")
    print(f"  [単独] reference_images: {len(resolved_single.reference_images)}")
    assert len(resolved_single.char_images) == 1

    # ツーショット + purpose 付き参照
    spec_multi = SceneKeyframeSpec(
        scene_number=2,
        components=[
            CharacterComponent(character="Yui", variant_id="casual"),
            CharacterComponent(character="Saki", variant_id="casual"),
            ReferenceComponent(text="友人同士の自然な距離感", purpose=ReferencePurpose.ATMOSPHERE),
        ],
    )
    resolved_multi = GeminiKeyframeEngine._resolve_components(assets, spec_multi)
    print(f"\n  [ツーショット] char_images: {len(resolved_multi.char_images)}")
    print(f"  [ツーショット] identity_blocks: {len(resolved_multi.identity_blocks)}")
    print(f"  [ツーショット] reference_infos: {resolved_multi.reference_infos}")
    assert len(resolved_multi.char_images) == 2
    assert len(resolved_multi.identity_blocks) == 2
    assert len(resolved_multi.reference_infos) == 1
    assert resolved_multi.reference_infos[0].purpose == "atmosphere"

    print("\n  ✓ 単独/ツーショットのコンポーネント解決が正常（purpose 伝搬確認済）")


async def verify_generation(dry_run: bool = False) -> None:
    """検証5: 実際のキーフレーム生成（2カットのみ）."""
    print("\n" + "=" * 60)
    print(f"検証5: キーフレーム生成 {'(dry-run)' if dry_run else '(実行)'}")
    print("=" * 60)

    if dry_run:
        print("\n  --dry-run: API コールをスキップします")
        print("  ✓ dry-run 完了")
        return

    api_key = os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI", "")
    if not api_key:
        print("  ✗ DAILY_ROUTINE_API_KEY_GOOGLE_AI が未設定")
        return

    # データ読み込み
    assets = AssetSet.model_validate_json(ASSET_SET_PATH.read_text())
    storyboard_full = Storyboard.model_validate_json(STORYBOARD_PATH.read_text())
    scenario = Scenario.model_validate_json(SCENARIO_PATH.read_text())

    # Storyboard をシーン3-4の各1カットに絞り込み
    trimmed_scenes = []
    for scene in storyboard_full.scenes:
        if scene.scene_number in (3, 4):
            trimmed = scene.model_copy(update={"cuts": [scene.cuts[0]]})
            trimmed_scenes.append(trimmed)
    storyboard = storyboard_full.model_copy(update={"scenes": trimmed_scenes, "total_cuts": len(trimmed_scenes)})
    print(f"\n  Storyboard 絞り込み: {len(trimmed_scenes)} シーン × 各1カット = {len(trimmed_scenes)} カット")

    # 新フォーマットの KeyframeMapping（purpose 付き）
    mapping = KeyframeMapping(
        scenes=[
            SceneKeyframeSpec(
                scene_number=3,
                environment="ダイビング船デッキ",
                pose="フルフェイスマスクを装着している最中のポーズ",
                components=[
                    CharacterComponent(character="Yui", variant_id="drysuit"),
                    ReferenceComponent(
                        image=PROJECT_DIR / "assets" / "items" / "full_face_mask.png",
                        text="フルフェイスマスク",
                        purpose=ReferencePurpose.WEARING,
                    ),
                ],
            ),
            SceneKeyframeSpec(
                scene_number=4,
                environment="水中シーン",
                pose="カメラに向かって手を振る",
                components=[
                    CharacterComponent(character="Yui", variant_id="drysuit"),
                    CharacterComponent(character="Saki", variant_id="drysuit"),
                    ReferenceComponent(
                        text="ダイビング機材を装着した二人が、カメラに向かって自然に手を振る",
                        purpose=ReferencePurpose.ATMOSPHERE,
                    ),
                ],
            ),
        ]
    )

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    client = GeminiKeyframeClient(api_key=api_key)
    engine = GeminiKeyframeEngine.from_components(client=client)

    print("  キーフレーム生成開始...")
    result = await engine.generate_keyframes(
        scenario=scenario,
        storyboard=storyboard,
        assets=assets,
        output_dir=OUTPUT_DIR,
        keyframe_mapping=mapping,
    )

    print(f"\n  生成結果: {len(result.keyframes)} 枚")
    for kf in result.keyframes:
        size = kf.image_path.stat().st_size if kf.image_path.exists() else 0
        print(f"    {kf.cut_id}: {kf.image_path.name} ({size:,} bytes)")
        print(f"      prompt: {kf.prompt[:120]}...")

    print(f"\n  出力先: {OUTPUT_DIR}")
    print("  ✓ キーフレーム生成完了")


def main() -> None:
    parser = argparse.ArgumentParser(description="keyframe_mapping コンポーネント化の検証")
    parser.add_argument("--dry-run", action="store_true", help="API コールをスキップ")
    args = parser.parse_args()

    print("=" * 60)
    print("keyframe_mapping コンポーネント化 検証スクリプト")
    print("=" * 60)

    # オフライン検証
    verify_backward_compat()
    verify_new_format_parse()
    verify_prompt_generation()
    verify_component_resolution()

    # オンライン検証
    asyncio.run(verify_generation(dry_run=args.dry_run))

    print("\n" + "=" * 60)
    print("全検証完了")
    print("=" * 60)


if __name__ == "__main__":
    main()
