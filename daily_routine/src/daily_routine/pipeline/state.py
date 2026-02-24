"""パイプライン状態の永続化."""

import logging
from pathlib import Path

import yaml

from daily_routine.schemas.project import (
    PipelineState,
    PipelineStep,
    StepState,
)

logger = logging.getLogger(__name__)

_STATE_FILE = "state.yaml"


def initialize_state(project_id: str) -> PipelineState:
    """初期状態のPipelineStateを生成する.

    全ステップをPENDINGで初期化する。

    Args:
        project_id: プロジェクトID

    Returns:
        初期化されたPipelineState
    """
    steps = {step: StepState() for step in PipelineStep}
    return PipelineState(project_id=project_id, steps=steps)


def load_state(project_dir: Path) -> PipelineState:
    """プロジェクトディレクトリからstate.yamlを読み込む.

    Args:
        project_dir: プロジェクトデータディレクトリ

    Returns:
        読み込んだPipelineState

    Raises:
        FileNotFoundError: state.yamlが存在しない場合
    """
    state_path = project_dir / _STATE_FILE
    if not state_path.exists():
        msg = f"state.yamlが見つかりません: {state_path}"
        raise FileNotFoundError(msg)

    data = yaml.safe_load(state_path.read_text(encoding="utf-8"))
    return PipelineState(**data)


def save_state(project_dir: Path, state: PipelineState) -> None:
    """PipelineStateをstate.yamlに書き込む.

    updated_atを現在時刻に更新してから保存する。

    Args:
        project_dir: プロジェクトデータディレクトリ
        state: 保存するPipelineState
    """
    from datetime import datetime

    state.updated_at = datetime.now()

    state_path = project_dir / _STATE_FILE
    state_path.parent.mkdir(parents=True, exist_ok=True)

    data = state.model_dump(mode="json")
    state_path.write_text(
        yaml.dump(data, allow_unicode=True, default_flow_style=False, sort_keys=False),
        encoding="utf-8",
    )
    logger.debug("状態を保存しました: %s", state_path)
