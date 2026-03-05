"""GeminiAssetGenerator のモックテスト."""

import json
from unittest.mock import AsyncMock

import pytest
import yaml

from daily_routine.asset.generator import GeminiAssetGenerator, _sanitize_filename
from daily_routine.asset.prompt import PromptBuilder
from daily_routine.schemas.asset import AssetSet, EnvironmentSeeds, EnvironmentSeedSpec
from daily_routine.schemas.scenario import CameraWork, CharacterSpec, SceneSpec


@pytest.fixture
def mock_client():
    """GeminiImageClient のモック."""
    client = AsyncMock()
    client.model_name = "gemini-3-pro-image-preview"

    async def fake_generate(prompt, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-image")
        return output_path

    async def fake_generate_with_reference(prompt, reference_images, output_path):
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(b"fake-image")
        return output_path

    async def fake_analyze_with_flash(prompt, images, temperature=0.0):
        return "Young adult East Asian female, dark hair, casual outfit"

    client.generate.side_effect = fake_generate
    client.generate_with_reference.side_effect = fake_generate_with_reference
    client.analyze_with_flash.side_effect = fake_analyze_with_flash
    return client


@pytest.fixture
def prompt_builder():
    return PromptBuilder()


@pytest.fixture
def generator(mock_client, prompt_builder):
    return GeminiAssetGenerator.from_components(client=mock_client, prompt_builder=prompt_builder)


@pytest.fixture
def character():
    return CharacterSpec(
        name="Aoi",
        appearance="25-year-old Japanese woman",
        outfit="navy blue blazer",
        reference_prompt="A 25-year-old Japanese woman, front view, green chroma key background",
    )


@pytest.fixture
def scene():
    return SceneSpec(
        scene_number=1,
        duration_sec=3.0,
        situation="朝の寝室",
        camera_work=CameraWork(type="close-up", description="顔のアップ"),
        caption_text="朝6時",
        image_prompt="Modern bedroom, morning light, no people",
    )


class TestGenerateCharacterModeA:
    """モードA（プロンプトのみ）のキャラクター生成テスト."""

    @pytest.mark.asyncio
    async def test_generate_character_モードA_正面プロンプトのみ生成(self, generator, mock_client, character, tmp_path):
        output_dir = tmp_path / "character" / "Aoi"
        result = await generator.generate_character(character, output_dir)

        assert result.character_name == "Aoi"
        assert result.front_view == output_dir / "front.png"

        # 正面はプロンプトのみ（generate）
        assert mock_client.generate.call_count == 1
        assert mock_client.generate_with_reference.call_count == 0

    @pytest.mark.asyncio
    async def test_generate_character_モードA_generate_with_reference未使用(self, generator, mock_client, character, tmp_path):
        output_dir = tmp_path / "character" / "Aoi"
        await generator.generate_character(character, output_dir)

        # 正面のみ生成のため generate_with_reference は呼ばれない
        assert mock_client.generate_with_reference.call_count == 0


class TestGenerateCharacterModeB:
    """モードB（ユーザー参照画像）のキャラクター生成テスト."""

    @pytest.mark.asyncio
    async def test_generate_character_モードB_全て参照画像付き(self, generator, mock_client, character, tmp_path):
        output_dir = tmp_path / "character" / "Aoi"
        ref_image = tmp_path / "reference" / "aoi.png"
        ref_image.parent.mkdir(parents=True, exist_ok=True)
        ref_image.write_bytes(b"user-reference")

        await generator.generate_character(character, output_dir, reference_image=ref_image)

        # モードB: 正面のみ generate_with_reference を使用
        assert mock_client.generate.call_count == 0
        assert mock_client.generate_with_reference.call_count == 1

    @pytest.mark.asyncio
    async def test_generate_character_モードB_正面はユーザー画像のみ参照(
        self, generator, mock_client, character, tmp_path
    ):
        output_dir = tmp_path / "character" / "Aoi"
        ref_image = tmp_path / "reference" / "aoi.png"
        ref_image.parent.mkdir(parents=True, exist_ok=True)
        ref_image.write_bytes(b"user-reference")

        await generator.generate_character(character, output_dir, reference_image=ref_image)

        # 正面生成のみ: ユーザー参照画像1枚
        assert mock_client.generate_with_reference.call_count == 1
        first_call = mock_client.generate_with_reference.call_args_list[0]
        ref_images = first_call[0][1]
        assert len(ref_images) == 1
        assert ref_images[0] == ref_image


class TestGenerateCharacterC1F2MA:
    """C1-F2-MA 方式のキャラクター生成テスト."""

    @pytest.mark.asyncio
    async def test_C1F2MA_手動配置_Flash分析2回_Pro生成1回(self, generator, mock_client, character, tmp_path):
        """person+clothing 指定 → Flash分析2回 + Pro生成1回."""
        output_dir = tmp_path / "character" / "Aoi"
        person_img = tmp_path / "person" / "Aoi.png"
        clothing_img = tmp_path / "clothing" / "Aoi.png"
        person_img.parent.mkdir(parents=True, exist_ok=True)
        clothing_img.parent.mkdir(parents=True, exist_ok=True)
        person_img.write_bytes(b"person-image")
        clothing_img.write_bytes(b"clothing-image")

        result = await generator.generate_character(
            character,
            output_dir,
            person_image=person_img,
            clothing_image=clothing_img,
        )

        assert result.character_name == "Aoi"
        assert result.front_view == output_dir / "front.png"

        # Flash 分析: 融合分析1回 + Identity Block抽出1回 = 2回
        assert mock_client.analyze_with_flash.call_count == 2
        # Pro 生成: front のみ = 1回
        assert mock_client.generate_with_reference.call_count == 1
        # generate（参照なし）は呼ばれない
        assert mock_client.generate.call_count == 0

    @pytest.mark.asyncio
    async def test_C1F2MA_identity_block抽出(self, generator, mock_client, character, tmp_path):
        """identity_block が空でないこと."""
        output_dir = tmp_path / "character" / "Aoi"
        person_img = tmp_path / "person" / "Aoi.png"
        clothing_img = tmp_path / "clothing" / "Aoi.png"
        person_img.parent.mkdir(parents=True, exist_ok=True)
        clothing_img.parent.mkdir(parents=True, exist_ok=True)
        person_img.write_bytes(b"person-image")
        clothing_img.write_bytes(b"clothing-image")

        result = await generator.generate_character(
            character,
            output_dir,
            person_image=person_img,
            clothing_image=clothing_img,
        )

        assert result.identity_block != ""
        assert "East Asian" in result.identity_block

    @pytest.mark.asyncio
    async def test_C1F2MA_正面生成_person_clothing参照(self, generator, mock_client, character, tmp_path):
        """正面生成で person+clothing が参照画像として渡されること."""
        output_dir = tmp_path / "character" / "Aoi"
        person_img = tmp_path / "person" / "Aoi.png"
        clothing_img = tmp_path / "clothing" / "Aoi.png"
        person_img.parent.mkdir(parents=True, exist_ok=True)
        clothing_img.parent.mkdir(parents=True, exist_ok=True)
        person_img.write_bytes(b"person-image")
        clothing_img.write_bytes(b"clothing-image")

        await generator.generate_character(
            character,
            output_dir,
            person_image=person_img,
            clothing_image=clothing_img,
        )

        # 1回の generate_with_reference は MA 生成（person+clothing）
        assert mock_client.generate_with_reference.call_count == 1
        call_obj = mock_client.generate_with_reference.call_args_list[0]
        ref_images = call_obj[0][1]
        assert len(ref_images) == 2
        assert ref_images[0] == person_img
        assert ref_images[1] == clothing_img


class TestMappingYaml:
    """mapping.yaml の管理テスト."""

    def test_mapping_yaml自動生成_存在しない場合(self, generator, character, tmp_path):
        """存在しない場合に CharacterSpec[] から生成."""
        reference_dir = tmp_path / "reference"
        mapping = generator._load_or_create_mapping([character], reference_dir)

        assert len(mapping.characters) == 1
        assert mapping.characters[0].name == "Aoi"
        assert mapping.characters[0].person is None
        assert mapping.characters[0].clothing is None
        assert len(mapping.characters[0].clothing_variants) == 1
        assert mapping.characters[0].clothing_variants[0].label == "default"

        # ファイルが作成されている
        mapping_path = reference_dir / "mapping.yaml"
        assert mapping_path.exists()

    def test_mapping_yaml読み込み_既存ファイル(self, generator, character, tmp_path):
        """既存ファイルのパスが正しく解決されること."""
        reference_dir = tmp_path / "reference"
        reference_dir.mkdir(parents=True, exist_ok=True)
        mapping_path = reference_dir / "mapping.yaml"
        mapping_path.write_text(
            yaml.dump(
                {
                    "characters": [
                        {"name": "Aoi", "person": "model_a.png", "clothing": "casual.png"},
                    ]
                },
                default_flow_style=False,
            ),
            encoding="utf-8",
        )

        mapping = generator._load_or_create_mapping([character], reference_dir)

        assert len(mapping.characters) == 1
        assert mapping.characters[0].person == "model_a.png"
        assert mapping.characters[0].clothing == "casual.png"

    def test_mapping_yaml自動生成_複数キャラクター(self, generator, tmp_path):
        reference_dir = tmp_path / "reference"
        chars = [
            CharacterSpec(name="Aoi", appearance="a", outfit="o", reference_prompt="r"),
            CharacterSpec(name="Ren", appearance="b", outfit="p", reference_prompt="s"),
        ]
        mapping = generator._load_or_create_mapping(chars, reference_dir)

        assert len(mapping.characters) == 2
        assert mapping.characters[0].name == "Aoi"
        assert mapping.characters[1].name == "Ren"


class TestResolveAndPrepareReferences:
    """_resolve_and_prepare_references のテスト."""

    @pytest.mark.asyncio
    async def test_自動生成_null時にperson_clothing生成(self, generator, mock_client, character, tmp_path):
        """null → 自動生成2回 (person + clothing)."""
        from daily_routine.schemas.asset import CharacterReferenceSpec, ReferenceMapping

        reference_dir = tmp_path / "reference"
        mapping = ReferenceMapping(characters=[CharacterReferenceSpec(name="Aoi", person=None, clothing=None)])

        result = await generator._resolve_and_prepare_references(mapping, [character], reference_dir)

        assert "Aoi" in result
        person_path, clothing_map = result["Aoi"]
        assert person_path == reference_dir / "person" / "Aoi.png"
        assert clothing_map["default"] == reference_dir / "clothing" / "Aoi.png"
        # 自動生成で generate が2回呼ばれる
        assert mock_client.generate.call_count == 2

    @pytest.mark.asyncio
    async def test_手動指定_既存ファイル使用(self, generator, mock_client, character, tmp_path):
        from daily_routine.schemas.asset import CharacterReferenceSpec, ReferenceMapping

        reference_dir = tmp_path / "reference"
        person_dir = reference_dir / "person"
        clothing_dir = reference_dir / "clothing"
        person_dir.mkdir(parents=True, exist_ok=True)
        clothing_dir.mkdir(parents=True, exist_ok=True)
        (person_dir / "model_a.png").write_bytes(b"person")
        (clothing_dir / "casual.png").write_bytes(b"clothing")

        mapping = ReferenceMapping(
            characters=[CharacterReferenceSpec(name="Aoi", person="model_a.png", clothing="casual.png")]
        )

        result = await generator._resolve_and_prepare_references(mapping, [character], reference_dir)

        assert result["Aoi"][0] == person_dir / "model_a.png"
        assert result["Aoi"][1]["default"] == clothing_dir / "casual.png"
        # 自動生成は呼ばれない
        assert mock_client.generate.call_count == 0

    @pytest.mark.asyncio
    async def test_共有人物画像_2キャラクターが同じperson参照(self, generator, mock_client, tmp_path):
        from daily_routine.schemas.asset import CharacterReferenceSpec, ReferenceMapping

        reference_dir = tmp_path / "reference"
        person_dir = reference_dir / "person"
        clothing_dir = reference_dir / "clothing"
        person_dir.mkdir(parents=True, exist_ok=True)
        clothing_dir.mkdir(parents=True, exist_ok=True)
        (person_dir / "model_a.png").write_bytes(b"shared-person")
        (clothing_dir / "casual.png").write_bytes(b"clothing1")
        (clothing_dir / "formal.png").write_bytes(b"clothing2")

        chars = [
            CharacterSpec(name="Aoi", appearance="a", outfit="casual", reference_prompt="r"),
            CharacterSpec(name="Yuki", appearance="b", outfit="formal", reference_prompt="s"),
        ]
        mapping = ReferenceMapping(
            characters=[
                CharacterReferenceSpec(name="Aoi", person="model_a.png", clothing="casual.png"),
                CharacterReferenceSpec(name="Yuki", person="model_a.png", clothing="formal.png"),
            ]
        )

        result = await generator._resolve_and_prepare_references(mapping, chars, reference_dir)

        # 同じ person 画像パスを共有
        assert result["Aoi"][0] == result["Yuki"][0]
        assert result["Aoi"][0] == person_dir / "model_a.png"
        # clothing は異なる
        assert result["Aoi"][1]["default"] != result["Yuki"][1]["default"]

    @pytest.mark.asyncio
    async def test_手動指定_ファイル未存在_FileNotFoundError(self, generator, character, tmp_path):
        from daily_routine.schemas.asset import CharacterReferenceSpec, ReferenceMapping

        reference_dir = tmp_path / "reference"
        mapping = ReferenceMapping(
            characters=[CharacterReferenceSpec(name="Aoi", person="nonexistent.png", clothing=None)]
        )

        with pytest.raises(FileNotFoundError, match="人物参照画像が見つかりません"):
            await generator._resolve_and_prepare_references(mapping, [character], reference_dir)

    @pytest.mark.asyncio
    async def test_clothing_variants_複数衣装解決(self, generator, mock_client, character, tmp_path):
        """clothing_variants 指定時に複数衣装が解決されること."""
        from daily_routine.schemas.asset import (
            CharacterReferenceSpec,
            ClothingReferenceSpec,
            ReferenceMapping,
        )

        reference_dir = tmp_path / "reference"
        clothing_dir = reference_dir / "clothing"
        clothing_dir.mkdir(parents=True, exist_ok=True)
        (clothing_dir / "pajama.png").write_bytes(b"pajama")
        (clothing_dir / "suit.png").write_bytes(b"suit")

        mapping = ReferenceMapping(
            characters=[
                CharacterReferenceSpec(
                    name="Aoi",
                    person=None,
                    clothing_variants=[
                        ClothingReferenceSpec(label="pajama", clothing="pajama.png"),
                        ClothingReferenceSpec(label="suit", clothing="suit.png"),
                    ],
                )
            ]
        )

        result = await generator._resolve_and_prepare_references(mapping, [character], reference_dir)

        person_path, clothing_map = result["Aoi"]
        assert len(clothing_map) == 2
        assert clothing_map["pajama"] == clothing_dir / "pajama.png"
        assert clothing_map["suit"] == clothing_dir / "suit.png"


class TestDetermineMode:
    """_determine_mode のテスト."""

    def test_全null_c1f2ma_auto(self):
        from daily_routine.schemas.asset import CharacterReferenceSpec, ReferenceMapping

        mapping = ReferenceMapping(characters=[CharacterReferenceSpec(name="Aoi", person=None, clothing=None)])
        assert GeminiAssetGenerator._determine_mode(mapping) == "c1f2ma_auto"

    def test_一部指定_c1f2ma_manual(self):
        from daily_routine.schemas.asset import CharacterReferenceSpec, ReferenceMapping

        mapping = ReferenceMapping(characters=[CharacterReferenceSpec(name="Aoi", person="model.png", clothing=None)])
        assert GeminiAssetGenerator._determine_mode(mapping) == "c1f2ma_manual"


class TestGenerateAssets:
    """generate_assets 統合テスト."""

    @pytest.mark.asyncio
    async def test_generate_assets_モードA_全アセット生成(self, generator, mock_client, character, scene, tmp_path):
        output_dir = tmp_path / "assets"
        result = await generator.generate_assets(
            characters=[character],
            scenes=[scene],
            output_dir=output_dir,
        )

        assert isinstance(result, AssetSet)
        assert len(result.characters) == 1

        # メタデータが保存されている
        metadata_path = output_dir / "metadata.json"
        assert metadata_path.exists()
        metadata = json.loads(metadata_path.read_text())
        assert metadata["mode"] == "prompt_only"
        assert metadata["model_name"] == "gemini-3-pro-image-preview"

    @pytest.mark.asyncio
    async def test_generate_assets_モードB_user_reference指定(self, generator, mock_client, character, scene, tmp_path):
        output_dir = tmp_path / "assets"
        ref_image = tmp_path / "reference" / "aoi.png"
        ref_image.parent.mkdir(parents=True, exist_ok=True)
        ref_image.write_bytes(b"user-ref")

        result = await generator.generate_assets(
            characters=[character],
            scenes=[scene],
            output_dir=output_dir,
            user_reference_images={"Aoi": ref_image},
        )

        assert isinstance(result, AssetSet)
        metadata = json.loads((output_dir / "metadata.json").read_text())
        assert metadata["mode"] == "user_reference"

    @pytest.mark.asyncio
    async def test_generate_assets_C1F2MA_person_clothing指定(self, generator, mock_client, character, scene, tmp_path):
        output_dir = tmp_path / "assets"
        person_img = tmp_path / "person" / "Aoi.png"
        clothing_img = tmp_path / "clothing" / "Aoi.png"
        person_img.parent.mkdir(parents=True, exist_ok=True)
        clothing_img.parent.mkdir(parents=True, exist_ok=True)
        person_img.write_bytes(b"person")
        clothing_img.write_bytes(b"clothing")

        result = await generator.generate_assets(
            characters=[character],
            scenes=[scene],
            output_dir=output_dir,
            person_images={"Aoi": person_img},
            clothing_images={"Aoi": clothing_img},
        )

        assert isinstance(result, AssetSet)
        assert len(result.characters) == 1
        metadata = json.loads((output_dir / "metadata.json").read_text())
        assert metadata["mode"] == "c1f2ma_manual"

    @pytest.mark.asyncio
    async def test_generate_assets_存在しないユーザー参照画像_FileNotFoundError(
        self, generator, character, scene, tmp_path
    ):
        output_dir = tmp_path / "assets"
        with pytest.raises(FileNotFoundError, match="ユーザー参照画像が見つかりません"):
            await generator.generate_assets(
                characters=[character],
                scenes=[scene],
                output_dir=output_dir,
                user_reference_images={"Aoi": tmp_path / "nonexistent.png"},
            )


class TestGenerateCharacterVariantId:
    """generate_character の variant_id テスト."""

    @pytest.mark.asyncio
    async def test_C1F2MA_variant_idが設定される(self, generator, mock_client, character, tmp_path):
        """variant_id が CharacterAsset に反映されること."""
        output_dir = tmp_path / "character" / "Aoi" / "pajama"
        person_img = tmp_path / "person" / "Aoi.png"
        clothing_img = tmp_path / "clothing" / "pajama.png"
        person_img.parent.mkdir(parents=True, exist_ok=True)
        clothing_img.parent.mkdir(parents=True, exist_ok=True)
        person_img.write_bytes(b"person-image")
        clothing_img.write_bytes(b"clothing-image")

        result = await generator.generate_character(
            character,
            output_dir,
            person_image=person_img,
            clothing_image=clothing_img,
            variant_id="pajama",
        )

        assert result.variant_id == "pajama"
        assert result.character_name == "Aoi"

    @pytest.mark.asyncio
    async def test_legacy_variant_idデフォルト(self, generator, mock_client, character, tmp_path):
        """legacy フローでデフォルト variant_id が設定されること."""
        output_dir = tmp_path / "character" / "Aoi"
        result = await generator.generate_character(character, output_dir)
        assert result.variant_id == "default"


class TestGenerateEnvironmentReference:
    """環境生成（source=reference）のテスト."""

    @pytest.mark.asyncio
    async def test_generate_assets_環境reference_EnvironmentAsset生成(
        self, generator, mock_client, character, scene, tmp_path
    ):
        output_dir = tmp_path / "assets"
        env_ref_dir = tmp_path / "env_ref"
        env_ref_dir.mkdir()
        (env_ref_dir / "boat.png").write_bytes(b"fake-ref")

        env_seeds = EnvironmentSeeds(
            environments=[
                EnvironmentSeedSpec(
                    scene_number=1,
                    source="reference",
                    reference_image="boat.png",
                    description="ダイビングボートと海",
                ),
            ]
        )

        result = await generator.generate_assets(
            characters=[character],
            scenes=[scene],
            output_dir=output_dir,
            env_seeds=env_seeds,
            env_reference_dir=env_ref_dir,
        )

        assert len(result.environments) == 1
        env = result.environments[0]
        assert env.scene_number == 1
        assert env.source_type == "reference"
        assert env.description == "ダイビングボートと海"
        assert env.image_path.name == "scene_01.png"
        # generate_with_reference が呼ばれている（キャラ分 + 環境1回）
        assert mock_client.generate_with_reference.call_count > 0

    @pytest.mark.asyncio
    async def test_generate_assets_環境MOD付き_修正プロンプト使用(
        self, generator, mock_client, character, scene, tmp_path
    ):
        output_dir = tmp_path / "assets"
        env_ref_dir = tmp_path / "env_ref"
        env_ref_dir.mkdir()
        (env_ref_dir / "boat.png").write_bytes(b"fake-ref")

        env_seeds = EnvironmentSeeds(
            environments=[
                EnvironmentSeedSpec(
                    scene_number=1,
                    source="reference",
                    reference_image="boat.png",
                    modification="Change the atmosphere to SUNSET.",
                ),
            ]
        )

        result = await generator.generate_assets(
            characters=[character],
            scenes=[scene],
            output_dir=output_dir,
            env_seeds=env_seeds,
            env_reference_dir=env_ref_dir,
        )

        assert len(result.environments) == 1
        assert result.environments[0].source_type == "reference"

        # 環境生成の generate_with_reference 呼び出しのプロンプトを確認
        # 最後の呼び出しが環境生成
        last_call = mock_client.generate_with_reference.call_args_list[-1]
        prompt = last_call[0][0]
        assert "SUNSET" in prompt

    @pytest.mark.asyncio
    async def test_generate_assets_参照画像未存在_FileNotFoundError(self, generator, character, scene, tmp_path):
        output_dir = tmp_path / "assets"
        env_ref_dir = tmp_path / "env_ref"
        env_ref_dir.mkdir()
        # boat.png を配置しない

        env_seeds = EnvironmentSeeds(
            environments=[
                EnvironmentSeedSpec(
                    scene_number=1,
                    source="reference",
                    reference_image="boat.png",
                ),
            ]
        )

        with pytest.raises(FileNotFoundError, match="環境参照画像が見つかりません"):
            await generator.generate_assets(
                characters=[character],
                scenes=[scene],
                output_dir=output_dir,
                env_seeds=env_seeds,
                env_reference_dir=env_ref_dir,
            )


class TestGenerateEnvironmentGenerate:
    """環境生成（source=generate）のテスト."""

    @pytest.mark.asyncio
    async def test_generate_assets_環境generate_SceneSpecのimage_prompt使用(
        self, generator, mock_client, character, scene, tmp_path
    ):
        output_dir = tmp_path / "assets"

        env_seeds = EnvironmentSeeds(
            environments=[
                EnvironmentSeedSpec(
                    scene_number=1,
                    source="generate",
                    description="朝の寝室",
                ),
            ]
        )

        result = await generator.generate_assets(
            characters=[character],
            scenes=[scene],
            output_dir=output_dir,
            env_seeds=env_seeds,
        )

        assert len(result.environments) == 1
        env = result.environments[0]
        assert env.scene_number == 1
        assert env.source_type == "generated"
        assert env.description == "朝の寝室"

        # generate（テキストベース）が呼ばれている
        # キャラ正面1回 + 環境1回 = 2回
        assert mock_client.generate.call_count == 2


class TestLoadEnvironmentSeeds:
    """_load_environment_seeds のテスト."""

    def test_YAML読み込み(self, generator, tmp_path):
        seeds_path = tmp_path / "environment_seeds.yaml"
        seeds_path.write_text(
            "environments:\n"
            "  - scene_number: 1\n"
            "    source: reference\n"
            "    reference_image: boat.png\n"
            "    description: ボート\n"
            "  - scene_number: 2\n"
            "    source: generate\n"
            "    description: カフェ\n",
            encoding="utf-8",
        )
        seeds = generator._load_environment_seeds(seeds_path)
        assert len(seeds.environments) == 2
        assert seeds.environments[0].source == "reference"
        assert seeds.environments[1].source == "generate"

    def test_YAML未存在_FileNotFoundError(self, generator, tmp_path):
        seeds_path = tmp_path / "nonexistent.yaml"
        with pytest.raises(FileNotFoundError, match="環境シードファイルが見つかりません"):
            generator._load_environment_seeds(seeds_path)


class TestItemSupport:
    """アイテム単位実行のテスト."""

    def test_supports_items_True(self, generator) -> None:
        assert generator.supports_items is True

    def test_list_items_キャラクターと環境(self, generator, character, tmp_path) -> None:
        """list_items がキャラクターと環境のアイテムIDを返すこと."""
        from daily_routine.schemas.scenario import CameraWork, Scenario, SceneSpec

        project_dir = tmp_path / "project"
        reference_dir = project_dir / "assets" / "reference"
        reference_dir.mkdir(parents=True, exist_ok=True)

        # environment_seeds.yaml を作成
        seeds_path = reference_dir / "environment_seeds.yaml"
        seeds_path.write_text(
            "environments:\n"
            "  - scene_number: 1\n"
            "    source: generate\n"
            "    description: 朝の寝室\n"
            "  - scene_number: 2\n"
            "    source: generate\n"
            "    description: カフェ\n",
            encoding="utf-8",
        )

        scenario = Scenario(
            title="テスト",
            total_duration_sec=6.0,
            characters=[character],
            scenes=[
                SceneSpec(
                    scene_number=1,
                    duration_sec=3.0,
                    situation="部屋",
                    camera_work=CameraWork(type="wide", description="ワイド"),
                    caption_text="テスト",
                    image_prompt="room",
                ),
                SceneSpec(
                    scene_number=2,
                    duration_sec=3.0,
                    situation="カフェ",
                    camera_work=CameraWork(type="wide", description="ワイド"),
                    caption_text="テスト",
                    image_prompt="cafe",
                ),
            ],
            bgm_direction="テスト",
        )

        items = generator.list_items(scenario, project_dir)

        # mapping.yaml が自動生成され、デフォルト衣装のキャラクターアイテム + 環境アイテム
        assert "char_Aoi_default" in items
        assert "env_1" in items
        assert "env_2" in items

    @pytest.mark.asyncio
    async def test_execute_item_キャラクター生成(self, generator, mock_client, character, tmp_path) -> None:
        """execute_item でキャラクターが AssetSet に追記されること."""
        from daily_routine.schemas.scenario import CameraWork, Scenario, SceneSpec

        project_dir = tmp_path / "project"
        reference_dir = project_dir / "assets" / "reference"
        reference_dir.mkdir(parents=True, exist_ok=True)

        scenario = Scenario(
            title="テスト",
            total_duration_sec=3.0,
            characters=[character],
            scenes=[
                SceneSpec(
                    scene_number=1,
                    duration_sec=3.0,
                    situation="部屋",
                    camera_work=CameraWork(type="wide", description="ワイド"),
                    caption_text="テスト",
                    image_prompt="room",
                ),
            ],
            bgm_direction="テスト",
        )

        await generator.execute_item("char_Aoi_default", scenario, project_dir)

        asset_set = generator.load_output(project_dir)
        assert len(asset_set.characters) == 1
        assert asset_set.characters[0].character_name == "Aoi"

    @pytest.mark.asyncio
    async def test_execute_item_環境生成(self, generator, mock_client, character, tmp_path) -> None:
        """execute_item で環境が AssetSet に追記されること."""
        from daily_routine.schemas.scenario import CameraWork, Scenario, SceneSpec

        project_dir = tmp_path / "project"
        reference_dir = project_dir / "assets" / "reference"
        reference_dir.mkdir(parents=True, exist_ok=True)

        seeds_path = reference_dir / "environment_seeds.yaml"
        seeds_path.write_text(
            "environments:\n"
            "  - scene_number: 1\n"
            "    source: generate\n"
            "    description: 朝の寝室\n",
            encoding="utf-8",
        )

        scenario = Scenario(
            title="テスト",
            total_duration_sec=3.0,
            characters=[character],
            scenes=[
                SceneSpec(
                    scene_number=1,
                    duration_sec=3.0,
                    situation="部屋",
                    camera_work=CameraWork(type="wide", description="ワイド"),
                    caption_text="テスト",
                    image_prompt="room",
                ),
            ],
            bgm_direction="テスト",
        )

        await generator.execute_item("env_1", scenario, project_dir)

        asset_set = generator.load_output(project_dir)
        assert len(asset_set.environments) == 1
        assert asset_set.environments[0].scene_number == 1


class TestSanitizeFilename:
    """_sanitize_filename のテスト."""

    def test_日本語名_サニタイズ(self):
        result = _sanitize_filename("ラテアート付きコーヒーカップ")
        assert "/" not in result
        assert "\\" not in result
        assert len(result) > 0

    def test_英数字名_そのまま(self):
        assert _sanitize_filename("smartphone") == "smartphone"

    def test_スペース含む名前_アンダースコアに置換(self):
        assert _sanitize_filename("coffee cup") == "coffee_cup"

    def test_空文字列_unnamed(self):
        assert _sanitize_filename("") == "unnamed"
