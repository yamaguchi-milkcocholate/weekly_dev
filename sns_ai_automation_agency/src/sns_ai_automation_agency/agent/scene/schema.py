from typing import List

from pydantic import BaseModel, ConfigDict, Field


class Scene(BaseModel):
    """シーンの構造化レスポンス"""

    model_config = ConfigDict(from_attributes=True)

    title: str = Field(..., description="シーンのタイトル")
    content: str = Field(..., description="シーンの内容")
    telop: str = Field(..., description="シーンのテロップ")
    image_search_query: str = Field(..., description="画像検索クエリ")


class MovieResponse(BaseModel):
    """動画の構造化レスポンス"""

    model_config = ConfigDict(from_attributes=True)
    scenes: List[Scene] = Field(..., description="発見したシーンのリスト")
