"""Runway Gen-4 Turbo 動画生成クライアント."""

import asyncio
import logging
import time
from pathlib import Path

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from daily_routine.utils.uploader import ImageUploader

from .base import VideoGenerationRequest, VideoGenerationResult, VideoGeneratorClient

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.dev.runwayml.com/v1"
_COST_PER_SEC = 0.05
_POLL_INTERVAL_SEC = 5
_POLL_MAX_ATTEMPTS = 60  # 5秒 x 60 = 最大5分

# Runway APIはピクセル比で指定する
_ASPECT_RATIO_MAP: dict[str, str] = {
    "16:9": "1280:720",
    "9:16": "720:1280",
    "4:3": "1104:832",
    "3:4": "832:1104",
    "1:1": "960:960",
    "21:9": "1584:672",
}


class RunwayClient(VideoGeneratorClient):
    """Runway Gen-4 Turbo クライアント."""

    def __init__(
        self,
        api_key: str,
        uploader: ImageUploader,
        model: str = "gen4_turbo",
    ) -> None:
        if not api_key:
            msg = "Runway APIキーが設定されていません"
            raise ValueError(msg)
        self._api_key = api_key
        self._uploader = uploader
        self._model = model

    def _build_headers(self) -> dict[str, str]:
        return {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06",
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=5, min=5, max=60),
        retry=retry_if_exception_type(httpx.HTTPStatusError),
    )
    async def generate(self, request: VideoGenerationRequest, output_path: Path) -> VideoGenerationResult:
        """リファレンス画像をGCSにアップロードし、Runway APIで動画を生成する.

        処理フロー:
        1. リファレンス画像を GCS にアップロードして公開 URL を取得
        2. image_to_video API で動画生成タスクを作成
        3. タスクIDでポーリング（5秒間隔、最大5分）
        4. 完了後、動画 URL からダウンロードして output_path に保存
        """
        if not request.reference_image_path.exists():
            msg = f"リファレンス画像が存在しません: {request.reference_image_path}"
            raise FileNotFoundError(msg)

        start = time.time()

        # 1. GCSにアップロード
        image_url = await self._uploader.upload(request.reference_image_path)
        logger.info("リファレンス画像をアップロードしました: %s", image_url)

        # 2. 動画生成タスクを作成
        duration_sec = request.duration_sec
        payload = {
            "model": self._model,
            "promptImage": image_url,
            "promptText": request.prompt,
            "ratio": _ASPECT_RATIO_MAP.get(request.aspect_ratio, request.aspect_ratio),
            "duration": duration_sec,
        }
        headers = self._build_headers()

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(f"{_BASE_URL}/image_to_video", json=payload, headers=headers)
            resp.raise_for_status()
            task_id = resp.json()["id"]
            logger.info("Runway動画生成タスクを作成しました: %s", task_id)

            # 3. ポーリング
            video_url = await self._poll_task(client, task_id, headers)

        # 4. ダウンロード
        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            resp = await client.get(video_url)
            resp.raise_for_status()
            output_path.write_bytes(resp.content)

        elapsed = time.time() - start
        logger.info("動画を保存しました: %s (%.1f秒)", output_path, elapsed)

        return VideoGenerationResult(
            video_path=output_path,
            generation_time_sec=elapsed,
            model_name=self._model,
            cost_usd=_COST_PER_SEC * duration_sec,
        )

    async def _poll_task(self, client: httpx.AsyncClient, task_id: str, headers: dict[str, str]) -> str:
        """タスクの完了をポーリングし、動画URLを返す."""
        for attempt in range(_POLL_MAX_ATTEMPTS):
            await asyncio.sleep(_POLL_INTERVAL_SEC)
            resp = await client.get(f"{_BASE_URL}/tasks/{task_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            status = data["status"]

            if status == "SUCCEEDED":
                logger.info("動画生成完了: task_id=%s", task_id)
                return data["output"][0]
            if status == "FAILED":
                msg = f"Runway動画生成に失敗しました: {data.get('failure')}"
                raise RuntimeError(msg)

            logger.debug(
                "ポーリング中... task_id=%s, status=%s, attempt=%d/%d",
                task_id,
                status,
                attempt + 1,
                _POLL_MAX_ATTEMPTS,
            )

        msg = f"Runway動画生成がタイムアウトしました: task_id={task_id}"
        raise TimeoutError(msg)
