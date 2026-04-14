"""Post-Production入出力のスキーマ."""

from pathlib import Path

from pydantic import BaseModel, Field


class CaptionStyle(BaseModel):
    """テロップスタイル."""

    font: str
    color: str
    background_color: str | None = None
    animation: str | None = None
    position: str = Field(description="表示位置（top, center, bottom等）")


class CaptionEntry(BaseModel):
    """テロップエントリ."""

    text: str
    start_time_ms: int
    end_time_ms: int
    style: CaptionStyle


class FinalOutput(BaseModel):
    """Post-Productionの出力."""

    video_path: Path
    duration_sec: float
    resolution: str = "1080x1920"
    fps: int
    captions: list[CaptionEntry]
