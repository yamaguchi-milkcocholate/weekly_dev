"""画像生成AI比較検証の実行スクリプト（LangGraphワークフロー）."""

import asyncio
import json
import logging
from typing import TypedDict

from langgraph.graph import END, START, StateGraph

from .clients.base import GenerationResult, ImageGeneratorClient
from .clients.dalle import DalleClient
from .clients.gemini import GeminiClient
from .clients.stability import StabilityClient
from .config import AI_NAMES, EVALUATION_DIR, GENERATED_DIR, NEGATIVE_PROMPT, VIEW_PROMPTS, build_prompt
from .evaluate import AIEvaluationResult, evaluate_all

logger = logging.getLogger(__name__)


# --- LangGraph State ---


class EvaluationState(TypedDict):
    """ワークフローの状態."""

    generation_results: dict[str, list[dict]]
    evaluation_results: list[dict]
    report: dict


# --- ノード関数 ---


async def generate_images(state: EvaluationState) -> dict:
    """全AIで画像を生成するノード."""
    clients: dict[str, ImageGeneratorClient] = {
        "stability": StabilityClient(output_dir=GENERATED_DIR / "stability"),
        "dalle": DalleClient(output_dir=GENERATED_DIR / "dalle"),
        "gemini": GeminiClient(output_dir=GENERATED_DIR / "gemini"),
    }

    generation_results: dict[str, list[dict]] = {}

    for dir_name, client in clients.items():
        ai_name = AI_NAMES[dir_name]
        logger.info("=== %s: 画像生成開始 ===", ai_name)
        results = []

        for view in VIEW_PROMPTS:
            prompt = build_prompt(view)
            from .clients.base import GenerationRequest

            request = GenerationRequest(
                prompt=prompt,
                negative_prompt=NEGATIVE_PROMPT if dir_name == "stability" else None,
            )

            try:
                result = await client.generate(request)
                # ファイル名をビュー名に変更
                target_path = GENERATED_DIR / dir_name / view.filename
                if result.image_path != target_path:
                    result.image_path.rename(target_path)
                    result = GenerationResult(
                        image_path=target_path,
                        generation_time_sec=result.generation_time_sec,
                        model_name=result.model_name,
                        cost_usd=result.cost_usd,
                        metadata=result.metadata,
                    )
                results.append(result.model_dump(mode="json"))
                logger.info("  %s (%s): 生成完了", view.description, view.view_name)
            except Exception:
                logger.exception("  %s (%s): 生成失敗", view.description, view.view_name)
                raise

        generation_results[dir_name] = results
        logger.info("=== %s: 全画像生成完了 ===", ai_name)

    return {"generation_results": generation_results}


async def evaluate_images(state: EvaluationState) -> dict:
    """GPT-4o Visionで全AIの画像を評価するノード."""
    logger.info("=== GPT-4o Vision 評価開始 ===")

    results = await evaluate_all(GENERATED_DIR)
    evaluation_results = [r.model_dump(mode="json") for r in results]

    # 評価結果をJSONファイルに保存
    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    eval_path = EVALUATION_DIR / "ai_evaluation.json"
    eval_path.write_text(json.dumps(evaluation_results, ensure_ascii=False, indent=2))
    logger.info("評価結果を保存: %s", eval_path)

    return {"evaluation_results": evaluation_results}


async def generate_report(state: EvaluationState) -> dict:
    """総合評価レポートを生成するノード."""
    logger.info("=== 総合評価レポート生成 ===")

    evaluation_results = [AIEvaluationResult(**r) for r in state["evaluation_results"]]
    generation_results = state["generation_results"]

    # AI別のサマリーを構築
    ai_summaries = []
    for eval_result in evaluation_results:
        dir_name = next(k for k, v in AI_NAMES.items() if v == eval_result.ai_name)
        gen_results = [GenerationResult(**r) for r in generation_results.get(dir_name, [])]

        total_time = sum(r.generation_time_sec for r in gen_results)
        total_cost = sum(r.cost_usd for r in gen_results if r.cost_usd)

        ai_summaries.append(
            {
                "ai_name": eval_result.ai_name,
                "model": gen_results[0].model_name if gen_results else "unknown",
                "scores": {
                    "facial_consistency": eval_result.score.facial_consistency,
                    "outfit_consistency": eval_result.score.outfit_consistency,
                    "style_consistency": eval_result.score.style_consistency,
                    "overall_quality": eval_result.score.overall_quality,
                },
                "weighted_score": (
                    eval_result.score.facial_consistency * 0.30
                    + eval_result.score.outfit_consistency * 0.20
                    + eval_result.score.style_consistency * 0.30
                    + eval_result.score.overall_quality * 0.20
                ),
                "reasoning": eval_result.score.reasoning,
                "total_generation_time_sec": round(total_time, 1),
                "total_cost_usd": round(total_cost, 3),
                "images_generated": len(gen_results),
            }
        )

    # 加重スコアでランキング
    ai_summaries.sort(key=lambda x: x["weighted_score"], reverse=True)

    report = {
        "title": "画像生成AI比較検証レポート",
        "evaluation_method": {
            "ai_evaluation": "GPT-4o Vision による3枚セットの一貫性評価",
            "scoring": {
                "facial_consistency": "顔の一貫性 (重み: 30%)",
                "outfit_consistency": "服装の一貫性 (重み: 20%)",
                "style_consistency": "画風の一貫性 (重み: 30%)",
                "overall_quality": "総合品質 (重み: 20%)",
            },
        },
        "results": ai_summaries,
        "ranking": [s["ai_name"] for s in ai_summaries],
        "recommendation": ai_summaries[0]["ai_name"] if ai_summaries else None,
    }

    # レポートをJSONファイルに保存
    EVALUATION_DIR.mkdir(parents=True, exist_ok=True)
    report_path = EVALUATION_DIR / "report.json"
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2))
    logger.info("総合評価レポートを保存: %s", report_path)

    return {"report": report}


# --- LangGraphワークフロー構築 ---


def build_workflow() -> StateGraph:
    """評価ワークフローを構築する."""
    workflow = StateGraph(EvaluationState)

    workflow.add_node("generate_images", generate_images)
    workflow.add_node("evaluate_images", evaluate_images)
    workflow.add_node("generate_report", generate_report)

    workflow.add_edge(START, "generate_images")
    workflow.add_edge("generate_images", "evaluate_images")
    workflow.add_edge("evaluate_images", "generate_report")
    workflow.add_edge("generate_report", END)

    return workflow


def build_evaluation_only_workflow() -> StateGraph:
    """評価のみのワークフロー（画像生成済みの場合）."""
    workflow = StateGraph(EvaluationState)

    workflow.add_node("evaluate_images", evaluate_images)
    workflow.add_node("generate_report", generate_report)

    workflow.add_edge(START, "evaluate_images")
    workflow.add_edge("evaluate_images", "generate_report")
    workflow.add_edge("generate_report", END)

    return workflow


async def run_full_evaluation() -> dict:
    """全ステップを実行する."""
    workflow = build_workflow()
    app = workflow.compile()

    initial_state: EvaluationState = {
        "generation_results": {},
        "evaluation_results": [],
        "report": {},
    }

    result = await app.ainvoke(initial_state)
    return result["report"]


async def run_evaluation_only() -> dict:
    """評価のみ実行する（画像生成済みの場合）."""
    # 既存の生成結果からgeneration_resultsを構築
    generation_results: dict[str, list[dict]] = {}
    for dir_name in AI_NAMES:
        ai_dir = GENERATED_DIR / dir_name
        if ai_dir.exists():
            results = []
            for view in VIEW_PROMPTS:
                path = ai_dir / view.filename
                if path.exists():
                    results.append(
                        GenerationResult(
                            image_path=path,
                            generation_time_sec=0.0,
                            model_name="unknown",
                            cost_usd=None,
                        ).model_dump(mode="json")
                    )
            generation_results[dir_name] = results

    workflow = build_evaluation_only_workflow()
    app = workflow.compile()

    initial_state: EvaluationState = {
        "generation_results": generation_results,
        "evaluation_results": [],
        "report": {},
    }

    result = await app.ainvoke(initial_state)
    return result["report"]


def main() -> None:
    """CLIエントリーポイント."""
    import argparse

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")

    parser = argparse.ArgumentParser(description="画像生成AI比較検証")
    parser.add_argument(
        "--evaluate-only",
        action="store_true",
        help="評価のみ実行（画像は既に生成済み）",
    )
    args = parser.parse_args()

    if args.evaluate_only:
        report = asyncio.run(run_evaluation_only())
    else:
        report = asyncio.run(run_full_evaluation())

    print("\n=== 総合評価レポート ===")
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
