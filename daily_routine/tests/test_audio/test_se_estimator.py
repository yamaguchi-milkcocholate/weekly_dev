"""se_estimator.py のユニットテスト."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from daily_routine.audio.se_estimator import SEEstimation, SEEstimator
from daily_routine.schemas.scenario import CameraWork, SceneSpec


def _make_scenes() -> list[SceneSpec]:
    """テスト用シーンリスト."""
    return [
        SceneSpec(
            scene_number=1,
            duration_sec=8.0,
            situation="朝、アラームが鳴りベッドから起き上がる",
            camera_work=CameraWork(type="close-up", description="アラームを止める手元"),
            caption_text="朝6時…今日も始まる",
            image_prompt="morning bedroom alarm clock",
            video_prompt="waking up in morning",
        ),
        SceneSpec(
            scene_number=2,
            duration_sec=7.0,
            situation="身支度を整え、玄関のドアを開けて出発する",
            camera_work=CameraWork(type="wide", description="玄関"),
            caption_text="いってきます！",
            image_prompt="entrance door morning",
            video_prompt="leaving home",
        ),
    ]


def _make_se_usage_points() -> list[str]:
    return [
        "朝の目覚めシーンでアラーム音",
        "ドアの開閉で場面転換を強調",
    ]


def _make_mock_response_json() -> str:
    """Gemini のモックレスポンス JSON."""
    return """{
  "estimations": [
    {
      "se_name": "alarm clock",
      "scene_number": 1,
      "trigger_description": "目覚まし時計のアラームが鳴る"
    },
    {
      "se_name": "door open close",
      "scene_number": 2,
      "trigger_description": "玄関のドアを開けて出発する"
    }
  ]
}"""


class TestSEEstimatorEstimate:
    """estimate のテスト."""

    @pytest.mark.asyncio
    async def test_estimate_正常_SE一覧を返す(self) -> None:
        estimator = SEEstimator(api_key="test-key")

        mock_response = MagicMock()
        mock_response.text = _make_mock_response_json()

        mock_models = MagicMock()
        mock_models.generate_content = AsyncMock(return_value=mock_response)

        mock_aio = MagicMock()
        mock_aio.models = mock_models

        mock_client = MagicMock()
        mock_client.aio = mock_aio

        with patch("daily_routine.audio.se_estimator.genai.Client", return_value=mock_client):
            result = await estimator.estimate(
                scenes=_make_scenes(),
                se_usage_points=_make_se_usage_points(),
            )

        assert len(result) == 2
        assert isinstance(result[0], SEEstimation)
        assert result[0].se_name == "alarm clock"
        assert result[0].scene_number == 1
        assert result[1].se_name == "door open close"
        assert result[1].scene_number == 2

    @pytest.mark.asyncio
    async def test_estimate_リトライ後成功(self) -> None:
        estimator = SEEstimator(api_key="test-key")

        mock_response = MagicMock()
        mock_response.text = _make_mock_response_json()

        call_count = 0

        async def generate_side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RuntimeError("Rate limited")
            return mock_response

        mock_models = MagicMock()
        mock_models.generate_content = AsyncMock(side_effect=generate_side_effect)

        mock_aio = MagicMock()
        mock_aio.models = mock_models

        mock_client = MagicMock()
        mock_client.aio = mock_aio

        with patch("daily_routine.audio.se_estimator.genai.Client", return_value=mock_client):
            result = await estimator.estimate(
                scenes=_make_scenes(),
                se_usage_points=_make_se_usage_points(),
            )

        assert len(result) == 2
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_estimate_リトライ上限超過_例外(self) -> None:
        estimator = SEEstimator(api_key="test-key")

        mock_models = MagicMock()
        mock_models.generate_content = AsyncMock(side_effect=RuntimeError("Rate limited"))

        mock_aio = MagicMock()
        mock_aio.models = mock_models

        mock_client = MagicMock()
        mock_client.aio = mock_aio

        with (
            patch("daily_routine.audio.se_estimator.genai.Client", return_value=mock_client),
            pytest.raises(RuntimeError, match="Rate limited"),
        ):
            await estimator.estimate(
                scenes=_make_scenes(),
                se_usage_points=_make_se_usage_points(),
            )


class TestSEEstimatorBuildPrompt:
    """_build_prompt のテスト."""

    def test_build_prompt_シーン情報とSE使用パターンを含む(self) -> None:
        estimator = SEEstimator(api_key="test-key")

        prompt = estimator._build_prompt(
            scenes=_make_scenes(),
            se_usage_points=_make_se_usage_points(),
        )

        assert "トレンドでの SE 使用パターン" in prompt
        assert "朝の目覚めシーンでアラーム音" in prompt
        assert "シーン1:" in prompt
        assert "朝、アラームが鳴りベッドから起き上がる" in prompt
        assert "朝6時…今日も始まる" in prompt
        assert "シーン2:" in prompt
        assert "最大2つの SE" in prompt
