"""bgm_selector.py のユニットテスト."""

from pathlib import Path

from daily_routine.audio.bgm_selector import BGMCandidate, BGMSelector


def _make_candidate(
    file_path: str = "audio/bgm/candidates/test.mp3",
    source: str = "manual",
    duration_sec: float = 120.0,
    genre: str = "lo-fi",
    estimated_bpm: int | None = None,
    relevance_score: float = 0.8,
) -> BGMCandidate:
    return BGMCandidate(
        file_path=Path(file_path),
        source=source,
        duration_sec=duration_sec,
        genre=genre,
        estimated_bpm=estimated_bpm,
        relevance_score=relevance_score,
    )


class TestBGMSelectorSelect:
    """select のテスト."""

    def test_select_正常_最高スコア候補を選定(self) -> None:
        selector = BGMSelector()
        candidates = [
            _make_candidate(file_path="a.mp3", relevance_score=0.92, duration_sec=120),
            _make_candidate(file_path="b.mp3", relevance_score=0.85, duration_sec=75),
            _make_candidate(file_path="c.mp3", relevance_score=0.68, duration_sec=90),
        ]

        result = selector.select(candidates, target_bpm_range=(110, 130), min_duration_sec=45.0)

        assert result is not None
        assert result.file_path == Path("a.mp3")

    def test_select_duration不足_除外(self) -> None:
        selector = BGMSelector()
        candidates = [
            _make_candidate(file_path="short.mp3", duration_sec=30, relevance_score=0.9),
        ]

        result = selector.select(candidates, target_bpm_range=(110, 130), min_duration_sec=45.0)

        assert result is None

    def test_select_relevance不足_除外(self) -> None:
        selector = BGMSelector()
        candidates = [
            _make_candidate(file_path="low_rel.mp3", duration_sec=120, relevance_score=0.3),
        ]

        result = selector.select(candidates, target_bpm_range=(110, 130), min_duration_sec=45.0)

        assert result is None

    def test_select_空リスト_None返却(self) -> None:
        selector = BGMSelector()

        result = selector.select([], target_bpm_range=(110, 130), min_duration_sec=45.0)

        assert result is None

    def test_select_BPM範囲内_スコア向上(self) -> None:
        selector = BGMSelector()
        # BPM なしの候補
        no_bpm = _make_candidate(file_path="no_bpm.mp3", relevance_score=0.8, estimated_bpm=None)
        # BPM 範囲内の候補（同じ relevance だが BPM スコアで上回る）
        with_bpm = _make_candidate(file_path="with_bpm.mp3", relevance_score=0.8, estimated_bpm=120)

        result = selector.select(
            [no_bpm, with_bpm],
            target_bpm_range=(110, 130),
            min_duration_sec=45.0,
        )

        assert result is not None
        assert result.file_path == Path("with_bpm.mp3")

    def test_select_BPM範囲外10以内_中間スコア(self) -> None:
        selector = BGMSelector()
        # BPM ±10 以内
        near_bpm = _make_candidate(file_path="near.mp3", relevance_score=0.8, estimated_bpm=105)
        # BPM 範囲外
        far_bpm = _make_candidate(file_path="far.mp3", relevance_score=0.8, estimated_bpm=80)

        result = selector.select(
            [near_bpm, far_bpm],
            target_bpm_range=(110, 130),
            min_duration_sec=45.0,
        )

        assert result is not None
        assert result.file_path == Path("near.mp3")

    def test_select_設計書の入出力例を検証(self) -> None:
        """設計書 4.2 節の BGM 候補メタデータ例に基づく検証."""
        selector = BGMSelector()
        candidates = [
            _make_candidate(file_path="candidate_001.mp3", duration_sec=120, relevance_score=0.92),
            _make_candidate(file_path="candidate_002.mp3", duration_sec=75, relevance_score=0.85),
            _make_candidate(file_path="candidate_003.mp3", duration_sec=90, relevance_score=0.68),
            _make_candidate(file_path="candidate_004.mp3", duration_sec=30, relevance_score=0.55),
            _make_candidate(file_path="candidate_005.mp3", duration_sec=45, relevance_score=0.38),
        ]

        result = selector.select(candidates, target_bpm_range=(110, 130), min_duration_sec=45.0)

        assert result is not None
        # candidate_001 が選定される（score = 0.92 * 0.7 + 0.0 * 0.3 = 0.644）
        assert result.file_path == Path("candidate_001.mp3")

    def test_select_duration境界値_丁度の場合は通過(self) -> None:
        selector = BGMSelector()
        candidates = [
            _make_candidate(file_path="exact.mp3", duration_sec=45.0, relevance_score=0.6),
        ]

        result = selector.select(candidates, target_bpm_range=(110, 130), min_duration_sec=45.0)

        assert result is not None
        assert result.file_path == Path("exact.mp3")


class TestBGMSelectorCalcBpmScore:
    """_calc_bpm_score のテスト."""

    def test_bpm_none_0を返す(self) -> None:
        assert BGMSelector._calc_bpm_score(None, (110, 130)) == 0.0

    def test_bpm_範囲内_1を返す(self) -> None:
        assert BGMSelector._calc_bpm_score(120, (110, 130)) == 1.0

    def test_bpm_範囲最小値_1を返す(self) -> None:
        assert BGMSelector._calc_bpm_score(110, (110, 130)) == 1.0

    def test_bpm_範囲最大値_1を返す(self) -> None:
        assert BGMSelector._calc_bpm_score(130, (110, 130)) == 1.0

    def test_bpm_10以内_05を返す(self) -> None:
        assert BGMSelector._calc_bpm_score(105, (110, 130)) == 0.5
        assert BGMSelector._calc_bpm_score(135, (110, 130)) == 0.5

    def test_bpm_範囲外_0を返す(self) -> None:
        assert BGMSelector._calc_bpm_score(80, (110, 130)) == 0.0
        assert BGMSelector._calc_bpm_score(160, (110, 130)) == 0.0
