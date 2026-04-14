"""Audio Engine入出力のスキーマ."""

from pathlib import Path

from pydantic import BaseModel, Field


class BGM(BaseModel):
    """BGM."""

    file_path: Path
    bpm: int
    genre: str
    duration_sec: float
    source: str = Field(description="生成元（AI名 or フリー素材ライブラリ名）")


class SoundEffect(BaseModel):
    """効果音."""

    name: str
    file_path: Path
    trigger_time_ms: int = Field(description="挿入タイミング（ミリ秒）")
    scene_number: int
    trigger_description: str = Field(description="トリガーとなる動作/物体")


class AudioAsset(BaseModel):
    """Audio Engineの出力."""

    bgm: BGM
    sound_effects: list[SoundEffect]
