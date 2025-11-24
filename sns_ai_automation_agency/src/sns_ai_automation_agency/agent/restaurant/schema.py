from typing import Annotated, List

from langgraph.graph import MessagesState
from pydantic import BaseModel, ConfigDict, Field


# LangGraph用のカスタムreducer関数（説明文付き）
def merge_survey_history(existing: List, new: List) -> List:
    """各回の調査サマリー履歴を結合する"""
    return existing + new


def merge_areas(existing: List, new: List) -> List:
    """発見した飲食店エリアのリストを結合する"""
    return existing + new


def merge_errors(existing: List, new: List) -> List:
    """処理エラーのリストを結合する"""
    return existing + new


# 飲食店情報のPydanticモデル
class Restaurant(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    name: str = Field(..., description="店舗名")
    category: str = Field(..., description="業態カテゴリ（カフェ、レストラン、居酒屋など）")
    walking_minutes: int = Field(..., description="駅からの徒歩時間（分）")
    location: str = Field(..., description="具体的な場所・住所")
    area_name: str = Field(..., description="所属するエリア名（商店街名など）")
    features: List[str] = Field(..., description="特徴・売りポイント")
    price_range: str = Field(..., description="価格帯（低/中/高）")
    business_hours: str = Field(..., description="営業時間")
    sns_appeal_points: List[str] = Field(..., description="SNSアピールポイント（映えるポイント、話題性など）")
    source_url: str = Field(default="", description="情報源URL")


# エリア情報の集約モデル
class FoodArea(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    area_name: str = Field(..., description="エリア名")
    walking_minutes_range: str = Field(..., description="駅からの徒歩時間範囲（例: 3-7分）")
    main_categories: List[str] = Field(..., description="主要な飲食店カテゴリ")
    area_characteristics: str = Field(..., description="エリアの特徴・雰囲気")
    sns_highlights: List[str] = Field(..., description="SNS発信用のエリアハイライト")
    instagrammable_spots: List[str] = Field(..., description="インスタ映えするスポット・特徴")
    restaurants: List[Restaurant] = Field(..., description="エリア内の飲食店リスト")


# 各回の調査サマリー
class SurveySummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    iteration_number: int = Field(..., description="調査回数")
    search_strategy: str = Field(..., description="その回の調査戦略")
    new_restaurants_count: int = Field(..., description="新規発見店舗数")
    new_areas_found: List[FoodArea] = Field(..., description="新規発見エリア名リスト")
    key_discoveries: List[str] = Field(..., description="その回の主要発見事項")
    geographical_coverage: str = Field(..., description="その回でカバーした地理的範囲")


# LLM用の調査サマリー生成レスポンス
class SurveySummaryGeneration(BaseModel):
    """調査サマリー生成用の構造化レスポンス"""

    model_config = ConfigDict(from_attributes=True)

    new_restaurants_count: int = Field(..., description="この回で新たに発見した店舗数")
    new_areas_found: List[FoodArea] = Field(
        ..., description="この回で新たに発見したエリア名リスト (重複は除外すること)"
    )
    key_discoveries: List[str] = Field(..., description="この回の主要な発見事項（3-5個の具体的な洞察）")
    geographical_coverage: str = Field(..., description="地理的カバレッジの説明（この回でカバーした範囲）")


# LLM用の分析ノードレスポンス
class AnalysisNodeResponse(BaseModel):
    """分析ノード用の構造化レスポンス"""

    model_config = ConfigDict(from_attributes=True)

    continue_survey: bool = Field(..., description="調査を継続すべきかどうか")
    continuation_reason: str = Field(..., description="継続・終了の理由")
    survey_evaluation: str = Field(..., description="累積調査の評価（良好/普通/要改善）")
    coverage_gaps: List[str] = Field(..., description="調査不足と思われる領域")
    next_strategy: str = Field(..., description="次回調査の具体的方針（継続の場合）")
    strategic_rationale: str = Field(..., description="戦略的根拠")
    priority_gaps: List[str] = Field(..., description="優先的に埋めるべき調査ギャップ")


# 調査結果の分析情報
class SurveyAnalysis(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    geographical_coverage: str = Field(..., description="地理的カバレッジ分析（方角・範囲）")
    walking_time_distribution: str = Field(..., description="徒歩時間分布の傾向")
    category_distribution: str = Field(..., description="業態カテゴリの分布状況")
    sns_content_potential: str = Field(..., description="SNSコンテンツとしてのポテンシャル分析")
    coverage_gaps: List[str] = Field(..., description="調査不足と思われる領域")
    next_survey_strategy: str = Field(..., description="次回調査の推奨戦略")
    # 新規追加：累積調査の要約
    cumulative_summary: str = Field(..., description="初回〜現在までの調査全体の要約")
    unexplored_potential: List[str] = Field(..., description="未調査の可能性が高い領域・業態・条件")


# 次回調査指示
class NextSurveyPlan(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    focus_area: str = Field(..., description="重点調査エリア（方角・距離）")
    target_categories: List[str] = Field(..., description="重点調査する業態")
    walking_time_range: str = Field(..., description="重点調査する徒歩時間範囲")
    sns_focus_points: List[str] = Field(..., description="SNS観点で重視する調査ポイント")
    exclusion_criteria: str = Field(..., description="既に調査済みのため除外する条件")
    search_query: str = Field(
        ...,
        description="次回調査用の検索クエリ（調査エリア・業態・徒歩分数・SNS観点をまとめる）",
    )
    # 新規追加：累積調査を考慮した戦略的要素
    strategic_rationale: str = Field(..., description="累積調査結果を踏まえた戦略的根拠")
    priority_gaps: List[str] = Field(..., description="優先的に埋めるべき調査ギャップ")


# MessagesStateを継承したエージェント状態管理（説明文付きLangGraph reducer使用）
class RestaurantSurveyState(MessagesState):
    # 入力パラメータ
    station_name: Annotated[str, "調査対象の駅名"]
    max_iterations: Annotated[int, "最大調査回数"]

    # 調査結果の蓄積（説明文付きカスタムreducerで自動結合）
    survey_iteration: Annotated[int, "現在の調査回数"]
    discovered_areas: Annotated[List[FoodArea], merge_areas]

    # 調査履歴の管理（説明文付きカスタムreducerで自動結合）
    survey_history: Annotated[List[SurveySummary], merge_survey_history]

    # 各イテレーションの分析結果
    current_analysis: Annotated[SurveyAnalysis, "現在の調査結果分析"]
    next_plan: Annotated[NextSurveyPlan, "次回調査計画"]

    # 制御フラグ
    current_process: Annotated[str, "現在の処理名"]
    should_continue: Annotated[bool, "調査を継続するか"]
    completion_reason: Annotated[str, "調査完了の理由"]
    processing_errors: Annotated[List[str], merge_errors]


# 構造化出力用のResponseSchema（FoodArea中心）
class FoodAreaSearchResponse(BaseModel):
    """飲食店エリア検索結果の構造化レスポンス"""

    model_config = ConfigDict(from_attributes=True)

    discovered_areas: List[FoodArea] = Field(..., description="発見した飲食店エリアのリスト")
    search_summary: str = Field(..., description="検索結果の要約")
    total_areas_found: int = Field(..., description="発見したエリア総数")
    search_area_coverage: str = Field(..., description="検索でカバーしたエリアの説明")
    sns_highlights: List[str] = Field(..., description="特にSNS映えする要素のハイライト")
    exclusion_applied: bool = Field(..., description="除外条件が適用されたかどうか")
    data_reliability: str = Field(..., description="データの信頼性評価（高/中/低）")
