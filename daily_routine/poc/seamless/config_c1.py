"""Phase C-1: キャラクター生成 — 検証設計.

オリジナルキャラクターを生成する。

検証パターン:
  C1-T:  テキストのみ生成（Flash分析でmodel_1.pngからキャラ記述生成 → Pro画像生成）
  C1-R1: 参照画像 + 摂動指示（直接編集型）
  C1-R2: 2段階（Flash分析 → 参照画像付きPro生成）
  C1-F1: 複数画像 + 融合指示（直接編集型）— clothing_1〜4 を個別に試行
  C1-F2: 2段階（Flash分析 → 複数画像付きPro生成）— clothing_1〜4 を個別に試行
  C1-ID: Identity Block 自動生成（最良結果に対して実行）
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_c1"

# --- 画像パス ---
ASSETS_DIR = BASE_DIR / "reference" / "assets"
MODEL_REF = ASSETS_DIR / "model_1.png"  # キャラクターの容姿参照
CLOTHING_IMAGES: list[Path] = [
    ASSETS_DIR / "clothing_1.png",
    ASSETS_DIR / "clothing_2.png",
    ASSETS_DIR / "clothing_3.png",
    ASSETS_DIR / "clothing_4.png",
]

# --- Gemini モデル定数 ---
PRO_IMAGE_MODEL = "gemini-3-pro-image-preview"
FLASH_TEXT_MODEL = "gemini-3-flash-preview"

COST_PER_IMAGE_GEN = 0.04  # Pro 画像生成コスト
COST_PER_TEXT_GEN = 0.01  # Flash テキスト生成コスト（概算）
ASPECT_RATIO = "9:16"

# --- 共通プロンプト部品 ---
FULLBODY_NEUTRAL = "Full body shot, standing, neutral background."
DIFFERENT_PERSON = "This must be a DIFFERENT person, not the same person in different clothes."


# =============================================================================
# C1-T: テキストのみ生成
# Step 0: Flash が model_1.png を分析してキャラクター記述を自動生成
# Step 1: Pro がキャラクター記述からテキストのみで画像生成（参照画像なし）
# =============================================================================

C1T_FLASH_ANALYSIS_PROMPT = (
    "Analyze this person's physical features in detail.\n"
    "Generate a character description for image generation.\n"
    "Include: age, gender, ethnicity, build, face shape, eye shape, "
    "skin tone, hair style, hair color, hair length.\n"
    "Do NOT include clothing or accessories — describe only physical features.\n"
    "Output only the character description, nothing else."
)

# Step 1 のプロンプトテンプレート（{character_description} を動的に埋める）
C1T_GENERATION_TEMPLATE = (
    "Generate a photo of: {{character_description}}\n"
    "Wearing a casual outfit suitable for a young Japanese woman.\n"
    f"{FULLBODY_NEUTRAL}\n"
    "The character should look like a real Japanese woman."
)


# =============================================================================
# C1-R1: 参照画像 + 摂動指示（直接編集型、1パス）
# =============================================================================
C1R1_PROMPT = (
    "Image 1 shows a reference character.\n"
    "Generate a photo of a SIMILAR but DIFFERENT character.\n"
    "Keep: face shape, age range, body type, skin tone.\n"
    "Change: outfit to a different casual style, hairstyle to a slightly different style.\n"
    f"{FULLBODY_NEUTRAL}\n"
    f"{DIFFERENT_PERSON}"
)


# =============================================================================
# C1-R2: 2段階（Flash分析 → 参照画像付きPro生成）
# =============================================================================

# Step 1: Flash メタプロンプト
C1R2_META_PROMPT = (
    "Analyze this person's physical features.\n"
    "Generate a character description for image generation.\n"
    "The new character should share similar physical features "
    "(face shape, age, build, skin tone) but have different styling "
    "(outfit, hair, accessories).\n"
    "Suggest a specific new outfit and hairstyle.\n"
    "Output only the character description, nothing else."
)

# Step 2 テンプレート（{flash_description} を動的に埋める）
C1R2_GENERATION_TEMPLATE = (
    "Image 1 shows a reference for physical features only.\n"
    "Generate a photo of the following character (a DIFFERENT person):\n"
    "{{flash_description}}\n"
    f"{FULLBODY_NEUTRAL}"
)


# =============================================================================
# C1-F1: 複数画像 + 融合指示（直接編集型、1パス）
# =============================================================================
C1F1_PROMPT = (
    "Image 1 shows the person whose physical features to use "
    "(face, body type, skin tone, hair).\n"
    "Image 2 shows the outfit to wear.\n"
    "Generate a photo of the person from image 1 "
    "wearing the outfit from image 2.\n"
    f"{FULLBODY_NEUTRAL}\n"
    "Single person only, solo."
)


# =============================================================================
# C1-F2: 2段階（Flash分析 → 複数画像付きPro生成）
# =============================================================================

# Step 1: Flash メタプロンプト
C1F2_META_PROMPT = (
    "Analyze all images carefully.\n"
    "Image 1 shows a person. Image 2 shows an outfit.\n"
    "Generate a detailed character description that combines:\n"
    "- Physical features from image 1\n"
    "- Outfit from image 2\n"
    "Output only the character description, nothing else."
)

# Step 2 テンプレート（{flash_description} を動的に埋める）
C1F2_GENERATION_TEMPLATE = (
    "Image 1 shows the reference person. Image 2 shows the outfit.\n"
    "Generate a photo of the following character:\n"
    "{{flash_description}}\n"
    f"{FULLBODY_NEUTRAL}\n"
    "Single person only, solo."
)


# =============================================================================
# C1-F2-MA: マルチアングル生成（C1-F2 の深掘り）
# Flash分析は1回（正面用と共通）、Proで正面/側面/背面を生成
# =============================================================================

ANGLE_DEFINITIONS: dict[str, dict[str, str]] = {
    "front": {
        "name": "正面",
        "pose": "Full body shot from head to feet, standing, facing the camera, neutral background. "
                "The entire body including shoes must be fully visible with space below the feet.",
    },
    "side": {
        "name": "側面",
        "pose": "Full body shot from head to feet, standing, side view (profile), neutral background. "
                "The entire body including shoes must be fully visible with space below the feet.",
    },
    "back": {
        "name": "背面",
        "pose": "Full body shot from head to feet, standing, back view (seen from behind), neutral background. "
                "The entire body including shoes must be fully visible with space below the feet.",
    },
}

# Step 2 テンプレート（アングル別）
C1F2MA_GENERATION_TEMPLATE = (
    "Image 1 shows the reference person. Image 2 shows the outfit.\n"
    "Generate a photo of the following character:\n"
    "{{flash_description}}\n"
    "{{angle_pose}}\n"
    "Single person only, solo."
)


# =============================================================================
# C1-ID: Identity Block 自動生成
# =============================================================================

# Step 1: Flash がキャラ画像を分析 → Identity Block テキスト
C1ID_ANALYSIS_PROMPT = (
    "Analyze this character and generate a concise identity description "
    "covering: age, gender, ethnicity, build, face features, hair, outfit, "
    "accessories. This will be used to reproduce this exact character "
    "in different scenes. Output only the description."
)

# Step 2: Pro が Identity Block + 別ポーズで再現テスト
C1ID_REPRODUCTION_TEMPLATE = (
    "Image 1 shows the target character.\n"
    "Generate a photo of this EXACT same character:\n"
    "{{identity_block}}\n"
    "The character is sitting at a cafe table, smiling, "
    "with a cup of coffee in front.\n"
    "Single person only, solo."
)


# =============================================================================
# パターン定義
# =============================================================================
PATTERNS: dict[str, dict] = {
    "C1-T": {
        "name": "テキストのみ生成（Flash分析 → Pro生成）",
        "description": "model_1.pngをFlash分析してキャラ記述生成 → テキストのみでPro画像生成",
        "steps": [
            {
                "name": "flash_analysis",
                "task": "Flash キャラクター分析",
                "model": FLASH_TEXT_MODEL,
                "type": "text",
                "cost": COST_PER_TEXT_GEN,
            },
            {
                "name": "text_generation",
                "task": "Pro テキストベース画像生成",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "C1-R1": {
        "name": "参照画像 + 摂動指示（直接編集型）",
        "description": "参照画像を入力し変更箇所を指示して1パス生成",
        "steps": [
            {
                "name": "perturbation_generation",
                "task": "Pro 摂動生成",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "C1-R2": {
        "name": "2段階（Flash分析 → 参照画像付きPro生成）",
        "description": "Flash が参照画像を分析してキャラ記述生成 → Pro が参照画像付きで生成",
        "steps": [
            {
                "name": "flash_analysis",
                "task": "Flash キャラクター分析",
                "model": FLASH_TEXT_MODEL,
                "type": "text",
                "cost": COST_PER_TEXT_GEN,
            },
            {
                "name": "reference_generation",
                "task": "Pro 参照付き生成",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "C1-F1": {
        "name": "複数画像 + 融合指示（直接編集型）",
        "description": "人物画像 + 服装画像を入力し1パスで融合生成",
        "steps": [
            {
                "name": "fusion_generation",
                "task": "Pro 融合生成",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "C1-F2": {
        "name": "2段階（Flash分析 → 複数画像付きPro生成）",
        "description": "Flash が全画像を分析してキャラ記述生成 → Pro が参照画像付きで生成",
        "steps": [
            {
                "name": "flash_analysis",
                "task": "Flash 融合分析",
                "model": FLASH_TEXT_MODEL,
                "type": "text",
                "cost": COST_PER_TEXT_GEN,
            },
            {
                "name": "fusion_generation",
                "task": "Pro 融合生成",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "C1-ID": {
        "name": "Identity Block 自動生成 + 再現テスト",
        "description": "生成キャラのIdentity Blockを自動抽出し、別シーンで再現性を検証",
        "steps": [
            {
                "name": "identity_extraction",
                "task": "Flash Identity Block 抽出",
                "model": FLASH_TEXT_MODEL,
                "type": "text",
                "cost": COST_PER_TEXT_GEN,
            },
            {
                "name": "reproduction_test",
                "task": "Pro 再現テスト",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
}

# C1-F1/F2 は clothing パターンごとに実行するため、コスト = パターンコスト × clothing数
FUSION_CLOTHING_COUNT = len(CLOTHING_IMAGES)


def estimate_cost_per_pattern(pattern_key: str) -> float:
    """パターン1回あたりのコストを算出する."""
    return sum(step["cost"] for step in PATTERNS[pattern_key]["steps"])


def estimate_total_cost() -> float:
    """全パターンのコストを算出する（C1-F1/F2 は clothing数分を考慮）."""
    total = 0.0
    for key in PATTERNS:
        if key == "C1-ID":
            continue  # C1-ID は最良結果に対して実行するため別計算
        base_cost = estimate_cost_per_pattern(key)
        if key in ("C1-F1", "C1-F2"):
            total += base_cost * FUSION_CLOTHING_COUNT
        else:
            total += base_cost
    # C1-ID は1回分
    total += estimate_cost_per_pattern("C1-ID")
    return total
