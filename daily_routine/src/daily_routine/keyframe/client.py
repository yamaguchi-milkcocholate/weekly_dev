"""Gemini C3-I1 キーフレーム生成クライアント."""

import asyncio
import logging
from pathlib import Path

from google import genai
from google.genai.types import GenerateContentConfig, ImageConfig, Part

from .prompt import ReferenceInfo, build_flash_meta_prompt, build_generation_prompt

logger = logging.getLogger(__name__)

FLASH_TEXT_MODEL = "gemini-3-flash-preview"
PRO_IMAGE_MODEL = "gemini-3-pro-image-preview"
ASPECT_RATIO = "9:16"
MAX_RETRIES = 3


def _load_image_part(image_path: Path) -> Part:
    """画像ファイルを SDK の Part に変換する."""
    data = image_path.read_bytes()
    suffix = image_path.suffix.lstrip(".")
    mime = f"image/{suffix}" if suffix not in ("jpg", "jpeg") else "image/jpeg"
    return Part.from_bytes(data=data, mime_type=mime)


_CONTENT_TEXT_BY_PURPOSE: dict[str, str] = {
    "wearing": "Item reference (character wears this): {text}",
    "holding": "Item reference (character holds this): {text}",
    "atmosphere": "Atmosphere/style reference: {text}",
    "background": "Background object reference: {text}",
    "interaction": "Item reference (character uses this): {text}",
    "general": "Additional reference: {text}",
    "subject": "Main subject reference: {text}",
}


def _build_reference_content_text(info: ReferenceInfo) -> str:
    """ReferenceInfo から contents に追加するテキストを生成する."""
    template = _CONTENT_TEXT_BY_PURPOSE.get(info.purpose, _CONTENT_TEXT_BY_PURPOSE["general"])
    return template.format(text=info.text)


class GeminiKeyframeClient:
    """Gemini C3-I1 キーフレーム生成クライアント（Flash+Pro 2パス）."""

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    async def analyze_scene(
        self,
        char_images: list[Path],
        env_image: Path | None,
        identity_blocks: list[str],
        pose_instruction: str,
        reference_images: list[Path] | None = None,
        reference_infos: list[ReferenceInfo] | None = None,
    ) -> str:
        """Step 1: Flash 最小指示分析 -> シーンプロンプト."""
        ref_images = reference_images or []
        ref_infos = reference_infos or []
        has_env = env_image is not None and env_image.exists()

        meta_prompt = build_flash_meta_prompt(
            identity_blocks=identity_blocks,
            pose_instruction=pose_instruction,
            num_char_images=len(char_images),
            has_env_image=has_env,
            reference_infos=ref_infos,
        )

        contents: list[Part | str] = []
        for img in char_images:
            contents.append(_load_image_part(img))
        if has_env:
            contents.append(_load_image_part(env_image))  # type: ignore[arg-type]
        for ref_img in ref_images:
            if ref_img.exists():
                contents.append(_load_image_part(ref_img))
        for info in ref_infos:
            if info.text:
                contents.append(_build_reference_content_text(info))
        contents.append(meta_prompt)

        config = GenerateContentConfig(
            response_modalities=["TEXT"],
            temperature=0.0,
        )

        text = await self._generate_text_with_retry(
            model=FLASH_TEXT_MODEL,
            contents=contents,
            config=config,
            step_name="flash_analysis",
        )
        return text

    async def generate_keyframe(
        self,
        char_images: list[Path],
        env_image: Path | None,
        flash_prompt: str,
        reference_images: list[Path] | None = None,
        reference_infos: list[ReferenceInfo] | None = None,
        output_path: Path = Path("keyframe.png"),
    ) -> Path:
        """Step 2: Pro シーン画像生成 -> キーフレーム画像(9:16)."""
        ref_images = reference_images or []
        ref_infos = reference_infos or []
        has_env = env_image is not None and env_image.exists()

        generation_prompt = build_generation_prompt(
            flash_prompt=flash_prompt,
            num_char_images=len(char_images),
            has_env_image=has_env,
            reference_infos=ref_infos,
        )

        contents: list[Part | str] = []
        for img in char_images:
            contents.append(_load_image_part(img))
        if has_env:
            contents.append(_load_image_part(env_image))  # type: ignore[arg-type]
        for ref_img in ref_images:
            if ref_img.exists():
                contents.append(_load_image_part(ref_img))
        contents.append(generation_prompt)

        config = GenerateContentConfig(
            response_modalities=["TEXT", "IMAGE"],
            image_config=ImageConfig(aspect_ratio=ASPECT_RATIO),
        )

        image_data = await self._generate_image_with_retry(
            model=PRO_IMAGE_MODEL,
            contents=contents,
            config=config,
            step_name="scene_generation",
        )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_data)
        logger.info("キーフレーム画像を保存しました: %s (%d bytes)", output_path, len(image_data))
        return output_path

    async def _generate_text_with_retry(
        self,
        model: str,
        contents: list,
        config: GenerateContentConfig,
        step_name: str,
    ) -> str:
        """テキスト生成（リトライ付き）."""
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            logger.info("SDK テキスト生成リクエスト送信中 (model: %s, attempt %d/%d)", model, attempt, MAX_RETRIES)
            try:
                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=model,
                    contents=contents,
                    config=config,
                )
                text = ""
                for part in response.candidates[0].content.parts:
                    if part.text:
                        text += part.text
                if not text.strip():
                    msg = f"テキストが生成されませんでした ({step_name})"
                    raise RuntimeError(msg)
                return text.strip()
            except Exception as e:
                last_error = e
                error_str = str(e)
                if "500" in error_str or "503" in error_str or "timeout" in error_str.lower():
                    wait_sec = 10 * attempt
                    logger.warning("サーバーエラー: %s, %d秒後にリトライ...", error_str[:200], wait_sec)
                    await asyncio.sleep(wait_sec)
                else:
                    raise

        msg = f"全リトライ失敗 ({step_name}): {last_error}"
        raise RuntimeError(msg)

    async def _generate_image_with_retry(
        self,
        model: str,
        contents: list,
        config: GenerateContentConfig,
        step_name: str,
    ) -> bytes:
        """画像生成（リトライ付き）."""
        last_error: Exception | None = None
        for attempt in range(1, MAX_RETRIES + 1):
            logger.info("SDK 画像生成リクエスト送信中 (model: %s, attempt %d/%d)", model, attempt, MAX_RETRIES)
            try:
                response = await asyncio.to_thread(
                    self._client.models.generate_content,
                    model=model,
                    contents=contents,
                    config=config,
                )
                for part in response.candidates[0].content.parts:
                    if part.inline_data:
                        return part.inline_data.data

                msg = f"画像が生成されませんでした ({step_name})"
                raise RuntimeError(msg)
            except Exception as e:
                last_error = e
                error_str = str(e)
                if "500" in error_str or "503" in error_str or "timeout" in error_str.lower():
                    wait_sec = 10 * attempt
                    logger.warning("サーバーエラー: %s, %d秒後にリトライ...", error_str[:200], wait_sec)
                    await asyncio.sleep(wait_sec)
                else:
                    raise

        msg = f"全リトライ失敗 ({step_name}): {last_error}"
        raise RuntimeError(msg)
