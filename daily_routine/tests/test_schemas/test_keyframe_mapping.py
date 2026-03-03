"""schemas/keyframe_mapping.py のテスト."""

from pathlib import Path

from daily_routine.schemas.keyframe_mapping import KeyframeMapping, SceneKeyframeSpec


class TestSceneKeyframeSpec:
    """SceneKeyframeSpec のテスト."""

    def test_create_最小(self) -> None:
        spec = SceneKeyframeSpec(scene_number=1)
        assert spec.scene_number == 1
        assert spec.character == ""
        assert spec.variant_id == ""
        assert spec.environment == ""
        assert spec.pose == ""
        assert spec.reference_image is None
        assert spec.reference_text == ""

    def test_create_全フィールド(self) -> None:
        spec = SceneKeyframeSpec(
            scene_number=2,
            character="Aoi",
            variant_id="suit",
            environment="カフェ",
            pose="sitting with coffee",
            reference_image=Path("ref/cafe.png"),
            reference_text="Warm cafe atmosphere",
        )
        assert spec.scene_number == 2
        assert spec.character == "Aoi"
        assert spec.variant_id == "suit"
        assert spec.reference_image == Path("ref/cafe.png")

    def test_variant_idデフォルト空文字(self) -> None:
        spec = SceneKeyframeSpec(scene_number=1, character="Aoi")
        assert spec.variant_id == ""

    def test_既存YAMLにvariant_idなし_後方互換(self) -> None:
        """既存の keyframe_mapping.yaml（variant_id なし）の後方互換."""
        data = {"scene_number": 1, "character": "Aoi", "environment": "office"}
        spec = SceneKeyframeSpec.model_validate(data)
        assert spec.variant_id == ""


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
