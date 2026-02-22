"""Geminiを使った画像生成AI評価ロジック."""

import base64
import json
import logging
import os
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from pydantic import BaseModel

logger = logging.getLogger(__name__)

EVALUATION_PROMPT = """\
以下の3枚の画像は、同一のキャラクター設定から異なるポーズ（正面・横向き・斜め後ろ）で生成されたものです。
3枚の画像を比較し、以下の観点でスコアをつけてください。

キャラクター設定:
- 25歳の日本人女性
- ダークブラウンのセミロングヘア（毛先内巻き）
- ブラウンのアーモンド型の目
- 白い襟付きブラウス、ネイビーのタイトスカート（膝丈）
- ベージュのパンプス、小さなゴールドピアス、腕時計
- セミリアリスティックなスタイル

以下のJSON形式で回答してください。スコアは0〜100の整数です。
```json
{
  "facial_consistency": <3枚間での顔の特徴の一貫性 0-100>,
  "outfit_consistency": <3枚間での服装の一貫性 0-100>,
  "style_consistency": <3枚間での画風・トーンの一貫性 0-100>,
  "overall_quality": <画像の総合品質 0-100>,
  "reasoning": "<評価理由の簡潔な説明>"
}
```

JSONのみを出力してください。"""


class AIEvaluationScore(BaseModel):
    """Geminiによる評価スコア."""

    facial_consistency: int
    outfit_consistency: int
    style_consistency: int
    overall_quality: int
    reasoning: str


class AIEvaluationResult(BaseModel):
    """1つのAIに対する評価結果."""

    ai_name: str
    score: AIEvaluationScore
    image_paths: list[Path]


def _encode_image_to_base64(image_path: Path) -> str:
    """画像をBase64エンコードする."""
    return base64.b64encode(image_path.read_bytes()).decode("utf-8")


async def evaluate_image_set(
    ai_name: str,
    image_paths: list[Path],
    api_key: str | None = None,
) -> AIEvaluationResult:
    """3枚の画像セットをGeminiで評価する."""
    google_api_key = api_key or os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI", "")

    llm = ChatGoogleGenerativeAI(
        model="gemini-3-pro-preview",
        google_api_key=google_api_key,
        temperature=0.0,
    )

    # マルチモーダルメッセージを構築
    content = [{"type": "text", "text": EVALUATION_PROMPT}]

    labels = ["1枚目（正面）", "2枚目（横向き）", "3枚目（斜め後ろ）"]
    for label, path in zip(labels, image_paths):
        b64 = _encode_image_to_base64(path)
        content.append({"type": "text", "text": f"\n{label}:"})
        content.append(
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}", "detail": "high"},
            }
        )

    message = HumanMessage(content=content)
    response = await llm.ainvoke([message])

    # レスポンスからJSONを抽出
    raw_content = response.content
    if isinstance(raw_content, list):
        response_text = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in raw_content)
    else:
        response_text = raw_content
    response_text = response_text.strip()
    if response_text.startswith("```"):
        response_text = response_text.split("```")[1]
        if response_text.startswith("json"):
            response_text = response_text[4:]
    response_text = response_text.strip()

    score_data = json.loads(response_text)
    score = AIEvaluationScore(**score_data)

    logger.info(
        "%s 評価完了: facial=%d, outfit=%d, style=%d, quality=%d",
        ai_name,
        score.facial_consistency,
        score.outfit_consistency,
        score.style_consistency,
        score.overall_quality,
    )

    return AIEvaluationResult(
        ai_name=ai_name,
        score=score,
        image_paths=image_paths,
    )


async def evaluate_all(
    generated_dir: Path,
    api_key: str | None = None,
) -> list[AIEvaluationResult]:
    """全AIの画像セットを評価する."""
    from .config import AI_NAMES, VIEW_PROMPTS

    results = []

    for dir_name, ai_name in AI_NAMES.items():
        ai_dir = generated_dir / dir_name
        if not ai_dir.exists():
            logger.warning("ディレクトリが見つかりません: %s", ai_dir)
            continue

        # ビュー名でソートして正面・横・背面の順で取得
        image_paths = []
        for view in VIEW_PROMPTS:
            path = ai_dir / view.filename
            if path.exists():
                image_paths.append(path)
            else:
                logger.warning("画像が見つかりません: %s", path)

        if len(image_paths) != 3:
            logger.warning("%s: 3枚の画像が揃っていません（%d枚）", ai_name, len(image_paths))
            continue

        result = await evaluate_image_set(ai_name, image_paths, api_key=api_key)
        results.append(result)

    return results
