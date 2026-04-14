"""IntelligenceEngine（ABCの具象実装）."""

import json
import logging
from pathlib import Path

from daily_routine.intelligence.base import IntelligenceEngineBase, SeedVideo
from daily_routine.intelligence.trend_aggregator import (
    SeedVideoData,
    TrendAggregator,
)
from daily_routine.pipeline.base import StepEngine
from daily_routine.schemas.intelligence import TrendReport
from daily_routine.schemas.pipeline_io import IntelligenceInput

logger = logging.getLogger(__name__)

_REPORT_FILENAME = "report.json"


class IntelligenceEngine(StepEngine[IntelligenceInput, TrendReport], IntelligenceEngineBase):
    """Intelligence Engine の具象実装.

    StepEngine[IntelligenceInput, TrendReport] を実装しパイプラインに統合しつつ、
    IntelligenceEngineBase の analyze() も実装する。
    """

    def __init__(
        self,
        google_ai_api_key: str = "",
    ) -> None:
        self._google_ai_api_key = google_ai_api_key

    async def execute(self, input_data: IntelligenceInput, project_dir: Path) -> TrendReport:
        """パイプラインステップとして実行する."""
        return await self.analyze(
            keyword=input_data.keyword,
            seed_videos=input_data.seed_videos,
        )

    async def analyze(
        self,
        keyword: str,
        seed_videos: list[SeedVideo],
    ) -> TrendReport:
        """ユーザー提供の競合動画情報を分析し、トレンドレポートを生成する."""
        # SeedVideo → SeedVideoData 変換
        seed_data_list = [
            SeedVideoData(
                scene_captures=seed.scene_captures,
                user_note=seed.note,
            )
            for seed in seed_videos
        ]

        logger.info("シード動画 %d 件からトレンド分析を開始", len(seed_data_list))

        # LLM 統合分析・トレンド集約
        aggregator = TrendAggregator(api_key=self._google_ai_api_key)
        report = await aggregator.aggregate(
            keyword=keyword,
            seed_videos=seed_data_list,
        )

        return report

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
