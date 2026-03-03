"""OpenAIStoryboardEngine のモックテスト."""

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from daily_routine.schemas.pipeline_io import StoryboardInput
from daily_routine.schemas.scenario import (
    CameraWork,
    CharacterSpec,
    Scenario,
    SceneSpec,
)
from daily_routine.schemas.storyboard import (
    CutSpec,
    MotionIntensity,
    SceneStoryboard,
    Storyboard,
    Transition,
)
from daily_routine.storyboard.engine import OpenAIStoryboardEngine


def _make_scenario() -> Scenario:
    """テスト用のScenarioを作成する."""
    return Scenario(
        title="OLの一日 〜テスト編〜",
        total_duration_sec=45.0,
        characters=[
            CharacterSpec(
                name="Aoi",
                appearance="25-year-old Japanese woman",
                outfit="white blouse, navy skirt",
                reference_prompt="A 25-year-old Japanese woman, full body, white background",
            )
        ],
        scenes=[
            SceneSpec(
                scene_number=1,
                duration_sec=15.0,
                situation="朝起きる",
                camera_work=CameraWork(type="close-up", description="目覚まし時計のクローズアップ"),
                caption_text="おはよう〜",
                image_prompt="A cozy bedroom, morning light",
            ),
            SceneSpec(
                scene_number=2,
                duration_sec=15.0,
                situation="通勤する",
                camera_work=CameraWork(type="wide", description="駅のホーム"),
                caption_text="通勤ラッシュ",
                image_prompt="A train station platform",
            ),
            SceneSpec(
                scene_number=3,
                duration_sec=15.0,
                situation="オフィスで仕事",
                camera_work=CameraWork(type="POV", description="デスク上のPOV"),
                caption_text="今日も頑張る",
                image_prompt="A modern office desk",
            ),
        ],
        bgm_direction="明るいlo-fi pop、BPM 110〜130",
    )


def _make_storyboard() -> Storyboard:
    """テスト用のStoryboardを作成する."""
    return Storyboard(
        title="OLの一日 〜テスト編〜",
        total_duration_sec=45.0,
        total_cuts=15,
        scenes=[
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=15.0,
                cuts=[
                    CutSpec(
                        cut_id=f"scene_01_cut_{i:02d}",
                        scene_number=1,
                        cut_number=i,
                        duration_sec=3.0,
                        motion_intensity=MotionIntensity.SUBTLE,
                        camera_work="Slow zoom-in",
                        action_description="朝起きる",
                        motion_prompt="@char slowly opens eyes, the camera gently zooms in",
                        keyframe_prompt="@char lying in bed, cozy bedroom, morning light",
                        transition=Transition.CUT,
                    )
                    for i in range(1, 6)
                ],
            ),
            SceneStoryboard(
                scene_number=2,
                scene_duration_sec=15.0,
                cuts=[
                    CutSpec(
                        cut_id="scene_02_cut_01",
                        scene_number=2,
                        cut_number=1,
                        duration_sec=3.0,
                        motion_intensity=MotionIntensity.DYNAMIC,
                        camera_work="Pan right",
                        action_description="通勤する",
                        motion_prompt="@char walks along the platform, the camera pans right",
                        keyframe_prompt="@char standing on a train platform, wide shot",
                        transition=Transition.CROSS_FADE,
                    ),
                ]
                + [
                    CutSpec(
                        cut_id=f"scene_02_cut_{i:02d}",
                        scene_number=2,
                        cut_number=i,
                        duration_sec=3.0,
                        motion_intensity=MotionIntensity.DYNAMIC,
                        camera_work="Pan right",
                        action_description="通勤する",
                        motion_prompt="@char walks along the platform, the camera pans right",
                        keyframe_prompt="@char standing on a train platform, wide shot",
                        transition=Transition.CUT,
                    )
                    for i in range(2, 6)
                ],
            ),
            SceneStoryboard(
                scene_number=3,
                scene_duration_sec=15.0,
                cuts=[
                    CutSpec(
                        cut_id="scene_03_cut_01",
                        scene_number=3,
                        cut_number=1,
                        duration_sec=3.0,
                        motion_intensity=MotionIntensity.MODERATE,
                        camera_work="Static",
                        action_description="デスクで仕事",
                        motion_prompt="@char types on keyboard, the camera remains still",
                        keyframe_prompt="@char at a modern office desk, POV shot",
                        transition=Transition.CROSS_FADE,
                    ),
                ]
                + [
                    CutSpec(
                        cut_id=f"scene_03_cut_{i:02d}",
                        scene_number=3,
                        cut_number=i,
                        duration_sec=3.0,
                        motion_intensity=MotionIntensity.MODERATE,
                        camera_work="Static",
                        action_description="デスクで仕事",
                        motion_prompt="@char types on keyboard, the camera remains still",
                        keyframe_prompt="@char at a modern office desk, POV shot",
                        transition=Transition.CUT,
                    )
                    for i in range(2, 6)
                ],
            ),
        ],
    )


class TestOpenAIStoryboardEngine:
    """OpenAIStoryboardEngine のテスト."""

    def test_APIキー未設定_ValueError(self) -> None:
        engine = OpenAIStoryboardEngine(api_key="")
        with pytest.raises(ValueError, match="API キーが設定されていません"):
            import asyncio

            asyncio.run(
                engine.generate(
                    scenario=_make_scenario(),
                    output_dir=Path("/tmp/test"),
                )
            )

    @pytest.mark.asyncio
    async def test_正常系_Storyboard生成(self) -> None:
        engine = OpenAIStoryboardEngine(api_key="test-key")
        storyboard = _make_storyboard()

        with patch.object(engine, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = storyboard

            result = await engine.generate(
                scenario=_make_scenario(),
                output_dir=Path("/tmp/test"),
            )

        assert result.title == "OLの一日 〜テスト編〜"
        assert result.total_cuts == 15
        assert len(result.scenes) == 3
        mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_バリデーションエラー時_リトライ成功(self) -> None:
        engine = OpenAIStoryboardEngine(api_key="test-key", max_retries=2)

        # 1回目: カット数不足のStoryboard
        bad_storyboard = Storyboard(
            title="テスト",
            total_duration_sec=9.0,
            total_cuts=3,
            scenes=[
                SceneStoryboard(
                    scene_number=1,
                    scene_duration_sec=9.0,
                    cuts=[
                        CutSpec(
                            cut_id=f"scene_01_cut_{i:02d}",
                            scene_number=1,
                            cut_number=i,
                            duration_sec=3.0,
                            motion_intensity=MotionIntensity.SUBTLE,
                            camera_work="Static",
                            action_description="テスト",
                            motion_prompt="@char sits still, the camera remains static",
                            keyframe_prompt="@char in a room",
                            transition=Transition.CUT,
                        )
                        for i in range(1, 4)
                    ],
                ),
            ],
        )
        good_storyboard = _make_storyboard()

        with patch.object(engine, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [bad_storyboard, good_storyboard]

            result = await engine.generate(
                scenario=_make_scenario(),
                output_dir=Path("/tmp/test"),
            )

        assert result.total_cuts == 15
        assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_最大リトライ超過_RuntimeError(self) -> None:
        engine = OpenAIStoryboardEngine(api_key="test-key", max_retries=1)

        bad_storyboard = Storyboard(
            title="テスト",
            total_duration_sec=9.0,
            total_cuts=3,
            scenes=[
                SceneStoryboard(
                    scene_number=1,
                    scene_duration_sec=9.0,
                    cuts=[
                        CutSpec(
                            cut_id=f"scene_01_cut_{i:02d}",
                            scene_number=1,
                            cut_number=i,
                            duration_sec=3.0,
                            motion_intensity=MotionIntensity.SUBTLE,
                            camera_work="Static",
                            action_description="テスト",
                            motion_prompt="@char sits still, the camera remains static",
                            keyframe_prompt="@char in a room",
                            transition=Transition.CUT,
                        )
                        for i in range(1, 4)
                    ],
                ),
            ],
        )

        with patch.object(engine, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = bad_storyboard

            with pytest.raises(RuntimeError, match="2 回失敗"):
                await engine.generate(
                    scenario=_make_scenario(),
                    output_dir=Path("/tmp/test"),
                )

        assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_LLMが不正な型を返す_RuntimeError(self) -> None:
        engine = OpenAIStoryboardEngine(api_key="test-key", max_retries=0)

        with patch.object(engine, "_call_llm", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = RuntimeError("LLM が Storyboard を返しませんでした")

            with pytest.raises(RuntimeError, match="Storyboard を返しませんでした"):
                await engine.generate(
                    scenario=_make_scenario(),
                    output_dir=Path("/tmp/test"),
                )


class TestOpenAIStoryboardEnginePersistence:
    """OpenAIStoryboardEngine の永続化テスト."""

    def test_save_output_ファイル作成(self, tmp_path: Path) -> None:
        engine = OpenAIStoryboardEngine(api_key="test-key")
        storyboard = _make_storyboard()

        engine.save_output(tmp_path, storyboard)

        storyboard_file = tmp_path / "storyboard" / "storyboard.json"
        assert storyboard_file.exists()

    def test_load_output_正常読み込み(self, tmp_path: Path) -> None:
        engine = OpenAIStoryboardEngine(api_key="test-key")
        storyboard = _make_storyboard()

        engine.save_output(tmp_path, storyboard)
        loaded = engine.load_output(tmp_path)

        assert loaded.title == storyboard.title
        assert loaded.total_cuts == storyboard.total_cuts
        assert len(loaded.scenes) == len(storyboard.scenes)

    def test_load_output_ファイル未存在_FileNotFoundError(self, tmp_path: Path) -> None:
        engine = OpenAIStoryboardEngine(api_key="test-key")

        with pytest.raises(FileNotFoundError):
            engine.load_output(tmp_path)

    def test_execute_はgenerateを呼ぶ(self) -> None:
        """execute が generate のラッパーであることを確認する."""
        engine = OpenAIStoryboardEngine(api_key="test-key")
        storyboard = _make_storyboard()

        with patch.object(engine, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = storyboard

            import asyncio

            input_data = StoryboardInput(scenario=_make_scenario())
            result = asyncio.run(engine.execute(input_data, Path("/tmp/test")))

        assert result == storyboard
        mock_gen.assert_called_once()
