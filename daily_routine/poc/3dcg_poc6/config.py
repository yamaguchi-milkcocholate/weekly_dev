"""PoC Step 6: 3Dレンダリング → AI画像生成の設定."""

from dataclasses import dataclass
from pathlib import Path

BASE_DIR = Path(__file__).parent
INPUT_DIR = BASE_DIR / "input" / "camera"
GENERATED_DIR = BASE_DIR / "output"
EVALUATION_DIR = GENERATED_DIR / "evaluation"


@dataclass(frozen=True)
class CameraAngle:
    """カメラアングル定義."""

    id: str
    filename: str


CAMERA_ANGLES: list[CameraAngle] = [
    CameraAngle(id="カメラ1", filename="カメラ1.png"),
    CameraAngle(id="カメラ2", filename="カメラ2.png"),
    CameraAngle(id="カメラ3", filename="カメラ3.png"),
    CameraAngle(id="カメラ4", filename="カメラ4.png"),
    CameraAngle(id="カメラ5", filename="カメラ5.png"),
    CameraAngle(id="カメラ6", filename="カメラ6.png"),
]

# --- プロンプトテンプレート ---

PROMPT_TEMPLATE = """\
Transform this untextured 3D render into a photorealistic interior photograph by adding realistic materials and textures to the existing surfaces.

STRICT RULES — violations will ruin the result:
1. OBJECT FIDELITY: Every object in the render must appear in the output at the EXACT same position, size, and shape. Do NOT remove, replace, reshape, or reinterpret any object.
2. NO ADDITIONS: Do NOT add any object, furniture, decoration, curtain, plant, shelf, rug, or element that is not visible in the original render. The set of objects must be identical.
3. SPATIAL LOCK: Wall positions, room shape, ceiling, floor boundaries, and camera angle must be pixel-accurate to the original.
4. CONSISTENT IDENTITY: Each object must keep a consistent realistic appearance — for example, if a chair appears as a black mesh office chair, it must look like the same black mesh office chair from every angle.
5. TEXTURE ONLY: Your job is ONLY to apply photorealistic materials/textures/lighting to the existing geometry. Think of it as "re-skinning" the 3D scene, not redesigning it.

Style to apply (affects materials, lighting, and color grading ONLY — not object placement or addition):
{style_text}"""


def build_prompt(style_text: str) -> str:
    """スタイルテキストをプロンプトテンプレートに埋め込む."""
    return PROMPT_TEMPLATE.format(style_text=style_text)
