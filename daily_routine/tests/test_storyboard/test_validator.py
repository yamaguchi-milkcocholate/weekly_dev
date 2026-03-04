"""StoryboardValidator のテスト."""

import pytest

from daily_routine.schemas.storyboard import (
    CutSpec,
    MotionIntensity,
    SceneStoryboard,
    Storyboard,
    Transition,
)
from daily_routine.storyboard.validator import StoryboardValidationError, StoryboardValidator


def _make_cut(
    scene_number: int = 1,
    cut_number: int = 1,
    duration_sec: float = 3.0,
    keyframe_prompt: str = "@char sits at a cafe table, morning light",
    motion_prompt: str = "@char slowly sips coffee, the camera zooms in",
    cut_id: str | None = None,
    transition: Transition = Transition.CUT,
    action_description: str = "コーヒーを飲む",
    has_character: bool = True,
) -> CutSpec:
    """テスト用のCutSpecを作成する."""
    if cut_id is None:
        cut_id = f"scene_{scene_number:02d}_cut_{cut_number:02d}"
    return CutSpec(
        cut_id=cut_id,
        scene_number=scene_number,
        cut_number=cut_number,
        duration_sec=duration_sec,
        motion_intensity=MotionIntensity.SUBTLE,
        camera_work="Slow zoom-in",
        action_description=action_description,
        motion_prompt=motion_prompt,
        keyframe_prompt=keyframe_prompt,
        transition=transition,
        has_character=has_character,
    )


def _make_storyboard(
    total_duration_sec: float | None = None,
    total_cuts: int | None = None,
    scenes: list[SceneStoryboard] | None = None,
) -> Storyboard:
    """テスト用のStoryboardを作成する."""
    if scenes is None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=9.0,
                cuts=[
                    _make_cut(1, 1, 3.0),
                    _make_cut(1, 2, 3.0),
                    _make_cut(1, 3, 3.0),
                ],
            ),
            SceneStoryboard(
                scene_number=2,
                scene_duration_sec=9.0,
                cuts=[
                    _make_cut(2, 1, 3.0, transition=Transition.CROSS_FADE),
                    _make_cut(2, 2, 3.0),
                    _make_cut(2, 3, 3.0),
                ],
            ),
            SceneStoryboard(
                scene_number=3,
                scene_duration_sec=12.0,
                cuts=[
                    _make_cut(3, 1, 3.0, transition=Transition.CROSS_FADE),
                    _make_cut(3, 2, 3.0),
                    _make_cut(3, 3, 3.0),
                    _make_cut(3, 4, 3.0),
                ],
            ),
        ]
    all_cuts = [c for s in scenes for c in s.cuts]
    if total_duration_sec is None:
        total_duration_sec = sum(c.duration_sec for c in all_cuts)
    if total_cuts is None:
        total_cuts = len(all_cuts)
    return Storyboard(
        title="テスト動画",
        total_duration_sec=total_duration_sec,
        total_cuts=total_cuts,
        scenes=scenes,
    )


class TestStoryboardValidator:
    """StoryboardValidator のテスト."""

    def setup_method(self) -> None:
        self.validator = StoryboardValidator()

    def test_正常なStoryboard_バリデーション通過(self) -> None:
        storyboard = _make_storyboard()
        self.validator.validate(storyboard)

    def test_全体カット数不足_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=9.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 4)],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("10〜40" in e for e in exc_info.value.errors)

    def test_全体カット数超過_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=i,
                scene_duration_sec=10.0,
                cuts=[_make_cut(i, j, 2.0) for j in range(1, 6)],
            )
            for i in range(1, 10)
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("10〜40" in e for e in exc_info.value.errors)

    def test_カット尺が範囲外_短すぎ_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=31.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 11)] + [_make_cut(1, 11, 1.0)],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("2〜5 秒" in e for e in exc_info.value.errors)

    def test_カット尺が範囲外_長すぎ_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=36.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 11)] + [_make_cut(1, 11, 6.0)],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("2〜5 秒" in e for e in exc_info.value.errors)

    def test_カット尺が非整数_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=30.5,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 10)] + [_make_cut(1, 10, 3.5)],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("整数" in e for e in exc_info.value.errors)

    def test_シーン内カット合計不一致_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=15.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 11)],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("scene_duration_sec" in e for e in exc_info.value.errors)

    def test_全カット合計と全体尺不一致_エラー(self) -> None:
        storyboard = _make_storyboard(total_duration_sec=100.0)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("total_duration_sec" in e for e in exc_info.value.errors)

    def test_keyframe_prompt空_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=30.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 10)] + [_make_cut(1, 10, 3.0, keyframe_prompt="")],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("keyframe_prompt が空" in e for e in exc_info.value.errors)

    def test_cut_id形式不正_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=30.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 10)] + [_make_cut(1, 10, 3.0, cut_id="invalid_format")],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("scene_NN_cut_NN" in e for e in exc_info.value.errors)

    def test_motion_promptに日本語_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=30.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 10)]
                + [_make_cut(1, 10, 3.0, motion_prompt="ゆっくり歩く")],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("日本語" in e for e in exc_info.value.errors)

    def test_keyframe_promptにcharタグなし_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=30.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 10)]
                + [_make_cut(1, 10, 3.0, keyframe_prompt="A woman sits at a cafe table")],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("@char" in e for e in exc_info.value.errors)

    def test_action_descriptionにcharタグ_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=30.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 10)]
                + [_make_cut(1, 10, 3.0, action_description="@char がコーヒーを飲む")],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("action_description" in e and "@char" in e for e in exc_info.value.errors)

    def test_シーン間トランジションがcutのまま_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=15.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 6)],
            ),
            SceneStoryboard(
                scene_number=2,
                scene_duration_sec=15.0,
                cuts=[_make_cut(2, i, 3.0) for i in range(1, 6)],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("cross_fade" in e for e in exc_info.value.errors)

    def test_シーン1の最初のカットはcross_fade不要(self) -> None:
        storyboard = _make_storyboard()
        # シーン1の最初のカットが cut でもエラーにならないことを確認
        assert storyboard.scenes[0].cuts[0].transition == Transition.CUT
        self.validator.validate(storyboard)  # エラーなし

    def test_has_character_false_charタグなし_通過(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=30.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 10)]
                + [
                    _make_cut(
                        1,
                        10,
                        3.0,
                        keyframe_prompt="Coffee beans on a wooden table, warm lighting",
                        has_character=False,
                    )
                ],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        self.validator.validate(storyboard)

    def test_has_character_false_charタグあり_エラー(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=30.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 10)]
                + [
                    _make_cut(
                        1,
                        10,
                        3.0,
                        keyframe_prompt="@char holds coffee beans",
                        has_character=False,
                    )
                ],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert any("has_character=false" in e for e in exc_info.value.errors)

    def test_has_character混在_通過(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=30.0,
                cuts=[_make_cut(1, i, 3.0) for i in range(1, 10)]
                + [
                    _make_cut(
                        1,
                        10,
                        3.0,
                        keyframe_prompt="Steaming latte on marble counter, soft bokeh",
                        has_character=False,
                    )
                ],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        self.validator.validate(storyboard)

    def test_複数エラー_全て報告(self) -> None:
        scenes = [
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=6.0,
                cuts=[
                    _make_cut(1, 1, 1.0, keyframe_prompt="", motion_prompt="日本語プロンプト", cut_id="bad"),
                    _make_cut(1, 2, 3.0),
                ],
            ),
        ]
        storyboard = _make_storyboard(scenes=scenes)
        with pytest.raises(StoryboardValidationError) as exc_info:
            self.validator.validate(storyboard)
        assert len(exc_info.value.errors) >= 3
