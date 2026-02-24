"""engine.py の統合テスト."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daily_routine.intelligence.base import SeedVideo
from daily_routine.intelligence.engine import IntelligenceEngine
from daily_routine.intelligence.transcript import TranscriptResult, TranscriptSegment
from daily_routine.intelligence.youtube import VideoMetadata
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


def _make_metadata(video_id: str = "vid001") -> VideoMetadata:
    return VideoMetadata(
        video_id=video_id,
        title="テスト動画",
        description="テスト説明",
        channel_title="テストチャンネル",
        published_at="2026-01-01T00:00:00Z",
        view_count=100000,
        like_count=5000,
        duration_sec=55,
        thumbnail_url="https://example.com/thumb.jpg",
        tags=["OL", "ルーティン"],
    )


def _make_transcript(video_id: str = "vid001") -> TranscriptResult:
    return TranscriptResult(
        video_id=video_id,
        source="youtube_caption",
        language="ja",
        segments=[
            TranscriptSegment(start_sec=0.0, duration_sec=2.0, text="テスト字幕"),
        ],
        full_text="テスト字幕",
    )


def _make_empty_transcript(video_id: str = "vid001") -> TranscriptResult:
    return TranscriptResult(video_id=video_id, source="none")


class TestIntelligenceEngine:
    """IntelligenceEngine 統合テスト."""

    @pytest.mark.asyncio
    async def test_analyze_一気通貫(self) -> None:
        """Phase A → B → C の完全フローテスト."""
        engine = IntelligenceEngine(
            youtube_api_key="yt-key",
            google_ai_api_key="gemini-key",
        )

        # YouTubeClient モック
        mock_yt = AsyncMock()
        mock_yt.get_video_metadata = AsyncMock(return_value=_make_metadata("seed001"))
        mock_yt.search_related = AsyncMock(return_value=[_make_metadata("exp001")])
        mock_yt.close = AsyncMock()

        # TranscriptFetcher モック
        mock_tf = MagicMock()
        mock_tf.fetch = AsyncMock(return_value=_make_transcript("seed001"))

        # TrendAggregator モック
        mock_report = TrendReport.model_validate_json(_make_sample_trend_report_json())
        mock_agg = MagicMock()
        mock_agg.aggregate = AsyncMock(return_value=mock_report)

        with (
            patch(
                "daily_routine.intelligence.engine.YouTubeClient",
                return_value=mock_yt,
            ),
            patch(
                "daily_routine.intelligence.engine.TranscriptFetcher",
                return_value=mock_tf,
            ),
            patch(
                "daily_routine.intelligence.engine.TrendAggregator",
                return_value=mock_agg,
            ),
        ):
            result = await engine.analyze(
                keyword="OLの一日",
                seed_videos=[SeedVideo(url="https://www.youtube.com/shorts/seed001")],
                max_expand_videos=5,
            )

        assert isinstance(result, TrendReport)
        assert result.keyword == "OLの一日"

        # YouTubeClient が呼ばれたことを検証
        mock_yt.get_video_metadata.assert_called_once_with("seed001")
        mock_yt.search_related.assert_called_once()
        mock_yt.close.assert_called_once()

        # TrendAggregator が呼ばれたことを検証
        mock_agg.aggregate.assert_called_once()
        call_kwargs = mock_agg.aggregate.call_args.kwargs
        assert call_kwargs["keyword"] == "OLの一日"
        assert len(call_kwargs["seed_videos"]) == 1
        assert len(call_kwargs["expanded_videos"]) == 1

    @pytest.mark.asyncio
    async def test_analyze_拡張検索0件_シード動画のみで分析(self) -> None:
        engine = IntelligenceEngine(
            youtube_api_key="yt-key",
            google_ai_api_key="gemini-key",
        )

        mock_yt = AsyncMock()
        mock_yt.get_video_metadata = AsyncMock(return_value=_make_metadata("seed001"))
        mock_yt.search_related = AsyncMock(return_value=[])  # 0件
        mock_yt.close = AsyncMock()

        mock_tf = MagicMock()
        mock_tf.fetch = AsyncMock(return_value=_make_transcript())

        mock_report = TrendReport.model_validate_json(_make_sample_trend_report_json())
        mock_agg = MagicMock()
        mock_agg.aggregate = AsyncMock(return_value=mock_report)

        with (
            patch("daily_routine.intelligence.engine.YouTubeClient", return_value=mock_yt),
            patch("daily_routine.intelligence.engine.TranscriptFetcher", return_value=mock_tf),
            patch("daily_routine.intelligence.engine.TrendAggregator", return_value=mock_agg),
        ):
            result = await engine.analyze(
                keyword="テスト",
                seed_videos=[SeedVideo(url="https://www.youtube.com/shorts/seed001")],
            )

        assert isinstance(result, TrendReport)
        call_kwargs = mock_agg.aggregate.call_args.kwargs
        assert call_kwargs["expanded_videos"] == []

    @pytest.mark.asyncio
    async def test_analyze_字幕なし_degraded_mode(self) -> None:
        engine = IntelligenceEngine(
            youtube_api_key="yt-key",
            google_ai_api_key="gemini-key",
        )

        mock_yt = AsyncMock()
        mock_yt.get_video_metadata = AsyncMock(return_value=_make_metadata())
        mock_yt.search_related = AsyncMock(return_value=[])
        mock_yt.close = AsyncMock()

        # 字幕取得失敗
        mock_tf = MagicMock()
        mock_tf.fetch = AsyncMock(return_value=_make_empty_transcript())

        mock_report = TrendReport.model_validate_json(_make_sample_trend_report_json())
        mock_agg = MagicMock()
        mock_agg.aggregate = AsyncMock(return_value=mock_report)

        with (
            patch("daily_routine.intelligence.engine.YouTubeClient", return_value=mock_yt),
            patch("daily_routine.intelligence.engine.TranscriptFetcher", return_value=mock_tf),
            patch("daily_routine.intelligence.engine.TrendAggregator", return_value=mock_agg),
        ):
            result = await engine.analyze(
                keyword="テスト",
                seed_videos=[SeedVideo(url="https://www.youtube.com/shorts/vid001")],
            )

        assert isinstance(result, TrendReport)
        # transcript は None として渡される
        call_kwargs = mock_agg.aggregate.call_args.kwargs
        assert call_kwargs["seed_videos"][0].transcript is None

    @pytest.mark.asyncio
    async def test_analyze_シード動画メタデータ取得失敗_例外(self) -> None:
        engine = IntelligenceEngine(youtube_api_key="yt-key", google_ai_api_key="gemini-key")

        mock_yt = AsyncMock()
        mock_yt.get_video_metadata = AsyncMock(side_effect=ValueError("見つかりません"))
        mock_yt.close = AsyncMock()

        mock_tf = MagicMock()

        with (
            patch("daily_routine.intelligence.engine.YouTubeClient", return_value=mock_yt),
            patch("daily_routine.intelligence.engine.TranscriptFetcher", return_value=mock_tf),
            pytest.raises(ValueError, match="見つかりません"),
        ):
            await engine.analyze(
                keyword="テスト",
                seed_videos=[SeedVideo(url="https://www.youtube.com/shorts/bad_vid_0001")],
            )


class TestIntelligenceEngineStepEngine:
    """StepEngine インターフェースのテスト."""

    @pytest.mark.asyncio
    async def test_execute_IntelligenceInput経由(self) -> None:
        engine = IntelligenceEngine(youtube_api_key="yt-key", google_ai_api_key="gemini-key")

        mock_report = TrendReport.model_validate_json(_make_sample_trend_report_json())
        mock_analyze = AsyncMock(return_value=mock_report)

        with patch.object(engine, "analyze", mock_analyze):
            input_data = IntelligenceInput(keyword="OLの一日")
            result = await engine.execute(input_data, Path("/tmp/test"))

        assert isinstance(result, TrendReport)
        mock_analyze.assert_called_once()

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


class TestIntelligenceEngineSceneCapture:
    """画像なしシード動画のテスト."""

    @pytest.mark.asyncio
    async def test_scene_captures空_正常動作(self) -> None:
        engine = IntelligenceEngine(youtube_api_key="yt-key", google_ai_api_key="gemini-key")

        mock_yt = AsyncMock()
        mock_yt.get_video_metadata = AsyncMock(return_value=_make_metadata())
        mock_yt.search_related = AsyncMock(return_value=[])
        mock_yt.close = AsyncMock()

        mock_tf = MagicMock()
        mock_tf.fetch = AsyncMock(return_value=_make_transcript())

        mock_report = TrendReport.model_validate_json(_make_sample_trend_report_json())
        mock_agg = MagicMock()
        mock_agg.aggregate = AsyncMock(return_value=mock_report)

        with (
            patch("daily_routine.intelligence.engine.YouTubeClient", return_value=mock_yt),
            patch("daily_routine.intelligence.engine.TranscriptFetcher", return_value=mock_tf),
            patch("daily_routine.intelligence.engine.TrendAggregator", return_value=mock_agg),
        ):
            # scene_captures なしの SeedVideo
            result = await engine.analyze(
                keyword="テスト",
                seed_videos=[SeedVideo(url="https://www.youtube.com/shorts/vid001")],
            )

        assert isinstance(result, TrendReport)
        call_kwargs = mock_agg.aggregate.call_args.kwargs
        assert call_kwargs["seed_videos"][0].scene_captures == []
