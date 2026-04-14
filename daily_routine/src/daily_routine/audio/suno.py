"""Suno API v4 クライアント（BGM 生成）."""

import asyncio
import logging
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_BASE_URL = "https://apibox.erweima.ai"
_MAX_RETRIES = 3


class SunoTrack(BaseModel):
    """Suno で生成されたトラック."""

    track_id: str
    title: str
    audio_url: str = Field(description="ダウンロード可能な音声 URL")
    duration_sec: float
    tags: list[str] = Field(default_factory=list)
    status: str = Field(description="生成ステータス: 'complete' | 'generating' | 'error'")


class SunoGenerationError(Exception):
    """Suno API での生成エラー."""


class SunoTimeoutError(SunoGenerationError):
    """Suno API 生成のタイムアウト."""


class SunoClient:
    """Suno API v4 クライアント."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key

    async def generate(
        self,
        prompt: str,
        duration_sec: int = 60,
        instrumental: bool = True,
    ) -> list[SunoTrack]:
        """BGM を生成する.

        Suno はプロンプトから2曲を同時生成する。
        instrumental=True でボーカルなしの楽曲を生成。

        Args:
            prompt: 楽曲の説明（ジャンル、BPM、雰囲気等）
            duration_sec: 目標楽曲長（秒）
            instrumental: インストゥルメンタルのみ

        Returns:
            生成されたトラックのリスト（通常2曲）

        Raises:
            SunoGenerationError: 生成リクエストに失敗した場合
        """
        payload = {
            "prompt": prompt,
            "customMode": False,
            "instrumental": instrumental,
        }

        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.post(
                f"{_BASE_URL}/api/v4/generate",
                json=payload,
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 200:
            msg = f"Suno 生成リクエスト失敗: {data.get('message', 'unknown error')}"
            raise SunoGenerationError(msg)

        task_id = data.get("data", {}).get("taskId", "")
        if not task_id:
            msg = "Suno レスポンスに taskId がありません"
            raise SunoGenerationError(msg)

        logger.info("Suno 生成リクエスト送信: taskId=%s", task_id)

        # ポーリングで完了を待機
        tracks = await self.wait_for_completion([task_id])
        return tracks

    async def wait_for_completion(
        self,
        task_ids: list[str],
        timeout_sec: int = 300,
        poll_interval_sec: int = 10,
    ) -> list[SunoTrack]:
        """トラック生成の完了を待機する.

        Args:
            task_ids: 待機対象のタスクID
            timeout_sec: タイムアウト（秒）
            poll_interval_sec: ポーリング間隔（秒）

        Returns:
            完了したトラックのリスト

        Raises:
            SunoTimeoutError: タイムアウトした場合
            SunoGenerationError: 生成に失敗した場合
        """
        elapsed = 0

        while elapsed < timeout_sec:
            all_tracks: list[SunoTrack] = []
            all_complete = True

            for task_id in task_ids:
                tracks = await self._get_task_status(task_id)
                for track in tracks:
                    if track.status == "error":
                        msg = f"Suno 楽曲生成エラー: track_id={track.track_id}"
                        raise SunoGenerationError(msg)
                    if track.status != "complete":
                        all_complete = False
                all_tracks.extend(tracks)

            if all_complete and all_tracks:
                logger.info("Suno 生成完了: %d曲", len(all_tracks))
                return all_tracks

            logger.debug("Suno 生成待機中... (%d秒経過)", elapsed)
            await asyncio.sleep(poll_interval_sec)
            elapsed += poll_interval_sec

        raise SunoTimeoutError(f"Suno 生成タイムアウト ({timeout_sec}秒)")

    async def download(self, audio_url: str, output_path: Path) -> Path:
        """生成された音声ファイルをダウンロードする.

        Args:
            audio_url: ダウンロード元 URL
            output_path: 保存先パス

        Returns:
            ダウンロードしたファイルのパス

        Raises:
            httpx.HTTPStatusError: ダウンロードに失敗した場合
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.get(audio_url, follow_redirects=True)
                    response.raise_for_status()
                    output_path.write_bytes(response.content)
                    logger.info("Suno ダウンロード完了: %s", output_path)
                    return output_path
            except (httpx.HTTPError, OSError):
                if attempt < _MAX_RETRIES:
                    logger.warning("Suno ダウンロードリトライ (%d/%d): %s", attempt, _MAX_RETRIES, audio_url)
                else:
                    logger.error("Suno ダウンロード失敗（リトライ上限）: %s", audio_url)
                    raise

        return output_path  # unreachable, for type checker

    async def _get_task_status(self, task_id: str) -> list[SunoTrack]:
        """タスクの生成ステータスを取得する.

        Args:
            task_id: Suno のタスクID

        Returns:
            トラック情報のリスト
        """
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{_BASE_URL}/api/v4/generate/record-info",
                params={"taskId": task_id},
                headers={"Authorization": f"Bearer {self._api_key}"},
            )
            response.raise_for_status()
            data = response.json()

        if data.get("code") != 200:
            return []

        records = data.get("data", {}).get("response", {}).get("sunoData", [])
        tracks: list[SunoTrack] = []
        for record in records:
            status_raw = record.get("status", "")
            # Suno のステータスをマッピング
            if status_raw in ("complete", "streaming"):
                status = "complete"
            elif status_raw == "error":
                status = "error"
            else:
                status = "generating"

            tracks.append(
                SunoTrack(
                    track_id=record.get("id", ""),
                    title=record.get("title", ""),
                    audio_url=record.get("audioUrl", "") or record.get("sourceAudioUrl", ""),
                    duration_sec=record.get("duration", 0),
                    tags=[t.strip() for t in record.get("tags", "").split(",") if t.strip()],
                    status=status,
                )
            )

        return tracks
