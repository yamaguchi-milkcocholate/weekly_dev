import asyncio
import os
from typing import Any, Dict, List

import httpx
from dotenv import load_dotenv


async def search_google_images_async(query: str, count: int = 10) -> List[Dict[str, Any]]:
    """駅名を受け取り、駅名標っぽい画像候補を返す（非同期版）"""
    load_dotenv()

    GOOGLE_API_KEY = os.environ["GOOGLE_CUSTOM_SEARCH_API_KEY"]
    GOOGLE_CX = os.environ["GOOGLE_CUSTOM_SEARCH_CX"]
    GOOGLE_ENDPOINT = "https://www.googleapis.com/customsearch/v1"

    params = {
        "key": GOOGLE_API_KEY,
        "cx": GOOGLE_CX,
        "searchType": "image",
        "q": query,
        "num": count,
        "safe": "active",
        "imgType": "photo",
        "gl": "jp",  # 地域を日本に設定
        "hl": "ja",  # 言語を日本語に設定
        "lr": "lang_ja",  # 検索結果を日本語に制限
        "filter": "0",  # 重複フィルタを無効化（より多くの結果）
    }

    async with httpx.AsyncClient() as client:
        res = await client.get(GOOGLE_ENDPOINT, params=params)
        res.raise_for_status()
        data = res.json()

    items = data.get("items", [])
    if not items:
        return []

    result = []
    for i, item in enumerate(items):
        image = item.get("image", None)
        if not image:
            continue

        result.append(
            {
                "id": f"img_{i + 1}",
                "snippet": item.get("snippet", ""),
                "link": item.get("link", ""),
                "thumbnailLink": image.get("thumbnailLink", ""),
                "width": image.get("width", 0),
                "height": image.get("height", 0),
                "rank": i + 1,
            }
        )

    return result


def search_google_images(query: str, count: int = 10) -> List[Dict[str, Any]]:
    """駅名を受け取り、駅名標っぽい画像候補を返す（同期版・後方互換性のため）"""
    return asyncio.run(search_google_images_async(query, count))
