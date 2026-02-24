"""音声ダウンロード（Whisper フォールバック用）."""

import asyncio
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


class AudioDownloader:
    """YouTube動画の音声をダウンロードする（Whisperフォールバック用）."""

    def __init__(self, output_dir: Path) -> None:
        self._output_dir = output_dir

    async def download(self, video_id: str) -> Path:
        """動画の音声をMP3で取得する.

        yt-dlp をサブプロセスとして呼び出す。
        出力先: {output_dir}/{video_id}/audio.mp3

        Returns:
            ダウンロードした音声ファイルのパス

        Raises:
            RuntimeError: ダウンロード失敗時
        """
        video_dir = self._output_dir / video_id
        video_dir.mkdir(parents=True, exist_ok=True)
        output_path = video_dir / "audio.mp3"

        if output_path.exists():
            logger.info("音声ファイルが既に存在します: %s", output_path)
            return output_path

        url = f"https://www.youtube.com/watch?v={video_id}"
        cmd = [
            "yt-dlp",
            "--extract-audio",
            "--audio-format",
            "mp3",
            "--output",
            str(video_dir / "audio.%(ext)s"),
            "--no-playlist",
            "--quiet",
            url,
        ]

        logger.info("音声ダウンロード開始: %s", video_id)
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await process.communicate()

        if process.returncode != 0:
            error_msg = stderr.decode().strip()
            msg = f"音声ダウンロード失敗: {video_id} ({error_msg})"
            raise RuntimeError(msg)

        if not output_path.exists():
            msg = f"音声ファイルが生成されませんでした: {output_path}"
            raise RuntimeError(msg)

        logger.info("音声ダウンロード完了: %s", output_path)
        return output_path
