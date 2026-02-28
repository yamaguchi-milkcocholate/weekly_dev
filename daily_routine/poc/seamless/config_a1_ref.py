"""Phase A-1 再検証: 参照画像ベースの人物差し替えプロンプト最適化.

全パターンで参照画像（front.png）を使用し、SDK の ImageConfig(aspect_ratio="9:16") で
アスペクト比を制御する。6パターン × 3seed = 18生成。

前回実験（config_a1.py）からの変更点:
- 全パターンで参照画像を使用（前回は P5 のみ）
- REST API → Python SDK（aspect_ratio 制御のため）
- プロンプトは参照画像の活用方法のバリエーション
"""

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_a1_ref"
REPO_ROOT = Path(__file__).resolve().parents[2]

SEED_CAPTURE_DIR = REPO_ROOT / "seeds" / "captures" / "tamachan_life_"
CHARACTER_REF = BASE_DIR / "reference" / "front.png"

# --- Gemini 定数 ---
GEMINI_MODEL = "gemini-3-pro-image-preview"
COST_PER_IMAGE = 0.04
ASPECT_RATIO = "9:16"

# --- 検証対象の seed 画像（構図が異なる3枚） ---
SEED_IMAGES: list[str] = [
    "1.png",  # デスク・上半身・室内（側面顔）
    "4.png",  # 鏡・全身・外出前（コート姿）
    "8.png",  # カフェ・上半身・PC（正面寄り）
]

# --- キャラクター仕様 ---

# Identity Block（5-7 特徴記述子）
CHARACTER_IDENTITY_BLOCK = (
    "a young Japanese woman, mid 20s, slender build. "
    "Wavy dark brown shoulder-length hair, soft round eyes, fair skin. "
    "Wearing a beige V-neck blouse, light gray pencil skirt, "
    "a delicate gold necklace, beige flat shoes."
)


# =============================================================================
# パターン定義
# =============================================================================


@dataclass
class RefPattern:
    """参照画像ベース実験パターン."""

    id: str
    name: str
    prompt: str
    description: str = ""


# --- R1: 参照のみ（ベースライン） ---
PATTERN_R1 = RefPattern(
    id="R1",
    name="参照のみ（ベースライン）",
    description="参照画像 + 最小限のテキスト指示。Identity Block なし",
    prompt=(
        "Replace the person in image 2 with the person from image 1. "
        "Keep everything else exactly the same. "
        "Single person only, solo."
    ),
)

# --- R2: 参照 + Identity Block ---
PATTERN_R2 = RefPattern(
    id="R2",
    name="参照 + Identity Block",
    description="参照画像 + テキストでもキャラ特徴を記述（画像とテキストの補完効果を検証）",
    prompt=(
        "Replace the person in image 2 with the person from image 1: "
        f"{CHARACTER_IDENTITY_BLOCK} "
        "Keep the exact same background, composition, camera angle, "
        "lighting, and overall atmosphere. "
        "Single person only, solo."
    ),
)

# --- R3: 参照 + 選択的編集テンプレート ---
PATTERN_R3 = RefPattern(
    id="R3",
    name="参照 + 選択的編集テンプレート",
    description="Google公式 'change only X to Y' + 参照画像",
    prompt=(
        "Using image 2 as the base, change only the person to "
        "the person shown in image 1. "
        "Keep everything else exactly the same, preserving the original "
        "style, lighting, composition, and background. "
        "Single person only, solo."
    ),
)

# --- R4: 参照 + ALL CAPS 保持 ---
PATTERN_R4 = RefPattern(
    id="R4",
    name="参照 + ALL CAPS 保持",
    description="参照画像 + MUST/MUST NOT 強調の保持指示",
    prompt=(
        "Replace the person in image 2 with the person from image 1. "
        "MUST preserve the exact same background, composition, camera angle, "
        "lighting, and overall atmosphere. "
        "MUST NOT change any background elements, furniture, or room layout. "
        "Single person only, solo."
    ),
)

# --- R5: 参照 + 明示的役割記述 ---
PATTERN_R5 = RefPattern(
    id="R5",
    name="参照 + 明示的役割記述",
    description="各画像の役割を詳細に説明",
    prompt=(
        "Image 1 is a character reference showing the target person's full appearance. "
        "Image 2 is the scene to edit. "
        "Replace the person in image 2 with the character from image 1, "
        "matching their face, hair, body type, and clothing exactly. "
        "Keep the scene, background, composition, and lighting from image 2 unchanged. "
        "Single person only, solo."
    ),
)

# --- R6: 参照 + Identity Block + ALL CAPS ---
PATTERN_R6 = RefPattern(
    id="R6",
    name="参照 + Identity Block + ALL CAPS",
    description="R2 + R4 の組み合わせ（最も情報量が多いパターン）",
    prompt=(
        "Image 1 shows the target character. Image 2 is the scene to edit. "
        "Replace the person in image 2 with the character from image 1: "
        f"{CHARACTER_IDENTITY_BLOCK} "
        "MUST preserve the exact same background, composition, camera angle, "
        "lighting, and overall atmosphere from image 2. "
        "MUST NOT change any background elements, furniture, or room layout. "
        "Single person only, solo."
    ),
)

# =============================================================================
# 全パターン一覧
# =============================================================================

ALL_PATTERNS: list[RefPattern] = [
    PATTERN_R1,
    PATTERN_R2,
    PATTERN_R3,
    PATTERN_R4,
    PATTERN_R5,
    PATTERN_R6,
]


def get_patterns_by_ids(ids: list[str]) -> list[RefPattern]:
    """パターン ID でフィルタしてパターンを返す."""
    id_set = {i.strip() for i in ids}
    return [p for p in ALL_PATTERNS if p.id in id_set]


def estimate_total_cost() -> float:
    """全パターン × 全 seed 画像のコストを算出する."""
    return len(ALL_PATTERNS) * len(SEED_IMAGES) * COST_PER_IMAGE
