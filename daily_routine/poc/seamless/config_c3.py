"""Phase C-3: キャラ × 環境融合 — 検証設計.

C-1で生成したキャラクターとC-2で生成した環境を融合し、
キャラクターが環境に自然に存在するシーン（keyframe）を生成する。

検証パターン:
  C3-I1: S3M踏襲（最小指示Flash分析 → Pro生成）— 画像入力型
  C3-I2: テキストリッチ型（コンテキスト付きFlash分析 → Pro生成）— 画像入力型
  C3-T:  テキスト環境型（環境画像なし、テキスト記述のみ）
"""

from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_c3"

# --- C1 出力（キャラクター）---
C1_OUTPUT_DIR = BASE_DIR / "generated" / "phase_c1"

# キャラクター参照画像（C1-F2-MA 最良結果: clothing_4 = レーシングスーツ）
CHARACTER_IMAGE_FRONT = C1_OUTPUT_DIR / "c1-f2-ma" / "c1f2ma_clothing_4_front.png"
CHARACTER_IMAGE_SIDE = C1_OUTPUT_DIR / "c1-f2-ma" / "c1f2ma_clothing_4_side.png"
CHARACTER_IMAGE_BACK = C1_OUTPUT_DIR / "c1-f2-ma" / "c1f2ma_clothing_4_back.png"

# Identity Block（C1-ID 出力 — 生成後の画像を分析した記述）
IDENTITY_BLOCK = (
    "Young adult East Asian female, approximately early 20s. "
    "Slender, petite, and athletic build. "
    "Heart-shaped face, large dark brown eyes, small straight nose, "
    "and a calm, neutral expression. "
    "Dark brown/black hair with straight forehead bangs and two long, "
    "neat braids (pigtails) draped over her shoulders. "
    "A professional one-piece motorcycle racing leather suit in a vibrant "
    "blue, red, and black color-block pattern. The suit features "
    '"DAINESE" branding on the limbs and the name "HARUKA" printed on the chest. '
    "She wears matching heavy-duty black motorcycle racing boots. "
    "She is holding a black full-face motorcycle helmet with red accents "
    "and a dark tinted visor tucked under her right arm."
)

# --- C2 出力（環境）---
C2_OUTPUT_DIR = BASE_DIR / "generated" / "phase_c2"

# 環境画像（C2-R2 最良結果）
ENV_IMAGES: dict[str, Path] = {
    "env_1": C2_OUTPUT_DIR / "c2-r2" / "c2r2_env_1.png",  # ダイビングボート＋海
    "env_2": C2_OUTPUT_DIR / "c2-r2" / "c2r2_env_2.png",  # カートサーキット
}

# 環境記述テキスト（C2-ED 出力）
ENV_DESCRIPTIONS: dict[str, str] = {
    "env_1": (
        "Tropical marine environment viewed from the stern of a white boat "
        "during a bright summer midday. The lighting is harsh and direct, "
        "casting sharp shadows on the clean white deck. The color palette is "
        "a vibrant mix of brilliant whites, turquoise, and deep cerulean blues "
        "against a pale sky. The atmosphere is serene and expansive, featuring "
        "clear, layered tropical waters leading to a small, distant "
        "palm-fringed island on a flat horizon under scattered light clouds."
    ),
    "env_2": (
        "This outdoor go-kart racing circuit is set against a backdrop of a lush, "
        "densely forested hillside, suggesting a summer season. The scene is "
        "captured during midday under diffuse, natural lighting from a bright "
        "but overcast sky filled with soft white and grey clouds. The color palette "
        "is characterized by the neutral grey of the asphalt track and the deep "
        "greens of the background forest, punctuated by vibrant pops of bright red "
        "from long rows of interlocking plastic safety barriers and occasional blue "
        "tarps. A white metal post-and-rail fence runs through the foreground. "
        "Key features include the winding asphalt track, tire-wall buffers, a small "
        "elevated white control booth, and the towering wall of trees. "
        "The atmosphere is calm and expectant, typical of a track during a lull "
        "in activity."
    ),
}

# --- ポーズ定義 ---
POSES: dict[str, str] = {
    "standing_confident": "standing confidently with one hand on hip, looking at the camera",
    "walking": "walking towards the camera with a natural stride",
    "selfie": "holding up a phone in one hand taking a selfie, smiling",
}

# --- シナリオコンテキスト（C3-I2 用）---
SCENARIO_CONTEXTS: dict[str, str] = {
    "env_1": (
        "A young female motorcycle racer is visiting a tropical island "
        "for a relaxing day off between races. She is still wearing her "
        "racing suit from the morning practice session on the boat."
    ),
    "env_2": (
        "A young female motorcycle racer has just arrived at a go-kart circuit "
        "for a fun recreational day. She is wearing her professional racing suit "
        "and is excited to try the go-kart track."
    ),
}

# --- Gemini モデル定数 ---
PRO_IMAGE_MODEL = "gemini-3-pro-image-preview"
FLASH_TEXT_MODEL = "gemini-3-flash-preview"

COST_PER_IMAGE_GEN = 0.04  # Pro 画像生成コスト
COST_PER_TEXT_GEN = 0.01  # Flash テキスト生成コスト（概算）
ASPECT_RATIO = "9:16"


# =============================================================================
# C3-I1: S3M踏襲（最小指示Flash分析 → Pro生成）
# キャラ画像 + 環境画像 の両方を入力して融合する標準フロー
# =============================================================================

C3I1_FLASH_META_PROMPT = (
    "Analyze both images carefully.\n"
    "Image 1 shows the character. Image 2 shows the environment.\n"
    "Generate an image generation prompt that places the character "
    "naturally in this environment.\n"
    "The character is: {{identity_block}}\n"
    "The character's pose: {{pose_instruction}}\n"
    "Output only the prompt text, nothing else."
)

C3I1_GENERATION_TEMPLATE = (
    "Image 1 shows the character reference. Image 2 shows the environment reference.\n"
    "{{flash_prompt}}\n"
    "Single person only, solo. Photo-realistic, natural lighting."
)


# =============================================================================
# C3-I2: テキストリッチ型（シナリオコンテキスト付きFlash分析 → Pro生成）
# Flash への入力情報にシナリオコンテキストと環境記述テキストを追加
# =============================================================================

C3I2_FLASH_META_PROMPT = (
    "Analyze both images carefully.\n"
    "Image 1: the character — {{identity_block}}\n"
    "Image 2: the environment — {{env_description}}\n"
    "Scenario context: {{scenario_context}}\n"
    "Generate an image generation prompt that:\n"
    "- Places the character naturally in this environment\n"
    "- Matches the scenario context\n"
    "- Specifies the character's pose: {{pose_instruction}}\n"
    "- Describes natural lighting and atmosphere\n"
    "Output only the prompt text, nothing else."
)

C3I2_GENERATION_TEMPLATE = (
    "Image 1 shows the character reference. Image 2 shows the environment reference.\n"
    "{{flash_prompt}}\n"
    "Single person only, solo. Photo-realistic, natural lighting."
)


# =============================================================================
# C3-T: テキスト環境型（環境画像なし、テキスト記述のみ）
# 環境画像を渡さず、テキストのみで環境を記述して融合
# =============================================================================

C3T_PROMPT = (
    "Image 1 shows the character: {{identity_block}}\n"
    "Generate a photo of this character in the following environment:\n"
    "{{env_description}}\n"
    "The character's pose: {{pose_instruction}}\n"
    "Single person only, solo. Photo-realistic, natural lighting."
)


# =============================================================================
# パターン定義
# =============================================================================
PATTERNS: dict[str, dict] = {
    "C3-I1": {
        "name": "S3M踏襲（最小指示Flash分析 → Pro生成）",
        "description": "キャラ画像 + 環境画像 → Flash最小指示分析 → Pro画像生成",
        "steps": [
            {
                "name": "flash_analysis",
                "task": "Flash シーン分析",
                "model": FLASH_TEXT_MODEL,
                "type": "text",
                "cost": COST_PER_TEXT_GEN,
            },
            {
                "name": "scene_generation",
                "task": "Pro シーン画像生成",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "C3-I2": {
        "name": "テキストリッチ型（コンテキスト付きFlash分析 → Pro生成）",
        "description": "キャラ画像 + 環境画像 + Identity Block + 環境記述 + シナリオ → Flash分析 → Pro画像生成",
        "steps": [
            {
                "name": "flash_analysis",
                "task": "Flash コンテキスト付きシーン分析",
                "model": FLASH_TEXT_MODEL,
                "type": "text",
                "cost": COST_PER_TEXT_GEN,
            },
            {
                "name": "scene_generation",
                "task": "Pro シーン画像生成",
                "model": PRO_IMAGE_MODEL,
                "type": "image",
                "cost": COST_PER_IMAGE_GEN,
            },
        ],
    },
    "C3-T": {
        "name": "テキスト環境型（環境画像なし）",
        "description": "キャラ画像 + テキスト環境記述 → Pro画像生成（環境画像なし）",
        "steps": [
            {
                "name": "scene_generation",
                "task": "Pro テキスト環境シーン生成",
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


def estimate_total_cost(
    pattern_keys: list[str],
    env_count: int,
    pose_count: int,
) -> float:
    """全パターンのコストを算出する（環境数×ポーズ数を考慮）."""
    total = 0.0
    for key in pattern_keys:
        total += estimate_cost_per_pattern(key) * env_count * pose_count
    return total
