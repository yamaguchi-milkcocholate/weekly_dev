"""ScenarioValidator のテスト."""

import pytest

from daily_routine.scenario.validator import ScenarioValidationError, ScenarioValidator
from daily_routine.schemas.scenario import (
    CameraWork,
    CharacterSpec,
    PropSpec,
    Scenario,
    SceneSpec,
)


def _make_scene(scene_number: int = 1, duration_sec: float = 5.0) -> SceneSpec:
    """テスト用のシーンを作成する."""
    return SceneSpec(
        scene_number=scene_number,
        duration_sec=duration_sec,
        situation="テスト状況",
        camera_work=CameraWork(type="POV", description="テストカメラワーク"),
        caption_text="テストテロップ",
        image_prompt="test image prompt",
        video_prompt="test video prompt",
    )


def _make_character() -> CharacterSpec:
    """テスト用のキャラクターを作成する."""
    return CharacterSpec(
        name="Aoi",
        appearance="25-year-old Japanese woman",
        outfit="white blouse, navy skirt",
        reference_prompt="A 25-year-old Japanese woman, full body, white background",
    )


def _make_prop() -> PropSpec:
    """テスト用の小物を作成する."""
    return PropSpec(
        name="スマートフォン",
        description="主人公が使用するスマホ",
        image_prompt="A modern smartphone, white background",
    )


def _make_scenario(
    total_duration_sec: float = 45.0,
    scenes: list[SceneSpec] | None = None,
    characters: list[CharacterSpec] | None = None,
) -> Scenario:
    """テスト用のシナリオを作成する."""
    if scenes is None:
        scenes = [
            _make_scene(1, 15.0),
            _make_scene(2, 15.0),
            _make_scene(3, 15.0),
        ]
    if characters is None:
        characters = [_make_character()]
    return Scenario(
        title="テスト動画",
        total_duration_sec=total_duration_sec,
        characters=characters,
        props=[_make_prop()],
        scenes=scenes,
        bgm_direction="明るいlo-fi pop、BPM 110〜130",
    )


class TestScenarioValidator:
    """ScenarioValidator のテスト."""

    def setup_method(self) -> None:
        self.validator = ScenarioValidator()

    def test_正常なシナリオ_バリデーション通過(self) -> None:
        scenario = _make_scenario()
        self.validator.validate(scenario, duration_range=(30, 60))

    def test_尺超過_エラー(self) -> None:
        scenario = _make_scenario(total_duration_sec=75.0)
        with pytest.raises(ScenarioValidationError) as exc_info:
            self.validator.validate(scenario, duration_range=(30, 60))
        assert "30〜60秒の範囲内" in exc_info.value.errors[0]

    def test_尺不足_エラー(self) -> None:
        scenario = _make_scenario(total_duration_sec=10.0)
        with pytest.raises(ScenarioValidationError) as exc_info:
            self.validator.validate(scenario, duration_range=(30, 60))
        assert "30〜60秒の範囲内" in exc_info.value.errors[0]

    def test_シーン0件_エラー(self) -> None:
        scenario = _make_scenario(scenes=[])
        with pytest.raises(ScenarioValidationError) as exc_info:
            self.validator.validate(scenario, duration_range=(0, 100))
        assert any("scenes が 0 件" in e for e in exc_info.value.errors)

    def test_duration_sec合計不一致_エラー(self) -> None:
        scenes = [_make_scene(1, 10.0), _make_scene(2, 10.0)]
        scenario = _make_scenario(total_duration_sec=45.0, scenes=scenes)
        with pytest.raises(ScenarioValidationError) as exc_info:
            self.validator.validate(scenario, duration_range=(0, 100))
        assert any("±2秒以内" in e for e in exc_info.value.errors)

    def test_duration_sec合計が許容範囲内_通過(self) -> None:
        scenes = [_make_scene(1, 15.0), _make_scene(2, 14.5), _make_scene(3, 15.0)]
        scenario = _make_scenario(total_duration_sec=45.0, scenes=scenes)
        # 合計44.5 vs 45.0 → 差0.5秒 → 許容範囲内
        self.validator.validate(scenario, duration_range=(30, 60))

    def test_scene_number非連番_エラー(self) -> None:
        scenes = [_make_scene(1, 15.0), _make_scene(2, 15.0), _make_scene(4, 15.0)]
        scenario = _make_scenario(scenes=scenes)
        with pytest.raises(ScenarioValidationError) as exc_info:
            self.validator.validate(scenario, duration_range=(30, 60))
        assert any("連番" in e for e in exc_info.value.errors)

    def test_キャラクター0件_エラー(self) -> None:
        scenario = _make_scenario(characters=[])
        with pytest.raises(ScenarioValidationError) as exc_info:
            self.validator.validate(scenario, duration_range=(0, 100))
        assert any("characters が 0 件" in e for e in exc_info.value.errors)

    def test_duration_sec_0以下_エラー(self) -> None:
        scenes = [_make_scene(1, 0.0), _make_scene(2, 15.0), _make_scene(3, 15.0)]
        scenario = _make_scenario(total_duration_sec=30.0, scenes=scenes)
        with pytest.raises(ScenarioValidationError) as exc_info:
            self.validator.validate(scenario, duration_range=(0, 100))
        assert any("0 より大きい値" in e for e in exc_info.value.errors)

    def test_複数エラー_全て報告(self) -> None:
        scenario = _make_scenario(
            total_duration_sec=100.0,
            scenes=[],
            characters=[],
        )
        with pytest.raises(ScenarioValidationError) as exc_info:
            self.validator.validate(scenario, duration_range=(30, 60))
        assert len(exc_info.value.errors) >= 3
