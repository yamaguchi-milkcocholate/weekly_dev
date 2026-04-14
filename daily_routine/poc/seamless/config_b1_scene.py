"""Phase B-1 改訂: シーン統合生成 — 検証設計.

レイヤー合成（段階的パイプライン）からシーン統合生成へのパラダイムシフト。
人物と環境を同時に生成することで、照明・接地・空気感の一体感を実現する。

検証パターン:
  1回目（方針A, B, C の代表各1つ）:
    S1: 統合1パス（3画像入力: キャラ参照 + seed + 背景参照）
    S3: Flash統合分析 → Pro生成（3画像入力）
    S5: 精度維持型分割（シーン先行生成 → キャラ差替）
  2回目（S3 の派生パターン — S3 が最有望のため）:
    S4: Flash統合分析 → Pro生成（seed も Pro に入力 — 構図保持強化）
    S3m: Flash統合分析（最小指示メタプロンプト）→ Pro生成

seed_4（全身・立ち・外出）を主軸にする。
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_b1_scene"
REPO_ROOT = Path(__file__).resolve().parents[2]

# --- 画像パス ---
SEED_CAPTURE_DIR = REPO_ROOT / "seeds" / "captures" / "tamachan_life_"
CHARACTER_REF = BASE_DIR / "reference" / "front.png"
BACKGROUND_REF = BASE_DIR / "reference" / "sakura.jpg"

# --- Gemini モデル定数 ---
PRO_IMAGE_MODEL = "gemini-3-pro-image-preview"
FLASH_IMAGE_MODEL = "gemini-3.1-flash-image-preview"
FLASH_TEXT_MODEL = "gemini-3-flash-preview"

COST_PER_IMAGE_GEN = 0.04  # Pro 画像生成コスト
COST_PER_TEXT_GEN = 0.01  # Flash テキスト生成コスト（概算）
ASPECT_RATIO = "9:16"

# --- 検証対象の seed 画像（1回目は seed_4 のみ） ---
SEED_IMAGES: list[str] = [
    "4.png",  # 鏡・全身・玄関・立ち（鏡越し撮影）— 屋外背景との整合性が最も高い
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
# S1: 統合1パス（3画像入力、シーン生成指示）
# =============================================================================
S1_PROMPT = (
    "Image 1 shows the target character.\n"
    "Image 2 shows the reference composition and pose.\n"
    "Image 3 shows the target background environment.\n"
    "Generate a photo of the character from image 1 in the environment from image 3, "
    "matching the composition and camera angle from image 2.\n"
    f"The character is: {CHARACTER_IDENTITY_BLOCK}\n"
    f"The character's pose: {POSE_INSTRUCTION}\n"
    "MUST match the spatial layout, depth, and camera angle from image 2.\n"
    "MUST place the character naturally within the environment from image 3.\n"
    "Single person only, solo."
)


# =============================================================================
# S3: Flash統合分析 → Pro生成（3画像入力）
# =============================================================================

# Step 1: Flash メタプロンプト（seed + 背景参照の両方を分析）
S3_META_PROMPT = (
    "Image 1 is the original scene with its composition, camera angle, and foreground objects.\n"
    "Image 2 is the target environment.\n"
    "Generate an image generation prompt that recreates the scene from image 1 "
    "in the environment from image 2.\n"
    "The prompt must:\n"
    "- Maintain the composition, camera angle, and foreground objects from image 1\n"
    "- Place the character naturally in the environment from image 2\n"
    f"- The character should be: {CHARACTER_IDENTITY_BLOCK}\n"
    f"- The character's pose: {POSE_INSTRUCTION}\n"
    "- Reference two input images: Image 1 (character reference photo), "
    "Image 2 (background environment reference)\n"
    "Output only the prompt text, nothing else."
)

# Step 2: Pro はキャラ参照 + 背景参照 + Flash生成プロンプトで生成
# （プロンプトは動的生成のため定数なし）


# =============================================================================
# S4: Flash統合分析 → Pro生成（seed も Pro に入力して構図保持を強化）
# =============================================================================
# Step 1: S3 と同じ Flash メタプロンプト（S3_META_PROMPT を再利用）
# Step 2: Pro は [キャラ参照] + [seed] + [背景参照] + Flash生成プロンプトで生成
# （S3 との差分: Pro に seed 画像も渡す → 構図参照の強化）


# =============================================================================
# S3m: Flash統合分析（最小指示メタプロンプト）→ Pro生成
# =============================================================================
# A-2 知見: 最小指示メタプロンプト（M1）が最良。Flash に分析を委ねる。
S3M_META_PROMPT = (
    "Analyze both images carefully.\n"
    "Image 1 is the original scene. Image 2 is the target environment.\n"
    "Generate an image generation prompt that recreates the scene from image 1 "
    "in the environment from image 2.\n"
    f"The character should be: {CHARACTER_IDENTITY_BLOCK}\n"
    f"The character's pose: {POSE_INSTRUCTION}\n"
    "Output only the prompt text, nothing else."
)


# =============================================================================
# S5: 精度維持型分割（シーン先行生成 → キャラ差替）
# =============================================================================

# Step 1: シーン生成（背景変更、元 seed の人物は保持）
S5_STEP1_PROMPT = (
    "Image 1 shows the original scene with composition and camera angle to maintain.\n"
    "Image 2 shows the target background environment.\n"
    "Replace the background in image 1 with the environment from image 2.\n"
    "Keep the person exactly as they appear in image 1.\n"
    "Single person only, solo."
)

# Step 2: キャラクター差替（A-1 全部入りプロンプト）
S5_STEP2_PROMPT = (
    "Image 1 shows the target character. Image 2 is the scene to edit.\n"
    f"Replace the person in image 2 with the character from image 1: "
    f"{CHARACTER_IDENTITY_BLOCK}\n"
    f"Change the pose to: {POSE_INSTRUCTION}\n"
    "MUST preserve the exact same background, composition, camera angle, "
    "lighting, and overall atmosphere from image 2.\n"
    "MUST NOT change any background elements.\n"
    "Single person only, solo."
)


# =============================================================================
# パターン定義
# =============================================================================
PATTERNS: dict[str, dict] = {
    "S1": {
        "name": "統合1パス（3画像入力）",
        "approach": "A: 統合1パス生成",
        "steps": [
            {
                "name": "scene_generation",
                "task": "統合シーン生成",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "S3": {
        "name": "Flash統合分析 → Pro生成",
        "approach": "B: Flash統合分析",
        "steps": [
            {
                "name": "flash_analysis",
                "task": "Flash 統合分析",
                "model": FLASH_TEXT_MODEL,
                "type": "text",
                "cost": COST_PER_TEXT_GEN,
            },
            {
                "name": "scene_generation",
                "task": "Pro シーン生成",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "S4": {
        "name": "Flash統合分析 → Pro生成（seed入力あり）",
        "approach": "B: Flash統合分析（構図保持強化）",
        "steps": [
            {
                "name": "flash_analysis",
                "task": "Flash 統合分析",
                "model": FLASH_TEXT_MODEL,
                "type": "text",
                "cost": COST_PER_TEXT_GEN,
            },
            {
                "name": "scene_generation",
                "task": "Pro シーン生成（seed入力あり）",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "S3M_CMP": {
        "name": "Flash統合分析（最小指示）→ Pro/Flash画像生成比較",
        "approach": "B: Flash統合分析（最小指示）— 同一プロンプトで画像生成モデルを比較",
        "steps": [
            {
                "name": "flash_analysis",
                "task": "Flash 統合分析（最小指示）",
                "model": FLASH_TEXT_MODEL,
                "type": "text",
                "cost": COST_PER_TEXT_GEN,
            },
            {
                "name": "scene_generation_pro",
                "task": "Pro 画像生成",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
            {
                "name": "scene_generation_flash",
                "task": "Flash 画像生成",
                "model": FLASH_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "S5": {
        "name": "精度維持型分割（シーン先行 → キャラ差替）",
        "approach": "C: 精度維持型分割",
        "steps": [
            {
                "name": "scene_generation",
                "task": "シーン生成（背景変更）",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
            {
                "name": "character_swap",
                "task": "キャラクター差替",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
}


def estimate_cost_per_pattern(pattern_key: str) -> float:
    """パターン1回あたりのコストを算出する."""
    return sum(step["cost"] for step in PATTERNS[pattern_key]["steps"])


def estimate_total_cost() -> float:
    """全パターン × 全seed のコストを算出する."""
    total = 0.0
    for pattern_key in PATTERNS:
        total += estimate_cost_per_pattern(pattern_key) * len(SEED_IMAGES)
    return total
