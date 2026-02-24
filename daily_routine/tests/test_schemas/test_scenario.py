"""schemas/scenario.py のテスト."""

from daily_routine.schemas.scenario import CameraWork, CharacterSpec, PropSpec, Scenario, SceneSpec


def _make_scenario() -> Scenario:
    return Scenario(
        title="OLの一日",
        total_duration_sec=45.0,
        characters=[
            CharacterSpec(
                name="花子",
                appearance="20代女性、黒髪ロング",
                outfit="オフィスカジュアル",
                reference_prompt="20s Japanese woman, long black hair, office casual",
            ),
        ],
        props=[
            PropSpec(
                name="スマートフォン",
                description="主人公が使用するスマホ",
                image_prompt="A modern smartphone, white background",
            ),
        ],
        scenes=[
            SceneSpec(
                scene_number=1,
                duration_sec=5.0,
                situation="朝の通勤",
                camera_work=CameraWork(type="POV", description="主観視点で駅を歩く"),
                caption_text="朝7時に出発！",
                image_prompt="Japanese train station morning",
                video_prompt="Walking in crowded station, POV",
            ),
        ],
        bgm_direction="朝の爽やかなLo-Fi",
    )


class TestScenario:
    """Scenario のテスト."""

    def test_create(self) -> None:
        scenario = _make_scenario()
        assert scenario.title == "OLの一日"
        assert len(scenario.characters) == 1
        assert len(scenario.scenes) == 1

    def test_roundtrip_json(self) -> None:
        scenario = _make_scenario()
        data = scenario.model_dump(mode="json")
        restored = Scenario(**data)
        assert restored.scenes[0].camera_work.type == "POV"
        assert restored.characters[0].name == "花子"
