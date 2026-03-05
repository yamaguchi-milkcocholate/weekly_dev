"""Gemini C3-I1 キーフレーム生成エンジン."""

import logging
from dataclasses import dataclass, field
from pathlib import Path

from daily_routine.pipeline.base import StepEngine
from daily_routine.schemas.asset import AssetSet, CharacterAsset, KeyframeAsset
from daily_routine.schemas.keyframe_mapping import (
    CharacterComponent,
    KeyframeMapping,
    ReferenceComponent,
    SceneKeyframeSpec,
)
from daily_routine.schemas.pipeline_io import KeyframeInput
from daily_routine.schemas.scenario import Scenario
from daily_routine.schemas.storyboard import CutSpec, Storyboard

from .base import KeyframeEngineBase
from .client import GeminiKeyframeClient
from .prompt import ReferenceInfo

logger = logging.getLogger(__name__)

_STYLE_CONTINUITY_REF = ReferenceInfo(
    purpose="atmosphere",
    text="Previous cut from the same location. "
         "Match the color palette, lighting tone, "
         "and overall visual atmosphere.",
    has_image=True,
)


@dataclass
class ResolvedComponents:
    """コンポーネント解決結果."""

    char_images: list[Path] = field(default_factory=list)
    identity_blocks: list[str] = field(default_factory=list)
    reference_images: list[Path] = field(default_factory=list)
    reference_infos: list[ReferenceInfo] = field(default_factory=list)


class GeminiKeyframeEngine(StepEngine[KeyframeInput, AssetSet], KeyframeEngineBase):
    """Gemini C3-I1 を使ったキーフレーム生成エンジン."""

    def __init__(self, api_key: str = "") -> None:
        if api_key:
            self._client = GeminiKeyframeClient(api_key=api_key)
        else:
            self._client = None  # type: ignore[assignment]

    @classmethod
    def from_components(cls, client: GeminiKeyframeClient) -> "GeminiKeyframeEngine":
        """テスト用DI: 構築済みクライアントを注入する."""
        instance = cls.__new__(cls)
        instance._client = client
        return instance

    async def execute(self, input_data: KeyframeInput, project_dir: Path) -> AssetSet:
        """キーフレーム画像を生成する."""
        output_dir = project_dir / "assets" / "keyframes"
        return await self.generate_keyframes(
            scenario=input_data.scenario,
            storyboard=input_data.storyboard,
            assets=input_data.assets,
            output_dir=output_dir,
            keyframe_mapping=input_data.keyframe_mapping,
            project_dir=project_dir,
        )

    async def generate_keyframes(
        self,
        scenario: Scenario,
        storyboard: Storyboard,
        assets: AssetSet,
        output_dir: Path,
        keyframe_mapping: KeyframeMapping | None = None,
        project_dir: Path | None = None,
    ) -> AssetSet:
        """全カットのキーフレーム画像を生成する."""
        output_dir.mkdir(parents=True, exist_ok=True)

        all_cuts_preview = [cut for scene in storyboard.scenes for cut in scene.cuts]
        has_any_character_cut = any(cut.has_character for cut in all_cuts_preview)
        if has_any_character_cut and not assets.characters:
            msg = "キャラクターアセットが存在しません"
            raise ValueError(msg)

        all_cuts = [cut for scene in storyboard.scenes for cut in scene.cuts]
        total_cuts = len(all_cuts)

        keyframes: list[KeyframeAsset] = []
        prev_keyframe_by_env: dict[Path, Path] = {}
        for i, cut in enumerate(all_cuts, start=1):
            keyframe_path = output_dir / f"{cut.cut_id}.png"

            logger.info("キーフレーム %d/%d (%s) の生成を開始します", i, total_cuts, cut.cut_id)

            # KeyframeMapping 参照（シーン単位、同一シーン内の全カットに同じマッピングを適用）
            spec = keyframe_mapping.get_spec(cut.scene_number) if keyframe_mapping else None

            # コンポーネント解決
            resolved = self._resolve_components(assets, spec, require_character=cut.has_character)

            # 環境解決: マッピング指定（description 検索）→ scene_number 検索
            env_image = self._resolve_environment(assets, cut.scene_number, spec)

            # スタイル連続性: 同一環境の前カット参照を注入
            if env_image is not None and env_image in prev_keyframe_by_env:
                prev_kf = prev_keyframe_by_env[env_image]
                if prev_kf.exists():
                    resolved.reference_images.append(prev_kf)
                    resolved.reference_infos.append(_STYLE_CONTINUITY_REF)
                    logger.info("  スタイル連続性: 前カット参照を注入 (%s)", prev_kf.name)

            # ポーズ取得
            pose_instruction = cut.pose_instruction
            if spec and spec.pose and not pose_instruction:
                pose_instruction = spec.pose

            # Step 1: Flash シーン分析
            logger.info("  Step 1: Flash シーン分析")
            flash_prompt = await self._client.analyze_scene(
                char_images=resolved.char_images,
                env_image=env_image,
                identity_blocks=resolved.identity_blocks,
                pose_instruction=pose_instruction,
                reference_images=resolved.reference_images,
                reference_infos=resolved.reference_infos,
            )
            logger.info("  Flash 生成プロンプト: %s", flash_prompt[:200])

            # Step 2: Pro シーン画像生成
            logger.info("  Step 2: Pro シーン画像生成")
            result_path = await self._client.generate_keyframe(
                char_images=resolved.char_images,
                env_image=env_image,
                flash_prompt=flash_prompt,
                reference_images=resolved.reference_images,
                reference_infos=resolved.reference_infos,
                output_path=keyframe_path,
            )

            # スタイル連続性: 生成結果をトラッキング更新
            if env_image is not None:
                prev_keyframe_by_env[env_image] = result_path

            keyframes.append(
                KeyframeAsset(
                    scene_number=cut.scene_number,
                    image_path=result_path,
                    prompt=flash_prompt,
                    cut_id=cut.cut_id,
                    generation_method="gemini",
                )
            )

            logger.info("キーフレーム %d/%d 完了", i, total_cuts)

        return assets.model_copy(update={"keyframes": keyframes})

    @staticmethod
    def _resolve_components(
        assets: AssetSet, spec: SceneKeyframeSpec | None, *, require_character: bool = True
    ) -> ResolvedComponents:
        """spec.components をイテレートしてコンポーネントを解決する."""
        resolved = ResolvedComponents()

        if not spec or not spec.components:
            # コンポーネント未指定 → デフォルト（先頭キャラクター、require_character=True の場合のみ）
            if require_character:
                char = assets.characters[0]
                resolved.char_images.append(char.front_view)
                resolved.identity_blocks.append(char.identity_block)
            return resolved

        for component in spec.components:
            if isinstance(component, CharacterComponent):
                if not require_character:
                    continue
                char = GeminiKeyframeEngine._find_character_asset(assets, component.character, component.variant_id)
                resolved.char_images.append(char.front_view)
                resolved.identity_blocks.append(char.identity_block)
            elif isinstance(component, ReferenceComponent):
                if component.image:
                    resolved.reference_images.append(component.image)
                resolved.reference_infos.append(
                    ReferenceInfo(
                        purpose=str(component.purpose),
                        text=component.text,
                        has_image=component.image is not None,
                    )
                )

        # require_character=True のときのみデフォルトフォールバック
        if require_character and not resolved.char_images:
            char = assets.characters[0]
            resolved.char_images.append(char.front_view)
            resolved.identity_blocks.append(char.identity_block)

        return resolved

    @staticmethod
    def _find_character_asset(assets: AssetSet, character_name: str, variant_id: str = "") -> CharacterAsset:
        """キャラクター名 + variant_id で AssetSet からキャラクターを検索する."""
        if character_name:
            if variant_id:
                for char in assets.characters:
                    if char.character_name == character_name and char.variant_id == variant_id:
                        return char
                logger.warning(
                    "キャラクター '%s' variant '%s' が見つかりません。名前のみで検索します",
                    character_name,
                    variant_id,
                )
            for char in assets.characters:
                if char.character_name == character_name:
                    return char
            logger.warning(
                "マッピング指定のキャラクター '%s' が見つかりません。デフォルトを使用します",
                character_name,
            )
        return assets.characters[0]

    @staticmethod
    def _resolve_environment(assets: AssetSet, scene_number: int, spec: SceneKeyframeSpec | None) -> Path | None:
        """マッピング指定の環境を解決する。未指定時は scene_number でフォールバック."""
        if spec and spec.environment:
            for env in assets.environments:
                if env.description == spec.environment:
                    return env.image_path
            logger.warning(
                "マッピング指定の環境 '%s' が見つかりません。scene_number でフォールバックします",
                spec.environment,
            )
        # フォールバック: scene_number で検索
        for env in assets.environments:
            if env.scene_number == scene_number:
                return env.image_path
        return None

    def _find_previous_keyframe_same_env(
        self,
        target_cut: CutSpec,
        storyboard: Storyboard,
        assets: AssetSet,
        keyframe_mapping: KeyframeMapping | None,
    ) -> Path | None:
        """同一環境の直前キーフレームを検索する（execute_item 用）."""
        # 対象カットの環境を解決
        spec = keyframe_mapping.get_spec(target_cut.scene_number) if keyframe_mapping else None
        target_env = self._resolve_environment(assets, target_cut.scene_number, spec)
        if target_env is None:
            return None

        # 全カットを順序通りに取得し、対象カットのインデックスを特定
        all_cuts: list[CutSpec] = [cut for scene in storyboard.scenes for cut in scene.cuts]
        target_idx: int | None = None
        for i, cut in enumerate(all_cuts):
            if cut.cut_id == target_cut.cut_id:
                target_idx = i
                break
        if target_idx is None or target_idx == 0:
            return None

        # 既存キーフレームの cut_id → image_path マップを構築
        kf_map: dict[str, Path] = {kf.cut_id: kf.image_path for kf in assets.keyframes}

        # インデックスを逆順走査し、同一環境の最も近いキーフレームを返す
        for i in range(target_idx - 1, -1, -1):
            prev_cut = all_cuts[i]
            prev_spec = keyframe_mapping.get_spec(prev_cut.scene_number) if keyframe_mapping else None
            prev_env = self._resolve_environment(assets, prev_cut.scene_number, prev_spec)
            if prev_env == target_env and prev_cut.cut_id in kf_map:
                prev_path = kf_map[prev_cut.cut_id]
                if prev_path.exists():
                    return prev_path
        return None

    # --- アイテム単位実行 ---

    @property
    def supports_items(self) -> bool:
        """アイテム単位実行に対応する."""
        return True

    def list_items(self, input_data: KeyframeInput, project_dir: Path) -> list[str]:
        """全カットIDをアイテムIDとして返す."""
        return [cut.cut_id for scene in input_data.storyboard.scenes for cut in scene.cuts]

    async def execute_item(self, item_id: str, input_data: KeyframeInput, project_dir: Path) -> None:
        """指定 cut_id のキーフレーム1枚を生成し、AssetSet に追記保存する."""
        output_dir = project_dir / "assets" / "keyframes"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 既存の AssetSet を読み込み
        try:
            assets = self.load_output(project_dir)
        except FileNotFoundError:
            assets = input_data.assets.model_copy()

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
            msg = f"カット '{item_id}' が Storyboard に見つかりません"
            raise ValueError(msg)

        keyframe_path = output_dir / f"{target_cut.cut_id}.png"

        spec = input_data.keyframe_mapping.get_spec(target_cut.scene_number) if input_data.keyframe_mapping else None
        resolved = self._resolve_components(assets, spec, require_character=target_cut.has_character)
        env_image = self._resolve_environment(assets, target_cut.scene_number, spec)

        # スタイル連続性: 同一環境の前カット参照を注入
        prev_kf = self._find_previous_keyframe_same_env(
            target_cut, input_data.storyboard, assets, input_data.keyframe_mapping
        )
        if prev_kf is not None:
            resolved.reference_images.append(prev_kf)
            resolved.reference_infos.append(_STYLE_CONTINUITY_REF)
            logger.info("  スタイル連続性: 前カット参照を注入 (%s)", prev_kf.name)

        pose_instruction = target_cut.pose_instruction
        if spec and spec.pose and not pose_instruction:
            pose_instruction = spec.pose

        flash_prompt = await self._client.analyze_scene(
            char_images=resolved.char_images,
            env_image=env_image,
            identity_blocks=resolved.identity_blocks,
            pose_instruction=pose_instruction,
            reference_images=resolved.reference_images,
            reference_infos=resolved.reference_infos,
        )

        result_path = await self._client.generate_keyframe(
            char_images=resolved.char_images,
            env_image=env_image,
            flash_prompt=flash_prompt,
            reference_images=resolved.reference_images,
            reference_infos=resolved.reference_infos,
            output_path=keyframe_path,
        )

        new_keyframe = KeyframeAsset(
            scene_number=target_cut.scene_number,
            image_path=result_path,
            prompt=flash_prompt,
            cut_id=target_cut.cut_id,
            generation_method="gemini",
        )

        # 既存の同一 cut_id のキーフレームを置換、なければ追加
        replaced = False
        for i, kf in enumerate(assets.keyframes):
            if kf.cut_id == item_id:
                assets.keyframes[i] = new_keyframe
                replaced = True
                break
        if not replaced:
            assets.keyframes.append(new_keyframe)

        self.save_output(project_dir, assets)
        logger.info("キーフレーム '%s' を生成・保存しました", item_id)

    def save_output(self, project_dir: Path, output: AssetSet) -> None:
        """AssetSet（keyframes 含む）を保存する."""
        metadata_path = project_dir / "assets" / "asset_set.json"
        metadata_path.parent.mkdir(parents=True, exist_ok=True)
        metadata_path.write_text(output.model_dump_json(indent=2))

    def load_output(self, project_dir: Path) -> AssetSet:
        """保存済みの AssetSet を読み込む."""
        metadata_path = project_dir / "assets" / "asset_set.json"
        if not metadata_path.exists():
            msg = f"AssetSet ファイルが見つかりません: {metadata_path}"
            raise FileNotFoundError(msg)
        return AssetSet.model_validate_json(metadata_path.read_text())
