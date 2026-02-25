"""Keyframe Engine のレイヤー境界インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from daily_routine.schemas.asset import AssetSet
from daily_routine.schemas.storyboard import Storyboard


class KeyframeEngineBase(ABC):
    """Keyframe Engine のレイヤー境界インターフェース."""

    @abstractmethod
    async def generate_keyframes(
        self,
        storyboard: Storyboard,
        assets: AssetSet,
        output_dir: Path,
    ) -> AssetSet:
        """全カットのキーフレーム画像を生成する.

        Args:
            storyboard: 絵コンテ（カット単位の keyframe_prompt を含む）
            assets: アセットセット（characters[0].front_view を参照画像として使用）
            output_dir: キーフレーム画像の出力ディレクトリ

        Returns:
            keyframes が追加された AssetSet
        """
        ...
