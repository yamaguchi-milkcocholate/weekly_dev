"""PromptBuilder のテスト."""

import pytest

from daily_routine.asset.prompt import (
    _C2_TEXT_GENERATION_SUFFIX,
    _C2R2_BASE_PROMPT,
    _MA_ANGLE_INSTRUCTIONS,
    _STYLE_SUFFIX,
    _VIEW_PROMPTS,
    _WHITE_BG,
    FLASH_FUSION_ANALYSIS_PROMPT,
    IDENTITY_BLOCK_EXTRACTION_PROMPT,
    PromptBuilder,
)
from daily_routine.schemas.scenario import CameraWork, CharacterSpec, SceneSpec


@pytest.fixture
def builder():
    return PromptBuilder()


@pytest.fixture
def character():
    return CharacterSpec(
        name="Aoi",
        appearance="25-year-old Japanese woman, shoulder-length black hair",
        outfit="navy blue blazer over white blouse, gray pencil skirt",
        reference_prompt=(
            "A 25-year-old Japanese woman with shoulder-length black hair. "
            "Wearing navy blue blazer over white blouse, gray pencil skirt. "
            "Full body standing pose, front view, plain white background, studio lighting, "
            "semi-realistic style, high quality"
        ),
    )


@pytest.fixture
def scene():
    return SceneSpec(
        scene_number=1,
        duration_sec=3.0,
        situation="朝、主人公が目覚まし時計のアラームで目を覚ます",
        camera_work=CameraWork(type="close-up", description="顔のアップから引いていく"),
        caption_text="朝6時…今日も始まる",
        image_prompt="Modern Japanese apartment bedroom in early morning, soft sunlight, no people, photorealistic",
    )


class TestBuildCharacterPrompt:
    """build_character_prompt のテスト."""

    def test_正面_参照なし_reference_promptを返す(self, builder, character):
        result = builder.build_character_prompt(character, "front", has_reference=False)
        assert result == character.reference_prompt

    def test_正面_参照あり_同一性強調プロンプト(self, builder, character):
        result = builder.build_character_prompt(character, "front", has_reference=True)
        assert "Generate this same character in front view" in result
        assert "Maintain the exact same appearance" in result
        assert character.appearance in result
        assert character.outfit in result
        assert _STYLE_SUFFIX in result
        assert _WHITE_BG in result

    def test_横向き_参照あり_sideビュープロンプト(self, builder, character):
        result = builder.build_character_prompt(character, "side", has_reference=True)
        assert "Generate this same character in side view" in result
        assert _VIEW_PROMPTS["side"] in result

    def test_背面_参照あり_backビュープロンプト(self, builder, character):
        result = builder.build_character_prompt(character, "back", has_reference=True)
        assert "Generate this same character in back view" in result
        assert _VIEW_PROMPTS["back"] in result

    def test_横向き_参照なし_フォールバックプロンプト(self, builder, character):
        result = builder.build_character_prompt(character, "side", has_reference=False)
        assert character.appearance in result
        assert character.outfit in result
        assert _VIEW_PROMPTS["side"] in result

    def test_不明なビュー_ValueError(self, builder, character):
        with pytest.raises(ValueError, match="不明なビュー"):
            builder.build_character_prompt(character, "top", has_reference=False)


class TestBuildMaGenerationPrompt:
    """build_ma_generation_prompt のテスト."""

    def test_front_アングル指示含む(self, builder):
        result = builder.build_ma_generation_prompt("A young woman with dark hair", "front")
        assert "A young woman with dark hair" in result
        assert "facing the camera" in result
        assert "Full body shot from head to feet" in result
        assert "space below the feet" in result
        assert "Single person only" in result

    def test_side_アングル指示含む(self, builder):
        result = builder.build_ma_generation_prompt("A young woman with dark hair", "side")
        assert "side view (profile)" in result

    def test_back_アングル指示含む(self, builder):
        result = builder.build_ma_generation_prompt("A young woman with dark hair", "back")
        assert "back view (seen from behind)" in result

    def test_全アングル_構造一致(self, builder):
        for view in _MA_ANGLE_INSTRUCTIONS:
            result = builder.build_ma_generation_prompt("test description", view)
            assert "Image 1 shows the reference person" in result
            assert "Image 2 shows the outfit" in result
            assert "test description" in result

    def test_不明なビュー_ValueError(self, builder):
        with pytest.raises(ValueError, match="不明なビュー"):
            builder.build_ma_generation_prompt("desc", "top")


class TestBuildAutoPersonPrompt:
    """build_auto_person_prompt のテスト."""

    def test_appearance埋め込み(self, builder):
        result = builder.build_auto_person_prompt("25-year-old Japanese woman, shoulder-length black hair")
        assert "25-year-old Japanese woman, shoulder-length black hair" in result
        assert "Full body shot from head to feet" in result
        assert "plain white background" in result

    def test_構造(self, builder):
        result = builder.build_auto_person_prompt("test appearance")
        assert "A person with the following appearance" in result
        assert "Single person only" in result


class TestBuildAutoClothingPrompt:
    """build_auto_clothing_prompt のテスト."""

    def test_outfit埋め込み(self, builder):
        result = builder.build_auto_clothing_prompt("navy blue blazer over white blouse")
        assert "navy blue blazer over white blouse" in result
        assert "flat lay" in result
        assert "plain white background" in result

    def test_構造(self, builder):
        result = builder.build_auto_clothing_prompt("test outfit")
        assert "no person wearing it" in result


class TestC1F2MAPromptConstants:
    """C1-F2-MA プロンプト定数のテスト."""

    def test_flash_fusion_analysis_prompt_構造(self):
        assert "Image 1 shows a person" in FLASH_FUSION_ANALYSIS_PROMPT
        assert "Image 2 shows an outfit" in FLASH_FUSION_ANALYSIS_PROMPT
        assert "character description" in FLASH_FUSION_ANALYSIS_PROMPT

    def test_identity_block_extraction_prompt_構造(self):
        assert "identity description" in IDENTITY_BLOCK_EXTRACTION_PROMPT
        assert "age, gender, ethnicity" in IDENTITY_BLOCK_EXTRACTION_PROMPT
        assert "reproduce this exact character" in IDENTITY_BLOCK_EXTRACTION_PROMPT


class TestBuildEnvironmentPrompt:
    """build_environment_prompt のテスト."""

    def test_基本_C2R2プロンプト(self, builder):
        result = builder.build_environment_prompt()
        assert result == _C2R2_BASE_PROMPT
        assert "Recreate ONLY the environment" in result
        assert "removing all people completely" in result

    def test_MOD_修正指示が末尾に追加(self, builder):
        mod = "Change the atmosphere to SUNSET. Warm orange and pink sky."
        result = builder.build_environment_prompt(modification=mod)
        assert result.startswith(_C2R2_BASE_PROMPT)
        assert result.endswith(mod)
        assert f"\n{mod}" in result


class TestBuildEnvironmentTextPrompt:
    """build_environment_text_prompt のテスト."""

    def test_image_promptにサフィックス追加(self, builder, scene):
        result = builder.build_environment_text_prompt(scene.image_prompt)
        assert result.startswith(scene.image_prompt)
        assert "NO people" in result
        assert "eye level camera" in result
        assert result.endswith(_C2_TEXT_GENERATION_SUFFIX)
