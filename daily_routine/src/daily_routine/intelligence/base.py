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

    url: str = Field(description="YouTube動画のURL")
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
        max_expand_videos: int = 10,
    ) -> TrendReport:
        """ユーザー提供の競合動画情報を分析し、拡張検索を経てトレンドレポートを生成する.

        Args:
            keyword: 検索キーワード（例：「OLの一日」）
            seed_videos: ユーザーが提供した競合動画情報のリスト
            max_expand_videos: 拡張検索で追加取得する動画の最大数

        Returns:
            トレンド分析レポート
        """
        ...
