"""画像生成AI比較検証用の設定・プロンプト定義."""

from dataclasses import dataclass
from pathlib import Path

# ディレクトリ設定
BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated"
EVALUATION_DIR = BASE_DIR / "evaluation"

# テストキャラクター定義
CHARACTER_SPEC = {
    "name": "テストキャラクター Aoi",
    "gender": "女性",
    "age_appearance": "25歳前後",
    "hair": {"color": "ダークブラウン", "style": "セミロング、毛先が軽く内巻き"},
    "eyes": {"color": "ブラウン", "shape": "やや大きめのアーモンド型"},
    "skin": "明るい肌色",
    "build": "標準体型、やや細身",
    "outfit": {
        "top": "白いブラウス（襟付き）",
        "bottom": "ネイビーのタイトスカート（膝丈）",
        "shoes": "ベージュのパンプス",
        "accessories": "小さなゴールドのピアス、腕時計",
    },
    "style": "リアル寄りのセミリアリスティック（アニメ調ではない）",
}

# 共通プロンプト要素
COMMON_PROMPT_ELEMENTS = (
    "25-year-old Japanese woman, dark brown semi-long hair with inward curls at the tips, "
    "brown almond-shaped eyes, white collared blouse, navy knee-length tight skirt, "
    "beige pumps, small gold earrings, wristwatch, "
    "semi-realistic style, high quality, studio lighting, plain white background"
)


@dataclass
class ViewPrompt:
    """ビューごとのプロンプト定義."""

    view_name: str
    filename: str
    description: str
    prompt_suffix: str


# 生成画像セット定義（各AIごとに3枚）
VIEW_PROMPTS = [
    ViewPrompt(
        view_name="front",
        filename="front.png",
        description="正面全身",
        prompt_suffix="full body, front view, standing pose, looking at camera",
    ),
    ViewPrompt(
        view_name="side",
        filename="side.png",
        description="横向き（右向き）上半身",
        prompt_suffix="upper body, right side profile view, natural pose",
    ),
    ViewPrompt(
        view_name="back",
        filename="back.png",
        description="斜め後ろ（左後方から）全身",
        prompt_suffix="full body, rear three-quarter view from left behind, standing pose",
    ),
]


def build_prompt(view: ViewPrompt) -> str:
    """ビュー定義からプロンプトを構築する."""
    return f"{COMMON_PROMPT_ELEMENTS}, {view.prompt_suffix}"


# AI別のネガティブプロンプト（Stability AI用）
NEGATIVE_PROMPT = (
    "anime, cartoon, illustration, low quality, blurry, deformed, extra limbs, bad anatomy, watermark, text, signature"
)

# AI名とディレクトリのマッピング
AI_NAMES = {
    "stability": "Stability AI",
    "dalle": "DALL-E 3",
    "gemini": "Gemini",
}
