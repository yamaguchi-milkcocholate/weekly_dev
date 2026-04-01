"""PoC Step 6: AI画像生成の評価ロジック.

Phase 1: 構造維持・スタイル反映・生成品質の3軸評価（レンダリング画像+生成画像の2画像入力）
Phase 2: マルチショット一貫性の評価
"""

import base64
import json
import logging
import os
from pathlib import Path

import httpx
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

EVAL_MODEL = "gemini-3-flash-preview"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


# --- Phase 1: 単体品質評価 ---


class Phase1Score(BaseModel):
    """Phase 1 評価スコア."""

    structure_preservation: int = Field(description="構造維持スコア 0-100")
    style_reflection: int = Field(description="スタイル反映スコア 0-100")
    generation_quality: int = Field(description="生成品質スコア 0-100")
    reasoning: str = Field(description="評価理由")


class Phase1Result(BaseModel):
    """Phase 1 評価結果."""

    camera_id: str
    score: Phase1Score
    render_image: str
    generated_image: str


PHASE1_PROMPT = """\
以下は3Dレンダリング画像（テクスチャなし）をAI画像生成で変換した結果です。

入力:
- 画像1: 3Dレンダリング画像（構造情報、テクスチャなし）
- 画像2: AI生成結果

以下の3軸で0-100のスコアをつけてください:
1. structure_preservation: 家具の位置・壁との距離・空間配置・壁の有無が元のレンダリングと一致しているか。壁が消えたり、存在しない窓・階段・ドアが追加されていたら大幅減点
2. style_reflection: リアルなインテリア写真として自然なテクスチャ・色調・照明が適用されているか
3. generation_quality: リアルさ・自然さ・破綻のなさ

JSONのみ出力してください:
{{"structure_preservation": N, "style_reflection": N, "generation_quality": N, "reasoning": "..."}}"""


# --- Phase 2: 一貫性評価 ---


class Phase2Score(BaseModel):
    """Phase 2 一貫性評価スコア."""

    material_consistency: int = Field(description="マテリアル一貫性 0-100")
    lighting_consistency: int = Field(description="照明一貫性 0-100")
    color_consistency: int = Field(description="色調一貫性 0-100")
    overall_consistency: int = Field(description="総合一貫性 0-100")
    reasoning: str = Field(description="評価理由")


class Phase2Result(BaseModel):
    """Phase 2 一貫性評価結果."""

    score: Phase2Score
    image_count: int


PHASE2_PROMPT = """\
以下の画像は、同じ部屋を異なるカメラアングルから撮影したものです。
すべて同一のAI画像生成サービスで生成されました。

これらの画像が「同じ部屋に見えるか」を以下の観点で0-100のスコアをつけてください:
1. material_consistency: 壁・床・家具のマテリアル（素材感）が統一されているか
2. lighting_consistency: 照明の色温度・明るさ・影の方向が統一されているか
3. color_consistency: 全体の色調・カラーパレットが統一されているか
4. overall_consistency: 総合的に同じ部屋に見えるか

JSONのみ出力してください:
{{"material_consistency": N, "lighting_consistency": N, "color_consistency": N, "overall_consistency": N, "reasoning": "..."}}"""


# --- 共通ユーティリティ ---


def _encode_image_inline(image_path: Path) -> dict:
    """Gemini API用の inline_data パートを構築する."""
    data = image_path.read_bytes()
    suffix = image_path.suffix.lstrip(".")
    mime = f"image/{suffix}" if suffix != "jpg" else "image/jpeg"
    return {
        "inline_data": {
            "mime_type": mime,
            "data": base64.b64encode(data).decode("utf-8"),
        }
    }


def _call_gemini(parts: list[dict], api_key: str) -> str:
    """Gemini APIを呼び出し、テキストレスポンスを返す."""
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "temperature": 0.0,
            "responseModalities": ["TEXT"],
        },
    }

    url = f"{GEMINI_BASE_URL}/models/{EVAL_MODEL}:generateContent"

    with httpx.Client(timeout=httpx.Timeout(60.0)) as client:
        resp = client.post(
            url,
            json=payload,
            headers={"x-goog-api-key": api_key},
        )
        if resp.status_code >= 400:
            logger.error("Gemini 評価API エラー: status=%d, body=%s", resp.status_code, resp.text)
        resp.raise_for_status()

    result = resp.json()
    candidates = result.get("candidates", [])
    for candidate in candidates:
        content = candidate.get("content", {})
        parts_resp = content.get("parts", [])
        for part in parts_resp:
            if "text" in part:
                return part["text"]

    msg = "Gemini: テキストレスポンスが取得できませんでした"
    raise RuntimeError(msg)


def _parse_json_response(text: str) -> dict:
    """GeminiレスポンスからJSON部分を抽出してパースする."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    text = text.strip()
    return json.loads(text)


# --- Phase 1 評価 ---


def evaluate_phase1(
    camera_id: str,
    render_image: Path,
    generated_image: Path,
    api_key: str | None = None,
) -> Phase1Result:
    """単体品質を評価する（構造維持・スタイル反映・生成品質）."""
    key = api_key or os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI", "")

    parts = [
        {"text": PHASE1_PROMPT},
        {"text": "\n画像1（3Dレンダリング）:"},
        _encode_image_inline(render_image),
        {"text": "\n画像2（AI生成結果）:"},
        _encode_image_inline(generated_image),
    ]

    response_text = _call_gemini(parts, key)
    score_data = _parse_json_response(response_text)
    score = Phase1Score(**score_data)

    logger.info(
        "%s 評価: structure=%d, style=%d, quality=%d",
        camera_id,
        score.structure_preservation, score.style_reflection, score.generation_quality,
    )

    return Phase1Result(
        camera_id=camera_id,
        score=score,
        render_image=str(render_image),
        generated_image=str(generated_image),
    )


# --- Phase 2 評価 ---


def evaluate_phase2(
    generated_images: list[Path],
    api_key: str | None = None,
) -> Phase2Result:
    """マルチショット一貫性を評価する."""
    key = api_key or os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI", "")

    parts: list[dict] = [{"text": PHASE2_PROMPT}]
    for i, image_path in enumerate(generated_images, 1):
        parts.append({"text": f"\n画像{i}:"})
        parts.append(_encode_image_inline(image_path))

    response_text = _call_gemini(parts, key)
    score_data = _parse_json_response(response_text)
    score = Phase2Score(**score_data)

    logger.info(
        "一貫性評価: material=%d, lighting=%d, color=%d, overall=%d",
        score.material_consistency, score.lighting_consistency,
        score.color_consistency, score.overall_consistency,
    )

    return Phase2Result(
        score=score,
        image_count=len(generated_images),
    )
