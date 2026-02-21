"""schemas/asset.py のテスト."""

from pathlib import Path

from daily_routine.schemas.asset import AssetSet, BackgroundAsset, CharacterAsset, PropAsset


def _make_asset_set() -> AssetSet:
    return AssetSet(
        characters=[
            CharacterAsset(
                character_name="花子",
                front_view=Path("assets/character/hanako_front.png"),
                side_view=Path("assets/character/hanako_side.png"),
                back_view=Path("assets/character/hanako_back.png"),
            ),
        ],
        props=[
            PropAsset(name="スマホ", image_path=Path("assets/props/smartphone.png")),
        ],
        backgrounds=[
            BackgroundAsset(
                scene_number=1,
                description="駅の改札前",
                image_path=Path("assets/backgrounds/station.png"),
            ),
        ],
    )


class TestAssetSet:
    """AssetSet のテスト."""

    def test_create(self) -> None:
        asset_set = _make_asset_set()
        assert len(asset_set.characters) == 1
        assert asset_set.characters[0].character_name == "花子"

    def test_roundtrip_json(self) -> None:
        asset_set = _make_asset_set()
        data = asset_set.model_dump(mode="json")
        restored = AssetSet(**data)
        assert restored.characters[0].front_view == Path("assets/character/hanako_front.png")
        assert restored.props[0].name == "スマホ"
