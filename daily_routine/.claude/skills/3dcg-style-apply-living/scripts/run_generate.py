"""3dcg-style-apply-living: Gemini画像生成スクリプト.

2段階方式（re-skinning → 小物追加）でインテリア画像を生成する。
俯瞰referenceを使ったマルチアングル生成にも対応。

Usage:
    # Pass 1: re-skinning
    uv run python .claude/skills/3dcg-style-apply-living/scripts/run_generate.py \
        --input <workdir>/input/overhead.png \
        --prompt-type reskin \
        --style-text "Bright, warm vintage cafe-inspired interior..." \
        --output <workdir>/output/step1_overhead.png

    # Pass 2: 小物追加
    uv run python .claude/skills/3dcg-style-apply-living/scripts/run_generate.py \
        --input <workdir>/output/step1_overhead.png \
        --prompt-type add-items \
        --output <workdir>/output/step2_overhead.png

    # マルチアングル（素レンダリング入力）: 俯瞰referenceでre-skinning+小物追加を同時実行
    uv run python .claude/skills/3dcg-style-apply-living/scripts/run_generate.py \
        --input <workdir>/input/camera/カメラ1.png \
        --reference <workdir>/output/step2_overhead.png \
        --prompt-type multi-angle \
        --furniture-list "desk, chair" \
        --output <workdir>/output/カメラ1.png

    # マルチアングル（PoC6 re-skinning済み入力）: 俯瞰referenceで小物追加のみ
    uv run python .claude/skills/3dcg-style-apply-living/scripts/run_generate.py \
        --input <workdir>/input/camera/カメラ1.png \
        --reference <workdir>/output/step2_overhead.png \
        --prompt-type add-items-ref \
        --output <workdir>/output/カメラ1.png
"""

import argparse
import asyncio
import base64
import logging
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3-pro-image-preview"
API_BASE = "https://generativelanguage.googleapis.com/v1beta"
COST_PER_IMAGE = 0.134

# --- プロンプトテンプレート ---

PROMPT_RESKIN = """\
Transform this untextured 3D render into a photorealistic interior photograph by adding realistic materials and textures to the existing surfaces.

STRICT RULES — violations will ruin the result:
1. PIXEL-LEVEL POSITION LOCK: Every object ({furniture_list}) must remain at its EXACT pixel position. Do NOT move, shift, resize, or reposition any furniture even slightly.
2. NO ADDITIONS: Do NOT add any object, furniture, decoration, curtain, plant, shelf, rug, or element that is not visible in the original render. The set of objects must be identical.
3. SPATIAL LOCK: Wall positions, room shape, ceiling, floor boundaries, and camera angle must be pixel-accurate to the original.
4. CONSISTENT IDENTITY: Each object must keep a consistent realistic appearance.
5. TEXTURE ONLY: Your job is ONLY to apply photorealistic materials/textures/lighting to the existing geometry. Think of it as "re-skinning" the 3D scene, not redesigning it.

Style to apply (affects materials, lighting, and color grading ONLY — not object placement or addition):
{style_text}"""

PROMPT_MULTI_ANGLE = """\
Image 1 is an untextured 3D render from a specific camera angle. Image 2 is a photorealistic overhead view of the SAME room, showing the final desired look including materials, textures, lighting, and small lifestyle items.

Your task: Transform Image 1 into a photorealistic photograph that is CONSISTENT with Image 2.

STRICT RULES — violations will ruin the result:
1. PIXEL-LEVEL POSITION LOCK: Every object ({furniture_list}) in Image 1 must remain at its EXACT pixel position. Do NOT move, shift, resize, or reposition any furniture.
2. CAMERA ANGLE LOCK: The camera angle, perspective, and field of view must be identical to Image 1. Do NOT change the viewpoint.
3. STYLE MATCH: Apply the same materials, textures, flooring, wall finishes, and lighting as seen in Image 2 (the overhead reference).
4. ITEM CONSISTENCY: Any small items (books, plants, cups, etc.) visible in Image 2 that would be visible from this camera angle should appear in approximately the correct positions.
5. WALL LOCK: All walls, partitions, and room boundaries must match Image 1 exactly.
6. Do NOT add any items that are not visible in either Image 1 or Image 2."""

PROMPT_ADD_ITEMS_REF = """\
Image 1 is a photorealistic interior photograph from a specific camera angle. Image 2 is a photorealistic overhead view of the SAME room, showing small lifestyle items that have been added.

Your task: Add small lifestyle items to Image 1 so that it is CONSISTENT with Image 2.

STRICT RULES — violations will ruin the result:
1. PIXEL-LEVEL STRUCTURE LOCK: All walls, partitions, room boundaries, furniture, camera angle, lighting, and color grading in Image 1 must remain pixel-identical. Do NOT change ANYTHING about the existing scene.
2. ITEM CONSISTENCY: Look at Image 2 (overhead) to see what small items exist and where they are placed. Add the same types of items in the corresponding positions as seen from this camera angle.
3. ONLY ADD small items that are visible in Image 2. Do NOT invent new items.
4. DO NOT place items in walkways or open floor passages.
5. Keep the same photorealistic quality and style as Image 1.

ALLOWED items (only if visible in Image 2):
- Potted plants (small), books, magazines, coffee cups, dishes, cushions, throw blankets, candles, photo frames, pen holders, small clocks

NOT ALLOWED (do NOT add these even if they seem to appear in Image 2):
- Kitchen appliances, sinks, stoves, refrigerators, shelving units, cabinets, large furniture, lamps, rugs, curtains, or any item larger than a shoebox"""

PROMPT_ADD_ITEMS = """\
This is a photorealistic interior photograph. Add small lifestyle items to make it feel lived-in and cozy.

STRICT RULES:
1. WALLS ARE SACRED: All walls, partitions, and room boundaries must remain exactly as they are. Do NOT remove, merge, open up, or alter any wall. The room shape and all wall positions must be pixel-identical to the input.
2. DO NOT change, move, resize, or reshape any existing furniture. Every existing object must remain pixel-identical.
3. DO NOT change the camera angle, lighting style, or color grading.
4. DO NOT place items in walkways or open floor passages between furniture.
5. Keep the same photorealistic quality and style as the input image.

Freely add small decorative and lifestyle items wherever they look natural and realistic. Use your judgment for what items to add and where to place them.

ALLOWED items (small, hand-held or tabletop size only):
- Potted plants (small), books, magazines, coffee cups, dishes, cushions, throw blankets, candles, photo frames, pen holders, small clocks

NOT ALLOWED (do NOT add these):
- Kitchen appliances, sinks, stoves, refrigerators, shelving units, cabinets, large furniture, lamps, rugs, curtains, or any item larger than a shoebox"""


def _encode_image(image_path: Path) -> dict:
    """Gemini API用の inline_data パートを構築する."""
    data = image_path.read_bytes()
    suffix = image_path.suffix.lstrip(".")
    mime = f"image/{suffix}" if suffix != "jpg" else "image/jpeg"
    return {
        "inline_data": {
            "mime_type": mime,
            "data": base64.b64encode(data).decode("utf-8"),
        }
    }


def _extract_image(result: dict) -> bytes | None:
    """Gemini レスポンスから画像バイナリを抽出する."""
    for candidate in result.get("candidates", []):
        for part in candidate.get("content", {}).get("parts", []):
            if "inlineData" in part:
                return base64.b64decode(part["inlineData"]["data"])
    return None


async def generate(
    api_key: str, image_path: Path, prompt: str, output_path: Path, reference_path: Path | None = None
) -> None:
    """Gemini APIで画像を生成して保存する."""
    parts = [_encode_image(image_path)]
    if reference_path:
        parts.append(_encode_image(reference_path))
    parts.append({"text": prompt})
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }
    url = f"{API_BASE}/models/{MODEL_NAME}:generateContent"

    start = time.monotonic()
    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"x-goog-api-key": api_key},
        )
        if resp.status_code >= 400:
            logger.error("Gemini API エラー: status=%d, body=%s", resp.status_code, resp.text)
        resp.raise_for_status()

    elapsed = time.monotonic() - start
    result = resp.json()
    image_data = _extract_image(result)
    if image_data is None:
        msg = "Gemini: 画像が生成されませんでした"
        raise RuntimeError(msg)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_data)
    logger.info("生成完了: %s (%.1f秒, $%.3f)", output_path, elapsed, COST_PER_IMAGE)


async def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="3dcg-style-apply-living: Gemini画像生成")
    parser.add_argument("--input", type=Path, required=True, help="入力画像パス")
    parser.add_argument("--prompt-type", choices=["reskin", "add-items", "add-items-ref", "multi-angle"], required=True, help="プロンプト種別")
    parser.add_argument("--reference", type=Path, default=None, help="参照画像パス（multi-angle時の俯瞰reference）")
    parser.add_argument("--style-text", type=str, default="", help="スタイルテキスト（reskin時は必須）")
    parser.add_argument("--furniture-list", type=str, default="bed, desk, chair, table, closet", help="画像内の家具リスト（カンマ区切り、reskin時にプロンプトに埋め込まれる）")
    parser.add_argument("--extra-instructions", type=str, default="", help="プロンプト末尾に追加する指示テキスト")
    parser.add_argument("--output", type=Path, required=True, help="出力画像パス")
    args = parser.parse_args()

    api_key = os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI", "")
    if not api_key:
        logger.error("DAILY_ROUTINE_API_KEY_GOOGLE_AI が設定されていません")
        return

    if not args.input.exists():
        logger.error("入力画像が見つかりません: %s", args.input)
        return

    reference_path = None
    if args.prompt_type == "reskin":
        if not args.style_text:
            logger.error("--style-text は reskin 時に必須です")
            return
        prompt = PROMPT_RESKIN.format(style_text=args.style_text, furniture_list=args.furniture_list)
    elif args.prompt_type in ("multi-angle", "add-items-ref"):
        if not args.reference or not args.reference.exists():
            logger.error("--reference は %s 時に必須です（俯瞰reference画像パス）", args.prompt_type)
            return
        reference_path = args.reference
        if args.prompt_type == "multi-angle":
            prompt = PROMPT_MULTI_ANGLE.format(furniture_list=args.furniture_list)
        else:
            prompt = PROMPT_ADD_ITEMS_REF
    else:
        prompt = PROMPT_ADD_ITEMS

    if args.extra_instructions:
        prompt = f"{prompt}\n\nADDITIONAL INSTRUCTIONS:\n{args.extra_instructions}"

    await generate(api_key, args.input, prompt, args.output, reference_path=reference_path)


if __name__ == "__main__":
    asyncio.run(main())
