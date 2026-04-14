"""動画生成AIクライアントの共通インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field


class VideoGenerationRequest(BaseModel):
    """動画生成リクエスト."""

    reference_image_path: Path = Field(description="リファレンス画像のパス")
    prompt: str = Field(description="動画生成プロンプト")
    duration_sec: int = Field(default=8, description="動画の長さ（秒）")
    aspect_ratio: str = Field(default="9:16", description="アスペクト比")


class VideoGenerationResult(BaseModel):
    """動画生成結果."""

    video_path: Path = Field(description="生成された動画ファイルのパス")
    generation_time_sec: float = Field(description="生成にかかった時間（秒）")
    model_name: str = Field(description="使用モデル名")
    cost_usd: float | None = Field(default=None, description="推定コスト（USD）")


class VideoGeneratorClient(ABC):
    """動画生成AIクライアントの共通インターフェース."""

    @abstractmethod
    async def generate(self, request: VideoGenerationRequest, output_path: Path) -> VideoGenerationResult:
        """リファレンス画像から動画を生成して保存し、結果を返す.

        Args:
            request: 動画生成リクエスト
            output_path: 動画ファイルの保存先パス
        """
        ...
