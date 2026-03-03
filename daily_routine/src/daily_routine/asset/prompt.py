"""プロンプトテンプレートの構築・管理."""

import logging

from daily_routine.schemas.scenario import CharacterSpec

logger = logging.getLogger(__name__)

# PoC (poc/image_gen/config.py) で実証済みのスタイル指定
_STYLE_SUFFIX = "semi-realistic style, high quality, studio lighting"
_CHARACTER_BG = "solid bright green chroma key background (#00FF00)"

# ビュー別のポーズ・アングル指定（PoC の VIEW_PROMPTS 構造を踏襲）
# C1-F2-MA 検証で確立された全身条件を反映
_VIEW_PROMPTS: dict[str, str] = {
    "front": "full body shot from head to feet, front view, standing pose, looking at camera",
    "side": "full body shot from head to feet, right side profile view, natural standing pose",
    "back": "full body shot from head to feet, rear view, standing pose, looking away from camera",
}

# C2-R2: 参照画像から環境再現（人物除去）
_C2R2_BASE_PROMPT = (
    "Image 1 shows a photo with people in a specific environment.\n"
    "Recreate ONLY the environment/location from this image, "
    "removing all people completely.\n"
    "Keep: the exact same location type, structures, weather, lighting, "
    "color palette, atmosphere, time of day.\n"
    "Remove: all people, all persons.\n"
    "The scene must have NO people, no persons, completely empty.\n"
    "Composition: eye level camera, suitable for placing "
    "a full-body standing person in the center of the frame.\n"
    "Photo-realistic, natural lighting."
)

# --- C1-F2-MA プロンプト ---

# Flash 融合分析プロンプト（person + clothing → テキスト記述）
FLASH_FUSION_ANALYSIS_PROMPT = (
    "Analyze all images carefully.\n"
    "Image 1 shows a person. Image 2 shows an outfit.\n"
    "Generate a detailed character description that combines:\n"
    "- Physical features from image 1\n"
    "- Outfit from image 2\n"
    "Output only the character description, nothing else."
)

# Identity Block 抽出プロンプト（生成済み画像 → 再現用テキスト）
IDENTITY_BLOCK_EXTRACTION_PROMPT = (
    "Analyze this character and generate a concise identity description\n"
    "covering: age, gender, ethnicity, build, face features, hair, outfit,\n"
    "accessories. This will be used to reproduce this exact character\n"
    "in different scenes. Output only the description."
)

# Pro マルチアングル生成テンプレート
_MA_GENERATION_TEMPLATE = (
    "Image 1 shows the reference person. Image 2 shows the outfit.\n"
    "Generate a photo of the following character:\n"
    "{flash_description}\n"
    "Full body shot from head to feet, standing, {angle_instruction}, "
    "solid bright green chroma key background (#00FF00).\n"
    "The entire body including shoes must be fully visible with space below the feet.\n"
    "Single person only, solo."
)

# マルチアングル生成のアングル別指示
_MA_ANGLE_INSTRUCTIONS: dict[str, str] = {
    "front": "facing the camera",
    "side": "side view (profile)",
    "back": "back view (seen from behind)",
}

# 人物ベース画像自動生成テンプレート（person が null の場合）
_AUTO_PERSON_TEMPLATE = (
    "A person with the following appearance:\n"
    "{appearance}\n"
    "Full body shot from head to feet, standing, facing the camera, "
    "solid bright green chroma key background (#00FF00).\n"
    "The entire body including shoes must be fully visible with space below the feet.\n"
    "Single person only, solo. Photo-realistic, studio lighting."
)

# 服装画像自動生成テンプレート（clothing が null の場合）
_AUTO_CLOTHING_TEMPLATE = (
    "A flat lay photo of the following outfit on a plain white background:\n"
    "{outfit}\n"
    "Neatly arranged, no person wearing it. Studio lighting, high quality."
)

# テキストベース環境生成の構図指示サフィックス
_C2_TEXT_GENERATION_SUFFIX = (
    "\nThe scene must have NO people, no persons, completely empty.\n"
    "Composition: eye level camera, suitable for placing "
    "a full-body standing person in the center of the frame.\n"
    "Photo-realistic, natural lighting."
)


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
                f"{view_prompt}, {_CHARACTER_BG}, {_STYLE_SUFFIX}"
            )

        # モードA: プロンプトのみ（正面画像生成時）
        # CharacterSpec.reference_prompt を基盤として使用
        if view == "front":
            return character.reference_prompt

        # 正面以外でも参照なしの場合（通常は発生しないが安全のため）
        return f"{character.appearance}. {character.outfit}. {view_prompt}, {_CHARACTER_BG}, {_STYLE_SUFFIX}"

    def build_ma_generation_prompt(self, flash_description: str, view: str) -> str:
        """C1-F2-MA マルチアングル生成プロンプトを構築する.

        Args:
            flash_description: Flash 融合分析で生成されたキャラクター記述
            view: 生成するビュー ("front" | "side" | "back")

        Returns:
            画像生成プロンプト
        """
        angle_instruction = _MA_ANGLE_INSTRUCTIONS.get(view)
        if angle_instruction is None:
            msg = "不明なビュー: %s (対応: %s)"
            raise ValueError(msg % (view, ", ".join(_MA_ANGLE_INSTRUCTIONS)))

        return _MA_GENERATION_TEMPLATE.format(
            flash_description=flash_description,
            angle_instruction=angle_instruction,
        )

    def build_auto_person_prompt(self, appearance: str) -> str:
        """人物ベース画像の自動生成プロンプトを構築する.

        Args:
            appearance: CharacterSpec.appearance テキスト

        Returns:
            画像生成プロンプト
        """
        return _AUTO_PERSON_TEMPLATE.format(appearance=appearance)

    def build_auto_clothing_prompt(self, outfit: str) -> str:
        """服装画像の自動生成プロンプトを構築する.

        Args:
            outfit: CharacterSpec.outfit テキスト

        Returns:
            画像生成プロンプト
        """
        return _AUTO_CLOTHING_TEMPLATE.format(outfit=outfit)

    def build_environment_prompt(self, modification: str = "") -> str:
        """C2-R2 / C2-R2-MOD 環境再現プロンプトを構築する.

        Args:
            modification: C2-R2-MOD 修正指示（空なら C2-R2 そのまま）

        Returns:
            画像生成プロンプト
        """
        if modification:
            return f"{_C2R2_BASE_PROMPT}\n{modification}"
        return _C2R2_BASE_PROMPT

    def build_environment_text_prompt(self, image_prompt: str) -> str:
        """テキストベース環境生成プロンプトを構築する.

        Args:
            image_prompt: SceneSpec.image_prompt

        Returns:
            画像生成プロンプト
        """
        return f"{image_prompt}{_C2_TEXT_GENERATION_SUFFIX}"
