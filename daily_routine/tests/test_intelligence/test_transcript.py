"""transcript.py のテスト."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daily_routine.intelligence.transcript import (
    TranscriptFetcher,
    TranscriptResult,
    TranscriptSegment,
)


def _make_mock_transcript(language_code: str = "ja", is_generated: bool = False):
    """youtube-transcript-api のトランスクリプトオブジェクトをモックする."""
    mock = MagicMock()
    mock.language_code = language_code
    mock.is_generated = is_generated

    segment1 = MagicMock()
    segment1.start = 0.0
    segment1.duration = 2.0
    segment1.text = "テスト字幕1"

    segment2 = MagicMock()
    segment2.start = 2.0
    segment2.duration = 3.0
    segment2.text = "テスト字幕2"

    mock.fetch.return_value = [segment1, segment2]
    return mock


def _make_mock_transcript_list(*transcripts):
    """transcript_list のモックを作成（複数回イテレーション対応）."""
    mock_list = MagicMock()
    mock_list.__iter__ = lambda self: iter(transcripts)
    return mock_list


class TestTranscriptFetcher:
    """TranscriptFetcher のテスト."""

    @pytest.mark.asyncio
    async def test_youtube_caption_日本語手動字幕(self) -> None:
        mock_transcript = _make_mock_transcript("ja", is_generated=False)
        mock_list = _make_mock_transcript_list(mock_transcript)

        mock_api = MagicMock()
        mock_api.list.return_value = mock_list

        fetcher = TranscriptFetcher()
        with patch("daily_routine.intelligence.transcript.YouTubeTranscriptApi", return_value=mock_api):
            result = await fetcher.fetch("test_vid")

        assert isinstance(result, TranscriptResult)
        assert result.video_id == "test_vid"
        assert result.source == "youtube_caption"
        assert result.language == "ja"
        assert len(result.segments) == 2
        assert result.segments[0].text == "テスト字幕1"
        assert "テスト字幕1" in result.full_text

    @pytest.mark.asyncio
    async def test_自動生成字幕_フォールバック(self) -> None:
        mock_transcript = _make_mock_transcript("ja", is_generated=True)
        mock_list = _make_mock_transcript_list(mock_transcript)

        mock_api = MagicMock()
        mock_api.list.return_value = mock_list

        fetcher = TranscriptFetcher()
        with patch("daily_routine.intelligence.transcript.YouTubeTranscriptApi", return_value=mock_api):
            result = await fetcher.fetch("test_vid")

        assert result.source == "youtube_caption"
        assert result.language == "ja"

    @pytest.mark.asyncio
    async def test_英語字幕_フォールバック(self) -> None:
        mock_transcript = _make_mock_transcript("en", is_generated=False)
        mock_list = _make_mock_transcript_list(mock_transcript)

        mock_api = MagicMock()
        mock_api.list.return_value = mock_list

        fetcher = TranscriptFetcher()
        with patch("daily_routine.intelligence.transcript.YouTubeTranscriptApi", return_value=mock_api):
            result = await fetcher.fetch("test_vid")

        assert result.source == "youtube_caption"
        assert result.language == "en"

    @pytest.mark.asyncio
    async def test_日本語手動_優先度が高い(self) -> None:
        ja_manual = _make_mock_transcript("ja", is_generated=False)
        en_manual = _make_mock_transcript("en", is_generated=False)
        ja_auto = _make_mock_transcript("ja", is_generated=True)
        mock_list = _make_mock_transcript_list(en_manual, ja_auto, ja_manual)

        mock_api = MagicMock()
        mock_api.list.return_value = mock_list

        fetcher = TranscriptFetcher()
        with patch("daily_routine.intelligence.transcript.YouTubeTranscriptApi", return_value=mock_api):
            result = await fetcher.fetch("test_vid")

        assert result.language == "ja"

    @pytest.mark.asyncio
    async def test_字幕なし_Whisperなし_空結果(self) -> None:
        from youtube_transcript_api._errors import TranscriptsDisabled

        mock_api = MagicMock()
        mock_api.list.side_effect = TranscriptsDisabled("test_vid")

        fetcher = TranscriptFetcher()
        with patch("daily_routine.intelligence.transcript.YouTubeTranscriptApi", return_value=mock_api):
            result = await fetcher.fetch("test_vid")

        assert result.source == "none"
        assert result.segments == []
        assert result.full_text == ""

    @pytest.mark.asyncio
    async def test_字幕なし_Whisper成功(self, tmp_path: Path) -> None:
        from youtube_transcript_api._errors import TranscriptsDisabled

        mock_api = MagicMock()
        mock_api.list.side_effect = TranscriptsDisabled("test_vid")

        whisper_response = MagicMock()
        whisper_response.json.return_value = {
            "text": "Whisperテキスト",
            "language": "ja",
            "segments": [
                {"start": 0.0, "end": 2.0, "text": "Whisperセグメント1"},
                {"start": 2.0, "end": 5.0, "text": "Whisperセグメント2"},
            ],
        }
        whisper_response.raise_for_status.return_value = None

        # 実ファイルを作成
        audio_path = tmp_path / "test_audio.mp3"
        audio_path.write_bytes(b"fake audio data")

        mock_client = AsyncMock()
        mock_client.post.return_value = whisper_response
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        fetcher = TranscriptFetcher(openai_api_key="test-key")
        with (
            patch("daily_routine.intelligence.transcript.YouTubeTranscriptApi", return_value=mock_api),
            patch("daily_routine.intelligence.transcript.httpx.AsyncClient", return_value=mock_client),
        ):
            result = await fetcher.fetch("test_vid", audio_path=audio_path)

        assert result.source == "whisper"
        assert result.full_text == "Whisperテキスト"
        assert len(result.segments) == 2
        assert result.segments[0].text == "Whisperセグメント1"

    @pytest.mark.asyncio
    async def test_字幕なし_音声ファイルなし_空結果(self) -> None:
        from youtube_transcript_api._errors import TranscriptsDisabled

        mock_api = MagicMock()
        mock_api.list.side_effect = TranscriptsDisabled("test_vid")

        fetcher = TranscriptFetcher(openai_api_key="test-key")
        with patch("daily_routine.intelligence.transcript.YouTubeTranscriptApi", return_value=mock_api):
            result = await fetcher.fetch("test_vid", audio_path=Path("/nonexistent/audio.mp3"))

        assert result.source == "none"


class TestTranscriptSegment:
    """TranscriptSegment のテスト."""

    def test_作成(self) -> None:
        seg = TranscriptSegment(start_sec=1.5, duration_sec=2.0, text="テスト")
        assert seg.start_sec == 1.5
        assert seg.duration_sec == 2.0
        assert seg.text == "テスト"
