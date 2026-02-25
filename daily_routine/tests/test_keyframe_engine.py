"""RunwayKeyframeEngine のモックテスト."""

from pathlib import Path
from unittest.mock import AsyncMock

import pytest

from daily_routine.keyframe.engine import RunwayKeyframeEngine
from daily_routine.schemas.asset import AssetSet, BackgroundAsset, CharacterAsset, KeyframeAsset, PropAsset
from daily_routine.schemas.pipeline_io import KeyframeInput
from daily_routine.schemas.scenario import CameraWork, CharacterSpec, Scenario, SceneSpec
from daily_routine.schemas.storyboard import (
    CutSpec,
    MotionIntensity,
    SceneStoryboard,
    Storyboard,
    Transition,
)
from daily_routine.visual.clients.gen4_image import ImageGenerationResult, RunwayImageClient


@pytest.fixture
def sample_scenario() -> Scenario:
    """テスト用Scenario."""
    return Scenario(
        title="テスト動画",
        total_duration_sec=16.0,
        characters=[
            CharacterSpec(
                name="Aoi",
                appearance="20代女性",
                outfit="白ブラウス",
                reference_prompt="A young Japanese woman",
            )
        ],
        props=[],
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
        ],
        bgm_direction="明るいポップス",
    )


@pytest.fixture
def sample_storyboard() -> Storyboard:
    """テスト用Storyboard."""
    return Storyboard(
        title="テスト動画",
        total_duration_sec=16.0,
        total_cuts=4,
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
                        action_description="玄関のドアを開ける",
                        motion_prompt="She opens the door and steps out",
                        keyframe_prompt="@char walks out of a modern apartment entrance, morning light",
                        transition=Transition.FADE_IN,
                    ),
                    CutSpec(
                        cut_id="scene_01_cut_02",
                        scene_number=1,
                        cut_number=2,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.DYNAMIC,
                        camera_work="medium shot, slow zoom-in",
                        action_description="歩き出す",
                        motion_prompt="She walks forward confidently",
                        keyframe_prompt="@char walks on a residential street, morning sunlight",
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
                        action_description="コーヒーカップに手を伸ばす",
                        motion_prompt="She reaches for a coffee cup",
                        keyframe_prompt="@char sits at a cafe counter with a coffee cup",
                        transition=Transition.CROSS_FADE,
                    ),
                    CutSpec(
                        cut_id="scene_02_cut_02",
                        scene_number=2,
                        cut_number=2,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.SUBTLE,
                        camera_work="close-up, slow dolly in",
                        action_description="コーヒーを飲む",
                        motion_prompt="She picks up the cup and takes a sip",
                        keyframe_prompt="@char sips coffee at a cafe counter",
                    ),
                ],
            ),
        ],
    )


@pytest.fixture
def sample_assets(tmp_path: Path) -> AssetSet:
    """テスト用AssetSet."""
    char_dir = tmp_path / "assets" / "character" / "Aoi"
    char_dir.mkdir(parents=True)
    front = char_dir / "front.png"
    front.write_bytes(b"fake-png")

    return AssetSet(
        characters=[
            CharacterAsset(
                character_name="Aoi",
                front_view=front,
                side_view=char_dir / "side.png",
                back_view=char_dir / "back.png",
            )
        ],
        props=[],
        backgrounds=[],
    )


def _make_mock_image_result(output_path: Path) -> ImageGenerationResult:
    """モックの ImageGenerationResult を作成する."""
    return ImageGenerationResult(
        image_path=output_path,
        model_name="gen4_image_turbo",
        cost_usd=0.02,
    )


class TestGenerateKeyframes:
    """RunwayKeyframeEngine.generate_keyframes のテスト."""

    @pytest.mark.asyncio
    async def test_generate_keyframes_全カット生成(
        self, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """全カットのキーフレーム画像が生成される."""
        mock_client = AsyncMock(spec=RunwayImageClient)

        async def mock_generate(request, output_path):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-keyframe")
            return _make_mock_image_result(output_path)

        mock_client.generate.side_effect = mock_generate

        engine = RunwayKeyframeEngine.from_components(image_client=mock_client)
        output_dir = tmp_path / "assets" / "keyframes"
        result = await engine.generate_keyframes(sample_storyboard, sample_assets, output_dir)

        assert mock_client.generate.await_count == 4
        assert len(result.keyframes) == 4

    @pytest.mark.asyncio
    async def test_generate_keyframes_AssetSet構造(
        self, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """出力のAssetSetにkeyframesが正しく追加される."""
        mock_client = AsyncMock(spec=RunwayImageClient)

        async def mock_generate(request, output_path):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-keyframe")
            return _make_mock_image_result(output_path)

        mock_client.generate.side_effect = mock_generate

        engine = RunwayKeyframeEngine.from_components(image_client=mock_client)
        output_dir = tmp_path / "assets" / "keyframes"
        result = await engine.generate_keyframes(sample_storyboard, sample_assets, output_dir)

        # 元のアセットは保持される
        assert len(result.characters) == 1
        assert result.characters[0].character_name == "Aoi"

        # キーフレームが追加されている
        assert len(result.keyframes) == 4
        assert result.keyframes[0].scene_number == 1
        assert result.keyframes[0].prompt == "@char walks out of a modern apartment entrance, morning light"
        assert result.keyframes[2].scene_number == 2

    @pytest.mark.asyncio
    async def test_generate_keyframes_参照画像がfront_view(
        self, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """参照画像としてcharacters[0].front_viewが使用される."""
        mock_client = AsyncMock(spec=RunwayImageClient)

        async def mock_generate(request, output_path):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-keyframe")
            return _make_mock_image_result(output_path)

        mock_client.generate.side_effect = mock_generate

        engine = RunwayKeyframeEngine.from_components(image_client=mock_client)
        output_dir = tmp_path / "assets" / "keyframes"
        await engine.generate_keyframes(sample_storyboard, sample_assets, output_dir)

        # 各呼び出しで front_view が参照画像として使われている
        for call in mock_client.generate.call_args_list:
            request = call[0][0]
            assert "char" in request.reference_images
            assert request.reference_images["char"] == sample_assets.characters[0].front_view

    @pytest.mark.asyncio
    async def test_generate_keyframes_キャラクター不在_ValueError(
        self, sample_storyboard: Storyboard, tmp_path: Path
    ) -> None:
        """キャラクターがない場合エラー."""
        mock_client = AsyncMock(spec=RunwayImageClient)
        engine = RunwayKeyframeEngine.from_components(image_client=mock_client)
        empty_assets = AssetSet(characters=[], props=[], backgrounds=[])

        with pytest.raises(ValueError, match="キャラクターアセット"):
            await engine.generate_keyframes(sample_storyboard, empty_assets, tmp_path / "keyframes")


class TestKeyframeEngineExecute:
    """RunwayKeyframeEngine.execute のテスト."""

    @pytest.mark.asyncio
    async def test_execute_KeyframeInput経由(
        self, sample_scenario: Scenario, sample_storyboard: Storyboard, sample_assets: AssetSet, tmp_path: Path
    ) -> None:
        """execute が generate_keyframes を呼び、save_output で保存する."""
        mock_client = AsyncMock(spec=RunwayImageClient)

        async def mock_generate(request, output_path):
            output_path.parent.mkdir(parents=True, exist_ok=True)
            output_path.write_bytes(b"fake-keyframe")
            return _make_mock_image_result(output_path)

        mock_client.generate.side_effect = mock_generate

        engine = RunwayKeyframeEngine.from_components(image_client=mock_client)
        input_data = KeyframeInput(scenario=sample_scenario, storyboard=sample_storyboard, assets=sample_assets)
        result = await engine.execute(input_data, tmp_path)

        assert isinstance(result, AssetSet)
        assert len(result.keyframes) == 4


class TestKeyframeEnginePersistence:
    """RunwayKeyframeEngine の永続化テスト."""

    def test_save_load_roundtrip(self, tmp_path: Path) -> None:
        """save_output → load_output のラウンドトリップ."""
        engine = RunwayKeyframeEngine()

        assets = AssetSet(
            characters=[
                CharacterAsset(
                    character_name="Aoi",
                    front_view=Path("assets/character/front.png"),
                    side_view=Path("assets/character/side.png"),
                    back_view=Path("assets/character/back.png"),
                )
            ],
            props=[PropAsset(name="coffee", image_path=Path("assets/props/coffee.png"))],
            backgrounds=[
                BackgroundAsset(scene_number=1, description="玄関", image_path=Path("assets/bg/s01.png")),
            ],
            keyframes=[
                KeyframeAsset(
                    scene_number=1,
                    image_path=Path("assets/keyframes/scene_01_cut_01.png"),
                    prompt="@char at apartment entrance",
                ),
                KeyframeAsset(
                    scene_number=2,
                    image_path=Path("assets/keyframes/scene_02_cut_01.png"),
                    prompt="@char at cafe counter",
                ),
            ],
        )

        engine.save_output(tmp_path, assets)
        loaded = engine.load_output(tmp_path)

        assert len(loaded.keyframes) == 2
        assert loaded.keyframes[0].scene_number == 1
        assert loaded.keyframes[0].image_path == Path("assets/keyframes/scene_01_cut_01.png")
        assert loaded.characters[0].character_name == "Aoi"

    def test_load_output_ファイル未存在_FileNotFoundError(self, tmp_path: Path) -> None:
        """保存ファイルがない場合エラー."""
        engine = RunwayKeyframeEngine()

        with pytest.raises(FileNotFoundError, match="AssetSet"):
            engine.load_output(tmp_path)
