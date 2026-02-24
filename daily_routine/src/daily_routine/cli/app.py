"""CLI エントリーポイント."""

import asyncio
import logging
from pathlib import Path

import typer
import yaml

from daily_routine.config.manager import get_project_dir, init_project, load_global_config
from daily_routine.intelligence.base import SceneCapture, SeedVideo
from daily_routine.logging import setup_logging
from daily_routine.pipeline.exceptions import InvalidStateError, PipelineError
from daily_routine.pipeline.runner import resume_pipeline, retry_pipeline, run_pipeline
from daily_routine.pipeline.state import load_state
from daily_routine.schemas.project import PipelineState

logger = logging.getLogger(__name__)

app = typer.Typer(
    name="daily-routine",
    help="「〇〇の一日」AI動画生成パイプライン",
)


def _register_engines() -> None:
    """パイプラインエンジンを登録する."""
    from daily_routine.asset.generator import GeminiAssetGenerator
    from daily_routine.audio.engine import AudioEngine
    from daily_routine.intelligence.engine import IntelligenceEngine
    from daily_routine.pipeline.registry import register_engine
    from daily_routine.scenario.engine import OpenAIScenarioEngine
    from daily_routine.schemas.project import PipelineStep

    register_engine(PipelineStep.INTELLIGENCE, IntelligenceEngine)
    register_engine(PipelineStep.SCENARIO, OpenAIScenarioEngine)
    register_engine(PipelineStep.ASSET, GeminiAssetGenerator)
    register_engine(PipelineStep.AUDIO, AudioEngine)


@app.callback()
def _setup(
    log_level: str = typer.Option("INFO", help="ログレベル（DEBUG, INFO, WARNING, ERROR）"),
) -> None:
    """アプリケーション共通の初期化."""
    config = load_global_config()
    setup_logging(level=log_level, log_file=config.logging.file)
    _register_engines()


@app.command()
def run(
    keyword: str = typer.Argument(help="検索キーワード"),
    project_id: str | None = typer.Option(None, help="プロジェクトID（省略時は自動生成）"),
    seeds: Path | None = typer.Option(None, help="シード動画情報のYAMLファイルパス"),
) -> None:
    """パイプラインを新規実行する.

    プロジェクトを初期化し、最初のステップ（Intelligence）を実行する。
    ステップ完了後にチェックポイントで停止する。
    """
    global_config = load_global_config()
    project_config = init_project(global_config, keyword, project_id)
    project_dir = get_project_dir(global_config, project_config.project_id)

    seed_videos = _load_seeds(seeds) if seeds else None

    try:
        api_keys = global_config.api_keys.model_dump()
        state = asyncio.run(
            run_pipeline(
                project_dir,
                project_config.project_id,
                keyword,
                api_keys=api_keys,
                seed_videos=seed_videos,
            )
        )
        _print_state_summary(state)
    except PipelineError as e:
        typer.echo(f"エラー: {e}", err=True)
        raise typer.Exit(code=1) from e


@app.command()
def resume(
    project_id: str = typer.Argument(help="プロジェクトID"),
) -> None:
    """チェックポイントから再開する.

    AWAITING_REVIEWのステップを承認し、次のステップを実行する。
    """
    global_config = load_global_config()
    project_dir = get_project_dir(global_config, project_id)

    try:
        api_keys = global_config.api_keys.model_dump()
        state = asyncio.run(resume_pipeline(project_dir, api_keys=api_keys))
        _print_state_summary(state)
    except InvalidStateError as e:
        typer.echo(f"エラー: {e}", err=True)
        raise typer.Exit(code=1) from e
    except PipelineError as e:
        typer.echo(f"エラー: {e}", err=True)
        raise typer.Exit(code=1) from e


@app.command()
def retry(
    project_id: str = typer.Argument(help="プロジェクトID"),
) -> None:
    """エラーステップを再試行する.

    ERROR状態のステップを再実行する。
    """
    global_config = load_global_config()
    project_dir = get_project_dir(global_config, project_id)

    try:
        api_keys = global_config.api_keys.model_dump()
        state = asyncio.run(retry_pipeline(project_dir, api_keys=api_keys))
        _print_state_summary(state)
    except InvalidStateError as e:
        typer.echo(f"エラー: {e}", err=True)
        raise typer.Exit(code=1) from e
    except PipelineError as e:
        typer.echo(f"エラー: {e}", err=True)
        raise typer.Exit(code=1) from e


@app.command()
def status(
    project_id: str = typer.Argument(help="プロジェクトID"),
) -> None:
    """プロジェクトの実行状態を表示する."""
    global_config = load_global_config()
    project_dir = get_project_dir(global_config, project_id)

    try:
        state = load_state(project_dir)
        _print_state_summary(state)
    except FileNotFoundError:
        typer.echo(f"エラー: プロジェクト '{project_id}' の状態ファイルが見つかりません", err=True)
        raise typer.Exit(code=1)


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


def _load_seeds(seeds_path: Path) -> list[SeedVideo]:
    """シード動画情報のYAMLファイルを読み込む.

    Args:
        seeds_path: YAMLファイルのパス

    Returns:
        SeedVideoのリスト

    Raises:
        typer.Exit: ファイルが存在しない、またはフォーマットが不正な場合
    """
    if not seeds_path.exists():
        typer.echo(f"エラー: シードファイルが見つかりません: {seeds_path}", err=True)
        raise typer.Exit(code=1)

    with open(seeds_path) as f:
        raw = yaml.safe_load(f) or {}

    raw_videos = raw.get("seed_videos", [])
    if not raw_videos:
        typer.echo("警告: seed_videos が空です。拡張検索のみで実行します", err=True)
        return []

    seed_videos: list[SeedVideo] = []
    for entry in raw_videos:
        captures = [
            SceneCapture(
                image_path=Path(cap["image_path"]),
                description=cap.get("description", ""),
                timestamp_sec=cap.get("timestamp_sec"),
            )
            for cap in entry.get("scene_captures", [])
        ]
        seed_videos.append(
            SeedVideo(
                url=entry["url"],
                note=entry.get("note", ""),
                scene_captures=captures,
            )
        )

    logger.info("シード動画を %d 件読み込みました: %s", len(seed_videos), seeds_path)
    return seed_videos


def _print_state_summary(state: PipelineState) -> None:
    """パイプライン状態のサマリーを表示する."""
    typer.echo(f"プロジェクト: {state.project_id}")
    typer.echo(f"完了: {'Yes' if state.completed else 'No'}")
    typer.echo(f"現在のステップ: {state.current_step.value if state.current_step else '-'}")
    typer.echo("---")
    for step, step_state in state.steps.items():
        status_icon = {
            "pending": "[ ]",
            "running": "[~]",
            "awaiting_review": "[?]",
            "approved": "[v]",
            "error": "[x]",
        }.get(step_state.status.value, "[.]")
        line = f"  {status_icon} {step.value}: {step_state.status.value}"
        if step_state.error:
            line += f" ({step_state.error})"
        if step_state.retry_count > 0:
            line += f" [retry: {step_state.retry_count}]"
        typer.echo(line)


if __name__ == "__main__":
    app()
