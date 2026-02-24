"""pipeline/registry.py のテスト."""

from pathlib import Path

import pytest

from daily_routine.pipeline.base import StepEngine
from daily_routine.pipeline.registry import (
    _registry,
    create_engine,
    get_registered_steps,
    register_engine,
)
from daily_routine.schemas.project import PipelineStep


class MockEngine(StepEngine[str, str]):
    """テスト用のモックエンジン."""

    def __init__(self, **kwargs: object) -> None:
        self.kwargs = kwargs

    async def execute(self, input_data: str, project_dir: Path) -> str:
        return f"output_of_{input_data}"

    def load_output(self, project_dir: Path) -> str:
        return (project_dir / "mock_output.txt").read_text()

    def save_output(self, project_dir: Path, output: str) -> None:
        (project_dir / "mock_output.txt").write_text(output)


@pytest.fixture(autouse=True)
def _clear_registry():
    """テスト間でレジストリをクリアする."""
    _registry.clear()
    yield
    _registry.clear()


class TestRegistry:
    """エンジンレジストリのテスト."""

    def test_register_and_create_engine_正常(self) -> None:
        register_engine(PipelineStep.INTELLIGENCE, MockEngine)
        engine = create_engine(PipelineStep.INTELLIGENCE)
        assert isinstance(engine, MockEngine)

    def test_create_engine_未登録_KeyError(self) -> None:
        with pytest.raises(KeyError, match="intelligence"):
            create_engine(PipelineStep.INTELLIGENCE)

    def test_create_engine_kwargsが渡される(self) -> None:
        register_engine(PipelineStep.INTELLIGENCE, MockEngine)
        engine = create_engine(PipelineStep.INTELLIGENCE, api_key="test-key", model="gpt-4")
        assert isinstance(engine, MockEngine)
        assert engine.kwargs == {"api_key": "test-key", "model": "gpt-4"}

    def test_create_engine_kwargs省略時は空(self) -> None:
        register_engine(PipelineStep.INTELLIGENCE, MockEngine)
        engine = create_engine(PipelineStep.INTELLIGENCE)
        assert isinstance(engine, MockEngine)
        assert engine.kwargs == {}

    def test_get_registered_steps_登録済み一覧(self) -> None:
        register_engine(PipelineStep.INTELLIGENCE, MockEngine)
        register_engine(PipelineStep.SCENARIO, MockEngine)
        steps = get_registered_steps()
        assert PipelineStep.INTELLIGENCE in steps
        assert PipelineStep.SCENARIO in steps
        assert len(steps) == 2
