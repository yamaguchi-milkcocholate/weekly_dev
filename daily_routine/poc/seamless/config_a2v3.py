"""Phase A-2v3: ポーズ変更 — 2段階AIワークフローの Step 1 検証.

v2 でフル制約（P4/P6）が最高品質と確認されたが、フル制約には seed 固有の記述が必要。
本番パイプラインでは以下の 2 段階で全自動化する:

  Step 1（テキスト生成）: Gemini が seed 画像を分析 → フル制約付き画像加工プロンプトを生成
  Step 2（画像生成）:     Gemini がプロンプトで seed 画像を加工

v3 では Step 1 の品質（Gemini が適切な制約を生成できるか）を検証する。

検証軸:
- メタプロンプトの指示方法（最小指示 / 分析項目明示 / テンプレート提示 / Few-shot）
"""

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "phase_a2v3"
REPO_ROOT = Path(__file__).resolve().parents[2]

# --- Gemini モデル定数 ---
STEP1_MODEL = "gemini-3-flash-preview"  # Step 1: テキスト生成（seed 分析）
STEP2_MODEL = "gemini-3-pro-image-preview"  # Step 2: 画像生成

COST_PER_STEP1 = 0.01  # テキスト生成コスト（概算）
COST_PER_STEP2 = 0.04  # 画像生成コスト

# --- キャラクター Identity Block（Phase A-1 で確立済み） ---
CHARACTER_IDENTITY_BLOCK = (
    "a young Japanese woman, mid 20s, slender build. "
    "Wavy dark brown shoulder-length hair, soft round eyes, fair skin. "
    "Wearing a beige V-neck blouse, light gray pencil skirt, "
    "a delicate gold necklace, beige flat shoes."
)

# --- ポーズ変更指示（v2 P4 と同一、比較のため固定） ---
POSE_INSTRUCTION = "taking a selfie with a smartphone in her right hand"

# --- 検証対象の seed 画像（3チャンネル、座り/立ち混在） ---
SEED_IMAGES: list[dict] = [
    {
        "file": "mimirun_kirakira/1.jpeg",
        "label": "mimirun_1",
        "description": "屋外・立ち・全身・ストレッチ",
    },
    {
        "file": "tamachan_life_/2.png",
        "label": "tamachan_2",
        "description": "室内・座り・デスク・ピンクキーボード",
    },
    {
        "file": "tamachan_life_/3.png",
        "label": "tamachan_3",
        "description": "室内・立ち・下半身メイン",
    },
]

SEED_BASE_DIR = REPO_ROOT / "seeds" / "captures"


def get_seed_path(seed: dict) -> Path:
    """seed 定義から画像パスを取得する."""
    return SEED_BASE_DIR / seed["file"]


# =============================================================================
# メタプロンプト定義
# =============================================================================


@dataclass
class A2v3MetaPrompt:
    """Phase A-2v3 メタプロンプトパターン."""

    id: str
    name: str
    description: str

    def build_meta_prompt(
        self,
        identity_block: str = CHARACTER_IDENTITY_BLOCK,
        pose_instruction: str = POSE_INSTRUCTION,
    ) -> str:
        """メタプロンプトを構築する. サブクラスでオーバーライドしない."""
        raise NotImplementedError

    @property
    def cost_step1(self) -> float:
        return COST_PER_STEP1

    @property
    def cost_step2(self) -> float:
        return COST_PER_STEP2

    @property
    def cost_total(self) -> float:
        return self.cost_step1 + self.cost_step2


# --- M1: 最小指示（ベースライン） ---
class MetaPromptM1(A2v3MetaPrompt):
    """Gemini に分析・制約設計の両方を委ねる最小指示."""

    def build_meta_prompt(
        self,
        identity_block: str = CHARACTER_IDENTITY_BLOCK,
        pose_instruction: str = POSE_INSTRUCTION,
    ) -> str:
        return (
            "Analyze this image carefully.\n"
            "Generate an image editing prompt that changes the person's pose to "
            f"{pose_instruction}.\n"
            f"The character should be: {identity_block}\n"
            "The prompt must preserve the scene composition, background, and all objects.\n"
            "Output only the prompt text, nothing else."
        )


# --- M2: 分析項目明示 ---
class MetaPromptM2(A2v3MetaPrompt):
    """分析すべき項目（位置/オブジェクト/カメラ）を列挙して指示."""

    def build_meta_prompt(
        self,
        identity_block: str = CHARACTER_IDENTITY_BLOCK,
        pose_instruction: str = POSE_INSTRUCTION,
    ) -> str:
        return (
            "Analyze this image and identify:\n"
            "1. The person's current body position (seated, standing, etc.)\n"
            "2. All objects near the person (on desk, table, floor, etc.)\n"
            "3. The camera angle and framing (close-up, medium shot, etc.)\n"
            "\n"
            "Based on your analysis, generate an image editing prompt that:\n"
            f"- Changes the person to {identity_block}\n"
            f"- Changes the pose to {pose_instruction}\n"
            "- Explicitly constrains the identified position, objects, and camera angle "
            "to remain unchanged\n"
            '- Uses "MUST" / "MUST NOT" for constraints\n'
            "\n"
            "Output only the prompt text, nothing else."
        )


# --- M3: テンプレート提示 ---
class MetaPromptM3(A2v3MetaPrompt):
    """P4 のプロンプト構造をテンプレートとして渡し穴埋めさせる."""

    def build_meta_prompt(
        self,
        identity_block: str = CHARACTER_IDENTITY_BLOCK,
        pose_instruction: str = POSE_INSTRUCTION,
    ) -> str:
        return (
            "Analyze this image. Fill in the template below to create an image editing prompt.\n"
            "Replace the [bracketed] parts based on what you observe in the image.\n"
            "\n"
            "Template:\n"
            "Using the provided image, change only the person to [IDENTITY_BLOCK].\n"
            "While remaining in her current [POSITION] position,\n"
            "she [POSE_ACTION].\n"
            "MUST NOT change the camera angle, camera distance, or framing.\n"
            "MUST keep all objects [OBJECT_LOCATION] exactly as they are.\n"
            "MUST preserve the exact same background, composition, lighting, "
            "and overall atmosphere.\n"
            "MUST NOT change any background elements, furniture, or room layout.\n"
            "Single person only, solo.\n"
            "\n"
            "Fill in:\n"
            f"- [IDENTITY_BLOCK]: {identity_block}\n"
            '- [POSITION]: the person\'s current position (e.g., "seated", "standing")\n'
            f"- [POSE_ACTION]: {pose_instruction}\n"
            "- [OBJECT_LOCATION]: where objects are located "
            '(e.g., "on the table or desk", "on the floor")\n'
            "\n"
            "Output only the filled-in prompt, nothing else."
        )


# --- M4: Few-shot（例示付き） ---
class MetaPromptM4(A2v3MetaPrompt):
    """カフェ構図の P4 手動プロンプトを良い例として 1 つ提示."""

    def build_meta_prompt(
        self,
        identity_block: str = CHARACTER_IDENTITY_BLOCK,
        pose_instruction: str = POSE_INSTRUCTION,
    ) -> str:
        return (
            "You are an image editing prompt generator.\n"
            "Given a seed image and a pose change instruction, generate a prompt\n"
            "that changes the pose while preserving the scene.\n"
            "\n"
            "Example:\n"
            "- Image: A woman sitting at a cafe table with a laptop and a coffee cup\n"
            '- Pose instruction: "taking a selfie with a smartphone in her right hand"\n'
            "- Generated prompt:\n"
            f'  "Using the provided image, change only the person to {identity_block}.\n'
            "   While remaining in her current seated position,\n"
            "   she takes a selfie with a smartphone in her right hand.\n"
            "   MUST NOT change the camera angle, camera distance, or framing.\n"
            "   MUST keep all objects on the table exactly as they are.\n"
            "   MUST preserve the exact same background, composition,\n"
            "   lighting, and overall atmosphere.\n"
            "   MUST NOT change any background elements, furniture, or room layout.\n"
            '   Single person only, solo."\n'
            "\n"
            "Now analyze the provided image and generate a similar prompt for:\n"
            f"- Character: {identity_block}\n"
            f'- Pose instruction: "{pose_instruction}"\n'
            "\n"
            "Output only the prompt text, nothing else."
        )


# =============================================================================
# 全パターン一覧
# =============================================================================

ALL_META_PROMPTS: list[A2v3MetaPrompt] = [
    MetaPromptM1(
        id="M1",
        name="最小指示（ベースライン）",
        description="分析・制約設計を全て Gemini に委ねる",
    ),
    MetaPromptM2(
        id="M2",
        name="分析項目明示",
        description="分析すべき 3 項目（位置/オブジェクト/カメラ）を列挙",
    ),
    MetaPromptM3(
        id="M3",
        name="テンプレート提示",
        description="P4 のプロンプト構造をテンプレートとして渡し穴埋めさせる",
    ),
    MetaPromptM4(
        id="M4",
        name="Few-shot（例示付き）",
        description="カフェ構図の P4 手動プロンプトを良い例として 1 つ提示",
    ),
]


def get_meta_prompts_by_ids(ids: list[str]) -> list[A2v3MetaPrompt]:
    """メタプロンプト ID でフィルタして返す."""
    id_set = {i.strip() for i in ids}
    return [m for m in ALL_META_PROMPTS if m.id in id_set]


def estimate_total_cost() -> float:
    """全パターン × 全 seed 画像のコストを算出する."""
    return len(ALL_META_PROMPTS) * len(SEED_IMAGES) * (COST_PER_STEP1 + COST_PER_STEP2)
