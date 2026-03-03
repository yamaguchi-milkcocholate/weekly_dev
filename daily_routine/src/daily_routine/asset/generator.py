"""Gemini を使った Asset Generator 実装."""

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

import yaml

from daily_routine.pipeline.base import StepEngine
from daily_routine.schemas.asset import (
    AssetSet,
    CharacterAsset,
    CharacterReferenceSpec,
    ClothingReferenceSpec,
    EnvironmentAsset,
    EnvironmentSeeds,
    EnvironmentSeedSpec,
    ReferenceMapping,
)
from daily_routine.schemas.scenario import CharacterSpec, Scenario, SceneSpec

from .base import AssetGenerator
from .client import GeminiImageClient
from .prompt import (
    FLASH_FUSION_ANALYSIS_PROMPT,
    IDENTITY_BLOCK_EXTRACTION_PROMPT,
    PromptBuilder,
)

logger = logging.getLogger(__name__)

# キャラクターの標準ビュー
_CHARACTER_VIEWS = ["front", "side", "back"]

# 並列生成時の同時実行数上限（Gemini API レート制限対策）
_MAX_CONCURRENCY = 3

_ASSET_SET_FILENAME = "asset_set.json"
_MAPPING_FILENAME = "mapping.yaml"


class GeminiAssetGenerator(StepEngine[Scenario, AssetSet], AssetGenerator):
    """Gemini を使った Asset Generator 実装.

    StepEngine[Scenario, AssetSet] を実装しパイプラインに統合しつつ、
    AssetGenerator の各メソッドも実装する。

    C1-F2-MA 方式:
    1. mapping.yaml で参照画像を一元管理
    2. null の場合はテキストから自動生成
    3. Flash 融合分析 → Pro マルチアングル生成 → Identity Block 抽出
    """

    def __init__(
        self,
        api_key: str = "",
        model_name: str = "gemini-3-pro-image-preview",
    ) -> None:
        if api_key:
            self._client = GeminiImageClient(api_key=api_key, model_name=model_name)
        else:
            self._client = None  # type: ignore[assignment]
        self._prompt_builder = PromptBuilder()
        self._api_call_count = 0

    @classmethod
    def from_components(cls, client: GeminiImageClient, prompt_builder: PromptBuilder) -> "GeminiAssetGenerator":
        """クライアントとプロンプトビルダーを直接注入してインスタンスを生成する."""
        instance = cls.__new__(cls)
        instance._client = client
        instance._prompt_builder = prompt_builder
        instance._api_call_count = 0
        return instance

    async def execute(self, input_data: Scenario, project_dir: Path) -> AssetSet:
        """パイプラインステップとして実行する."""
        if self._client is None:
            msg = "Gemini API キーが設定されていません"
            raise ValueError(msg)

        output_dir = project_dir / "assets"
        reference_dir = output_dir / "reference"

        # 1. mapping.yaml の読み込み or 生成
        mapping = self._load_or_create_mapping(input_data.characters, reference_dir)

        # 2. 参照画像の解決（null は自動生成）
        char_refs = await self._resolve_and_prepare_references(mapping, input_data.characters, reference_dir)

        # 3. 環境シードファイルの読み込み
        seeds_path = reference_dir / "environment_seeds.yaml"
        env_seeds = self._load_environment_seeds(seeds_path)
        env_reference_dir = reference_dir / "environments"

        # 4. 全キャラクターで C1-F2-MA 実行（衣装バリアントごと）
        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
        character_tasks = []
        for char in input_data.characters:
            person_path, clothing_map = char_refs[char.name]
            for label, clothing_path in clothing_map.items():
                character_tasks.append(
                    self._generate_character_with_semaphore(
                        semaphore,
                        char,
                        output_dir / "character" / char.name / label,
                        person_image=person_path,
                        clothing_image=clothing_path,
                        variant_id=label,
                    )
                )
        character_assets = await asyncio.gather(*character_tasks)

        # 5. 環境画像生成（順次実行）
        environment_assets: list[EnvironmentAsset] = []
        if env_seeds and env_seeds.environments:
            environment_assets = await self._generate_environments(
                env_seeds=env_seeds,
                scenes=input_data.scenes,
                env_reference_dir=env_reference_dir,
                output_dir=output_dir / "environments",
            )

        asset_set = AssetSet(
            characters=list(character_assets),
            environments=environment_assets,
        )

        # モード判定
        mode = self._determine_mode(mapping)
        self._save_metadata(output_dir, mode)

        logger.info(
            "アセット生成完了: キャラクター=%d, 環境=%d, API呼び出し=%d",
            len(asset_set.characters),
            len(asset_set.environments),
            self._api_call_count,
        )
        return asset_set

    def load_output(self, project_dir: Path) -> AssetSet:
        """永続化済みの AssetSet を読み込む."""
        asset_set_path = project_dir / "assets" / _ASSET_SET_FILENAME
        if not asset_set_path.exists():
            msg = f"AssetSetファイルが見つかりません: {asset_set_path}"
            raise FileNotFoundError(msg)
        data = json.loads(asset_set_path.read_text(encoding="utf-8"))
        return AssetSet.model_validate(data)

    def save_output(self, project_dir: Path, output: AssetSet) -> None:
        """AssetSet を永続化する."""
        assets_dir = project_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        asset_set_path = assets_dir / _ASSET_SET_FILENAME
        asset_set_path.write_text(
            output.model_dump_json(indent=2),
            encoding="utf-8",
        )
        logger.info("AssetSet を保存しました: %s", asset_set_path)

    # --- mapping.yaml 管理 ---

    def _load_or_create_mapping(
        self,
        characters: list[CharacterSpec],
        reference_dir: Path,
    ) -> ReferenceMapping:
        """mapping.yaml を読み込み、存在しなければ自動生成する."""
        mapping_path = reference_dir / _MAPPING_FILENAME
        if mapping_path.exists():
            logger.info("mapping.yaml を読み込み: %s", mapping_path)
            data = yaml.safe_load(mapping_path.read_text(encoding="utf-8"))
            return ReferenceMapping.model_validate(data)

        # 存在しなければ全 null で自動生成
        logger.info("mapping.yaml が存在しないため自動生成します")
        mapping = ReferenceMapping(
            characters=[
                CharacterReferenceSpec(
                    name=char.name,
                    person=None,
                    clothing=None,
                    clothing_variants=[ClothingReferenceSpec(label="default", clothing=None)],
                )
                for char in characters
            ]
        )
        reference_dir.mkdir(parents=True, exist_ok=True)
        mapping_path.write_text(
            yaml.dump(
                mapping.model_dump(),
                default_flow_style=False,
                allow_unicode=True,
            ),
            encoding="utf-8",
        )
        logger.info("mapping.yaml を自動生成しました: %s", mapping_path)
        return mapping

    # --- 参照画像の解決 + 自動生成 ---

    async def _resolve_and_prepare_references(
        self,
        mapping: ReferenceMapping,
        characters: list[CharacterSpec],
        reference_dir: Path,
    ) -> dict[str, tuple[Path, dict[str, Path]]]:
        """mapping から各キャラクターの person/clothing パスを解決する.

        null の場合はテキストから自動生成する。

        Returns:
            {キャラクター名: (person_path, {variant_label: clothing_path})}
        """
        char_spec_map = {c.name: c for c in characters}
        result: dict[str, tuple[Path, dict[str, Path]]] = {}

        person_dir = reference_dir / "person"
        clothing_dir = reference_dir / "clothing"
        person_dir.mkdir(parents=True, exist_ok=True)
        clothing_dir.mkdir(parents=True, exist_ok=True)

        for ref_spec in mapping.characters:
            char = char_spec_map.get(ref_spec.name)
            if char is None:
                logger.warning("mapping.yaml のキャラクター '%s' が Scenario に見つかりません", ref_spec.name)
                continue

            # person 解決
            if ref_spec.person:
                person_path = person_dir / ref_spec.person
                if not person_path.exists():
                    msg = f"人物参照画像が見つかりません: {person_path}"
                    raise FileNotFoundError(msg)
            else:
                person_path = person_dir / f"{ref_spec.name}.png"
                if not person_path.exists():
                    await self._auto_generate_person(char, person_path)

            # clothing 解決（バリアント対応）
            clothing_map: dict[str, Path] = {}
            if ref_spec.clothing_variants:
                for variant in ref_spec.clothing_variants:
                    clothing_map[variant.label] = await self._resolve_single_clothing(
                        char,
                        variant.clothing,
                        clothing_dir,
                        ref_spec.name,
                        variant.label,
                    )
            else:
                clothing_map["default"] = await self._resolve_single_clothing(
                    char,
                    ref_spec.clothing,
                    clothing_dir,
                    ref_spec.name,
                    "default",
                )

            result[ref_spec.name] = (person_path, clothing_map)

        return result

    async def _resolve_single_clothing(
        self,
        char: CharacterSpec,
        clothing_filename: str | None,
        clothing_dir: Path,
        char_name: str,
        label: str,
    ) -> Path:
        """1つの clothing パスを解決する。null の場合は自動生成."""
        if clothing_filename:
            clothing_path = clothing_dir / clothing_filename
            if not clothing_path.exists():
                msg = f"服装参照画像が見つかりません: {clothing_path}"
                raise FileNotFoundError(msg)
            return clothing_path

        suffix = f"_{label}" if label != "default" else ""
        clothing_path = clothing_dir / f"{char_name}{suffix}.png"
        if not clothing_path.exists():
            await self._auto_generate_clothing(char, clothing_path)
        return clothing_path

    async def _auto_generate_person(self, character: CharacterSpec, output_path: Path) -> None:
        """テキストから人物ベース画像を自動生成する."""
        logger.info("人物画像を自動生成: %s → %s", character.name, output_path.name)
        prompt = self._prompt_builder.build_auto_person_prompt(character.appearance)
        await self._client.generate(prompt, output_path)
        self._api_call_count += 1

    async def _auto_generate_clothing(self, character: CharacterSpec, output_path: Path) -> None:
        """テキストから服装画像を自動生成する."""
        logger.info("服装画像を自動生成: %s → %s", character.name, output_path.name)
        prompt = self._prompt_builder.build_auto_clothing_prompt(character.outfit)
        await self._client.generate(prompt, output_path)
        self._api_call_count += 1

    # --- C1-F2-MA キャラクター生成 ---

    async def generate_assets(
        self,
        characters: list[CharacterSpec],
        scenes: list[SceneSpec],
        output_dir: Path,
        user_reference_images: dict[str, Path] | None = None,
        person_images: dict[str, Path] | None = None,
        clothing_images: dict[str, Path] | None = None,
        env_seeds: EnvironmentSeeds | None = None,
        env_reference_dir: Path | None = None,
    ) -> AssetSet:
        """全アセットを生成する.

        person_images + clothing_images が指定されていれば C1-F2-MA を使用。
        それ以外は旧来のフローにフォールバック。
        """
        self._api_call_count = 0

        # C1-F2-MA モード
        if person_images and clothing_images:
            mode = "c1f2ma_manual"
            logger.info("アセット生成を開始 (モード: %s)", mode)

            semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
            character_tasks = [
                self._generate_character_with_semaphore(
                    semaphore,
                    char,
                    output_dir / "character" / char.name / "default",
                    person_image=person_images.get(char.name),
                    clothing_image=clothing_images.get(char.name),
                    variant_id="default",
                )
                for char in characters
            ]
            character_assets = await asyncio.gather(*character_tasks)
        else:
            # 旧来フロー（後方互換）
            user_reference_images = user_reference_images or {}
            mode = "user_reference" if user_reference_images else "prompt_only"
            logger.info("アセット生成を開始 (モード: %s)", mode)

            for name, ref_path in user_reference_images.items():
                if not ref_path.exists():
                    msg = f"ユーザー参照画像が見つかりません: {name} -> {ref_path}"
                    raise FileNotFoundError(msg)

            semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
            character_tasks = [
                self._generate_character_with_semaphore(
                    semaphore,
                    character,
                    output_dir / "character" / character.name,
                    reference_image=user_reference_images.get(character.name),
                )
                for character in characters
            ]
            character_assets = await asyncio.gather(*character_tasks)

        # 環境画像生成（順次実行）
        environment_assets: list[EnvironmentAsset] = []
        if env_seeds and env_seeds.environments:
            environment_assets = await self._generate_environments(
                env_seeds=env_seeds,
                scenes=scenes,
                env_reference_dir=env_reference_dir or output_dir / "reference" / "environments",
                output_dir=output_dir / "environments",
            )

        asset_set = AssetSet(
            characters=list(character_assets),
            environments=environment_assets,
        )

        self._save_metadata(output_dir, mode)

        logger.info(
            "アセット生成完了: キャラクター=%d, 環境=%d, API呼び出し=%d",
            len(asset_set.characters),
            len(asset_set.environments),
            self._api_call_count,
        )
        return asset_set

    async def generate_character(
        self,
        character: CharacterSpec,
        output_dir: Path,
        reference_image: Path | None = None,
        person_image: Path | None = None,
        clothing_image: Path | None = None,
        variant_id: str = "default",
    ) -> CharacterAsset:
        """1キャラクターのリファレンス画像セットを生成する.

        person_image + clothing_image が両方指定 → C1-F2-MA フロー
        それ以外 → 旧来フロー（モードA/B）
        """
        if person_image is not None and clothing_image is not None:
            return await self._generate_character_c1f2ma(
                character,
                output_dir,
                person_image,
                clothing_image,
                variant_id,
            )

        return await self._generate_character_legacy(character, output_dir, reference_image, variant_id)

    async def _generate_character_c1f2ma(
        self,
        character: CharacterSpec,
        output_dir: Path,
        person_image: Path,
        clothing_image: Path,
        variant_id: str = "default",
    ) -> CharacterAsset:
        """C1-F2-MA 方式でキャラクター画像を生成する.

        Step 1: Flash 融合分析（person + clothing → flash_description）
        Step 2: Pro マルチアングル生成（front/side/back × 各1回、person+clothing 参照）
        Step 3: Flash Identity Block 抽出（front → identity_block）
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        logger.info("C1-F2-MA キャラクター生成開始: %s (variant=%s)", character.name, variant_id)

        # Step 1: Flash 融合分析
        flash_description = await self._client.analyze_with_flash(
            FLASH_FUSION_ANALYSIS_PROMPT,
            [person_image, clothing_image],
        )
        self._api_call_count += 1
        logger.info("Flash 融合分析完了: %s (%d文字)", character.name, len(flash_description))

        # Step 2: Pro マルチアングル生成
        view_paths: dict[str, Path] = {}
        for view in _CHARACTER_VIEWS:
            view_path = output_dir / f"{view}.png"
            prompt = self._prompt_builder.build_ma_generation_prompt(flash_description, view)
            await self._client.generate_with_reference(prompt, [person_image, clothing_image], view_path)
            self._api_call_count += 1
            view_paths[view] = view_path

        # Step 3: Flash Identity Block 抽出
        identity_block = await self._client.analyze_with_flash(
            IDENTITY_BLOCK_EXTRACTION_PROMPT,
            [view_paths["front"]],
        )
        self._api_call_count += 1
        logger.info("Identity Block 抽出完了: %s (%d文字)", character.name, len(identity_block))

        logger.info("C1-F2-MA キャラクター生成完了: %s (variant=%s)", character.name, variant_id)
        return CharacterAsset(
            character_name=character.name,
            variant_id=variant_id,
            front_view=view_paths["front"],
            side_view=view_paths["side"],
            back_view=view_paths["back"],
            identity_block=identity_block,
        )

    async def _generate_character_legacy(
        self,
        character: CharacterSpec,
        output_dir: Path,
        reference_image: Path | None = None,
        variant_id: str = "default",
    ) -> CharacterAsset:
        """旧来方式でキャラクター画像を生成する（後方互換）."""
        output_dir.mkdir(parents=True, exist_ok=True)

        has_user_ref = reference_image is not None
        logger.info("キャラクター画像生成開始: %s (参照画像: %s)", character.name, "あり" if has_user_ref else "なし")

        # 正面画像の生成
        front_path = output_dir / "front.png"
        if has_user_ref:
            prompt = self._prompt_builder.build_character_prompt(character, "front", has_reference=True)
            await self._client.generate_with_reference(prompt, [reference_image], front_path)
        else:
            prompt = self._prompt_builder.build_character_prompt(character, "front", has_reference=False)
            await self._client.generate(prompt, front_path)
        self._api_call_count += 1

        # 横・背面画像の生成（正面画像を参照）
        view_paths: dict[str, Path] = {"front": front_path}
        for view in ["side", "back"]:
            view_path = output_dir / f"{view}.png"
            prompt = self._prompt_builder.build_character_prompt(character, view, has_reference=True)

            ref_images = [front_path]
            if has_user_ref:
                ref_images = [reference_image, front_path]

            await self._client.generate_with_reference(prompt, ref_images, view_path)
            self._api_call_count += 1
            view_paths[view] = view_path

        logger.info("キャラクター画像生成完了: %s (variant=%s)", character.name, variant_id)
        return CharacterAsset(
            character_name=character.name,
            variant_id=variant_id,
            front_view=view_paths["front"],
            side_view=view_paths["side"],
            back_view=view_paths["back"],
        )

    async def _generate_character_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        character: CharacterSpec,
        output_dir: Path,
        reference_image: Path | None = None,
        person_image: Path | None = None,
        clothing_image: Path | None = None,
        variant_id: str = "default",
    ) -> CharacterAsset:
        async with semaphore:
            return await self.generate_character(
                character,
                output_dir,
                reference_image,
                person_image=person_image,
                clothing_image=clothing_image,
                variant_id=variant_id,
            )

    # --- 環境画像生成 ---

    def _load_environment_seeds(self, seeds_path: Path) -> EnvironmentSeeds:
        """YAML シードファイルを読み込む."""
        if not seeds_path.exists():
            msg = f"環境シードファイルが見つかりません: {seeds_path}"
            raise FileNotFoundError(msg)
        data = yaml.safe_load(seeds_path.read_text(encoding="utf-8"))
        return EnvironmentSeeds.model_validate(data)

    async def _generate_environments(
        self,
        env_seeds: EnvironmentSeeds,
        scenes: list[SceneSpec],
        env_reference_dir: Path,
        output_dir: Path,
    ) -> list[EnvironmentAsset]:
        """全環境画像を順次生成する."""
        output_dir.mkdir(parents=True, exist_ok=True)
        results: list[EnvironmentAsset] = []
        for seed in env_seeds.environments:
            env_asset = await self._generate_single_environment(
                seed=seed,
                scenes=scenes,
                env_reference_dir=env_reference_dir,
                output_dir=output_dir,
            )
            results.append(env_asset)
        return results

    async def _generate_single_environment(
        self,
        seed: EnvironmentSeedSpec,
        scenes: list[SceneSpec],
        env_reference_dir: Path,
        output_dir: Path,
    ) -> EnvironmentAsset:
        """1環境画像を生成し EnvironmentAsset を返す."""
        output_path = output_dir / f"scene_{seed.scene_number:02d}.png"

        if seed.source == "reference":
            ref_image_path = env_reference_dir / seed.reference_image
            if not ref_image_path.exists():
                msg = f"環境参照画像が見つかりません: {ref_image_path}"
                raise FileNotFoundError(msg)
            prompt = self._prompt_builder.build_environment_prompt(seed.modification)
            await self._client.generate_with_reference(prompt, [ref_image_path], output_path)
            self._api_call_count += 1
            logger.info("環境画像生成完了 (reference): scene=%d", seed.scene_number)
            return EnvironmentAsset(
                scene_number=seed.scene_number,
                description=seed.description,
                image_path=output_path,
                source_type="reference",
            )

        # source == "generate"
        scene = next((s for s in scenes if s.scene_number == seed.scene_number), None)
        if scene is None:
            msg = f"scene_number={seed.scene_number} に対応する SceneSpec が見つかりません"
            raise ValueError(msg)
        prompt = self._prompt_builder.build_environment_text_prompt(scene.image_prompt)
        await self._client.generate(prompt, output_path)
        self._api_call_count += 1
        logger.info("環境画像生成完了 (generate): scene=%d", seed.scene_number)
        return EnvironmentAsset(
            scene_number=seed.scene_number,
            description=seed.description,
            image_path=output_path,
            source_type="generated",
        )

    # --- ユーティリティ ---

    @staticmethod
    def _determine_mode(mapping: ReferenceMapping) -> str:
        """mapping の状態からモード文字列を判定する."""
        has_any_manual = any(ref.person is not None or ref.clothing is not None for ref in mapping.characters)
        if has_any_manual:
            return "c1f2ma_manual"
        return "c1f2ma_auto"

    def _save_metadata(self, output_dir: Path, mode: str) -> None:
        """メタデータ JSON を保存する."""
        metadata = {
            "generated_at": datetime.now(tz=UTC).isoformat(),
            "model_name": self._client.model_name,
            "mode": mode,
            "total_api_calls": self._api_call_count,
        }
        metadata_path = output_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        logger.info("メタデータを保存: %s", metadata_path)


def _sanitize_filename(name: str) -> str:
    """ファイル名に使用できない文字を置換する."""
    sanitized = re.sub(r"[^\w\s-]", "", name)
    sanitized = re.sub(r"[\s]+", "_", sanitized)
    return sanitized.strip("_").lower() or "unnamed"
