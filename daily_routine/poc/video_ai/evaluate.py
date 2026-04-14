"""LLMベースのキャラクター同一性評価スクリプト.

Gemini (Google AI) でリファレンス画像と抽出フレームを比較し、
同一性スコアをJSON形式で出力する。

Usage:
    uv run python poc/video_ai/evaluate.py [--ais veo,kling,luma,runway]
"""

import argparse
import asyncio
import base64
import json
import logging
import os
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
ALL_AIS = ["veo", "kling", "luma", "runway"]

EVALUATION_PROMPT = """\
以下の2枚の画像を比較してください。
1枚目はキャラクターのリファレンス画像（正解）です。
2枚目はAI動画生成の1フレームです。

以下の観点で1〜10のスコアをつけ、JSON形式で回答してください。

{
  "face_similarity": <顔の特徴の一致度 1-10>,
  "hair_consistency": <髪型・髪色の一致度 1-10>,
  "outfit_consistency": <服装の一致度 1-10>,
  "body_proportion": <体型・プロポーションの一致度 1-10>,
  "overall_identity": <総合的なキャラクター同一性 1-10>,
  "reasoning": "<判定理由の簡潔な説明>"
}

JSONのみを出力してください。"""


def _encode_image(path: Path) -> str:
    return base64.b64encode(path.read_bytes()).decode()


async def evaluate_frame(
    api_key: str,
    reference_path: Path,
    frame_path: Path,
    http_client: httpx.AsyncClient,
) -> dict:
    """1フレームをリファレンス画像と比較評価する."""
    ref_b64 = _encode_image(reference_path)
    frame_b64 = _encode_image(frame_path)

    url = (
        "https://generativelanguage.googleapis.com/v1beta/"
        "models/gemini-2.5-flash:generateContent"
        f"?key={api_key}"
    )

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": EVALUATION_PROMPT},
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": ref_b64,
                        }
                    },
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": frame_b64,
                        }
                    },
                ],
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "temperature": 0,
        },
    }

    resp = await http_client.post(url, json=payload)
    resp.raise_for_status()
    data = resp.json()

    raw = data["candidates"][0]["content"]["parts"][0]["text"]
    return json.loads(raw)


async def evaluate_ai(
    api_key: str,
    ai_name: str,
    reference_path: Path,
    http_client: httpx.AsyncClient,
) -> dict:
    """1つのAIの全フレームを評価する."""
    frames_dir = BASE_DIR / "frames" / ai_name
    frames = sorted(frames_dir.glob("frame_*.png"))

    if not frames:
        logger.warning("%s: no frames found in %s", ai_name, frames_dir)
        return {"ai": ai_name, "error": "no frames found", "frame_scores": []}

    logger.info("%s: evaluating %d frames", ai_name, len(frames))
    frame_scores = []

    for frame in frames:
        logger.info("  evaluating %s", frame.name)
        score = await evaluate_frame(api_key, reference_path, frame, http_client)
        score["frame"] = frame.name
        frame_scores.append(score)

    return {"ai": ai_name, "frame_scores": frame_scores}


async def main(ais: list[str]) -> None:
    api_key = os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI")
    if not api_key:
        logger.error("DAILY_ROUTINE_API_KEY_GOOGLE_AI not set")
        return

    reference_path = BASE_DIR / "reference" / "front.png"
    if not reference_path.exists():
        logger.error("Reference image not found: %s", reference_path)
        return

    eval_dir = BASE_DIR / "evaluation"
    eval_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as http_client:
        for ai in ais:
            result = await evaluate_ai(api_key, ai, reference_path, http_client)
            output_path = eval_dir / f"{ai}_scores.json"
            output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
            logger.info("%s: scores saved -> %s", ai, output_path)

    logger.info("Evaluation complete.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="LLMベースのキャラクター同一性評価")
    parser.add_argument("--ais", default=",".join(ALL_AIS), help="対象AI (カンマ区切り)")
    args = parser.parse_args()
    asyncio.run(main([a.strip() for a in args.ais.split(",")]))
