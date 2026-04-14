"""LLM 統合分析・トレンド集約."""

import logging

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

from daily_routine.intelligence.base import SceneCapture
from daily_routine.schemas.intelligence import TrendReport

logger = logging.getLogger(__name__)


class SeedVideoData(BaseModel):
    """シード動画の統合データ（ユーザー提供）."""

    scene_captures: list[SceneCapture] = Field(default_factory=list)
    user_note: str = Field(default="")


_SYSTEM_PROMPT = """\
あなたはショート動画のトレンドアナリストです。
競合動画の分析データを受け取り、構造化されたトレンドレポートを生成します。

## 分析の指針

1. シード動画のユーザー提供画像を解析し、テキスト説明と照合してシーン構成・映像特徴を把握する
2. テキスト説明からテロップの内容傾向、ナレーション有無、BGM言及等を分析する
3. 以下の各カテゴリについて具体的かつ実用的な分析結果を生成する:
   - SceneStructure: シーン数・尺、フック手法、遷移パターン
   - CaptionTrend: テロップスタイル
   - VisualTrend: シチュエーション・小物・カメラワーク・色調
   - AudioTrend: BGMテンポ・ジャンル、SE使用箇所（ユーザー説明から推定）
   - AssetRequirement: 必要素材リスト

## 注意事項

- BPMはユーザー説明から推定してください（音声分析はできません）
- 具体的な例を含めてください（例: 「AM 6:00 のテロップで日常感を演出」）
- 日本語で回答してください
"""


class TrendAggregator:
    """全データの LLM 統合分析とトレンド集約."""

    def __init__(self, api_key: str) -> None:
        self._client = genai.Client(api_key=api_key)

    async def aggregate(
        self,
        keyword: str,
        seed_videos: list[SeedVideoData],
    ) -> TrendReport:
        """全動画データを統合分析し、トレンドレポートを生成する."""
        contents = self._build_contents(keyword, seed_videos)
        total_videos = len(seed_videos)

        logger.info("LLM統合分析開始: シード%d件", len(seed_videos))

        response = await self._client.aio.models.generate_content(
            model="gemini-2.5-flash",
            contents=contents,
            config=types.GenerateContentConfig(
                system_instruction=_SYSTEM_PROMPT,
                response_mime_type="application/json",
                response_schema=TrendReport,
            ),
        )

        # レスポンスからTrendReportをパース
        report = TrendReport.model_validate_json(response.text)

        # LLM が出力しない可能性のあるフィールドを補正
        if not report.keyword:
            report.keyword = keyword
        if report.analyzed_video_count == 0:
            report.analyzed_video_count = total_videos

        logger.info("LLM統合分析完了: %d動画を分析", report.analyzed_video_count)
        return report

    def _build_contents(
        self,
        keyword: str,
        seed_videos: list[SeedVideoData],
    ) -> list[types.Part]:
        """LLMへの入力コンテンツを構築する."""
        parts: list[types.Part] = []

        # ヘッダー
        parts.append(types.Part.from_text(text=f"# トレンド分析依頼\n\nキーワード: 「{keyword}」\n"))

        # シード動画（深い分析）
        for i, seed in enumerate(seed_videos, 1):
            parts.append(
                types.Part.from_text(
                    text=f"\n## シード動画 {i}\n- ユーザーメモ: {seed.user_note}\n",
                )
            )

            # ユーザー提供のスクリーンショット画像
            for j, capture in enumerate(seed.scene_captures, 1):
                if capture.image_path.exists():
                    image_bytes = capture.image_path.read_bytes()
                    # 拡張子からMIMEタイプを推定
                    suffix = capture.image_path.suffix.lower()
                    mime_map = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp"}
                    mime_type = mime_map.get(suffix, "image/png")
                    parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))

                timestamp = f" (約{capture.timestamp_sec:.1f}秒地点)" if capture.timestamp_sec else ""
                parts.append(
                    types.Part.from_text(
                        text=f"  シーン{j}{timestamp}: {capture.description}\n",
                    )
                )

        # 分析指示
        total = len(seed_videos)
        parts.append(
            types.Part.from_text(
                text=f"\n# 分析指示\n"
                f"上記の全データを分析し、「{keyword}」ジャンルのショート動画の"
                f"トレンドレポートをJSON形式で生成してください。\n"
                f"keyword は「{keyword}」、analyzed_video_count は {total} としてください。\n",
            )
        )

        return parts
