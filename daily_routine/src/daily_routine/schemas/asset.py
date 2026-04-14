"""Asset Generator入出力のスキーマ."""

from pathlib import Path

from pydantic import BaseModel, Field


class ClothingReferenceSpec(BaseModel):
    """衣装バリアント別の参照画像."""

    label: str = Field(description="衣装ラベル（例: 'pajama', 'suit', 'casual'）")
    clothing: str | None = Field(default=None, description="服装画像ファイル名（clothing/ 相対パス）")


class CharacterReferenceSpec(BaseModel):
    """キャラクター参照画像のマッピング."""

    name: str = Field(description="キャラクター名")
    person: str | None = Field(default=None, description="人物画像ファイル名（person/ 相対パス）")
    clothing: str | None = Field(default=None, description="服装画像ファイル名（clothing/ 相対パス）")
    clothing_variants: list[ClothingReferenceSpec] = Field(
        default_factory=list,
        description="衣装バリアント別の参照画像",
    )


class ReferenceMapping(BaseModel):
    """参照画像マッピング設定."""

    characters: list[CharacterReferenceSpec] = Field(default_factory=list)


class CharacterAsset(BaseModel):
    """キャラクターアセット."""

    character_name: str
    variant_id: str = Field(default="default", description="衣装バリアントID")
    front_view: Path = Field(description="正面画像パス")
    identity_block: str = Field(default="", description="Identity Block テキスト（C1-ID 出力）")


class EnvironmentAsset(BaseModel):
    """環境アセット（C2 出力）."""

    scene_number: int
    description: str = Field(default="", description="環境の説明（マッピング照合用）")
    image_path: Path
    source_type: str = Field(default="generated")  # reference/generated/text_fallback


class KeyframeAsset(BaseModel):
    """キーフレーム画像アセット."""

    scene_number: int = Field(description="シーン番号")
    image_path: Path = Field(description="キーフレーム画像ファイルパス")
    prompt: str = Field(description="生成に使用したプロンプト")
    cut_id: str = Field(default="", description="カットID")
    generation_method: str = Field(default="gemini", description="生成方式")


class EnvironmentSeedSpec(BaseModel):
    """環境シード仕様."""

    scene_number: int
    source: str = Field(description="生成ソース: 'reference' or 'generate'")
    reference_image: str = Field(default="", description="参照画像ファイル名（source=referenceの時必須）")
    modification: str = Field(default="", description="C2-R2-MOD 修正指示（source=referenceの時のみ有効）")
    description: str = Field(default="", description="環境の説明（keyframe_mapping照合用）")


class EnvironmentSeeds(BaseModel):
    """環境シード定義."""

    environments: list[EnvironmentSeedSpec] = Field(default_factory=list)


class AssetSet(BaseModel):
    """Asset Generatorの出力."""

    characters: list[CharacterAsset]
    environments: list[EnvironmentAsset] = Field(
        default_factory=list,
        description="環境アセット（C2 出力）",
    )
    keyframes: list[KeyframeAsset] = Field(
        default_factory=list,
        description="各シーンのキーフレーム画像",
    )
