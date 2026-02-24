"""Asset Generator レイヤーの抽象インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from daily_routine.schemas.asset import AssetSet, BackgroundAsset, CharacterAsset, PropAsset
from daily_routine.schemas.scenario import CharacterSpec, PropSpec, SceneSpec


class AssetGenerator(ABC):
    """Asset Generator レイヤーの抽象インターフェース."""

    @abstractmethod
    async def generate_assets(
        self,
        characters: list[CharacterSpec],
        props: list[PropSpec],
        scenes: list[SceneSpec],
        output_dir: Path,
        user_reference_images: dict[str, Path] | None = None,
    ) -> AssetSet:
        """シナリオ仕様に基づき全アセットを生成する.

        Args:
            characters: キャラクター仕様リスト
            props: 小物仕様リスト（名前・説明・画像生成プロンプトを含む）
            scenes: シーン仕様リスト
            output_dir: 出力ディレクトリ
            user_reference_images: ユーザー指定の参照画像 {キャラクター名: 画像パス}
        """
        ...

    @abstractmethod
    async def generate_character(
        self,
        character: CharacterSpec,
        output_dir: Path,
        reference_image: Path | None = None,
    ) -> CharacterAsset:
        """1キャラクターのリファレンス画像セットを生成する.

        Args:
            character: キャラクター仕様
            output_dir: 出力ディレクトリ
            reference_image: ユーザー指定の参照画像（省略時はプロンプトのみで生成）
        """
        ...

    @abstractmethod
    async def generate_prop(
        self,
        name: str,
        description: str,
        output_dir: Path,
    ) -> PropAsset:
        """小物の画像を生成する."""
        ...

    @abstractmethod
    async def generate_background(
        self,
        scene: SceneSpec,
        output_dir: Path,
    ) -> BackgroundAsset:
        """シーンの背景画像を生成する."""
        ...
