"""PromptBuilder のテスト."""

import pytest

from daily_routine.asset.prompt import _EXPRESSION_PROMPTS, _STYLE_SUFFIX, _VIEW_PROMPTS, _WHITE_BG, PromptBuilder
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


class TestBuildExpressionPrompt:
    """build_expression_prompt のテスト."""

    def test_smile_参照あり_同一性強調プロンプト(self, builder, character):
        result = builder.build_expression_prompt(character, "smile", has_reference=True)
        assert "Generate this same character" in result
        assert _EXPRESSION_PROMPTS["smile"] in result
        assert "Maintain the exact same appearance" in result
        assert character.appearance in result
        assert character.outfit in result
        assert _STYLE_SUFFIX in result

    def test_serious_参照なし_キャラ情報含むプロンプト(self, builder, character):
        result = builder.build_expression_prompt(character, "serious", has_reference=False)
        assert character.appearance in result
        assert character.outfit in result
        assert _EXPRESSION_PROMPTS["serious"] in result

    def test_未定義表情_そのまま使用(self, builder, character):
        result = builder.build_expression_prompt(character, "laughing loudly", has_reference=True)
        assert "laughing loudly" in result

    def test_全定義済み表情_プロンプト生成可能(self, builder, character):
        for expression in _EXPRESSION_PROMPTS:
            result = builder.build_expression_prompt(character, expression, has_reference=True)
            assert _EXPRESSION_PROMPTS[expression] in result


class TestBuildPropPrompt:
    """build_prop_prompt のテスト."""

    def test_小物プロンプト_スタイル付加(self, builder):
        result = builder.build_prop_prompt("コーヒーカップ", "白い陶器製のコーヒーカップ")
        assert "白い陶器製のコーヒーカップ" in result
        assert "Product photography style" in result
        assert _WHITE_BG in result
        assert _STYLE_SUFFIX in result


class TestBuildBackgroundPrompt:
    """build_background_prompt のテスト."""

    def test_背景プロンプト_image_promptを返す(self, builder, scene):
        result = builder.build_background_prompt(scene)
        assert result == scene.image_prompt
