from pydantic import BaseModel, ConfigDict, Field


class StationSignResponse(BaseModel):
    """分析ノード用の構造化レスポンス"""

    model_config = ConfigDict(from_attributes=True)

    selected_id: str = Field(..., description="候補の id")
    reason: str = Field(..., description="選んだ理由を簡潔に1〜2文で述べること")
