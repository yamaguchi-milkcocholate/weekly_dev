"""Visual Core レイヤーの抽象インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from daily_routine.schemas.asset import AssetSet
from daily_routine.schemas.storyboard import Storyboard
from daily_routine.schemas.visual import VideoClipSet


class VisualEngine(ABC):
    """Visual Core レイヤーの抽象インターフェース."""

    @abstractmethod
    async def generate_clips(
        self,
        storyboard: Storyboard,
        assets: AssetSet,
        output_dir: Path,
    ) -> VideoClipSet:
        """絵コンテとアセットに基づき全カットの動画クリップを生成する.

        Args:
            storyboard: 絵コンテ（カット単位の motion_prompt を含む）
            assets: Asset Generator の出力（リファレンス画像セット）
            output_dir: 動画クリップの出力ディレクトリ
        """
        ...

    @abstractmethod
    async def generate_cut_clip(
        self,
        cut_id: str,
        prompt: str,
        reference_image: Path,
        duration_sec: int,
        output_path: Path,
    ) -> Path:
        """単一カットの動画クリップを生成する.

        Args:
            cut_id: カットID
            prompt: 動画生成プロンプト
            reference_image: リファレンス画像パス
            duration_sec: 動画の尺（秒）
            output_path: 動画ファイルの保存先パス
        """
        ...
