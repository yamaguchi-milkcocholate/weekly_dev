"""Google Veo (Vertex AI) 動画生成クライアント."""

import asyncio
import base64
import logging
import time

import httpx

from .base import VideoGenerationRequest, VideoGenerationResult, VideoGeneratorClient

logger = logging.getLogger(__name__)

_COST_PER_SEC = 0.50


class VeoClient(VideoGeneratorClient):
    """Google Veo 2 クライアント（Vertex AI経由）."""

    def __init__(self, project_id: str, location: str = "us-central1", output_dir: str = "generated/veo") -> None:
        self.project_id = project_id
        self.location = location
        self.output_dir = output_dir
        self.model = "veo-2.0-generate-001"
        self._base_url = (
            f"https://{location}-aiplatform.googleapis.com/v1/projects/{project_id}"
            f"/locations/{location}/publishers/google/models/{self.model}"
        )

    async def _get_access_token(self) -> str:
        proc = await asyncio.create_subprocess_exec(
            "gcloud", "auth", "print-access-token",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, stderr = await proc.communicate()
        if proc.returncode != 0:
            raise RuntimeError(f"gcloud auth failed: {stderr.decode()}")
        return stdout.decode().strip()

    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        image_bytes = request.reference_image_path.read_bytes()
        image_b64 = base64.b64encode(image_bytes).decode()

        duration_sec = 8
        payload = {
            "instances": [
                {
                    "prompt": request.prompt,
                    "image": {"bytesBase64Encoded": image_b64, "mimeType": "image/png"},
                }
            ],
            "parameters": {
                "aspectRatio": request.aspect_ratio,
                "durationSeconds": duration_sec,
                "sampleCount": 1,
            },
        }

        token = await self._get_access_token()
        headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
        start = time.time()

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(f"{self._base_url}:predictLongRunning", json=payload, headers=headers)
            resp.raise_for_status()
            operation = resp.json()
            operation_name = operation["name"]
            logger.info("Veo operation started: %s", operation_name)

            video_b64 = await self._poll_operation(client, operation_name, headers)

        elapsed = time.time() - start

        from pathlib import Path

        out_dir = Path(self.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        video_path = out_dir / "output.mp4"
        video_path.write_bytes(base64.b64decode(video_b64))

        return VideoGenerationResult(
            video_path=video_path,
            generation_time_sec=elapsed,
            model_name=self.model,
            cost_usd=_COST_PER_SEC * duration_sec,
            metadata={"operation_name": operation_name},
        )

    async def _poll_operation(self, client: httpx.AsyncClient, operation_name: str, headers: dict) -> str:
        poll_url = f"{self._base_url}:fetchPredictOperation"
        for _ in range(120):
            await asyncio.sleep(10)
            resp = await client.post(
                poll_url, json={"operationName": operation_name}, headers=headers
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("done"):
                videos = data["response"]["videos"]
                if not videos:
                    raise RuntimeError("Veo returned no videos")
                return videos[0]["bytesBase64Encoded"]
            logger.debug("Veo polling... (not done yet)")
        raise TimeoutError("Veo operation timed out after 20 minutes")

    def get_api_info(self) -> dict:
        return {
            "provider": "Google Veo (Vertex AI)",
            "model": self.model,
            "cost_per_sec_usd": _COST_PER_SEC,
            "max_duration_sec": 8,
            "image_input": "base64",
        }
