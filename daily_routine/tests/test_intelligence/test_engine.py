"""engine.py の統合テスト."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daily_routine.intelligence.base import SceneCapture, SeedVideo
from daily_routine.intelligence.engine import IntelligenceEngine
from daily_routine.schemas.intelligence import TrendReport
from daily_routine.schemas.pipeline_io import IntelligenceInput


def _make_sample_trend_report_json() -> str:
    return """{
  "keyword": "OLの一日",
  "analyzed_video_count": 3,
  "scene_structure": {
    "total_scenes": 8,
    "avg_scene_duration_sec": 7.0,
    "hook_techniques": ["時刻テロップ"],
    "transition_patterns": ["時系列遷移"]
  },
  "caption_trend": {
    "font_styles": ["丸ゴシック"],
    "color_schemes": ["白文字+黒縁取り"],
    "animation_types": ["ポップイン"],
    "positions": ["画面中央下"],
    "emphasis_techniques": ["キーワード色変え"]
  },
  "visual_trend": {
    "situations": ["起床", "通勤"],
    "props": ["スマホ"],
    "camera_works": ["俯瞰"],
    "color_tones": ["暖色系"]
  },
  "audio_trend": {
    "bpm_range": [90, 120],
    "genres": ["Lo-Fi"],
    "volume_patterns": ["フェードイン"],
    "se_usage_points": ["アラーム音"]
  },
  "asset_requirements": {
    "characters": ["OL"],
    "props": ["スマホ"],
    "backgrounds": ["オフィス"]
  }
}"""


class TestIntelligenceEngine:
    """IntelligenceEngine 統合テスト."""

    @pytest.mark.asyncio
    async def test_analyze_シード動画からトレンド分析(self) -> None:
        """SeedVideo → SeedVideoData → TrendAggregator の完全フローテスト."""
        engine = IntelligenceEngine(google_ai_api_key="gemini-key")

        mock_report = TrendReport.model_validate_json(_make_sample_trend_report_json())
        mock_agg = MagicMock()
        mock_agg.aggregate = AsyncMock(return_value=mock_report)

        with patch(
            "daily_routine.intelligence.engine.TrendAggregator",
            return_value=mock_agg,
        ):
            result = await engine.analyze(
                keyword="OLの一日",
                seed_videos=[SeedVideo(note="営業職の忙しさを表現")],
            )

        assert isinstance(result, TrendReport)
        assert result.keyword == "OLの一日"

        # TrendAggregator が呼ばれたことを検証
        mock_agg.aggregate.assert_called_once()
        call_kwargs = mock_agg.aggregate.call_args.kwargs
        assert call_kwargs["keyword"] == "OLの一日"
        assert len(call_kwargs["seed_videos"]) == 1
        assert call_kwargs["seed_videos"][0].user_note == "営業職の忙しさを表現"

    @pytest.mark.asyncio
    async def test_analyze_scene_captures変換(self, tmp_path: Path) -> None:
        """scene_captures が SeedVideoData に正しく渡されることを検証."""
        engine = IntelligenceEngine(google_ai_api_key="gemini-key")

        img = tmp_path / "scene.png"
        img.write_bytes(b"\x89PNG")

        mock_report = TrendReport.model_validate_json(_make_sample_trend_report_json())
        mock_agg = MagicMock()
        mock_agg.aggregate = AsyncMock(return_value=mock_report)

        with patch(
            "daily_routine.intelligence.engine.TrendAggregator",
            return_value=mock_agg,
        ):
            result = await engine.analyze(
                keyword="テスト",
                seed_videos=[
                    SeedVideo(
                        note="テスト動画",
                        scene_captures=[
                            SceneCapture(image_path=img, description="冒頭シーン", timestamp_sec=1.0),
                        ],
                    )
                ],
            )

        assert isinstance(result, TrendReport)
        call_kwargs = mock_agg.aggregate.call_args.kwargs
        assert len(call_kwargs["seed_videos"][0].scene_captures) == 1
        assert call_kwargs["seed_videos"][0].scene_captures[0].description == "冒頭シーン"

    @pytest.mark.asyncio
    async def test_analyze_空シード動画リスト(self) -> None:
        """シード動画0件でも正常動作."""
        engine = IntelligenceEngine(google_ai_api_key="gemini-key")

        mock_report = TrendReport.model_validate_json(_make_sample_trend_report_json())
        mock_agg = MagicMock()
        mock_agg.aggregate = AsyncMock(return_value=mock_report)

        with patch(
            "daily_routine.intelligence.engine.TrendAggregator",
            return_value=mock_agg,
        ):
            result = await engine.analyze(keyword="テスト", seed_videos=[])

        assert isinstance(result, TrendReport)
        call_kwargs = mock_agg.aggregate.call_args.kwargs
        assert call_kwargs["seed_videos"] == []


class TestIntelligenceEngineStepEngine:
    """StepEngine インターフェースのテスト."""

    @pytest.mark.asyncio
    async def test_execute_IntelligenceInput経由(self) -> None:
        engine = IntelligenceEngine(google_ai_api_key="gemini-key")

        mock_report = TrendReport.model_validate_json(_make_sample_trend_report_json())
        mock_analyze = AsyncMock(return_value=mock_report)

        with patch.object(engine, "analyze", mock_analyze):
            input_data = IntelligenceInput(keyword="OLの一日")
            result = await engine.execute(input_data, Path("/tmp/test"))

        assert isinstance(result, TrendReport)
        mock_analyze.assert_called_once_with(keyword="OLの一日", seed_videos=[])

    def test_save_output_and_load_output(self, tmp_path: Path) -> None:
        engine = IntelligenceEngine()
        report = TrendReport.model_validate_json(_make_sample_trend_report_json())

        engine.save_output(tmp_path, report)

        # ファイル存在確認
        report_path = tmp_path / "intelligence" / "report.json"
        assert report_path.exists()

        # ロード
        loaded = engine.load_output(tmp_path)
        assert loaded.keyword == report.keyword
        assert loaded.analyzed_video_count == report.analyzed_video_count
        assert loaded.scene_structure.total_scenes == report.scene_structure.total_scenes

    def test_load_output_ファイルなし_FileNotFoundError(self, tmp_path: Path) -> None:
        engine = IntelligenceEngine()
        with pytest.raises(FileNotFoundError, match="TrendReport"):
            engine.load_output(tmp_path)

    def test_save_output_JSONラウンドトリップ(self, tmp_path: Path) -> None:
        engine = IntelligenceEngine()
        report = TrendReport.model_validate_json(_make_sample_trend_report_json())

        engine.save_output(tmp_path, report)

        # JSONとして直接読み込んで検証
        report_path = tmp_path / "intelligence" / "report.json"
        data = json.loads(report_path.read_text())
        assert data["keyword"] == "OLの一日"
        assert data["audio_trend"]["bpm_range"] == [90, 120]
