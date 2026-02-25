"""schemas/visual.py のテスト."""

from pathlib import Path

from daily_routine.schemas.visual import VideoClip, VideoClipSet


class TestVideoClipSet:
    """VideoClipSet のテスト."""

    def test_create(self) -> None:
        clip_set = VideoClipSet(
            clips=[
                VideoClip(
                    scene_number=1,
                    clip_path=Path("clips/scene_1/clip.mp4"),
                    duration_sec=5.0,
                    model_name="gen4_turbo",
                ),
                VideoClip(
                    scene_number=2,
                    clip_path=Path("clips/scene_2/clip.mp4"),
                    duration_sec=4.5,
                    model_name="gen4_turbo",
                    cost_usd=0.5,
                    quality_score=0.85,
                    generation_time_sec=75.0,
                ),
            ],
            total_cost_usd=0.5,
            provider="runway",
        )
        assert len(clip_set.clips) == 2
        assert clip_set.clips[0].quality_score is None
        assert clip_set.clips[0].cost_usd is None
        assert clip_set.clips[1].quality_score == 0.85
        assert clip_set.clips[1].cost_usd == 0.5
        assert clip_set.total_cost_usd == 0.5
        assert clip_set.provider == "runway"

    def test_roundtrip_json(self) -> None:
        clip_set = VideoClipSet(
            clips=[
                VideoClip(
                    scene_number=1,
                    clip_path=Path("clips/scene_1/clip.mp4"),
                    duration_sec=5.0,
                    model_name="gen4_turbo",
                    cost_usd=0.5,
                    generation_time_sec=75.0,
                )
            ],
            total_cost_usd=0.5,
            provider="runway",
        )
        data = clip_set.model_dump(mode="json")
        restored = VideoClipSet(**data)
        assert restored.clips[0].clip_path == Path("clips/scene_1/clip.mp4")
        assert restored.clips[0].model_name == "gen4_turbo"
        assert restored.total_cost_usd == 0.5
        assert restored.provider == "runway"
