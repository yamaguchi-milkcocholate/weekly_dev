"""Scenario Engine のレイヤー境界インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from daily_routine.schemas.intelligence import TrendReport
from daily_routine.schemas.scenario import Scenario


class ScenarioEngineBase(ABC):
    """Scenario Engine のレイヤー境界インターフェース."""

    @abstractmethod
    async def generate(
        self,
        trend_report: TrendReport,
        output_dir: Path,
        duration_range: tuple[int, int] = (30, 60),
        user_direction: str | None = None,
    ) -> Scenario:
        """トレンド分析レポートからシナリオを生成する.

        Args:
            trend_report: Intelligence Engine が生成したトレンド分析レポート
            output_dir: 出力ディレクトリ（scenario.json の保存先）
            duration_range: 動画尺の範囲（秒）。デフォルトは 30〜60秒
            user_direction: ユーザーのクリエイティブディレクション（自由テキスト）。
                例: 「コメディ寄りにしたい」「朝のシーンを長めに」等。
                省略時はトレンド分析のみに基づいて生成する。

        Returns:
            シナリオ（キャラクター仕様、小物仕様、シーン仕様、BGM方向性を含む）
        """
        ...
