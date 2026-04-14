"""pipeline/summarizer.py のテスト."""

import logging
from pathlib import Path

import pytest

from daily_routine.pipeline.summarizer import (
    StepSummarizer,
    log_item_summary,
    log_summary,
)
from daily_routine.schemas.asset import (
    AssetSet,
    CharacterAsset,
    EnvironmentAsset,
    KeyframeAsset,
)
from daily_routine.schemas.audio import BGM, AudioAsset, SoundEffect
from daily_routine.schemas.intelligence import AudioTrend
from daily_routine.schemas.keyframe_mapping import (
    CharacterComponent,
    KeyframeMapping,
    SceneKeyframeSpec,
)
from daily_routine.schemas.pipeline_io import AudioInput, KeyframeInput, VisualInput
from daily_routine.schemas.project import PipelineStep
from daily_routine.schemas.scenario import CameraWork, CharacterSpec, Scenario, SceneSpec
from daily_routine.schemas.storyboard import (
    CutSpec,
    MotionIntensity,
    SceneStoryboard,
    Storyboard,
    Transition,
)


def _make_scenario() -> Scenario:
    return Scenario(
        title="テスト動画",
        total_duration_sec=12.0,
        characters=[
            CharacterSpec(
                name="Ai",
                appearance="A young Japanese woman with long black hair",
                outfit="Beige knit sweater and dark brown pleated skirt",
                reference_prompt="Full body standing pose on green screen",
            ),
        ],
        scenes=[
            SceneSpec(
                scene_number=1,
                duration_sec=4.0,
                situation="朝の身支度",
                camera_work=CameraWork(type="medium", description="medium shot"),
                caption_text="朝の身支度",
                image_prompt="A modern bedroom with morning sunlight, no people",
            ),
            SceneSpec(
                scene_number=2,
                duration_sec=4.0,
                situation="通勤途中",
                camera_work=CameraWork(type="wide", description="wide shot"),
                caption_text="通勤途中",
                image_prompt="A busy city street in the morning",
            ),
            SceneSpec(
                scene_number=3,
                duration_sec=4.0,
                situation="カフェでモーニング",
                camera_work=CameraWork(type="close-up", description="close-up"),
                caption_text="カフェでモーニング",
                image_prompt="A cozy cafe interior with warm lighting, no people",
            ),
        ],
        bgm_direction="爽やかな朝をイメージした明るいポップス",
    )


def _make_storyboard() -> Storyboard:
    return Storyboard(
        title="テスト動画",
        total_duration_sec=12.0,
        total_cuts=3,
        scenes=[
            SceneStoryboard(
                scene_number=1,
                scene_duration_sec=4.0,
                cuts=[
                    CutSpec(
                        cut_id="s01_c01",
                        scene_number=1,
                        cut_number=1,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.SUBTLE,
                        camera_work="slow zoom-in",
                        action_description="鏡の前で身だしなみチェック",
                        motion_prompt="The woman adjusts her collar",
                        keyframe_prompt="@char in a bedroom adjusting collar",
                        transition=Transition.CUT,
                        pose_instruction="Standing in front of mirror",
                        has_character=True,
                    ),
                ],
            ),
            SceneStoryboard(
                scene_number=2,
                scene_duration_sec=4.0,
                cuts=[
                    CutSpec(
                        cut_id="s02_c01",
                        scene_number=2,
                        cut_number=1,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.STATIC,
                        camera_work="static",
                        action_description="街並みの風景",
                        motion_prompt="Busy street scene",
                        keyframe_prompt="City street morning",
                        transition=Transition.CUT,
                        has_character=False,
                    ),
                ],
            ),
            SceneStoryboard(
                scene_number=3,
                scene_duration_sec=4.0,
                cuts=[
                    CutSpec(
                        cut_id="s03_c01",
                        scene_number=3,
                        cut_number=1,
                        duration_sec=4.0,
                        motion_intensity=MotionIntensity.MODERATE,
                        camera_work="pan",
                        action_description="コーヒーを注文",
                        motion_prompt="@char orders coffee at counter",
                        keyframe_prompt="@char at cafe counter",
                        transition=Transition.CUT,
                        pose_instruction="Leaning on counter",
                        has_character=True,
                    ),
                ],
            ),
        ],
    )


def _make_assets(tmp_path: Path) -> AssetSet:
    front_on = tmp_path / "front_on.png"
    front_on.write_bytes(b"fake")
    front_off = tmp_path / "front_off.png"
    front_off.write_bytes(b"fake")
    env1 = tmp_path / "scene_01.png"
    env1.write_bytes(b"fake")
    env3 = tmp_path / "scene_03.png"
    env3.write_bytes(b"fake")

    return AssetSet(
        characters=[
            CharacterAsset(
                character_name="Ai",
                variant_id="on",
                front_view=front_on,
                identity_block="Young woman",
            ),
            CharacterAsset(
                character_name="Ai",
                variant_id="off",
                front_view=front_off,
                identity_block="Young woman casual",
            ),
        ],
        environments=[
            EnvironmentAsset(scene_number=1, description="bedroom", image_path=env1),
            EnvironmentAsset(scene_number=3, description="cafe", image_path=env3),
        ],
        keyframes=[
            KeyframeAsset(
                scene_number=1,
                image_path=tmp_path / "s01_c01.png",
                prompt="test",
                cut_id="s01_c01",
            ),
            KeyframeAsset(
                scene_number=3,
                image_path=tmp_path / "s03_c01.png",
                prompt="test",
                cut_id="s03_c01",
            ),
        ],
    )


def _make_keyframe_mapping() -> KeyframeMapping:
    return KeyframeMapping(
        scenes=[
            SceneKeyframeSpec(
                scene_number=1,
                environment="bedroom",
                pose="Standing in front of mirror",
                components=[CharacterComponent(character="Ai", variant_id="off")],
            ),
            SceneKeyframeSpec(
                scene_number=3,
                environment="cafe",
                pose="Leaning on counter",
                components=[CharacterComponent(character="Ai", variant_id="on")],
            ),
        ]
    )


# --- Keyframe 解決プレビューテスト ---


class TestStepPreKeyframe:
    """Keyframe ステップの実行前サマリーテスト."""

    def test_step_pre_keyframe_カットごとのvariant_idが表示される(self, tmp_path: Path) -> None:
        assets = _make_assets(tmp_path)
        mapping = _make_keyframe_mapping()
        input_data = KeyframeInput(
            scenario=_make_scenario(),
            storyboard=_make_storyboard(),
            assets=assets,
            keyframe_mapping=mapping,
        )

        summarizer = StepSummarizer()
        result = summarizer.build_step_pre_summary(PipelineStep.KEYFRAME, input_data, tmp_path)

        assert result is not None
        assert result.step == PipelineStep.KEYFRAME
        assert result.phase == "pre"

        # 総カット数
        total_entry = next(e for e in result.entries if e.label == "総カット数")
        assert total_entry.value == "3"

        # カットプレビュー
        assert len(result.item_summaries) == 3

        # s01_c01: Ai variant=off（mapping指定）
        s01 = result.item_summaries[0]
        char_entry = next(e for e in s01.entries if e.label == "キャラクター")
        assert "Ai" in char_entry.value
        assert "off" in char_entry.value

        # s02_c01: has_character=False → キャラクターなし
        s02 = result.item_summaries[1]
        char_entry = next(e for e in s02.entries if e.label == "キャラクター")
        assert char_entry.value == "(なし)"

    def test_step_pre_keyframe_環境画像なし_警告が出る(self, tmp_path: Path) -> None:
        assets = _make_assets(tmp_path)
        # scene_number=2 は環境アセットがない
        input_data = KeyframeInput(
            scenario=_make_scenario(),
            storyboard=_make_storyboard(),
            assets=assets,
            keyframe_mapping=None,
        )

        summarizer = StepSummarizer()
        result = summarizer.build_step_pre_summary(PipelineStep.KEYFRAME, input_data, tmp_path)

        assert result is not None
        # scene 2 用の警告
        assert any("scene_number=2" in w for w in result.warnings)

    def test_step_pre_keyframe_variant不一致_フォールバック警告(self, tmp_path: Path) -> None:
        assets = _make_assets(tmp_path)
        # variant_id "casual" は存在しない
        mapping = KeyframeMapping(
            scenes=[
                SceneKeyframeSpec(
                    scene_number=1,
                    environment="bedroom",
                    components=[CharacterComponent(character="Ai", variant_id="casual")],
                ),
            ]
        )
        input_data = KeyframeInput(
            scenario=_make_scenario(),
            storyboard=_make_storyboard(),
            assets=assets,
            keyframe_mapping=mapping,
        )

        summarizer = StepSummarizer()
        result = summarizer.build_step_pre_summary(PipelineStep.KEYFRAME, input_data, tmp_path)

        assert result is not None
        # variant 不一致の警告
        assert any("casual" in w for w in result.warnings)

    def test_step_pre_keyframe_マッピングなし_デフォルトキャラクター使用(self, tmp_path: Path) -> None:
        assets = _make_assets(tmp_path)
        input_data = KeyframeInput(
            scenario=_make_scenario(),
            storyboard=_make_storyboard(),
            assets=assets,
            keyframe_mapping=None,
        )

        summarizer = StepSummarizer()
        result = summarizer.build_step_pre_summary(PipelineStep.KEYFRAME, input_data, tmp_path)

        assert result is not None
        # keyframe_mapping なし
        mapping_entry = next(e for e in result.entries if e.label == "keyframe_mapping")
        assert mapping_entry.value == "なし"

        # has_character=True のカットはデフォルト(先頭)キャラクター
        s01 = result.item_summaries[0]
        char_entry = next(e for e in s01.entries if e.label == "キャラクター")
        assert "Ai" in char_entry.value
        assert "on" in char_entry.value  # 先頭は variant=on

    def test_step_pre_keyframe_has_character_false_キャラクターなし(self, tmp_path: Path) -> None:
        assets = _make_assets(tmp_path)
        input_data = KeyframeInput(
            scenario=_make_scenario(),
            storyboard=_make_storyboard(),
            assets=assets,
            keyframe_mapping=_make_keyframe_mapping(),
        )

        summarizer = StepSummarizer()
        result = summarizer.build_step_pre_summary(PipelineStep.KEYFRAME, input_data, tmp_path)

        assert result is not None
        # s02_c01 は has_character=False
        s02 = result.item_summaries[1]
        char_entry = next(e for e in s02.entries if e.label == "キャラクター")
        assert char_entry.value == "(なし)"


class TestItemPreKeyframe:
    """Keyframe アイテムの実行前サマリーテスト."""

    def test_item_pre_keyframe_単一カットの詳細表示(self, tmp_path: Path) -> None:
        assets = _make_assets(tmp_path)
        mapping = _make_keyframe_mapping()
        input_data = KeyframeInput(
            scenario=_make_scenario(),
            storyboard=_make_storyboard(),
            assets=assets,
            keyframe_mapping=mapping,
        )

        summarizer = StepSummarizer()
        result = summarizer.build_item_pre_summary(PipelineStep.KEYFRAME, "s01_c01", input_data, tmp_path)

        assert result is not None
        assert result.item_id == "s01_c01"

        # キャラクター情報
        char_entry = next(e for e in result.entries if e.label == "キャラクター")
        assert "Ai" in char_entry.value
        assert "off" in char_entry.value

        # 環境画像
        env_entry = next(e for e in result.entries if e.label == "環境画像")
        assert "scene_01.png" in env_entry.value

        # ポーズ
        pose_entry = next(e for e in result.entries if e.label == "pose_instruction")
        assert "Standing in front of mirror" in pose_entry.value

        # 出力パス
        assert result.output_path == "assets/keyframes/s01_c01.png"

        # 処理ステップ
        assert len(result.processing_steps) == 2
        assert result.processing_steps[0].name == "Flash Scene 分析"
        assert result.processing_steps[1].name == "Pro Keyframe 生成"


# --- Asset テスト ---


class TestStepPreAsset:
    """Asset ステップの実行前サマリーテスト."""

    def test_step_pre_asset_mapping存在_バリアント一覧表示(self, tmp_path: Path) -> None:
        scenario = _make_scenario()
        # mapping.yaml を配置
        mapping_path = tmp_path / "assets" / "reference" / "mapping.yaml"
        mapping_path.parent.mkdir(parents=True, exist_ok=True)
        mapping_path.write_text("characters: []")

        summarizer = StepSummarizer()
        result = summarizer.build_step_pre_summary(PipelineStep.ASSET, scenario, tmp_path)

        assert result is not None
        assert result.step == PipelineStep.ASSET
        mapping_entry = next(e for e in result.entries if e.label == "mapping.yaml")
        assert mapping_entry.value == "あり"

    def test_step_pre_asset_mapping不在(self, tmp_path: Path) -> None:
        scenario = _make_scenario()
        summarizer = StepSummarizer()
        result = summarizer.build_step_pre_summary(PipelineStep.ASSET, scenario, tmp_path)

        assert result is not None
        mapping_entry = next(e for e in result.entries if e.label == "mapping.yaml")
        assert mapping_entry.value == "なし"

    def test_item_pre_asset_キャラクターアイテムの種別表示(self, tmp_path: Path) -> None:
        scenario = _make_scenario()
        summarizer = StepSummarizer()
        result = summarizer.build_item_pre_summary(PipelineStep.ASSET, "char_Ai_casual", scenario, tmp_path)

        assert result is not None
        assert result.item_id == "char_Ai_casual"

        kind_entry = next(e for e in result.entries if e.label == "種別")
        assert kind_entry.value == "キャラクター"

        char_entry = next(e for e in result.entries if e.label == "キャラクター")
        assert char_entry.value == "Ai"

        variant_entry = next(e for e in result.entries if e.label == "バリアント")
        assert variant_entry.value == "casual"

        assert result.output_path == "assets/character/Ai/casual/front.png"
        assert len(result.processing_steps) == 3

    def test_item_pre_asset_環境アイテムの種別表示(self, tmp_path: Path) -> None:
        scenario = _make_scenario()
        summarizer = StepSummarizer()
        result = summarizer.build_item_pre_summary(PipelineStep.ASSET, "env_1", scenario, tmp_path)

        assert result is not None
        kind_entry = next(e for e in result.entries if e.label == "種別")
        assert kind_entry.value == "環境"

        assert result.output_path == "assets/environments/scene_01.png"


# --- Visual テスト ---


class TestItemPreVisual:
    """Visual アイテムの実行前サマリーテスト."""

    def test_item_pre_visual_キーフレームとmotion_prompt表示(self, tmp_path: Path) -> None:
        assets = _make_assets(tmp_path)
        input_data = VisualInput(
            scenario=_make_scenario(),
            storyboard=_make_storyboard(),
            assets=assets,
        )

        summarizer = StepSummarizer()
        result = summarizer.build_item_pre_summary(PipelineStep.VISUAL, "s01_c01", input_data, tmp_path)

        assert result is not None
        assert result.item_id == "s01_c01"

        # キーフレーム画像
        kf_entry = next(e for e in result.entries if e.label == "キーフレーム")
        assert "s01_c01.png" in kf_entry.value

        # motion_prompt + 日本語訳
        motion_entry = next(e for e in result.entries if e.label == "motion_prompt")
        assert "The woman adjusts her collar" in motion_entry.value
        assert "日本語: 鏡の前で身だしなみチェック" in motion_entry.value

        # 尺
        dur_entry = next(e for e in result.entries if e.label == "尺")
        assert dur_entry.value == "4sec"

        # 出力パス
        assert result.output_path == "clips/s01_c01.mp4"

        # 処理ステップ
        assert len(result.processing_steps) == 3


# --- Audio テスト ---


class TestStepPreAudio:
    """Audio ステップの実行前サマリーテスト."""

    def test_step_pre_audio_BGM方向性表示(self, tmp_path: Path) -> None:
        scenario = _make_scenario()
        audio_trend = AudioTrend(
            bpm_range=[100, 130],
            genres=["pop", "lo-fi"],
            volume_patterns=["consistent"],
            se_usage_points=[],
        )
        input_data = AudioInput(audio_trend=audio_trend, scenario=scenario)

        summarizer = StepSummarizer()
        result = summarizer.build_step_pre_summary(PipelineStep.AUDIO, input_data, tmp_path)

        assert result is not None
        assert result.step == PipelineStep.AUDIO

        bgm_entry = next(e for e in result.entries if e.label == "BGM方向性")
        assert "爽やか" in bgm_entry.value

        bpm_entry = next(e for e in result.entries if e.label == "BPM範囲")
        assert bpm_entry.value == "100-130"

        genre_entry = next(e for e in result.entries if e.label == "ジャンル")
        assert "pop" in genre_entry.value


class TestStepPostAudio:
    """Audio ステップの実行後サマリーテスト."""

    def test_step_post_audio_BGMファイル表示(self, tmp_path: Path) -> None:
        scenario = _make_scenario()
        audio_trend = AudioTrend(
            bpm_range=[100, 130],
            genres=[],
            volume_patterns=[],
            se_usage_points=[],
        )
        input_data = AudioInput(audio_trend=audio_trend, scenario=scenario)
        output = AudioAsset(
            bgm=BGM(
                file_path=Path("/tmp/bgm.mp3"),
                bpm=120,
                genre="pop",
                duration_sec=30.0,
                source="suno",
            ),
            sound_effects=[
                SoundEffect(
                    name="click",
                    file_path=Path("/tmp/click.wav"),
                    trigger_time_ms=1000,
                    scene_number=1,
                    trigger_description="button click",
                ),
            ],
        )

        summarizer = StepSummarizer()
        result = summarizer.build_step_post_summary(PipelineStep.AUDIO, input_data, output, tmp_path)

        assert result is not None
        bgm_entry = next(e for e in result.entries if e.label == "BGMファイル")
        assert bgm_entry.value == "bgm.mp3"

        se_entry = next(e for e in result.entries if e.label == "SE数")
        assert se_entry.value == "1"


# --- 共通テスト ---


class TestLogSummary:
    """ログ出力テスト."""

    def test_log_summary_info出力(self, caplog: pytest.LogCaptureFixture) -> None:
        from daily_routine.pipeline.summarizer import StepSummary, SummaryEntry

        summary = StepSummary(
            step=PipelineStep.ASSET,
            phase="pre",
            title="Test Summary",
            entries=[SummaryEntry(label="テスト", value="値")],
        )

        with caplog.at_level(logging.INFO, logger="daily_routine.pipeline.summarizer"):
            log_summary(summary)

        assert "Test Summary" in caplog.text
        assert "テスト: 値" in caplog.text

    def test_log_summary_warning出力(self, caplog: pytest.LogCaptureFixture) -> None:
        from daily_routine.pipeline.summarizer import StepSummary, SummaryEntry

        summary = StepSummary(
            step=PipelineStep.KEYFRAME,
            phase="pre",
            title="Warning Test",
            entries=[SummaryEntry(label="問題", value="見つからない", warning=True)],
            warnings=["test warning"],
        )

        with caplog.at_level(logging.WARNING, logger="daily_routine.pipeline.summarizer"):
            log_summary(summary)

        assert "問題: 見つからない" in caplog.text
        assert "test warning" in caplog.text

    def test_log_item_summary出力(self, caplog: pytest.LogCaptureFixture) -> None:
        from daily_routine.pipeline.summarizer import ItemSummary, ProcessingStep, SummaryEntry

        summary = ItemSummary(
            item_id="test_item",
            entries=[SummaryEntry(label="入力", value="テスト値")],
            output_path="out/test.png",
            processing_steps=[ProcessingStep(1, "Step1", "in", "out")],
        )

        with caplog.at_level(logging.INFO, logger="daily_routine.pipeline.summarizer"):
            log_item_summary(summary)

        assert "test_item" in caplog.text
        assert "テスト値" in caplog.text
        assert "out/test.png" in caplog.text


class TestUnsupportedStep:
    """未対応ステップのテスト."""

    def test_未対応ステップ_None返却(self, tmp_path: Path) -> None:
        summarizer = StepSummarizer()

        assert summarizer.build_step_pre_summary(PipelineStep.INTELLIGENCE, "dummy", tmp_path) is None
        assert summarizer.build_step_pre_summary(PipelineStep.SCENARIO, "dummy", tmp_path) is None
        assert summarizer.build_item_pre_summary(PipelineStep.AUDIO, "item", "dummy", tmp_path) is None
        assert summarizer.build_step_post_summary(PipelineStep.ASSET, "dummy", "out", tmp_path) is None
