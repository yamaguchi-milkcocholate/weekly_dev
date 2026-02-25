"""ScenarioPromptBuilder のテスト."""

from daily_routine.scenario.prompt import ScenarioPromptBuilder
from daily_routine.schemas.intelligence import (
    AssetRequirement,
    AudioTrend,
    CaptionTrend,
    SceneStructure,
    TrendReport,
    VisualTrend,
)


def _make_trend_report() -> TrendReport:
    """テスト用のTrendReportを作成する."""
    return TrendReport(
        keyword="OLの一日",
        analyzed_video_count=15,
        scene_structure=SceneStructure(
            total_scenes=8,
            avg_scene_duration_sec=5.0,
            hook_techniques=["目覚ましアラームの音から始まる", "時計のクローズアップ"],
            transition_patterns=["カット切り替え", "ホワイトフェード"],
        ),
        caption_trend=CaptionTrend(
            font_styles=["太ゴシック", "丸ゴシック"],
            color_schemes=["白文字+黒縁", "ピンク+白縁"],
            animation_types=["ポップイン", "スライドイン"],
            positions=["center-bottom", "center"],
            emphasis_techniques=["キーワード拡大", "絵文字併用"],
        ),
        visual_trend=VisualTrend(
            situations=["朝の目覚め", "メイク", "通勤電車"],
            props=["スマートフォン", "コーヒーカップ"],
            camera_works=["POV", "close-up", "wide"],
            color_tones=["warm filter", "soft pastel"],
        ),
        audio_trend=AudioTrend(
            bpm_range=[110, 130],
            genres=["lo-fi pop", "acoustic"],
            volume_patterns=["冒頭やや大きめ→安定"],
            se_usage_points=["目覚まし音", "キーボード打鍵"],
        ),
        asset_requirements=AssetRequirement(
            characters=["OL（主人公）"],
            props=["スマートフォン", "コーヒーカップ"],
            backgrounds=["ベッドルーム", "オフィス"],
        ),
    )


class TestScenarioPromptBuilder:
    """ScenarioPromptBuilder のテスト."""

    def setup_method(self) -> None:
        self.builder = ScenarioPromptBuilder()
        self.trend_report = _make_trend_report()

    def test_システムプロンプト_シーン構成情報を含む(self) -> None:
        prompt = self.builder.build_system_prompt(self.trend_report)
        assert "目覚ましアラームの音から始まる" in prompt
        assert "カット切り替え" in prompt
        assert "5.0秒" in prompt

    def test_システムプロンプト_テロップトレンドを含む(self) -> None:
        prompt = self.builder.build_system_prompt(self.trend_report)
        assert "太ゴシック" in prompt
        assert "キーワード拡大" in prompt

    def test_システムプロンプト_映像トレンドを含む(self) -> None:
        prompt = self.builder.build_system_prompt(self.trend_report)
        assert "朝の目覚め" in prompt
        assert "POV" in prompt
        assert "warm filter" in prompt

    def test_システムプロンプト_音響トレンドを含む(self) -> None:
        prompt = self.builder.build_system_prompt(self.trend_report)
        assert "110〜130" in prompt
        assert "lo-fi pop" in prompt

    def test_システムプロンプト_素材要件を含む(self) -> None:
        prompt = self.builder.build_system_prompt(self.trend_report)
        assert "OL（主人公）" in prompt
        assert "ベッドルーム" in prompt

    def test_システムプロンプト_生成ルールを含む(self) -> None:
        prompt = self.builder.build_system_prompt(self.trend_report)
        assert "reference_prompt" in prompt
        assert "image_prompt" in prompt

    def test_ユーザープロンプト_キーワードとduration_rangeを含む(self) -> None:
        prompt = self.builder.build_user_prompt("OLの一日", (30, 60))
        assert "OLの一日" in prompt
        assert "30" in prompt
        assert "60" in prompt

    def test_ユーザープロンプト_user_directionあり(self) -> None:
        prompt = self.builder.build_user_prompt(
            "OLの一日",
            (30, 60),
            user_direction="コメディ要素を入れて明るい雰囲気にしてほしい",
        )
        assert "コメディ要素" in prompt
        assert "創作意図" in prompt

    def test_ユーザープロンプト_user_directionなし(self) -> None:
        prompt = self.builder.build_user_prompt("OLの一日", (30, 60))
        assert "創作意図" not in prompt

    def test_リトライプロンプト_エラー内容を含む(self) -> None:
        errors = [
            "total_duration_sec が 75.0 秒です",
            "scene_number が連番になっていません",
        ]
        prompt = self.builder.build_retry_prompt(errors)
        assert "75.0" in prompt
        assert "連番" in prompt
        assert "修正してください" in prompt
