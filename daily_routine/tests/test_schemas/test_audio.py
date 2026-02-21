"""schemas/audio.py のテスト."""

from pathlib import Path

from daily_routine.schemas.audio import AudioAsset, BGM, SoundEffect


def _make_audio_asset() -> AudioAsset:
    return AudioAsset(
        bgm=BGM(
            file_path=Path("audio/bgm/lofi_01.mp3"),
            bpm=120,
            genre="Lo-Fi",
            duration_sec=45.0,
            source="Suno",
        ),
        sound_effects=[
            SoundEffect(
                name="ドアベル",
                file_path=Path("audio/se/doorbell.mp3"),
                trigger_time_ms=5000,
                scene_number=1,
                trigger_description="ドアを開ける動作",
            ),
        ],
    )


class TestAudioAsset:
    """AudioAsset のテスト."""

    def test_create(self) -> None:
        audio = _make_audio_asset()
        assert audio.bgm.bpm == 120
        assert len(audio.sound_effects) == 1

    def test_roundtrip_json(self) -> None:
        audio = _make_audio_asset()
        data = audio.model_dump(mode="json")
        restored = AudioAsset(**data)
        assert restored.bgm.source == "Suno"
        assert restored.sound_effects[0].trigger_time_ms == 5000
