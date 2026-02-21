"""プロジェクト設定・メタデータのスキーマ."""

from datetime import datetime
from enum import Enum
from pydantic import BaseModel, Field


class PipelineStep(str, Enum):
    """パイプラインのステップ."""

    INTELLIGENCE = "intelligence"
    SCENARIO = "scenario"
    ASSET = "asset"
    VISUAL = "visual"
    AUDIO = "audio"
    POST_PRODUCTION = "post_production"


class CheckpointStatus(str, Enum):
    """チェックポイントのステータス."""

    PENDING = "pending"
    RUNNING = "running"
    AWAITING_REVIEW = "awaiting_review"
    APPROVED = "approved"
    REJECTED = "rejected"


class StepState(BaseModel):
    """各ステップの実行状態."""

    status: CheckpointStatus = CheckpointStatus.PENDING
    started_at: datetime | None = None
    completed_at: datetime | None = None
    error: str | None = None


class PipelineState(BaseModel):
    """パイプライン全体の実行状態."""

    project_id: str
    current_step: PipelineStep | None = None
    steps: dict[PipelineStep, StepState] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)


class ProjectConfig(BaseModel):
    """プロジェクト設定."""

    project_id: str
    keyword: str = Field(description="検索キーワード（例：「OLの一日」）")
    output_fps: int = Field(default=30, description="出力フレームレート")
    output_duration_range: tuple[int, int] = Field(
        default=(30, 60),
        description="出力動画尺の範囲（秒）",
    )
    created_at: datetime = Field(default_factory=datetime.now)
