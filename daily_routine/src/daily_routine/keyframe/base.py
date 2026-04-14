"""Keyframe Engine のレイヤー境界インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from daily_routine.schemas.asset import AssetSet
from daily_routine.schemas.keyframe_mapping import KeyframeMapping
from daily_routine.schemas.scenario import Scenario
from daily_routine.schemas.storyboard import Storyboard


class KeyframeEngineBase(ABC):
    """Keyframe Engine のレイヤー境界インターフェース."""

    @abstractmethod
    async def generate_keyframes(
        self,
        scenario: Scenario,
        storyboard: Storyboard,
        assets: AssetSet,
        output_dir: Path,
        keyframe_mapping: KeyframeMapping | None = None,
        project_dir: Path | None = None,
    ) -> AssetSet:
        """全カットのキーフレーム画像を生成する.

        Args:
            scenario: シナリオ
            storyboard: 絵コンテ（カット単位の情報を含む）
            assets: アセットセット（characters, environments を参照）
            output_dir: キーフレーム画像の出力ディレクトリ
            keyframe_mapping: キーフレームマッピング（任意）
            project_dir: プロジェクトディレクトリ（パス解決に使用）

        Returns:
            keyframes が追加された AssetSet
        """
        ...
