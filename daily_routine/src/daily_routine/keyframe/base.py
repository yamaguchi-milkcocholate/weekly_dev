"""Keyframe Engine のレイヤー境界インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from daily_routine.schemas.asset import AssetSet
from daily_routine.schemas.storyboard import Storyboard
from daily_routine.schemas.style_mapping import StyleMapping


class KeyframeEngineBase(ABC):
    """Keyframe Engine のレイヤー境界インターフェース."""

    @abstractmethod
    async def generate_keyframes(
        self,
        storyboard: Storyboard,
        assets: AssetSet,
        output_dir: Path,
        style_mapping: StyleMapping | None = None,
        project_dir: Path | None = None,
    ) -> AssetSet:
        """全カットのキーフレーム画像を生成する.

        Args:
            storyboard: 絵コンテ（カット単位の keyframe_prompt を含む）
            assets: アセットセット（characters[0].front_view を参照画像として使用）
            output_dir: キーフレーム画像の出力ディレクトリ
            style_mapping: スタイル参照画像のマッピング（任意）
            project_dir: プロジェクトディレクトリ（パス解決に使用）

        Returns:
            keyframes が追加された AssetSet
        """
        ...
