"""Phase A-1: 人物差し替え（Character Swap）プロンプト最適化.

Gemini 3.1 Pro で人物差し替えの6パターンを検証する。
seed画像3枚 × 6パターン = 18生成。

プロンプト設計方針（docs/guidelines/visual_prompt.md + Web調査結果 準拠）:
- "change" / "replace" を使用（"transform" は全体再構築リスクがあるため避ける）
- ポジティブ保持指示（"keep X the same" > "don't change X"）
- 代名詞を避け、具体的な記述を使う
- Identity Block はプロンプト先頭に配置
"""

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_a1"
REPO_ROOT = Path(__file__).resolve().parents[2]

SEED_CAPTURE_DIR = REPO_ROOT / "seeds" / "captures" / "tamachan_life_"
CHARACTER_REF = BASE_DIR / "reference" / "front.png"

# --- Gemini 定数 ---
GEMINI_MODEL = "gemini-3-pro-image-preview"
COST_PER_IMAGE = 0.04  # Gemini 3 Pro Image (Nano Banana Pro)

# --- 検証対象の seed 画像（構図が異なる3枚） ---
SEED_IMAGES: list[str] = [
    "1.png",   # デスク・上半身・室内（側面顔）
    "4.png",   # 鏡・全身・外出前（コート姿）
    "8.png",   # カフェ・上半身・PC（正面寄り）
]

# --- キャラクター仕様 ---

# 簡潔版（P1 用）: 最小限の記述
CHARACTER_BRIEF = "a young Japanese woman with wavy dark brown shoulder-length hair"

# Identity Block 版（P2, P3, P6 用）: 5-7 特徴記述子
CHARACTER_IDENTITY_BLOCK = (
    "a young Japanese woman, mid 20s, slender build. "
    "Wavy dark brown shoulder-length hair, soft round eyes, fair skin. "
    "Wearing a beige V-neck blouse, light gray pencil skirt, "
    "a delicate gold necklace, beige flat shoes."
)

# 保持指示（ポジティブ表現）
PRESERVE_INSTRUCTION = (
    "Keep the exact same background, composition, camera angle, "
    "lighting, and overall atmosphere."
)

# 強化保持指示（P6 ALL CAPS 版）
PRESERVE_INSTRUCTION_CAPS = (
    "MUST preserve the exact same background, composition, camera angle, "
    "lighting, and overall atmosphere. "
    "MUST NOT change any background elements, furniture, or room layout."
)


# =============================================================================
# パターン定義
# =============================================================================


@dataclass
class A1Pattern:
    """Phase A-1 実験パターン."""

    id: str
    name: str
    prompt: str
    use_character_ref: bool = False
    description: str = ""

    @property
    def cost(self) -> float:
        return COST_PER_IMAGE


# --- P1: ベースライン（簡潔な指示、テキストのみ） ---
PATTERN_P1 = A1Pattern(
    id="P1",
    name="ベースライン: 簡潔指示",
    description="最小限のキャラ記述 + replace 動詞。保持指示なし。ベースライン測定用",
    prompt=(
        f"Replace the person in this image with {CHARACTER_BRIEF}. "
        "Single person only, solo."
    ),
    use_character_ref=False,
)

# --- P2: Identity Block + 保持指示 ---
PATTERN_P2 = A1Pattern(
    id="P2",
    name="Identity Block + 保持指示",
    description="5-7特徴の構造化キャラ記述 + ポジティブ保持指示",
    prompt=(
        f"Replace the person in this image with {CHARACTER_IDENTITY_BLOCK} "
        f"{PRESERVE_INSTRUCTION} "
        "Single person only, solo."
    ),
    use_character_ref=False,
)

# --- P3: 選択的編集テンプレート（Google公式推奨） ---
PATTERN_P3 = A1Pattern(
    id="P3",
    name="選択的編集テンプレート",
    description="Google公式推奨の 'change only X to Y' テンプレート",
    prompt=(
        "Using the provided image, change only the person to "
        f"{CHARACTER_IDENTITY_BLOCK} "
        "Keep everything else exactly the same, preserving the original "
        "style, lighting, composition, and background. "
        "Single person only, solo."
    ),
    use_character_ref=False,
)

# --- P4: 動詞バリエーション（change vs replace vs transform） ---
# P4 は3サブパターンに分割
PATTERN_P4_CHANGE = A1Pattern(
    id="P4a",
    name="動詞: change",
    description="'change the person to' — 最も狭いスコープ",
    prompt=(
        f"Change the person in this image to {CHARACTER_IDENTITY_BLOCK} "
        f"{PRESERVE_INSTRUCTION} "
        "Single person only, solo."
    ),
    use_character_ref=False,
)

PATTERN_P4_REPLACE = A1Pattern(
    id="P4b",
    name="動詞: replace",
    description="'replace the person with' — 人物スワップ向き",
    prompt=(
        f"Replace the person in this image with {CHARACTER_IDENTITY_BLOCK} "
        f"{PRESERVE_INSTRUCTION} "
        "Single person only, solo."
    ),
    use_character_ref=False,
)

PATTERN_P4_TRANSFORM = A1Pattern(
    id="P4c",
    name="動詞: transform",
    description="'transform the person into' — 全体再構築リスクの検証",
    prompt=(
        f"Transform the person in this image into {CHARACTER_IDENTITY_BLOCK} "
        f"{PRESERVE_INSTRUCTION} "
        "Single person only, solo."
    ),
    use_character_ref=False,
)

# --- P5: 参照画像あり（キャラ参照 + seed） ---
PATTERN_P5 = A1Pattern(
    id="P5",
    name="参照画像あり",
    description="キャラ参照画像(image 1) + seed画像(image 2) の2枚入力",
    prompt=(
        "Use image 1 as a character reference. "
        "Replace the person in image 2 with the woman from image 1. "
        "Keep the exact same background, composition, camera angle, "
        "lighting, and overall atmosphere from image 2. "
        "Single person only, solo."
    ),
    use_character_ref=True,
)

# --- P6: ALL CAPS 強調 + MUST NOT 制約 ---
PATTERN_P6 = A1Pattern(
    id="P6",
    name="ALL CAPS 強調 + MUST NOT",
    description="ALL CAPS の保持指示 + MUST NOT 制約で変更範囲を厳密制御",
    prompt=(
        f"Replace the person in this image with {CHARACTER_IDENTITY_BLOCK} "
        f"{PRESERVE_INSTRUCTION_CAPS} "
        "Single person only, solo."
    ),
    use_character_ref=False,
)

# =============================================================================
# 全パターン一覧
# =============================================================================

ALL_PATTERNS: list[A1Pattern] = [
    PATTERN_P1,
    PATTERN_P2,
    PATTERN_P3,
    PATTERN_P4_CHANGE,
    PATTERN_P4_REPLACE,
    PATTERN_P4_TRANSFORM,
    PATTERN_P5,
    PATTERN_P6,
]


def get_patterns_by_ids(ids: list[str]) -> list[A1Pattern]:
    """パターン ID でフィルタしてパターンを返す."""
    id_set = {i.strip() for i in ids}
    return [p for p in ALL_PATTERNS if p.id in id_set]


def estimate_total_cost() -> float:
    """全パターン × 全 seed 画像のコストを算出する."""
    return len(ALL_PATTERNS) * len(SEED_IMAGES) * COST_PER_IMAGE
