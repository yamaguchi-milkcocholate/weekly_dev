from pydantic import BaseModel, Field


class SearchQueryResponse(BaseModel):
    query: str = Field(..., description="画像検索用クエリ（日本語キーワードの並び）")
    reason_core: str = Field(..., description="核となる視覚イメージの説明（短く）")
    reason_living: str = Field(..., description="「住みたい街・住む目線」をどう反映したか")
    reason_simplicity: str = Field(..., description="1秒で伝わるように何を削ったか・絞ったか")
