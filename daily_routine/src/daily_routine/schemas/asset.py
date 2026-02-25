"""Asset Generator入出力のスキーマ."""

from pathlib import Path

from pydantic import BaseModel, Field


class CharacterAsset(BaseModel):
    """キャラクターアセット."""

    character_name: str
    front_view: Path = Field(description="正面画像パス")
    side_view: Path = Field(description="横向き画像パス")
    back_view: Path = Field(description="背面画像パス")
    expressions: dict[str, Path] = Field(
        default_factory=dict,
        description="表情バリエーション {表情名: 画像パス}",
    )


class PropAsset(BaseModel):
    """小物アセット."""

    name: str
    image_path: Path


class BackgroundAsset(BaseModel):
    """背景アセット."""

    scene_number: int
    description: str
    image_path: Path


class KeyframeAsset(BaseModel):
    """キーフレーム画像アセット."""

    scene_number: int = Field(description="シーン番号")
    image_path: Path = Field(description="キーフレーム画像ファイルパス")
    prompt: str = Field(description="生成に使用したプロンプト")


class AssetSet(BaseModel):
    """Asset Generatorの出力."""

    characters: list[CharacterAsset]
    props: list[PropAsset]
    backgrounds: list[BackgroundAsset]
    keyframes: list[KeyframeAsset] = Field(
        default_factory=list,
        description="各シーンのキーフレーム画像（Gen-4 Imageで生成）",
    )
