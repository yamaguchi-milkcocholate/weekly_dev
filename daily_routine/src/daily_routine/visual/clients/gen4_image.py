"""Runway Gen-4 Image キーフレーム画像生成クライアント."""

import asyncio
import logging
import time
from pathlib import Path

import httpx
from pydantic import BaseModel, Field
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from daily_routine.utils.uploader import ImageUploader

logger = logging.getLogger(__name__)

_BASE_URL = "https://api.dev.runwayml.com/v1"
_COST_PER_IMAGE = 0.02  # Gen-4 Image Turbo = 2 credits = $0.02
_POLL_INTERVAL_SEC = 5
_POLL_MAX_ATTEMPTS = 60  # 5秒 x 60 = 最大5分


class ImageGenerationRequest(BaseModel):
    """画像生成リクエスト."""

    prompt: str = Field(description="画像生成プロンプト（@tagを含む）")
    reference_images: dict[str, Path] = Field(description="参照画像 {tag: 画像パス}")
    ratio: str = Field(default="1080:1920", description="出力解像度（幅:高さ）")


class ImageGenerationResult(BaseModel):
    """画像生成結果."""

    image_path: Path = Field(description="生成された画像ファイルのパス")
    model_name: str = Field(description="使用モデル名")
    cost_usd: float | None = Field(default=None, description="推定コスト（USD）")


class RunwayImageClient:
    """Runway Gen-4 Image クライアント."""

    def __init__(
        self,
        api_key: str,
        uploader: ImageUploader,
        model: str = "gen4_image_turbo",
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
    async def generate(self, request: ImageGenerationRequest, output_path: Path) -> ImageGenerationResult:
        """参照画像を使ってキーフレーム画像を生成する.

        処理フロー:
        1. 参照画像を GCS にアップロード
        2. Gen-4 Image API でリクエスト（referenceImages + @tag）
        3. タスクIDでポーリング
        4. 完了後、画像URLからダウンロードして保存
        """
        start = time.time()

        # 1. 参照画像をGCSにアップロード
        reference_images = []
        for tag, image_path in request.reference_images.items():
            if not image_path.exists():
                msg = f"参照画像が存在しません: {image_path}"
                raise FileNotFoundError(msg)
            image_url = await self._uploader.upload(image_path)
            reference_images.append({"uri": image_url, "tag": tag})
            logger.info("参照画像をアップロードしました: tag=%s, url=%s", tag, image_url)

        # 2. 画像生成タスクを作成
        payload: dict = {
            "model": self._model,
            "promptText": request.prompt,
            "ratio": request.ratio,
            "referenceImages": reference_images,
        }
        headers = self._build_headers()

        async with httpx.AsyncClient(timeout=httpx.Timeout(300.0)) as client:
            resp = await client.post(f"{_BASE_URL}/text_to_image", json=payload, headers=headers)
            if resp.status_code >= 400:
                logger.error("Runway API エラー: status=%d, body=%s", resp.status_code, resp.text)
            resp.raise_for_status()
            task_id = resp.json()["id"]
            logger.info("Runway画像生成タスクを作成しました: %s", task_id)

            # 3. ポーリング
            image_url = await self._poll_task(client, task_id, headers)

        # 4. ダウンロード
        output_path.parent.mkdir(parents=True, exist_ok=True)
        async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
            resp = await client.get(image_url)
            resp.raise_for_status()
            output_path.write_bytes(resp.content)

        elapsed = time.time() - start
        logger.info("画像を保存しました: %s (%.1f秒)", output_path, elapsed)

        return ImageGenerationResult(
            image_path=output_path,
            model_name=self._model,
            cost_usd=_COST_PER_IMAGE,
        )

    async def _poll_task(self, client: httpx.AsyncClient, task_id: str, headers: dict[str, str]) -> str:
        """タスクの完了をポーリングし、画像URLを返す."""
        for attempt in range(_POLL_MAX_ATTEMPTS):
            await asyncio.sleep(_POLL_INTERVAL_SEC)
            resp = await client.get(f"{_BASE_URL}/tasks/{task_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            status = data["status"]

            if status == "SUCCEEDED":
                logger.info("画像生成完了: task_id=%s", task_id)
                return data["output"][0]
            if status == "FAILED":
                msg = f"Runway画像生成に失敗しました: {data.get('failure')}"
                raise RuntimeError(msg)

            logger.debug(
                "ポーリング中... task_id=%s, status=%s, attempt=%d/%d",
                task_id,
                status,
                attempt + 1,
                _POLL_MAX_ATTEMPTS,
            )

        msg = f"Runway画像生成がタイムアウトしました: task_id={task_id}"
        raise TimeoutError(msg)
