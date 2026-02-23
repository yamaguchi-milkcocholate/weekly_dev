"""Kling AI 動画生成クライアント.

Kling APIはAccess Key + Secret KeyによるJWT (HS256) 認証を使用する。
リクエストごとにJWTトークンを生成し、Authorizationヘッダーに付与する。
"""

import asyncio
import logging
import os
import time
from pathlib import Path

import httpx
import jwt

from .base import VideoGenerationRequest, VideoGenerationResult, VideoGeneratorClient

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.klingai.com/v1"
_TOKEN_EXPIRE_SECONDS = 1800
_CLOCK_SKEW_SECONDS = 5
_REFRESH_BUFFER_SECONDS = 60


def _generate_jwt(access_key: str, secret_key: str) -> str:
    """Access KeyとSecret KeyからJWTトークンを生成する."""
    now = int(time.time())
    headers = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": access_key,
        "exp": now + _TOKEN_EXPIRE_SECONDS,
        "nbf": now - _CLOCK_SKEW_SECONDS,
    }
    return jwt.encode(payload, secret_key, headers=headers)


class KlingClient(VideoGeneratorClient):
    """Kling AI v2.5 Turbo クライアント."""

    def __init__(
        self,
        access_key: str | None = None,
        secret_key: str | None = None,
        output_dir: str = "generated/kling",
    ) -> None:
        self._access_key = access_key or os.environ["DAILY_ROUTINE_API_KEY_KLING_AK"]
        self._secret_key = secret_key or os.environ["DAILY_ROUTINE_API_KEY_KLING_SK"]
        self.output_dir = output_dir
        self.model = "kling-v2-5-turbo"
        self._cached_token: str | None = None
        self._token_exp: int = 0

    def _get_auth_headers(self) -> dict[str, str]:
        """認証ヘッダーを返す。トークンが期限切れの場合は自動再生成する."""
        now = int(time.time())
        if self._cached_token is None or now >= (self._token_exp - _REFRESH_BUFFER_SECONDS):
            self._cached_token = _generate_jwt(self._access_key, self._secret_key)
            self._token_exp = now + _TOKEN_EXPIRE_SECONDS
            logger.debug("Kling JWT token refreshed")
        return {
            "Authorization": f"Bearer {self._cached_token}",
            "Content-Type": "application/json",
        }

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

        start = time.time()

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(
                f"{_BASE_URL}/videos/image2video", json=payload, headers=self._get_auth_headers()
            )
            resp.raise_for_status()
            task_id = resp.json()["data"]["task_id"]
            logger.info("Kling task started: %s", task_id)

            video_url = await self._poll_task(client, task_id)

        elapsed = time.time() - start

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

    async def _poll_task(self, client: httpx.AsyncClient, task_id: str) -> str:
        for _ in range(120):
            await asyncio.sleep(5)
            resp = await client.get(
                f"{_BASE_URL}/videos/image2video/{task_id}", headers=self._get_auth_headers()
            )
            resp.raise_for_status()
            data = resp.json()["data"]
            status = data["task_status"]
            if status == "succeed":
                return data["task_result"]["videos"][0]["url"]
            if status == "failed":
                raise RuntimeError("Kling task failed: %s" % data.get("task_status_msg"))
            logger.debug("Kling polling... status=%s", status)
        raise TimeoutError("Kling task timed out after 10 minutes")

    def get_api_info(self) -> dict:
        return {
            "provider": "Kling AI",
            "model": self.model,
            "cost_5sec_usd": 0.21,
            "max_duration_sec": 10,
            "image_input": "url",
            "auth": "JWT (HS256) via Access Key + Secret Key",
        }
