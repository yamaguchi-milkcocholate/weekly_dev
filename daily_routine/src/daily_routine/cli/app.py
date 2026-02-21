"""CLI エントリーポイント."""

import typer

from daily_routine.config.manager import init_project, load_global_config
from daily_routine.logging import setup_logging

app = typer.Typer(
    name="daily-routine",
    help="「〇〇の一日」AI動画生成パイプライン",
)


@app.callback()
def _setup(
    log_level: str = typer.Option("INFO", help="ログレベル（DEBUG, INFO, WARNING, ERROR）"),
) -> None:
    """アプリケーション共通の初期化."""
    config = load_global_config()
    setup_logging(level=log_level, log_file=config.logging.file)


@app.command()
def run(
    keyword: str = typer.Argument(help="検索キーワード"),
    project_id: str | None = typer.Option(None, help="プロジェクトID（省略時は自動生成）"),
    step: str | None = typer.Option(None, help="特定ステップのみ実行"),
) -> None:
    """パイプラインを実行する."""
    typer.echo(f"パイプライン実行: keyword={keyword}, project_id={project_id}, step={step}")
    typer.echo("（未実装: Phase 1で各レイヤーを実装後に有効化）")


@app.command()
def status(
    project_id: str = typer.Argument(help="プロジェクトID"),
) -> None:
    """プロジェクトの実行状態を表示する."""
    typer.echo(f"ステータス確認: project_id={project_id}")
    typer.echo("（未実装: パイプライン実行後に有効化）")


@app.command()
def init(
    keyword: str = typer.Argument(help="検索キーワード"),
    project_id: str | None = typer.Option(None, help="プロジェクトID"),
) -> None:
    """新規プロジェクトを初期化する."""
    global_config = load_global_config()
    config = init_project(global_config, keyword, project_id)
    typer.echo(f"プロジェクトを初期化しました: {config.project_id}")
    typer.echo(f"データディレクトリ: {global_config.data_root / 'projects' / config.project_id}")


if __name__ == "__main__":
    app()
