"""schemas/keyframe_mapping.py のテスト."""

from pathlib import Path

import pytest
from pydantic import ValidationError

from daily_routine.schemas.keyframe_mapping import (
    CharacterComponent,
    KeyframeMapping,
    ReferenceComponent,
    ReferencePurpose,
    SceneKeyframeSpec,
)


class TestCharacterComponent:
    """CharacterComponent のテスト."""

    def test_create_デフォルト(self) -> None:
        comp = CharacterComponent()
        assert comp.type == "character"
        assert comp.character == ""
        assert comp.variant_id == ""

    def test_create_全フィールド(self) -> None:
        comp = CharacterComponent(character="Yui", variant_id="casual")
        assert comp.type == "character"
        assert comp.character == "Yui"
        assert comp.variant_id == "casual"


class TestReferencePurpose:
    """ReferencePurpose のテスト."""

    def test_全値パース(self) -> None:
        expected = {"wearing", "holding", "atmosphere", "background", "interaction", "general", "subject"}
        actual = {p.value for p in ReferencePurpose}
        assert actual == expected

    def test_文字列からパース(self) -> None:
        assert ReferencePurpose("wearing") == ReferencePurpose.WEARING
        assert ReferencePurpose("general") == ReferencePurpose.GENERAL

    def test_不正値_ValueError(self) -> None:
        with pytest.raises(ValueError):
            ReferencePurpose("invalid_purpose")


class TestReferenceComponent:
    """ReferenceComponent のテスト."""

    def test_create_デフォルト(self) -> None:
        comp = ReferenceComponent()
        assert comp.type == "reference"
        assert comp.image is None
        assert comp.text == ""
        assert comp.purpose == ReferencePurpose.GENERAL

    def test_create_全フィールド(self) -> None:
        comp = ReferenceComponent(image=Path("ref/latte.png"), text="特大のラテカップ", purpose="wearing")
        assert comp.type == "reference"
        assert comp.image == Path("ref/latte.png")
        assert comp.text == "特大のラテカップ"
        assert comp.purpose == ReferencePurpose.WEARING

    def test_purpose未指定_デフォルトgeneral(self) -> None:
        comp = ReferenceComponent(text="何かの参照")
        assert comp.purpose == ReferencePurpose.GENERAL

    def test_purpose不正値_バリデーションエラー(self) -> None:
        with pytest.raises(ValidationError):
            ReferenceComponent(text="test", purpose="invalid_purpose")

    def test_YAML辞書からpurpose付きパース(self) -> None:
        data = {"type": "reference", "text": "フルフェイスマスク", "purpose": "wearing"}
        comp = ReferenceComponent.model_validate(data)
        assert comp.purpose == ReferencePurpose.WEARING


class TestSceneKeyframeSpec:
    """SceneKeyframeSpec のテスト."""

    def test_create_最小(self) -> None:
        spec = SceneKeyframeSpec(scene_number=1)
        assert spec.scene_number == 1
        assert spec.components == []
        assert spec.character == ""
        assert spec.variant_id == ""
        assert spec.environment == ""
        assert spec.pose == ""
        assert spec.reference_image is None
        assert spec.reference_text == ""

    def test_create_新フォーマット_components(self) -> None:
        spec = SceneKeyframeSpec(
            scene_number=1,
            environment="朝のカフェ",
            pose="右手でカップを口元へ",
            components=[
                CharacterComponent(character="Yui", variant_id="casual"),
                CharacterComponent(character="Saki", variant_id="casual"),
                ReferenceComponent(image=Path("reference/latte.png"), text="特大のラテカップ"),
            ],
        )
        assert len(spec.components) == 3
        assert len(spec.character_components) == 2
        assert len(spec.reference_components) == 1
        assert spec.primary_character is not None
        assert spec.primary_character.character == "Yui"

    def test_create_旧フォーマット_後方互換(self) -> None:
        """旧フォーマット（character/variant_id/reference_image/reference_text）が自動変換される."""
        spec = SceneKeyframeSpec(
            scene_number=2,
            character="Aoi",
            variant_id="suit",
            environment="カフェ",
            pose="sitting with coffee",
            reference_image=Path("ref/cafe.png"),
            reference_text="Warm cafe atmosphere",
        )
        assert len(spec.components) == 2
        assert spec.character_components[0].character == "Aoi"
        assert spec.character_components[0].variant_id == "suit"
        assert spec.reference_components[0].image == Path("ref/cafe.png")
        assert spec.reference_components[0].text == "Warm cafe atmosphere"

    def test_旧フォーマット_characterのみ(self) -> None:
        """旧フォーマットで character のみ指定した場合."""
        spec = SceneKeyframeSpec(scene_number=1, character="Aoi")
        assert len(spec.components) == 1
        assert spec.character_components[0].character == "Aoi"

    def test_旧フォーマット_referenceのみ(self) -> None:
        """旧フォーマットで reference_image のみ指定した場合."""
        spec = SceneKeyframeSpec(scene_number=1, reference_image=Path("ref.png"))
        assert len(spec.components) == 1
        assert spec.reference_components[0].image == Path("ref.png")

    def test_components優先_旧フィールド無視(self) -> None:
        """components が指定されている場合、旧フィールドからの自動マイグレーションは行わない."""
        spec = SceneKeyframeSpec(
            scene_number=1,
            character="OldChar",
            components=[CharacterComponent(character="NewChar")],
        )
        assert len(spec.components) == 1
        assert spec.components[0].character == "NewChar"  # type: ignore[union-attr]

    def test_variant_idデフォルト空文字(self) -> None:
        spec = SceneKeyframeSpec(scene_number=1, character="Aoi")
        assert spec.variant_id == ""

    def test_既存YAMLにvariant_idなし_後方互換(self) -> None:
        """既存の keyframe_mapping.yaml（variant_id なし）の後方互換."""
        data = {"scene_number": 1, "character": "Aoi", "environment": "office"}
        spec = SceneKeyframeSpec.model_validate(data)
        assert spec.variant_id == ""
        assert len(spec.components) == 1
        assert spec.character_components[0].character == "Aoi"

    def test_primary_character_空(self) -> None:
        spec = SceneKeyframeSpec(scene_number=1)
        assert spec.primary_character is None

    def test_character_components_空(self) -> None:
        spec = SceneKeyframeSpec(
            scene_number=1,
            components=[ReferenceComponent(text="ambient reference")],
        )
        assert spec.character_components == []
        assert len(spec.reference_components) == 1

    def test_YAML辞書からのパース_新フォーマット(self) -> None:
        """YAML由来の辞書から新フォーマットをパースする."""
        data = {
            "scene_number": 1,
            "environment": "カフェ",
            "components": [
                {"type": "character", "character": "Yui", "variant_id": "casual"},
                {"type": "reference", "image": "ref/latte.png", "text": "ラテ"},
            ],
        }
        spec = SceneKeyframeSpec.model_validate(data)
        assert len(spec.components) == 2
        assert spec.character_components[0].character == "Yui"
        assert spec.reference_components[0].image == Path("ref/latte.png")


class TestKeyframeMapping:
    """KeyframeMapping のテスト."""

    def test_デフォルト空リスト(self) -> None:
        mapping = KeyframeMapping()
        assert mapping.scenes == []

    def test_get_spec_存在するシーン(self) -> None:
        mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(scene_number=1, character="Aoi"),
                SceneKeyframeSpec(scene_number=3, character="Aoi", pose="walking"),
            ]
        )
        spec = mapping.get_spec(3)
        assert spec is not None
        assert spec.pose == "walking"

    def test_get_spec_存在しないシーン(self) -> None:
        mapping = KeyframeMapping(scenes=[SceneKeyframeSpec(scene_number=1)])
        assert mapping.get_spec(99) is None

    def test_roundtrip_json(self) -> None:
        mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(
                    scene_number=1,
                    character="Aoi",
                    reference_image=Path("ref.png"),
                ),
            ]
        )
        data = mapping.model_dump(mode="json")
        restored = KeyframeMapping(**data)
        assert len(restored.scenes) == 1
        assert restored.scenes[0].reference_image == Path("ref.png")
        # 旧フィールドから自動変換されたコンポーネントも保持される
        assert len(restored.scenes[0].components) == 2

    def test_roundtrip_json_新フォーマット(self) -> None:
        mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(
                    scene_number=1,
                    environment="カフェ",
                    components=[
                        CharacterComponent(character="Yui"),
                        ReferenceComponent(image=Path("ref.png")),
                    ],
                ),
            ]
        )
        data = mapping.model_dump(mode="json")
        restored = KeyframeMapping.model_validate(data)
        assert len(restored.scenes[0].components) == 2
        assert restored.scenes[0].character_components[0].character == "Yui"
