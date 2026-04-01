"""PoC Step 6: Gemini 3.0 Pro Image クライアント.

1画像入力+テキストスタイル方式。httpx直接REST API呼び出し。
"""

import base64
import logging
import os
import time
from pathlib import Path

import httpx

from .base import RenderToImageClient, RenderToImageRequest, RenderToImageResult

logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3-pro-image-preview"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
COST_PER_IMAGE = 0.134  # 1K/2K解像度


def _encode_image_inline(image_path: Path) -> dict:
    """Gemini API用の inline_data パートを構築する."""
    data = image_path.read_bytes()
    suffix = image_path.suffix.lstrip(".")
    mime = f"image/{suffix}" if suffix != "jpg" else "image/jpeg"
    return {
        "inline_data": {
            "mime_type": mime,
            "data": base64.b64encode(data).decode("utf-8"),
        }
    }


def _extract_image(result: dict) -> bytes | None:
    """Gemini レスポンスから画像バイナリを抽出する."""
    candidates = result.get("candidates", [])
    for candidate in candidates:
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        for part in parts:
            if "inlineData" in part:
                return base64.b64decode(part["inlineData"]["data"])
    return None


class GeminiRenderClient(RenderToImageClient):
    """Gemini 3.0 Pro Image を使った画像生成クライアント."""

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key or os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI", "")
        if not self._api_key:
            msg = "DAILY_ROUTINE_API_KEY_GOOGLE_AI が設定されていません"
            raise ValueError(msg)

    async def generate(self, request: RenderToImageRequest, output_path: Path) -> RenderToImageResult:
        """レンダリング画像+テキストスタイルからAI画像を生成する."""
        start = time.monotonic()

        parts = [
            _encode_image_inline(request.render_image_path),
            {"text": request.prompt},
        ]

        payload = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "responseModalities": ["TEXT", "IMAGE"],
            },
        }

        url = f"{BASE_URL}/models/{MODEL_NAME}:generateContent"

        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
            resp = await client.post(
                url,
                json=payload,
                headers={"x-goog-api-key": self._api_key},
            )
            if resp.status_code >= 400:
                logger.error("Gemini API エラー: status=%d, body=%s", resp.status_code, resp.text)
            resp.raise_for_status()

        result = resp.json()
        image_data = _extract_image(result)
        if image_data is None:
            msg = "Gemini: 画像が生成されませんでした"
            raise RuntimeError(msg)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_data)

        elapsed = time.monotonic() - start
        logger.info("Gemini 生成完了: %s (%.1f秒)", request.camera_id, elapsed)

        return RenderToImageResult(
            image_path=output_path,
            generation_time_sec=elapsed,
            model_name=MODEL_NAME,
            cost_usd=COST_PER_IMAGE,
            camera_id=request.camera_id,
        )

    def get_api_info(self) -> dict:
        return {
            "provider": "Google AI",
            "model": MODEL_NAME,
            "cost_per_image_usd": COST_PER_IMAGE,
            "sdk": "httpx (REST API直接)",
        }
