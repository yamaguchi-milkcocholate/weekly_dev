"""Asset Generator レイヤーの抽象インターフェース."""

from abc import ABC, abstractmethod
from pathlib import Path

from daily_routine.schemas.asset import AssetSet, CharacterAsset
from daily_routine.schemas.scenario import CharacterSpec, SceneSpec


class AssetGenerator(ABC):
    """Asset Generator レイヤーの抽象インターフェース."""

    @abstractmethod
    async def generate_assets(
        self,
        characters: list[CharacterSpec],
        scenes: list[SceneSpec],
        output_dir: Path,
        user_reference_images: dict[str, Path] | None = None,
        person_images: dict[str, Path] | None = None,
        clothing_images: dict[str, Path] | None = None,
    ) -> AssetSet:
        """シナリオ仕様に基づき全アセットを生成する.

        Args:
            characters: キャラクター仕様リスト
            scenes: シーン仕様リスト
            output_dir: 出力ディレクトリ
            user_reference_images: ユーザー指定の参照画像 {キャラクター名: 画像パス}
            person_images: 人物参照画像 {キャラクター名: 画像パス}
            clothing_images: 服装参照画像 {キャラクター名: 画像パス}
        """
        ...

    @abstractmethod
    async def generate_character(
        self,
        character: CharacterSpec,
        output_dir: Path,
        reference_image: Path | None = None,
        person_image: Path | None = None,
        clothing_image: Path | None = None,
        variant_id: str = "default",
    ) -> CharacterAsset:
        """1キャラクターのリファレンス画像セットを生成する.

        Args:
            character: キャラクター仕様
            output_dir: 出力ディレクトリ
            reference_image: ユーザー指定の参照画像（省略時はプロンプトのみで生成）
            person_image: 人物参照画像（C1-F2-MA 用）
            clothing_image: 服装参照画像（C1-F2-MA 用）
            variant_id: 衣装バリアントID
        """
        ...
