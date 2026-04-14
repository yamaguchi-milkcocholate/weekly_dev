"""Runway Gen-4 Turbo 動画生成クライアント."""

import asyncio
import logging
import os
import time

import httpx

from .base import VideoGenerationRequest, VideoGenerationResult, VideoGeneratorClient

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.dev.runwayml.com/v1"
_COST_PER_SEC = 0.05

# Runway APIはピクセル比で指定する（"9:16" 等の一般的な比率は不可）
_ASPECT_RATIO_MAP = {
    "16:9": "1280:720",
    "9:16": "720:1280",
    "4:3": "1104:832",
    "3:4": "832:1104",
    "1:1": "960:960",
    "21:9": "1584:672",
}


class RunwayClient(VideoGeneratorClient):
    """Runway Gen-4 Turbo クライアント."""

    def __init__(self, api_key: str | None = None, output_dir: str = "generated/runway") -> None:
        self.api_key = api_key or os.environ["DAILY_ROUTINE_API_KEY_RUNWAY"]
        self.output_dir = output_dir
        self.model = "gen4_turbo"

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        image_url = request.metadata.get("image_url")
        if not image_url:
            raise ValueError("Runway requires image_url in request metadata (URL-based image input)")

        duration_sec = 10
        payload = {
            "model": self.model,
            "promptImage": image_url,
            "promptText": request.prompt,
            "ratio": _ASPECT_RATIO_MAP.get(request.aspect_ratio, request.aspect_ratio),
            "duration": duration_sec,
        }

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "X-Runway-Version": "2024-11-06",
        }
        start = time.time()

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(f"{_BASE_URL}/image_to_video", json=payload, headers=headers)
            resp.raise_for_status()
            task_id = resp.json()["id"]
            logger.info("Runway task started: %s", task_id)

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
            cost_usd=_COST_PER_SEC * duration_sec,
            metadata={"task_id": task_id},
        )

    async def _poll_task(self, client: httpx.AsyncClient, task_id: str, headers: dict) -> str:
        for _ in range(120):
            await asyncio.sleep(5)
            resp = await client.get(f"{_BASE_URL}/tasks/{task_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            status = data["status"]
            if status == "SUCCEEDED":
                return data["output"][0]
            if status == "FAILED":
                raise RuntimeError(f"Runway task failed: {data.get('failure')}")
            logger.debug("Runway polling... status=%s", status)
        raise TimeoutError("Runway task timed out after 10 minutes")

    def get_api_info(self) -> dict:
        return {
            "provider": "Runway",
            "model": self.model,
            "cost_per_sec_usd": _COST_PER_SEC,
            "default_duration_sec": 10,
            "image_input": "url (promptImage)",
        }
