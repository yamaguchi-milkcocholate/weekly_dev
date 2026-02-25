"""engine.py の統合テスト."""

import json
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from daily_routine.audio.engine import AudioEngine, _get_audio_duration
from daily_routine.audio.se_estimator import SEEstimation
from daily_routine.audio.suno import SunoTrack
from daily_routine.schemas.audio import BGM, AudioAsset, SoundEffect
from daily_routine.schemas.intelligence import AudioTrend
from daily_routine.schemas.pipeline_io import AudioInput
from daily_routine.schemas.scenario import CameraWork, Scenario, SceneSpec


def _make_audio_trend() -> AudioTrend:
    return AudioTrend(
        bpm_range=[110, 130],
        genres=["lo-fi", "chill hop"],
        volume_patterns=["イントロで小さく→メインで通常→ラストで余韻"],
        se_usage_points=[
            "朝の目覚めシーンでアラーム音",
            "ドアの開閉で場面転換を強調",
        ],
    )


def _make_scenario() -> Scenario:
    return Scenario(
        title="OLの一日",
        total_duration_sec=45.0,
        characters=[],
        props=[],
        scenes=[
            SceneSpec(
                scene_number=1,
                duration_sec=8.0,
                situation="朝、アラームが鳴りベッドから起き上がる",
                camera_work=CameraWork(type="close-up", description="アラーム"),
                caption_text="朝6時…今日も始まる",
                image_prompt="morning bedroom",
            ),
            SceneSpec(
                scene_number=2,
                duration_sec=7.0,
                situation="身支度を整え、玄関のドアを開けて出発する",
                camera_work=CameraWork(type="wide", description="玄関"),
                caption_text="いってきます！",
                image_prompt="entrance door",
            ),
        ],
        bgm_direction="朝の準備シーンに合う爽やかで軽快な曲、lo-fi系で統一",
    )


def _make_se_estimations() -> list[SEEstimation]:
    return [
        SEEstimation(se_name="alarm clock", scene_number=1, trigger_description="目覚まし時計のアラーム"),
        SEEstimation(se_name="door open close", scene_number=2, trigger_description="玄関のドアを開ける"),
    ]


def _place_bgm_file(output_dir: Path, filename: str = "lofi_morning.mp3") -> Path:
    """テスト用 BGM ファイルを配置するヘルパー."""
    candidates_dir = output_dir / "bgm" / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)
    file_path = candidates_dir / filename
    file_path.write_bytes(b"\xff\xfb\x90\x00" * 100)
    return file_path


def _place_se_file(output_dir: Path, scene_number: int, se_name: str) -> Path:
    """テスト用 SE ファイルを配置するヘルパー."""
    se_dir = output_dir / "se"
    se_dir.mkdir(parents=True, exist_ok=True)
    filename = f"scene_{scene_number:02d}_{se_name.replace(' ', '_')}.mp3"
    file_path = se_dir / filename
    file_path.write_bytes(b"\xff\xfb\x90\x00" * 10)
    return file_path


class TestAudioEngineGenerate:
    """AudioEngine.generate 統合テスト."""

    @pytest.mark.asyncio
    async def test_generate_配置済みBGMとSEで完了_Suno未使用(self, tmp_path: Path) -> None:
        """BGM と SE がディレクトリに配置済み → そのまま完了."""
        engine = AudioEngine(google_ai_api_key="gemini-key")
        output_dir = tmp_path / "audio"

        # BGM と SE を配置
        _place_bgm_file(output_dir)
        _place_se_file(output_dir, 1, "alarm clock")
        _place_se_file(output_dir, 2, "door open close")

        mock_estimator = AsyncMock()
        mock_estimator.estimate = AsyncMock(return_value=_make_se_estimations())

        with (
            patch("daily_routine.audio.engine.SEEstimator", return_value=mock_estimator),
            patch("daily_routine.audio.engine._get_audio_duration", return_value=120.0),
        ):
            result = await engine.generate(
                audio_trend=_make_audio_trend(),
                scenario=_make_scenario(),
                output_dir=output_dir,
            )

        assert isinstance(result, AudioAsset)
        assert result.bgm.source == "manual"
        assert result.bgm.duration_sec == 120.0
        assert len(result.sound_effects) == 2
        assert result.sound_effects[0].name == "alarm clock"
        assert result.sound_effects[0].trigger_time_ms == 0
        assert result.sound_effects[1].name == "door open close"

        # 調達リストが保存されている
        assert (output_dir / "procurement.json").exists()
        # SE 推定結果が保存されている
        assert (output_dir / "tmp" / "se_estimations.json").exists()

    @pytest.mark.asyncio
    async def test_generate_BGM未配置_Sunoフォールバック(self, tmp_path: Path) -> None:
        """BGM 未配置 → Suno API で生成にフォールバック."""
        engine = AudioEngine(suno_api_key="suno-key", google_ai_api_key="gemini-key")
        output_dir = tmp_path / "audio"

        suno_tracks = [
            SunoTrack(
                track_id="suno-001",
                title="Generated BGM",
                audio_url="https://cdn.suno.ai/suno-001.mp3",
                duration_sec=62.0,
                tags=["lo-fi"],
                status="complete",
            ),
        ]
        mock_suno = AsyncMock(spec=["generate", "download"])
        mock_suno.generate = AsyncMock(return_value=suno_tracks)
        mock_suno.download = AsyncMock(side_effect=lambda url, path: _write_dummy_file(path))

        mock_estimator = AsyncMock()
        mock_estimator.estimate = AsyncMock(return_value=[])

        with (
            patch("daily_routine.audio.engine.SunoClient", return_value=mock_suno),
            patch("daily_routine.audio.engine.SEEstimator", return_value=mock_estimator),
        ):
            result = await engine.generate(
                audio_trend=_make_audio_trend(),
                scenario=_make_scenario(),
                output_dir=output_dir,
            )

        assert result.bgm.source == "suno"
        assert result.bgm.duration_sec == 62.0
        mock_suno.generate.assert_called_once()

    @pytest.mark.asyncio
    async def test_generate_BGM未配置_Sunoなし_エラー(self, tmp_path: Path) -> None:
        """BGM 未配置 + Suno キーなし → RuntimeError."""
        engine = AudioEngine(google_ai_api_key="gemini-key")
        output_dir = tmp_path / "audio"

        mock_estimator = AsyncMock()
        mock_estimator.estimate = AsyncMock(return_value=[])

        with (
            patch("daily_routine.audio.engine.SEEstimator", return_value=mock_estimator),
            pytest.raises(RuntimeError, match="BGM が配置されていません"),
        ):
            await engine.generate(
                audio_trend=_make_audio_trend(),
                scenario=_make_scenario(),
                output_dir=output_dir,
            )

        # エラーでも調達リストは保存される
        assert (output_dir / "procurement.json").exists()

    @pytest.mark.asyncio
    async def test_generate_SE一部未配置_配置済みのみ処理(self, tmp_path: Path) -> None:
        """SE の一部のみ配置 → 配置済みのみ SoundEffect に含まれる."""
        engine = AudioEngine(google_ai_api_key="gemini-key")
        output_dir = tmp_path / "audio"

        # BGM と SE（1件のみ）を配置
        _place_bgm_file(output_dir)
        _place_se_file(output_dir, 1, "alarm clock")
        # scene_02_door_open_close.mp3 は未配置

        mock_estimator = AsyncMock()
        mock_estimator.estimate = AsyncMock(return_value=_make_se_estimations())

        with (
            patch("daily_routine.audio.engine.SEEstimator", return_value=mock_estimator),
            patch("daily_routine.audio.engine._get_audio_duration", return_value=120.0),
        ):
            result = await engine.generate(
                audio_trend=_make_audio_trend(),
                scenario=_make_scenario(),
                output_dir=output_dir,
            )

        assert len(result.sound_effects) == 1
        assert result.sound_effects[0].name == "alarm clock"

    @pytest.mark.asyncio
    async def test_generate_SE推定キャッシュ_再実行時はGemini不要(self, tmp_path: Path) -> None:
        """SE 推定結果がキャッシュされていれば Gemini を呼ばない."""
        engine = AudioEngine()
        output_dir = tmp_path / "audio"

        # BGM を配置
        _place_bgm_file(output_dir)

        # SE 推定キャッシュを事前に配置
        tmp_dir = output_dir / "tmp"
        tmp_dir.mkdir(parents=True, exist_ok=True)
        cache_data = [e.model_dump(mode="json") for e in _make_se_estimations()]
        (tmp_dir / "se_estimations.json").write_text(json.dumps(cache_data), encoding="utf-8")

        with patch("daily_routine.audio.engine._get_audio_duration", return_value=120.0):
            result = await engine.generate(
                audio_trend=_make_audio_trend(),
                scenario=_make_scenario(),
                output_dir=output_dir,
            )

        # SEEstimator は呼ばれない（キャッシュから読み込み）
        assert isinstance(result, AudioAsset)


class TestAudioEngineProcurement:
    """調達リスト生成のテスト."""

    @pytest.mark.asyncio
    async def test_procurement_BGM条件とSE名が含まれる(self, tmp_path: Path) -> None:
        engine = AudioEngine(google_ai_api_key="gemini-key")
        output_dir = tmp_path / "audio"

        # BGM を配置（エラーを避ける）
        _place_bgm_file(output_dir)

        mock_estimator = AsyncMock()
        mock_estimator.estimate = AsyncMock(return_value=_make_se_estimations())

        with (
            patch("daily_routine.audio.engine.SEEstimator", return_value=mock_estimator),
            patch("daily_routine.audio.engine._get_audio_duration", return_value=120.0),
        ):
            await engine.generate(
                audio_trend=_make_audio_trend(),
                scenario=_make_scenario(),
                output_dir=output_dir,
            )

        procurement_path = output_dir / "procurement.json"
        assert procurement_path.exists()

        data = json.loads(procurement_path.read_text())
        assert data["bgm"]["genres"] == ["lo-fi", "chill hop"]
        assert data["bgm"]["bpm_range"] == [110, 130]
        assert data["bgm"]["min_duration_sec"] == 45.0
        assert "朝の準備シーン" in data["bgm"]["direction"]
        assert len(data["sound_effects"]) == 2
        assert data["sound_effects"][0]["se_name"] == "alarm clock"
        assert data["sound_effects"][0]["expected_filename"] == "scene_01_alarm_clock.*"
        assert data["sound_effects"][1]["se_name"] == "door open close"


class TestAudioEngineStepEngine:
    """StepEngine インターフェースのテスト."""

    @pytest.mark.asyncio
    async def test_execute_AudioInput経由(self) -> None:
        engine = AudioEngine(google_ai_api_key="gemini-key")

        mock_asset = AudioAsset(
            bgm=BGM(
                file_path=Path("audio/bgm/selected.mp3"),
                bpm=0,
                genre="lo-fi",
                duration_sec=120,
                source="manual",
            ),
            sound_effects=[],
        )
        mock_generate = AsyncMock(return_value=mock_asset)

        with patch.object(engine, "generate", mock_generate):
            input_data = AudioInput(audio_trend=_make_audio_trend(), scenario=_make_scenario())
            result = await engine.execute(input_data, Path("/tmp/test"))

        assert isinstance(result, AudioAsset)
        mock_generate.assert_called_once()

    def test_save_output_and_load_output(self, tmp_path: Path) -> None:
        engine = AudioEngine()
        asset = AudioAsset(
            bgm=BGM(
                file_path=Path("audio/bgm/selected.mp3"),
                bpm=0,
                genre="lo-fi",
                duration_sec=120.0,
                source="manual",
            ),
            sound_effects=[
                SoundEffect(
                    name="alarm clock",
                    file_path=Path("audio/se/scene_01_alarm_clock.mp3"),
                    trigger_time_ms=0,
                    scene_number=1,
                    trigger_description="目覚まし時計のアラーム",
                ),
            ],
        )

        engine.save_output(tmp_path, asset)

        asset_path = tmp_path / "audio" / "audio_asset.json"
        assert asset_path.exists()

        loaded = engine.load_output(tmp_path)
        assert loaded.bgm.genre == "lo-fi"
        assert loaded.bgm.duration_sec == 120.0
        assert len(loaded.sound_effects) == 1
        assert loaded.sound_effects[0].name == "alarm clock"

    def test_load_output_ファイルなし_FileNotFoundError(self, tmp_path: Path) -> None:
        engine = AudioEngine()
        with pytest.raises(FileNotFoundError, match="AudioAsset"):
            engine.load_output(tmp_path)

    def test_save_output_JSONラウンドトリップ(self, tmp_path: Path) -> None:
        engine = AudioEngine()
        asset = AudioAsset(
            bgm=BGM(
                file_path=Path("audio/bgm/selected.mp3"),
                bpm=118,
                genre="lo-fi chill hop",
                duration_sec=62.0,
                source="suno",
            ),
            sound_effects=[],
        )

        engine.save_output(tmp_path, asset)

        asset_path = tmp_path / "audio" / "audio_asset.json"
        data = json.loads(asset_path.read_text())
        assert data["bgm"]["source"] == "suno"
        assert data["bgm"]["bpm"] == 118


class TestAudioEngineBuildBgmPrompt:
    """_build_bgm_prompt のテスト."""

    def test_build_bgm_prompt_ジャンルとBPMを含む(self) -> None:
        prompt = AudioEngine._build_bgm_prompt(_make_audio_trend(), _make_scenario())

        assert "lo-fi" in prompt
        assert "chill hop" in prompt
        assert "110-130 BPM" in prompt
        assert "instrumental" in prompt
        assert "朝の準備シーン" in prompt


class TestAudioEngineScanFiles:
    """ファイルスキャン関連のテスト."""

    def test_scan_bgm_candidates_配置あり(self, tmp_path: Path) -> None:
        engine = AudioEngine()
        output_dir = tmp_path / "audio"
        _place_bgm_file(output_dir, "track1.mp3")
        _place_bgm_file(output_dir, "track2.wav")

        with patch("daily_routine.audio.engine._get_audio_duration", return_value=60.0):
            candidates = engine._scan_bgm_candidates(output_dir)

        assert len(candidates) == 2
        assert all(c.source == "manual" for c in candidates)
        assert all(c.relevance_score == 0.9 for c in candidates)

    def test_scan_bgm_candidates_配置なし_空リスト(self, tmp_path: Path) -> None:
        engine = AudioEngine()
        output_dir = tmp_path / "audio"
        (output_dir / "bgm" / "candidates").mkdir(parents=True, exist_ok=True)

        candidates = engine._scan_bgm_candidates(output_dir)
        assert candidates == []

    def test_scan_bgm_candidates_非音声ファイルを除外(self, tmp_path: Path) -> None:
        engine = AudioEngine()
        output_dir = tmp_path / "audio"
        candidates_dir = output_dir / "bgm" / "candidates"
        candidates_dir.mkdir(parents=True, exist_ok=True)
        (candidates_dir / "readme.txt").write_text("not audio")
        _place_bgm_file(output_dir, "valid.mp3")

        with patch("daily_routine.audio.engine._get_audio_duration", return_value=60.0):
            candidates = engine._scan_bgm_candidates(output_dir)

        assert len(candidates) == 1
        assert candidates[0].file_path.name == "valid.mp3"

    def test_scan_se_files_全配置(self, tmp_path: Path) -> None:
        engine = AudioEngine()
        output_dir = tmp_path / "audio"
        _place_se_file(output_dir, 1, "alarm clock")
        _place_se_file(output_dir, 2, "door open close")

        result = engine._scan_se_files(output_dir, _make_se_estimations())

        assert len(result) == 2
        assert result[0].name == "alarm clock"
        assert result[0].scene_number == 1
        assert result[1].name == "door open close"

    def test_scan_se_files_一部未配置(self, tmp_path: Path) -> None:
        engine = AudioEngine()
        output_dir = tmp_path / "audio"
        _place_se_file(output_dir, 1, "alarm clock")
        # scene_02 は未配置

        result = engine._scan_se_files(output_dir, _make_se_estimations())

        assert len(result) == 1
        assert result[0].name == "alarm clock"

    def test_scan_se_files_wav拡張子でも検出(self, tmp_path: Path) -> None:
        engine = AudioEngine()
        output_dir = tmp_path / "audio"
        se_dir = output_dir / "se"
        se_dir.mkdir(parents=True, exist_ok=True)
        (se_dir / "scene_01_alarm_clock.wav").write_bytes(b"\x00" * 10)

        estimations = [SEEstimation(se_name="alarm clock", scene_number=1, trigger_description="test")]
        result = engine._scan_se_files(output_dir, estimations)

        assert len(result) == 1
        assert result[0].file_path == Path("audio/se/scene_01_alarm_clock.wav")


class TestGetAudioDuration:
    """_get_audio_duration のテスト."""

    def test_不正ファイル_0を返す(self, tmp_path: Path) -> None:
        file_path = tmp_path / "invalid.mp3"
        file_path.write_bytes(b"\x00" * 10)

        result = _get_audio_duration(file_path)
        assert result == 0.0

    def test_存在しないファイル_0を返す(self, tmp_path: Path) -> None:
        result = _get_audio_duration(tmp_path / "nonexistent.mp3")
        assert result == 0.0


def _write_dummy_file(path: Path) -> Path:
    """ダミーファイルを書き込むヘルパー."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"\xff\xfb\x90\x00" * 10)
    return path
