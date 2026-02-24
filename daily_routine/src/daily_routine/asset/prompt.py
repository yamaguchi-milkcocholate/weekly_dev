"""プロンプトテンプレートの構築・管理."""

import logging

from daily_routine.schemas.scenario import CharacterSpec, SceneSpec

logger = logging.getLogger(__name__)

# PoC (poc/image_gen/config.py) で実証済みのスタイル指定
_STYLE_SUFFIX = "semi-realistic style, high quality, studio lighting"
_WHITE_BG = "plain white background"

# ビュー別のポーズ・アングル指定（PoC の VIEW_PROMPTS 構造を踏襲）
_VIEW_PROMPTS: dict[str, str] = {
    "front": "full body, front view, standing pose, looking at camera",
    "side": "full body, right side profile view, natural standing pose",
    "back": "full body, rear view, standing pose, looking away from camera",
}

# 表情別のプロンプト付加
_EXPRESSION_PROMPTS: dict[str, str] = {
    "smile": "smiling warmly, happy expression",
    "serious": "serious expression, focused look",
    "surprised": "surprised expression, wide eyes, open mouth slightly",
    "sad": "sad expression, downcast eyes",
    "angry": "angry expression, furrowed brows",
}


class PromptBuilder:
    """プロンプトテンプレートの構築・管理."""

    def build_character_prompt(
        self,
        character: CharacterSpec,
        view: str,
        has_reference: bool = False,
    ) -> str:
        """キャラクターのビュー別プロンプトを構築する.

        Args:
            character: キャラクター仕様
            view: 生成するビュー ("front" | "side" | "back")
            has_reference: 参照画像がある場合 True（プロンプト構造が変わる）

        Returns:
            画像生成プロンプト
        """
        view_prompt = _VIEW_PROMPTS.get(view)
        if view_prompt is None:
            msg = "不明なビュー: %s (対応: %s)"
            raise ValueError(msg % (view, ", ".join(_VIEW_PROMPTS)))

        if has_reference:
            # モードB or 自動生成正面画像を参照する場合
            # 参照画像との同一性を強調する指示を付加
            return (
                f"Generate this same character in {view} view. "
                f"Maintain the exact same appearance, clothing, and style as the reference image. "
                f"{character.appearance}. {character.outfit}. "
                f"{view_prompt}, {_WHITE_BG}, {_STYLE_SUFFIX}"
            )

        # モードA: プロンプトのみ（正面画像生成時）
        # CharacterSpec.reference_prompt を基盤として使用
        if view == "front":
            return character.reference_prompt

        # 正面以外でも参照なしの場合（通常は発生しないが安全のため）
        return f"{character.appearance}. {character.outfit}. {view_prompt}, {_WHITE_BG}, {_STYLE_SUFFIX}"

    def build_expression_prompt(
        self,
        character: CharacterSpec,
        expression: str,
        has_reference: bool = False,
    ) -> str:
        """キャラクターの表情バリエーション用プロンプトを構築する.

        Args:
            character: キャラクター仕様
            expression: 表情名 ("smile", "serious", "surprised" 等)
            has_reference: 参照画像がある場合 True

        Returns:
            画像生成プロンプト
        """
        expression_prompt = _EXPRESSION_PROMPTS.get(expression, expression)

        if has_reference:
            return (
                f"Generate this same character with {expression_prompt}. "
                f"Maintain the exact same appearance, clothing, and style as the reference image. "
                f"{character.appearance}. {character.outfit}. "
                f"Upper body, front view, {_WHITE_BG}, {_STYLE_SUFFIX}"
            )

        return (
            f"{character.appearance}. {character.outfit}. "
            f"{expression_prompt}. "
            f"Upper body, front view, {_WHITE_BG}, {_STYLE_SUFFIX}"
        )

    def build_prop_prompt(self, name: str, description: str) -> str:
        """小物の画像生成プロンプトを構築する.

        設計書方針: 白背景、スタジオライティング、商品撮影風

        Args:
            name: 小物名
            description: 小物の説明

        Returns:
            画像生成プロンプト
        """
        return f"{description}. Product photography style, {_WHITE_BG}, {_STYLE_SUFFIX}"

    def build_background_prompt(self, scene: SceneSpec) -> str:
        """背景の画像生成プロンプトを構築する.

        設計書方針: シーンの image_prompt を基盤とし、キャラクター不在・背景のみの指定を付加

        Args:
            scene: シーン仕様

        Returns:
            画像生成プロンプト
        """
        # SceneSpec.image_prompt は既にキャラクター不在の背景用プロンプト
        return scene.image_prompt
