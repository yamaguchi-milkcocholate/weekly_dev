"""pipeline/runner.py のテスト."""

from pathlib import Path

import pytest

from daily_routine.intelligence.base import SeedVideo
from daily_routine.pipeline.base import StepEngine
from daily_routine.pipeline.exceptions import InvalidStateError
from daily_routine.pipeline.registry import _registry, register_engine
from daily_routine.pipeline.runner import (
    FULL_STEP_ORDER,
    PLANNING_STEP_ORDER,
    PRODUCTION_STEP_ORDER,
    STEP_ORDER,
    _build_input,
    _engine_kwargs,
    _get_next_step,
    _get_previous_step,
    _load_keyframe_mapping,
    resume_pipeline,
    retry_pipeline,
    run_pipeline,
    run_planning_pipeline,
    run_production_pipeline,
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

    def test_get_next_step_フルパイプライン(self) -> None:
        state = initialize_state("test")
        assert _get_next_step(PipelineStep.INTELLIGENCE, state) == PipelineStep.SCENARIO
        assert _get_next_step(PipelineStep.POST_PRODUCTION, state) is None

    def test_get_previous_step_フルパイプライン(self) -> None:
        state = initialize_state("test")
        assert _get_previous_step(PipelineStep.SCENARIO, state) == PipelineStep.INTELLIGENCE
        assert _get_previous_step(PipelineStep.INTELLIGENCE, state) is None

    def test_get_next_step_プロダクションのみ(self) -> None:
        state = initialize_state("test", step_order=PRODUCTION_STEP_ORDER)
        assert _get_next_step(PipelineStep.ASSET, state) == PipelineStep.KEYFRAME
        assert _get_next_step(PipelineStep.AUDIO, state) is None
        # フルパイプラインに含まれるがプロダクションには含まれないステップ
        assert _get_next_step(PipelineStep.INTELLIGENCE, state) is None

    def test_get_previous_step_プランニングのみ(self) -> None:
        state = initialize_state("test", step_order=PLANNING_STEP_ORDER)
        assert _get_previous_step(PipelineStep.SCENARIO, state) == PipelineStep.INTELLIGENCE
        assert _get_previous_step(PipelineStep.INTELLIGENCE, state) is None
        assert _get_previous_step(PipelineStep.STORYBOARD, state) == PipelineStep.SCENARIO


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


class TestRunProductionPipeline:
    """run_production_pipeline のテスト."""

    @pytest.mark.asyncio
    async def test_ASSETステップから開始(self, tmp_path) -> None:
        # scenario と storyboard の出力を配置（MockEngine の load_output が使われるので mock_output.txt を配置）
        (tmp_path / "mock_output.txt").write_text("mock_output")

        state = await run_production_pipeline(tmp_path, "prod-project")

        assert state.project_id == "prod-project"
        assert state.current_step == PipelineStep.ASSET
        assert state.steps[PipelineStep.ASSET].status == CheckpointStatus.AWAITING_REVIEW
        # プランニングステップは含まれない
        assert PipelineStep.INTELLIGENCE not in state.steps
        assert PipelineStep.SCENARIO not in state.steps
        assert PipelineStep.STORYBOARD not in state.steps
        # プロダクションステップのみ含まれる
        assert list(state.steps.keys()) == PRODUCTION_STEP_ORDER

    @pytest.mark.asyncio
    async def test_前提ファイル不足_InvalidStateError(self, tmp_path) -> None:
        # MockEngine の load_output はファイルが無くてもデフォルト値を返すため
        # _validate_production_prerequisites を直接テスト
        # FailingEngine を scenario に登録してファイル不在をシミュレート

        class _FileNotFoundEngine(MockEngine):
            def load_output(self, project_dir: Path) -> str:
                msg = "scenario.json が見つかりません"
                raise FileNotFoundError(msg)

        _registry.clear()
        register_engine(PipelineStep.SCENARIO, _FileNotFoundEngine)
        register_engine(PipelineStep.STORYBOARD, _FileNotFoundEngine)
        for step in PipelineStep:
            if step not in (PipelineStep.SCENARIO, PipelineStep.STORYBOARD):
                register_engine(step, MockEngine)

        with pytest.raises(InvalidStateError, match="scenario"):
            await run_production_pipeline(tmp_path, "prod-project")

    def test_resume_プロダクションステップ内の次ステップ導出(self, tmp_path) -> None:
        state = initialize_state("prod-project", step_order=PRODUCTION_STEP_ORDER)
        # プロダクションパイプラインで ASSET → KEYFRAME → VISUAL → AUDIO の順序が保持される
        assert _get_next_step(PipelineStep.ASSET, state) == PipelineStep.KEYFRAME
        assert _get_next_step(PipelineStep.KEYFRAME, state) == PipelineStep.VISUAL
        assert _get_next_step(PipelineStep.VISUAL, state) == PipelineStep.AUDIO
        assert _get_next_step(PipelineStep.AUDIO, state) is None
        # INTELLIGENCE は state に含まれないので None
        assert _get_next_step(PipelineStep.INTELLIGENCE, state) is None

    @pytest.mark.asyncio
    async def test_最終ステップ_プロダクション完了(self, tmp_path) -> None:
        # AUDIO を AWAITING_REVIEW にしたプロダクション状態を作成
        state = initialize_state("prod-project", step_order=PRODUCTION_STEP_ORDER)
        for step in PRODUCTION_STEP_ORDER[:-1]:
            state.steps[step].status = CheckpointStatus.APPROVED
        state.steps[PipelineStep.AUDIO].status = CheckpointStatus.AWAITING_REVIEW
        state.current_step = PipelineStep.AUDIO
        save_state(tmp_path, state)

        state = await resume_pipeline(tmp_path)

        assert state.completed is True
        assert state.steps[PipelineStep.AUDIO].status == CheckpointStatus.APPROVED


class TestRunPlanningPipeline:
    """run_planning_pipeline のテスト."""

    @pytest.mark.asyncio
    async def test_INTELLIGENCEステップから開始(self, tmp_path) -> None:
        state = await run_planning_pipeline(tmp_path, "plan-project", "OLの一日")

        assert state.project_id == "plan-project"
        assert state.current_step == PipelineStep.INTELLIGENCE
        assert state.steps[PipelineStep.INTELLIGENCE].status == CheckpointStatus.AWAITING_REVIEW
        # プロダクションステップは含まれない
        assert PipelineStep.ASSET not in state.steps
        assert PipelineStep.VISUAL not in state.steps
        # プランニングステップのみ含まれる
        assert list(state.steps.keys()) == PLANNING_STEP_ORDER

    @pytest.mark.asyncio
    async def test_seed_videos付きで実行(self, tmp_path) -> None:
        seeds = [SeedVideo(note="参考動画")]
        state = await run_planning_pipeline(tmp_path, "plan-project", "OLの一日", seed_videos=seeds)

        assert state.steps[PipelineStep.INTELLIGENCE].status == CheckpointStatus.AWAITING_REVIEW

    @pytest.mark.asyncio
    async def test_最終ステップ_プランニング完了(self, tmp_path) -> None:
        # STORYBOARD を AWAITING_REVIEW にしたプランニング状態を作成
        state = initialize_state("plan-project", step_order=PLANNING_STEP_ORDER)
        for step in PLANNING_STEP_ORDER[:-1]:
            state.steps[step].status = CheckpointStatus.APPROVED
        state.steps[PipelineStep.STORYBOARD].status = CheckpointStatus.AWAITING_REVIEW
        state.current_step = PipelineStep.STORYBOARD
        save_state(tmp_path, state)

        state = await resume_pipeline(tmp_path)

        assert state.completed is True
        assert state.steps[PipelineStep.STORYBOARD].status == CheckpointStatus.APPROVED


class TestDynamicStepOrder:
    """state ベースのステップ順序テスト."""

    def test_プロダクションパイプラインのステップ順序_INTELLIGENCEに飛ばない(self) -> None:
        """プロダクションパイプラインの state では ASSET の次は KEYFRAME になること."""
        state = initialize_state("prod-project", step_order=PRODUCTION_STEP_ORDER)

        # ASSET → KEYFRAME（INTELLIGENCE や SCENARIO には飛ばない）
        next_step = _get_next_step(PipelineStep.ASSET, state)
        assert next_step == PipelineStep.KEYFRAME
        assert PipelineStep.INTELLIGENCE not in state.steps

    @pytest.mark.asyncio
    async def test_プロダクションパイプラインの永続化と復元(self, tmp_path) -> None:
        """プロダクション state がYAML永続化を通じてステップ順序を維持すること."""
        state = initialize_state("prod-project", step_order=PRODUCTION_STEP_ORDER)
        state.steps[PipelineStep.ASSET].status = CheckpointStatus.AWAITING_REVIEW
        state.current_step = PipelineStep.ASSET
        save_state(tmp_path, state)

        from daily_routine.pipeline.state import load_state

        loaded = load_state(tmp_path)
        assert list(loaded.steps.keys()) == PRODUCTION_STEP_ORDER
        assert _get_next_step(PipelineStep.ASSET, loaded) == PipelineStep.KEYFRAME

    def test_step_order定数の整合性(self) -> None:
        assert STEP_ORDER == FULL_STEP_ORDER
        assert PLANNING_STEP_ORDER + PRODUCTION_STEP_ORDER == FULL_STEP_ORDER[:-1]  # POST_PRODUCTION除く
