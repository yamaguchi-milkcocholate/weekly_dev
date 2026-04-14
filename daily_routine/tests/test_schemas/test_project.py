"""schemas/project.py のテスト."""

import json

import pytest
from pydantic import ValidationError

from daily_routine.schemas.project import (
    CheckpointStatus,
    PipelineState,
    PipelineStep,
    ProjectConfig,
    StepState,
)


class TestPipelineStep:
    """PipelineStep Enum のテスト."""

    def test_values(self) -> None:
        assert PipelineStep.INTELLIGENCE == "intelligence"
        assert PipelineStep.POST_PRODUCTION == "post_production"

    def test_serializes_as_string(self) -> None:
        assert json.loads(json.dumps(PipelineStep.AUDIO.value)) == "audio"


class TestStepState:
    """StepState のテスト."""

    def test_default_pending(self) -> None:
        state = StepState()
        assert state.status == CheckpointStatus.PENDING
        assert state.started_at is None

    def test_roundtrip_json(self) -> None:
        state = StepState(status=CheckpointStatus.RUNNING)
        data = state.model_dump(mode="json")
        restored = StepState(**data)
        assert restored.status == state.status


class TestPipelineState:
    """PipelineState のテスト."""

    def test_create_minimal(self) -> None:
        state = PipelineState(project_id="test-001")
        assert state.project_id == "test-001"
        assert state.current_step is None
        assert state.steps == {}

    def test_roundtrip_json(self) -> None:
        state = PipelineState(
            project_id="test-001",
            current_step=PipelineStep.SCENARIO,
            steps={PipelineStep.INTELLIGENCE: StepState(status=CheckpointStatus.APPROVED)},
        )
        data = state.model_dump(mode="json")
        restored = PipelineState(**data)
        assert restored.current_step == PipelineStep.SCENARIO
        assert restored.steps[PipelineStep.INTELLIGENCE].status == CheckpointStatus.APPROVED


class TestProjectConfig:
    """ProjectConfig のテスト."""

    def test_create_with_defaults(self) -> None:
        config = ProjectConfig(project_id="p-001", keyword="OLの一日")
        assert config.output_fps == 30
        assert config.output_duration_range == (30, 60)

    def test_roundtrip_json(self) -> None:
        config = ProjectConfig(project_id="p-001", keyword="OLの一日")
        data = config.model_dump(mode="json")
        restored = ProjectConfig(**data)
        assert restored.project_id == config.project_id
        assert restored.keyword == config.keyword

    def test_validation_error_missing_required(self) -> None:
        with pytest.raises(ValidationError):
            ProjectConfig()  # type: ignore[call-arg]
