"""StoryboardPromptBuilder のテスト."""

from daily_routine.schemas.scenario import (
    CameraWork,
    CharacterSpec,
    Scenario,
    SceneSpec,
)
from daily_routine.storyboard.prompt import StoryboardPromptBuilder


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
                reference_prompt="A 25-year-old Japanese woman, full body, green chroma key background",
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


class TestStoryboardPromptBuilder:
    """StoryboardPromptBuilder のテスト."""

    def setup_method(self) -> None:
        self.builder = StoryboardPromptBuilder()
        self.scenario = _make_scenario()

    def test_システムプロンプト_I2V制約を含む(self) -> None:
        prompt = self.builder.build_system_prompt()
        assert "I2V" in prompt or "Image-to-Video" in prompt
        assert "2-3秒" in prompt or "2〜5秒" in prompt

    def test_システムプロンプト_カメラワーク語彙を含む(self) -> None:
        prompt = self.builder.build_system_prompt()
        assert "Static" in prompt
        assert "zoom-in" in prompt or "Slow zoom-in" in prompt
        assert "Pan" in prompt

    def test_システムプロンプト_プロンプト品質ルールを含む(self) -> None:
        prompt = self.builder.build_system_prompt()
        assert "@char" in prompt
        assert "motion_prompt" in prompt or "keyframe_prompt" in prompt

    def test_システムプロンプト_生成ルールを含む(self) -> None:
        prompt = self.builder.build_system_prompt()
        assert "scene_" in prompt and "cut_" in prompt
        assert "transition" in prompt or "トランジション" in prompt

    def test_ユーザープロンプト_シナリオ情報を含む(self) -> None:
        prompt = self.builder.build_user_prompt(self.scenario)
        assert "OLの一日" in prompt
        assert "45" in prompt

    def test_ユーザープロンプト_キャラクター情報を含む(self) -> None:
        prompt = self.builder.build_user_prompt(self.scenario)
        assert "Aoi" in prompt
        assert "25-year-old" in prompt

    def test_ユーザープロンプト_シーン情報を含む(self) -> None:
        prompt = self.builder.build_user_prompt(self.scenario)
        assert "朝起きる" in prompt
        assert "通勤する" in prompt
        assert "15" in prompt

    def test_リトライプロンプト_エラー内容を含む(self) -> None:
        errors = [
            "全体カット数が 8 です。10〜40 の範囲内にしてください",
            "scene_01_cut_03 の duration_sec が 6 です。2〜5 秒にしてください",
        ]
        prompt = self.builder.build_retry_prompt(errors)
        assert "10〜40" in prompt
        assert "scene_01_cut_03" in prompt
        assert "修正" in prompt
