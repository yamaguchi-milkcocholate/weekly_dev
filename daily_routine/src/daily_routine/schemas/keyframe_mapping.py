"""キーフレームマッピングスキーマ."""

from pathlib import Path

from pydantic import BaseModel, Field


class SceneKeyframeSpec(BaseModel):
    """1シーンのキーフレーム生成仕様."""

    scene_number: int
    character: str = ""
    variant_id: str = Field(default="", description="衣装バリアントID（空=デフォルトバリアント）")
    environment: str = ""
    pose: str = ""
    reference_image: Path | None = None
    reference_text: str = ""


class KeyframeMapping(BaseModel):
    """シーンごとのキーフレーム生成マッピング."""

    scenes: list[SceneKeyframeSpec] = Field(default_factory=list)

    def get_spec(self, scene_number: int) -> SceneKeyframeSpec | None:
        """指定シーンのキーフレーム仕様を返す。未指定なら None."""
        for spec in self.scenes:
            if spec.scene_number == scene_number:
                return spec
        return None
