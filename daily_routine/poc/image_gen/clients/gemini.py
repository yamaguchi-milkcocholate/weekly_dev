"""Gemini 3 Pro Image クライアント（langchain-google-genai 経由）."""

import base64
import logging
import os
import time
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI

from .base import GenerationRequest, GenerationResult, ImageGeneratorClient

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3-pro-image-preview"


class GeminiClient(ImageGeneratorClient):
    """Gemini 3 Pro Image を使った画像生成クライアント."""

    def __init__(self, output_dir: Path, api_key: str | None = None) -> None:
        self.api_key = api_key or os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI", "")
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.llm = ChatGoogleGenerativeAI(
            model=MODEL_NAME,
            google_api_key=self.api_key,
        )

    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Gemini 3 Pro Image で画像を生成する."""
        start_time = time.monotonic()

        response = await self.llm.ainvoke([HumanMessage(content=request.prompt)])
        elapsed = time.monotonic() - start_time

        # レスポンスから画像データを抽出
        image_data = self._extract_image(response)
        if image_data is None:
            raise RuntimeError("Gemini: 画像が生成されませんでした")

        output_path = self.output_dir / f"{int(time.time())}.png"
        output_path.write_bytes(image_data)

        logger.info("Gemini 3 Pro Image: 画像生成完了 (%.1f秒) -> %s", elapsed, output_path)

        return GenerationResult(
            image_path=output_path,
            generation_time_sec=elapsed,
            model_name=MODEL_NAME,
            cost_usd=None,
            metadata={},
        )

    @staticmethod
    def _extract_image(response: object) -> bytes | None:
        """langchain レスポンスから画像バイナリを抽出する."""
        content = response.content
        if isinstance(content, list):
            for part in content:
                if not isinstance(part, dict):
                    continue
                # inline_data 形式（mime_type + data）
                if "inline_data" in part:
                    return base64.b64decode(part["inline_data"]["data"])
                # image_url 形式（data URI）
                if part.get("type") == "image_url":
                    url = part["image_url"]["url"]
                    if url.startswith("data:"):
                        return base64.b64decode(url.split(",", 1)[1])
        return None

    def get_api_info(self) -> dict:
        """Gemini 3 Pro Image APIの情報を返す."""
        return {
            "provider": "Google AI",
            "model": MODEL_NAME,
            "cost_per_image_usd": None,
            "max_resolution": "4K",
            "supports_negative_prompt": False,
            "supports_seed": False,
            "sdk": "langchain-google-genai",
        }
