"""Phase C-2: 環境生成 — 検証設計.

参照写真（人物入り）から環境の雰囲気を取り出し、
人物不在・C3人物配置向きの環境画像を生成する。

検証パターン:
  C2-R1: Flash分析 → テキストのみPro生成（参照画像をProに渡さない）
  C2-R2: 参照画像 + 環境再現指示（直接編集型、1パス）
  C2-R3: 参照画像 + 構図テンプレート指示（雰囲気と構図を分離）
  C2-ED: 環境記述テキスト自動生成（生成画像からFlash分析）
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_c2"

# --- 画像パス ---
ASSETS_DIR = BASE_DIR / "reference" / "assets"
ENV_IMAGES: list[Path] = [
    ASSETS_DIR / "env_1.png",  # ダイビングボート＋海
    ASSETS_DIR / "env_2.png",  # カートサーキット
]

# --- Gemini モデル定数 ---
PRO_IMAGE_MODEL = "gemini-3-pro-image-preview"
FLASH_TEXT_MODEL = "gemini-3-flash-preview"

COST_PER_IMAGE_GEN = 0.04  # Pro 画像生成コスト
COST_PER_TEXT_GEN = 0.01  # Flash テキスト生成コスト（概算）
ASPECT_RATIO = "9:16"

# --- 共通プロンプト部品 ---
NO_PEOPLE = "The scene must have NO people, no persons, completely empty."
PHOTO_REALISTIC = "Photo-realistic, natural lighting."
COMPOSITION_FULLBODY = (
    "Composition: eye level camera, suitable for placing "
    "a full-body standing person in the center of the frame."
)


# =============================================================================
# C2-R1: Flash分析 → テキストのみPro生成
# 参照写真をFlashが分析して環境記述を生成 → Proにはテキストのみ（参照画像なし）
# =============================================================================

C2R1_FLASH_ANALYSIS_PROMPT = (
    "Analyze the ENVIRONMENT (background/location) in this image, ignoring any people.\n"
    "Describe in detail: location type, structures, ground/surface, sky/weather,\n"
    "lighting conditions, color palette, atmosphere, spatial layout.\n"
    "Then generate an image generation prompt that recreates this same environment\n"
    "with the same atmosphere, but with NO people present.\n"
    "The composition should be suitable for later placing a full-body standing person.\n"
    "Output only the prompt text, nothing else."
)

# Step 2 テンプレート
C2R1_GENERATION_TEMPLATE = (
    "{{flash_description}}\n"
    f"{NO_PEOPLE}\n"
    f"{PHOTO_REALISTIC}"
)


# =============================================================================
# C2-R2: 参照画像 + 環境再現指示（直接編集型、1パス）
# =============================================================================

C2R2_PROMPT = (
    "Image 1 shows a photo with people in a specific environment.\n"
    "Recreate ONLY the environment/location from this image, "
    "removing all people completely.\n"
    "Keep: the exact same location type, structures, weather, lighting, "
    "color palette, atmosphere, time of day.\n"
    "Remove: all people, all persons.\n"
    f"{NO_PEOPLE}\n"
    f"{COMPOSITION_FULLBODY}\n"
    f"{PHOTO_REALISTIC}"
)


# =============================================================================
# C2-R3: 参照画像 + 構図テンプレート指示
# 雰囲気と構図を分離して指示
# =============================================================================

C2R3_PROMPT = (
    "Image 1 shows a reference photo. Focus on the ENVIRONMENT only, ignore people.\n"
    "Generate a photo of the same type of environment with the same atmosphere.\n"
    "Environment requirements:\n"
    "- Same location type and setting as image 1\n"
    "- Same weather, lighting, and time of day\n"
    "- Same overall color palette and mood\n"
    "Composition requirements:\n"
    "- Camera at eye level\n"
    "- Depth: medium background\n"
    "- Framing: suitable for placing a full-body standing person in the center\n"
    "- Clear space in the foreground for a person to stand\n"
    f"{NO_PEOPLE}\n"
    f"{PHOTO_REALISTIC}"
)


# =============================================================================
# C2-ED: 環境記述テキスト自動生成
# 生成した環境画像からC3用の環境記述テキストを自動抽出する
# =============================================================================

C2ED_ANALYSIS_PROMPT = (
    "Analyze this environment image and generate a concise description\n"
    "covering: location type, season, time of day, lighting conditions,\n"
    "color palette, atmosphere, key environmental features.\n"
    "This will be used to reproduce this environment in combined scenes.\n"
    "Output only the description."
)


# =============================================================================
# パターン定義
# =============================================================================
PATTERNS: dict[str, dict] = {
    "C2-R1": {
        "name": "Flash分析 → テキストのみPro生成",
        "description": "参照写真をFlash分析して環境テキスト化 → テキストのみでPro画像生成",
        "steps": [
            {
                "name": "flash_analysis",
                "task": "Flash 環境分析",
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
    "C2-R2": {
        "name": "参照画像 + 環境再現指示（直接編集型）",
        "description": "参照画像を入力し人物除去・環境再現を1パスで指示",
        "steps": [
            {
                "name": "recreation_generation",
                "task": "Pro 環境再現生成",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "C2-R3": {
        "name": "参照画像 + 構図テンプレート指示",
        "description": "参照画像の雰囲気と構図要件を分離して指示",
        "steps": [
            {
                "name": "composition_generation",
                "task": "Pro 構図テンプレート生成",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "C2-ED": {
        "name": "環境記述テキスト自動生成",
        "description": "生成環境画像からFlashで環境記述テキストを自動抽出",
        "steps": [
            {
                "name": "environment_description",
                "task": "Flash 環境記述抽出",
                "model": FLASH_TEXT_MODEL,
                "type": "text",
                "cost": COST_PER_TEXT_GEN,
            },
        ],
    },
}

ENV_IMAGE_COUNT = len(ENV_IMAGES)


def estimate_cost_per_pattern(pattern_key: str) -> float:
    """パターン1回あたりのコストを算出する."""
    return sum(step["cost"] for step in PATTERNS[pattern_key]["steps"])


def estimate_total_cost() -> float:
    """全パターンのコストを算出する（env画像数分を考慮）."""
    total = 0.0
    for key in PATTERNS:
        if key == "C2-ED":
            continue
        total += estimate_cost_per_pattern(key) * ENV_IMAGE_COUNT
    # C2-ED は最良結果分のみ
    total += estimate_cost_per_pattern("C2-ED") * ENV_IMAGE_COUNT
    return total
