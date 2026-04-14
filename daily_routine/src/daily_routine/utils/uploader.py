"""画像アップロードユーティリティ."""

import asyncio
import logging
from abc import ABC, abstractmethod
from pathlib import Path

logger = logging.getLogger(__name__)


class ImageUploader(ABC):
    """画像アップロードの抽象インターフェース."""

    @abstractmethod
    async def upload(self, image_path: Path) -> str:
        """画像をアップロードし、公開URLを返す."""
        ...


class GcsUploader(ImageUploader):
    """Google Cloud Storage へのアップローダー."""

    def __init__(self, bucket_name: str, prefix: str = "visual/") -> None:
        if not bucket_name:
            msg = "GCSバケット名が設定されていません"
            raise ValueError(msg)
        self._bucket_name = bucket_name
        self._prefix = prefix

    async def upload(self, image_path: Path) -> str:
        """画像を GCS にアップロードし、公開 URL を返す."""
        if not image_path.exists():
            msg = f"画像ファイルが存在しません: {image_path}"
            raise FileNotFoundError(msg)

        gcs_dest = f"gs://{self._bucket_name}/{self._prefix}{image_path.name}"

        proc = await asyncio.create_subprocess_exec(
            "gcloud",
            "storage",
            "cp",
            str(image_path),
            gcs_dest,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await proc.communicate()

        if proc.returncode != 0:
            msg = f"GCSアップロードに失敗しました: {stderr.decode().strip()}"
            raise RuntimeError(msg)

        public_url = f"https://storage.googleapis.com/{self._bucket_name}/{self._prefix}{image_path.name}"
        logger.info("GCSにアップロードしました: %s -> %s", image_path, public_url)
        return public_url
