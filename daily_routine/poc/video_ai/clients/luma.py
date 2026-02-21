"""Luma Dream Machine 動画生成クライアント."""

import asyncio
import logging
import os
import time

import httpx

from .base import VideoGenerationRequest, VideoGenerationResult, VideoGeneratorClient

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.lumalabs.ai/dream-machine/v1"


class LumaClient(VideoGeneratorClient):
    """Luma Dream Machine (Ray 2) クライアント."""

    def __init__(self, api_key: str | None = None, output_dir: str = "generated/luma") -> None:
        self.api_key = api_key or os.environ["DAILY_ROUTINE_API_KEY_LUMA"]
        self.output_dir = output_dir
        self.model = "ray-2"

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        image_url = request.metadata.get("image_url")
        if not image_url:
            raise ValueError("Luma requires image_url in request metadata (URL-based image input)")

        payload = {
            "prompt": request.prompt,
            "model": self.model,
            "aspect_ratio": request.aspect_ratio,
            "keyframes": {
                "frame0": {
                    "type": "image",
                    "url": image_url,
                },
            },
        }

        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        start = time.time()

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(f"{_BASE_URL}/generations", json=payload, headers=headers)
            resp.raise_for_status()
            generation_id = resp.json()["id"]
            logger.info("Luma generation started: %s", generation_id)

            video_url = await self._poll_generation(client, generation_id, headers)

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
            cost_usd=1.60,
            metadata={"generation_id": generation_id},
        )

    async def _poll_generation(self, client: httpx.AsyncClient, generation_id: str, headers: dict) -> str:
        for _ in range(120):
            await asyncio.sleep(5)
            resp = await client.get(f"{_BASE_URL}/generations/{generation_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            state = data["state"]
            if state == "completed":
                return data["assets"]["video"]
            if state == "failed":
                raise RuntimeError(f"Luma generation failed: {data.get('failure_reason')}")
            logger.debug("Luma polling... state=%s", state)
        raise TimeoutError("Luma generation timed out after 10 minutes")

    def get_api_info(self) -> dict:
        return {
            "provider": "Luma Dream Machine",
            "model": self.model,
            "cost_approx_usd": 1.60,
            "max_duration_sec": 5,
            "image_input": "url (keyframes.frame0)",
        }
