"""Phase A-2v2: ポーズ変更 — 制約設計によるプロンプト構築フロー検証.

初回検証（v1）でポーズ記述の粒度を比較した結果、本質は「制約の伝え方」と判明。
v2 ではポーズ指示を簡潔に固定し、制約の有無・種類を変えて検証する。

検証軸:
- 制約なし vs 位置固定 vs 画角固定 vs フル制約
- 意図的変更の許可
- モデル委任型（自動化の鍵）
- 別ポーズでの汎化確認
"""

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_a2v2"
REPO_ROOT = Path(__file__).resolve().parents[2]

SEED_CAPTURE_DIR = REPO_ROOT / "seeds" / "captures" / "tamachan_life_"

# --- Gemini 定数 ---
GEMINI_MODEL = "gemini-3-pro-image-preview"
COST_PER_IMAGE = 0.04

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

# --- 汎用保持指示（Phase A-1 から流用、ベースライン用） ---
GENERIC_PRESERVE = (
    "MUST preserve the exact same background, composition, "
    "lighting, and overall atmosphere. "
    "MUST NOT change any background elements, furniture, or room layout."
)


# =============================================================================
# パターン定義
# =============================================================================


@dataclass
class A2v2Pattern:
    """Phase A-2v2 実験パターン."""

    id: str
    name: str
    prompt: str
    description: str = ""

    @property
    def cost(self) -> float:
        return COST_PER_IMAGE


# --- P1: 制約なし（ベースライン） ---
# 汎用保持指示のみ。初回検証 P1 と同等。
PATTERN_P1 = A2v2Pattern(
    id="P1",
    name="制約なし（ベースライン）",
    description="汎用保持指示のみ。位置・画角の明示的制約なし",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "Change her pose to taking a selfie with a smartphone in her right hand. "
        f"{GENERIC_PRESERVE} "
        "Single person only, solo."
    ),
)

# --- P2: 位置コンテキスト統合 ---
# ポーズ指示に「座ったまま」を組み込む
PATTERN_P2 = A2v2Pattern(
    id="P2",
    name="位置コンテキスト統合",
    description="ポーズ指示に 'while remaining seated' を組み込み、位置を固定",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "While remaining in her current seated position, "
        "she takes a selfie with a smartphone in her right hand. "
        f"{GENERIC_PRESERVE} "
        "Single person only, solo."
    ),
)

# --- P3: 画角固定 ---
# カメラアングル・距離・フレーミングの固定を明示
PATTERN_P3 = A2v2Pattern(
    id="P3",
    name="画角固定",
    description="カメラアングル・距離・フレーミングの固定を明示的に指示",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "Change her pose to taking a selfie with a smartphone in her right hand. "
        f"{GENERIC_PRESERVE} "
        "MUST NOT change the camera angle, camera distance, or framing. "
        "Single person only, solo."
    ),
)

# --- P4: フル制約（位置+画角+オブジェクト） ---
# 手動で正しい制約をすべて書いた場合の最大保持
PATTERN_P4 = A2v2Pattern(
    id="P4",
    name="フル制約（位置+画角+オブジェクト）",
    description="位置固定+画角固定+周辺オブジェクト保持を全て明示",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "While remaining in her current seated position, "
        "she takes a selfie with a smartphone in her right hand. "
        "MUST NOT change the camera angle, camera distance, or framing. "
        "MUST keep all objects on the table or desk exactly as they are. "
        f"{GENERIC_PRESERVE} "
        "Single person only, solo."
    ),
)

# --- P5: 意図的変更許可（立ち上がり+自撮り） ---
# 立ち上がりを明示的に許可
PATTERN_P5 = A2v2Pattern(
    id="P5",
    name="意図的変更許可（立ち上がり+自撮り）",
    description="立ち上がりを意図的に許可し、自撮りポーズに変更",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "She stands up and takes a selfie with a smartphone in her right hand, "
        "smiling at the phone camera. "
        f"{GENERIC_PRESERVE} "
        "Single person only, solo."
    ),
)

# --- P6: 別ポーズ+フル制約（腕組み・座ったまま） ---
# 自撮り以外のポーズでフル制約が機能するか検証
PATTERN_P6 = A2v2Pattern(
    id="P6",
    name="別ポーズ+フル制約（腕組み）",
    description="腕組みポーズ+フル制約。自撮り以外でも制約が機能するか検証",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "While remaining in her current seated position, "
        "she crosses her arms over her chest with a confident, relaxed expression. "
        "MUST NOT change the camera angle, camera distance, or framing. "
        "MUST keep all objects on the table or desk exactly as they are. "
        f"{GENERIC_PRESERVE} "
        "Single person only, solo."
    ),
)

# --- P7: 別ポーズ+意図的変更許可（腕組み+立ち上がり） ---
PATTERN_P7 = A2v2Pattern(
    id="P7",
    name="別ポーズ+意図的変更許可（腕組み+立つ）",
    description="腕組み+立ち上がりを許可。意図的変更が別ポーズでも機能するか検証",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "She stands up with arms crossed over her chest, "
        "looking slightly to the right with a confident expression. "
        f"{GENERIC_PRESERVE} "
        "Single person only, solo."
    ),
)

# --- P8: モデル委任型 ---
# 具体的な制約を書かず、モデルに判断を委ねる
PATTERN_P8 = A2v2Pattern(
    id="P8",
    name="モデル委任型",
    description="具体的制約を書かず「現在の姿勢・画角を維持して」とだけ指示。自動化の鍵",
    prompt=(
        f"Using the provided image, change only the person to {CHARACTER_IDENTITY_BLOCK} "
        "Change her pose to taking a selfie with a smartphone in her right hand. "
        "Keep the person in her current body position (seated or standing). "
        "Maintain the current camera angle and framing. "
        "Keep all surrounding objects in place. "
        f"{GENERIC_PRESERVE} "
        "Single person only, solo."
    ),
)


# =============================================================================
# 全パターン一覧
# =============================================================================

ALL_PATTERNS: list[A2v2Pattern] = [
    PATTERN_P1,
    PATTERN_P2,
    PATTERN_P3,
    PATTERN_P4,
    PATTERN_P5,
    PATTERN_P6,
    PATTERN_P7,
    PATTERN_P8,
]


def get_patterns_by_ids(ids: list[str]) -> list[A2v2Pattern]:
    """パターン ID でフィルタしてパターンを返す."""
    id_set = {i.strip() for i in ids}
    return [p for p in ALL_PATTERNS if p.id in id_set]


def estimate_total_cost() -> float:
    """全パターン × 全 seed 画像のコストを算出する."""
    return len(ALL_PATTERNS) * len(SEED_IMAGES) * COST_PER_IMAGE
