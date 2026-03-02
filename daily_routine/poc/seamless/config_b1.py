"""Phase B-1: 複合編集 — 段階的パイプライン検証設計.

A1〜A5 で確立した各タスクのベストプラクティスを統合した
段階的パイプラインが一気通貫で動作するかを検証する。

パイプライン:
  Step 0: テキスト除去（A-5 ベストプラクティス）
  Step 1a: Flash 分析 → 画像加工プロンプト生成（A-2 ベストプラクティス）
  Step 1b: Pro 加工 — 人物差し替え+ポーズ変更（A-1 + A-2 統合）
  Step 2: 背景変更（A-3 ベストプラクティス）

検証軸:
- 段階的パイプラインが品質劣化なく動作するか
- 各ステップの中間出力の品質
- Step 1a のメタプロンプトが B1+B2 統合タスクで適切に機能するか
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_b1v3"
REPO_ROOT = Path(__file__).resolve().parents[2]

# --- 画像パス ---
SEED_CAPTURE_DIR = REPO_ROOT / "seeds" / "captures" / "tamachan_life_"
CHARACTER_REF = BASE_DIR / "reference" / "front.png"
BACKGROUND_REF = BASE_DIR / "reference" / "sakura.jpg"

# --- Gemini モデル定数 ---
STEP0_MODEL = "gemini-3-pro-image-preview"  # Step 0: テキスト除去（画像生成）
STEP1A_MODEL = "gemini-3-flash-preview"  # Step 1a: seed 分析・プロンプト生成（テキスト生成）
STEP1B_MODEL = "gemini-3-pro-image-preview"  # Step 1b: 人物差し替え+ポーズ変更（画像生成）
STEP2_MODEL = "gemini-3-pro-image-preview"  # Step 2: 背景変更（画像生成）

COST_PER_IMAGE_GEN = 0.04  # Pro 画像生成コスト
COST_PER_TEXT_GEN = 0.01  # Flash テキスト生成コスト（概算）
ASPECT_RATIO = "9:16"

# --- 検証対象の seed 画像（構図が異なる3枚） ---
SEED_IMAGES: list[str] = [
    "1.png",  # デスク・上半身・室内・座り（側面顔）— テキスト「4:49 起床する」
    "4.png",  # 鏡・全身・玄関・立ち（鏡越し撮影）— テキスト「6:40 出発」
    "8.png",  # カフェ・上半身・テーブル越し・座り（正面寄り）— テキスト「7:59 モチベ上げるために...」
]

# --- キャラクター Identity Block（Phase A-1 で確立済み） ---
CHARACTER_IDENTITY_BLOCK = (
    "a young Japanese woman, mid 20s, slender build. "
    "Wavy dark brown shoulder-length hair, soft round eyes, fair skin. "
    "Wearing a beige V-neck blouse, light gray pencil skirt, "
    "a delicate gold necklace, beige flat shoes."
)

# --- ポーズ変更指示（A-2v3 と同一、比較のため固定） ---
POSE_INSTRUCTION = "taking a selfie with a smartphone in her right hand"


# =============================================================================
# 各ステップのプロンプト定義
# =============================================================================

# Step 0: テキスト除去（A-5 T1: 簡潔指示が最強）
STEP0_PROMPT = "Remove all text overlays from this image."

# Step 1a: メタプロンプト（A-2v3 M1: 最小指示が最良 + A-1 要素を統合）
STEP1A_META_PROMPT = (
    "Analyze this image carefully.\n"
    "Generate an image editing prompt that:\n"
    "1. Replaces the person with this character: {identity_block}\n"
    "2. Changes the pose to {pose_instruction}\n"
    "The prompt should reference two input images:\n"
    "- Image 1: character reference photo\n"
    "- Image 2: the scene to edit\n"
    "The prompt must preserve the scene composition, background, and all objects.\n"
    "Output only the prompt text, nothing else."
)

# 背景変更（2枚入力: seed + 背景参照のみ。キャラ参照は不要）
BG_CHANGE_PROMPT = (
    "Image 1 is the scene to edit. "
    "Image 2 shows the target background environment. "
    "Replace the background in image 1 with the environment from image 2. "
    "Keep the person exactly as they appear in image 1. "
    "Single person only, solo."
)


def build_step1a_meta_prompt(
    identity_block: str = CHARACTER_IDENTITY_BLOCK,
    pose_instruction: str = POSE_INSTRUCTION,
) -> str:
    """Step 1a のメタプロンプトを構築する."""
    return STEP1A_META_PROMPT.format(
        identity_block=identity_block,
        pose_instruction=pose_instruction,
    )


def estimate_cost_per_seed() -> float:
    """seed 1枚あたりのパイプライン総コストを算出する."""
    return (
        COST_PER_IMAGE_GEN  # Step 0: テキスト除去
        + COST_PER_TEXT_GEN  # Step 1a: Flash 分析
        + COST_PER_IMAGE_GEN  # Step 1b: Pro 加工
        + COST_PER_IMAGE_GEN  # Step 2: 背景変更
    )


def estimate_total_cost() -> float:
    """全 seed 画像のコストを算出する."""
    return len(SEED_IMAGES) * estimate_cost_per_seed()
