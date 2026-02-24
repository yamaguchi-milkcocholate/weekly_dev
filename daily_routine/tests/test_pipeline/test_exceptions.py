"""pipeline/exceptions.py のテスト."""

from daily_routine.pipeline.exceptions import (
    InvalidStateError,
    PipelineError,
    StepExecutionError,
)
from daily_routine.schemas.project import PipelineStep


class TestStepExecutionError:
    """StepExecutionError のテスト."""

    def test_メッセージにステップ名を含む(self) -> None:
        err = StepExecutionError(PipelineStep.INTELLIGENCE, "API呼び出し失敗")
        assert "intelligence" in str(err)
        assert "API呼び出し失敗" in str(err)

    def test_cause保持(self) -> None:
        cause = ValueError("元のエラー")
        err = StepExecutionError(PipelineStep.SCENARIO, "変換エラー", cause=cause)
        assert err.cause is cause
        assert err.step == PipelineStep.SCENARIO

    def test_PipelineErrorのサブクラス(self) -> None:
        err = StepExecutionError(PipelineStep.ASSET, "テスト")
        assert isinstance(err, PipelineError)


class TestInvalidStateError:
    """InvalidStateError のテスト."""

    def test_メッセージ(self) -> None:
        err = InvalidStateError("不正な状態遷移です")
        assert str(err) == "不正な状態遷移です"

    def test_PipelineErrorのサブクラス(self) -> None:
        err = InvalidStateError("テスト")
        assert isinstance(err, PipelineError)
