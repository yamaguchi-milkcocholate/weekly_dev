"""スタイル参照画像のマッピングスキーマ."""

from pathlib import Path

from pydantic import BaseModel, Field


class SceneStyleReference(BaseModel):
    """1シーンのスタイル参照画像."""

    scene_number: int = Field(description="シーン番号")
    reference: Path = Field(description="参照画像のパス")


class StyleMapping(BaseModel):
    """スタイル参照画像のマッピング."""

    mappings: list[SceneStyleReference] = Field(
        default_factory=list,
        description="シーン番号と参照画像のマッピング",
    )

    def get_reference(self, scene_number: int) -> Path | None:
        """指定シーンの参照画像パスを返す。未指定なら None."""
        for m in self.mappings:
            if m.scene_number == scene_number:
                return m.reference
        return None
