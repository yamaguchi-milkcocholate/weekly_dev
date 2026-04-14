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
    _auto_generate_keyframe_mapping,
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
from daily_routine.schemas.asset import AssetSet, CharacterAsset, EnvironmentAsset
from daily_routine.schemas.project import (
    CheckpointStatus,
    PipelineStep,
)
from daily_routine.schemas.storyboard import (
    CutSpec,
    MotionIntensity,
    SceneStoryboard,
    Storyboard,
    Transition,
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


class MockItemEngine(StepEngine[object, str]):
    """アイテム対応のモックエンジン."""

    executed_items: list[str] = []

    def __init__(self, output_value: str = "mock_output", **_kwargs: object) -> None:
        self._output_value = output_value
        MockItemEngine.executed_items = []

    async def execute(self, input_data: object, project_dir: Path) -> str:
        return self._output_value

    def load_output(self, project_dir: Path) -> str:
        output_file = project_dir / "mock_output.txt"
        if output_file.exists():
            return output_file.read_text()
        return self._output_value

    def save_output(self, project_dir: Path, output: str) -> None:
        (project_dir / "mock_output.txt").write_text(output)

    @property
    def supports_items(self) -> bool:
        return True

    def list_items(self, input_data: object, project_dir: Path) -> list[str]:
        return ["item_a", "item_b", "item_c"]

    async def execute_item(self, item_id: str, input_data: object, project_dir: Path) -> None:
        MockItemEngine.executed_items.append(item_id)


class FailingItemEngine(StepEngine[object, str]):
    """アイテム実行でエラーを発生させるテスト用エンジン."""

    def __init__(self, **_kwargs: object) -> None:
        pass

    async def execute(self, input_data: object, project_dir: Path) -> str:
        return ""

    def load_output(self, project_dir: Path) -> str:
        return ""

    def save_output(self, project_dir: Path, output: str) -> None:
        pass

    @property
    def supports_items(self) -> bool:
        return True

    def list_items(self, input_data: object, project_dir: Path) -> list[str]:
        return ["item_a", "item_b"]

    async def execute_item(self, item_id: str, input_data: object, project_dir: Path) -> None:
        msg = "アイテム生成エラー"
        raise RuntimeError(msg)


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


class TestAutoGenerateKeyframeMapping:
    """_auto_generate_keyframe_mapping のテスト."""

    def _make_storyboard_and_assets(self, tmp_path: Path) -> tuple[Storyboard, AssetSet]:
        """has_character が True/False 混在するテストデータを作成."""
        front_view = tmp_path / "front.png"
        front_view.write_bytes(b"fake_image")

        storyboard = Storyboard(
            title="テスト動画",
            total_duration_sec=9.0,
            total_cuts=3,
            scenes=[
                SceneStoryboard(
                    scene_number=1,
                    scene_duration_sec=3.0,
                    cuts=[
                        CutSpec(
                            cut_id="scene_01_cut_01",
                            scene_number=1,
                            cut_number=1,
                            duration_sec=3.0,
                            motion_intensity=MotionIntensity.SUBTLE,
                            camera_work="slow zoom-in",
                            action_description="人物が立っている",
                            motion_prompt="@char stands",
                            keyframe_prompt="@char in a room",
                            transition=Transition.CUT,
                            has_character=True,
                        ),
                    ],
                ),
                SceneStoryboard(
                    scene_number=2,
                    scene_duration_sec=3.0,
                    cuts=[
                        CutSpec(
                            cut_id="scene_02_cut_01",
                            scene_number=2,
                            cut_number=1,
                            duration_sec=3.0,
                            motion_intensity=MotionIntensity.STATIC,
                            camera_work="static",
                            action_description="コーヒー豆のクローズアップ",
                            motion_prompt="Steam rises",
                            keyframe_prompt="Coffee beans close-up",
                            transition=Transition.CUT,
                            has_character=False,
                        ),
                    ],
                ),
                SceneStoryboard(
                    scene_number=3,
                    scene_duration_sec=3.0,
                    cuts=[
                        CutSpec(
                            cut_id="scene_03_cut_01",
                            scene_number=3,
                            cut_number=1,
                            duration_sec=3.0,
                            motion_intensity=MotionIntensity.MODERATE,
                            camera_work="pan",
                            action_description="人物がコーヒーを飲む",
                            motion_prompt="@char drinks coffee",
                            keyframe_prompt="@char drinking coffee",
                            transition=Transition.CUT,
                            has_character=True,
                        ),
                    ],
                ),
            ],
        )

        assets = AssetSet(
            characters=[
                CharacterAsset(
                    character_name="花子",
                    front_view=front_view,
                    identity_block="Young adult female",
                ),
            ],
        )
        return storyboard, assets

    def _setup_mock_engines(self, storyboard: Storyboard, assets: AssetSet) -> None:
        """Storyboard と AssetSet を返すモックエンジンを登録."""

        class _StoryboardEngine(MockEngine):
            def load_output(self, project_dir: Path) -> Storyboard:
                return storyboard

        class _AssetEngine(MockEngine):
            def load_output(self, project_dir: Path) -> AssetSet:
                return assets

        _registry.clear()
        for step in PipelineStep:
            register_engine(step, MockEngine)
        register_engine(PipelineStep.STORYBOARD, _StoryboardEngine)
        register_engine(PipelineStep.ASSET, _AssetEngine)

    def test_has_character_falseのシーンにCharacterComponentが含まれない(self, tmp_path: Path) -> None:
        """has_character=False のシーンでは components が空になること."""
        import yaml

        storyboard, assets = self._make_storyboard_and_assets(tmp_path)
        self._setup_mock_engines(storyboard, assets)

        _auto_generate_keyframe_mapping(tmp_path)

        mapping_path = tmp_path / "storyboard" / "keyframe_mapping.yaml"
        assert mapping_path.exists()
        data = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))

        # scene 2 は has_character=False → CharacterComponent なし
        scene2 = [s for s in data["scenes"] if s["scene_number"] == 2][0]
        assert scene2["components"] == []

    def test_has_character_trueのシーンにCharacterComponentが含まれる(self, tmp_path: Path) -> None:
        """has_character=True のシーンでは CharacterComponent が含まれること."""
        import yaml

        storyboard, assets = self._make_storyboard_and_assets(tmp_path)
        self._setup_mock_engines(storyboard, assets)

        _auto_generate_keyframe_mapping(tmp_path)

        mapping_path = tmp_path / "storyboard" / "keyframe_mapping.yaml"
        data = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))

        # scene 1 は has_character=True → CharacterComponent あり
        scene1 = [s for s in data["scenes"] if s["scene_number"] == 1][0]
        char_components = [c for c in scene1["components"] if c.get("type") == "character"]
        assert len(char_components) == 1
        assert char_components[0]["character"] == "花子"

        # scene 3 も has_character=True → CharacterComponent あり
        scene3 = [s for s in data["scenes"] if s["scene_number"] == 3][0]
        char_components = [c for c in scene3["components"] if c.get("type") == "character"]
        assert len(char_components) == 1


class TestItemStepExecution:
    """アイテム単位実行のテスト."""

    @pytest.mark.asyncio
    async def test_アイテム対応ステップ_最初のアイテム実行後に停止(self, tmp_path) -> None:
        """アイテム対応ステップが最初のアイテム実行後にAWAITING_REVIEWで停止すること."""
        _registry.clear()
        register_engine(PipelineStep.INTELLIGENCE, MockItemEngine)
        for step in list(PipelineStep)[1:]:
            register_engine(step, MockEngine)

        state = await run_pipeline(tmp_path, "test-project", "OLの一日")

        assert state.current_step == PipelineStep.INTELLIGENCE
        assert state.steps[PipelineStep.INTELLIGENCE].status == CheckpointStatus.AWAITING_REVIEW
        assert len(state.steps[PipelineStep.INTELLIGENCE].items) == 3
        assert state.steps[PipelineStep.INTELLIGENCE].items[0].status == CheckpointStatus.AWAITING_REVIEW
        assert state.steps[PipelineStep.INTELLIGENCE].items[0].item_id == "item_a"
        assert state.steps[PipelineStep.INTELLIGENCE].items[1].status == CheckpointStatus.PENDING
        assert state.steps[PipelineStep.INTELLIGENCE].current_item_id == "item_a"
        assert MockItemEngine.executed_items == ["item_a"]

    @pytest.mark.asyncio
    async def test_resume_次のアイテムへ進行(self, tmp_path) -> None:
        """resume で現在のアイテムを承認し、次のアイテムを実行すること."""
        _registry.clear()
        register_engine(PipelineStep.INTELLIGENCE, MockItemEngine)
        for step in list(PipelineStep)[1:]:
            register_engine(step, MockEngine)

        await run_pipeline(tmp_path, "test-project", "OLの一日")
        state = await resume_pipeline(tmp_path)

        step_state = state.steps[PipelineStep.INTELLIGENCE]
        assert step_state.items[0].status == CheckpointStatus.APPROVED
        assert step_state.items[1].status == CheckpointStatus.AWAITING_REVIEW
        assert step_state.items[2].status == CheckpointStatus.PENDING
        assert step_state.current_item_id == "item_b"
        assert "item_b" in MockItemEngine.executed_items

    @pytest.mark.asyncio
    async def test_全アイテム完了後_次のステップへ遷移(self, tmp_path) -> None:
        """全アイテム完了後に resume で次のステップへ遷移すること."""
        _registry.clear()
        register_engine(PipelineStep.INTELLIGENCE, MockItemEngine)
        for step in list(PipelineStep)[1:]:
            register_engine(step, MockEngine)

        await run_pipeline(tmp_path, "test-project", "OLの一日")

        # item_a → item_b → item_c → 次のステップ
        await resume_pipeline(tmp_path)  # item_b 実行
        await resume_pipeline(tmp_path)  # item_c 実行
        state = await resume_pipeline(tmp_path)  # 全アイテム完了 → SCENARIO

        assert state.steps[PipelineStep.INTELLIGENCE].status == CheckpointStatus.APPROVED
        assert state.current_step == PipelineStep.SCENARIO
        assert state.steps[PipelineStep.SCENARIO].status == CheckpointStatus.AWAITING_REVIEW

    @pytest.mark.asyncio
    async def test_アイテム実行エラー_ERROR状態(self, tmp_path) -> None:
        """アイテム実行でエラーが発生するとERROR状態になること."""
        _registry.clear()
        register_engine(PipelineStep.INTELLIGENCE, FailingItemEngine)
        for step in list(PipelineStep)[1:]:
            register_engine(step, MockEngine)

        state = await run_pipeline(tmp_path, "test-project", "OLの一日")

        step_state = state.steps[PipelineStep.INTELLIGENCE]
        assert step_state.status == CheckpointStatus.ERROR
        assert step_state.items[0].status == CheckpointStatus.ERROR
        assert step_state.items[0].error == "アイテム生成エラー"


class TestItemRetry:
    """アイテム単位リトライのテスト."""

    @pytest.mark.asyncio
    async def test_retry_item_個別アイテムリトライ(self, tmp_path) -> None:
        """retry --item でアイテム単位のリトライができること."""
        _registry.clear()
        register_engine(PipelineStep.INTELLIGENCE, MockItemEngine)
        for step in list(PipelineStep)[1:]:
            register_engine(step, MockEngine)

        await run_pipeline(tmp_path, "test-project", "OLの一日")

        # item_a が AWAITING_REVIEW の状態でリトライ
        state = await retry_pipeline(tmp_path, item_id="item_a")

        step_state = state.steps[PipelineStep.INTELLIGENCE]
        assert step_state.items[0].status == CheckpointStatus.AWAITING_REVIEW
        assert "item_a" in MockItemEngine.executed_items

    @pytest.mark.asyncio
    async def test_retry_item_存在しないアイテム_InvalidStateError(self, tmp_path) -> None:
        """存在しないアイテムIDでリトライするとエラーになること."""
        _registry.clear()
        register_engine(PipelineStep.INTELLIGENCE, MockItemEngine)
        for step in list(PipelineStep)[1:]:
            register_engine(step, MockEngine)

        await run_pipeline(tmp_path, "test-project", "OLの一日")

        with pytest.raises(InvalidStateError, match="見つかりません"):
            await retry_pipeline(tmp_path, item_id="nonexistent")

    @pytest.mark.asyncio
    async def test_retry_item_非アイテムステップ_InvalidStateError(self, tmp_path) -> None:
        """アイテム未対応ステップでアイテムリトライするとエラーになること."""
        await run_pipeline(tmp_path, "test-project", "OLの一日")

        with pytest.raises(InvalidStateError, match="アイテム単位実行ではありません"):
            await retry_pipeline(tmp_path, item_id="some_item")

    @pytest.mark.asyncio
    async def test_retry_item_PENDING状態のアイテム_InvalidStateError(self, tmp_path) -> None:
        """PENDING状態のアイテムをリトライしようとするとエラーになること."""
        _registry.clear()
        register_engine(PipelineStep.INTELLIGENCE, MockItemEngine)
        for step in list(PipelineStep)[1:]:
            register_engine(step, MockEngine)

        await run_pipeline(tmp_path, "test-project", "OLの一日")

        # item_b は PENDING 状態
        with pytest.raises(InvalidStateError, match="pending"):
            await retry_pipeline(tmp_path, item_id="item_b")


class TestAutoGenerateKeyframeMappingClothingVariant:
    """P1: clothing_variant ベースの variant_id 割り当てテスト."""

    def _make_data(
        self,
        tmp_path: Path,
        *,
        clothing_variants: list[str] | None = None,
        asset_variant_ids: list[str] | None = None,
    ) -> tuple[Storyboard, AssetSet]:
        """clothing_variant テスト用データを作成."""
        front_view = tmp_path / "front.png"
        front_view.write_bytes(b"fake_image")

        if clothing_variants is None:
            clothing_variants = ["home", "work", "work"]
        if asset_variant_ids is None:
            asset_variant_ids = ["home", "work"]

        storyboard_scenes = []
        for i, cv in enumerate(clothing_variants, start=1):
            storyboard_scenes.append(
                SceneStoryboard(
                    scene_number=i,
                    scene_duration_sec=3.0,
                    cuts=[
                        CutSpec(
                            cut_id=f"scene_{i:02d}_cut_01",
                            scene_number=i,
                            cut_number=1,
                            duration_sec=3.0,
                            motion_intensity=MotionIntensity.SUBTLE,
                            camera_work="static",
                            action_description="テスト",
                            motion_prompt="test",
                            keyframe_prompt="@char test",
                            transition=Transition.CUT,
                            has_character=True,
                            clothing_variant=cv,
                        ),
                    ],
                )
            )

        storyboard = Storyboard(
            title="テスト動画",
            total_duration_sec=3.0 * len(clothing_variants),
            total_cuts=len(clothing_variants),
            scenes=storyboard_scenes,
        )

        characters = [
            CharacterAsset(
                character_name="花子",
                variant_id=vid,
                front_view=front_view,
                identity_block="Young adult female",
            )
            for vid in asset_variant_ids
        ]

        assets = AssetSet(characters=characters)
        return storyboard, assets

    def _setup_engines(self, storyboard: Storyboard, assets: AssetSet) -> None:
        class _StoryboardEngine(MockEngine):
            def load_output(self, project_dir: Path) -> Storyboard:
                return storyboard

        class _AssetEngine(MockEngine):
            def load_output(self, project_dir: Path) -> AssetSet:
                return assets

        _registry.clear()
        for step in PipelineStep:
            register_engine(step, MockEngine)
        register_engine(PipelineStep.STORYBOARD, _StoryboardEngine)
        register_engine(PipelineStep.ASSET, _AssetEngine)

    def test_clothing_variantに基づくvariant_id割り当て(self, tmp_path: Path) -> None:
        """clothing_variant が asset の variant_id にマッチすること."""
        import yaml

        storyboard, assets = self._make_data(tmp_path)
        self._setup_engines(storyboard, assets)

        _auto_generate_keyframe_mapping(tmp_path)

        mapping_path = tmp_path / "storyboard" / "keyframe_mapping.yaml"
        data = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))

        scene1 = [s for s in data["scenes"] if s["scene_number"] == 1][0]
        scene2 = [s for s in data["scenes"] if s["scene_number"] == 2][0]
        scene3 = [s for s in data["scenes"] if s["scene_number"] == 3][0]

        assert scene1["components"][0]["variant_id"] == "home"
        assert scene2["components"][0]["variant_id"] == "work"
        assert scene3["components"][0]["variant_id"] == "work"

    def test_clothing_variant不一致_フォールバック警告(self, tmp_path: Path) -> None:
        """clothing_variant に一致する asset がない場合、最初のバリアントにフォールバックすること."""
        import yaml

        storyboard, assets = self._make_data(
            tmp_path,
            clothing_variants=["pajama"],
            asset_variant_ids=["home", "work"],
        )
        self._setup_engines(storyboard, assets)

        _auto_generate_keyframe_mapping(tmp_path)

        mapping_path = tmp_path / "storyboard" / "keyframe_mapping.yaml"
        data = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))

        scene1 = [s for s in data["scenes"] if s["scene_number"] == 1][0]
        # フォールバックで最初の asset の variant_id が使用される
        assert scene1["components"][0]["variant_id"] == "home"

    def test_clothing_variant未設定_default使用(self, tmp_path: Path) -> None:
        """clothing_variant が未設定（default）の場合の動作確認."""
        import yaml

        storyboard, assets = self._make_data(
            tmp_path,
            clothing_variants=["default"],
            asset_variant_ids=["default"],
        )
        self._setup_engines(storyboard, assets)

        _auto_generate_keyframe_mapping(tmp_path)

        mapping_path = tmp_path / "storyboard" / "keyframe_mapping.yaml"
        data = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))

        scene1 = [s for s in data["scenes"] if s["scene_number"] == 1][0]
        assert scene1["components"][0]["variant_id"] == "default"

    def test_複数バリアント_シーンごとに異なるvariant_id(self, tmp_path: Path) -> None:
        """シーンごとに異なる clothing_variant が正しく反映されること."""
        import yaml

        storyboard, assets = self._make_data(
            tmp_path,
            clothing_variants=["home", "work", "casual", "home"],
            asset_variant_ids=["home", "work", "casual"],
        )
        self._setup_engines(storyboard, assets)

        _auto_generate_keyframe_mapping(tmp_path)

        mapping_path = tmp_path / "storyboard" / "keyframe_mapping.yaml"
        data = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))

        variant_ids = [
            s["components"][0]["variant_id"] for s in sorted(data["scenes"], key=lambda x: x["scene_number"])
        ]
        assert variant_ids == ["home", "work", "casual", "home"]
