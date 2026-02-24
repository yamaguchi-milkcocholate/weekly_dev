"""AudioEngine（ABC の具象実装）."""

import json
import logging
import shutil
from pathlib import Path

from mutagen import File as MutagenFile
from pydantic import BaseModel, Field

from daily_routine.audio.base import AudioEngineBase
from daily_routine.audio.bgm_selector import BGMCandidate, BGMSelector
from daily_routine.audio.se_estimator import SEEstimation, SEEstimator
from daily_routine.audio.suno import SunoClient, SunoTrack
from daily_routine.pipeline.base import StepEngine
from daily_routine.schemas.audio import BGM, AudioAsset, SoundEffect
from daily_routine.schemas.intelligence import AudioTrend
from daily_routine.schemas.pipeline_io import AudioInput
from daily_routine.schemas.scenario import Scenario

logger = logging.getLogger(__name__)

_ASSET_FILENAME = "audio_asset.json"
_PROCUREMENT_FILENAME = "procurement.json"
_AUDIO_EXTENSIONS = {".mp3", ".wav", ".ogg", ".m4a", ".flac"}


class BGMCriteria(BaseModel):
    """BGM の調達条件."""

    genres: list[str] = Field(description="ジャンル")
    bpm_range: list[int] = Field(description="BPM 範囲 [min, max]")
    min_duration_sec: float = Field(description="最低楽曲長（秒）")
    direction: str = Field(description="BGM の方向性指示")
    placement_dir: str = Field(description="ファイル配置先ディレクトリ（相対パス）")


class SEProcurementItem(BaseModel):
    """SE 調達リストの1項目."""

    se_name: str = Field(description="SE の名前（英語、検索キーワード）")
    scene_number: int = Field(description="挿入するシーン番号")
    trigger_description: str = Field(description="トリガーとなる動作/物体の説明")
    expected_filename: str = Field(description="期待するファイル名")


class AudioProcurement(BaseModel):
    """音声素材の調達リスト."""

    bgm: BGMCriteria
    sound_effects: list[SEProcurementItem]


class AudioEngine(StepEngine[AudioInput, AudioAsset], AudioEngineBase):
    """Audio Engine の具象実装.

    「調達リスト出力 + 人手配置 + ローカルスキャン」方式で動作する。

    1. SE 推定（Gemini）と BGM 条件を procurement.json に出力
    2. audio/bgm/candidates/ と audio/se/ に配置されたファイルをスキャン
    3. 配置済みファイルから AudioAsset を構築

    BGM が未配置の場合、Suno API（オプション）でフォールバック生成可能。
    """

    def __init__(
        self,
        suno_api_key: str = "",
        google_ai_api_key: str = "",
        max_se_per_scene: int = 2,
    ) -> None:
        self._suno_api_key = suno_api_key
        self._google_ai_api_key = google_ai_api_key
        self._max_se_per_scene = max_se_per_scene

    async def execute(self, input_data: AudioInput, project_dir: Path) -> AudioAsset:
        """パイプラインステップとして実行する."""
        return await self.generate(
            audio_trend=input_data.audio_trend,
            scenario=input_data.scenario,
            output_dir=project_dir / "audio",
        )

    async def generate(
        self,
        audio_trend: AudioTrend,
        scenario: Scenario,
        output_dir: Path,
    ) -> AudioAsset:
        """トレンド分析とシナリオに基づき、BGM と SE を調達する."""
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / "bgm" / "candidates").mkdir(parents=True, exist_ok=True)
        (output_dir / "se").mkdir(parents=True, exist_ok=True)
        (output_dir / "tmp").mkdir(parents=True, exist_ok=True)

        # SE 推定（Gemini）を実行し、調達リストを生成・保存
        estimations = await self._estimate_se(audio_trend, scenario, output_dir)
        self._save_procurement(output_dir, audio_trend, scenario, estimations)

        # Phase A: BGM 調達
        logger.info("Phase A: BGM 調達開始")
        bgm = await self._phase_a_bgm(audio_trend, scenario, output_dir)

        # Phase B: SE 割り当て（配置済みファイルをスキャン）
        logger.info("Phase B: SE 割り当て開始")
        sound_effects = self._scan_se_files(output_dir, estimations)

        return AudioAsset(bgm=bgm, sound_effects=sound_effects)

    async def _estimate_se(
        self,
        audio_trend: AudioTrend,
        scenario: Scenario,
        output_dir: Path,
    ) -> list[SEEstimation]:
        """SE 推定を実行する（キャッシュがあればロード）.

        Args:
            audio_trend: 音響トレンド
            scenario: シナリオ
            output_dir: 出力ディレクトリ

        Returns:
            SE 推定結果のリスト
        """
        # キャッシュ確認
        cache_path = output_dir / "tmp" / "se_estimations.json"
        if cache_path.exists():
            logger.info("SE 推定結果をキャッシュから読み込みます: %s", cache_path)
            data = json.loads(cache_path.read_text(encoding="utf-8"))
            return [SEEstimation.model_validate(item) for item in data]

        if not self._google_ai_api_key:
            logger.warning("Google AI API キーが未設定。SE 推定をスキップします。")
            return []

        estimator = SEEstimator(
            api_key=self._google_ai_api_key,
            max_se_per_scene=self._max_se_per_scene,
        )
        estimations = await estimator.estimate(
            scenes=scenario.scenes,
            se_usage_points=audio_trend.se_usage_points,
        )

        # キャッシュ保存
        self._save_se_estimations(output_dir, estimations)
        return estimations

    async def _phase_a_bgm(
        self,
        audio_trend: AudioTrend,
        scenario: Scenario,
        output_dir: Path,
    ) -> BGM:
        """Phase A: BGM 調達（人手配置優先 + Suno フォールバック）.

        Args:
            audio_trend: 音響トレンド
            scenario: シナリオ
            output_dir: 出力ディレクトリ

        Returns:
            選定された BGM

        Raises:
            RuntimeError: BGM を調達できなかった場合
        """
        selector = BGMSelector()
        bpm_range = (audio_trend.bpm_range[0], audio_trend.bpm_range[1])

        # Step 1: 配置済み BGM ファイルをスキャン
        candidates = self._scan_bgm_candidates(output_dir)
        if candidates:
            logger.info("配置済み BGM 候補: %d件", len(candidates))
            selected = selector.select(candidates, bpm_range, scenario.total_duration_sec)
            if selected is not None:
                return self._finalize_bgm(selected, output_dir)

        # Step 2: Suno フォールバック（API キーがある場合のみ）
        if self._suno_api_key:
            logger.warning("配置済み BGM で条件を満たす候補がありません。Suno API で生成します。")
            selected = await self._suno_fallback(audio_trend, scenario, output_dir, selector, bpm_range)
            if selected is not None:
                return self._finalize_bgm(selected, output_dir)

        # Step 3: BGM 未調達
        msg = (
            "BGM が配置されていません。"
            f" {output_dir / _PROCUREMENT_FILENAME} を参照し、"
            f" {output_dir / 'bgm' / 'candidates'} に BGM ファイルを配置してください。"
        )
        raise RuntimeError(msg)

    def _finalize_bgm(self, selected: BGMCandidate, output_dir: Path) -> BGM:
        """選定された BGM を selected ファイルにコピーし、BGM オブジェクトを返す."""
        selected_path = output_dir / "bgm" / "selected.mp3"
        shutil.copy2(selected.file_path, selected_path)

        return BGM(
            file_path=Path("audio/bgm/selected.mp3"),
            bpm=selected.estimated_bpm or 0,
            genre=selected.genre,
            duration_sec=selected.duration_sec,
            source=selected.source,
        )

    async def _suno_fallback(
        self,
        audio_trend: AudioTrend,
        scenario: Scenario,
        output_dir: Path,
        selector: BGMSelector,
        bpm_range: tuple[int, int],
    ) -> BGMCandidate | None:
        """Suno API で BGM を生成する（フォールバック）."""
        suno_client = SunoClient(api_key=self._suno_api_key)
        prompt = self._build_bgm_prompt(audio_trend, scenario)
        logger.info("Suno BGM 生成: prompt=%s", prompt[:100])

        suno_tracks = await suno_client.generate(prompt=prompt)

        suno_candidates: list[BGMCandidate] = []
        for i, track in enumerate(suno_tracks):
            candidate_path = output_dir / "bgm" / "candidates" / f"suno_{i + 1:03d}.mp3"
            try:
                await suno_client.download(track.audio_url, candidate_path)
                suno_candidates.append(self._suno_to_candidate(track, candidate_path))
            except Exception:
                logger.warning("Suno BGM ダウンロードスキップ: %s", track.title, exc_info=True)

        return selector.select(suno_candidates, bpm_range, scenario.total_duration_sec)

    def _scan_bgm_candidates(self, output_dir: Path) -> list[BGMCandidate]:
        """配置済み BGM ファイルをスキャンして候補リストを構築する.

        audio/bgm/candidates/ 内の音声ファイルを検出し、
        mutagen で duration を取得して BGMCandidate を生成する。

        Args:
            output_dir: 出力ディレクトリ

        Returns:
            BGM 候補リスト
        """
        candidates_dir = output_dir / "bgm" / "candidates"
        if not candidates_dir.exists():
            return []

        candidates: list[BGMCandidate] = []
        for audio_file in sorted(candidates_dir.iterdir()):
            if audio_file.suffix.lower() not in _AUDIO_EXTENSIONS:
                continue
            duration = _get_audio_duration(audio_file)
            candidates.append(
                BGMCandidate(
                    file_path=audio_file,
                    source="manual",
                    duration_sec=duration,
                    genre="",
                    estimated_bpm=None,
                    relevance_score=0.9,
                )
            )
            logger.debug("BGM 候補検出: %s (%.1f秒)", audio_file.name, duration)

        return candidates

    def _scan_se_files(
        self,
        output_dir: Path,
        estimations: list[SEEstimation],
    ) -> list[SoundEffect]:
        """配置済み SE ファイルをスキャンして SoundEffect リストを構築する.

        SE 推定結果の期待ファイル名と一致するファイルを audio/se/ から検出する。

        Args:
            output_dir: 出力ディレクトリ
            estimations: SE 推定結果

        Returns:
            SoundEffect リスト
        """
        se_dir = output_dir / "se"
        sound_effects: list[SoundEffect] = []

        for est in estimations:
            expected_stem = f"scene_{est.scene_number:02d}_{est.se_name.replace(' ', '_')}"
            matched_file = self._find_audio_file(se_dir, expected_stem)

            if matched_file is not None:
                relative_path = Path("audio/se") / matched_file.name
                sound_effects.append(
                    SoundEffect(
                        name=est.se_name,
                        file_path=relative_path,
                        trigger_time_ms=0,  # T2-3 で映像ベースに算出
                        scene_number=est.scene_number,
                        trigger_description=est.trigger_description,
                    )
                )
                logger.info("SE 検出: %s", matched_file.name)
            else:
                logger.warning("SE ファイル未配置（スキップ）: %s.*", expected_stem)

        logger.info("SE 検出完了: %d/%d 件", len(sound_effects), len(estimations))
        return sound_effects

    @staticmethod
    def _find_audio_file(directory: Path, stem: str) -> Path | None:
        """指定ディレクトリから拡張子を問わず音声ファイルを検索する."""
        for ext in _AUDIO_EXTENSIONS:
            candidate = directory / f"{stem}{ext}"
            if candidate.exists():
                return candidate
        return None

    def _save_procurement(
        self,
        output_dir: Path,
        audio_trend: AudioTrend,
        scenario: Scenario,
        estimations: list[SEEstimation],
    ) -> None:
        """調達リストを保存する."""
        se_items = [
            SEProcurementItem(
                se_name=est.se_name,
                scene_number=est.scene_number,
                trigger_description=est.trigger_description,
                expected_filename=f"scene_{est.scene_number:02d}_{est.se_name.replace(' ', '_')}.*",
            )
            for est in estimations
        ]

        procurement = AudioProcurement(
            bgm=BGMCriteria(
                genres=audio_trend.genres,
                bpm_range=audio_trend.bpm_range,
                min_duration_sec=scenario.total_duration_sec,
                direction=scenario.bgm_direction,
                placement_dir="audio/bgm/candidates/",
            ),
            sound_effects=se_items,
        )

        procurement_path = output_dir / _PROCUREMENT_FILENAME
        procurement_path.write_text(
            procurement.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("調達リストを保存しました: %s", procurement_path)

    @staticmethod
    def _build_bgm_prompt(audio_trend: AudioTrend, scenario: Scenario) -> str:
        """Suno 用の BGM 生成プロンプトを構築する."""
        genres = ", ".join(audio_trend.genres)
        bpm_min, bpm_max = audio_trend.bpm_range[0], audio_trend.bpm_range[1]
        return f"{genres}, {bpm_min}-{bpm_max} BPM, instrumental, {scenario.bgm_direction}"

    @staticmethod
    def _suno_to_candidate(track: SunoTrack, file_path: Path) -> BGMCandidate:
        """SunoTrack を BGMCandidate に変換する."""
        return BGMCandidate(
            file_path=file_path,
            source="suno",
            duration_sec=track.duration_sec,
            genre=", ".join(track.tags) if track.tags else "",
            estimated_bpm=None,
            relevance_score=0.8,
        )

    @staticmethod
    def _save_se_estimations(output_dir: Path, estimations: list[SEEstimation]) -> None:
        """SE 推定結果を保存する."""
        tmp_path = output_dir / "tmp" / "se_estimations.json"
        data = [e.model_dump(mode="json") for e in estimations]
        tmp_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        logger.debug("SE 推定結果を保存: %s", tmp_path)

    def load_output(self, project_dir: Path) -> AudioAsset:
        """永続化済みの AudioAsset を読み込む."""
        asset_path = project_dir / "audio" / _ASSET_FILENAME
        if not asset_path.exists():
            msg = f"AudioAsset ファイルが見つかりません: {asset_path}"
            raise FileNotFoundError(msg)
        return AudioAsset.model_validate_json(asset_path.read_text(encoding="utf-8"))

    def save_output(self, project_dir: Path, output: AudioAsset) -> None:
        """AudioAsset を永続化する."""
        audio_dir = project_dir / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)

        asset_path = audio_dir / _ASSET_FILENAME
        asset_path.write_text(
            output.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("AudioAsset を保存しました: %s", asset_path)


def _get_audio_duration(path: Path) -> float:
    """音声ファイルの duration を取得する.

    Args:
        path: 音声ファイルのパス

    Returns:
        duration（秒）。取得できない場合は 0.0
    """
    try:
        audio = MutagenFile(path)
        if audio is not None and audio.info is not None:
            return audio.info.length
    except Exception:
        logger.warning("音声メタデータ取得失敗: %s", path, exc_info=True)
    return 0.0
