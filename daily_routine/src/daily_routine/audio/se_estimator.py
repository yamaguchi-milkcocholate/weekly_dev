"""LLM による SE 推定."""

import logging

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from daily_routine.schemas.scenario import SceneSpec

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3


class SEEstimation(BaseModel):
    """1つの SE の推定結果."""

    se_name: str = Field(description="SE の名前（英語、検索キーワードとして使用）")
    scene_number: int = Field(description="挿入するシーン番号")
    trigger_description: str = Field(description="トリガーとなる動作/物体の説明")


class SEEstimationList(BaseModel):
    """SE 推定結果のリスト（Structured Output 用）."""

    estimations: list[SEEstimation]


_SYSTEM_PROMPT = """あなたは動画の効果音（SE）設計の専門家です。
以下のシーン情報から、各シーンに最適な効果音を割り当ててください。

## ルール:
- 1シーンあたり最大2つの SE
- SE 名は英語の検索キーワードとして使えるもの（例: "footsteps", "door open"）
- trigger_description にはどの動作/物体が SE のトリガーかを日本語で記載
- 環境音（雑踏、鳥の声等）も考慮
- 日常動作に対応する SE を優先（足音、ドア、キーボード等）"""


class SEEstimator:
    """LLM でシーン情報から必要な SE を推定する."""

    def __init__(self, api_key: str, max_se_per_scene: int = 2) -> None:
        self._api_key = api_key
        self._max_se_per_scene = max_se_per_scene

    async def estimate(
        self,
        scenes: list[SceneSpec],
        se_usage_points: list[str],
    ) -> list[SEEstimation]:
        """シナリオの各シーンから必要な SE を推定する.

        Args:
            scenes: シナリオの全シーン仕様
            se_usage_points: トレンドでの SE 使用パターン

        Returns:
            各シーンに割り当てる SE の推定リスト
        """
        user_prompt = self._build_prompt(scenes, se_usage_points)

        client = genai.Client(api_key=self._api_key)

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                response = await client.aio.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=user_prompt,
                    config=types.GenerateContentConfig(
                        system_instruction=_SYSTEM_PROMPT,
                        response_mime_type="application/json",
                        response_schema=SEEstimationList,
                    ),
                )

                result = SEEstimationList.model_validate_json(response.text)
                logger.info("SE 推定完了: %d件", len(result.estimations))
                return result.estimations

            except Exception:
                if attempt < _MAX_RETRIES:
                    logger.warning("SE 推定リトライ (%d/%d)", attempt, _MAX_RETRIES, exc_info=True)
                else:
                    logger.error("SE 推定失敗（リトライ上限）")
                    raise

        return []  # unreachable, for type checker

    def _build_prompt(
        self,
        scenes: list[SceneSpec],
        se_usage_points: list[str],
    ) -> str:
        """SE 推定用のプロンプトを構築する.

        Args:
            scenes: シナリオの全シーン仕様
            se_usage_points: トレンドでの SE 使用パターン

        Returns:
            構築されたプロンプト文字列
        """
        parts: list[str] = []

        parts.append("## トレンドでの SE 使用パターン:")
        for point in se_usage_points:
            parts.append(f"- {point}")

        parts.append("")
        parts.append("## シーン一覧:")
        for scene in scenes:
            parts.append(f"シーン{scene.scene_number}: {scene.situation} / テロップ: {scene.caption_text}")

        parts.append("")
        parts.append(f"## 制約: 1シーンあたり最大{self._max_se_per_scene}つの SE")

        return "\n".join(parts)
