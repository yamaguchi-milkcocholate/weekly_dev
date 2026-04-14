"""Phase A-3: 背景変更（B3）精度向上 — 検証設計.

全パターンで背景参照画像を使用し、テキスト指示の組み合わせを変えて検証する。

入力構成（全パターン共通）:
  [キャラ参照(image 1)] + [seed画像(image 2)] + [背景参照(image 3)] + テキスト

検証軸:
- 画像役割の記述の有無・粒度
- 背景テキスト補足の有無
- 人物保持指示の粒度（汎用 vs ALL CAPS 全部入り）
- 選択的編集テンプレート（only）
- 照明変更の許可
- 環境コンテキスト統合
"""

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_a3"
REPO_ROOT = Path(__file__).resolve().parents[2]

SEED_CAPTURE_DIR = REPO_ROOT / "seeds" / "captures" / "tamachan_life_"

# --- 参照画像 ---
CHARACTER_REF = BASE_DIR / "reference" / "front.png"
BACKGROUND_REF = BASE_DIR / "reference" / "sakura.jpg"

# --- Gemini 定数 ---
GEMINI_MODEL = "gemini-3-pro-image-preview"
COST_PER_IMAGE = 0.04
ASPECT_RATIO = "9:16"

# --- 検証対象の seed 画像（構図が異なる3枚） ---
SEED_IMAGES: list[str] = [
    "1.png",  # デスク・上半身・室内・座り（側面顔）
    "4.png",  # 鏡・全身・玄関・立ち（鏡越し撮影）
    "8.png",  # カフェ・上半身・テーブル越し・座り（正面寄り）
]

# --- キャラクター Identity Block（Phase A-1 で確立済み） ---
CHARACTER_IDENTITY_BLOCK = (
    "a young Japanese woman, mid 20s, slender build. "
    "Wavy dark brown shoulder-length hair, soft round eyes, fair skin. "
    "Wearing a beige V-neck blouse, light gray pencil skirt, "
    "a delicate gold necklace, beige flat shoes."
)

# --- 汎用保持指示（Phase A-1 から流用） ---
GENERIC_PRESERVE = (
    "MUST preserve the exact same composition, camera angle, "
    "lighting, and overall atmosphere. "
    "MUST NOT change any elements of the person."
)


# =============================================================================
# パターン定義
# =============================================================================


@dataclass
class A3Pattern:
    """Phase A-3 実験パターン."""

    id: str
    name: str
    prompt: str
    description: str = ""

    @property
    def cost(self) -> float:
        return COST_PER_IMAGE


# --- B1: ベースライン（簡潔指示） ---
PATTERN_B1 = A3Pattern(
    id="B1",
    name="ベースライン（簡潔指示）",
    description="最小限のテキスト指示 + 汎用人物保持。背景参照画像がどこまで効くか確認",
    prompt=(
        "Replace the background in image 2 with the environment shown in image 3. "
        "Keep the person from image 2 exactly as they are. "
        "Single person only, solo."
    ),
)

# --- B2: 画像役割の明示的記述 ---
PATTERN_B2 = A3Pattern(
    id="B2",
    name="画像役割の明示的記述",
    description="3枚それぞれの役割を明確に記述。A-1で役割記述が安定性に寄与した知見の応用",
    prompt=(
        "Image 1 is the character reference showing the target person's appearance. "
        "Image 2 is the scene to edit. "
        "Image 3 shows the target background environment. "
        "Replace the background in image 2 with the environment from image 3. "
        "Keep the person exactly as they appear in image 2. "
        "Single person only, solo."
    ),
)

# --- B3: 背景テキスト補足あり ---
PATTERN_B3 = A3Pattern(
    id="B3",
    name="背景テキスト補足あり",
    description="背景参照画像 + テキストでも背景の特徴を記述。画像とテキストの補完効果を検証",
    prompt=(
        "Image 1 is the character reference. "
        "Image 2 is the scene to edit. "
        "Image 3 shows the target background. "
        "Replace the background in image 2 with the environment from image 3: "
        "a scenic riverside path lined with blooming pink cherry blossom trees "
        "and bright yellow rapeseed flowers, under a clear blue sky with mountains "
        "in the distance. "
        "Keep the person exactly as they appear in image 2. "
        "Single person only, solo."
    ),
)

# --- B4: 人物保持 ALL CAPS 全部入り ---
PATTERN_B4 = A3Pattern(
    id="B4",
    name="人物保持 ALL CAPS 全部入り",
    description="役割記述 + Identity Block + ALL CAPS人物保持。A-1の全部入り最強が背景変更でも成立するか（最重要）",
    prompt=(
        "Image 1 shows the target character. Image 2 is the scene to edit. "
        "Image 3 shows the target background environment. "
        "Replace the background in image 2 with the environment from image 3. "
        f"The person is: {CHARACTER_IDENTITY_BLOCK} "
        "MUST preserve the person's face, hair, clothing, pose, and body position exactly. "
        "MUST NOT alter any aspect of the person's appearance. "
        "MUST match the background atmosphere and spatial layout from image 3. "
        "Single person only, solo."
    ),
)

# --- B5: 選択的編集テンプレート ---
PATTERN_B5 = A3Pattern(
    id="B5",
    name="選択的編集テンプレート（only）",
    description="'Change only the background' で変更スコープを限定。人物に一切触れない指示の効果",
    prompt=(
        "Image 1 is the character reference. "
        "Image 2 is the scene to edit. "
        "Image 3 shows the target background. "
        "Using image 2 as the base, change only the background "
        "to match the environment shown in image 3. "
        "Keep everything else exactly the same, preserving the person's appearance, "
        "pose, clothing, and position. "
        "Single person only, solo."
    ),
)

# --- B6: 照明変更許可 ---
PATTERN_B6 = A3Pattern(
    id="B6",
    name="照明変更許可",
    description="B4ベース + 照明を新環境に合わせて調整を許可。自然さが向上するか検証",
    prompt=(
        "Image 1 shows the target character. Image 2 is the scene to edit. "
        "Image 3 shows the target background environment. "
        "Replace the background in image 2 with the environment from image 3. "
        f"The person is: {CHARACTER_IDENTITY_BLOCK} "
        "MUST preserve the person's face, hair, clothing, pose, and body position exactly. "
        "MUST NOT alter any aspect of the person's appearance. "
        "MUST match the background atmosphere and spatial layout from image 3. "
        "Adjust the lighting on the person to naturally match the new outdoor environment. "
        "Single person only, solo."
    ),
)

# --- B7: 環境コンテキスト統合 ---
PATTERN_B7 = A3Pattern(
    id="B7",
    name="環境コンテキスト統合",
    description="人物の状況と背景を統合記述。人物ポーズと新背景の整合性が向上するか",
    prompt=(
        "Image 1 is the character reference. "
        "Image 2 is the scene to edit. "
        "Image 3 shows the target background. "
        "Place the person from image 2 into the cherry blossom riverside "
        "environment shown in image 3. "
        "She is now standing along the scenic path under blooming sakura trees. "
        "Keep her face, hair, clothing, and overall appearance exactly the same. "
        "Single person only, solo."
    ),
)

# --- B8: 全部入り + 環境統合 ---
PATTERN_B8 = A3Pattern(
    id="B8",
    name="全部入り + 環境統合",
    description="B4（全部入り）+ B7（環境統合）の組み合わせ。最大情報量パターン",
    prompt=(
        "Image 1 shows the target character. Image 2 is the scene to edit. "
        "Image 3 shows the target background environment. "
        "Place the person from image 2 into the cherry blossom riverside "
        "environment shown in image 3. "
        f"The person is: {CHARACTER_IDENTITY_BLOCK} "
        "She is now standing along the scenic path under blooming sakura trees. "
        "MUST preserve the person's face, hair, clothing, and body exactly. "
        "MUST NOT alter any aspect of the person's appearance. "
        "MUST match the background atmosphere and spatial layout from image 3. "
        "Adjust the lighting on the person to naturally match the outdoor environment. "
        "Single person only, solo."
    ),
)


# =============================================================================
# 全パターン一覧
# =============================================================================

ALL_PATTERNS: list[A3Pattern] = [
    PATTERN_B1,
    PATTERN_B2,
    PATTERN_B3,
    PATTERN_B4,
    PATTERN_B5,
    PATTERN_B6,
    PATTERN_B7,
    PATTERN_B8,
]


def get_patterns_by_ids(ids: list[str]) -> list[A3Pattern]:
    """パターン ID でフィルタしてパターンを返す."""
    id_set = {i.strip() for i in ids}
    return [p for p in ALL_PATTERNS if p.id in id_set]


def estimate_total_cost() -> float:
    """全パターン × 全 seed 画像のコストを算出する."""
    return len(ALL_PATTERNS) * len(SEED_IMAGES) * COST_PER_IMAGE
