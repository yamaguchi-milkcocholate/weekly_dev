"""Seamless Keyframe PoC: 実験パラメータ定義.

実験1: Kontext Max による人物直接差し替え（D-A, D-B）
実験2: Iterative In-Context Editing vs 1パス（I-A, I-B）
実験3: Character Anchor Chain（anchor）

プロンプト設計方針（docs/guidelines/visual_prompt.md セクション2 準拠）:
- 否定表現を使わない（"no X" → 肯定的な置換表現）
- "transform" を避ける（"change X to Y" を使用）
- 変更しない要素を明示的に保持指示する
- 参照画像がある場合、外見の過度な再記述を避ける
- 代名詞を避け、具体的な記述を使う
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated"
REPO_ROOT = Path(__file__).resolve().parents[2]

SEED_CAPTURE_DIR = REPO_ROOT / "seeds" / "captures" / "tamachan_life_"
CHARACTER_REF = BASE_DIR / "reference" / "front.png"
DEFAULT_SCENE_IMAGE = "6.png"

# --- キャラクター仕様（全プロンプト共通） ---
# 参照画像なし（Pro 1枚入力）の場合に使用する、完全なキャラクター記述
CHARACTER_DESC = (
    "a young Japanese woman, mid 20s, slender build, "
    "wavy dark brown shoulder-length hair, soft round eyes, fair skin, "
    "wearing a beige V-neck blouse, light gray pencil skirt, "
    "a delicate gold necklace, beige flat shoes"
)

# 保持指示（否定表現を使わず、維持すべき要素を肯定的に記述）
IDENTITY_ANCHOR = (
    "Maintain the same facial features, hairstyle, and outfit throughout. "
    "Single person only, solo."
)

# --- コスト定数 ---
COST_PRO = 0.04
COST_MAX = 0.08


class Endpoint(str, Enum):
    """BFL FLUX Kontext エンドポイント."""

    PRO = "v1/flux-kontext-pro"
    MAX = "v1/flux-kontext-max"


@dataclass
class GenerationStep:
    """1回の画像生成ステップ."""

    step_id: str
    endpoint: Endpoint
    prompt: str
    seed: int | None = 42
    num_images: int = 1
    aspect_ratio: str | None = None
    use_seed_capture: bool = True
    use_character_ref: bool = False
    use_previous_output: bool = False
    output_filename: str = ""

    def __post_init__(self) -> None:
        if not self.output_filename:
            self.output_filename = f"{self.step_id}.png"

    @property
    def cost(self) -> float:
        if self.endpoint == Endpoint.MAX:
            return COST_MAX * self.num_images
        return COST_PRO * self.num_images


# =============================================================================
# 実験パターン定義
# =============================================================================


@dataclass
class ExperimentPattern:
    """実験パターン定義."""

    id: str
    name: str
    experiment_group: str
    steps: list[GenerationStep] = field(default_factory=list)
    description: str = ""

    @property
    def cost(self) -> float:
        return sum(step.cost for step in self.steps)

    @property
    def image_count(self) -> int:
        return sum(step.num_images for step in self.steps)


# =============================================================================
# 実験1: Kontext Max による人物直接差し替え
# =============================================================================

# D-A: Max 2枚入力 — 参照画像があるため外見の過度な再記述を避ける
PATTERN_D_A = ExperimentPattern(
    id="D-A",
    name="Max（2枚入力）",
    experiment_group="exp1_max",
    description="seed キャプチャ + front.png の2枚を Kontext Max に入力し、構図保持+人物差し替え",
    steps=[
        GenerationStep(
            step_id="scene_6",
            endpoint=Endpoint.MAX,
            prompt=(
                "Change the person in image_1 to the woman from image_2. "
                "Keep the exact same composition, background, camera angle, and lighting from image_1. "
                f"{IDENTITY_ANCHOR}"
            ),
            aspect_ratio="9:16",
            use_seed_capture=True,
            use_character_ref=True,
        ),
    ],
)

# D-B: Pro 1枚入力 — 参照画像なしのためキャラクター記述が必要
PATTERN_D_B = ExperimentPattern(
    id="D-B",
    name="Pro I2I（1枚入力）",
    experiment_group="exp1_max",
    description="seed キャプチャのみ入力し、プロンプトで人物記述",
    steps=[
        GenerationStep(
            step_id="scene_6",
            endpoint=Endpoint.PRO,
            prompt=(
                f"Change the person in this image to {CHARACTER_DESC}. "
                "Keep the exact same composition, background, camera angle, and lighting. "
                f"{IDENTITY_ANCHOR}"
            ),
            use_seed_capture=True,
            use_character_ref=False,
        ),
    ],
)

# =============================================================================
# 実験2: Iterative In-Context Editing vs 1パス
# =============================================================================

# I-A: 1パスで人物差し替え＋照明調整を同時指示
PATTERN_I_A = ExperimentPattern(
    id="I-A",
    name="1パス（全変更同時指示）",
    experiment_group="exp2_iterative",
    description="人物差し替え＋照明調整を1プロンプトで同時指示",
    steps=[
        GenerationStep(
            step_id="scene_6",
            endpoint=Endpoint.PRO,
            prompt=(
                f"Change the person in this image to {CHARACTER_DESC}. "
                "Subtly warm the lighting tone to soft golden hour atmosphere. "
                "Keep the exact same composition, background, and camera angle. "
                f"{IDENTITY_ANCHOR}"
            ),
            use_seed_capture=True,
        ),
    ],
)

# I-B: 3パス連鎖 — 各ステップで1変更に絞り、保持指示を強化
PATTERN_I_B = ExperimentPattern(
    id="I-B",
    name="3パス（段階的編集）",
    experiment_group="exp2_iterative",
    description="Pass1: 人物差し替え → Pass2: 照明微調整 → Pass3: 顔ディテール微調整",
    steps=[
        GenerationStep(
            step_id="pass_1",
            endpoint=Endpoint.PRO,
            prompt=(
                f"Change the person in this image to {CHARACTER_DESC}. "
                "Keep the exact same composition, background, camera angle, and lighting. "
                f"{IDENTITY_ANCHOR}"
            ),
            use_seed_capture=True,
            use_previous_output=False,
        ),
        GenerationStep(
            step_id="pass_2",
            endpoint=Endpoint.PRO,
            prompt=(
                "Subtly warm the lighting tone of this image, "
                "adding a gentle golden hour warmth while preserving the existing atmosphere. "
                "Keep the person, pose, background, and composition completely unchanged. "
                f"{IDENTITY_ANCHOR}"
            ),
            use_seed_capture=False,
            use_previous_output=True,
        ),
        GenerationStep(
            step_id="pass_3",
            endpoint=Endpoint.PRO,
            prompt=(
                "Slightly refine the facial details of the woman in this image "
                "for a more natural, photorealistic appearance. "
                "Keep everything else completely unchanged — same pose, lighting, "
                "composition, background, and outfit. "
                f"{IDENTITY_ANCHOR}"
            ),
            use_seed_capture=False,
            use_previous_output=True,
        ),
    ],
)

# =============================================================================
# 実験3: Character Anchor Chain
# =============================================================================

PATTERN_ANCHOR = ExperimentPattern(
    id="anchor",
    name="Anchor Chain（連鎖生成）",
    experiment_group="exp3_anchor_chain",
    description="Step1: 人物差し替え → Step2: 前出力を参照してポーズ微修正",
    steps=[
        GenerationStep(
            step_id="step_1",
            endpoint=Endpoint.PRO,
            prompt=(
                f"Change the person in this image to {CHARACTER_DESC}. "
                "Keep the exact same composition, background, camera angle, and lighting. "
                f"{IDENTITY_ANCHOR}"
            ),
            use_seed_capture=True,
            use_previous_output=False,
        ),
        GenerationStep(
            step_id="step_2",
            endpoint=Endpoint.PRO,
            prompt=(
                "The woman in this image turns her head slightly toward the camera "
                "with a gentle confident smile. "
                "Keep the same facial features, hairstyle, outfit, "
                "background, lighting, and overall composition. "
                f"{IDENTITY_ANCHOR}"
            ),
            use_seed_capture=False,
            use_previous_output=True,
        ),
    ],
)

# =============================================================================
# 実験4: ポーズ変更（自撮り化）
# =============================================================================

# 自撮りポーズの共通記述
SELFIE_POSE = (
    "holds a smartphone in her right hand, arm extended forward, "
    "taking a selfie with the front camera, smiling gently at the phone screen. "
    "The camera angle is slightly above eye level, as seen from the phone's perspective."
)

# P-A: 1パスで人物差し替え + ポーズ変更を同時指示
PATTERN_P_A = ExperimentPattern(
    id="P-A",
    name="1パス（人物差し替え + ポーズ変更）",
    experiment_group="exp4_pose",
    description="seed キャプチャから人物差し替えとポーズ変更を同時に1パスで指示",
    steps=[
        GenerationStep(
            step_id="selfie",
            endpoint=Endpoint.PRO,
            prompt=(
                f"Change the person in this image to {CHARACTER_DESC}. "
                f"She {SELFIE_POSE} "
                "Keep the same background environment and lighting. "
                f"{IDENTITY_ANCHOR}"
            ),
            use_seed_capture=True,
        ),
    ],
)

# P-B: 2パス（人物差し替え → ポーズ変更）
PATTERN_P_B = ExperimentPattern(
    id="P-B",
    name="2パス（差し替え → ポーズ変更）",
    experiment_group="exp4_pose",
    description="Pass1: 人物差し替えのみ → Pass2: ポーズを自撮りに変更",
    steps=[
        GenerationStep(
            step_id="pass_1",
            endpoint=Endpoint.PRO,
            prompt=(
                f"Change the person in this image to {CHARACTER_DESC}. "
                "Keep the exact same composition, background, camera angle, and lighting. "
                f"{IDENTITY_ANCHOR}"
            ),
            use_seed_capture=True,
            use_previous_output=False,
        ),
        GenerationStep(
            step_id="pass_2",
            endpoint=Endpoint.PRO,
            prompt=(
                f"The woman in this image {SELFIE_POSE} "
                "Keep the same facial features, hairstyle, outfit, "
                "background environment, and lighting. "
                f"{IDENTITY_ANCHOR}"
            ),
            use_seed_capture=False,
            use_previous_output=True,
        ),
    ],
)

# P-C: 1パス（ポーズ変更のみ、人物差し替えなし）
PATTERN_P_C = ExperimentPattern(
    id="P-C",
    name="1パス（ポーズ変更のみ）",
    experiment_group="exp4_pose",
    description="seed キャプチャの人物をそのまま、ポーズだけ自撮りに変更",
    steps=[
        GenerationStep(
            step_id="selfie",
            endpoint=Endpoint.PRO,
            prompt=(
                f"The person in this image {SELFIE_POSE} "
                "Keep the same background environment and lighting. "
                "Single person only, solo."
            ),
            use_seed_capture=True,
        ),
    ],
)

# =============================================================================
# 全パターン一覧
# =============================================================================

ALL_PATTERNS: list[ExperimentPattern] = [
    PATTERN_D_A,
    PATTERN_D_B,
    PATTERN_I_A,
    PATTERN_I_B,
    PATTERN_ANCHOR,
    PATTERN_P_A,
    PATTERN_P_B,
    PATTERN_P_C,
]

EXPERIMENT_GROUPS = {
    "exp1": "exp1_max",
    "exp2": "exp2_iterative",
    "exp3": "exp3_anchor_chain",
    "exp4": "exp4_pose",
}


# =============================================================================
# ヘルパー関数
# =============================================================================


def get_patterns_by_experiment(experiment_id: str) -> list[ExperimentPattern]:
    """exp1/exp2/exp3 でフィルタしてパターンを返す."""
    group = EXPERIMENT_GROUPS.get(experiment_id)
    if not group:
        return []
    return [p for p in ALL_PATTERNS if p.experiment_group == group]


def get_patterns_by_ids(ids: list[str]) -> list[ExperimentPattern]:
    """パターン ID でフィルタしてパターンを返す."""
    id_set = {i.strip() for i in ids}
    return [p for p in ALL_PATTERNS if p.id in id_set]


def estimate_cost(patterns: list[ExperimentPattern]) -> float:
    """パターンリストの推定コストを算出する."""
    return sum(p.cost for p in patterns)


def count_images(patterns: list[ExperimentPattern]) -> int:
    """パターンリストの生成画像数を算出する."""
    return sum(p.image_count for p in patterns)
