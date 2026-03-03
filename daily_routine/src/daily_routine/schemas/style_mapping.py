"""スタイル参照画像のマッピングスキーマ.

非推奨: このモジュールは Runway Gen-4 Image 方式で使用していたもの。
Gemini C3-I1 方式への移行に伴い、schemas/keyframe_mapping.py に置き換え。
プロダクションコードからの参照は全て削除済み。テスト互換のため残置。
"""

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
