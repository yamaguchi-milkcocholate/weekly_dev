"""Phase A-2: ポーズ変更（Pose Change）プロンプト最適化.

Gemini 3 Pro でポーズ変更の7パターンを検証する。
seed画像3枚 × 7パターン = 21生成。

検証軸:
- ポーズ記述の具体性（具体的 vs 全体動作）
- カメラアングルの明示的指示
- 手指アナトミー強調
- 段階的ポーズ記述
- 異なるポーズ種別での汎用性
"""

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_a2"
REPO_ROOT = Path(__file__).resolve().parents[2]

SEED_CAPTURE_DIR = REPO_ROOT / "seeds" / "captures" / "tamachan_life_"

# --- Gemini 定数 ---
GEMINI_MODEL = "gemini-3-pro-image-preview"
COST_PER_IMAGE = 0.04  # Gemini 3 Pro Image

# --- 検証対象の seed 画像（構図が異なる3枚） ---
SEED_IMAGES: list[str] = [
    "1.png",  # デスク・上半身・室内（側面顔）
    "4.png",  # 鏡・全身・外出前（コート姿）
    "8.png",  # カフェ・上半身・PC（正面寄り）
]

# --- キャラクター Identity Block（Phase A-1 で確立済み） ---
CHARACTER_IDENTITY_BLOCK = (
    "a young Japanese woman, mid 20s, slender build. "
    "Wavy dark brown shoulder-length hair, soft round eyes, fair skin. "
    "Wearing a beige V-neck blouse, light gray pencil skirt, "
    "a delicate gold necklace, beige flat shoes."
)

# --- 保持指示（Phase A-1 で確立済み） ---
PRESERVE_INSTRUCTION = (
    "MUST preserve the exact same background, composition, "
    "lighting, and overall atmosphere. "
    "MUST NOT change any background elements, furniture, or room layout."
)

# --- 人物保持指示 ---
PERSON_PRESERVE = (
    "Keep the person's facial features, hair, skin tone, and clothing "
    "exactly the same."
)


# =============================================================================
# パターン定義
# =============================================================================


@dataclass
class A2Pattern:
    """Phase A-2 実験パターン."""

    id: str
    name: str
    prompt: str
    description: str = ""

    @property
    def cost(self) -> float:
        return COST_PER_IMAGE


# --- P1: ベースライン（簡潔指示） ---
PATTERN_P1 = A2Pattern(
    id="P1",
    name="ベースライン: 簡潔ポーズ指示",
    description="最小限のポーズ指示。「自撮りポーズに変更」のみ。ベースライン測定用",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "Change her pose to taking a selfie with a smartphone. "
        f"{PRESERVE_INSTRUCTION} "
        "Single person only, solo."
    ),
)

# --- P2: 具体的動作指示（身体部位ごと） ---
PATTERN_P2 = A2Pattern(
    id="P2",
    name="具体的動作指示（部位別）",
    description="右手・左手・腕・顔の向きを個別に細かく指示",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "Change her pose: she holds a smartphone in her right hand with arm extended forward, "
        "her left hand is relaxed at her side, she tilts her head slightly to the right, "
        "and smiles naturally at the phone camera. "
        f"{PERSON_PRESERVE} "
        f"{PRESERVE_INSTRUCTION} "
        "Single person only, solo."
    ),
)

# --- P3: 全体動作指示（動作名のみ） ---
PATTERN_P3 = A2Pattern(
    id="P3",
    name="全体動作指示（動作名のみ）",
    description="具体的な部位記述を省き、動作名のみで指示",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "She is cheerfully taking a selfie, holding a smartphone out in front of her face, "
        "smiling brightly at the camera. "
        f"{PERSON_PRESERVE} "
        f"{PRESERVE_INSTRUCTION} "
        "Single person only, solo."
    ),
)

# --- P4: カメラアングル明示 ---
PATTERN_P4 = A2Pattern(
    id="P4",
    name="カメラアングル明示",
    description="レンズ・ショットタイプ・アングルを明示して構図をコントロール",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "She is taking a selfie with a smartphone. "
        "Medium close-up shot, 35mm lens, slightly high angle as if shot from her extended arm. "
        "Natural smile, looking directly at the phone camera. "
        f"{PERSON_PRESERVE} "
        f"{PRESERVE_INSTRUCTION} "
        "Single person only, solo."
    ),
)

# --- P5: 手指アナトミー強調 ---
PATTERN_P5 = A2Pattern(
    id="P5",
    name="手指アナトミー強調",
    description="手指の自然さを改善するアナトミー指示を追加",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "She is taking a selfie, holding a smartphone in her right hand with arm extended. "
        "Correct hand anatomy, five fingers naturally gripping the phone, "
        "proper thumb placement on the screen side. "
        "Natural smile, looking at the phone camera. "
        f"{PERSON_PRESERVE} "
        f"{PRESERVE_INSTRUCTION} "
        "Single person only, solo."
    ),
)

# --- P6: 段階的ポーズ記述 ---
PATTERN_P6 = A2Pattern(
    id="P6",
    name="段階的ポーズ記述",
    description="First/Then/Finally で段階的にポーズを組み立てる",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "Adjust her pose step by step: "
        "First, she raises her right arm and holds a smartphone out in front of her. "
        "Then, she tilts her head slightly and looks at the phone screen with a natural smile. "
        "Finally, ensure correct hand anatomy with five fingers gripping the phone naturally. "
        f"{PERSON_PRESERVE} "
        f"{PRESERVE_INSTRUCTION} "
        "Single person only, solo."
    ),
)

# --- P7: 異なるポーズ（腕組み＋横向き） ---
PATTERN_P7 = A2Pattern(
    id="P7",
    name="異なるポーズ（腕組み）",
    description="自撮り以外のポーズで汎用性を確認。腕組みポーズ。",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "Change her pose: she stands with arms crossed over her chest, "
        "weight shifted to her left leg, looking slightly to the right "
        "with a confident, relaxed expression. "
        f"{PERSON_PRESERVE} "
        f"{PRESERVE_INSTRUCTION} "
        "Single person only, solo."
    ),
)


# =============================================================================
# 全パターン一覧
# =============================================================================

ALL_PATTERNS: list[A2Pattern] = [
    PATTERN_P1,
    PATTERN_P2,
    PATTERN_P3,
    PATTERN_P4,
    PATTERN_P5,
    PATTERN_P6,
    PATTERN_P7,
]


def get_patterns_by_ids(ids: list[str]) -> list[A2Pattern]:
    """パターン ID でフィルタしてパターンを返す."""
    id_set = {i.strip() for i in ids}
    return [p for p in ALL_PATTERNS if p.id in id_set]


def estimate_total_cost() -> float:
    """全パターン × 全 seed 画像のコストを算出する."""
    return len(ALL_PATTERNS) * len(SEED_IMAGES) * COST_PER_IMAGE
