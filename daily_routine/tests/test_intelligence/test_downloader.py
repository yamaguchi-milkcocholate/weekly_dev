"""downloader.py のテスト."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from daily_routine.intelligence.downloader import AudioDownloader


class TestAudioDownloader:
    """AudioDownloader のテスト."""

    @pytest.mark.asyncio
    async def test_ダウンロード成功(self, tmp_path: Path) -> None:
        downloader = AudioDownloader(output_dir=tmp_path)
        output_path = tmp_path / "test_vid" / "audio.mp3"

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")

        async def fake_exec(*args, **kwargs):
            # yt-dlp がファイルを作成する動作をシミュレート
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("fake audio")
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec):
            result = await downloader.download("test_vid")

        assert result == output_path
        assert result.exists()

    @pytest.mark.asyncio
    async def test_ダウンロード失敗_RuntimeError(self, tmp_path: Path) -> None:
        downloader = AudioDownloader(output_dir=tmp_path)

        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"yt-dlp error")

        with (
            patch("asyncio.create_subprocess_exec", return_value=mock_process),
            pytest.raises(RuntimeError, match="音声ダウンロード失敗"),
        ):
            await downloader.download("fail_vid")

    @pytest.mark.asyncio
    async def test_既存ファイル_スキップ(self, tmp_path: Path) -> None:
        video_dir = tmp_path / "cached_vid"
        video_dir.mkdir()
        audio_file = video_dir / "audio.mp3"
        audio_file.write_text("existing audio")

        downloader = AudioDownloader(output_dir=tmp_path)
        result = await downloader.download("cached_vid")

        assert result == audio_file

    @pytest.mark.asyncio
    async def test_コマンド引数の検証(self, tmp_path: Path) -> None:
        downloader = AudioDownloader(output_dir=tmp_path)
        output_path = tmp_path / "cmd_test" / "audio.mp3"

        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"", b"")

        async def fake_exec(*args, **kwargs):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_text("fake")
            return mock_process

        with patch("asyncio.create_subprocess_exec", side_effect=fake_exec) as mock_exec:
            await downloader.download("cmd_test")

        # yt-dlp コマンドの検証
        call_args = mock_exec.call_args.args
        assert call_args[0] == "yt-dlp"
        assert "--extract-audio" in call_args
        assert "--audio-format" in call_args
        assert "mp3" in call_args
