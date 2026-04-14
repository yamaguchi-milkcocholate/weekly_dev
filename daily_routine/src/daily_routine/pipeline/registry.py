"""エンジンレジストリ.

PipelineStep と StepEngine の対応を管理する。
各レイヤーの実装が追加された際に、ここに登録する。
"""

import logging

from daily_routine.pipeline.base import StepEngine
from daily_routine.schemas.project import PipelineStep

logger = logging.getLogger(__name__)

_registry: dict[PipelineStep, type[StepEngine]] = {}


def register_engine(step: PipelineStep, engine_class: type[StepEngine]) -> None:
    """ステップにエンジンクラスを登録する.

    Args:
        step: パイプラインステップ
        engine_class: StepEngineのサブクラス
    """
    _registry[step] = engine_class
    logger.debug("エンジンを登録しました: %s -> %s", step.value, engine_class.__name__)


def create_engine(step: PipelineStep, **kwargs: object) -> StepEngine:
    """登録済みのエンジンクラスからインスタンスを生成する.

    Args:
        step: パイプラインステップ
        **kwargs: エンジンクラスのコンストラクタに渡すキーワード引数

    Returns:
        StepEngineのインスタンス

    Raises:
        KeyError: 未登録のステップが指定された場合
    """
    if step not in _registry:
        msg = f"ステップ '{step.value}' のエンジンが未登録です"
        raise KeyError(msg)
    return _registry[step](**kwargs)


def get_registered_steps() -> list[PipelineStep]:
    """登録済みステップの一覧を取得する."""
    return list(_registry.keys())
