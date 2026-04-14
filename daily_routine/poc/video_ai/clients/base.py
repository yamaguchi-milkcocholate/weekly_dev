"""動画生成AIクライアントの共通インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel


class VideoGenerationRequest(BaseModel):
    """動画生成リクエスト."""

    reference_image_path: Path
    prompt: str
    duration_sec: int = 5
    aspect_ratio: str = "9:16"
    metadata: dict = {}


class VideoGenerationResult(BaseModel):
    """動画生成結果."""

    video_path: Path
    generation_time_sec: float
    model_name: str
    cost_usd: float | None = None
    metadata: dict = {}


class VideoGeneratorClient(ABC):
    """動画生成AIクライアントの共通インターフェース."""

    @abstractmethod
    async def generate(self, request: VideoGenerationRequest) -> VideoGenerationResult:
        """リファレンス画像から動画を生成して保存し、結果を返す."""
        ...

    @abstractmethod
    def get_api_info(self) -> dict:
        """API情報（レート制限、コスト等）を返す."""
        ...
