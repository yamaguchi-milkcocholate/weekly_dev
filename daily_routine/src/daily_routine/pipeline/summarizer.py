"""ステップ実行サマリー機能.

各ステップ・各アイテムの実行前/後にパラメータと結果をログ出力する。
Keyframe では variant_id / 環境画像 / ポーズの解決結果と不一致警告を表示する。
"""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from daily_routine.schemas.project import PipelineStep

logger = logging.getLogger(__name__)

_SEPARATOR = "=" * 60


@dataclass
class SummaryEntry:
    """1行の情報."""

    label: str
    value: str
    warning: bool = False


@dataclass
class ProcessingStep:
    """処理ステップの説明."""

    order: int
    name: str
    input_desc: str = ""
    output_desc: str = ""


@dataclass
class ItemSummary:
    """アイテム単位のサマリー."""

    item_id: str
    entries: list[SummaryEntry] = field(default_factory=list)
    output_path: str = ""
    processing_steps: list[ProcessingStep] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


@dataclass
class StepSummary:
    """ステップ全体のサマリー."""

    step: PipelineStep
    phase: str  # "pre" or "post"
    title: str
    entries: list[SummaryEntry] = field(default_factory=list)
    item_summaries: list[ItemSummary] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


class StepSummarizer:
    """ステップ実行サマリービルダー."""

    def build_step_pre_summary(self, step: PipelineStep, input_data: object, project_dir: Path) -> StepSummary | None:
        """ステップレベルの実行前サマリー."""
        builder = _STEP_PRE_BUILDERS.get(step)
        if builder is None:
            return None
        return builder(input_data, project_dir)

    def build_item_pre_summary(
        self, step: PipelineStep, item_id: str, input_data: object, project_dir: Path
    ) -> ItemSummary | None:
        """アイテムレベルの実行前サマリー."""
        builder = _ITEM_PRE_BUILDERS.get(step)
        if builder is None:
            return None
        return builder(item_id, input_data, project_dir)

    def build_step_post_summary(
        self, step: PipelineStep, input_data: object, output: object, project_dir: Path
    ) -> StepSummary | None:
        """ステップレベルの実行後サマリー."""
        builder = _STEP_POST_BUILDERS.get(step)
        if builder is None:
            return None
        return builder(input_data, output, project_dir)


# --- Asset ビルダー ---


def _step_pre_asset(input_data: object, project_dir: Path) -> StepSummary:
    """Asset ステップの実行前サマリー."""
    from daily_routine.schemas.scenario import Scenario

    summary = StepSummary(
        step=PipelineStep.ASSET,
        phase="pre",
        title="Asset 生成計画 (実行前サマリー)",
    )

    if not isinstance(input_data, Scenario):
        return summary

    # キャラクター一覧
    char_names = [c.name for c in input_data.characters]
    summary.entries.append(SummaryEntry(label="キャラクター", value=", ".join(char_names) if char_names else "(なし)"))

    # mapping.yaml 有無
    mapping_path = project_dir / "assets" / "reference" / "mapping.yaml"
    summary.entries.append(SummaryEntry(label="mapping.yaml", value="あり" if mapping_path.exists() else "なし"))

    # environment_seeds.yaml 有無
    seeds_path = project_dir / "assets" / "reference" / "environment_seeds.yaml"
    summary.entries.append(
        SummaryEntry(label="environment_seeds.yaml", value="あり" if seeds_path.exists() else "なし")
    )

    return summary


def _item_pre_asset(item_id: str, input_data: object, project_dir: Path) -> ItemSummary:
    """Asset アイテムの実行前サマリー."""
    from daily_routine.schemas.scenario import Scenario

    summary = ItemSummary(item_id=item_id)

    if not isinstance(input_data, Scenario):
        return summary

    if item_id.startswith("char_"):
        # char_{name}_{variant} パース
        parts = item_id.split("_", 1)[1]
        last_underscore = parts.rfind("_")
        char_name = parts[:last_underscore]
        variant_label = parts[last_underscore + 1 :]

        char_spec = next((c for c in input_data.characters if c.name == char_name), None)

        summary.entries.append(SummaryEntry(label="種別", value="キャラクター"))
        summary.entries.append(SummaryEntry(label="キャラクター", value=char_name))
        summary.entries.append(SummaryEntry(label="バリアント", value=variant_label))

        # 参照画像パス
        suffix = f"_{variant_label}" if variant_label != "default" else ""
        summary.entries.append(
            SummaryEntry(label="参照画像", value=f"person/{char_name}.png, clothing/{char_name}{suffix}.png")
        )

        if char_spec:
            summary.entries.append(SummaryEntry(label="appearance", value=char_spec.appearance))
            summary.entries.append(SummaryEntry(label="outfit", value=char_spec.outfit))

        summary.output_path = f"assets/character/{char_name}/{variant_label}/front.png"
        summary.processing_steps = [
            ProcessingStep(1, "Flash Fusion 分析", "[person.png + clothing.png]", "融合テキスト分析"),
            ProcessingStep(2, "Pro 画像生成", "[融合分析 + 参照画像]", "front.png (フルボディ正面)"),
            ProcessingStep(3, "Flash Identity 抽出", "[front.png]", "identity_block テキスト"),
        ]

    elif item_id.startswith("env_"):
        scene_number = int(item_id.split("_", 1)[1])

        summary.entries.append(SummaryEntry(label="種別", value="環境"))
        summary.entries.append(SummaryEntry(label="シーン", value=str(scene_number)))

        # environment_seeds からソース情報を取得
        seeds_path = project_dir / "assets" / "reference" / "environment_seeds.yaml"
        source = "generate"
        if seeds_path.exists():
            import yaml

            data = yaml.safe_load(seeds_path.read_text(encoding="utf-8"))
            from daily_routine.schemas.asset import EnvironmentSeeds

            env_seeds = EnvironmentSeeds.model_validate(data)
            seed = next((s for s in env_seeds.environments if s.scene_number == scene_number), None)
            if seed:
                source = seed.source
                summary.entries.append(SummaryEntry(label="ソース", value=source))
                if source == "reference" and seed.reference_image:
                    summary.entries.append(SummaryEntry(label="参照画像", value=f"environments/{seed.reference_image}"))

        # SceneSpec の image_prompt と situation（日本語訳）
        scene_spec = next((s for s in input_data.scenes if s.scene_number == scene_number), None)
        if scene_spec:
            jp_suffix = f"\n                    (日本語: {scene_spec.situation})" if scene_spec.situation else ""
            summary.entries.append(SummaryEntry(label="image_prompt", value=scene_spec.image_prompt + jp_suffix))

        summary.output_path = f"assets/environments/scene_{scene_number:02d}.png"
        if source == "reference":
            summary.processing_steps = [
                ProcessingStep(1, "Pro Reference 生成", "[参照画像 + image_prompt]", "環境画像"),
            ]
        else:
            summary.processing_steps = [
                ProcessingStep(1, "Pro テキスト生成", "[image_prompt]", "環境画像"),
            ]

    return summary


# --- Keyframe ビルダー ---


def _step_pre_keyframe(input_data: object, project_dir: Path) -> StepSummary:
    """Keyframe ステップの実行前サマリー（全カットプレビュー + 警告）."""
    from daily_routine.schemas.pipeline_io import KeyframeInput

    summary = StepSummary(
        step=PipelineStep.KEYFRAME,
        phase="pre",
        title="Keyframe 生成計画 (実行前サマリー)",
    )

    if not isinstance(input_data, KeyframeInput):
        return summary

    storyboard = input_data.storyboard
    assets = input_data.assets
    keyframe_mapping = input_data.keyframe_mapping

    all_cuts = [cut for scene in storyboard.scenes for cut in scene.cuts]
    summary.entries.append(SummaryEntry(label="総カット数", value=str(len(all_cuts))))

    # 利用可能キャラクター一覧
    char_labels = [f"{c.character_name}({c.variant_id})" for c in assets.characters]
    summary.entries.append(
        SummaryEntry(label="利用可能キャラクター", value=", ".join(char_labels) if char_labels else "(なし)")
    )

    # 利用可能環境一覧
    env_labels = [f"scene_{e.scene_number}" for e in assets.environments]
    summary.entries.append(SummaryEntry(label="利用可能環境", value=", ".join(env_labels) if env_labels else "(なし)"))

    # keyframe_mapping 有無
    if keyframe_mapping:
        summary.entries.append(
            SummaryEntry(
                label="keyframe_mapping",
                value=f"あり ({len(keyframe_mapping.scenes)} シーン定義)",
            )
        )
    else:
        summary.entries.append(SummaryEntry(label="keyframe_mapping", value="なし"))

    # 全カットプレビュー
    warnings: list[str] = []
    cut_previews: list[ItemSummary] = []

    for cut in all_cuts:
        preview = ItemSummary(item_id=cut.cut_id)
        preview.entries.append(SummaryEntry(label="scene", value=str(cut.scene_number)))
        preview.entries.append(SummaryEntry(label="has_char", value=str(cut.has_character)))

        spec = keyframe_mapping.get_spec(cut.scene_number) if keyframe_mapping else None

        # キャラクター解決
        if cut.has_character:
            char_info = _resolve_character_preview(assets, spec)
            preview.entries.append(SummaryEntry(label="キャラクター", value=char_info.label, warning=char_info.warning))
            if char_info.warning and char_info.warning_msg:
                preview.warnings.append(char_info.warning_msg)
                warnings.append(f"{cut.cut_id}: {char_info.warning_msg}")
        else:
            preview.entries.append(SummaryEntry(label="キャラクター", value="(なし)"))

        # 環境解決
        env_info = _resolve_environment_preview(assets, cut.scene_number, spec)
        preview.entries.append(SummaryEntry(label="環境", value=env_info.label, warning=env_info.warning))
        if env_info.warning and env_info.warning_msg:
            preview.warnings.append(env_info.warning_msg)
            warnings.append(f"{cut.cut_id}: {env_info.warning_msg}")

        # ポーズ
        pose = cut.pose_instruction
        if spec and spec.pose and not pose:
            pose = spec.pose
        preview.entries.append(SummaryEntry(label="ポーズ", value=pose if pose else "(なし)"))

        cut_previews.append(preview)

    summary.item_summaries = cut_previews
    summary.warnings = warnings

    return summary


@dataclass
class _ResolveResult:
    """解決結果."""

    label: str
    warning: bool = False
    warning_msg: str = ""


def _resolve_character_preview(assets: object, spec: object) -> _ResolveResult:
    """Keyframe のキャラクター解決をリードオンリーで再現する."""
    from daily_routine.schemas.asset import AssetSet
    from daily_routine.schemas.keyframe_mapping import CharacterComponent, SceneKeyframeSpec

    if not isinstance(assets, AssetSet) or not assets.characters:
        return _ResolveResult(label="(キャラクターなし)", warning=True, warning_msg="キャラクターアセットがありません")

    if not isinstance(spec, SceneKeyframeSpec) or not spec.components:
        # デフォルト: 先頭キャラクター
        char = assets.characters[0]
        return _ResolveResult(label=f"{char.character_name} variant={char.variant_id}")

    # components からキャラクターを探す
    for component in spec.components:
        if isinstance(component, CharacterComponent):
            name = component.character
            variant = component.variant_id

            # name + variant_id でマッチ
            if name and variant:
                matched = next(
                    (c for c in assets.characters if c.character_name == name and c.variant_id == variant),
                    None,
                )
                if matched:
                    return _ResolveResult(label=f"{matched.character_name} variant={matched.variant_id}")

                # variant 不一致 → 名前のみ検索
                name_matched = next((c for c in assets.characters if c.character_name == name), None)
                if name_matched:
                    return _ResolveResult(
                        label=f"{name_matched.character_name} variant={name_matched.variant_id} (指定: {variant})",
                        warning=True,
                        warning_msg=f"variant '{variant}' が見つかりません。 '{name_matched.variant_id}' を使用します",
                    )

                # 名前もなし → デフォルト
                default = assets.characters[0]
                return _ResolveResult(
                    label=f"{default.character_name} variant={default.variant_id} (指定: {name})",
                    warning=True,
                    warning_msg=f"キャラクター '{name}' が見つかりません。デフォルトを使用します",
                )

            if name:
                matched = next((c for c in assets.characters if c.character_name == name), None)
                if matched:
                    return _ResolveResult(label=f"{matched.character_name} variant={matched.variant_id}")
                default = assets.characters[0]
                return _ResolveResult(
                    label=f"{default.character_name} variant={default.variant_id} (指定: {name})",
                    warning=True,
                    warning_msg=f"キャラクター '{name}' が見つかりません。デフォルトを使用します",
                )

            # 名前未指定 → デフォルト
            char = assets.characters[0]
            return _ResolveResult(label=f"{char.character_name} variant={char.variant_id}")

    # CharacterComponent がない場合
    char = assets.characters[0]
    return _ResolveResult(label=f"{char.character_name} variant={char.variant_id}")


def _resolve_environment_preview(assets: object, scene_number: int, spec: object) -> _ResolveResult:
    """Keyframe の環境解決をリードオンリーで再現する."""
    from daily_routine.schemas.asset import AssetSet
    from daily_routine.schemas.keyframe_mapping import SceneKeyframeSpec

    if not isinstance(assets, AssetSet):
        return _ResolveResult(label="(未解決)", warning=True, warning_msg="AssetSet がありません")

    if isinstance(spec, SceneKeyframeSpec) and spec.environment:
        # マッピング指定の description で検索
        for env in assets.environments:
            if env.description == spec.environment:
                return _ResolveResult(label=env.image_path.name)

        # description 不一致 → scene_number フォールバック
        for env in assets.environments:
            if env.scene_number == scene_number:
                return _ResolveResult(
                    label=f"{env.image_path.name} (指定: {spec.environment})",
                    warning=True,
                    warning_msg=f"環境 '{spec.environment}' が見つかりません。"
                    f"scene_number={scene_number} でフォールバック",
                )

        return _ResolveResult(
            label="(未解決) [!]",
            warning=True,
            warning_msg=f"環境画像が見つかりません (environment='{spec.environment}', scene_number={scene_number})",
        )

    # spec なしまたは environment 未指定 → scene_number で検索
    for env in assets.environments:
        if env.scene_number == scene_number:
            return _ResolveResult(label=env.image_path.name)

    return _ResolveResult(
        label="(未解決) [!]",
        warning=True,
        warning_msg=f"環境画像が見つかりません (scene_number={scene_number})",
    )


def _item_pre_keyframe(item_id: str, input_data: object, project_dir: Path) -> ItemSummary:
    """Keyframe アイテムの実行前サマリー."""
    from daily_routine.schemas.pipeline_io import KeyframeInput

    summary = ItemSummary(item_id=item_id)

    if not isinstance(input_data, KeyframeInput):
        return summary

    # 対象カットを検索
    target_cut = None
    for scene in input_data.storyboard.scenes:
        for cut in scene.cuts:
            if cut.cut_id == item_id:
                target_cut = cut
                break
        if target_cut:
            break

    if target_cut is None:
        summary.warnings.append(f"カット '{item_id}' が見つかりません")
        return summary

    assets = input_data.assets
    keyframe_mapping = input_data.keyframe_mapping
    spec = keyframe_mapping.get_spec(target_cut.scene_number) if keyframe_mapping else None

    # キャラクター解決
    if target_cut.has_character:
        char_info = _resolve_character_preview(assets, spec)
        char_asset = _find_matching_character(assets, spec)
        if char_asset:
            summary.entries.append(
                SummaryEntry(
                    label="キャラクター",
                    value=f"{char_asset.character_name} variant={char_asset.variant_id} → {char_asset.front_view.name}",
                )
            )
        else:
            summary.entries.append(SummaryEntry(label="キャラクター", value=char_info.label, warning=char_info.warning))
    else:
        summary.entries.append(SummaryEntry(label="キャラクター", value="(なし)"))

    # 環境解決
    env_info = _resolve_environment_preview(assets, target_cut.scene_number, spec)
    env_label = env_info.label
    summary.entries.append(SummaryEntry(label="環境画像", value=env_label, warning=env_info.warning))

    # ポーズ
    pose = target_cut.pose_instruction
    if spec and spec.pose and not pose:
        pose = spec.pose
    if pose:
        summary.entries.append(SummaryEntry(label="pose_instruction", value=pose))

    # keyframe_prompt
    if target_cut.keyframe_prompt:
        summary.entries.append(SummaryEntry(label="keyframe_prompt", value=target_cut.keyframe_prompt))

    summary.output_path = f"assets/keyframes/{item_id}.png"
    summary.processing_steps = [
        ProcessingStep(
            1,
            "Flash Scene 分析",
            "[キャラ画像 + 環境画像 + identity_block + pose_instruction]",
            "シーン記述テキスト",
        ),
        ProcessingStep(2, "Pro Keyframe 生成", "[キャラ画像 + 環境画像 + シーン記述]", "keyframe PNG (9:16)"),
    ]

    return summary


def _find_matching_character(assets: object, spec: object) -> object | None:
    """spec に基づいてマッチする CharacterAsset を返す."""
    from daily_routine.schemas.asset import AssetSet
    from daily_routine.schemas.keyframe_mapping import CharacterComponent, SceneKeyframeSpec

    if not isinstance(assets, AssetSet) or not assets.characters:
        return None

    if not isinstance(spec, SceneKeyframeSpec) or not spec.components:
        return assets.characters[0]

    for component in spec.components:
        if isinstance(component, CharacterComponent):
            name = component.character
            variant = component.variant_id
            if name and variant:
                matched = next(
                    (c for c in assets.characters if c.character_name == name and c.variant_id == variant),
                    None,
                )
                if matched:
                    return matched
            if name:
                matched = next((c for c in assets.characters if c.character_name == name), None)
                if matched:
                    return matched
            return assets.characters[0]

    return assets.characters[0]


# --- Visual ビルダー ---


def _step_pre_visual(input_data: object, project_dir: Path) -> StepSummary:
    """Visual ステップの実行前サマリー."""
    from daily_routine.schemas.pipeline_io import VisualInput

    summary = StepSummary(
        step=PipelineStep.VISUAL,
        phase="pre",
        title="Visual 生成計画 (実行前サマリー)",
    )

    if not isinstance(input_data, VisualInput):
        return summary

    all_cuts = [cut for scene in input_data.storyboard.scenes for cut in scene.cuts]
    summary.entries.append(SummaryEntry(label="総カット数", value=str(len(all_cuts))))
    summary.entries.append(SummaryEntry(label="キーフレーム数", value=str(len(input_data.assets.keyframes))))

    return summary


def _item_pre_visual(item_id: str, input_data: object, project_dir: Path) -> ItemSummary:
    """Visual アイテムの実行前サマリー."""
    from daily_routine.schemas.pipeline_io import VisualInput

    summary = ItemSummary(item_id=item_id)

    if not isinstance(input_data, VisualInput):
        return summary

    # 対象カットを検索
    target_cut = None
    for scene in input_data.storyboard.scenes:
        for cut in scene.cuts:
            if cut.cut_id == item_id:
                target_cut = cut
                break
        if target_cut:
            break

    if target_cut is None:
        summary.warnings.append(f"カット '{item_id}' が見つかりません")
        return summary

    # キーフレーム画像パス
    kf = next(
        (k for k in input_data.assets.keyframes if k.cut_id == item_id),
        next((k for k in input_data.assets.keyframes if k.scene_number == target_cut.scene_number), None),
    )
    if kf:
        summary.entries.append(SummaryEntry(label="キーフレーム", value=str(kf.image_path.name)))
    else:
        summary.entries.append(SummaryEntry(label="キーフレーム", value="(未発見)", warning=True))
        summary.warnings.append(f"キーフレーム画像が見つかりません: {item_id}")

    # motion_prompt + 日本語訳
    motion_value = target_cut.motion_prompt
    if target_cut.action_description:
        motion_value += f"\n                    (日本語: {target_cut.action_description})"
    summary.entries.append(SummaryEntry(label="motion_prompt", value=motion_value))

    summary.entries.append(SummaryEntry(label="尺", value=f"{int(target_cut.duration_sec)}sec"))

    summary.output_path = f"clips/{item_id}.mp4"
    summary.processing_steps = [
        ProcessingStep(1, "GCS Upload", "[keyframe PNG]", "GCS URL"),
        ProcessingStep(2, "Runway I2V", "[GCS URL + motion_prompt + duration]", "タスク作成・ポーリング"),
        ProcessingStep(3, "Download", "[video URL]", "MP4 (9:16)"),
    ]

    return summary


# --- Audio ビルダー ---


def _step_pre_audio(input_data: object, project_dir: Path) -> StepSummary:
    """Audio ステップの実行前サマリー."""
    from daily_routine.schemas.pipeline_io import AudioInput

    summary = StepSummary(
        step=PipelineStep.AUDIO,
        phase="pre",
        title="Audio 生成計画 (実行前サマリー)",
    )

    if not isinstance(input_data, AudioInput):
        return summary

    audio_trend = input_data.audio_trend
    summary.entries.append(SummaryEntry(label="BGM方向性", value=input_data.scenario.bgm_direction))
    summary.entries.append(
        SummaryEntry(label="BPM範囲", value=f"{audio_trend.bpm_range[0]}-{audio_trend.bpm_range[1]}")
    )
    if audio_trend.genres:
        summary.entries.append(SummaryEntry(label="ジャンル", value=", ".join(audio_trend.genres)))

    return summary


def _step_post_audio(input_data: object, output: object, project_dir: Path) -> StepSummary:
    """Audio ステップの実行後サマリー."""
    from daily_routine.schemas.audio import AudioAsset

    summary = StepSummary(
        step=PipelineStep.AUDIO,
        phase="post",
        title="Audio 生成結果 (実行後サマリー)",
    )

    if not isinstance(output, AudioAsset):
        return summary

    summary.entries.append(SummaryEntry(label="BGMファイル", value=str(output.bgm.file_path.name)))
    summary.entries.append(SummaryEntry(label="SE数", value=str(len(output.sound_effects))))

    return summary


# --- ディスパッチテーブル ---

_STEP_PRE_BUILDERS: dict[PipelineStep, object] = {
    PipelineStep.ASSET: _step_pre_asset,
    PipelineStep.KEYFRAME: _step_pre_keyframe,
    PipelineStep.VISUAL: _step_pre_visual,
    PipelineStep.AUDIO: _step_pre_audio,
}

_ITEM_PRE_BUILDERS: dict[PipelineStep, object] = {
    PipelineStep.ASSET: _item_pre_asset,
    PipelineStep.KEYFRAME: _item_pre_keyframe,
    PipelineStep.VISUAL: _item_pre_visual,
}

_STEP_POST_BUILDERS: dict[PipelineStep, object] = {
    PipelineStep.AUDIO: _step_post_audio,
}


# --- ログ出力 ---


def log_summary(summary: StepSummary) -> None:
    """StepSummary をログ出力する."""
    logger.info(_SEPARATOR)
    logger.info("[%s] %s", summary.step.value, summary.title)
    logger.info(_SEPARATOR)

    for entry in summary.entries:
        if entry.warning:
            logger.warning("  %s: %s", entry.label, entry.value)
        else:
            logger.info("  %s: %s", entry.label, entry.value)

    # カットプレビュー（Keyframe ステップ）
    if summary.item_summaries:
        logger.info("")
        logger.info("  --- 全カットプレビュー (%d件) ---", len(summary.item_summaries))
        for item in summary.item_summaries:
            # 1行目: cut_id + scene + has_char
            scene_entry = next((e for e in item.entries if e.label == "scene"), None)
            has_char_entry = next((e for e in item.entries if e.label == "has_char"), None)
            scene_val = scene_entry.value if scene_entry else "?"
            has_char_val = has_char_entry.value if has_char_entry else "?"
            logger.info("  [%s] scene=%s has_char=%s", item.item_id, scene_val, has_char_val)

            # 2行目: キャラクター・環境・ポーズ
            char_entry = next((e for e in item.entries if e.label == "キャラクター"), None)
            env_entry = next((e for e in item.entries if e.label == "環境"), None)
            pose_entry = next((e for e in item.entries if e.label == "ポーズ"), None)
            parts = []
            if char_entry:
                parts.append(f"キャラクター: {char_entry.value}")
            if env_entry:
                parts.append(f"環境: {env_entry.value}")
            if pose_entry:
                parts.append(f"ポーズ: {pose_entry.value}")
            if parts:
                detail_line = "  ".join(parts)
                if any(e.warning for e in item.entries if e.label in ("キャラクター", "環境")):
                    logger.warning("    %s", detail_line)
                else:
                    logger.info("    %s", detail_line)

    # 警告
    if summary.warnings:
        logger.info("")
        logger.warning("  --- 警告 (%d件) ---", len(summary.warnings))
        for w in summary.warnings:
            logger.warning("  [!] %s", w)

    logger.info(_SEPARATOR)


def log_item_summary(summary: ItemSummary) -> None:
    """ItemSummary をログ出力する."""
    logger.info("")
    logger.info("  --- [%s] 生成 ---", summary.item_id)

    if summary.entries:
        logger.info("    入力:")
        for entry in summary.entries:
            if entry.warning:
                logger.warning("      %s: %s", entry.label, entry.value)
            else:
                logger.info("      %s: %s", entry.label, entry.value)

    if summary.output_path:
        logger.info("    出力: %s", summary.output_path)

    if summary.processing_steps:
        logger.info("    処理:")
        for ps in summary.processing_steps:
            logger.info("      %d. %s: %s → %s", ps.order, ps.name, ps.input_desc, ps.output_desc)

    if summary.warnings:
        for w in summary.warnings:
            logger.warning("    [!] %s", w)
