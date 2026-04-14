"""RunwayImageClient のモックテスト."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from daily_routine.utils.uploader import ImageUploader
from daily_routine.visual.clients.gen4_image import ImageGenerationRequest, RunwayImageClient


@pytest.fixture
def mock_uploader() -> AsyncMock:
    """モックImageUploader."""
    uploader = AsyncMock(spec=ImageUploader)
    uploader.upload.return_value = "https://storage.googleapis.com/bucket/visual/front.png"
    return uploader


@pytest.fixture
def image_client(mock_uploader: AsyncMock) -> RunwayImageClient:
    """テスト用RunwayImageClient."""
    return RunwayImageClient(api_key="test-api-key", uploader=mock_uploader, model="gen4_image_turbo")


@pytest.fixture
def sample_request(tmp_path: Path) -> ImageGenerationRequest:
    """テスト用リクエスト."""
    char_image = tmp_path / "front.png"
    char_image.write_bytes(b"fake-png-data")
    return ImageGenerationRequest(
        prompt="@char sits at a modern office desk, typing on laptop, soft daylight",
        reference_images={"char": char_image},
        aspect_ratio="9:16",
    )


def _make_mock_response(status_code: int, json_data: dict) -> httpx.Response:
    """モックhttpxレスポンスを作成する."""
    request = httpx.Request("GET", "https://example.com")
    return httpx.Response(status_code=status_code, json=json_data, request=request)


def _make_mock_bytes_response(status_code: int, content: bytes) -> httpx.Response:
    """モックhttpxバイトレスポンスを作成する."""
    request = httpx.Request("GET", "https://example.com")
    return httpx.Response(status_code=status_code, content=content, request=request)


class TestRunwayImageGenerate:
    """RunwayImageClient.generate のテスト."""

    @pytest.mark.asyncio
    async def test_generate_正常_画像ファイル生成(
        self, image_client: RunwayImageClient, sample_request: ImageGenerationRequest, tmp_path: Path
    ) -> None:
        """GCSアップロード → API呼び出し → ポーリング → ダウンロード → 保存の一連フロー."""
        output_path = tmp_path / "keyframes" / "scene_01.png"

        create_response = _make_mock_response(200, {"id": "task-img-123"})
        poll_response = _make_mock_response(
            200, {"status": "SUCCEEDED", "output": ["https://runway.example.com/image.png"]}
        )
        download_response = _make_mock_bytes_response(200, b"fake-image-data")

        mock_client = AsyncMock()
        mock_client.post.return_value = create_response
        mock_client.get.side_effect = [poll_response, download_response]

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("daily_routine.visual.clients.gen4_image.httpx.AsyncClient", return_value=mock_client),
            patch("daily_routine.visual.clients.gen4_image.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await image_client.generate(sample_request, output_path)

        assert result.image_path == output_path
        assert result.model_name == "gen4_image_turbo"
        assert result.cost_usd == 0.02
        assert output_path.exists()
        assert output_path.read_bytes() == b"fake-image-data"

    @pytest.mark.asyncio
    async def test_generate_リクエスト構築_referenceImagesとtag(
        self,
        image_client: RunwayImageClient,
        sample_request: ImageGenerationRequest,
        mock_uploader: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """リクエストペイロードにreferenceImagesと@tagが正しく含まれる."""
        output_path = tmp_path / "keyframes" / "scene_01.png"

        create_response = _make_mock_response(200, {"id": "task-payload"})
        poll_response = _make_mock_response(
            200, {"status": "SUCCEEDED", "output": ["https://runway.example.com/image.png"]}
        )
        download_response = _make_mock_bytes_response(200, b"fake-image-data")

        mock_client = AsyncMock()
        mock_client.post.return_value = create_response
        mock_client.get.side_effect = [poll_response, download_response]

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("daily_routine.visual.clients.gen4_image.httpx.AsyncClient", return_value=mock_client),
            patch("daily_routine.visual.clients.gen4_image.asyncio.sleep", new_callable=AsyncMock),
        ):
            await image_client.generate(sample_request, output_path)

        # GCSアップロードが呼ばれた
        mock_uploader.upload.assert_awaited_once()

        # APIリクエストの構造を検証
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["model"] == "gen4_image_turbo"
        assert payload["promptText"] == sample_request.prompt
        assert len(payload["referenceImages"]) == 1
        assert payload["referenceImages"][0]["tag"] == "char"
        assert payload["referenceImages"][0]["uri"] == "https://storage.googleapis.com/bucket/visual/front.png"

    @pytest.mark.asyncio
    async def test_generate_ポーリングタイムアウト_TimeoutError(
        self, image_client: RunwayImageClient, sample_request: ImageGenerationRequest, tmp_path: Path
    ) -> None:
        """ポーリング上限超過で TimeoutError."""
        output_path = tmp_path / "keyframes" / "scene_01.png"

        create_response = _make_mock_response(200, {"id": "task-timeout"})
        running_response = _make_mock_response(200, {"status": "RUNNING"})

        mock_client = AsyncMock()
        mock_client.post.return_value = create_response
        mock_client.get.return_value = running_response

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("daily_routine.visual.clients.gen4_image.httpx.AsyncClient", return_value=mock_client),
            patch("daily_routine.visual.clients.gen4_image.asyncio.sleep", new_callable=AsyncMock),
            patch("daily_routine.visual.clients.gen4_image._POLL_MAX_ATTEMPTS", 2),
        ):
            with pytest.raises(TimeoutError, match="タイムアウト"):
                await image_client.generate(sample_request, output_path)

    @pytest.mark.asyncio
    async def test_generate_タスク失敗_RuntimeError(
        self, image_client: RunwayImageClient, sample_request: ImageGenerationRequest, tmp_path: Path
    ) -> None:
        """API がタスク失敗を返した場合."""
        output_path = tmp_path / "keyframes" / "scene_01.png"

        create_response = _make_mock_response(200, {"id": "task-fail"})
        failed_response = _make_mock_response(200, {"status": "FAILED", "failure": "content_policy"})

        mock_client = AsyncMock()
        mock_client.post.return_value = create_response
        mock_client.get.return_value = failed_response

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("daily_routine.visual.clients.gen4_image.httpx.AsyncClient", return_value=mock_client),
            patch("daily_routine.visual.clients.gen4_image.asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(RuntimeError, match="失敗"):
                await image_client.generate(sample_request, output_path)

    @pytest.mark.asyncio
    async def test_generate_参照画像不在_FileNotFoundError(
        self, image_client: RunwayImageClient, tmp_path: Path
    ) -> None:
        """存在しない参照画像でエラー."""
        request = ImageGenerationRequest(
            prompt="@char in a scene",
            reference_images={"char": tmp_path / "nonexistent.png"},
        )
        output_path = tmp_path / "keyframes" / "scene_01.png"

        with pytest.raises(FileNotFoundError, match="参照画像が存在しません"):
            await image_client.generate(request, output_path)


class TestRunwayImageClientInit:
    """RunwayImageClient 初期化のテスト."""

    def test_APIキー未設定_ValueError(self) -> None:
        """APIキー空文字でエラー."""
        uploader = AsyncMock(spec=ImageUploader)
        with pytest.raises(ValueError, match="APIキー"):
            RunwayImageClient(api_key="", uploader=uploader)
