"""Phase A-4: スタイル転写（B5）プロンプト最適化.

seed 画像の色味・照明・雰囲気を参考にしつつ、独自キャラクター＋独自シーンで
新規画像を生成するベストプラクティスを確立する。

B1〜B3 が seed を直接編集する I2I タスクだったのに対し、B5 は seed の雰囲気を
参考に「新規に生成する」タスク。

検証の核心:
- 参照画像ベース vs テキストのみ: どちらがスタイル再現度が高いか
- スタイル要素の明示化: 6属性分解で精度が上がるか
- Visual DNA 抽出: 2段階手法は有効か
- キャラクター参照との共存: スタイル + キャラクターの2枚入力で両方を反映できるか
- 構図リークの制御: seed の構図がコピーされる問題を防げるか

8パターン × 3seed = 24生成。
"""

from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_a4"
REPO_ROOT = Path(__file__).resolve().parents[2]

SEED_CAPTURE_DIR = REPO_ROOT / "seeds" / "captures" / "tamachan_life_"
CHARACTER_REF = BASE_DIR / "reference" / "front.png"

# --- Gemini 定数 ---
GEMINI_MODEL = "gemini-3-pro-image-preview"
COST_PER_IMAGE = 0.04
ASPECT_RATIO = "9:16"

# --- 検証対象の seed 画像（スタイルのソースとして使用） ---
SEED_IMAGES: list[str] = [
    "1.png",  # 早朝デスク・暖色間接照明（暖色系、低照度、親密な雰囲気）
    "4.png",  # 鏡越し全身・自然光（ニュートラル、全身構図、日常感）
    "8.png",  # カフェPC作業・レンガ壁（暖色系、奥行きある構図、落ち着いた雰囲気）
]

# --- キャラクター仕様 ---
CHARACTER_IDENTITY_BLOCK = (
    "a young Japanese woman, mid 20s, slender build. "
    "Wavy dark brown shoulder-length hair, soft round eyes, fair skin. "
    "Wearing a beige V-neck blouse, light gray pencil skirt, "
    "a delicate gold necklace, beige flat shoes."
)

# --- 生成シーン（全パターン共通、seed と意図的に異なる構図） ---
SCENE_DESCRIPTION = (
    "A young woman standing on a train station platform, waiting for a morning commuter train. "
    "She is sitting on a platform bench, looking at her smartphone. "
    "Morning rush hour, other commuters visible in the background."
)


# =============================================================================
# パターン定義
# =============================================================================


@dataclass
class StylePattern:
    """スタイル転写実験パターン."""

    id: str
    name: str
    prompt: str
    description: str = ""
    uses_seed_image: bool = True  # seed 画像を参照として渡すか
    uses_extra_ref: bool = False  # 追加の環境参照画像を使うか
    is_two_stage: bool = False  # 2段階手法（Visual DNA 抽出）か
    visual_dna_extraction_prompt: str = ""  # Step 1 のスタイル抽出プロンプト
    extra_ref_images: list[str] = field(default_factory=list)


# --- S1: テキストのみ（ベースライン） ---
PATTERN_S1 = StylePattern(
    id="S1",
    name="テキストのみ（ベースライン）",
    description="シーン記述 + Identity Block のみ。スタイル指定なし。品質のベースライン",
    uses_seed_image=False,
    prompt=(
        "Image 1 shows the target character. "
        f"Generate a new 9:16 vertical scene: {SCENE_DESCRIPTION} "
        f"The person in the scene is the character from Image 1: {CHARACTER_IDENTITY_BLOCK} "
        "MUST preserve the character identity from Image 1 exactly. "
        "Single person only, solo."
    ),
)

# --- S2: テキストでスタイル指定 ---
PATTERN_S2 = StylePattern(
    id="S2",
    name="テキストでスタイル指定",
    description="スタイルを言語化して指定。参照画像なしでどこまで再現できるか",
    uses_seed_image=False,
    prompt=(
        "Image 1 shows the target character. "
        f"Generate a new 9:16 vertical scene: {SCENE_DESCRIPTION} "
        f"The person in the scene is the character from Image 1: {CHARACTER_IDENTITY_BLOCK} "
        "Visual style: warm amber tones, soft golden hour lighting from camera-left, "
        "cinematic lifestyle photography, shallow depth of field, "
        "muted earth tone color palette, intimate and cozy mood, subtle film grain. "
        "MUST preserve the character identity from Image 1 exactly. "
        "Single person only, solo."
    ),
)

# --- S3: seed 参照 + 簡潔指示 ---
PATTERN_S3 = StylePattern(
    id="S3",
    name="seed参照 + 簡潔指示",
    description="'Use the style of Image 1' と簡潔に指示。最小限のスタイル転写指示",
    uses_seed_image=True,
    prompt=(
        "Image 1 is the style reference. Image 2 shows the target character. "
        f"Generate a new 9:16 vertical scene in the style of Image 1: {SCENE_DESCRIPTION} "
        f"The person in the scene is the character from Image 2: {CHARACTER_IDENTITY_BLOCK} "
        "MUST preserve the character identity from Image 2 exactly. "
        "Single person only, solo."
    ),
)

# --- S4: seed 参照 + 6 属性明示 ---
PATTERN_S4 = StylePattern(
    id="S4",
    name="seed参照 + 6属性明示",
    description="medium, color palette, mood, rendering technique, saturation, textures の6属性を明示",
    uses_seed_image=True,
    prompt=(
        "Image 1 is the style reference. Image 2 shows the target character. "
        f"Generate a new 9:16 vertical scene: {SCENE_DESCRIPTION} "
        f"The person in the scene is the character from Image 2: {CHARACTER_IDENTITY_BLOCK} "
        "Apply the same medium, color palette, mood, rendering technique, "
        "saturation level, textures, and overall style from Image 1 to this new scene. "
        "MUST preserve the character identity from Image 2 exactly. "
        "Single person only, solo."
    ),
)

# --- S5: seed 参照 + 構図リーク防止強化 ---
PATTERN_S5 = StylePattern(
    id="S5",
    name="seed参照 + 構図リーク防止強化",
    description="S4 + MUST NOT で構図リークを明示的に禁止",
    uses_seed_image=True,
    prompt=(
        "Image 1 is the style reference. Image 2 shows the target character. "
        f"Generate a new 9:16 vertical scene: {SCENE_DESCRIPTION} "
        f"The person in the scene is the character from Image 2: {CHARACTER_IDENTITY_BLOCK} "
        "Apply the same medium, color palette, mood, rendering technique, "
        "saturation level, textures, and overall style from Image 1 to this new scene. "
        "MUST preserve the character identity from Image 2 exactly. "
        "MUST NOT copy the composition, background elements, or subject positioning from Image 1. "
        "MUST NOT reproduce the room, furniture, or environment shown in Image 1. "
        "The scene MUST be a train station platform, not the setting from Image 1. "
        "Single person only, solo."
    ),
)

# --- S6: Visual DNA 抽出（2段階） ---
VISUAL_DNA_EXTRACTION_PROMPT = (
    "Analyze this image and extract its complete visual style as a concise prompt. "
    "Include: color palette (specific tones), lighting setup (direction, quality, temperature), "
    "mood/atmosphere, photographic style, texture/grain, saturation level, "
    "and color grading characteristics. "
    "Output ONLY the style description as a single paragraph, no JSON, no labels. "
    "Do not describe the subject or composition, only the visual style."
)

PATTERN_S6 = StylePattern(
    id="S6",
    name="Visual DNA 抽出（2段階）",
    description="Step 1: Gemini に seed のスタイルを抽出 → Step 2: 抽出結果で新規生成",
    uses_seed_image=False,
    is_two_stage=True,
    visual_dna_extraction_prompt=VISUAL_DNA_EXTRACTION_PROMPT,
    prompt=(
        "Image 1 shows the target character. "
        f"Generate a new 9:16 vertical scene: {SCENE_DESCRIPTION} "
        f"The person in the scene is the character from Image 1: {CHARACTER_IDENTITY_BLOCK} "
        "Visual style: {extracted_style} "
        "MUST preserve the character identity from Image 1 exactly. "
        "Single person only, solo."
    ),
)

# --- S7: seed 参照 + ALL CAPS 全部入り ---
PATTERN_S7 = StylePattern(
    id="S7",
    name="seed参照 + ALL CAPS 全部入り",
    description="画像役割記述 + Identity Block + 6属性明示 + ALL CAPS 保持/禁止。最大情報量",
    uses_seed_image=True,
    prompt=(
        "Image 1 is the style reference — use its color palette, lighting, color grading, "
        "saturation level, textures, and overall visual atmosphere. "
        "Image 2 shows the target character's full appearance including face, hair, body type, and clothing. "
        f"Generate a completely new 9:16 vertical scene: {SCENE_DESCRIPTION} "
        f"The person in the scene is the character from Image 2: {CHARACTER_IDENTITY_BLOCK} "
        "Apply the same medium, color palette, mood, rendering technique, "
        "saturation level, textures, and overall style from Image 1. "
        "MUST preserve the character identity from Image 2 exactly — face, hair, body type, clothing. "
        "MUST NOT copy the composition, background elements, or subject positioning from Image 1. "
        "MUST NOT reproduce the room, furniture, or environment shown in Image 1. "
        "MUST NOT change any character facial features or clothing from Image 2. "
        "The scene MUST be a train station platform, not the setting from Image 1. "
        "Single person only, solo."
    ),
)

# --- S8: 3枚入力（seed + 別環境参照 + キャラ） ---
PATTERN_S8 = StylePattern(
    id="S8",
    name="3枚入力（seed + 環境参照 + キャラ）",
    description="seedのスタイル + 別の駅画像の環境 + キャラの3枚入力。役割分離の精度を検証",
    uses_seed_image=True,
    uses_extra_ref=True,
    extra_ref_images=["5.png"],  # 駅の改札（駅環境の参照として使用）
    prompt=(
        "Image 1 is the style reference — use its color palette, lighting, and visual atmosphere. "
        "Image 2 is the environment reference — use the station setting and architectural elements. "
        "Image 3 shows the target character. "
        f"Generate a new 9:16 vertical scene combining these references: {SCENE_DESCRIPTION} "
        f"The person in the scene is the character from Image 3: {CHARACTER_IDENTITY_BLOCK} "
        "Apply the visual style (colors, lighting, mood) from Image 1. "
        "Use the station environment context from Image 2. "
        "MUST preserve the character identity from Image 3 exactly. "
        "MUST NOT copy the exact composition from any reference image. "
        "Single person only, solo."
    ),
)


# =============================================================================
# 全パターン一覧
# =============================================================================

ALL_PATTERNS: list[StylePattern] = [
    PATTERN_S1,
    PATTERN_S2,
    PATTERN_S3,
    PATTERN_S4,
    PATTERN_S5,
    PATTERN_S6,
    PATTERN_S7,
    PATTERN_S8,
]


def get_patterns_by_ids(ids: list[str]) -> list[StylePattern]:
    """パターン ID でフィルタしてパターンを返す."""
    id_set = {i.strip() for i in ids}
    return [p for p in ALL_PATTERNS if p.id in id_set]


def estimate_total_cost() -> float:
    """全パターン × 全 seed 画像のコストを算出する."""
    return len(ALL_PATTERNS) * len(SEED_IMAGES) * COST_PER_IMAGE
