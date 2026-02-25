"""キーフレーム画像生成PoC: 実験パラメータ定義.

実験1: キャラクター分裂問題の検証（パターン A〜D）
実験2: Location 参照による背景リアル化の検証（パターン E〜G）
実験3: 自然文プロンプトの検証（パターン H〜I）
"""

from dataclasses import dataclass, field
from pathlib import Path

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated"
REPORTS_DIR = BASE_DIR / "reports"
LOCATION_REF_DIR = BASE_DIR / "references"

DEFAULT_REFERENCE_DIR = (
    Path(__file__).resolve().parents[2] / "outputs" / "projects" / "test-verify" / "assets" / "character" / "彩香"
)
CHAR_TAG = "char"
LOCATION_TAG = "location"


@dataclass
class PromptPattern:
    """プロンプトパターン定義."""

    id: str
    name: str
    template: str
    use_char_tag: bool  # @char タグでキャラクター参照するか
    use_location_tag: bool = False  # @location タグで背景参照するか
    scene_prompts: dict[str, str] = field(default_factory=dict)  # シーンIDごとの固定プロンプト（自然文用）


# --- 実験1: 分裂問題検証（A〜D） ---
PROMPT_PATTERNS_V1: list[PromptPattern] = [
    PromptPattern(
        id="A",
        name="現状再現",
        template=(
            "@{char_tag} A young Japanese woman in a business suit, {action} in {environment}."
            " {lighting}. {composition}."
        ),
        use_char_tag=True,
    ),
    PromptPattern(
        id="B",
        name="シンプル @char",
        template="@{char_tag} {action}. {lighting}, {environment}. {composition}.",
        use_char_tag=True,
    ),
    PromptPattern(
        id="C",
        name="代名詞方式",
        template="She {action}. {lighting}, {environment}. {composition}.",
        use_char_tag=False,
    ),
    PromptPattern(
        id="D",
        name="制約付き",
        template="@{char_tag} {action}. Single person only. {lighting}, {environment}. {composition}.",
        use_char_tag=True,
    ),
]

# --- 実験2: Location 参照検証（E〜G） ---
PROMPT_PATTERNS_V2: list[PromptPattern] = [
    PromptPattern(
        id="E",
        name="char + location（テンプレート）",
        template="@{char_tag} {action} in @{location_tag}. {lighting}. {composition}.",
        use_char_tag=True,
        use_location_tag=True,
    ),
    PromptPattern(
        id="F",
        name="char + location（環境描写なし）",
        template="@{char_tag} {action}. @{location_tag}. {lighting}. {composition}.",
        use_char_tag=True,
        use_location_tag=True,
    ),
    PromptPattern(
        id="G",
        name="char + location + 制約付き",
        template="@{char_tag} {action} in @{location_tag}. Single person only. {lighting}. {composition}.",
        use_char_tag=True,
        use_location_tag=True,
    ),
]

# --- 実験3: 自然文プロンプト検証（H〜I） ---
PROMPT_PATTERNS_V3: list[PromptPattern] = [
    PromptPattern(
        id="H",
        name="自然文 + location",
        template="",  # scene_prompts を使用
        use_char_tag=True,
        use_location_tag=True,
        scene_prompts={
            "bed": (
                "@char slowly stretches in @location, tangled in white sheets,"
                " first morning light streaming through sheer curtains"
                " casting long golden shadows across the room."
                " Soft intimate close-up from slightly above, shallow depth of field,"
                " lifestyle photography."
            ),
            "cafe": (
                "@char sits in @location, both hands wrapped around a warm latte,"
                " steam curling upward, soft bokeh of the cafe interior in the background."
                " Medium shot, eye level, 50mm lens perspective, warm natural light from the window."
            ),
            "desk": (
                "@char types intently on a laptop in @location,"
                " ambient glow from the monitor illuminating her focused expression."
                " Cool natural light filtering through blinds,"
                " medium shot from front-left angle, shallow depth of field, film grain."
            ),
            "walk": (
                "@char strides purposefully down the sidewalk in @location,"
                " carrying a leather bag, afternoon sunlight casting long diagonal shadows"
                " across the pavement, slight breeze moving her hair."
                " Full body shot, slight low angle, cinematic depth of field."
            ),
        },
    ),
    PromptPattern(
        id="I",
        name="自然文 + location（シネマティック）",
        template="",  # scene_prompts を使用
        use_char_tag=True,
        use_location_tag=True,
        scene_prompts={
            "bed": (
                "@char wakes up in @location, arms reaching above her head in a languid stretch,"
                " white duvet pooling around her waist."
                " First morning light catches dust motes drifting through the air."
                " Overhead medium shot, Rembrandt lighting, 35mm film aesthetic."
            ),
            "cafe": (
                "@char gazes out the window in @location,"
                " fingers lightly tracing the rim of a ceramic coffee cup."
                " Soft diffused daylight wraps around her silhouette,"
                " warm amber tones reflected off wooden surfaces."
                " Medium close-up, shallow depth of field, anamorphic lens bokeh."
            ),
            "desk": (
                "@char leans forward at her desk in @location, fingers hovering over the keyboard,"
                " the blue glow of the screen reflected in her eyes."
                " Desk lamp casts a warm pool of light against cool ambient tones."
                " Medium shot, chiaroscuro lighting, cinematic color grading."
            ),
            "walk": (
                "@char walks through @location, her silhouette framed between"
                " rows of bare winter trees lining the boulevard."
                " Golden hour backlight creates a warm rim light around her figure."
                " Wide shot, leading lines converging toward her,"
                " cinematic depth of field, film grain."
            ),
        },
    ),
]

PROMPT_PATTERNS: list[PromptPattern] = PROMPT_PATTERNS_V1 + PROMPT_PATTERNS_V2 + PROMPT_PATTERNS_V3

# シーンごとの背景参照画像ファイル名マッピング
LOCATION_REF_FILES: dict[str, str] = {
    "bed": "bed_bg",
    "cafe": "cafe_bg",
    "desk": "desk_bg",
    "walk": "walk_bg",
}

# 対応する拡張子を探索する
_SUPPORTED_EXTENSIONS = [".png", ".jpg", ".jpeg"]


def find_location_ref(scene_id: str, ref_dir: Path | None = None) -> Path | None:
    """シーンIDに対応する背景参照画像を探す."""
    ref_dir = ref_dir or LOCATION_REF_DIR
    base_name = LOCATION_REF_FILES.get(scene_id)
    if not base_name:
        return None
    for ext in _SUPPORTED_EXTENSIONS:
        path = ref_dir / f"{base_name}{ext}"
        if path.exists():
            return path
    return None


@dataclass
class Scene:
    """テストシーン定義."""

    id: str
    name: str
    action: str
    environment: str
    lighting: str
    composition: str
    split_risk: str


SCENES: list[Scene] = [
    Scene(
        id="bed",
        name="ベッドで起床",
        action="waking up in bed, stretching arms",
        environment="a cozy bedroom with morning sunlight through curtains",
        lighting="Warm golden morning light",
        composition="Medium shot from slightly above",
        split_risk="高",
    ),
    Scene(
        id="cafe",
        name="カフェでコーヒー",
        action="sitting at a cafe table, holding a coffee cup",
        environment="a modern cafe with large windows",
        lighting="Soft natural daylight",
        composition="Medium shot, eye level",
        split_risk="中",
    ),
    Scene(
        id="desk",
        name="オフィスデスク",
        action="sitting at a desk, typing on a laptop",
        environment="a modern office with a large monitor",
        lighting="Cool fluorescent office lighting",
        composition="Medium shot from front-left angle",
        split_risk="低",
    ),
    Scene(
        id="walk",
        name="街を歩く",
        action="walking down a city sidewalk, carrying a bag",
        environment="a busy urban street with shops",
        lighting="Bright afternoon sunlight with soft shadows",
        composition="Full body shot, slight low angle",
        split_risk="中",
    ),
]


def build_prompt(pattern: PromptPattern, scene: Scene) -> str:
    """パターンとシーンからプロンプトを構築する."""
    # 自然文パターン: シーンIDに対応する固定プロンプトを使用
    if pattern.scene_prompts and scene.id in pattern.scene_prompts:
        return pattern.scene_prompts[scene.id]

    # テンプレートパターン: スロットを埋める
    return pattern.template.format(
        char_tag=CHAR_TAG,
        location_tag=LOCATION_TAG,
        action=scene.action,
        environment=scene.environment,
        lighting=scene.lighting,
        composition=scene.composition,
    )


def get_patterns_by_ids(ids: list[str]) -> list[PromptPattern]:
    """IDリストからパターンを取得する."""
    id_set = {i.upper() for i in ids}
    return [p for p in PROMPT_PATTERNS if p.id in id_set]


def get_scenes_by_ids(ids: list[str]) -> list[Scene]:
    """IDリストからシーンを取得する."""
    id_set = {i.lower() for i in ids}
    return [s for s in SCENES if s.id in id_set]
