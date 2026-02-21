"""Scenario Engine入出力のスキーマ."""

from pydantic import BaseModel, Field


class CameraWork(BaseModel):
    """カメラワーク指定."""

    type: str = Field(description="POV, close-up, wide等")
    description: str


class SceneSpec(BaseModel):
    """シーン仕様."""

    scene_number: int
    duration_sec: float
    situation: str = Field(description="状況説明")
    camera_work: CameraWork
    caption_text: str = Field(description="テロップテキスト")
    image_prompt: str = Field(description="Asset Generator用の画像生成プロンプト")
    video_prompt: str = Field(description="Visual Core用の動画生成プロンプト")


class CharacterSpec(BaseModel):
    """キャラクター仕様."""

    name: str
    appearance: str = Field(description="外見の詳細説明")
    outfit: str = Field(description="服装の詳細説明")
    reference_prompt: str = Field(description="リファレンス画像生成用プロンプト")


class Scenario(BaseModel):
    """Scenario Engineの出力."""

    title: str
    total_duration_sec: float
    characters: list[CharacterSpec]
    scenes: list[SceneSpec]
    bgm_direction: str = Field(description="BGMの方向性指示")
