"""マルチビュー画像生成: 1枚の参照画像からfront/side/backを生成する.

Gemini 3.1 Flash Image を使用。Tripo AI マルチビュー入力用。
各ビューのプロンプトは引数で外部から注入する。
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

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3.1-flash-image-preview"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def _encode_image_inline(image_path: Path) -> dict:
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
    candidates = result.get("candidates", [])
    for candidate in candidates:
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        for part in parts:
            if "inlineData" in part:
                return base64.b64decode(part["inlineData"]["data"])
    return None


def _build_prompt(description: str, view_instruction: str) -> str:
    """ビュー別のプロンプトを構築する."""
    return f"""You are given a reference image of an object. {view_instruction}

OBJECT: {description}

STRICT REQUIREMENTS:
1. ONLY THE OBJECT: Render ONLY the described object. No other objects, no floor, no surface, no table, no stand.
2. SOLID GRAY BACKGROUND: Uniform flat mid-gray background (#808080). No gradients, no vignette, no environment.
3. NO SHADOWS: Absolutely no cast shadows, drop shadows, or contact shadows.
4. CONSISTENT LIGHTING: Soft, diffuse studio lighting evenly from all sides. No specular highlights on background.
5. IDENTICAL OBJECT: Exactly the same shape, proportions, materials, colors, textures, and details as the reference.
6. CENTERED COMPOSITION: Object centered in frame with consistent scale across all views.
7. PHOTOREALISTIC: High-quality photorealistic rendering matching the reference.

Output ONLY the image."""


async def _call_gemini(api_key: str, parts: list[dict]) -> dict:
    """Gemini APIを呼び出す."""
    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }
    url = f"{BASE_URL}/models/{MODEL_NAME}:generateContent"

    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"x-goog-api-key": api_key},
        )
        if resp.status_code >= 400:
            logger.error("Gemini API エラー: status=%d, body=%s", resp.status_code, resp.text)
        resp.raise_for_status()

    return resp.json()


async def generate_all_views(
    image_path: Path,
    description: str,
    view_prompts: dict[str, str],
    output_dir: Path,
) -> dict[str, Path]:
    """指定されたビューを独立生成する.

    Args:
        image_path: 参照画像パス
        description: オブジェクトの説明
        view_prompts: ビュー名→ビュー固有の指示テキストの辞書
        output_dir: 出力ディレクトリ
    """
    api_key = os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI", "")
    if not api_key:
        msg = "DAILY_ROUTINE_API_KEY_GOOGLE_AI が設定されていません"
        raise ValueError(msg)

    output_dir.mkdir(parents=True, exist_ok=True)
    results: dict[str, Path] = {}

    for view, view_instruction in view_prompts.items():
        start = time.monotonic()
        output_path = output_dir / f"{view}.png"

        parts: list[dict] = [
            _encode_image_inline(image_path),
            {"text": _build_prompt(description, view_instruction)},
        ]

        result = await _call_gemini(api_key, parts)
        image_data = _extract_image(result)
        if image_data is None:
            msg = f"Gemini: {view}ビューの画像が生成されませんでした"
            raise RuntimeError(msg)

        output_path.write_bytes(image_data)
        results[view] = output_path

        elapsed = time.monotonic() - start
        logger.info("%s ビュー生成完了 (%.1f秒): %s", view, elapsed, output_path)

    return results


def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="マルチビュー画像生成（Tripo用）")
    parser.add_argument("--image", type=Path, required=True, help="参照画像パス")
    parser.add_argument("--description", type=str, required=True, help="オブジェクトの説明")
    parser.add_argument("--front", type=str, required=True, help="frontビューの指示プロンプト")
    parser.add_argument("--side", type=str, required=True, help="sideビューの指示プロンプト")
    parser.add_argument("--back", type=str, required=True, help="backビューの指示プロンプト")
    parser.add_argument("--output-dir", type=Path, default=Path("poc/asset_image_gen/output"), help="出力ディレクトリ")
    args = parser.parse_args()

    if not args.image.exists():
        msg = f"画像が見つかりません: {args.image}"
        raise FileNotFoundError(msg)

    view_prompts = {
        "front": args.front,
        "side": args.side,
        "back": args.back,
    }

    results = asyncio.run(generate_all_views(args.image, args.description, view_prompts, args.output_dir))
    logger.info("全ビュー生成完了: %s", list(results.keys()))


if __name__ == "__main__":
    main()
