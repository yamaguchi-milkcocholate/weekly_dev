"""GeminiImageClient のモックテスト."""

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from daily_routine.asset.client import GeminiImageClient, _extract_image


class TestGeminiImageClientInit:
    """初期化テスト."""

    def test_init_空APIキー_ValueError(self):
        with pytest.raises(ValueError, match="API キーが設定されていません"):
            GeminiImageClient(api_key="")

    @patch("daily_routine.asset.client.ChatGoogleGenerativeAI")
    def test_init_正常_インスタンス生成(self, mock_llm_cls):
        client = GeminiImageClient(api_key="test-key")
        assert client.api_key == "test-key"
        assert client.model_name == "gemini-3-pro-image-preview"
        mock_llm_cls.assert_called_once_with(model="gemini-3-pro-image-preview", google_api_key="test-key")

    @patch("daily_routine.asset.client.ChatGoogleGenerativeAI")
    def test_init_カスタムモデル名_反映される(self, mock_llm_cls):
        client = GeminiImageClient(api_key="test-key", model_name="custom-model")
        assert client.model_name == "custom-model"


class TestGeminiImageClientGenerate:
    """generate メソッドのテスト."""

    @patch("daily_routine.asset.client.ChatGoogleGenerativeAI")
    @pytest.mark.asyncio
    async def test_generate_正常レスポンス_画像保存(self, mock_llm_cls, tmp_path):
        # 画像データを base64 エンコード
        fake_image = b"fake-png-data"
        b64_data = base64.b64encode(fake_image).decode("utf-8")

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = SimpleNamespace(
            content=[{"inline_data": {"data": b64_data, "mime_type": "image/png"}}]
        )
        mock_llm_cls.return_value = mock_llm

        client = GeminiImageClient(api_key="test-key")
        output_path = tmp_path / "output" / "test.png"
        result = await client.generate("test prompt", output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.read_bytes() == fake_image
        mock_llm.ainvoke.assert_called_once()

    @patch("daily_routine.asset.client.ChatGoogleGenerativeAI")
    @pytest.mark.asyncio
    async def test_generate_画像なしレスポンス_RuntimeError(self, mock_llm_cls, tmp_path):
        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = SimpleNamespace(content=[{"type": "text", "text": "no image"}])
        mock_llm_cls.return_value = mock_llm

        client = GeminiImageClient(api_key="test-key")
        output_path = tmp_path / "test.png"

        with pytest.raises(RuntimeError, match="画像が生成されませんでした"):
            await client.generate("test prompt", output_path)


class TestGeminiImageClientGenerateWithReference:
    """generate_with_reference メソッドのテスト."""

    @patch("daily_routine.asset.client.ChatGoogleGenerativeAI")
    @pytest.mark.asyncio
    async def test_generate_with_reference_正常_参照画像付き生成(self, mock_llm_cls, tmp_path):
        fake_image = b"fake-generated-image"
        b64_data = base64.b64encode(fake_image).decode("utf-8")

        mock_llm = AsyncMock()
        mock_llm.ainvoke.return_value = SimpleNamespace(
            content=[{"inline_data": {"data": b64_data, "mime_type": "image/png"}}]
        )
        mock_llm_cls.return_value = mock_llm

        # 参照画像を作成
        ref_image = tmp_path / "ref.png"
        ref_image.write_bytes(b"reference-image-data")

        client = GeminiImageClient(api_key="test-key")
        output_path = tmp_path / "output.png"
        result = await client.generate_with_reference("test prompt", [ref_image], output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.read_bytes() == fake_image

        # ainvoke に渡されたメッセージに画像データが含まれていることを検証
        call_args = mock_llm.ainvoke.call_args[0][0]
        message = call_args[0]
        assert len(message.content) == 2  # 参照画像1枚 + テキスト
        assert message.content[0]["type"] == "image_url"
        assert message.content[1]["type"] == "text"

    @patch("daily_routine.asset.client.ChatGoogleGenerativeAI")
    @pytest.mark.asyncio
    async def test_generate_with_reference_存在しない参照画像_FileNotFoundError(self, mock_llm_cls, tmp_path):
        mock_llm_cls.return_value = AsyncMock()
        client = GeminiImageClient(api_key="test-key")

        missing_ref = tmp_path / "nonexistent.png"
        output_path = tmp_path / "output.png"

        with pytest.raises(FileNotFoundError, match="参照画像が見つかりません"):
            await client.generate_with_reference("test", [missing_ref], output_path)


class TestExtractImage:
    """_extract_image ヘルパーのテスト."""

    def test_extract_image_inline_data形式_バイナリ抽出(self):
        fake_data = b"image-bytes"
        b64 = base64.b64encode(fake_data).decode("utf-8")
        response = SimpleNamespace(content=[{"inline_data": {"data": b64, "mime_type": "image/png"}}])
        assert _extract_image(response) == fake_data

    def test_extract_image_image_url形式_バイナリ抽出(self):
        fake_data = b"image-bytes"
        b64 = base64.b64encode(fake_data).decode("utf-8")
        response = SimpleNamespace(
            content=[{"type": "image_url", "image_url": {"url": f"data:image/png;base64,{b64}"}}]
        )
        assert _extract_image(response) == fake_data

    def test_extract_image_画像なし_None(self):
        response = SimpleNamespace(content=[{"type": "text", "text": "hello"}])
        assert _extract_image(response) is None

    def test_extract_image_空リスト_None(self):
        response = SimpleNamespace(content=[])
        assert _extract_image(response) is None

    def test_extract_image_文字列content_None(self):
        response = SimpleNamespace(content="just text")
        assert _extract_image(response) is None
