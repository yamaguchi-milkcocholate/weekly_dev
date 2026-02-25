"""RunwayClient のモックテスト."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from daily_routine.utils.uploader import ImageUploader
from daily_routine.visual.clients.base import VideoGenerationRequest
from daily_routine.visual.clients.runway import RunwayClient


@pytest.fixture
def mock_uploader() -> AsyncMock:
    """モックImageUploader."""
    uploader = AsyncMock(spec=ImageUploader)
    uploader.upload.return_value = "https://storage.googleapis.com/bucket/visual/front.png"
    return uploader


@pytest.fixture
def runway_client(mock_uploader: AsyncMock) -> RunwayClient:
    """テスト用RunwayClient."""
    return RunwayClient(api_key="test-api-key", uploader=mock_uploader, model="gen4_turbo")


@pytest.fixture
def sample_request(tmp_path: Path) -> VideoGenerationRequest:
    """テスト用リクエスト."""
    image_path = tmp_path / "front.png"
    image_path.write_bytes(b"fake-png-data")
    return VideoGenerationRequest(
        reference_image_path=image_path,
        prompt="A woman walks out of an apartment",
        duration_sec=10,
        aspect_ratio="9:16",
    )


def _make_mock_response(status_code: int, json_data: dict) -> httpx.Response:
    """モックhttpxレスポンスを作成する."""
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(status_code=status_code, json=json_data, request=request)
    return response


def _make_mock_bytes_response(status_code: int, content: bytes) -> httpx.Response:
    """モックhttpxバイトレスポンスを作成する."""
    request = httpx.Request("GET", "https://example.com")
    response = httpx.Response(status_code=status_code, content=content, request=request)
    return response


class TestRunwayGenerate:
    """RunwayClient.generate のテスト."""

    @pytest.mark.asyncio
    async def test_runway_generate_正常_動画ファイル生成(
        self, runway_client: RunwayClient, sample_request: VideoGenerationRequest, tmp_path: Path
    ) -> None:
        """GCSアップロード → API呼び出し → ポーリング → ダウンロード → 保存の一連フロー."""
        output_path = tmp_path / "clips" / "scene_01.mp4"

        # API応答のモック
        create_response = _make_mock_response(200, {"id": "task-123"})
        poll_response = _make_mock_response(
            200, {"status": "SUCCEEDED", "output": ["https://runway.example.com/video.mp4"]}
        )
        download_response = _make_mock_bytes_response(200, b"fake-video-data")

        mock_client = AsyncMock()
        mock_client.post.return_value = create_response
        mock_client.get.side_effect = [poll_response, download_response]

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("daily_routine.visual.clients.runway.httpx.AsyncClient", return_value=mock_client),
            patch("daily_routine.visual.clients.runway.asyncio.sleep", new_callable=AsyncMock),
        ):
            result = await runway_client.generate(sample_request, output_path)

        assert result.video_path == output_path
        assert result.model_name == "gen4_turbo"
        assert result.cost_usd == 0.5  # $0.05/sec * 10sec
        assert result.generation_time_sec > 0
        assert output_path.exists()
        assert output_path.read_bytes() == b"fake-video-data"

    @pytest.mark.asyncio
    async def test_runway_generate_ポーリングタイムアウト_TimeoutError(
        self, runway_client: RunwayClient, sample_request: VideoGenerationRequest, tmp_path: Path
    ) -> None:
        """5分超過で TimeoutError."""
        output_path = tmp_path / "clips" / "scene_01.mp4"

        create_response = _make_mock_response(200, {"id": "task-timeout"})
        # 常にRUNNINGを返す
        running_response = _make_mock_response(200, {"status": "RUNNING"})

        mock_client = AsyncMock()
        mock_client.post.return_value = create_response
        mock_client.get.return_value = running_response

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("daily_routine.visual.clients.runway.httpx.AsyncClient", return_value=mock_client),
            patch("daily_routine.visual.clients.runway.asyncio.sleep", new_callable=AsyncMock),
            patch("daily_routine.visual.clients.runway._POLL_MAX_ATTEMPTS", 2),
        ):
            with pytest.raises(TimeoutError, match="タイムアウト"):
                await runway_client.generate(sample_request, output_path)

    @pytest.mark.asyncio
    async def test_runway_generate_動画未返却_RuntimeError(
        self, runway_client: RunwayClient, sample_request: VideoGenerationRequest, tmp_path: Path
    ) -> None:
        """API がタスク失敗を返した場合."""
        output_path = tmp_path / "clips" / "scene_01.mp4"

        create_response = _make_mock_response(200, {"id": "task-fail"})
        failed_response = _make_mock_response(200, {"status": "FAILED", "failure": "content_policy"})

        mock_client = AsyncMock()
        mock_client.post.return_value = create_response
        mock_client.get.return_value = failed_response

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("daily_routine.visual.clients.runway.httpx.AsyncClient", return_value=mock_client),
            patch("daily_routine.visual.clients.runway.asyncio.sleep", new_callable=AsyncMock),
        ):
            with pytest.raises(RuntimeError, match="失敗"):
                await runway_client.generate(sample_request, output_path)

    @pytest.mark.asyncio
    async def test_runway_generate_リクエスト構築_URLとプロンプト(
        self,
        runway_client: RunwayClient,
        sample_request: VideoGenerationRequest,
        mock_uploader: AsyncMock,
        tmp_path: Path,
    ) -> None:
        """リクエストペイロードの構造が正しいこと."""
        output_path = tmp_path / "clips" / "scene_01.mp4"

        create_response = _make_mock_response(200, {"id": "task-payload"})
        poll_response = _make_mock_response(
            200, {"status": "SUCCEEDED", "output": ["https://runway.example.com/video.mp4"]}
        )
        download_response = _make_mock_bytes_response(200, b"fake-video-data")

        mock_client = AsyncMock()
        mock_client.post.return_value = create_response
        mock_client.get.side_effect = [poll_response, download_response]

        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=False)

        with (
            patch("daily_routine.visual.clients.runway.httpx.AsyncClient", return_value=mock_client),
            patch("daily_routine.visual.clients.runway.asyncio.sleep", new_callable=AsyncMock),
        ):
            await runway_client.generate(sample_request, output_path)

        # GCSアップロードが呼ばれた
        mock_uploader.upload.assert_awaited_once_with(sample_request.reference_image_path)

        # APIリクエストの構造を検証
        call_args = mock_client.post.call_args
        payload = call_args.kwargs["json"]
        assert payload["model"] == "gen4_turbo"
        assert payload["promptImage"] == "https://storage.googleapis.com/bucket/visual/front.png"
        assert payload["promptText"] == "A woman walks out of an apartment"
        assert payload["ratio"] == "720:1280"  # 9:16 → ピクセル比
        assert payload["duration"] == 10
