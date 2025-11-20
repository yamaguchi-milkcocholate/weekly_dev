import json
from typing import Any, Dict, Optional

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import tool
from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import END, StateGraph

import sns_ai_automation_agency.agent.restaurant.schema as schema
import sns_ai_automation_agency.utils as utils


def survey_restaurant_information(station_name: str, num_iterations: int, thread_id: Optional[str] = None) -> dict:
    load_dotenv()

    if thread_id:
        cache = utils.CachePathManager(app_name=thread_id)
        cache_file = cache.file(f"restaurant_survey_{station_name}.json")

        if cache_file.exists():
            with open(cache_file, "r", encoding="utf-8") as f:
                return json.load(f)
    else:
        cache, cache_file = None, None

    # LangGraphワークフロー構築
    workflow = StateGraph(schema.RestaurantSurveyState)

    # ノードの追加
    workflow.add_node("restaurant_survey_node", restaurant_survey_node)
    workflow.add_node("analysis_and_planning_node", analysis_and_planning_node)

    # ワークフローの定義
    workflow.set_entry_point("restaurant_survey_node")

    # 調査実行後は必ず分析へ
    workflow.add_conditional_edges(
        "restaurant_survey_node",
        should_continue_adaptive_survey,
        {"analysis_and_planning_node": "analysis_and_planning_node", END: END},
    )

    # 分析後は継続判定に基づいて次回調査または終了
    workflow.add_conditional_edges(
        "analysis_and_planning_node",
        should_continue_adaptive_survey,
        {"restaurant_survey_node": "restaurant_survey_node", END: END},
    )

    # メモリ設定
    memory = MemorySaver()

    # グラフコンパイル
    agent = workflow.compile(checkpointer=memory)

    initial_state = {
        "station_name": station_name,
        "max_iterations": num_iterations,
        "survey_iteration": 0,
        "messages": [HumanMessage(content=f"{station_name}の適応的飲食店調査を開始してください")],
    }
    config = {"configurable": {"thread_id": f"restaurant_survey_{station_name}.json"}}

    result: schema.RestaurantSurveyState = agent.invoke(initial_state, config)
    result_dict = utils.to_serializable(result)

    if cache:
        with open(cache_file, "w", encoding="utf-8") as f:
            json.dump(result_dict, f, ensure_ascii=False, indent=4)

    return result_dict


@tool
def search_food_areas_with_web_api(
    station_name: str, search_query: str, exclusion_criteria: str = ""
) -> schema.FoodAreaSearchResponse:
    """Web API機能付きモデルで飲食店エリア情報を検索（SNS向け特化、エリア単位の構造化出力）"""
    # gpt-5-search-api を使用してリアルタイム検索（エリア単位の構造化出力）
    search_llm = ChatOpenAI(model="gpt-5-search-api", temperature=0.1)
    structured_llm = search_llm.with_structured_output(schema.FoodAreaSearchResponse)

    search_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
あなたはSNS向け飲食店エリア専門リサーチャーです。
Web検索機能を使って、指定された駅周辺の飲食店エリア情報を事実ベースで調査し、
**エリア単位でまとめた構造化レスポンス**として返してください。


🎯 SNS特化エリア単位調査ポイント：
1. 商店街・食べ歩きエリア・グルメ街の特定
2. エリア内の代表的な飲食店の情報（店舗名・業態・価格帯・営業時間）
3. エリア全体の特徴・雰囲気・コンセプト
4. 駅からのアクセス情報（徒歩時間範囲）
5. エリア全体のSNSアピールポイント（統一感のある内装、街並み、フォトスポット、話題のメニューなど）
6. エリアの話題性・人気度（メディア露出、観光地化、地元密着度など）
7. エリア全体でのSNS投稿価値（テーマ性、回遊性、撮影スポットの豊富さ）
8. 信頼できる情報源（Google口コミ、SNS投稿、観光サイト、グルメサイト、地域情報など）

📋 エリア単位データ要件：
- 各エリアに3-8店舗程度を含める
- エリアの徒歩時間範囲を明確に
- エリアごとのSNS特化要素を具体的に（例：「レトロ商店街の統一看板」「カフェ街の緑豊かな雰囲気」）
- 除外条件が指定されている場合は厳格に適用
- エリア情報の信頼性を評価

**重要**: 個別店舗ではなく、飲食店が集積する「エリア」を中心に調査・整理してください。
            """,
            ),
            (
                "user",
                """
駅名: {station_name}
調査内容: {search_query}
除外条件: {exclusion_criteria}

上記の条件でSNS向け飲食店エリア調査を実行し、**エリア単位でまとめた**構造化レスポンスで返してください。
特に以下を重視：
- エリアごとの飲食店集積状況
- エリア全体のインスタ映えするビジュアル要素
- エリアの統一感・テーマ性・話題性
- 各エリア内の代表店舗情報
- データの信頼性と正確性
            """,
            ),
        ]
    )

    chain = search_prompt | structured_llm
    response: schema.FoodAreaSearchResponse = chain.invoke(
        {
            "station_name": station_name,
            "search_query": search_query,
            "exclusion_criteria": exclusion_criteria or "なし",
        }
    )

    print("  🔍 飲食店エリア検索完了: ")
    print(f"    - 発見エリア数: {response.total_areas_found}")
    print(f"    - 検索カバレッジ: {response.search_area_coverage.strip()}")
    print(f"    - 除外条件適用: {'はい' if response.exclusion_applied else 'いいえ'}")
    print(f"    - データ信頼性: {response.data_reliability}")

    return response


# Node 1: SNS特化飲食店調査実行ノード（LangGraph reducer対応・エリア単位・LLMベースのサマリー生成）
def restaurant_survey_node(state: schema.RestaurantSurveyState) -> schema.RestaurantSurveyState:
    """現在の調査戦略に基づいて飲食店エリア情報を収集（SNS特化・エリア単位）"""
    print(f"🔍 SNS特化飲食店エリア調査実行ノード開始 (第{state['survey_iteration'] + 1}回)")

    # 次回調査の検索パラメータ取得
    search_params = _get_search_params(state)
    # Web API検索実行（エリア単位の構造化出力）
    search_response = search_food_areas_with_web_api.invoke(
        {
            "station_name": search_params["station_name"],
            "search_query": search_params["search_query"],
            "exclusion_criteria": search_params["exclusion_criteria"],
        }
    )

    # LLMを使用してSurveySummaryを生成
    survey_summary = _generate_survey_summary_with_llm(
        state=state, search_response=search_response, search_params=search_params
    )

    # LangGraph reducer対応：新しい要素をreturnで返す
    result = {
        "current_process": "restaurant_survey_node",
        "survey_iteration": state["survey_iteration"] + 1,
        "discovered_areas": survey_summary.new_areas_found,  # 自動的に既存リストに結合される
        "survey_history": [survey_summary],  # 自動的に既存リストに結合される
    }

    print(f"  📚 調査履歴: {len(state['survey_history']) + 1}回分蓄積")

    return result


def _generate_survey_summary_with_llm(
    state: schema.RestaurantSurveyState, search_response: schema.FoodAreaSearchResponse, search_params: Dict[str, Any]
) -> schema.SurveySummary:
    """LLMを使用してSurveySummaryを生成する（with_structured_output使用）"""

    search_result = (
        json.dumps(search_response.model_dump(), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
    )
    survey_history = "\n,".join(
        [
            json.dumps(sh.model_dump(), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
            for sh in state["survey_history"]
        ]
    )

    # 構造化出力を使用するLLM
    summary_llm = ChatOpenAI(model="gpt-5-mini", temperature=0)
    structured_llm = summary_llm.with_structured_output(schema.SurveySummaryGeneration)

    # 構造化出力用プロンプトの構築
    summary_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
調査データを分析し、この回の調査サマリーを構造化された形式で生成してください。

🎯 調査サマリー生成の観点：
1. この回の調査戦略の効果と成果
2. 新規発見したエリア・店舗の特徴と価値
3. SNS観点での発見事項・魅力度
4. 地理的・業態的な発見パターン
5. 前回までとの比較での新規性・独自性
📋 構造化出力要件：
- key_discoveries: この回の主要な発見事項（3-5個の具体的で洞察に富んだ分析）
- geographical_coverage: この回でカバーした地理的範囲の説明
- 具体的でSNS特化観点を重視した内容
- 単純な数値羅列や一般的表現を避ける
            """,
            ),
            (
                "user",
                f"""
【調査情報】
駅名: {state["station_name"]}
調査回数: 第{state["survey_iteration"] + 1}回
調査戦略: {search_params["search_query"]}
除外条件: {search_params.get("exclusion_criteria", "なし")}

【今回の成果】
```json
{search_result}
```

【既存調査履歴】
```json
{survey_history}
```

上記の情報を分析し、この回の調査で得られた重要な発見事項と地理的カバレッジを教えてください。
上記の調査情報を分析し、SNS観点での魅力や前回調査との比較での新規性に注目して、
key_discoveriesとgeographical_coverageを構造化された形式で出力してください。
            """,
            ),
        ]
    )

    # 構造化LLMチェーンを実行
    chain = summary_prompt | structured_llm
    analysis_result: schema.SurveySummaryGeneration = chain.invoke({})

    print("  📝 調査サマリー生成完了: ")
    print(f"    - 新規発見店舗数: {analysis_result.new_restaurants_count}")
    print(f"    - 新規発見エリア: {analysis_result.new_areas_found}")
    print(f"    - 主要な発見事項: {analysis_result.key_discoveries}")
    print(f"    - 地理的カバレッジ: {analysis_result.geographical_coverage.strip()}")

    return schema.SurveySummary(
        iteration_number=state["survey_iteration"] + 1,
        search_strategy=search_params["search_query"],
        new_restaurants_count=analysis_result.new_restaurants_count,
        new_areas_found=analysis_result.new_areas_found,
        key_discoveries=analysis_result.key_discoveries,
        geographical_coverage=analysis_result.geographical_coverage.strip(),
    )


def _get_search_params(state: schema.RestaurantSurveyState) -> Dict[str, Any]:
    """次回調査の検索パラメータを取得（補助関数・エリア中心）"""
    # 初回調査の場合はエリア基本調査
    if state["survey_iteration"] == 0:
        search_query = f"{state['station_name']}周辺の飲食店が集まるエリア・商店街・グルメスポットを調査。SNS映えするエリアを優先し、各エリア内の代表店舗情報も含めて収集"
        exclusion_criteria = ""
        focus_area = f"{state['station_name']}駅周辺全般"
    else:
        # 2回目以降は戦略的調査
        search_query = state["next_plan"].search_query
        exclusion_criteria = state["next_plan"].exclusion_criteria
        focus_area = state["next_plan"].focus_area

    print(f"  📋 調査クエリ: {search_query}")
    print(f"  📍 重点エリア: {focus_area}")
    print(f"   除外条件: {exclusion_criteria or 'なし'}")
    return {
        "station_name": state["station_name"],
        "search_query": search_query,
        "exclusion_criteria": exclusion_criteria,
        "focus_area": focus_area,
    }


# Node 2: 結果分析＆次回戦略立案ノード（累積調査履歴分析機能追加）
def analysis_and_planning_node(state: schema.RestaurantSurveyState) -> schema.RestaurantSurveyState:
    """前回までの調査結果を分析し、次回調査戦略を立案（累積履歴を考慮）"""
    print("🧠 分析＆戦略立案ノード開始（累積調査履歴分析）")

    # 構造化出力を使用するLLM
    analysis_llm = ChatOpenAI(model="gpt-5.1", temperature=0)
    structured_analysis_llm = analysis_llm.with_structured_output(schema.AnalysisNodeResponse)

    # 現在の調査結果をサマリー
    survey_history_summary = []
    for i_survey_history in state["survey_history"]:
        i_survey_history_dump = i_survey_history.model_dump()

        i_mnew_areas_found_summary = "\n".join(
            ["- " + i_new_area_found["area_name"] for i_new_area_found in i_survey_history_dump["new_areas_found"]]
        )
        i_survey_summary = f"""
## 調査回数: 第{i_survey_history_dump["iteration_number"]}回
    【検索クエリ】
    {i_survey_history_dump["search_strategy"]}

    【検索結果で取得できたエリア】
    {i_mnew_areas_found_summary}

    【検索結果の地理的範囲】
    {i_survey_history_dump["geographical_coverage"]}

        """
        survey_history_summary.append(i_survey_summary)

    # 調査履歴の要約生成
    survey_history_summary = "\n".join(survey_history_summary)

    analysis_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
あなたは飲食店調査の戦略アナリストです。
累積的な調査履歴を詳細に分析し、包括的な調査継続判定と次回戦略を決定してください。

累積調査分析観点：
1. 地理的カバレッジ（方角・距離範囲の網羅性）
2. 徒歩時間帯の偏り分析
3. 業態カテゴリの網羅性 
4. 価格帯・客層の多様性
5. SNSコンテンツとしての魅力度
6. 各回の調査戦略の効果分析
7. 未調査領域の特定

継続判定基準：
- 新規情報発見の可能性（地理的・業態的ギャップ）
- 調査品質の向上余地
- SNSコンテンツとしての充実度
- 最大回数との関係

次回戦略立案：
- これまでの調査履歴で見落とした領域
- 戦略的に重要な未調査エリア
- SNS観点で不足している要素
- 除外すべき既調査内容の詳細
- 調査効率を高める具体的アプローチ

結果を以下の形式で出力：
1. 【継続判定】Yes/No + 理由
2. 【累積調査の評価】良好/普通/要改善 + 根拠
3. 【未調査ギャップ分析】具体的な不足領域
4. 【次回戦略】継続の場合の具体的調査方針
            """,
            ),
            (
                "user",
                f"""
駅名: {state["station_name"]}
最大調査回数: {state["max_iterations"]}

{survey_history_summary}

上記の累積調査結果を多角的に分析し、以下を詳細に判定してください：

1. 調査継続の必要性と根拠
2. これまでの調査履歴での戦略効果分析
3. 未調査領域の具体的特定
4. SNSコンテンツ観点での充実度評価
5. 次回調査戦略（継続の場合）

特に累積的な視点で、これまでの調査で取りこぼしている可能性がある領域を重視してください。
            """,
            ),
        ]
    )

    # 構造化分析の実行
    chain = analysis_prompt | structured_analysis_llm
    analysis_result: schema.AnalysisNodeResponse = chain.invoke({})

    print("  🧾 分析＆戦略立案完了: ")
    print(f"    - 調査継続判定: {'継続' if analysis_result.continue_survey else '終了'}")
    print(f"    - 継続・終了理由: {analysis_result.continuation_reason[:100]}...")
    print(f"    - 累積調査評価: {analysis_result.survey_evaluation}")
    print(f"    - 未調査ギャップ: {analysis_result.coverage_gaps}")
    print(f"    - 次回調査方針: {analysis_result.next_strategy.strip()[:100]}...")

    # 構造化出力から継続判定を取得
    should_continue = analysis_result.continue_survey and state["survey_iteration"] < state["max_iterations"]

    result = {}
    if should_continue:
        result["next_plan"] = _generate_next_plan_with_llm(state, analysis_result)
    else:
        result["completion_reason"] = analysis_result.continuation_reason

    result["current_process"] = "analysis_and_planning_node"
    result["should_continue"] = should_continue
    result["current_analysis"] = analysis_result

    return result


def _generate_next_plan_with_llm(
    state: schema.RestaurantSurveyState, analysis_result: schema.AnalysisNodeResponse
) -> schema.NextSurveyPlan:
    """LLMを使用してNextSurveyPlanを生成する（累積調査を考慮）"""

    analysis_detail = (
        json.dumps(analysis_result.model_dump(), indent=2, ensure_ascii=False).replace("{", "{{").replace("}", "}}")
    )

    # 構造化出力を使用するLLM
    plan_llm = ChatOpenAI(model="gpt-5-mini", temperature=0)
    structured_plan_llm = plan_llm.with_structured_output(schema.NextSurveyPlan)

    plan_prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                """
あなたは飲食店調査の戦略プランナーです。
累積的な調査履歴と最新の分析結果を踏まえ、次回調査の具体的な戦略計画を立案してください。
累積調査考慮ポイント：
1. これまでの調査で見落とした可能性のある領域
2. 戦略的に重要な未調査エリア
3. SNS観点で不足している要素
4. 除外すべき既調査内容の詳細
5. 調査効率を高める具体的アプローチ

                """,
            ),
            (
                "user",
                f"""
駅名: {state["station_name"]}
最大調査回数: {state["max_iterations"]}

最新の分析結果:
{analysis_detail}

上記を踏まえ、次回調査の具体的な戦略計画を詳細に立案してください。
`search_query`と`exclusion_criteria`は次回の調査でChatGPTに指示するプロンプトの一部として使用します。

プロンプトは以下の形式です。
```prompt
駅名: station_name
調査内容: search_query
除外条件: exclusion_criteria

上記の条件でSNS向け飲食店エリア調査を実行し、**エリア単位でまとめた**構造化レスポンスで返してください。
特に以下を重視：
- エリアごとの飲食店集積状況
- エリア全体のインスタ映えするビジュアル要素
- エリアの統一感・テーマ性・話題性
- 各エリア内の代表店舗情報
- データの信頼性と正確性
```

`search_query`,`exclusion_criteria`がprompt内で自然に使用できるように200文字以内で出力してください。
                """,
            ),
        ]
    )

    # 構造化プラン生成の実行
    chain = plan_prompt | structured_plan_llm
    next_plan: schema.NextSurveyPlan = chain.invoke({})

    print("  🗺️ 次回調査計画生成完了: ")
    print(f"    - 重点エリア: {next_plan.focus_area}")
    print(f"    - 重点業態: {next_plan.target_categories}")
    print(f"    - 徒歩時間範囲: {next_plan.walking_time_range}")
    print(f"    - SNS重視ポイント: {next_plan.sns_focus_points}")
    print(f"    - 除外条件: {next_plan.exclusion_criteria}")

    return next_plan


# 適応的調査の条件分岐関数
def should_continue_adaptive_survey(state: schema.RestaurantSurveyState) -> str:
    """調査継続の判定"""

    # 最大回数超過の場合は終了
    if state["survey_iteration"] >= state["max_iterations"]:
        return END

    # 初回は`restaurant_survey_node`
    if "current_process" not in state or not state["current_process"]:
        return "restaurant_survey_node"

    # 現在の処理がある場合は、反対側の処理を実行
    if state["current_process"] == "restaurant_survey_node":
        return "analysis_and_planning_node"

    elif state["current_process"] == "analysis_and_planning_node":
        # 継続フラグが False の場合は終了
        if not state["should_continue"]:
            return END
        return "restaurant_survey_node"

    else:
        raise Exception(f"想定されないフローです: {state['current_process']}")
