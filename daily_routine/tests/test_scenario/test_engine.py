"""OpenAIScenarioEngine のモックテスト."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daily_routine.scenario.engine import OpenAIScenarioEngine
from daily_routine.schemas.intelligence import (
    AssetRequirement,
    AudioTrend,
    CaptionTrend,
    SceneStructure,
    TrendReport,
    VisualTrend,
)
from daily_routine.schemas.scenario import (
    CameraWork,
    CharacterSpec,
    PropSpec,
    Scenario,
    SceneSpec,
)


def _make_trend_report() -> TrendReport:
    """テスト用のTrendReportを作成する."""
    return TrendReport(
        keyword="OLの一日",
        analyzed_video_count=15,
        scene_structure=SceneStructure(
            total_scenes=8,
            avg_scene_duration_sec=5.0,
            hook_techniques=["目覚ましアラーム"],
            transition_patterns=["カット切り替え"],
        ),
        caption_trend=CaptionTrend(
            font_styles=["太ゴシック"],
            color_schemes=["白文字+黒縁"],
            animation_types=["ポップイン"],
            positions=["center-bottom"],
            emphasis_techniques=["キーワード拡大"],
        ),
        visual_trend=VisualTrend(
            situations=["朝の目覚め"],
            props=["スマートフォン"],
            camera_works=["POV"],
            color_tones=["warm filter"],
        ),
        audio_trend=AudioTrend(
            bpm_range=[110, 130],
            genres=["lo-fi pop"],
            volume_patterns=["冒頭やや大きめ"],
            se_usage_points=["目覚まし音"],
        ),
        asset_requirements=AssetRequirement(
            characters=["OL（主人公）"],
            props=["スマートフォン"],
            backgrounds=["ベッドルーム"],
        ),
    )


def _make_scenario(total_duration_sec: float = 45.0) -> Scenario:
    """テスト用のScenarioを作成する."""
    return Scenario(
        title="OLの一日 〜テスト編〜",
        total_duration_sec=total_duration_sec,
        characters=[
            CharacterSpec(
                name="Aoi",
                appearance="25-year-old Japanese woman",
                outfit="white blouse, navy skirt",
                reference_prompt="A 25-year-old Japanese woman, full body, white background",
            )
        ],
        props=[
            PropSpec(
                name="スマートフォン",
                description="主人公が使用するスマホ",
                image_prompt="A modern smartphone, white background",
            )
        ],
        scenes=[
            SceneSpec(
                scene_number=1,
                duration_sec=15.0,
                situation="朝起きる",
                camera_work=CameraWork(type="close-up", description="目覚まし時計のクローズアップ"),
                caption_text="おはよう〜☀️",
                image_prompt="A cozy bedroom, morning light",
            ),
            SceneSpec(
                scene_number=2,
                duration_sec=15.0,
                situation="通勤する",
                camera_work=CameraWork(type="wide", description="駅のホーム"),
                caption_text="通勤ラッシュ🚃",
                image_prompt="A train station platform",
            ),
            SceneSpec(
                scene_number=3,
                duration_sec=15.0,
                situation="オフィスで仕事",
                camera_work=CameraWork(type="POV", description="デスク上のPOV"),
                caption_text="今日も頑張る💻",
                image_prompt="A modern office desk",
            ),
        ],
        bgm_direction="明るいlo-fi pop、BPM 110〜130",
    )


def _mock_openai_response(scenario: Scenario) -> MagicMock:
    """OpenAI APIレスポンスのモックを作成する."""
    mock_message = MagicMock()
    mock_message.parsed = scenario
    mock_message.refusal = None

    mock_choice = MagicMock()
    mock_choice.message = mock_message

    mock_response = MagicMock()
    mock_response.choices = [mock_choice]
    return mock_response


class TestOpenAIScenarioEngine:
    """OpenAIScenarioEngine のテスト."""

    def test_APIキー未設定_ValueError(self) -> None:
        engine = OpenAIScenarioEngine(api_key="")
        with pytest.raises(ValueError, match="API キーが設定されていません"):
            import asyncio

            asyncio.run(
                engine.generate(
                    trend_report=_make_trend_report(),
                    output_dir=Path("/tmp/test"),
                )
            )

    @pytest.mark.asyncio
    async def test_正常系_シナリオ生成(self) -> None:
        engine = OpenAIScenarioEngine(api_key="test-key")
        scenario = _make_scenario()

        with patch.object(engine, "_call_openai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = scenario

            result = await engine.generate(
                trend_report=_make_trend_report(),
                output_dir=Path("/tmp/test"),
            )

        assert result.title == "OLの一日 〜テスト編〜"
        assert len(result.scenes) == 3
        assert len(result.characters) == 1
        mock_call.assert_called_once()

    @pytest.mark.asyncio
    async def test_バリデーションエラー時_リトライ成功(self) -> None:
        engine = OpenAIScenarioEngine(api_key="test-key", max_retries=2)

        # 1回目: 尺超過のシナリオ、2回目: 正常シナリオ
        bad_scenario = _make_scenario(total_duration_sec=100.0)
        good_scenario = _make_scenario(total_duration_sec=45.0)

        with patch.object(engine, "_call_openai", new_callable=AsyncMock) as mock_call:
            mock_call.side_effect = [bad_scenario, good_scenario]

            result = await engine.generate(
                trend_report=_make_trend_report(),
                output_dir=Path("/tmp/test"),
            )

        assert result.total_duration_sec == 45.0
        assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_最大リトライ超過_RuntimeError(self) -> None:
        engine = OpenAIScenarioEngine(api_key="test-key", max_retries=1)

        bad_scenario = _make_scenario(total_duration_sec=100.0)

        with patch.object(engine, "_call_openai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = bad_scenario

            with pytest.raises(RuntimeError, match="2 回失敗"):
                await engine.generate(
                    trend_report=_make_trend_report(),
                    output_dir=Path("/tmp/test"),
                )

        # 初回 + リトライ1回 = 2回
        assert mock_call.call_count == 2

    @pytest.mark.asyncio
    async def test_refusal_RuntimeError(self) -> None:
        engine = OpenAIScenarioEngine(api_key="test-key", max_retries=0)

        mock_message = MagicMock()
        mock_message.parsed = None
        mock_message.refusal = "リクエストを処理できません"
        mock_choice = MagicMock()
        mock_choice.message = mock_message
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        with patch("daily_routine.scenario.engine.AsyncOpenAI") as mock_cls:
            mock_client = AsyncMock()
            mock_cls.return_value = mock_client
            mock_client.beta.chat.completions.parse = AsyncMock(return_value=mock_response)

            with pytest.raises(RuntimeError, match="拒否"):
                await engine.generate(
                    trend_report=_make_trend_report(),
                    output_dir=Path("/tmp/test"),
                )

    @pytest.mark.asyncio
    async def test_user_direction付きで生成(self) -> None:
        engine = OpenAIScenarioEngine(api_key="test-key")
        scenario = _make_scenario()

        with patch.object(engine, "_call_openai", new_callable=AsyncMock) as mock_call:
            mock_call.return_value = scenario

            result = await engine.generate(
                trend_report=_make_trend_report(),
                output_dir=Path("/tmp/test"),
                user_direction="コメディ要素を入れてほしい",
            )

        assert result is not None
        # _call_openai に渡された messages にユーザーの創作意図が含まれていることを確認
        call_args = mock_call.call_args
        messages = call_args[1]["messages"] if "messages" in call_args[1] else call_args[0][1]
        user_msg = next(m for m in messages if m["role"] == "user")
        assert "コメディ要素" in user_msg["content"]


class TestOpenAIScenarioEnginePersistence:
    """OpenAIScenarioEngine の永続化テスト."""

    def test_save_output_ファイル作成(self, tmp_path: Path) -> None:
        engine = OpenAIScenarioEngine(api_key="test-key")
        scenario = _make_scenario()

        engine.save_output(tmp_path, scenario)

        scenario_file = tmp_path / "scenario" / "scenario.json"
        assert scenario_file.exists()

    def test_load_output_正常読み込み(self, tmp_path: Path) -> None:
        engine = OpenAIScenarioEngine(api_key="test-key")
        scenario = _make_scenario()

        engine.save_output(tmp_path, scenario)
        loaded = engine.load_output(tmp_path)

        assert loaded.title == scenario.title
        assert len(loaded.scenes) == len(scenario.scenes)

    def test_load_output_ファイル未存在_FileNotFoundError(self, tmp_path: Path) -> None:
        engine = OpenAIScenarioEngine(api_key="test-key")

        with pytest.raises(FileNotFoundError):
            engine.load_output(tmp_path)

    def test_execute_はgenerateを呼ぶ(self) -> None:
        """execute が generate のラッパーであることを確認する."""
        engine = OpenAIScenarioEngine(api_key="test-key")
        scenario = _make_scenario()

        with patch.object(engine, "generate", new_callable=AsyncMock) as mock_gen:
            mock_gen.return_value = scenario

            import asyncio

            result = asyncio.run(engine.execute(_make_trend_report(), Path("/tmp/test")))

        assert result == scenario
        mock_gen.assert_called_once()
