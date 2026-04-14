"""Phase A-5: テキスト/オーバーレイ除去（B6）— 検証設計.

seed 画像上の時刻表示・テロップ等を自然に除去する手法を確立する。
Gemini I2I で除去指示のプロンプトパターンを比較検証する。

検証軸:
- 簡潔指示 vs 具体的指示
- 保持指示（ALL CAPS）の有無
- 除去対象の明示度（「全テキスト」vs「時刻+テロップ」）
"""

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_a5"
REPO_ROOT = Path(__file__).resolve().parents[2]

SEED_CAPTURE_DIR = REPO_ROOT / "seeds" / "captures" / "tamachan_life_"

# --- Gemini 定数 ---
GEMINI_MODEL = "gemini-3-pro-image-preview"
COST_PER_IMAGE = 0.04
ASPECT_RATIO = "9:16"

# --- 検証対象の seed 画像（テキストオーバーレイの種類が異なる3枚） ---
SEED_IMAGES: list[str] = [
    "1.png",  # 「4:49 起床する」中央に時刻+短いテロップ
    "4.png",  # 「6:40 出発」中央に時刻+短いテロップ
    "8.png",  # 「7:59 モチベ上げるために定期的にスタバ」中央に時刻+長めのテロップ
]


# =============================================================================
# パターン定義
# =============================================================================


@dataclass
class A5Pattern:
    """Phase A-5 実験パターン."""

    id: str
    name: str
    prompt: str
    description: str = ""

    @property
    def cost(self) -> float:
        return COST_PER_IMAGE


# --- T1: 簡潔指示（ベースライン） ---
PATTERN_T1 = A5Pattern(
    id="T1",
    name="簡潔指示（ベースライン）",
    description="最小限の除去指示。Gemini がどこまで自律的に処理できるか確認",
    prompt="Remove all text overlays from this image.",
)

# --- T2: 除去対象を具体的に指定 ---
PATTERN_T2 = A5Pattern(
    id="T2",
    name="除去対象を具体的に指定",
    description="時刻表示・日本語テロップを明示的に指定。対象が明確な方が精度が上がるか検証",
    prompt=(
        "Remove the timestamp numbers and Japanese text caption "
        "overlaid on this image. "
        "Reconstruct the underlying image content naturally."
    ),
)

# --- T3: ALL CAPS 保持指示付き ---
PATTERN_T3 = A5Pattern(
    id="T3",
    name="ALL CAPS 保持指示付き",
    description="除去指示 + ALL CAPS で人物・背景の保持を明示。他フェーズで有効だった手法の適用",
    prompt=(
        "Remove all text overlays (timestamp and caption) from this image. "
        "MUST preserve the person, their pose, clothing, and expression exactly. "
        "MUST preserve the background, lighting, and composition exactly. "
        "MUST NOT change anything other than removing the text. "
        "Reconstruct the areas behind the text naturally."
    ),
)

# --- T4: 編集モード指示（Replace/Clean） ---
PATTERN_T4 = A5Pattern(
    id="T4",
    name="編集モード指示（Clean）",
    description="A-3知見の応用: 'Clean'動詞でモデルを編集モードに誘導。最小限の変更を促す",
    prompt=(
        "This is a video screenshot with overlaid text showing a timestamp "
        "and activity description in Japanese. "
        "Clean the image by removing only the overlaid text. "
        "Fill in the areas where text was with the appropriate background content."
    ),
)


# =============================================================================
# 全パターン一覧
# =============================================================================

ALL_PATTERNS: list[A5Pattern] = [
    PATTERN_T1,
    PATTERN_T2,
    PATTERN_T3,
    PATTERN_T4,
]


def get_patterns_by_ids(ids: list[str]) -> list[A5Pattern]:
    """パターン ID でフィルタしてパターンを返す."""
    id_set = {i.strip() for i in ids}
    return [p for p in ALL_PATTERNS if p.id in id_set]


def estimate_total_cost() -> float:
    """全パターン × 全 seed 画像のコストを算出する."""
    return len(ALL_PATTERNS) * len(SEED_IMAGES) * COST_PER_IMAGE
