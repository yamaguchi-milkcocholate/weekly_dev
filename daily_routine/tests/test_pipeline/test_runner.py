"""pipeline/runner.py のテスト."""

from pathlib import Path

import pytest

from daily_routine.intelligence.base import SeedVideo
from daily_routine.pipeline.base import StepEngine
from daily_routine.pipeline.exceptions import InvalidStateError
from daily_routine.pipeline.registry import _registry, register_engine
from daily_routine.pipeline.runner import (
    STEP_ORDER,
    _build_input,
    _engine_kwargs,
    _get_next_step,
    _get_previous_step,
    _load_keyframe_mapping,
    resume_pipeline,
    retry_pipeline,
    run_pipeline,
)
from daily_routine.pipeline.state import initialize_state, save_state
from daily_routine.schemas.project import (
    CheckpointStatus,
    PipelineStep,
)


class MockEngine(StepEngine[object, str]):
    """テスト用のモックエンジン."""

    def __init__(self, output_value: str = "mock_output", **_kwargs: object) -> None:
        self._output_value = output_value

    async def execute(self, input_data: object, project_dir: Path) -> str:
        return self._output_value

    def load_output(self, project_dir: Path) -> str:
        output_file = project_dir / "mock_output.txt"
        if output_file.exists():
            return output_file.read_text()
        return self._output_value

    def save_output(self, project_dir: Path, output: str) -> None:
        (project_dir / "mock_output.txt").write_text(output)


class FailingEngine(StepEngine[object, str]):
    """エラーを発生させるテスト用エンジン."""

    def __init__(self, **_kwargs: object) -> None:
        pass

    async def execute(self, input_data: object, project_dir: Path) -> str:
        msg = "意図的なエラー"
        raise RuntimeError(msg)

    def load_output(self, project_dir: Path) -> str:
        return ""

    def save_output(self, project_dir: Path, output: str) -> None:
        pass


class _MockEngineFactory:
    """register_engineにクラスとして渡すためのファクトリ."""

    _output_value = "mock_output"

    def __init__(self, **_kwargs: object) -> None:
        self._engine = MockEngine(self._output_value)

    async def execute(self, input_data, project_dir):
        return await self._engine.execute(input_data, project_dir)

    def load_output(self, project_dir):
        return self._engine.load_output(project_dir)

    def save_output(self, project_dir, output):
        self._engine.save_output(project_dir, output)


@pytest.fixture(autouse=True)
def _setup_registry():
    """テスト用にモックエンジンを全ステップに登録する."""
    _registry.clear()
    for step in PipelineStep:
        register_engine(step, MockEngine)
    yield
    _registry.clear()


class TestRunPipeline:
    """run_pipeline のテスト."""

    @pytest.mark.asyncio
    async def test_最初のステップ実行後に停止(self, tmp_path) -> None:
        state = await run_pipeline(tmp_path, "test-project", "OLの一日")

        assert state.project_id == "test-project"
        assert state.current_step == PipelineStep.INTELLIGENCE
        assert state.steps[PipelineStep.INTELLIGENCE].status == CheckpointStatus.AWAITING_REVIEW

        # 他のステップはPENDINGのまま
        for step in STEP_ORDER[1:]:
            assert state.steps[step].status == CheckpointStatus.PENDING

    @pytest.mark.asyncio
    async def test_seed_videos付きで実行(self, tmp_path) -> None:
        seeds = [
            SeedVideo(note="テスト動画"),
        ]
        state = await run_pipeline(tmp_path, "test-project", "OLの一日", seed_videos=seeds)

        assert state.project_id == "test-project"
        assert state.steps[PipelineStep.INTELLIGENCE].status == CheckpointStatus.AWAITING_REVIEW


class TestBuildInput:
    """_build_input のテスト."""

    def test_intelligence_seed_videosが渡される(self, tmp_path) -> None:
        seeds = [
            SeedVideo(note="参考動画"),
        ]
        result = _build_input(PipelineStep.INTELLIGENCE, tmp_path, keyword="テスト", seed_videos=seeds)
        assert result.keyword == "テスト"
        assert len(result.seed_videos) == 1
        assert result.seed_videos[0].note == "参考動画"

    def test_intelligence_seed_videos省略時は空(self, tmp_path) -> None:
        result = _build_input(PipelineStep.INTELLIGENCE, tmp_path, keyword="テスト")
        assert result.seed_videos == []

    def test_intelligence_seed_videosがNone_空リスト(self, tmp_path) -> None:
        result = _build_input(PipelineStep.INTELLIGENCE, tmp_path, keyword="テスト", seed_videos=None)
        assert result.seed_videos == []


class TestResumePipeline:
    """resume_pipeline のテスト."""

    @pytest.mark.asyncio
    async def test_次ステップへ進行(self, tmp_path) -> None:
        # 最初のステップを実行済みにする
        await run_pipeline(tmp_path, "test-project", "OLの一日")

        # resume: intelligence → approved, scenario → awaiting_review
        state = await resume_pipeline(tmp_path)

        assert state.steps[PipelineStep.INTELLIGENCE].status == CheckpointStatus.APPROVED
        assert state.steps[PipelineStep.SCENARIO].status == CheckpointStatus.AWAITING_REVIEW
        assert state.current_step == PipelineStep.SCENARIO

    @pytest.mark.asyncio
    async def test_最終ステップ_パイプライン完了(self, tmp_path) -> None:
        # 全ステップを AWAITING_REVIEW まで進める
        state = initialize_state("test-project")
        for step in STEP_ORDER:
            state.steps[step].status = CheckpointStatus.APPROVED
        # 最終ステップだけ AWAITING_REVIEW にする
        last_step = STEP_ORDER[-1]
        state.steps[last_step].status = CheckpointStatus.AWAITING_REVIEW
        state.current_step = last_step
        save_state(tmp_path, state)

        state = await resume_pipeline(tmp_path)

        assert state.completed is True
        assert state.steps[last_step].status == CheckpointStatus.APPROVED

    @pytest.mark.asyncio
    async def test_不正な状態_InvalidStateError(self, tmp_path) -> None:
        # PENDINGの状態で resume しようとする
        state = initialize_state("test-project")
        state.current_step = PipelineStep.INTELLIGENCE
        save_state(tmp_path, state)

        with pytest.raises(InvalidStateError, match="AWAITING_REVIEW"):
            await resume_pipeline(tmp_path)

    @pytest.mark.asyncio
    async def test_完了済みパイプラインへのresume_InvalidStateError(self, tmp_path) -> None:
        state = initialize_state("test-project")
        state.completed = True
        save_state(tmp_path, state)

        with pytest.raises(InvalidStateError, match="完了"):
            await resume_pipeline(tmp_path)


class TestRetryPipeline:
    """retry_pipeline のテスト."""

    @pytest.mark.asyncio
    async def test_エラーステップを再実行(self, tmp_path) -> None:
        # ERROR状態を作る
        state = initialize_state("test-project")
        state.current_step = PipelineStep.SCENARIO
        state.steps[PipelineStep.SCENARIO].status = CheckpointStatus.ERROR
        state.steps[PipelineStep.SCENARIO].error = "API失敗"
        save_state(tmp_path, state)

        state = await retry_pipeline(tmp_path)

        assert state.steps[PipelineStep.SCENARIO].status == CheckpointStatus.AWAITING_REVIEW
        assert state.steps[PipelineStep.SCENARIO].retry_count == 1
        assert state.steps[PipelineStep.SCENARIO].error is None

    @pytest.mark.asyncio
    async def test_不正な状態_InvalidStateError(self, tmp_path) -> None:
        # AWAITING_REVIEW状態で retry しようとする
        state = initialize_state("test-project")
        state.current_step = PipelineStep.INTELLIGENCE
        state.steps[PipelineStep.INTELLIGENCE].status = CheckpointStatus.AWAITING_REVIEW
        save_state(tmp_path, state)

        with pytest.raises(InvalidStateError, match="ERROR"):
            await retry_pipeline(tmp_path)


class TestExecuteStepError:
    """_execute_step のエラーハンドリングテスト."""

    @pytest.mark.asyncio
    async def test_エラー発生_ERROR状態に遷移(self, tmp_path) -> None:
        _registry.clear()
        register_engine(PipelineStep.INTELLIGENCE, FailingEngine)
        for step in list(PipelineStep)[1:]:
            register_engine(step, MockEngine)

        state = await run_pipeline(tmp_path, "test-project", "OLの一日")

        assert state.steps[PipelineStep.INTELLIGENCE].status == CheckpointStatus.ERROR
        assert state.steps[PipelineStep.INTELLIGENCE].error == "意図的なエラー"


class TestHelpers:
    """ヘルパー関数のテスト."""

    def test_get_next_step(self) -> None:
        assert _get_next_step(PipelineStep.INTELLIGENCE) == PipelineStep.SCENARIO
        assert _get_next_step(PipelineStep.POST_PRODUCTION) is None

    def test_get_previous_step(self) -> None:
        assert _get_previous_step(PipelineStep.SCENARIO) == PipelineStep.INTELLIGENCE
        assert _get_previous_step(PipelineStep.INTELLIGENCE) is None


class TestEngineKwargs:
    """_engine_kwargs のテスト."""

    def test_intelligence_APIキーが渡される(self) -> None:
        api_keys = {
            "google_ai": "gai-key",
        }
        result = _engine_kwargs(PipelineStep.INTELLIGENCE, api_keys)
        assert result == {
            "google_ai_api_key": "gai-key",
        }

    def test_intelligence_キー未設定_空文字(self) -> None:
        result = _engine_kwargs(PipelineStep.INTELLIGENCE, {})
        assert result == {
            "google_ai_api_key": "",
        }

    def test_api_keysがNoneの場合_空dict(self) -> None:
        result = _engine_kwargs(PipelineStep.INTELLIGENCE, None)
        assert result == {}

    def test_scenarioステップ_openai_api_key(self) -> None:
        api_keys = {"openai": "oai-key"}
        result = _engine_kwargs(PipelineStep.SCENARIO, api_keys)
        assert result == {"api_key": "oai-key"}

    def test_assetステップ_google_ai_api_key(self) -> None:
        api_keys = {"google_ai": "gai-key"}
        result = _engine_kwargs(PipelineStep.ASSET, api_keys)
        assert result == {"api_key": "gai-key"}

    def test_keyframeステップ_google_ai_api_key(self) -> None:
        api_keys = {"google_ai": "gai-key"}
        result = _engine_kwargs(PipelineStep.KEYFRAME, api_keys)
        assert result == {"api_key": "gai-key"}

    def test_visualステップ_runway_api_key(self) -> None:
        api_keys = {"runway": "rw-key", "gcs_bucket": "my-bucket", "video_model": "gen4_turbo"}
        result = _engine_kwargs(PipelineStep.VISUAL, api_keys)
        assert result == {"api_key": "rw-key", "gcs_bucket": "my-bucket", "video_model": "gen4_turbo"}

    def test_他のステップ_空dict(self) -> None:
        api_keys = {"youtube_data_api": "yt-key"}
        result = _engine_kwargs(PipelineStep.POST_PRODUCTION, api_keys)
        assert result == {}


class TestLoadKeyframeMapping:
    """_load_keyframe_mapping のテスト."""

    def test_ファイルが存在しない_None(self, tmp_path: Path) -> None:
        result = _load_keyframe_mapping(tmp_path)
        assert result is None

    def test_ファイルが存在する_KeyframeMapping返却(self, tmp_path: Path) -> None:
        storyboard_dir = tmp_path / "storyboard"
        storyboard_dir.mkdir()
        mapping_file = storyboard_dir / "keyframe_mapping.yaml"
        mapping_file.write_text(
            "scenes:\n"
            "  - scene_number: 1\n"
            '    character: "Aoi"\n'
            '    pose: "standing"\n'
            "  - scene_number: 3\n"
            '    character: "Aoi"\n'
            '    reference_text: "cafe atmosphere"\n',
            encoding="utf-8",
        )

        result = _load_keyframe_mapping(tmp_path)
        assert result is not None
        assert len(result.scenes) == 2
        spec1 = result.get_spec(1)
        assert spec1 is not None
        assert spec1.pose == "standing"
        spec3 = result.get_spec(3)
        assert spec3 is not None
        assert spec3.reference_text == "cafe atmosphere"
        assert result.get_spec(2) is None

    def test_空マッピング_空リスト(self, tmp_path: Path) -> None:
        storyboard_dir = tmp_path / "storyboard"
        storyboard_dir.mkdir()
        mapping_file = storyboard_dir / "keyframe_mapping.yaml"
        mapping_file.write_text("scenes: []\n", encoding="utf-8")

        result = _load_keyframe_mapping(tmp_path)
        assert result is not None
        assert len(result.scenes) == 0
