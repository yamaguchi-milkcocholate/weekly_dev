"""画像生成AIクライアントの共通インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel


class GenerationRequest(BaseModel):
    """画像生成リクエスト."""

    prompt: str
    negative_prompt: str | None = None
    width: int = 1024
    height: int = 1024
    seed: int | None = None


class GenerationResult(BaseModel):
    """画像生成結果."""

    image_path: Path
    generation_time_sec: float
    model_name: str
    cost_usd: float | None = None
    metadata: dict = {}


class ImageGeneratorClient(ABC):
    """画像生成AIクライアントの共通インターフェース."""

    @abstractmethod
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """画像を生成して保存し、結果を返す."""
        ...

    @abstractmethod
    def get_api_info(self) -> dict:
        """API情報（レート制限、コスト等）を返す."""
        ...
