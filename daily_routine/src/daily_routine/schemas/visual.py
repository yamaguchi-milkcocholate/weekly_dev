"""Visual Core入出力のスキーマ."""

from pathlib import Path

from pydantic import BaseModel, Field


class VideoClip(BaseModel):
    """生成された動画クリップ."""

    scene_number: int
    clip_path: Path
    duration_sec: float
    quality_score: float | None = Field(
        default=None,
        description="品質スコア（0-1）、品質チェック後に設定",
    )


class VideoClipSet(BaseModel):
    """Visual Coreの出力."""

    clips: list[VideoClip]
