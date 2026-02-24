"""Audio Engine のレイヤー境界インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from daily_routine.schemas.audio import AudioAsset
from daily_routine.schemas.intelligence import AudioTrend
from daily_routine.schemas.scenario import Scenario


class AudioEngineBase(ABC):
    """Audio Engine のレイヤー境界インターフェース."""

    @abstractmethod
    async def generate(
        self,
        audio_trend: AudioTrend,
        scenario: Scenario,
        output_dir: Path,
    ) -> AudioAsset:
        """トレンド分析とシナリオに基づき、BGM と SE を調達する.

        Args:
            audio_trend: Intelligence Engine が生成した音響トレンド
            scenario: Scenario Engine が生成したシナリオ
            output_dir: 音声ファイルの出力先ディレクトリ

        Returns:
            BGM + SE のアセット情報
        """
        ...
