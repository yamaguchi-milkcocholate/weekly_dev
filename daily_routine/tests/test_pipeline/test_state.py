"""pipeline/state.py のテスト."""

import pytest

from daily_routine.pipeline.state import initialize_state, load_state, save_state
from daily_routine.schemas.project import (
    CheckpointStatus,
    PipelineStep,
)


class TestInitializeState:
    """initialize_state のテスト."""

    def test_全ステップPENDINGで初期化(self) -> None:
        state = initialize_state("test-project")
        assert state.project_id == "test-project"
        assert state.completed is False
        assert state.current_step is None
        for step in PipelineStep:
            assert step in state.steps
            assert state.steps[step].status == CheckpointStatus.PENDING


class TestSaveAndLoadState:
    """save_state / load_state のテスト."""

    def test_往復変換(self, tmp_path) -> None:
        state = initialize_state("roundtrip-test")
        state.current_step = PipelineStep.INTELLIGENCE
        state.steps[PipelineStep.INTELLIGENCE].status = CheckpointStatus.RUNNING

        save_state(tmp_path, state)
        loaded = load_state(tmp_path)

        assert loaded.project_id == state.project_id
        assert loaded.current_step == PipelineStep.INTELLIGENCE
        assert loaded.steps[PipelineStep.INTELLIGENCE].status == CheckpointStatus.RUNNING
        assert loaded.completed is False
        # 全ステップが保持されている
        for step in PipelineStep:
            assert step in loaded.steps

    def test_ERROR状態とretry_countの往復(self, tmp_path) -> None:
        state = initialize_state("error-test")
        state.steps[PipelineStep.ASSET].status = CheckpointStatus.ERROR
        state.steps[PipelineStep.ASSET].error = "API呼び出し失敗"
        state.steps[PipelineStep.ASSET].retry_count = 3

        save_state(tmp_path, state)
        loaded = load_state(tmp_path)

        assert loaded.steps[PipelineStep.ASSET].status == CheckpointStatus.ERROR
        assert loaded.steps[PipelineStep.ASSET].error == "API呼び出し失敗"
        assert loaded.steps[PipelineStep.ASSET].retry_count == 3


class TestInitializeStateWithStepOrder:
    """initialize_state の step_order 指定テスト."""

    def test_step_order指定_指定ステップのみ初期化(self) -> None:
        step_order = [PipelineStep.ASSET, PipelineStep.KEYFRAME, PipelineStep.VISUAL, PipelineStep.AUDIO]
        state = initialize_state("production-project", step_order=step_order)

        assert state.project_id == "production-project"
        assert list(state.steps.keys()) == step_order
        for step in step_order:
            assert state.steps[step].status == CheckpointStatus.PENDING
        # プランニングステップは含まれない
        assert PipelineStep.INTELLIGENCE not in state.steps
        assert PipelineStep.SCENARIO not in state.steps
        assert PipelineStep.STORYBOARD not in state.steps

    def test_step_order_None_全ステップ初期化(self) -> None:
        state = initialize_state("full-project", step_order=None)

        for step in PipelineStep:
            assert step in state.steps

    def test_step_order_プランニングのみ(self) -> None:
        step_order = [PipelineStep.INTELLIGENCE, PipelineStep.SCENARIO, PipelineStep.STORYBOARD]
        state = initialize_state("planning-project", step_order=step_order)

        assert list(state.steps.keys()) == step_order
        assert PipelineStep.ASSET not in state.steps


class TestLoadState:
    """load_state のテスト."""

    def test_ファイル未存在_FileNotFoundError(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError, match="state.yaml"):
            load_state(tmp_path)
