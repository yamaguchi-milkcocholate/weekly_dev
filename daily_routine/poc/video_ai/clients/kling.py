"""Kling AI 動画生成クライアント."""

import asyncio
import logging
import os
import time

import httpx

from .base import VideoGenerationRequest, VideoGenerationResult, VideoGeneratorClient

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.klingai.com/v1"


class KlingClient(VideoGeneratorClient):
    """Kling AI v2.5 Turbo クライアント."""

    def __init__(self, api_key: str | None = None, output_dir: str = "generated/kling") -> None:
        self.api_key = api_key or os.environ["DAILY_ROUTINE_API_KEY_KLING"]
        self.output_dir = output_dir
        self.model = "kling-v2-5-turbo"

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        image_url = request.metadata.get("image_url")
        if not image_url:
            raise ValueError("Kling requires image_url in request metadata (URL-based image input)")

        payload = {
            "model_name": self.model,
            "image": image_url,
            "prompt": request.prompt,
            "duration": str(request.duration_sec),
            "aspect_ratio": request.aspect_ratio,
            "mode": "std",
        }

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        start = time.time()

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(f"{_BASE_URL}/videos/image2video", json=payload, headers=headers)
            resp.raise_for_status()
            task_id = resp.json()["data"]["task_id"]
            logger.info("Kling task started: %s", task_id)

            video_url = await self._poll_task(client, task_id, headers)

        elapsed = time.time() - start

        from pathlib import Path

        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        video_path = out_dir / "output.mp4"

        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            resp = await client.get(video_url)
            resp.raise_for_status()
            video_path.write_bytes(resp.content)

        return VideoGenerationResult(
            video_path=video_path,
            generation_time_sec=elapsed,
            model_name=self.model,
            cost_usd=0.21,
            metadata={"task_id": task_id},
        )

    async def _poll_task(self, client: httpx.AsyncClient, task_id: str, headers: dict) -> str:
        for _ in range(120):
            await asyncio.sleep(5)
            resp = await client.get(f"{_BASE_URL}/videos/image2video/{task_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json()["data"]
            status = data["task_status"]
            if status == "succeed":
                return data["task_result"]["videos"][0]["url"]
            if status == "failed":
                raise RuntimeError(f"Kling task failed: {data.get('task_status_msg')}")
            logger.debug("Kling polling... status=%s", status)
        raise TimeoutError("Kling task timed out after 10 minutes")

    def get_api_info(self) -> dict:
        return {
            "provider": "Kling AI",
            "model": self.model,
            "cost_5sec_usd": 0.21,
            "max_duration_sec": 10,
            "image_input": "url",
        }
