"""Intelligence Engine のレイヤー境界インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from pydantic import BaseModel, Field

from daily_routine.schemas.intelligence import TrendReport


class SceneCapture(BaseModel):
    """ユーザーが提供する重要シーンのキャプチャ."""

    image_path: Path = Field(description="スクリーンショット画像のパス")
    description: str = Field(description="このシーンがなぜ重要か、どう活用してほしいか")
    timestamp_sec: float | None = Field(
        default=None,
        description="動画内の大まかな時刻（秒）。不明なら省略可",
    )


class SeedVideo(BaseModel):
    """ユーザーが提供するシード動画情報."""

    note: str = Field(default="", description="動画全体に対するテキスト補足")
    scene_captures: list[SceneCapture] = Field(
        default_factory=list,
        description="重要シーンのキャプチャ（1枚以上推奨）",
    )


class IntelligenceEngineBase(ABC):
    """Intelligence Engine のレイヤー境界インターフェース."""

    @abstractmethod
    async def analyze(
        self,
        keyword: str,
        seed_videos: list[SeedVideo],
    ) -> TrendReport:
        """ユーザー提供の競合動画情報を分析し、トレンドレポートを生成する.

        Args:
            keyword: 検索キーワード（例：「OLの一日」）
            seed_videos: ユーザーが提供した競合動画情報のリスト

        Returns:
            トレンド分析レポート
        """
        ...
