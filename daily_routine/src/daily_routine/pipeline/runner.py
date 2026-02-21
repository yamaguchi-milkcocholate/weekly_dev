"""パイプライン実行制御（骨格）."""

import logging

from daily_routine.config.manager import GlobalConfig
from daily_routine.schemas.project import PipelineState, PipelineStep, ProjectConfig

logger = logging.getLogger(__name__)

# パイプラインのステップ実行順序
STEP_ORDER: list[PipelineStep] = [
    PipelineStep.INTELLIGENCE,
    PipelineStep.SCENARIO,
    PipelineStep.ASSET,
    PipelineStep.VISUAL,
    PipelineStep.AUDIO,
    PipelineStep.POST_PRODUCTION,
]


async def run_pipeline(
    global_config: GlobalConfig,
    project_config: ProjectConfig,
    start_step: PipelineStep | None = None,
) -> PipelineState:
    """パイプラインを実行する.

    Args:
        global_config: グローバル設定
        project_config: プロジェクト設定
        start_step: 開始ステップ（省略時は最初から）

    Returns:
        パイプラインの実行状態
    """
    state = PipelineState(project_id=project_config.project_id)

    steps = STEP_ORDER
    if start_step is not None:
        idx = steps.index(start_step)
        steps = steps[idx:]

    for step in steps:
        logger.info("ステップ %s は未実装です（Phase 1 で実装予定）", step.value)

    return state
