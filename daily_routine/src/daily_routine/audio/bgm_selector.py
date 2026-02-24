"""BGM 候補選定ロジック."""

import logging
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class BGMCandidate(BaseModel):
    """BGM 候補."""

    file_path: Path
    source: str = Field(description="'manual' | 'suno'")
    duration_sec: float
    genre: str
    estimated_bpm: int | None = Field(default=None, description="推定 BPM（取得可能な場合）")
    relevance_score: float = Field(default=0.0, description="検索関連度スコア（0〜1）")


class BGMSelector:
    """BGM 候補プールから最適な1曲を選定する."""

    RELEVANCE_THRESHOLD: float = 0.5

    def select(
        self,
        candidates: list[BGMCandidate],
        target_bpm_range: tuple[int, int],
        min_duration_sec: float,
    ) -> BGMCandidate | None:
        """候補プールから最適な BGM を選定する.

        選定基準（優先度順）:
        1. duration がシナリオ尺（min_duration_sec）以上であること（必須）
        2. relevance_score が閾値（RELEVANCE_THRESHOLD）以上であること
        3. スコアが最も高い候補を返す

        候補がない場合は None を返し、呼び出し元が Suno フォールバックを判断する。

        Args:
            candidates: BGM 候補リスト
            target_bpm_range: トレンドの BPM 範囲 (min, max)
            min_duration_sec: シナリオの合計尺

        Returns:
            選定された BGM 候補。条件を満たす候補がなければ None
        """
        # 1. duration フィルタ
        filtered = [c for c in candidates if c.duration_sec >= min_duration_sec]
        if not filtered:
            logger.warning("duration 条件 (>= %.1f秒) を満たす候補がありません", min_duration_sec)
            return None

        # 2. relevance フィルタ
        filtered = [c for c in filtered if c.relevance_score >= self.RELEVANCE_THRESHOLD]
        if not filtered:
            logger.warning("relevance 条件 (>= %.2f) を満たす候補がありません", self.RELEVANCE_THRESHOLD)
            return None

        # 3. スコアリング
        best: BGMCandidate | None = None
        best_score = -1.0

        for candidate in filtered:
            bpm_score = self._calc_bpm_score(candidate.estimated_bpm, target_bpm_range)
            score = candidate.relevance_score * 0.7 + bpm_score * 0.3
            logger.debug(
                "BGM候補スコア: %s (relevance=%.2f, bpm_score=%.2f, total=%.3f)",
                candidate.file_path,
                candidate.relevance_score,
                bpm_score,
                score,
            )
            if score > best_score:
                best_score = score
                best = candidate

        if best is not None:
            logger.info("BGM 選定: %s (score=%.3f)", best.file_path, best_score)

        return best

    @staticmethod
    def _calc_bpm_score(estimated_bpm: int | None, target_range: tuple[int, int]) -> float:
        """BPM スコアを計算する.

        Args:
            estimated_bpm: 推定 BPM（None の場合は 0.0）
            target_range: トレンドの BPM 範囲 (min, max)

        Returns:
            BPM スコア（0.0 / 0.5 / 1.0）
        """
        if estimated_bpm is None:
            return 0.0

        bpm_min, bpm_max = target_range

        # BPM が範囲内
        if bpm_min <= estimated_bpm <= bpm_max:
            return 1.0

        # BPM が ±10 以内
        if (bpm_min - 10) <= estimated_bpm <= (bpm_max + 10):
            return 0.5

        return 0.0
