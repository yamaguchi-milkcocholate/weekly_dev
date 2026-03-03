"""DefaultVisualEngine のモックテスト."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from daily_routine.config.manager import ApiKeys, GlobalConfig, RunwayConfig, VisualConfig
from daily_routine.schemas.asset import AssetSet, CharacterAsset, KeyframeAsset
from daily_routine.schemas.scenario import CameraWork, CharacterSpec, Scenario, SceneSpec
from daily_routine.schemas.storyboard import (
    CutSpec,
    MotionIntensity,
    SceneStoryboard,
    Storyboard,
    Transition,
)
from daily_routine.schemas.visual import VideoClip, VideoClipSet
from daily_routine.visual.clients.base import VideoGenerationRequest, VideoGenerationResult
from daily_routine.visual.engine import DefaultVisualEngine, create_visual_engine


@pytest.fixture
def sample_scenario() -> Scenario:
    """テスト用Scenario."""
    return Scenario(
        title="テスト動画",
        total_duration_sec=24.0,
        characters=[
            CharacterSpec(
                name="Aoi",
                appearance="20代女性",
                outfit="白ブラウス",
                reference_prompt="A young Japanese woman",
            )
        ],
        scenes=[
            SceneSpec(
                scene_number=1,
                duration_sec=8.0,
                situation="朝、玄関を出る",
                camera_work=CameraWork(type="wide", description="全身ショット"),
                caption_text="AM 7:30 出勤",
                image_prompt="Modern apartment entrance",
            ),
            SceneSpec(
                scene_number=2,
                duration_sec=8.0,
                situation="カフェでコーヒーを飲む",
                camera_work=CameraWork(type="close-up", description="クローズアップ"),
                caption_text="毎朝のルーティン",
                image_prompt="Cafe interior",
            ),
            SceneSpec(
                scene_number=3,
                duration_sec=8.0,
                situation="オフィスで作業",
                camera_work=CameraWork(type="POV", description="POVショット"),
                caption_text="今日も頑張る",
                image_prompt="Office desk",
            ),
        ],
        bgm_direction="明るいポップス",
    )


@pytest.fixture
def sample_storyboard() -> Storyboard:
    """テスト用Storyboard."""
    return Storyboard(
        title="テスト動画",
        total_duration_sec=24.0,
        total_cuts=6,
        scenes=[
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=8.0,
                cuts=[
                    CutSpec(
                        cut_id="scene_01_cut_01",
                        scene_number=1,
                        cut_number=1,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.MODERATE,
                        camera_work="wide shot, static",
                        action_description="玄関を出る",
                        motion_prompt="She opens the door and steps out",
                        keyframe_prompt="@char at apartment entrance",
                    ),
                    CutSpec(
                        cut_id="scene_01_cut_02",
                        scene_number=1,
                        cut_number=2,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.DYNAMIC,
                        camera_work="medium shot, slow zoom-in",
                        action_description="歩き出す",
                        motion_prompt="She walks forward",
                        keyframe_prompt="@char walks on street",
                    ),
                ],
            ),
            SceneStoryboard(
                scene_number=2,
                scene_duration_sec=8.0,
                cuts=[
                    CutSpec(
                        cut_id="scene_02_cut_01",
                        scene_number=2,
                        cut_number=1,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.SUBTLE,
                        camera_work="close-up, static",
                        action_description="コーヒーに手を伸ばす",
                        motion_prompt="She reaches for a coffee cup",
                        keyframe_prompt="@char at cafe counter",
                        transition=Transition.CROSS_FADE,
                    ),
                    CutSpec(
                        cut_id="scene_02_cut_02",
                        scene_number=2,
                        cut_number=2,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.SUBTLE,
                        camera_work="close-up, dolly in",
                        action_description="コーヒーを飲む",
                        motion_prompt="She takes a sip of coffee",
                        keyframe_prompt="@char sips coffee",
                    ),
                ],
            ),
            SceneStoryboard(
                scene_number=3,
                scene_duration_sec=8.0,
                cuts=[
                    CutSpec(
                        cut_id="scene_03_cut_01",
                        scene_number=3,
                        cut_number=1,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.MODERATE,
                        camera_work="POV, static",
                        action_description="PCを開く",
                        motion_prompt="She opens the laptop",
                        keyframe_prompt="@char at office desk",
                        transition=Transition.CROSS_FADE,
                    ),
                    CutSpec(
                        cut_id="scene_03_cut_02",
                        scene_number=3,
                        cut_number=2,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.MODERATE,
                        camera_work="POV, slow zoom-in",
                        action_description="タイピング",
                        motion_prompt="She types on the keyboard",
                        keyframe_prompt="@char types on laptop",
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def sample_assets(tmp_path: Path) -> AssetSet:
    """テスト用AssetSet（実ファイルあり、キーフレーム含む）."""
    char_dir = tmp_path / "assets" / "character" / "Aoi"
    char_dir.mkdir(parents=True)
    front = char_dir / "front.png"
    side = char_dir / "side.png"
    back = char_dir / "back.png"
    for p in [front, side, back]:
        p.write_bytes(b"fake-png")

    # キーフレーム画像を作成（シーン番号単位で1枚ずつ — 同一シーン内のカットは同じキーフレームを参照）
    kf_dir = tmp_path / "assets" / "keyframes"
    kf_dir.mkdir(parents=True)
    kf1 = kf_dir / "scene_01.png"
    kf2 = kf_dir / "scene_02.png"
    kf3 = kf_dir / "scene_03.png"
    for p in [kf1, kf2, kf3]:
        p.write_bytes(b"fake-keyframe")

    return AssetSet(
        characters=[
            CharacterAsset(
                character_name="Aoi",
                front_view=front,
                side_view=side,
                back_view=back,
            )
        ],
        keyframes=[
            KeyframeAsset(
                scene_number=1, image_path=kf1, prompt="@char at apartment entrance", cut_id="scene_01_cut_01"
            ),
            KeyframeAsset(scene_number=2, image_path=kf2, prompt="@char at cafe counter", cut_id="scene_02_cut_01"),
            KeyframeAsset(scene_number=3, image_path=kf3, prompt="@char at office desk", cut_id="scene_03_cut_01"),
        ],
    )


def _make_mock_result(cut_index: int, output_path: Path) -> VideoGenerationResult:
    """モックのVideoGenerationResultを作成する."""
    return VideoGenerationResult(
        video_path=output_path,
        generation_time_sec=75.0 + cut_index,
        model_name="gen4_turbo",
        cost_usd=0.5,
    )


class TestGenerateClips:
    """DefaultVisualEngine.generate_clips のテスト."""

    @pytest.mark.asyncio
    async def test_generate_clips_全カット動画生成(
        self, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """Storyboard の全カットに対してクライアントが呼び出される."""
        output_dir = tmp_path / "clips"
        mock_client = AsyncMock()

        async def mock_generate(request: VideoGenerationRequest, output_path: Path) -> VideoGenerationResult:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-video")
            return _make_mock_result(1, output_path)

        mock_client.generate.side_effect = mock_generate

        engine = DefaultVisualEngine.from_components(client=mock_client, provider_name="runway")
        result = await engine.generate_clips(sample_storyboard, sample_assets, output_dir)

        assert mock_client.generate.await_count == 6
        assert len(result.clips) == 6

    @pytest.mark.asyncio
    async def test_generate_clips_出力VideoClipSetの構造(
        self, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """clips のサイズ、各 VideoClip のフィールド."""
        output_dir = tmp_path / "clips"
        mock_client = AsyncMock()

        cut_idx = 0

        async def mock_generate(request: VideoGenerationRequest, output_path: Path) -> VideoGenerationResult:
            nonlocal cut_idx
            cut_idx += 1
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-video")
            return _make_mock_result(cut_idx, output_path)

        mock_client.generate.side_effect = mock_generate

        engine = DefaultVisualEngine.from_components(client=mock_client, provider_name="runway")
        result = await engine.generate_clips(sample_storyboard, sample_assets, output_dir)

        assert len(result.clips) == 6
        for clip in result.clips:
            assert clip.model_name == "gen4_turbo"
            assert clip.duration_sec == 4.0
            assert clip.cost_usd == 0.5
            assert clip.generation_time_sec is not None

    @pytest.mark.asyncio
    async def test_generate_clips_コスト集計(
        self, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """total_cost_usd がクリップのコスト合計と一致."""
        output_dir = tmp_path / "clips"
        mock_client = AsyncMock()

        async def mock_generate(request: VideoGenerationRequest, output_path: Path) -> VideoGenerationResult:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-video")
            return _make_mock_result(1, output_path)

        mock_client.generate.side_effect = mock_generate

        engine = DefaultVisualEngine.from_components(client=mock_client, provider_name="runway")
        result = await engine.generate_clips(sample_storyboard, sample_assets, output_dir)

        expected_cost = sum(c.cost_usd for c in result.clips if c.cost_usd is not None)
        assert result.total_cost_usd == expected_cost
        assert result.total_cost_usd == 3.0  # 6 cuts * $0.50

    @pytest.mark.asyncio
    async def test_generate_clips_プロバイダ名設定(
        self, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """VideoClipSet.provider が正しく設定される."""
        output_dir = tmp_path / "clips"
        mock_client = AsyncMock()

        async def mock_generate(request: VideoGenerationRequest, output_path: Path) -> VideoGenerationResult:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-video")
            return _make_mock_result(1, output_path)

        mock_client.generate.side_effect = mock_generate

        engine = DefaultVisualEngine.from_components(client=mock_client, provider_name="runway")
        result = await engine.generate_clips(sample_storyboard, sample_assets, output_dir)

        assert result.provider == "runway"


class TestGenerateCutClip:
    """DefaultVisualEngine.generate_cut_clip のテスト."""

    @pytest.mark.asyncio
    async def test_generate_cut_clip_リファレンス画像不在_FileNotFoundError(self, tmp_path: Path) -> None:
        """存在しない画像パスでエラー."""
        mock_client = AsyncMock()
        engine = DefaultVisualEngine.from_components(client=mock_client, provider_name="runway")

        nonexistent = tmp_path / "nonexistent.png"
        output_path = tmp_path / "clips" / "scene_01_cut_01.mp4"

        with pytest.raises(FileNotFoundError, match="リファレンス画像が存在しません"):
            await engine.generate_cut_clip(
                cut_id="scene_01_cut_01",
                prompt="test prompt",
                reference_image=nonexistent,
                duration_sec=3,
                output_path=output_path,
            )


class TestCreateVisualEngine:
    """create_visual_engine のテスト."""

    def test_create_visual_engine_runwayプロバイダ(self) -> None:
        """設定 provider: 'runway' で RunwayClient が使用される."""
        config = GlobalConfig(
            api_keys=ApiKeys(runway="test-key"),
            visual=VisualConfig(
                provider="runway",
                runway=RunwayConfig(video_model="gen4_turbo", gcs_bucket="test-bucket"),
            ),
        )

        engine = create_visual_engine(config)

        assert isinstance(engine, DefaultVisualEngine)
        assert engine._provider_name == "runway"

    def test_create_visual_engine_不明プロバイダ_ValueError(self) -> None:
        """不明な provider でエラー."""
        config = GlobalConfig(
            api_keys=ApiKeys(runway="test-key"),
            visual=VisualConfig(provider="unknown"),
        )

        with pytest.raises(ValueError, match="不明な動画生成プロバイダ"):
            create_visual_engine(config)

    def test_create_visual_engine_APIキー未設定_ValueError(self) -> None:
        """APIキー未設定でエラー."""
        config = GlobalConfig(
            visual=VisualConfig(
                provider="runway",
                runway=RunwayConfig(gcs_bucket="test-bucket"),
            ),
        )

        with pytest.raises(ValueError, match="APIキー"):
            create_visual_engine(config)

    def test_create_visual_engine_GCSバケット未設定_ValueError(self) -> None:
        """GCSバケット未設定でエラー."""
        config = GlobalConfig(
            api_keys=ApiKeys(runway="test-key"),
            visual=VisualConfig(
                provider="runway",
                runway=RunwayConfig(gcs_bucket=""),
            ),
        )

        with pytest.raises(ValueError, match="GCSバケット"):
            create_visual_engine(config)


class TestVisualEngineExecute:
    """DefaultVisualEngine.execute のテスト."""

    @pytest.mark.asyncio
    async def test_execute_VisualInput経由(
        self, sample_scenario: Scenario, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """execute が generate_clips を呼び、save_output で保存する."""
        from daily_routine.schemas.pipeline_io import VisualInput

        mock_client = AsyncMock()

        async def mock_generate(request: VideoGenerationRequest, output_path: Path) -> VideoGenerationResult:
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-video")
            return _make_mock_result(1, output_path)

        mock_client.generate.side_effect = mock_generate

        engine = DefaultVisualEngine.from_components(client=mock_client, provider_name="runway")
        input_data = VisualInput(scenario=sample_scenario, storyboard=sample_storyboard, assets=sample_assets)
        result = await engine.execute(input_data, tmp_path)

        assert isinstance(result, VideoClipSet)
        assert len(result.clips) == 6


class TestVisualEnginePersistence:
    """DefaultVisualEngine の永続化テスト."""

    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        """save_output → load_output のラウンドトリップ."""
        engine = DefaultVisualEngine()

        clip_set = VideoClipSet(
            clips=[
                VideoClip(
                    scene_number=1,
                    clip_path=Path("clips/scene_01_cut_01.mp4"),
                    duration_sec=3.0,
                    model_name="gen4_turbo",
                    cost_usd=0.15,
                    generation_time_sec=75.0,
                ),
                VideoClip(
                    scene_number=1,
                    clip_path=Path("clips/scene_01_cut_02.mp4"),
                    duration_sec=3.0,
                    model_name="gen4_turbo",
                    cost_usd=0.15,
                    generation_time_sec=76.0,
                ),
            ],
            total_cost_usd=0.30,
            provider="runway",
        )

        engine.save_output(tmp_path, clip_set)
        loaded = engine.load_output(tmp_path)

        assert len(loaded.clips) == 2
        assert loaded.clips[0].scene_number == 1
        assert loaded.clips[0].clip_path == Path("clips/scene_01_cut_01.mp4")
        assert loaded.total_cost_usd == 0.30
        assert loaded.provider == "runway"

    def test_load_output_ファイル未存在_FileNotFoundError(self, tmp_path: Path) -> None:
        """保存ファイルがない場合エラー."""
        engine = DefaultVisualEngine()

        with pytest.raises(FileNotFoundError, match="VideoClipSet"):
            engine.load_output(tmp_path)
