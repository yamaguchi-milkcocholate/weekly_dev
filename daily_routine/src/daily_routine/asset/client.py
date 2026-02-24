"""Gemini 画像生成クライアント（本番用）."""

import base64
import logging
from pathlib import Path

from langchain_core.messages import HumanMessage
from langchain_google_genai import ChatGoogleGenerativeAI
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-3-pro-image-preview"


class GeminiImageClient:
    """Gemini 画像生成クライアント（本番用）.

    PoC の GeminiClient を本番用に昇格。
    参照画像入力・指数バックオフリトライ・設定管理を追加。
    """

    def __init__(self, api_key: str, model_name: str = _DEFAULT_MODEL) -> None:
        if not api_key:
            msg = "Gemini API キーが設定されていません"
            raise ValueError(msg)
        self.api_key = api_key
        self.model_name = model_name
        self._llm = ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=api_key,
        )

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((RuntimeError, ConnectionError)),
        reraise=True,
    )
    async def generate(self, prompt: str, output_path: Path) -> Path:
        """プロンプトから画像を生成して保存する.

        Args:
            prompt: 画像生成プロンプト
            output_path: 出力ファイルパス

        Returns:
            保存先のパス
        """
        logger.info("画像生成を開始: %s", output_path.name)

        response = await self._llm.ainvoke([HumanMessage(content=prompt)])
        image_data = _extract_image(response)
        if image_data is None:
            msg = "Gemini: 画像が生成されませんでした"
            raise RuntimeError(msg)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_data)
        logger.info("画像生成完了: %s", output_path)
        return output_path

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=2, min=2, max=30),
        retry=retry_if_exception_type((RuntimeError, ConnectionError)),
        reraise=True,
    )
    async def generate_with_reference(
        self,
        prompt: str,
        reference_images: list[Path],
        output_path: Path,
    ) -> Path:
        """参照画像付きで画像を生成する.

        Gemini は最大14枚の参照画像を入力可能。
        キャラクター一貫性維持のために、正面画像やユーザー指定の参照画像を
        横・背面・表情の生成時に入力する。

        Args:
            prompt: 画像生成プロンプト
            reference_images: 参照画像パスのリスト
            output_path: 出力ファイルパス

        Returns:
            保存先のパス
        """
        logger.info("参照画像付き画像生成を開始: %s (参照: %d枚)", output_path.name, len(reference_images))

        content: list[dict | str] = []
        for ref_path in reference_images:
            if not ref_path.exists():
                msg = f"参照画像が見つかりません: {ref_path}"
                raise FileNotFoundError(msg)
            image_bytes = ref_path.read_bytes()
            b64_data = base64.b64encode(image_bytes).decode("utf-8")
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:image/png;base64,{b64_data}"},
                }
            )

        content.append({"type": "text", "text": prompt})

        response = await self._llm.ainvoke([HumanMessage(content=content)])
        image_data = _extract_image(response)
        if image_data is None:
            msg = "Gemini: 参照画像付き生成で画像が返されませんでした"
            raise RuntimeError(msg)

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(image_data)
        logger.info("参照画像付き画像生成完了: %s", output_path)
        return output_path


def _extract_image(response: object) -> bytes | None:
    """langchain レスポンスから画像バイナリを抽出する."""
    content = response.content
    if isinstance(content, list):
        for part in content:
            if not isinstance(part, dict):
                continue
            # inline_data 形式（mime_type + data）
            if "inline_data" in part:
                return base64.b64decode(part["inline_data"]["data"])
            # image_url 形式（data URI）
            if part.get("type") == "image_url":
                url = part["image_url"]["url"]
                if url.startswith("data:"):
                    return base64.b64decode(url.split(",", 1)[1])
    return None
