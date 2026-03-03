"""schemas/asset.py のテスト."""

from pathlib import Path

from daily_routine.schemas.asset import (
    AssetSet,
    CharacterAsset,
    CharacterReferenceSpec,
    ClothingReferenceSpec,
    EnvironmentAsset,
    EnvironmentSeeds,
    EnvironmentSeedSpec,
    KeyframeAsset,
    ReferenceMapping,
)


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


class TestCharacterAssetVariantId:
    """CharacterAsset.variant_id のテスト."""

    def test_デフォルトdefault(self) -> None:
        char = CharacterAsset(
            character_name="花子",
            front_view=Path("front.png"),
            side_view=Path("side.png"),
            back_view=Path("back.png"),
        )
        assert char.variant_id == "default"

    def test_variant_id設定(self) -> None:
        char = CharacterAsset(
            character_name="花子",
            variant_id="pajama",
            front_view=Path("front.png"),
            side_view=Path("side.png"),
            back_view=Path("back.png"),
        )
        assert char.variant_id == "pajama"

    def test_既存JSONにvariant_idなし_デフォルト補完(self) -> None:
        """既存の asset_set.json（variant_id なし）の後方互換."""
        data = {
            "character_name": "花子",
            "front_view": "front.png",
            "side_view": "side.png",
            "back_view": "back.png",
        }
        char = CharacterAsset.model_validate(data)
        assert char.variant_id == "default"


class TestCharacterAssetIdentityBlock:
    """CharacterAsset.identity_block のテスト."""

    def test_デフォルト空文字(self) -> None:
        char = CharacterAsset(
            character_name="花子",
            front_view=Path("front.png"),
            side_view=Path("side.png"),
            back_view=Path("back.png"),
        )
        assert char.identity_block == ""

    def test_identity_block設定(self) -> None:
        char = CharacterAsset(
            character_name="花子",
            front_view=Path("front.png"),
            side_view=Path("side.png"),
            back_view=Path("back.png"),
            identity_block="Young adult female, dark hair",
        )
        assert char.identity_block == "Young adult female, dark hair"


class TestEnvironmentAsset:
    """EnvironmentAsset のテスト."""

    def test_create(self) -> None:
        env = EnvironmentAsset(
            scene_number=1,
            image_path=Path("assets/env/boat.png"),
        )
        assert env.scene_number == 1
        assert env.source_type == "generated"

    def test_source_type指定(self) -> None:
        env = EnvironmentAsset(
            scene_number=2,
            image_path=Path("assets/env/circuit.png"),
            source_type="reference",
        )
        assert env.source_type == "reference"


class TestAssetSetEnvironments:
    """AssetSet.environments のテスト."""

    def test_デフォルト空リスト(self) -> None:
        asset_set = _make_asset_set()
        assert asset_set.environments == []

    def test_environments付き(self) -> None:
        asset_set = AssetSet(
            characters=[],
            environments=[
                EnvironmentAsset(
                    scene_number=1,
                    image_path=Path("env/sea.png"),
                ),
            ],
        )
        assert len(asset_set.environments) == 1


class TestEnvironmentSeedSpec:
    """EnvironmentSeedSpec のテスト."""

    def test_reference_作成(self) -> None:
        seed = EnvironmentSeedSpec(
            scene_number=1,
            source="reference",
            reference_image="diving_boat.png",
            description="ダイビングボートと海",
        )
        assert seed.source == "reference"
        assert seed.reference_image == "diving_boat.png"
        assert seed.modification == ""

    def test_generate_作成(self) -> None:
        seed = EnvironmentSeedSpec(
            scene_number=2,
            source="generate",
            description="カフェの内装",
        )
        assert seed.source == "generate"
        assert seed.reference_image == ""

    def test_YAML辞書からパース(self) -> None:
        data = {
            "environments": [
                {
                    "scene_number": 1,
                    "source": "reference",
                    "reference_image": "boat.png",
                    "description": "ボート",
                },
                {
                    "scene_number": 2,
                    "source": "generate",
                    "description": "カフェ",
                },
            ]
        }
        seeds = EnvironmentSeeds.model_validate(data)
        assert len(seeds.environments) == 2
        assert seeds.environments[0].source == "reference"
        assert seeds.environments[1].source == "generate"


class TestClothingReferenceSpec:
    """ClothingReferenceSpec のテスト."""

    def test_作成(self) -> None:
        spec = ClothingReferenceSpec(label="pajama", clothing="pajama.png")
        assert spec.label == "pajama"
        assert spec.clothing == "pajama.png"

    def test_clothing_null(self) -> None:
        spec = ClothingReferenceSpec(label="default")
        assert spec.clothing is None


class TestCharacterReferenceSpec:
    """CharacterReferenceSpec のテスト."""

    def test_作成_全指定(self) -> None:
        spec = CharacterReferenceSpec(
            name="Aoi",
            person="model_a.png",
            clothing="casual.png",
        )
        assert spec.name == "Aoi"
        assert spec.person == "model_a.png"
        assert spec.clothing == "casual.png"

    def test_作成_null(self) -> None:
        spec = CharacterReferenceSpec(name="Ren")
        assert spec.person is None
        assert spec.clothing is None

    def test_作成_部分指定(self) -> None:
        spec = CharacterReferenceSpec(name="Yuki", person="model_b.png")
        assert spec.person == "model_b.png"
        assert spec.clothing is None

    def test_clothing_variantsデフォルト空リスト(self) -> None:
        spec = CharacterReferenceSpec(name="Aoi")
        assert spec.clothing_variants == []

    def test_clothing_variants設定(self) -> None:
        spec = CharacterReferenceSpec(
            name="Aoi",
            person="model_a.png",
            clothing_variants=[
                ClothingReferenceSpec(label="pajama", clothing="pajama.png"),
                ClothingReferenceSpec(label="suit", clothing="suit.png"),
            ],
        )
        assert len(spec.clothing_variants) == 2
        assert spec.clothing_variants[0].label == "pajama"
        assert spec.clothing_variants[1].label == "suit"


class TestReferenceMapping:
    """ReferenceMapping のテスト."""

    def test_作成(self) -> None:
        mapping = ReferenceMapping(
            characters=[
                CharacterReferenceSpec(name="Aoi", person="model_a.png", clothing="casual.png"),
                CharacterReferenceSpec(name="Ren"),
            ]
        )
        assert len(mapping.characters) == 2
        assert mapping.characters[0].name == "Aoi"
        assert mapping.characters[1].person is None

    def test_デフォルト空リスト(self) -> None:
        mapping = ReferenceMapping()
        assert mapping.characters == []

    def test_roundtrip_dict(self) -> None:
        mapping = ReferenceMapping(
            characters=[
                CharacterReferenceSpec(name="Aoi", person="model_a.png", clothing="casual.png"),
                CharacterReferenceSpec(name="Ren"),
            ]
        )
        data = mapping.model_dump()
        restored = ReferenceMapping.model_validate(data)
        assert restored.characters[0].person == "model_a.png"
        assert restored.characters[1].person is None

    def test_共有人物画像(self) -> None:
        mapping = ReferenceMapping(
            characters=[
                CharacterReferenceSpec(name="Aoi", person="model_a.png", clothing="casual.png"),
                CharacterReferenceSpec(name="Yuki", person="model_a.png", clothing="formal.png"),
            ]
        )
        assert mapping.characters[0].person == mapping.characters[1].person


class TestKeyframeAssetNewFields:
    """KeyframeAsset の cut_id, generation_method テスト."""

    def test_デフォルト値(self) -> None:
        kf = KeyframeAsset(
            scene_number=1,
            image_path=Path("kf.png"),
            prompt="test",
        )
        assert kf.cut_id == ""
        assert kf.generation_method == "gemini"

    def test_cut_id設定(self) -> None:
        kf = KeyframeAsset(
            scene_number=1,
            image_path=Path("kf.png"),
            prompt="test",
            cut_id="scene_01_cut_01",
            generation_method="gemini",
        )
        assert kf.cut_id == "scene_01_cut_01"
        assert kf.generation_method == "gemini"
