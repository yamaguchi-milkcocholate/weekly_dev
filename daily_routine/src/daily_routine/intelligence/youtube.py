"""YouTube Data API v3 クライアント."""

import logging
import re

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

_YOUTUBE_API_BASE = "https://www.googleapis.com/youtube/v3"

# ISO 8601 duration パターン（PT1M30S, PT45S, PT1H2M3S 等）
_DURATION_PATTERN = re.compile(r"PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+)S)?")

# YouTube URL から動画IDを抽出するパターン
_VIDEO_ID_PATTERNS = [
    re.compile(r"(?:youtube\.com/watch\?.*v=|youtu\.be/|youtube\.com/shorts/)([a-zA-Z0-9_-]+)"),
]


class VideoMetadata(BaseModel):
    """YouTube動画のメタデータ."""

    video_id: str
    title: str
    description: str
    channel_title: str
    published_at: str
    view_count: int
    like_count: int
    duration_sec: int = Field(description="動画の長さ（秒）")
    thumbnail_url: str
    tags: list[str] = Field(default_factory=list, description="動画タグ")
    category_id: str = Field(default="", description="YouTubeカテゴリID")


def _parse_iso8601_duration(duration: str) -> int:
    """ISO 8601 duration を秒数に変換する."""
    match = _DURATION_PATTERN.match(duration)
    if not match:
        return 0
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = int(match.group(3) or 0)
    return hours * 3600 + minutes * 60 + seconds


def extract_video_id(url: str) -> str:
    """YouTube URLから動画IDを抽出する.

    対応形式:
    - https://www.youtube.com/watch?v=VIDEO_ID
    - https://youtu.be/VIDEO_ID
    - https://www.youtube.com/shorts/VIDEO_ID

    Raises:
        ValueError: URLから動画IDを抽出できない場合
    """
    for pattern in _VIDEO_ID_PATTERNS:
        match = pattern.search(url)
        if match:
            return match.group(1)
    msg = f"YouTube URLから動画IDを抽出できません: {url}"
    raise ValueError(msg)


class YouTubeClient:
    """YouTube Data API v3 クライアント."""

    def __init__(self, api_key: str) -> None:
        self._api_key = api_key
        self._client = httpx.AsyncClient(timeout=30.0)

    async def close(self) -> None:
        """HTTPクライアントを閉じる."""
        await self._client.aclose()

    async def get_video_metadata(self, video_id: str) -> VideoMetadata:
        """動画IDからメタデータを取得する.

        videos.list API の snippet, statistics, contentDetails を使用。

        Raises:
            httpx.HTTPStatusError: APIリクエスト失敗時
            ValueError: 動画が見つからない場合
        """
        params = {
            "part": "snippet,statistics,contentDetails",
            "id": video_id,
            "key": self._api_key,
        }
        response = await self._client.get(f"{_YOUTUBE_API_BASE}/videos", params=params)
        response.raise_for_status()
        data = response.json()

        items = data.get("items", [])
        if not items:
            msg = f"動画が見つかりません: {video_id}"
            raise ValueError(msg)

        item = items[0]
        snippet = item["snippet"]
        statistics = item.get("statistics", {})
        content_details = item.get("contentDetails", {})

        return VideoMetadata(
            video_id=video_id,
            title=snippet.get("title", ""),
            description=snippet.get("description", ""),
            channel_title=snippet.get("channelTitle", ""),
            published_at=snippet.get("publishedAt", ""),
            view_count=int(statistics.get("viewCount", 0)),
            like_count=int(statistics.get("likeCount", 0)),
            duration_sec=_parse_iso8601_duration(content_details.get("duration", "PT0S")),
            thumbnail_url=snippet.get("thumbnails", {}).get("high", {}).get("url", ""),
            tags=snippet.get("tags", []),
            category_id=snippet.get("categoryId", ""),
        )

    async def search_related(
        self,
        seed_metadata: list[VideoMetadata],
        keyword: str,
        max_results: int = 20,
    ) -> list[VideoMetadata]:
        """シード動画の情報をもとに類似動画を拡張検索する.

        シード動画のタイトル・タグ・説明文から検索クエリを構築し、
        類似するショート動画を検索する。シード動画自体は除外する。
        """
        query = self._build_search_query(seed_metadata, keyword)
        seed_ids = {m.video_id for m in seed_metadata}

        logger.info("拡張検索クエリ: %s", query)

        params = {
            "part": "id",
            "q": query,
            "type": "video",
            "videoDuration": "short",
            "videoDefinition": "high",
            "order": "viewCount",
            "maxResults": min(max_results * 2, 50),  # フィルタ後に足りるよう多めに取得
            "key": self._api_key,
        }
        response = await self._client.get(f"{_YOUTUBE_API_BASE}/search", params=params)
        response.raise_for_status()
        data = response.json()

        video_ids = [
            item["id"]["videoId"]
            for item in data.get("items", [])
            if item.get("id", {}).get("videoId") and item["id"]["videoId"] not in seed_ids
        ]

        if not video_ids:
            logger.warning("拡張検索で類似動画が0件でした")
            return []

        results = []
        for vid in video_ids[:max_results]:
            try:
                metadata = await self.get_video_metadata(vid)
                # 60秒以下のショート動画のみ
                if metadata.duration_sec <= 60:
                    results.append(metadata)
            except (httpx.HTTPStatusError, ValueError):
                logger.warning("拡張検索動画のメタデータ取得失敗（スキップ）: %s", vid)
                continue

        logger.info("拡張検索結果: %d件", len(results))
        return results

    @staticmethod
    def _build_search_query(seed_metadata: list[VideoMetadata], keyword: str) -> str:
        """シード動画の情報から検索クエリを構築する."""
        # 頻出タグを収集
        tag_count: dict[str, int] = {}
        for meta in seed_metadata:
            for tag in meta.tags:
                tag_count[tag] = tag_count.get(tag, 0) + 1

        # 頻出上位3タグを取得
        top_tags = sorted(tag_count, key=lambda t: tag_count[t], reverse=True)[:3]

        parts = [keyword]
        parts.extend(top_tags)

        return " ".join(parts)
