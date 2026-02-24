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


class TestLoadState:
    """load_state のテスト."""

    def test_ファイル未存在_FileNotFoundError(self, tmp_path) -> None:
        with pytest.raises(FileNotFoundError, match="state.yaml"):
            load_state(tmp_path)
