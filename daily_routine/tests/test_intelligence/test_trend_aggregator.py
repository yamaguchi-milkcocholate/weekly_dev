"""trend_aggregator.py のテスト."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daily_routine.intelligence.trend_aggregator import (
    SeedVideoData,
    TrendAggregator,
)
from daily_routine.schemas.intelligence import TrendReport


def _make_sample_trend_report_json() -> str:
    """サンプルの TrendReport JSON文字列."""
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
    "backgrounds": ["オフィス"]
  }
}"""


class TestTrendAggregator:
    """TrendAggregator のテスト."""

    @pytest.mark.asyncio
    async def test_aggregate_正常生成(self) -> None:
        mock_response = MagicMock()
        mock_response.text = _make_sample_trend_report_json()

        mock_models = MagicMock()
        mock_models.generate_content = AsyncMock(return_value=mock_response)

        mock_aio = MagicMock()
        mock_aio.models = mock_models

        with patch("daily_routine.intelligence.trend_aggregator.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.aio = mock_aio
            mock_client_cls.return_value = mock_client

            aggregator = TrendAggregator(api_key="test-key")
            result = await aggregator.aggregate(
                keyword="OLの一日",
                seed_videos=[
                    SeedVideoData(
                        scene_captures=[],
                        user_note="朝ルーティンが参考になる",
                    ),
                ],
            )

        assert isinstance(result, TrendReport)
        assert result.keyword == "OLの一日"
        assert result.analyzed_video_count == 3
        assert len(result.scene_structure.hook_techniques) > 0

    @pytest.mark.asyncio
    async def test_aggregate_keyword補正(self) -> None:
        # LLM が keyword を空で返した場合の補正
        json_text = _make_sample_trend_report_json().replace('"OLの一日"', '""')

        mock_response = MagicMock()
        mock_response.text = json_text

        mock_models = MagicMock()
        mock_models.generate_content = AsyncMock(return_value=mock_response)

        mock_aio = MagicMock()
        mock_aio.models = mock_models

        with patch("daily_routine.intelligence.trend_aggregator.genai.Client") as mock_client_cls:
            mock_client = MagicMock()
            mock_client.aio = mock_aio
            mock_client_cls.return_value = mock_client

            aggregator = TrendAggregator(api_key="test-key")
            result = await aggregator.aggregate(
                keyword="テストキーワード",
                seed_videos=[
                    SeedVideoData(user_note="テスト"),
                ],
            )

        assert result.keyword == "テストキーワード"

    @pytest.mark.asyncio
    async def test_build_contents_画像あり(self, tmp_path: Path) -> None:
        from daily_routine.intelligence.base import SceneCapture

        # テスト用画像ファイル作成
        img_path = tmp_path / "scene.png"
        img_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"\x00" * 100)

        with patch("daily_routine.intelligence.trend_aggregator.genai.Client"):
            aggregator = TrendAggregator(api_key="test-key")

        seed = SeedVideoData(
            scene_captures=[
                SceneCapture(
                    image_path=img_path,
                    description="テストシーン",
                    timestamp_sec=1.5,
                ),
            ],
            user_note="テストメモ",
        )

        parts = aggregator._build_contents("OLの一日", [seed])

        # テキストパートの存在確認
        text_parts = [p for p in parts if hasattr(p, "text") and p.text]
        all_text = " ".join(p.text for p in text_parts)
        assert "OLの一日" in all_text
        assert "テストメモ" in all_text
        assert "テストシーン" in all_text

    @pytest.mark.asyncio
    async def test_build_contents_シード動画のみ(self) -> None:
        with patch("daily_routine.intelligence.trend_aggregator.genai.Client"):
            aggregator = TrendAggregator(api_key="test-key")

        seed = SeedVideoData(user_note="テストメモ")

        parts = aggregator._build_contents("テスト", [seed])

        text_parts = [p for p in parts if hasattr(p, "text") and p.text]
        all_text = " ".join(p.text for p in text_parts)
        assert "テスト" in all_text
        assert "テストメモ" in all_text


class TestDataModels:
    """中間データモデルのテスト."""

    def test_seed_video_data_作成(self) -> None:
        data = SeedVideoData(
            user_note="テスト",
        )
        assert data.user_note == "テスト"
        assert data.scene_captures == []

    def test_seed_video_data_デフォルト(self) -> None:
        data = SeedVideoData()
        assert data.user_note == ""
        assert data.scene_captures == []
