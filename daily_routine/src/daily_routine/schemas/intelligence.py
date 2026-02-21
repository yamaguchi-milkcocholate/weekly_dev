"""Intelligence Engine入出力のスキーマ."""

from pydantic import BaseModel, Field


class SceneStructure(BaseModel):
    """シーン構成の分析結果."""

    total_scenes: int
    avg_scene_duration_sec: float
    hook_techniques: list[str] = Field(description="冒頭フック手法")
    transition_patterns: list[str] = Field(description="シーン遷移パターン")


class CaptionTrend(BaseModel):
    """テロップトレンド."""

    font_styles: list[str]
    color_schemes: list[str]
    animation_types: list[str]
    positions: list[str]
    emphasis_techniques: list[str]


class VisualTrend(BaseModel):
    """映像トレンド."""

    situations: list[str] = Field(description="シチュエーション一覧")
    props: list[str] = Field(description="登場小物")
    camera_works: list[str] = Field(description="カメラワーク")
    color_tones: list[str] = Field(description="色調・フィルタ")


class AudioTrend(BaseModel):
    """音響トレンド."""

    bpm_range: tuple[int, int]
    genres: list[str]
    volume_patterns: list[str]
    se_usage_points: list[str] = Field(description="SE使用箇所")


class AssetRequirement(BaseModel):
    """素材要件."""

    characters: list[str] = Field(description="必要なキャラクター")
    props: list[str] = Field(description="必要な小物")
    backgrounds: list[str] = Field(description="必要な背景")


class TrendReport(BaseModel):
    """Intelligence Engineの出力: トレンド分析レポート."""

    keyword: str
    analyzed_video_count: int
    scene_structure: SceneStructure
    caption_trend: CaptionTrend
    visual_trend: VisualTrend
    audio_trend: AudioTrend
    asset_requirements: AssetRequirement
