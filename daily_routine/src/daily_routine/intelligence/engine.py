"""IntelligenceEngine（ABCの具象実装）."""

import json
import logging
from pathlib import Path

from daily_routine.intelligence.base import IntelligenceEngineBase, SeedVideo
from daily_routine.intelligence.downloader import AudioDownloader
from daily_routine.intelligence.transcript import TranscriptFetcher
from daily_routine.intelligence.trend_aggregator import (
    ExpandedVideoData,
    SeedVideoData,
    TrendAggregator,
)
from daily_routine.intelligence.youtube import YouTubeClient, extract_video_id
from daily_routine.pipeline.base import StepEngine
from daily_routine.schemas.intelligence import TrendReport
from daily_routine.schemas.pipeline_io import IntelligenceInput

logger = logging.getLogger(__name__)

_REPORT_FILENAME = "report.json"
_SEED_INPUT_FILENAME = "seed_input.json"


class IntelligenceEngine(StepEngine[IntelligenceInput, TrendReport], IntelligenceEngineBase):
    """Intelligence Engine の具象実装.

    StepEngine[IntelligenceInput, TrendReport] を実装しパイプラインに統合しつつ、
    IntelligenceEngineBase の analyze() も実装する。
    """

    def __init__(
        self,
        youtube_api_key: str = "",
        google_ai_api_key: str = "",
        openai_api_key: str = "",
    ) -> None:
        self._youtube_api_key = youtube_api_key
        self._google_ai_api_key = google_ai_api_key
        self._openai_api_key = openai_api_key

    async def execute(self, input_data: IntelligenceInput, project_dir: Path) -> TrendReport:
        """パイプラインステップとして実行する."""
        return await self.analyze(
            keyword=input_data.keyword,
            seed_videos=input_data.seed_videos,
            max_expand_videos=input_data.max_expand_videos,
        )

    async def analyze(
        self,
        keyword: str,
        seed_videos: list[SeedVideo],
        max_expand_videos: int = 10,
    ) -> TrendReport:
        """ユーザー提供の競合動画情報を分析し、トレンドレポートを生成する."""
        youtube_client = YouTubeClient(api_key=self._youtube_api_key)
        transcript_fetcher = TranscriptFetcher(openai_api_key=self._openai_api_key or None)

        try:
            # Phase A: シード動画の情報収集
            logger.info("Phase A: シード動画の情報収集 (%d件)", len(seed_videos))
            seed_data_list = await self._collect_seed_data(
                seed_videos,
                youtube_client,
                transcript_fetcher,
            )

            # Phase B: 拡張検索・追加情報取得
            logger.info("Phase B: 拡張検索 (最大%d件)", max_expand_videos)
            expanded_data_list = await self._expand_search(
                seed_data_list,
                keyword,
                max_expand_videos,
                youtube_client,
                transcript_fetcher,
            )

            # Phase C: LLM 統合分析・トレンド集約
            logger.info("Phase C: LLM 統合分析")
            aggregator = TrendAggregator(api_key=self._google_ai_api_key)
            report = await aggregator.aggregate(
                keyword=keyword,
                seed_videos=seed_data_list,
                expanded_videos=expanded_data_list,
            )

            return report
        finally:
            await youtube_client.close()

    async def _collect_seed_data(
        self,
        seed_videos: list[SeedVideo],
        youtube_client: YouTubeClient,
        transcript_fetcher: TranscriptFetcher,
    ) -> list[SeedVideoData]:
        """Phase A: シード動画のメタデータと字幕を収集する."""
        results = []
        for seed in seed_videos:
            video_id = extract_video_id(seed.url)
            logger.info("シード動画を処理中: %s (%s)", video_id, seed.url)

            # メタデータ取得（シード動画は必須 → 失敗時は例外を伝播）
            metadata = await youtube_client.get_video_metadata(video_id)

            # 字幕取得（失敗時はNone）
            transcript = await transcript_fetcher.fetch(video_id)
            if transcript.source == "none":
                # Whisperフォールバック用に音声ダウンロードを試行
                if self._openai_api_key:
                    try:
                        downloader = AudioDownloader(output_dir=Path("/tmp/daily_routine_audio"))
                        audio_path = await downloader.download(video_id)
                        transcript = await transcript_fetcher.fetch(video_id, audio_path=audio_path)
                    except Exception:
                        logger.warning("Whisperフォールバック失敗: %s", video_id, exc_info=True)

            results.append(
                SeedVideoData(
                    video_id=video_id,
                    metadata=metadata,
                    transcript=transcript if transcript.source != "none" else None,
                    scene_captures=seed.scene_captures,
                    user_note=seed.note,
                )
            )

        return results

    async def _expand_search(
        self,
        seed_data_list: list[SeedVideoData],
        keyword: str,
        max_expand_videos: int,
        youtube_client: YouTubeClient,
        transcript_fetcher: TranscriptFetcher,
    ) -> list[ExpandedVideoData]:
        """Phase B: 拡張検索で類似動画を取得する."""
        seed_metadata = [sd.metadata for sd in seed_data_list]

        expanded_metadata = await youtube_client.search_related(
            seed_metadata=seed_metadata,
            keyword=keyword,
            max_results=max_expand_videos,
        )

        if not expanded_metadata:
            logger.warning("拡張検索で類似動画が0件でした。シード動画のみで分析を続行します")
            return []

        results = []
        for meta in expanded_metadata:
            try:
                transcript = await transcript_fetcher.fetch(meta.video_id)
                results.append(
                    ExpandedVideoData(
                        video_id=meta.video_id,
                        metadata=meta,
                        transcript=transcript if transcript.source != "none" else None,
                    )
                )
            except Exception:
                logger.warning("拡張動画の処理に失敗（スキップ）: %s", meta.video_id, exc_info=True)
                continue

        logger.info("拡張検索動画: %d件取得", len(results))
        return results

    def load_output(self, project_dir: Path) -> TrendReport:
        """永続化済みの TrendReport を読み込む."""
        report_path = project_dir / "intelligence" / _REPORT_FILENAME
        if not report_path.exists():
            msg = f"TrendReportファイルが見つかりません: {report_path}"
            raise FileNotFoundError(msg)
        data = json.loads(report_path.read_text(encoding="utf-8"))
        return TrendReport.model_validate(data)

    def save_output(self, project_dir: Path, output: TrendReport) -> None:
        """TrendReport を永続化する."""
        intel_dir = project_dir / "intelligence"
        intel_dir.mkdir(parents=True, exist_ok=True)

        report_path = intel_dir / _REPORT_FILENAME
        report_path.write_text(
            output.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("TrendReport を保存しました: %s", report_path)
