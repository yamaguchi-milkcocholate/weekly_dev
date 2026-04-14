"""パイプライン固有の例外定義."""

from daily_routine.schemas.project import PipelineStep


class PipelineError(Exception):
    """パイプライン関連エラーの基底クラス."""


class StepExecutionError(PipelineError):
    """ステップ実行中のエラー.

    外部API呼び出し失敗、データ変換エラー等をラップする。
    """

    def __init__(self, step: PipelineStep, message: str, cause: Exception | None = None) -> None:
        self.step = step
        self.cause = cause
        super().__init__(f"ステップ '{step.value}' でエラー: {message}")


class InvalidStateError(PipelineError):
    """不正な状態遷移エラー.

    例: PENDING状態のステップに対するretry、完了済みパイプラインへのresume等。
    """

    def __init__(self, message: str) -> None:
        super().__init__(message)
