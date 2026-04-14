"""パイプライン複合入力型.

各ステップが必要とする入力データを定義する。
単一ステップの出力をそのまま受け取るステップ（Scenario, Asset）は
前ステップの出力型をそのまま使うため、ここでは定義しない。
"""

from pydantic import BaseModel, Field

from daily_routine.intelligence.base import SeedVideo
from daily_routine.schemas.audio import AudioAsset
from daily_routine.schemas.intelligence import AudioTrend
from daily_routine.schemas.keyframe_mapping import KeyframeMapping
from daily_routine.schemas.scenario import Scenario
from daily_routine.schemas.storyboard import Storyboard
from daily_routine.schemas.visual import VideoClipSet


class IntelligenceInput(BaseModel):
    """Intelligence Engine のパイプライン入力."""

    keyword: str
    seed_videos: list[SeedVideo] = Field(default_factory=list)


class StoryboardInput(BaseModel):
    """Storyboard Engine のパイプライン入力."""

    scenario: Scenario


class KeyframeInput(BaseModel):
    """Keyframe Engine のパイプライン入力（複合）."""

    scenario: Scenario
    storyboard: Storyboard
    assets: "AssetSet"
    keyframe_mapping: KeyframeMapping | None = None


class VisualInput(BaseModel):
    """Visual Core のパイプライン入力（複合）."""

    scenario: Scenario
    storyboard: Storyboard
    assets: "AssetSet"


class AudioInput(BaseModel):
    """Audio Engine のパイプライン入力（複合）."""

    audio_trend: AudioTrend
    scenario: Scenario


class PostProductionInput(BaseModel):
    """Post-Production のパイプライン入力（複合）."""

    scenario: Scenario
    storyboard: Storyboard
    video_clips: VideoClipSet
    audio_asset: AudioAsset


# 遅延インポートの解決
from daily_routine.schemas.asset import AssetSet  # noqa: E402

KeyframeInput.model_rebuild()
VisualInput.model_rebuild()
