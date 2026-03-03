"""schemas/intelligence.py のテスト."""

from daily_routine.schemas.intelligence import (
    AssetRequirement,
    AudioTrend,
    CaptionTrend,
    SceneStructure,
    TrendReport,
    VisualTrend,
)


def _make_trend_report() -> TrendReport:
    return TrendReport(
        keyword="OLの一日",
        analyzed_video_count=10,
        scene_structure=SceneStructure(
            total_scenes=8,
            avg_scene_duration_sec=5.0,
            hook_techniques=["テキストフック"],
            transition_patterns=["カット"],
        ),
        caption_trend=CaptionTrend(
            font_styles=["ゴシック"],
            color_schemes=["白黒"],
            animation_types=["フェード"],
            positions=["bottom"],
            emphasis_techniques=["太字"],
        ),
        visual_trend=VisualTrend(
            situations=["通勤"],
            camera_works=["POV"],
            color_tones=["暖色系"],
        ),
        audio_trend=AudioTrend(
            bpm_range=[100, 130],
            genres=["Lo-Fi"],
            volume_patterns=["フェードイン"],
            se_usage_points=["シーン切り替え"],
        ),
        asset_requirements=AssetRequirement(
            characters=["OL"],
            backgrounds=["オフィス", "電車"],
        ),
    )


class TestTrendReport:
    """TrendReport のテスト."""

    def test_create(self) -> None:
        report = _make_trend_report()
        assert report.keyword == "OLの一日"
        assert report.analyzed_video_count == 10

    def test_roundtrip_json(self) -> None:
        report = _make_trend_report()
        data = report.model_dump(mode="json")
        restored = TrendReport(**data)
        assert restored.keyword == report.keyword
        assert restored.scene_structure.total_scenes == report.scene_structure.total_scenes
        assert restored.audio_trend.bpm_range == report.audio_trend.bpm_range
