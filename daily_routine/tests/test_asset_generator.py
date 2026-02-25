"""GeminiAssetGenerator のモックテスト."""

import json
from unittest.mock import AsyncMock

import pytest

from daily_routine.asset.generator import GeminiAssetGenerator, _sanitize_filename
from daily_routine.asset.prompt import PromptBuilder
from daily_routine.schemas.asset import AssetSet
from daily_routine.schemas.scenario import CameraWork, CharacterSpec, PropSpec, SceneSpec


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

    client.generate.side_effect = fake_generate
    client.generate_with_reference.side_effect = fake_generate_with_reference
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
        reference_prompt="A 25-year-old Japanese woman, front view, white background",
    )


@pytest.fixture
def prop():
    return PropSpec(
        name="コーヒーカップ",
        description="白い陶器製のコーヒーカップ",
        image_prompt="A white ceramic coffee cup, product photography style",
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
        assert result.side_view == output_dir / "side.png"
        assert result.back_view == output_dir / "back.png"

        # 正面はプロンプトのみ（generate）、横・背面・表情は参照画像付き（generate_with_reference）
        assert mock_client.generate.call_count == 1
        # side + back + 3 expressions = 5
        assert mock_client.generate_with_reference.call_count == 5

    @pytest.mark.asyncio
    async def test_generate_character_モードA_表情3種生成(self, generator, character, tmp_path):
        output_dir = tmp_path / "character" / "Aoi"
        result = await generator.generate_character(character, output_dir)

        assert "smile" in result.expressions
        assert "serious" in result.expressions
        assert "surprised" in result.expressions
        assert len(result.expressions) == 3

    @pytest.mark.asyncio
    async def test_generate_character_モードA_参照画像は正面のみ(self, generator, mock_client, character, tmp_path):
        output_dir = tmp_path / "character" / "Aoi"
        await generator.generate_character(character, output_dir)

        # generate_with_reference の全呼び出しで、参照画像は正面画像のみ（1枚）
        for call_obj in mock_client.generate_with_reference.call_args_list:
            ref_images = call_obj[0][1]  # positional arg: reference_images
            assert len(ref_images) == 1
            assert ref_images[0] == output_dir / "front.png"


class TestGenerateCharacterModeB:
    """モードB（ユーザー参照画像）のキャラクター生成テスト."""

    @pytest.mark.asyncio
    async def test_generate_character_モードB_全て参照画像付き(self, generator, mock_client, character, tmp_path):
        output_dir = tmp_path / "character" / "Aoi"
        ref_image = tmp_path / "reference" / "aoi.png"
        ref_image.parent.mkdir(parents=True, exist_ok=True)
        ref_image.write_bytes(b"user-reference")

        await generator.generate_character(character, output_dir, reference_image=ref_image)

        # モードB: 全て generate_with_reference を使用
        assert mock_client.generate.call_count == 0
        # front + side + back + 3 expressions = 6
        assert mock_client.generate_with_reference.call_count == 6

    @pytest.mark.asyncio
    async def test_generate_character_モードB_正面はユーザー画像のみ参照(
        self, generator, mock_client, character, tmp_path
    ):
        output_dir = tmp_path / "character" / "Aoi"
        ref_image = tmp_path / "reference" / "aoi.png"
        ref_image.parent.mkdir(parents=True, exist_ok=True)
        ref_image.write_bytes(b"user-reference")

        await generator.generate_character(character, output_dir, reference_image=ref_image)

        # 最初の呼び出し（正面生成）: ユーザー参照画像のみ
        first_call = mock_client.generate_with_reference.call_args_list[0]
        ref_images = first_call[0][1]
        assert len(ref_images) == 1
        assert ref_images[0] == ref_image

    @pytest.mark.asyncio
    async def test_generate_character_モードB_横背面はユーザー画像と正面を参照(
        self, generator, mock_client, character, tmp_path
    ):
        output_dir = tmp_path / "character" / "Aoi"
        ref_image = tmp_path / "reference" / "aoi.png"
        ref_image.parent.mkdir(parents=True, exist_ok=True)
        ref_image.write_bytes(b"user-reference")

        await generator.generate_character(character, output_dir, reference_image=ref_image)

        # 2番目以降の呼び出し（横・背面・表情）: ユーザー画像 + 正面画像の2枚
        for call_obj in mock_client.generate_with_reference.call_args_list[1:]:
            ref_images = call_obj[0][1]
            assert len(ref_images) == 2
            assert ref_images[0] == ref_image
            assert ref_images[1] == output_dir / "front.png"


class TestGenerateProp:
    """小物画像生成のテスト."""

    @pytest.mark.asyncio
    async def test_generate_prop_正常_画像生成とPropAsset返却(self, generator, mock_client, tmp_path):
        result = await generator.generate_prop("コーヒーカップ", "A white coffee cup", tmp_path / "props")

        assert result.name == "コーヒーカップ"
        assert result.image_path.exists()
        mock_client.generate.assert_called_once()


class TestGenerateBackground:
    """背景画像生成のテスト."""

    @pytest.mark.asyncio
    async def test_generate_background_正常_ファイル名にシーン番号(self, generator, mock_client, scene, tmp_path):
        result = await generator.generate_background(scene, tmp_path / "backgrounds")

        assert result.scene_number == 1
        assert result.description == "朝の寝室"
        assert result.image_path.name == "scene_01.png"
        assert result.image_path.exists()


class TestGenerateAssets:
    """generate_assets 統合テスト."""

    @pytest.mark.asyncio
    async def test_generate_assets_モードA_全アセット生成(
        self, generator, mock_client, character, prop, scene, tmp_path
    ):
        output_dir = tmp_path / "assets"
        result = await generator.generate_assets(
            characters=[character],
            props=[prop],
            scenes=[scene],
            output_dir=output_dir,
        )

        assert isinstance(result, AssetSet)
        assert len(result.characters) == 1
        assert len(result.props) == 1
        assert len(result.backgrounds) == 1

        # メタデータが保存されている
        metadata_path = output_dir / "metadata.json"
        assert metadata_path.exists()
        metadata = json.loads(metadata_path.read_text())
        assert metadata["mode"] == "prompt_only"
        assert metadata["model_name"] == "gemini-3-pro-image-preview"

    @pytest.mark.asyncio
    async def test_generate_assets_モードB_user_reference指定(
        self, generator, mock_client, character, prop, scene, tmp_path
    ):
        output_dir = tmp_path / "assets"
        ref_image = tmp_path / "reference" / "aoi.png"
        ref_image.parent.mkdir(parents=True, exist_ok=True)
        ref_image.write_bytes(b"user-ref")

        result = await generator.generate_assets(
            characters=[character],
            props=[prop],
            scenes=[scene],
            output_dir=output_dir,
            user_reference_images={"Aoi": ref_image},
        )

        assert isinstance(result, AssetSet)
        metadata = json.loads((output_dir / "metadata.json").read_text())
        assert metadata["mode"] == "user_reference"

    @pytest.mark.asyncio
    async def test_generate_assets_重複小物_1回だけ生成(self, generator, mock_client, character, scene, tmp_path):
        dup_prop = PropSpec(
            name="スマートフォン",
            description="黒いスマートフォン",
            image_prompt="A black smartphone",
        )
        output_dir = tmp_path / "assets"
        result = await generator.generate_assets(
            characters=[character],
            props=[dup_prop, dup_prop],  # 同じ小物が2回
            scenes=[scene],
            output_dir=output_dir,
        )

        assert len(result.props) == 1

    @pytest.mark.asyncio
    async def test_generate_assets_存在しないユーザー参照画像_FileNotFoundError(
        self, generator, character, prop, scene, tmp_path
    ):
        output_dir = tmp_path / "assets"
        with pytest.raises(FileNotFoundError, match="ユーザー参照画像が見つかりません"):
            await generator.generate_assets(
                characters=[character],
                props=[prop],
                scenes=[scene],
                output_dir=output_dir,
                user_reference_images={"Aoi": tmp_path / "nonexistent.png"},
            )


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
