"""PoC Step 6: 共通インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field


class RenderToImageRequest(BaseModel):
    """3Dレンダリング → AI画像変換リクエスト."""

    render_image_path: Path = Field(description="3Dレンダリング画像（構造情報）")
    style_text: str = Field(description="スタイル記述テキスト")
    prompt: str = Field(description="生成指示プロンプト（スタイルテキスト埋め込み済み）")
    camera_id: str = Field(description="カメラID（例: 'カメラ1'）")


class RenderToImageResult(BaseModel):
    """3Dレンダリング → AI画像変換結果."""

    image_path: Path = Field(description="生成された画像ファイルのパス")
    generation_time_sec: float = Field(description="生成所要時間（秒）")
    model_name: str = Field(description="使用モデル名")
    cost_usd: float | None = Field(default=None, description="推定コスト（USD）")
    camera_id: str = Field(description="カメラID")
    metadata: dict = Field(default_factory=dict, description="追加情報")


class RenderToImageClient(ABC):
    """3Dレンダリング→AI画像変換クライアントの共通インターフェース."""

    @abstractmethod
    async def generate(self, request: RenderToImageRequest, output_path: Path) -> RenderToImageResult:
        """レンダリング画像+テキストスタイルからAI画像を生成して保存する."""
        ...

    @abstractmethod
    def get_api_info(self) -> dict:
        """API情報を返す."""
        ...
