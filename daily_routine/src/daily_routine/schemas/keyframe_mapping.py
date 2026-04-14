"""キーフレームマッピングスキーマ."""

from enum import StrEnum
from pathlib import Path
from typing import Annotated, Literal

from pydantic import BaseModel, Field


class ReferencePurpose(StrEnum):
    """参照画像の用途."""

    WEARING = "wearing"
    HOLDING = "holding"
    ATMOSPHERE = "atmosphere"
    BACKGROUND = "background"
    INTERACTION = "interaction"
    GENERAL = "general"
    SUBJECT = "subject"  # シーンの主体オブジェクト（キャラクター非依存）


class CharacterComponent(BaseModel):
    """キャラクターコンポーネント（AssetSet から front_view + identity_block を自動解決）."""

    type: Literal["character"] = "character"
    character: str = ""
    variant_id: str = Field(default="", description="衣装バリアントID（空=デフォルトバリアント）")


class ReferenceComponent(BaseModel):
    """参照コンポーネント（画像パス / テキストを直接指定）."""

    type: Literal["reference"] = "reference"
    image: Path | None = None
    text: str = ""
    purpose: ReferencePurpose = Field(default=ReferencePurpose.GENERAL, description="参照の用途")


SceneComponent = Annotated[
    CharacterComponent | ReferenceComponent,
    Field(discriminator="type"),
]


class SceneKeyframeSpec(BaseModel):
    """1シーンのキーフレーム生成仕様."""

    scene_number: int
    environment: str = ""
    pose: str = ""
    components: list[SceneComponent] = Field(default_factory=list)

    # --- 旧フィールド（後方互換、deprecated） ---
    character: str = ""
    variant_id: str = Field(default="", description="衣装バリアントID（空=デフォルトバリアント）")
    reference_image: Path | None = None
    reference_text: str = ""

    def model_post_init(self, __context: object) -> None:
        """旧フィールドから components への自動マイグレーション."""
        if self.components:
            return

        migrated: list[CharacterComponent | ReferenceComponent] = []
        if self.character:
            migrated.append(CharacterComponent(character=self.character, variant_id=self.variant_id))
        if self.reference_image or self.reference_text:
            migrated.append(ReferenceComponent(image=self.reference_image, text=self.reference_text))
        if migrated:
            self.components = migrated

    @property
    def character_components(self) -> list[CharacterComponent]:
        """キャラクターコンポーネント一覧."""
        return [c for c in self.components if isinstance(c, CharacterComponent)]

    @property
    def reference_components(self) -> list[ReferenceComponent]:
        """参照コンポーネント一覧."""
        return [c for c in self.components if isinstance(c, ReferenceComponent)]

    @property
    def primary_character(self) -> CharacterComponent | None:
        """主キャラクター（先頭の character コンポーネント）."""
        chars = self.character_components
        return chars[0] if chars else None


class KeyframeMapping(BaseModel):
    """シーンごとのキーフレーム生成マッピング."""

    scenes: list[SceneKeyframeSpec] = Field(default_factory=list)

    def get_spec(self, scene_number: int) -> SceneKeyframeSpec | None:
        """指定シーンのキーフレーム仕様を返す。未指定なら None."""
        for spec in self.scenes:
            if spec.scene_number == scene_number:
                return spec
        return None
