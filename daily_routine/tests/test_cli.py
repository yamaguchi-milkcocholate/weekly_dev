"""cli/app.py のテスト."""

from typer.testing import CliRunner

from daily_routine.cli.app import app

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
