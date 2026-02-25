"""Storyboard Engine のレイヤー境界インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from daily_routine.schemas.scenario import Scenario
from daily_routine.schemas.storyboard import Storyboard


class StoryboardEngineBase(ABC):
    """Storyboard Engine のレイヤー境界インターフェース."""

    @abstractmethod
    async def generate(
        self,
        scenario: Scenario,
        output_dir: Path,
    ) -> Storyboard:
        """シナリオからカット分解された絵コンテを生成する.

        Args:
            scenario: Scenario Engine が生成したシナリオ
            output_dir: 出力ディレクトリ（storyboard.json の保存先）

        Returns:
            絵コンテ（カット単位のキーフレーム/モーションプロンプトを含む）
        """
        ...
