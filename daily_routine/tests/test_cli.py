"""cli/app.py のテスト."""

from pathlib import Path

import pytest
import typer
from typer.testing import CliRunner

from daily_routine.cli.app import _load_seeds, app

runner = CliRunner()


class TestCliHelp:
    """CLI --help のテスト."""

    def test_main_help(self) -> None:
        result = runner.invoke(app, ["--help"])
        assert result.exit_code == 0
        assert "AI動画生成パイプライン" in result.output

    def test_run_help(self) -> None:
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "検索キーワード" in result.output

    def test_status_help(self) -> None:
        result = runner.invoke(app, ["status", "--help"])
        assert result.exit_code == 0
        assert "プロジェクトID" in result.output

    def test_init_help(self) -> None:
        result = runner.invoke(app, ["init", "--help"])
        assert result.exit_code == 0
        assert "検索キーワード" in result.output

    def test_resume_help(self) -> None:
        result = runner.invoke(app, ["resume", "--help"])
        assert result.exit_code == 0
        assert "プロジェクトID" in result.output

    def test_retry_help(self) -> None:
        result = runner.invoke(app, ["retry", "--help"])
        assert result.exit_code == 0
        assert "プロジェクトID" in result.output

    def test_run_help_seedsオプション表示(self) -> None:
        result = runner.invoke(app, ["run", "--help"])
        assert result.exit_code == 0
        assert "--seeds" in result.output


class TestLoadSeeds:
    """_load_seeds のテスト."""

    def test_正常なYAML読み込み(self, tmp_path: Path) -> None:
        seeds_yaml = tmp_path / "seeds.yaml"
        seeds_yaml.write_text(
            """\
seed_videos:
  - url: "https://www.youtube.com/watch?v=abc123"
    note: "テンポが良い"
    scene_captures:
      - image_path: "./captures/scene1.png"
        description: "冒頭のフック"
        timestamp_sec: 2.0
      - image_path: "./captures/scene2.png"
        description: "オフィスシーン"
  - url: "https://www.youtube.com/watch?v=def456"
    note: "BGMが参考になる"
""",
            encoding="utf-8",
        )

        result = _load_seeds(seeds_yaml)

        assert len(result) == 2
        assert result[0].url == "https://www.youtube.com/watch?v=abc123"
        assert result[0].note == "テンポが良い"
        assert len(result[0].scene_captures) == 2
        assert result[0].scene_captures[0].image_path == Path("./captures/scene1.png")
        assert result[0].scene_captures[0].description == "冒頭のフック"
        assert result[0].scene_captures[0].timestamp_sec == 2.0
        assert result[0].scene_captures[1].timestamp_sec is None
        assert result[1].url == "https://www.youtube.com/watch?v=def456"
        assert result[1].scene_captures == []

    def test_ファイル未存在_Exit(self, tmp_path: Path) -> None:
        with pytest.raises((SystemExit, typer.Exit)):
            _load_seeds(tmp_path / "nonexistent.yaml")

    def test_空のseed_videos_空リスト(self, tmp_path: Path) -> None:
        seeds_yaml = tmp_path / "seeds.yaml"
        seeds_yaml.write_text("seed_videos: []\n", encoding="utf-8")

        result = _load_seeds(seeds_yaml)
        assert result == []

    def test_seed_videosキー無し_空リスト(self, tmp_path: Path) -> None:
        seeds_yaml = tmp_path / "seeds.yaml"
        seeds_yaml.write_text("other_key: value\n", encoding="utf-8")

        result = _load_seeds(seeds_yaml)
        assert result == []
