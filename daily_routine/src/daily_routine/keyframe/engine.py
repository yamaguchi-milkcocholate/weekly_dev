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
from daily_routine.schemas.storyboard import Storyboard

from .base import KeyframeEngineBase
from .client import GeminiKeyframeClient
from .prompt import ReferenceInfo

logger = logging.getLogger(__name__)


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

        if not assets.characters:
            msg = "キャラクターアセットが存在しません"
            raise ValueError(msg)

        all_cuts = [cut for scene in storyboard.scenes for cut in scene.cuts]
        total_cuts = len(all_cuts)

        keyframes: list[KeyframeAsset] = []
        for i, cut in enumerate(all_cuts, start=1):
            keyframe_path = output_dir / f"{cut.cut_id}.png"

            logger.info("キーフレーム %d/%d (%s) の生成を開始します", i, total_cuts, cut.cut_id)

            # KeyframeMapping 参照（シーン単位、同一シーン内の全カットに同じマッピングを適用）
            spec = keyframe_mapping.get_spec(cut.scene_number) if keyframe_mapping else None

            # コンポーネント解決
            resolved = self._resolve_components(assets, spec)

            # 環境解決: マッピング指定（description 検索）→ scene_number 検索
            env_image = self._resolve_environment(assets, cut.scene_number, spec)

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
    def _resolve_components(assets: AssetSet, spec: SceneKeyframeSpec | None) -> ResolvedComponents:
        """spec.components をイテレートしてコンポーネントを解決する."""
        resolved = ResolvedComponents()

        if not spec or not spec.components:
            # コンポーネント未指定 → デフォルト（先頭キャラクター）
            char = assets.characters[0]
            resolved.char_images.append(char.front_view)
            resolved.identity_blocks.append(char.identity_block)
            return resolved

        for component in spec.components:
            if isinstance(component, CharacterComponent):
                char = GeminiKeyframeEngine._find_character_asset(
                    assets, component.character, component.variant_id
                )
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

        # キャラクターが1つも解決されなかった場合、デフォルトを使用
        if not resolved.char_images:
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
