"""suno.py のユニットテスト."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest

from daily_routine.audio.suno import SunoClient, SunoGenerationError, SunoTimeoutError, SunoTrack


def _make_generate_response(task_id: str = "task-001") -> dict:
    """生成リクエストのモックレスポンス."""
    return {
        "code": 200,
        "message": "success",
        "data": {"taskId": task_id},
    }


def _make_status_response_complete() -> dict:
    """生成完了のモックレスポンス."""
    return {
        "code": 200,
        "data": {
            "response": {
                "sunoData": [
                    {
                        "id": "track-001",
                        "title": "Lo-Fi Morning",
                        "audioUrl": "https://cdn.suno.ai/track-001.mp3",
                        "duration": 62.0,
                        "tags": "lo-fi, chill",
                        "status": "complete",
                    },
                    {
                        "id": "track-002",
                        "title": "Chill Vibes",
                        "audioUrl": "https://cdn.suno.ai/track-002.mp3",
                        "duration": 58.0,
                        "tags": "chill hop, relaxing",
                        "status": "complete",
                    },
                ]
            }
        },
    }


def _make_status_response_generating() -> dict:
    """生成中のモックレスポンス."""
    return {
        "code": 200,
        "data": {
            "response": {
                "sunoData": [
                    {
                        "id": "track-001",
                        "title": "",
                        "audioUrl": "",
                        "duration": 0,
                        "tags": "",
                        "status": "queued",
                    },
                ]
            }
        },
    }


def _make_status_response_error() -> dict:
    """生成エラーのモックレスポンス."""
    return {
        "code": 200,
        "data": {
            "response": {
                "sunoData": [
                    {
                        "id": "track-001",
                        "title": "",
                        "audioUrl": "",
                        "duration": 0,
                        "tags": "",
                        "status": "error",
                    },
                ]
            }
        },
    }


class TestSunoClientGenerate:
    """generate のテスト."""

    @pytest.mark.asyncio
    async def test_generate_正常_2曲返却(self) -> None:
        client = SunoClient(api_key="test-key")

        # generate リクエスト用モック
        mock_gen_response = MagicMock(spec=httpx.Response)
        mock_gen_response.json.return_value = _make_generate_response()
        mock_gen_response.raise_for_status = MagicMock()

        # ステータスポーリング用モック
        mock_status_response = MagicMock(spec=httpx.Response)
        mock_status_response.json.return_value = _make_status_response_complete()
        mock_status_response.raise_for_status = MagicMock()

        with patch("daily_routine.audio.suno.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_gen_response)
            mock_http.get = AsyncMock(return_value=mock_status_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            tracks = await client.generate("lo-fi chill hop, 110-130 BPM")

        assert len(tracks) == 2
        assert isinstance(tracks[0], SunoTrack)
        assert tracks[0].track_id == "track-001"
        assert tracks[0].status == "complete"
        assert tracks[0].duration_sec == 62.0
        assert "lo-fi" in tracks[0].tags

    @pytest.mark.asyncio
    async def test_generate_APIエラー_例外(self) -> None:
        client = SunoClient(api_key="test-key")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = {"code": 401, "message": "Unauthorized"}
        mock_response.raise_for_status = MagicMock()

        with patch("daily_routine.audio.suno.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.post = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            with pytest.raises(SunoGenerationError, match="Unauthorized"):
                await client.generate("test prompt")


class TestSunoClientWaitForCompletion:
    """wait_for_completion のテスト."""

    @pytest.mark.asyncio
    async def test_wait_ポーリング後完了(self) -> None:
        client = SunoClient(api_key="test-key")

        # 1回目は生成中、2回目は完了
        responses = [
            _make_status_response_generating(),
            _make_status_response_complete(),
        ]
        call_count = 0

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.raise_for_status = MagicMock()

        def json_side_effect():
            nonlocal call_count
            result = responses[min(call_count, len(responses) - 1)]
            call_count += 1
            return result

        mock_response.json = json_side_effect

        with (
            patch("daily_routine.audio.suno.httpx.AsyncClient") as mock_cls,
            patch("daily_routine.audio.suno.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            tracks = await client.wait_for_completion(["task-001"], poll_interval_sec=1)

        assert len(tracks) == 2
        assert all(t.status == "complete" for t in tracks)

    @pytest.mark.asyncio
    async def test_wait_タイムアウト_例外(self) -> None:
        client = SunoClient(api_key="test-key")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = _make_status_response_generating()
        mock_response.raise_for_status = MagicMock()

        with (
            patch("daily_routine.audio.suno.httpx.AsyncClient") as mock_cls,
            patch("daily_routine.audio.suno.asyncio.sleep", new_callable=AsyncMock),
        ):
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            with pytest.raises(SunoTimeoutError, match="タイムアウト"):
                await client.wait_for_completion(
                    ["task-001"],
                    timeout_sec=5,
                    poll_interval_sec=2,
                )

    @pytest.mark.asyncio
    async def test_wait_生成エラー_例外(self) -> None:
        client = SunoClient(api_key="test-key")

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.json.return_value = _make_status_response_error()
        mock_response.raise_for_status = MagicMock()

        with patch("daily_routine.audio.suno.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            with pytest.raises(SunoGenerationError, match="生成エラー"):
                await client.wait_for_completion(["task-001"])


class TestSunoClientDownload:
    """download のテスト."""

    @pytest.mark.asyncio
    async def test_download_正常_ファイル保存(self, tmp_path: Path) -> None:
        client = SunoClient(api_key="test-key")
        output_path = tmp_path / "bgm" / "suno_001.mp3"
        audio_content = b"\xff\xfb\x90\x00" * 100

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.content = audio_content
        mock_response.raise_for_status = MagicMock()

        with patch("daily_routine.audio.suno.httpx.AsyncClient") as mock_cls:
            mock_http = AsyncMock()
            mock_http.get = AsyncMock(return_value=mock_response)
            mock_http.__aenter__ = AsyncMock(return_value=mock_http)
            mock_http.__aexit__ = AsyncMock(return_value=None)
            mock_cls.return_value = mock_http

            result = await client.download("https://cdn.suno.ai/track.mp3", output_path)

        assert result == output_path
        assert output_path.exists()
        assert output_path.read_bytes() == audio_content
