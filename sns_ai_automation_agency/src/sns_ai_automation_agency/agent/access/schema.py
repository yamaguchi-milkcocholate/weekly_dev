# 必要なライブラリのインポート
from typing import Annotated, List

# State定義 - Agent間でやり取りするデータ構造
from langgraph.graph import MessagesState
from pydantic import BaseModel, ConfigDict, Field


# Pydantic BaseModelでStationクラスを定義
class Station(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="駅名")
    duration_minutes: int = Field(..., description="最短所要時間（分）")
    route: str = Field(..., description="経路")
    num_transfers: int = Field(..., description="乗換回数")


# 選択理由付きのStationクラス
class StationChoice(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="駅名")
    duration_minutes: int = Field(..., description="最短所要時間（分）")
    route: str = Field(..., description="経路")
    num_transfers: int = Field(..., description="乗換回数")
    choice_reason: str = Field(..., description="選択理由")


class ResponseSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    nearby_stations: List[Station] = Field(..., description="駅近隣主要駅へのアクセス情報")
    major_stations: List[Station] = Field(..., description="都心主要駅へのアクセス情報")
    highlight_stations: List[StationChoice] = Field(
        ..., description="駅近隣主要駅と都心主要駅のアクセス情報の注目ポイントリスト"
    )


# MessagesStateを継承して独立したノード処理に対応したState定義
class AgentState(MessagesState):
    # 入力パラメータ
    station_name: Annotated[str, "基準となる最寄り駅名"]

    # 各ノードの処理結果（独立した処理ステップ）
    nearby_stations: Annotated[List[Station], "近隣主要駅のStation情報リスト"]
    major_stations: Annotated[List[Station], "都心主要駅のStation情報リスト"]
    best_access_stations: Annotated[List[StationChoice], "アクセス良好駅の選択結果"]

    # 処理状態管理
    current_step: Annotated[str, "現在の処理ステップ"]
    processing_errors: Annotated[List[str], "処理中に発生したエラーのリスト"]
