"""パイプライン実行制御."""

import logging
from datetime import datetime
from pathlib import Path

from daily_routine.intelligence.base import SeedVideo
from daily_routine.pipeline.base import StepEngine
from daily_routine.pipeline.exceptions import InvalidStateError, StepExecutionError
from daily_routine.pipeline.registry import create_engine
from daily_routine.pipeline.state import initialize_state, load_state, save_state
from daily_routine.schemas.keyframe_mapping import KeyframeMapping
from daily_routine.schemas.pipeline_io import IntelligenceInput
from daily_routine.schemas.project import (
    CheckpointStatus,
    PipelineState,
    PipelineStep,
)

logger = logging.getLogger(__name__)

STEP_ORDER: list[PipelineStep] = [
    PipelineStep.INTELLIGENCE,
    PipelineStep.SCENARIO,
    PipelineStep.STORYBOARD,
    PipelineStep.ASSET,
    PipelineStep.KEYFRAME,
    PipelineStep.VISUAL,
    PipelineStep.AUDIO,
    PipelineStep.POST_PRODUCTION,
]


async def run_pipeline(
    project_dir: Path,
    project_id: str,
    keyword: str,
    api_keys: dict[str, str] | None = None,
    seed_videos: list[SeedVideo] | None = None,
) -> PipelineState:
    """パイプラインを新規実行する.

    最初のステップを実行し、AWAITING_REVIEWで停止する。

    Args:
        project_dir: プロジェクトデータディレクトリ
        project_id: プロジェクトID
        keyword: 検索キーワード（Intelligenceステップの入力）
        api_keys: APIキーの辞書（環境変数名のサフィックス小文字 → 値）
        seed_videos: ユーザー提供のシード動画情報リスト

    Returns:
        実行後のPipelineState
    """
    state = initialize_state(project_id)
    save_state(project_dir, state)

    first_step = STEP_ORDER[0]
    engine = create_engine(first_step, **_engine_kwargs(first_step, api_keys))
    input_data = _build_input(first_step, project_dir, keyword, seed_videos=seed_videos)

    state = await _execute_step(state, first_step, engine, input_data, project_dir)
    return state


async def resume_pipeline(
    project_dir: Path,
    api_keys: dict[str, str] | None = None,
) -> PipelineState:
    """パイプラインを再開する.

    現在AWAITING_REVIEWのステップをAPPROVEDにし、次のステップを実行する。

    Args:
        project_dir: プロジェクトデータディレクトリ
        api_keys: APIキーの辞書

    Returns:
        実行後のPipelineState

    Raises:
        InvalidStateError: 再開可能な状態でない場合
    """
    state = load_state(project_dir)

    if state.completed:
        raise InvalidStateError("パイプラインは既に完了しています")

    current_step = state.current_step
    if current_step is None:
        raise InvalidStateError("実行中のステップがありません")

    step_state = state.steps[current_step]
    if step_state.status != CheckpointStatus.AWAITING_REVIEW:
        raise InvalidStateError(
            f"ステップ '{current_step.value}' は '{step_state.status.value}' 状態です。"
            " resume は AWAITING_REVIEW 状態でのみ可能です"
        )

    # 現在のステップをAPPROVEDに遷移
    step_state.status = CheckpointStatus.APPROVED
    step_state.completed_at = datetime.now()

    next_step = _get_next_step(current_step)
    if next_step is None:
        # 最終ステップを承認 → パイプライン完了
        state.completed = True
        state.current_step = current_step
        save_state(project_dir, state)
        logger.info("パイプラインが完了しました: %s", state.project_id)
        return state

    # ASSET → KEYFRAME 遷移時に keyframe_mapping.yaml を自動生成
    if next_step == PipelineStep.KEYFRAME:
        _auto_generate_keyframe_mapping(project_dir)

    # 次のステップを実行
    engine = create_engine(next_step, **_engine_kwargs(next_step, api_keys))
    input_data = _build_input(next_step, project_dir)
    state = await _execute_step(state, next_step, engine, input_data, project_dir)
    return state


async def retry_pipeline(
    project_dir: Path,
    api_keys: dict[str, str] | None = None,
) -> PipelineState:
    """エラーステップを再試行する.

    Args:
        project_dir: プロジェクトデータディレクトリ
        api_keys: APIキーの辞書

    Returns:
        実行後のPipelineState

    Raises:
        InvalidStateError: 再試行可能な状態でない場合
    """
    state = load_state(project_dir)

    if state.completed:
        raise InvalidStateError("パイプラインは既に完了しています")

    current_step = state.current_step
    if current_step is None:
        raise InvalidStateError("実行中のステップがありません")

    step_state = state.steps[current_step]
    if step_state.status != CheckpointStatus.ERROR:
        raise InvalidStateError(
            f"ステップ '{current_step.value}' は '{step_state.status.value}' 状態です。"
            " retry は ERROR 状態でのみ可能です"
        )

    step_state.retry_count += 1
    logger.info(
        "ステップ '%s' をリトライします（%d回目）",
        current_step.value,
        step_state.retry_count,
    )

    engine = create_engine(current_step, **_engine_kwargs(current_step, api_keys))
    input_data = _build_input(current_step, project_dir)
    state = await _execute_step(state, current_step, engine, input_data, project_dir)
    return state


async def _execute_step(
    state: PipelineState,
    step: PipelineStep,
    engine: StepEngine,
    input_data: object,
    project_dir: Path,
) -> PipelineState:
    """単一ステップを実行する.

    Args:
        state: 現在のPipelineState
        step: 実行するステップ
        engine: ステップのエンジン
        input_data: ステップへの入力
        project_dir: プロジェクトデータディレクトリ

    Returns:
        更新されたPipelineState
    """
    step_state = state.steps[step]
    step_state.status = CheckpointStatus.RUNNING
    step_state.started_at = datetime.now()
    step_state.error = None
    state.current_step = step
    save_state(project_dir, state)

    logger.info("ステップ '%s' を実行中...", step.value)

    try:
        output = await engine.execute(input_data, project_dir)
        engine.save_output(project_dir, output)

        step_state.status = CheckpointStatus.AWAITING_REVIEW
        step_state.completed_at = datetime.now()
        logger.info("ステップ '%s' が完了しました（確認待ち）", step.value)
    except StepExecutionError:
        raise
    except Exception as e:
        step_state.status = CheckpointStatus.ERROR
        step_state.error = str(e)
        logger.error("ステップ '%s' でエラーが発生しました: %s", step.value, e)

    save_state(project_dir, state)
    return state


def _build_input(
    step: PipelineStep,
    project_dir: Path,
    keyword: str | None = None,
    seed_videos: list[SeedVideo] | None = None,
) -> object:
    """ステップに必要な入力データを過去の出力から組み立てる.

    Args:
        step: 実行するステップ
        project_dir: プロジェクトデータディレクトリ
        keyword: 検索キーワード（Intelligenceステップの初回実行時のみ）
        seed_videos: ユーザー提供のシード動画情報リスト

    Returns:
        ステップへの入力データ
    """
    from daily_routine.schemas.pipeline_io import (
        AudioInput,
        KeyframeInput,
        PostProductionInput,
        StoryboardInput,
        VisualInput,
    )

    if step == PipelineStep.INTELLIGENCE:
        return IntelligenceInput(keyword=keyword or "", seed_videos=seed_videos or [])
    elif step == PipelineStep.SCENARIO:
        return create_engine(PipelineStep.INTELLIGENCE).load_output(project_dir)
    elif step == PipelineStep.STORYBOARD:
        scenario = create_engine(PipelineStep.SCENARIO).load_output(project_dir)
        return StoryboardInput(scenario=scenario)
    elif step == PipelineStep.ASSET:
        return create_engine(PipelineStep.SCENARIO).load_output(project_dir)
    elif step == PipelineStep.KEYFRAME:
        scenario = create_engine(PipelineStep.SCENARIO).load_output(project_dir)
        storyboard = create_engine(PipelineStep.STORYBOARD).load_output(project_dir)
        assets = create_engine(PipelineStep.ASSET).load_output(project_dir)
        keyframe_mapping = _load_keyframe_mapping(project_dir)
        return KeyframeInput(
            scenario=scenario,
            storyboard=storyboard,
            assets=assets,
            keyframe_mapping=keyframe_mapping,
        )
    elif step == PipelineStep.VISUAL:
        scenario = create_engine(PipelineStep.SCENARIO).load_output(project_dir)
        storyboard = create_engine(PipelineStep.STORYBOARD).load_output(project_dir)
        assets = create_engine(PipelineStep.KEYFRAME).load_output(project_dir)
        return VisualInput(scenario=scenario, storyboard=storyboard, assets=assets)
    elif step == PipelineStep.AUDIO:
        trend_report = create_engine(PipelineStep.INTELLIGENCE).load_output(project_dir)
        scenario = create_engine(PipelineStep.SCENARIO).load_output(project_dir)
        return AudioInput(audio_trend=trend_report.audio_trend, scenario=scenario)
    elif step == PipelineStep.POST_PRODUCTION:
        scenario = create_engine(PipelineStep.SCENARIO).load_output(project_dir)
        storyboard = create_engine(PipelineStep.STORYBOARD).load_output(project_dir)
        clips = create_engine(PipelineStep.VISUAL).load_output(project_dir)
        audio = create_engine(PipelineStep.AUDIO).load_output(project_dir)
        return PostProductionInput(scenario=scenario, storyboard=storyboard, video_clips=clips, audio_asset=audio)

    msg = f"未知のステップ: {step}"
    raise ValueError(msg)


def _get_next_step(step: PipelineStep) -> PipelineStep | None:
    """指定ステップの次のステップを取得する."""
    try:
        idx = STEP_ORDER.index(step)
    except ValueError:
        return None
    if idx + 1 >= len(STEP_ORDER):
        return None
    return STEP_ORDER[idx + 1]


def _get_previous_step(step: PipelineStep) -> PipelineStep | None:
    """指定ステップの前のステップを取得する."""
    try:
        idx = STEP_ORDER.index(step)
    except ValueError:
        return None
    if idx == 0:
        return None
    return STEP_ORDER[idx - 1]


def _engine_kwargs(step: PipelineStep, api_keys: dict[str, str] | None) -> dict[str, str]:
    """ステップごとのエンジンコンストラクタ引数を構築する.

    Args:
        step: パイプラインステップ
        api_keys: APIキーの辞書（GlobalConfig.api_keys.model_dump() の形式）

    Returns:
        エンジンコンストラクタに渡すキーワード引数
    """
    if api_keys is None:
        return {}

    if step == PipelineStep.INTELLIGENCE:
        return {
            "google_ai_api_key": api_keys.get("google_ai", ""),
        }

    if step == PipelineStep.SCENARIO:
        return {
            "api_key": api_keys.get("openai", ""),
        }

    if step == PipelineStep.STORYBOARD:
        return {
            "api_key": api_keys.get("openai", ""),
        }

    if step == PipelineStep.ASSET:
        return {
            "api_key": api_keys.get("google_ai", ""),
        }

    if step == PipelineStep.KEYFRAME:
        return {
            "api_key": api_keys.get("google_ai", ""),
        }

    if step == PipelineStep.VISUAL:
        return {
            "api_key": api_keys.get("runway", ""),
            "gcs_bucket": api_keys.get("gcs_bucket", ""),
            "video_model": api_keys.get("video_model", "gen4_turbo"),
        }

    if step == PipelineStep.AUDIO:
        return {
            "suno_api_key": api_keys.get("suno", ""),
            "google_ai_api_key": api_keys.get("google_ai", ""),
        }

    return {}


_KEYFRAME_MAPPING_FILENAME = "keyframe_mapping.yaml"


def _load_keyframe_mapping(project_dir: Path) -> KeyframeMapping | None:
    """keyframe_mapping.yaml を読み込む。ファイルが存在しなければ None を返す."""

    mapping_path = project_dir / "storyboard" / _KEYFRAME_MAPPING_FILENAME
    if not mapping_path.exists():
        logger.info("keyframe_mapping.yaml が見つかりません。マッピングなしで生成します")
        return None

    import yaml

    data = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
    return KeyframeMapping.model_validate(data)


def _auto_generate_keyframe_mapping(project_dir: Path) -> None:
    """Storyboard + AssetSet から keyframe_mapping.yaml を自動生成する.

    既存ファイルがあれば上書きしない（ユーザー編集を保護）。
    """
    import yaml

    from daily_routine.schemas.keyframe_mapping import SceneKeyframeSpec

    mapping_path = project_dir / "storyboard" / _KEYFRAME_MAPPING_FILENAME
    if mapping_path.exists():
        return

    try:
        storyboard = create_engine(PipelineStep.STORYBOARD).load_output(project_dir)
        assets = create_engine(PipelineStep.ASSET).load_output(project_dir)
    except (FileNotFoundError, KeyError):
        logger.warning("Storyboard または AssetSet が見つからないため、keyframe_mapping の自動生成をスキップします")
        return

    scenes: list[dict] = []
    seen_scene_numbers: set[int] = set()

    for scene in storyboard.scenes:
        if scene.scene_number in seen_scene_numbers:
            continue
        seen_scene_numbers.add(scene.scene_number)

        character = assets.characters[0].character_name if assets.characters else ""
        variant_id = assets.characters[0].variant_id if assets.characters else ""
        environment = ""
        for env in assets.environments:
            if env.scene_number == scene.scene_number:
                environment = env.description
                break
        pose = ""
        if scene.cuts:
            pose = scene.cuts[0].pose_instruction

        scenes.append(
            SceneKeyframeSpec(
                scene_number=scene.scene_number,
                character=character,
                variant_id=variant_id,
                environment=environment,
                pose=pose,
            ).model_dump(mode="json")
        )

    mapping_data = {"scenes": scenes}
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text(
        yaml.dump(mapping_data, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    logger.info("keyframe_mapping.yaml を自動生成しました: %s", mapping_path)
