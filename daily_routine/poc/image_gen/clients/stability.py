"""Stability AI APIクライアント."""

import base64
import logging
import os
import time
from pathlib import Path

import httpx

from .base import GenerationRequest, GenerationResult, ImageGeneratorClient

logger = logging.getLogger(__name__)

# Stability AI REST API (SD3.5系)
STABILITY_API_URL = "https://api.stability.ai/v2beta/stable-image/generate/sd3"


class StabilityClient(ImageGeneratorClient):
    """Stability AI APIを使った画像生成クライアント."""

    def __init__(self, output_dir: Path, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("DAILY_ROUTINE_API_KEY_STABILITY", "")
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Stability AI APIで画像を生成する."""
        start_time = time.monotonic()

        form_data = {
            "prompt": request.prompt,
            "output_format": "png",
            "aspect_ratio": "1:1",
            "model": "sd3.5-large",
        }
        if request.negative_prompt:
            form_data["negative_prompt"] = request.negative_prompt
        if request.seed is not None:
            form_data["seed"] = str(request.seed)

        async with httpx.AsyncClient(timeout=120.0) as client:
            response = await client.post(
                STABILITY_API_URL,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
                files={k: (None, v) for k, v in form_data.items()},
            )
            response.raise_for_status()

        elapsed = time.monotonic() - start_time
        result_data = response.json()

        # APIレスポンスからBase64画像をデコードして保存
        image_b64 = result_data["image"]
        image_bytes = base64.b64decode(image_b64)

        output_path = self.output_dir / f"{int(time.time())}.png"
        output_path.write_bytes(image_bytes)

        logger.info("Stability AI: 画像生成完了 (%.1f秒) -> %s", elapsed, output_path)

        return GenerationResult(
            image_path=output_path,
            generation_time_sec=elapsed,
            model_name="sd3.5-large",
            cost_usd=0.065,  # SD3.5 Large: $0.065/image
            metadata={"seed": result_data.get("seed"), "finish_reason": result_data.get("finish_reason")},
        )

    def get_api_info(self) -> dict:
        """Stability AI APIの情報を返す."""
        return {
            "provider": "Stability AI",
            "model": "sd3.5-large",
            "cost_per_image_usd": 0.065,
            "max_resolution": "1024x1024",
            "supports_negative_prompt": True,
            "supports_seed": True,
            "sdk": "httpx (REST API直接呼び出し)",
        }
