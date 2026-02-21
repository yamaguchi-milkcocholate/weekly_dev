"""DALL-E 3 クライアント（OpenAI SDK経由）."""

import logging
import os
import time
from pathlib import Path

import httpx
from openai import AsyncOpenAI

from .base import GenerationRequest, GenerationResult, ImageGeneratorClient

logger = logging.getLogger(__name__)


class DalleClient(ImageGeneratorClient):
    """DALL-E 3 APIを使った画像生成クライアント."""

    def __init__(self, output_dir: Path, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("DAILY_ROUTINE_API_KEY_OPENAI", "")
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.client = AsyncOpenAI(api_key=self.api_key)

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """DALL-E 3 APIで画像を生成する."""
        start_time = time.monotonic()

        response = await self.client.images.generate(
            model="dall-e-3",
            prompt=request.prompt,
            size="1024x1024",
            quality="hd",
            n=1,
            response_format="url",
        )

        elapsed = time.monotonic() - start_time
        image_url = response.data[0].url
        revised_prompt = response.data[0].revised_prompt

        # 画像をダウンロードして保存
        async with httpx.AsyncClient(timeout=60.0) as http_client:
            img_response = await http_client.get(image_url)
            img_response.raise_for_status()

        output_path = self.output_dir / f"{int(time.time())}.png"
        output_path.write_bytes(img_response.content)

        logger.info("DALL-E 3: 画像生成完了 (%.1f秒) -> %s", elapsed, output_path)

        return GenerationResult(
            image_path=output_path,
            generation_time_sec=elapsed,
            model_name="dall-e-3",
            cost_usd=0.080,  # DALL-E 3 HD 1024x1024: $0.080/image
            metadata={"revised_prompt": revised_prompt},
        )

    def get_api_info(self) -> dict:
        """DALL-E 3 APIの情報を返す."""
        return {
            "provider": "OpenAI",
            "model": "dall-e-3",
            "cost_per_image_usd": 0.080,
            "max_resolution": "1024x1024 (HD)",
            "supports_negative_prompt": False,
            "supports_seed": False,
            "sdk": "openai (langchain-openai依存)",
        }
