"""字幕取得（youtube-transcript-api + Whisper フォールバック）."""

import logging
from pathlib import Path

import httpx
from pydantic import BaseModel, Field
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api._errors import TranscriptsDisabled

logger = logging.getLogger(__name__)


class TranscriptSegment(BaseModel):
    """字幕のセグメント."""

    start_sec: float = Field(description="開始時刻（秒）")
    duration_sec: float = Field(description="継続時間（秒）")
    text: str = Field(description="テキスト")


class TranscriptResult(BaseModel):
    """字幕取得結果."""

    video_id: str
    source: str = Field(description="取得元: 'youtube_caption' | 'whisper' | 'none'")
    language: str = Field(default="")
    segments: list[TranscriptSegment] = Field(default_factory=list)
    full_text: str = Field(default="", description="全文テキスト")


class TranscriptFetcher:
    """字幕取得（youtube-transcript-api + Whisper フォールバック）."""

    def __init__(self, openai_api_key: str | None = None) -> None:
        """初期化.

        Args:
            openai_api_key: Whisper API用キー（フォールバック用、省略時はフォールバック無効）
        """
        self._openai_api_key = openai_api_key

    async def fetch(self, video_id: str, audio_path: Path | None = None) -> TranscriptResult:
        """動画の字幕を取得する.

        1. youtube-transcript-api で字幕を試行（日本語 → 英語 → 自動生成の優先順）
        2. 字幕が存在しない場合、audio_path が指定されていれば Whisper API でフォールバック
        3. どちらも失敗した場合は空の TranscriptResult を返す

        Args:
            video_id: YouTube動画ID
            audio_path: 音声ファイルパス（Whisperフォールバック用、省略可）

        Returns:
            字幕結果
        """
        # 1. youtube-transcript-api で試行
        result = self._fetch_youtube_transcript(video_id)
        if result is not None:
            return result

        # 2. Whisper フォールバック
        if audio_path is not None and self._openai_api_key:
            result = await self._fetch_whisper(video_id, audio_path)
            if result is not None:
                return result

        # 3. 空結果
        logger.warning("字幕取得失敗（空結果を返します）: %s", video_id)
        return TranscriptResult(video_id=video_id, source="none")

    def _fetch_youtube_transcript(self, video_id: str) -> TranscriptResult | None:
        """youtube-transcript-api で字幕を取得する."""
        try:
            ytt_api = YouTubeTranscriptApi()
            transcript_list = ytt_api.list(video_id)
        except TranscriptsDisabled:
            logger.info("字幕が無効化されています: %s", video_id)
            return None
        except Exception:
            logger.warning("youtube-transcript-api でエラー: %s", video_id, exc_info=True)
            return None

        # 優先順位: 日本語手動 → 英語手動 → 日本語自動生成 → 英語自動生成 → 最初の字幕
        preferred_langs = ["ja", "en"]
        transcript = None

        # 手動字幕を優先
        for lang in preferred_langs:
            for t in transcript_list:
                if t.language_code == lang and not t.is_generated:
                    transcript = t
                    break
            if transcript:
                break

        # 自動生成字幕にフォールバック
        if transcript is None:
            for lang in preferred_langs:
                for t in transcript_list:
                    if t.language_code == lang and t.is_generated:
                        transcript = t
                        break
                if transcript:
                    break

        # どの言語でも最初の字幕
        if transcript is None:
            for t in transcript_list:
                transcript = t
                break

        if transcript is None:
            return None

        try:
            fetched = transcript.fetch()
            segments = [
                TranscriptSegment(
                    start_sec=s.start,
                    duration_sec=s.duration,
                    text=s.text,
                )
                for s in fetched
            ]
            full_text = " ".join(s.text for s in segments)
            return TranscriptResult(
                video_id=video_id,
                source="youtube_caption",
                language=transcript.language_code,
                segments=segments,
                full_text=full_text,
            )
        except Exception:
            logger.warning("字幕のフェッチに失敗: %s", video_id, exc_info=True)
            return None

    async def _fetch_whisper(self, video_id: str, audio_path: Path) -> TranscriptResult | None:
        """Whisper API で文字起こしを行う."""
        if not audio_path.exists():
            logger.warning("音声ファイルが存在しません: %s", audio_path)
            return None

        try:
            async with httpx.AsyncClient(timeout=120.0) as client:
                with audio_path.open("rb") as f:
                    response = await client.post(
                        "https://api.openai.com/v1/audio/transcriptions",
                        headers={"Authorization": f"Bearer {self._openai_api_key}"},
                        files={"file": (audio_path.name, f, "audio/mpeg")},
                        data={"model": "whisper-1", "response_format": "verbose_json", "language": "ja"},
                    )
                response.raise_for_status()
                data = response.json()

            segments = [
                TranscriptSegment(
                    start_sec=seg.get("start", 0.0),
                    duration_sec=seg.get("end", 0.0) - seg.get("start", 0.0),
                    text=seg.get("text", ""),
                )
                for seg in data.get("segments", [])
            ]
            full_text = data.get("text", "")

            return TranscriptResult(
                video_id=video_id,
                source="whisper",
                language=data.get("language", "ja"),
                segments=segments,
                full_text=full_text,
            )
        except Exception:
            logger.warning("Whisper API でエラー: %s", video_id, exc_info=True)
            return None
