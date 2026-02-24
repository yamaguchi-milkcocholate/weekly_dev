"""youtube.py のテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daily_routine.intelligence.youtube import (
    VideoMetadata,
    YouTubeClient,
    _parse_iso8601_duration,
    extract_video_id,
)


class TestExtractVideoId:
    """extract_video_id のテスト."""

    def test_watch_url(self) -> None:
        assert extract_video_id("https://www.youtube.com/watch?v=abc123xyz00") == "abc123xyz00"

    def test_short_url(self) -> None:
        assert extract_video_id("https://youtu.be/abc123xyz00") == "abc123xyz00"

    def test_shorts_url(self) -> None:
        assert extract_video_id("https://www.youtube.com/shorts/abc123xyz00") == "abc123xyz00"

    def test_watch_url_追加パラメータあり(self) -> None:
        assert extract_video_id("https://www.youtube.com/watch?v=abc123xyz00&t=30") == "abc123xyz00"

    def test_不正なURL_ValueError(self) -> None:
        with pytest.raises(ValueError, match="動画ID"):
            extract_video_id("https://example.com/not-youtube")


class TestParseIso8601Duration:
    """_parse_iso8601_duration のテスト."""

    def test_秒のみ(self) -> None:
        assert _parse_iso8601_duration("PT45S") == 45

    def test_分秒(self) -> None:
        assert _parse_iso8601_duration("PT1M30S") == 90

    def test_時分秒(self) -> None:
        assert _parse_iso8601_duration("PT1H2M3S") == 3723

    def test_分のみ(self) -> None:
        assert _parse_iso8601_duration("PT5M") == 300

    def test_不正なフォーマット(self) -> None:
        assert _parse_iso8601_duration("INVALID") == 0


def _make_videos_list_response(video_id: str = "test123video") -> dict:
    """videos.list APIのモックレスポンスを生成する."""
    return {
        "items": [
            {
                "snippet": {
                    "title": "テスト動画",
                    "description": "テスト説明",
                    "channelTitle": "テストチャンネル",
                    "publishedAt": "2026-01-01T00:00:00Z",
                    "thumbnails": {"high": {"url": "https://example.com/thumb.jpg"}},
                    "tags": ["OL", "ルーティン"],
                    "categoryId": "22",
                },
                "statistics": {
                    "viewCount": "100000",
                    "likeCount": "5000",
                },
                "contentDetails": {
                    "duration": "PT58S",
                },
            }
        ]
    }


def _make_search_response(video_ids: list[str]) -> dict:
    """search.list APIのモックレスポンスを生成する."""
    return {
        "items": [{"id": {"videoId": vid}} for vid in video_ids],
    }


def _mock_response(json_data: dict) -> MagicMock:
    """httpxレスポンスのモックを作成する（json()は同期メソッド）."""
    resp = MagicMock()
    resp.json.return_value = json_data
    resp.raise_for_status.return_value = None
    return resp


class TestYouTubeClient:
    """YouTubeClient のテスト."""

    @pytest.mark.asyncio
    async def test_get_video_metadata_正常取得(self) -> None:
        mock_resp = _mock_response(_make_videos_list_response("vid001"))

        client = YouTubeClient(api_key="test-key")
        with patch.object(client._client, "get", AsyncMock(return_value=mock_resp)) as mock_get:
            result = await client.get_video_metadata("vid001")

        assert isinstance(result, VideoMetadata)
        assert result.video_id == "vid001"
        assert result.title == "テスト動画"
        assert result.view_count == 100000
        assert result.duration_sec == 58
        assert result.tags == ["OL", "ルーティン"]

        # APIパラメータの検証
        call_args = mock_get.call_args
        assert "videos" in call_args.args[0]
        assert call_args.kwargs["params"]["id"] == "vid001"

    @pytest.mark.asyncio
    async def test_get_video_metadata_動画なし_ValueError(self) -> None:
        mock_resp = _mock_response({"items": []})

        client = YouTubeClient(api_key="test-key")
        with patch.object(client._client, "get", AsyncMock(return_value=mock_resp)):
            with pytest.raises(ValueError, match="見つかりません"):
                await client.get_video_metadata("nonexistent")

    @pytest.mark.asyncio
    async def test_search_related_正常検索(self) -> None:
        seed = VideoMetadata(
            video_id="seed001",
            title="OLの朝",
            description="朝のルーティン",
            channel_title="Ch",
            published_at="2026-01-01T00:00:00Z",
            view_count=100000,
            like_count=5000,
            duration_sec=55,
            thumbnail_url="https://example.com/thumb.jpg",
            tags=["OL", "朝"],
        )

        search_resp = _mock_response(_make_search_response(["exp001", "exp002", "seed001"]))
        metadata_resp = _mock_response(_make_videos_list_response())

        client = YouTubeClient(api_key="test-key")
        with patch.object(client._client, "get", AsyncMock(side_effect=[search_resp, metadata_resp, metadata_resp])):
            results = await client.search_related([seed], "OLの一日", max_results=10)

        # seed001 は除外されるので2件
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_search_related_結果0件(self) -> None:
        seed = VideoMetadata(
            video_id="seed001",
            title="テスト",
            description="",
            channel_title="Ch",
            published_at="2026-01-01T00:00:00Z",
            view_count=100,
            like_count=10,
            duration_sec=30,
            thumbnail_url="",
        )

        empty_resp = _mock_response({"items": []})

        client = YouTubeClient(api_key="test-key")
        with patch.object(client._client, "get", AsyncMock(return_value=empty_resp)):
            results = await client.search_related([seed], "テスト")

        assert results == []

    @pytest.mark.asyncio
    async def test_search_related_メタデータ取得失敗_スキップ(self) -> None:
        seed = VideoMetadata(
            video_id="seed001",
            title="テスト",
            description="",
            channel_title="Ch",
            published_at="2026-01-01T00:00:00Z",
            view_count=100,
            like_count=10,
            duration_sec=30,
            thumbnail_url="",
        )

        search_resp = _mock_response(_make_search_response(["fail001", "ok001"]))
        fail_resp = _mock_response({"items": []})
        ok_resp = _mock_response(_make_videos_list_response())

        client = YouTubeClient(api_key="test-key")
        with patch.object(client._client, "get", AsyncMock(side_effect=[search_resp, fail_resp, ok_resp])):
            results = await client.search_related([seed], "テスト")

        # fail001 はスキップ、ok001 のみ
        assert len(results) == 1


class TestBuildSearchQuery:
    """_build_search_query のテスト."""

    def test_キーワードとタグの結合(self) -> None:
        seed = VideoMetadata(
            video_id="v1",
            title="t",
            description="",
            channel_title="c",
            published_at="",
            view_count=0,
            like_count=0,
            duration_sec=30,
            thumbnail_url="",
            tags=["OL", "ルーティン", "朝", "OL"],
        )
        query = YouTubeClient._build_search_query([seed], "OLの一日")
        assert "OLの一日" in query
        assert "OL" in query

    def test_タグなし(self) -> None:
        seed = VideoMetadata(
            video_id="v1",
            title="t",
            description="",
            channel_title="c",
            published_at="",
            view_count=0,
            like_count=0,
            duration_sec=30,
            thumbnail_url="",
            tags=[],
        )
        query = YouTubeClient._build_search_query([seed], "テスト")
        assert query == "テスト"
