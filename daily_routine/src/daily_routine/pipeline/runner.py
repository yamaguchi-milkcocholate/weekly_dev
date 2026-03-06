"""パイプライン実行制御."""

import logging
from datetime import datetime
from pathlib import Path

from daily_routine.intelligence.base import SeedVideo
from daily_routine.pipeline.base import StepEngine
from daily_routine.pipeline.exceptions import InvalidStateError, StepExecutionError
from daily_routine.pipeline.registry import create_engine
from daily_routine.pipeline.state import initialize_state, load_state, save_state
from daily_routine.pipeline.summarizer import StepSummarizer, log_item_summary, log_summary
from daily_routine.schemas.keyframe_mapping import KeyframeMapping
from daily_routine.schemas.pipeline_io import IntelligenceInput
from daily_routine.schemas.project import (
    CheckpointStatus,
    ItemState,
    PipelineState,
    PipelineStep,
)

logger = logging.getLogger(__name__)

FULL_STEP_ORDER: list[PipelineStep] = [
    PipelineStep.INTELLIGENCE,
    PipelineStep.SCENARIO,
    PipelineStep.STORYBOARD,
    PipelineStep.ASSET,
    PipelineStep.KEYFRAME,
    PipelineStep.VISUAL,
    PipelineStep.AUDIO,
    PipelineStep.POST_PRODUCTION,
]

PLANNING_STEP_ORDER: list[PipelineStep] = [
    PipelineStep.INTELLIGENCE,
    PipelineStep.SCENARIO,
    PipelineStep.STORYBOARD,
]

PRODUCTION_STEP_ORDER: list[PipelineStep] = [
    PipelineStep.ASSET,
    PipelineStep.KEYFRAME,
    PipelineStep.VISUAL,
    PipelineStep.AUDIO,
]

STEP_ORDER = FULL_STEP_ORDER


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
    アイテム対応ステップの場合は現在のアイテムを承認し、次のアイテムを実行する。

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

    engine = create_engine(current_step, **_engine_kwargs(current_step, api_keys))

    # アイテムモード: アイテムが存在し、まだ完了していないアイテムがある場合
    if engine.supports_items and step_state.items:
        return await _resume_item_step(state, current_step, engine, project_dir, api_keys)

    # 既存動作: ステップを承認し、次のステップを実行
    step_state.status = CheckpointStatus.APPROVED
    step_state.completed_at = datetime.now()

    next_step = _get_next_step(current_step, state)
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
    next_engine = create_engine(next_step, **_engine_kwargs(next_step, api_keys))
    input_data = _build_input(next_step, project_dir)
    state = await _execute_step(state, next_step, next_engine, input_data, project_dir)
    return state


async def retry_pipeline(
    project_dir: Path,
    api_keys: dict[str, str] | None = None,
    item_id: str | None = None,
) -> PipelineState:
    """エラーステップまたは個別アイテムを再試行する.

    Args:
        project_dir: プロジェクトデータディレクトリ
        api_keys: APIキーの辞書
        item_id: リトライするアイテムID（省略時はステップ全体をリトライ）

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

    # アイテム単位リトライ
    if item_id is not None:
        if not step_state.items:
            raise InvalidStateError(f"ステップ '{current_step.value}' はアイテム単位実行ではありません")

        target_item = next((i for i in step_state.items if i.item_id == item_id), None)
        if target_item is None:
            raise InvalidStateError(f"アイテム '{item_id}' が見つかりません")

        if target_item.status not in (
            CheckpointStatus.AWAITING_REVIEW,
            CheckpointStatus.ERROR,
            CheckpointStatus.APPROVED,
        ):
            raise InvalidStateError(
                f"アイテム '{item_id}' は '{target_item.status.value}' 状態です。"
                " retry --item は AWAITING_REVIEW, APPROVED, ERROR 状態でのみ可能です"
            )

        engine = create_engine(current_step, **_engine_kwargs(current_step, api_keys))
        input_data = _build_input(current_step, project_dir)

        target_item.status = CheckpointStatus.RUNNING
        target_item.started_at = datetime.now()
        target_item.error = None
        step_state.current_item_id = item_id
        save_state(project_dir, state)

        summarizer = StepSummarizer()
        item_pre = summarizer.build_item_pre_summary(current_step, item_id, input_data, project_dir)
        if item_pre:
            log_item_summary(item_pre)

        try:
            await engine.execute_item(item_id, input_data, project_dir)
            target_item.status = CheckpointStatus.AWAITING_REVIEW
            target_item.completed_at = datetime.now()
            logger.info("アイテム '%s' のリトライが完了しました", item_id)
        except Exception as e:
            target_item.status = CheckpointStatus.ERROR
            target_item.error = str(e)
            logger.error("アイテム '%s' のリトライでエラーが発生しました: %s", item_id, e)

        save_state(project_dir, state)
        return state

    # ステップ全体のリトライ（既存動作）
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

    アイテム対応エンジンの場合はアイテムリストを初期化し、最初のアイテムを実行する。

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

    summarizer = StepSummarizer()
    step_pre = summarizer.build_step_pre_summary(step, input_data, project_dir)
    if step_pre:
        log_summary(step_pre)

    if engine.supports_items:
        # アイテム対応: リスト初期化 + 最初のアイテム実行
        return await _execute_item_step_init(state, step, engine, input_data, project_dir, summarizer=summarizer)

    try:
        output = await engine.execute(input_data, project_dir)
        engine.save_output(project_dir, output)

        step_post = summarizer.build_step_post_summary(step, input_data, output, project_dir)
        if step_post:
            log_summary(step_post)

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


async def _execute_item_step_init(
    state: PipelineState,
    step: PipelineStep,
    engine: StepEngine,
    input_data: object,
    project_dir: Path,
    *,
    summarizer: StepSummarizer | None = None,
) -> PipelineState:
    """アイテム対応ステップのアイテムリストを初期化し、最初のアイテムを実行する."""
    step_state = state.steps[step]

    try:
        item_ids = engine.list_items(input_data, project_dir)
        step_state.items = [ItemState(item_id=iid) for iid in item_ids]

        if not item_ids:
            # アイテムがない場合はステップ完了
            step_state.status = CheckpointStatus.AWAITING_REVIEW
            step_state.completed_at = datetime.now()
            save_state(project_dir, state)
            return state

        # 最初のアイテムを実行
        first_item = step_state.items[0]
        first_item.status = CheckpointStatus.RUNNING
        first_item.started_at = datetime.now()
        step_state.current_item_id = first_item.item_id
        save_state(project_dir, state)

        if summarizer:
            item_pre = summarizer.build_item_pre_summary(step, first_item.item_id, input_data, project_dir)
            if item_pre:
                log_item_summary(item_pre)

        await engine.execute_item(first_item.item_id, input_data, project_dir)
        first_item.status = CheckpointStatus.AWAITING_REVIEW
        first_item.completed_at = datetime.now()

        step_state.status = CheckpointStatus.AWAITING_REVIEW
        logger.info(
            "ステップ '%s' アイテム '%s' が完了しました（確認待ち）",
            step.value,
            first_item.item_id,
        )
    except StepExecutionError:
        raise
    except Exception as e:
        if step_state.items and step_state.current_item_id:
            current_item = next(
                (i for i in step_state.items if i.item_id == step_state.current_item_id),
                None,
            )
            if current_item:
                current_item.status = CheckpointStatus.ERROR
                current_item.error = str(e)
        step_state.status = CheckpointStatus.ERROR
        step_state.error = str(e)
        logger.error("ステップ '%s' でエラーが発生しました: %s", step.value, e)

    save_state(project_dir, state)
    return state


async def _resume_item_step(
    state: PipelineState,
    current_step: PipelineStep,
    engine: StepEngine,
    project_dir: Path,
    api_keys: dict[str, str] | None = None,
) -> PipelineState:
    """アイテム単位ステップの resume を処理する.

    1. 現在のアイテムを APPROVED に遷移
    2. 次の PENDING アイテムを検索
    3. あれば execute_item() を実行
    4. なければステップ完了 → 次のステップへ遷移
    """
    step_state = state.steps[current_step]
    input_data = _build_input(current_step, project_dir)

    # 1. 現在のアイテムを承認
    current_item = next(
        (i for i in step_state.items if i.item_id == step_state.current_item_id),
        None,
    )
    if current_item and current_item.status == CheckpointStatus.AWAITING_REVIEW:
        current_item.status = CheckpointStatus.APPROVED
        current_item.completed_at = datetime.now()

    # 2. 次の PENDING アイテムを検索
    next_item = next(
        (i for i in step_state.items if i.status == CheckpointStatus.PENDING),
        None,
    )

    if next_item is not None:
        # 3. 次のアイテムを実行
        next_item.status = CheckpointStatus.RUNNING
        next_item.started_at = datetime.now()
        step_state.current_item_id = next_item.item_id
        save_state(project_dir, state)

        summarizer = StepSummarizer()
        item_pre = summarizer.build_item_pre_summary(current_step, next_item.item_id, input_data, project_dir)
        if item_pre:
            log_item_summary(item_pre)

        try:
            await engine.execute_item(next_item.item_id, input_data, project_dir)
            next_item.status = CheckpointStatus.AWAITING_REVIEW
            next_item.completed_at = datetime.now()
            logger.info(
                "ステップ '%s' アイテム '%s' が完了しました（確認待ち）",
                current_step.value,
                next_item.item_id,
            )
        except Exception as e:
            next_item.status = CheckpointStatus.ERROR
            next_item.error = str(e)
            step_state.status = CheckpointStatus.ERROR
            step_state.error = str(e)
            logger.error(
                "ステップ '%s' アイテム '%s' でエラーが発生しました: %s",
                current_step.value,
                next_item.item_id,
                e,
            )

        save_state(project_dir, state)
        return state

    # 4. 全アイテム完了 → ステップを承認し次のステップへ
    step_state.status = CheckpointStatus.APPROVED
    step_state.completed_at = datetime.now()
    step_state.current_item_id = None

    next_step = _get_next_step(current_step, state)
    if next_step is None:
        state.completed = True
        save_state(project_dir, state)
        logger.info("パイプラインが完了しました: %s", state.project_id)
        return state

    # ASSET → KEYFRAME 遷移時に keyframe_mapping.yaml を自動生成
    if next_step == PipelineStep.KEYFRAME:
        _auto_generate_keyframe_mapping(project_dir)

    next_engine = create_engine(next_step, **_engine_kwargs(next_step, api_keys))
    next_input = _build_input(next_step, project_dir)
    state = await _execute_step(state, next_step, next_engine, next_input, project_dir)
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
        scenario = create_engine(PipelineStep.SCENARIO).load_output(project_dir)
        try:
            trend_report = create_engine(PipelineStep.INTELLIGENCE).load_output(project_dir)
            audio_trend = trend_report.audio_trend
        except FileNotFoundError:
            from daily_routine.schemas.intelligence import AudioTrend

            audio_trend = AudioTrend.default_from_scenario(scenario.bgm_direction)
        return AudioInput(audio_trend=audio_trend, scenario=scenario)
    elif step == PipelineStep.POST_PRODUCTION:
        scenario = create_engine(PipelineStep.SCENARIO).load_output(project_dir)
        storyboard = create_engine(PipelineStep.STORYBOARD).load_output(project_dir)
        clips = create_engine(PipelineStep.VISUAL).load_output(project_dir)
        audio = create_engine(PipelineStep.AUDIO).load_output(project_dir)
        return PostProductionInput(scenario=scenario, storyboard=storyboard, video_clips=clips, audio_asset=audio)

    msg = f"未知のステップ: {step}"
    raise ValueError(msg)


def _get_next_step(step: PipelineStep, state: PipelineState) -> PipelineStep | None:
    """指定ステップの次のステップをstateのステップ順序から取得する."""
    step_list = list(state.steps.keys())
    try:
        idx = step_list.index(step)
    except ValueError:
        return None
    if idx + 1 >= len(step_list):
        return None
    return step_list[idx + 1]


def _get_previous_step(step: PipelineStep, state: PipelineState) -> PipelineStep | None:
    """指定ステップの前のステップをstateのステップ順序から取得する."""
    step_list = list(state.steps.keys())
    try:
        idx = step_list.index(step)
    except ValueError:
        return None
    if idx == 0:
        return None
    return step_list[idx - 1]


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

    from daily_routine.schemas.keyframe_mapping import CharacterComponent, SceneKeyframeSpec

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

        scene_has_character = any(cut.has_character for cut in scene.cuts)
        components = []
        if scene_has_character and assets.characters:
            # storyboard のカットから clothing_variant を取得
            clothing_variant = "default"
            for cut in scene.cuts:
                if cut.has_character and cut.clothing_variant:
                    clothing_variant = cut.clothing_variant
                    break

            # clothing_variant にマッチする asset variant_id を検索
            char_name = assets.characters[0].character_name
            variant_id = clothing_variant
            matched = any(c.variant_id == clothing_variant for c in assets.characters if c.character_name == char_name)
            if not matched:
                # フォールバック: 最初のバリアントを使用 + 警告
                variant_id = assets.characters[0].variant_id
                logger.warning(
                    "clothing_variant '%s' に一致する asset が見つかりません (scene=%d)。"
                    "フォールバック: variant_id='%s'",
                    clothing_variant,
                    scene.scene_number,
                    variant_id,
                )

            components.append(
                CharacterComponent(
                    character=char_name,
                    variant_id=variant_id,
                )
            )

        # Step 1: 直接の scene_number マッチ
        environment = ""
        for env in assets.environments:
            if env.scene_number == scene.scene_number:
                environment = env.description
                break

        pose = ""
        if scene.cuts:
            pose = scene.cuts[0].pose_instruction

        spec = SceneKeyframeSpec(
            scene_number=scene.scene_number,
            environment=environment,
            pose=pose,
            components=components,
        )
        # exclude_defaults だと components 内の type フィールド（discriminator）も除外されるため
        # components は個別にシリアライズする
        dumped = spec.model_dump(mode="json", exclude={"components"}, exclude_defaults=True)
        dumped["components"] = [c.model_dump(mode="json") for c in components]
        scenes.append(dumped)

    mapping_data = {"scenes": scenes}
    mapping_path.parent.mkdir(parents=True, exist_ok=True)
    mapping_path.write_text(
        yaml.dump(mapping_data, allow_unicode=True, default_flow_style=False),
        encoding="utf-8",
    )
    logger.info("keyframe_mapping.yaml を自動生成しました: %s", mapping_path)


def _validate_production_prerequisites(project_dir: Path) -> None:
    """プロダクション実行の前提条件を検証する.

    scenario.json と storyboard.json の存在を確認する。

    Args:
        project_dir: プロジェクトデータディレクトリ

    Raises:
        InvalidStateError: 必要なファイルが存在しない場合
    """
    missing: list[str] = []
    try:
        create_engine(PipelineStep.SCENARIO).load_output(project_dir)
    except FileNotFoundError:
        missing.append("scenario")
    try:
        create_engine(PipelineStep.STORYBOARD).load_output(project_dir)
    except FileNotFoundError:
        missing.append("storyboard")

    if missing:
        msg = f"プロダクション実行に必要なファイルが見つかりません: {', '.join(missing)}"
        raise InvalidStateError(msg)


async def run_production_pipeline(
    project_dir: Path,
    project_id: str,
    api_keys: dict[str, str] | None = None,
) -> PipelineState:
    """プロダクションパイプラインを実行する（ASSETから開始）.

    scenario.json / storyboard.json が事前に配置されている前提で、
    ASSET → KEYFRAME → VISUAL → AUDIO のステップのみを初期化・実行する。

    Args:
        project_dir: プロジェクトデータディレクトリ
        project_id: プロジェクトID
        api_keys: APIキーの辞書

    Returns:
        実行後のPipelineState

    Raises:
        InvalidStateError: scenario / storyboard が存在しない場合
    """
    _validate_production_prerequisites(project_dir)

    state = initialize_state(project_id, step_order=PRODUCTION_STEP_ORDER)
    save_state(project_dir, state)

    first_step = PRODUCTION_STEP_ORDER[0]
    engine = create_engine(first_step, **_engine_kwargs(first_step, api_keys))
    input_data = _build_input(first_step, project_dir)

    state = await _execute_step(state, first_step, engine, input_data, project_dir)
    return state


async def run_planning_pipeline(
    project_dir: Path,
    project_id: str,
    keyword: str,
    api_keys: dict[str, str] | None = None,
    seed_videos: list[SeedVideo] | None = None,
) -> PipelineState:
    """プランニングパイプラインを実行する（INTELLIGENCEから開始）.

    INTELLIGENCE → SCENARIO → STORYBOARD のステップのみを初期化・実行する。

    Args:
        project_dir: プロジェクトデータディレクトリ
        project_id: プロジェクトID
        keyword: 検索キーワード
        api_keys: APIキーの辞書
        seed_videos: ユーザー提供のシード動画情報リスト

    Returns:
        実行後のPipelineState
    """
    state = initialize_state(project_id, step_order=PLANNING_STEP_ORDER)
    save_state(project_dir, state)

    first_step = PLANNING_STEP_ORDER[0]
    engine = create_engine(first_step, **_engine_kwargs(first_step, api_keys))
    input_data = _build_input(first_step, project_dir, keyword, seed_videos=seed_videos)

    state = await _execute_step(state, first_step, engine, input_data, project_dir)
    return state
