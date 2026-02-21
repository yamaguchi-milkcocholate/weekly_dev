"""比較分析スクリプト.

各AIの評価スコアを集約し、メトリクスを算出して比較レポートを生成する。

Usage:
    uv run python poc/video_ai/compare.py [--ais veo,kling,luma,runway]
"""

import argparse
import json
import logging
import statistics
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
ALL_AIS = ["veo", "kling", "luma", "runway"]
SCORE_KEYS = ["face_similarity", "hair_consistency", "outfit_consistency", "body_proportion", "overall_identity"]


def load_scores(ai_name: str) -> dict | None:
    scores_path = BASE_DIR / "evaluation" / f"{ai_name}_scores.json"
    if not scores_path.exists():
        logger.warning("%s: scores file not found (%s)", ai_name, scores_path)
        return None
    return json.loads(scores_path.read_text())


def compute_metrics(scores_data: dict) -> dict:
    """1つのAIの評価結果からメトリクスを算出する."""
    frame_scores = scores_data.get("frame_scores", [])
    if not frame_scores:
        return {"error": "no frame scores"}

    overall_scores = [f["overall_identity"] for f in frame_scores if "overall_identity" in f]
    if not overall_scores:
        return {"error": "no overall_identity scores"}

    metrics = {
        "num_frames": len(frame_scores),
        "overall_identity": {
            "mean": round(statistics.mean(overall_scores), 2),
            "min": min(overall_scores),
            "max": max(overall_scores),
            "stdev": round(statistics.stdev(overall_scores), 2) if len(overall_scores) > 1 else 0.0,
        },
        "per_aspect": {},
    }

    for key in SCORE_KEYS:
        values = [f[key] for f in frame_scores if key in f]
        if values:
            metrics["per_aspect"][key] = {
                "mean": round(statistics.mean(values), 2),
                "min": min(values),
                "max": max(values),
            }

    return metrics


def generate_ranking(ai_metrics: dict[str, dict]) -> list[dict]:
    """overall_identity の平均スコアでランキングを生成する."""
    ranked = []
    for ai, metrics in ai_metrics.items():
        if "error" in metrics:
            continue
        ranked.append({
            "ai": ai,
            "mean_overall_identity": metrics["overall_identity"]["mean"],
            "min_overall_identity": metrics["overall_identity"]["min"],
            "stability": metrics["overall_identity"]["stdev"],
        })
    ranked.sort(key=lambda x: x["mean_overall_identity"], reverse=True)
    for i, item in enumerate(ranked):
        item["rank"] = i + 1
    return ranked


def main(ais: list[str]) -> None:
    ai_metrics: dict[str, dict] = {}

    for ai in ais:
        data = load_scores(ai)
        if data is None:
            continue
        if "error" in data:
            ai_metrics[ai] = {"error": data["error"]}
            continue
        ai_metrics[ai] = compute_metrics(data)
        logger.info("%s: metrics computed", ai)

    if not ai_metrics:
        logger.error("No scores found for any AI. Run evaluate.py first.")
        return

    ranking = generate_ranking(ai_metrics)

    report = {
        "summary": {
            "total_ais_evaluated": len(ai_metrics),
            "ranking": ranking,
        },
        "detailed_metrics": ai_metrics,
    }

    output_path = BASE_DIR / "evaluation" / "comparison_report.json"
    output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False))
    logger.info("Comparison report saved: %s", output_path)

    # コンソールにランキングを表示
    if ranking:
        print("\n=== キャラクター同一性ランキング ===")
        for item in ranking:
            print(f"  #{item['rank']} {item['ai']}: mean={item['mean_overall_identity']}, "
                  f"min={item['min_overall_identity']}, stability(stdev)={item['stability']}")
        print()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="動画生成AI比較分析")
    parser.add_argument("--ais", default=",".join(ALL_AIS), help="対象AI (カンマ区切り)")
    args = parser.parse_args()
    main([a.strip() for a in args.ais.split(",")])
