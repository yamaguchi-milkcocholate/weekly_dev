"""schemas/post.py のテスト."""

from pathlib import Path

from daily_routine.schemas.post import CaptionEntry, CaptionStyle, FinalOutput


def _make_final_output() -> FinalOutput:
    return FinalOutput(
        video_path=Path("output/final.mp4"),
        duration_sec=45.0,
        fps=30,
        captions=[
            CaptionEntry(
                text="朝7時に出発！",
                start_time_ms=0,
                end_time_ms=3000,
                style=CaptionStyle(
                    font="Noto Sans JP",
                    color="#FFFFFF",
                    position="bottom",
                ),
            ),
        ],
    )


class TestFinalOutput:
    """FinalOutput のテスト."""

    def test_create(self) -> None:
        output = _make_final_output()
        assert output.resolution == "1080x1920"
        assert output.fps == 30

    def test_roundtrip_json(self) -> None:
        output = _make_final_output()
        data = output.model_dump(mode="json")
        restored = FinalOutput(**data)
        assert restored.video_path == Path("output/final.mp4")
        assert restored.captions[0].style.font == "Noto Sans JP"
