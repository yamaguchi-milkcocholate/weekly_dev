"""Geminiで3Dレンダリングフレーム + スタイル参照画像から合成ref画像を生成する.

各カット動画の先頭フレームとスタイル参照画像をGeminiに入力し、
「構図を維持したままスタイルを適用」した合成ref画像を生成する。

Usage:
    uv run python .claude/skills/floor_plan_to_video_sub_photoreal/scripts/generate_ref_image.py \
        --frame input/C1_first_frame.png \
        --style-ref input/style_ref.png \
        --output output/ref_images/C1_ref.png

    # カスタムプロンプト付き
    uv run python .claude/skills/floor_plan_to_video_sub_photoreal/scripts/generate_ref_image.py \
        --frame input/C1_first_frame.png \
        --style-ref input/style_ref.png \
        --prompt "..." \
        --output output/ref_images/C1_ref.png
"""

import argparse
import asyncio
import base64
import logging
import os
from pathlib import Path

import httpx
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

MODEL_NAME = "gemini-3-pro-image-preview"
BASE_URL = "https://generativelanguage.googleapis.com/v1beta"


def _find_dotenv() -> Path | None:
    """親ディレクトリを最大10階層さかのぼって.envを探す."""
    d = Path(__file__).resolve().parent
    for _ in range(10):
        if (d / ".env").exists():
            return d / ".env"
        if d.parent == d:
            break
        d = d.parent
    return None


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


async def generate_ref_image(
    frame_path: Path,
    style_ref_path: Path,
    output_path: Path,
    prompt: str,
) -> Path:
    """3Dレンダリングフレーム + スタイル参照画像から合成ref画像を生成する."""
    api_key = os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI", "")
    if not api_key:
        msg = "DAILY_ROUTINE_API_KEY_GOOGLE_AI が設定されていません"
        raise ValueError(msg)

    parts = [
        _encode_image_inline(frame_path),
        _encode_image_inline(style_ref_path),
        {"text": prompt},
    ]

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    url = f"{BASE_URL}/models/{MODEL_NAME}:generateContent"

    logger.info("Gemini ref画像生成開始: frame=%s, style_ref=%s", frame_path.name, style_ref_path.name)

    async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
        resp = await client.post(
            url,
            json=payload,
            headers={"x-goog-api-key": api_key},
        )
        if resp.status_code >= 400:
            logger.error("Gemini API エラー: status=%d, body=%s", resp.status_code, resp.text)
        resp.raise_for_status()

    result = resp.json()
    image_data = _extract_image(result)
    if image_data is None:
        msg = "Gemini: 画像が生成されませんでした"
        raise RuntimeError(msg)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_data)
    logger.info("ref画像生成完了: %s", output_path)

    return output_path


async def main() -> None:
    load_dotenv(dotenv_path=_find_dotenv())
    parser = argparse.ArgumentParser(description="Gemini ref画像合成")
    parser.add_argument("--frame", type=Path, required=True, help="3Dレンダリングの先頭フレーム画像")
    parser.add_argument("--style-ref", type=Path, required=True, help="スタイル参照画像")
    parser.add_argument("--prompt", type=str, required=True, help="Geminiに渡すプロンプト")
    parser.add_argument("--output", type=Path, required=True, help="出力ref画像パス")
    args = parser.parse_args()

    if not args.frame.exists():
        raise FileNotFoundError(f"フレーム画像が見つかりません: {args.frame}")
    if not args.style_ref.exists():
        raise FileNotFoundError(f"スタイル参照画像が見つかりません: {args.style_ref}")

    await generate_ref_image(
        frame_path=args.frame,
        style_ref_path=args.style_ref,
        output_path=args.output,
        prompt=args.prompt,
    )


if __name__ == "__main__":
    asyncio.run(main())
