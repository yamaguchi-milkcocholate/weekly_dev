"""schemas/style_mapping.py のテスト."""

from pathlib import Path

from daily_routine.schemas.style_mapping import SceneStyleReference, StyleMapping


class TestSceneStyleReference:
    """SceneStyleReference のテスト."""

    def test_create(self) -> None:
        ref = SceneStyleReference(scene_number=1, reference=Path("seeds/captures/abc/7.png"))
        assert ref.scene_number == 1
        assert ref.reference == Path("seeds/captures/abc/7.png")


class TestStyleMapping:
    """StyleMapping のテスト."""

    def test_空マッピング(self) -> None:
        mapping = StyleMapping()
        assert mapping.mappings == []

    def test_get_reference_存在するシーン(self) -> None:
        mapping = StyleMapping(
            mappings=[
                SceneStyleReference(scene_number=1, reference=Path("seeds/captures/abc/7.png")),
                SceneStyleReference(scene_number=3, reference=Path("assets/reference/cafe.png")),
            ]
        )
        assert mapping.get_reference(1) == Path("seeds/captures/abc/7.png")
        assert mapping.get_reference(3) == Path("assets/reference/cafe.png")

    def test_get_reference_存在しないシーン_None(self) -> None:
        mapping = StyleMapping(
            mappings=[
                SceneStyleReference(scene_number=1, reference=Path("seeds/captures/abc/7.png")),
            ]
        )
        assert mapping.get_reference(2) is None

    def test_get_reference_空マッピング_None(self) -> None:
        mapping = StyleMapping()
        assert mapping.get_reference(1) is None

    def test_model_validate_from_dict(self) -> None:
        data = {
            "mappings": [
                {"scene_number": 1, "reference": "seeds/captures/abc/7.png"},
                {"scene_number": 5, "reference": "assets/reference/cafe.png"},
            ]
        }
        mapping = StyleMapping.model_validate(data)
        assert len(mapping.mappings) == 2
        assert mapping.get_reference(1) == Path("seeds/captures/abc/7.png")
        assert mapping.get_reference(5) == Path("assets/reference/cafe.png")
