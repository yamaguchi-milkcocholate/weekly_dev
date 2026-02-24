"""Gemini を使った Asset Generator 実装."""

import asyncio
import json
import logging
import re
from datetime import UTC, datetime
from pathlib import Path

from daily_routine.pipeline.base import StepEngine
from daily_routine.schemas.asset import AssetSet, BackgroundAsset, CharacterAsset, PropAsset
from daily_routine.schemas.scenario import CharacterSpec, PropSpec, Scenario, SceneSpec

from .base import AssetGenerator
from .client import GeminiImageClient
from .prompt import PromptBuilder

logger = logging.getLogger(__name__)

# キャラクターの標準ビュー
_CHARACTER_VIEWS = ["front", "side", "back"]

# デフォルト表情バリエーション
_DEFAULT_EXPRESSIONS = ["smile", "serious", "surprised"]

# 並列生成時の同時実行数上限（Gemini API レート制限対策）
_MAX_CONCURRENCY = 3


_ASSET_SET_FILENAME = "asset_set.json"


class GeminiAssetGenerator(StepEngine[Scenario, AssetSet], AssetGenerator):
    """Gemini を使った Asset Generator 実装.

    StepEngine[Scenario, AssetSet] を実装しパイプラインに統合しつつ、
    AssetGenerator の各メソッドも実装する。
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

        # ユーザー参照画像の検出（assets/reference/ にあれば使用）
        reference_dir = output_dir / "reference"
        user_reference_images: dict[str, Path] | None = None
        if reference_dir.exists():
            refs: dict[str, Path] = {}
            for char in input_data.characters:
                for ext in (".png", ".jpg", ".jpeg"):
                    ref_path = reference_dir / f"{char.name}{ext}"
                    if ref_path.exists():
                        refs[char.name] = ref_path
                        break
            if refs:
                user_reference_images = refs

        return await self.generate_assets(
            characters=input_data.characters,
            props=input_data.props,
            scenes=input_data.scenes,
            output_dir=output_dir,
            user_reference_images=user_reference_images,
        )

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

    async def generate_assets(
        self,
        characters: list[CharacterSpec],
        props: list[PropSpec],
        scenes: list[SceneSpec],
        output_dir: Path,
        user_reference_images: dict[str, Path] | None = None,
    ) -> AssetSet:
        """全アセットを生成する.

        生成順序:
        1. キャラクター画像（正面 → 横・背面・表情の順で参照画像活用）
        2. 小物画像（並列生成可能）
        3. 背景画像（並列生成可能）
        """
        self._api_call_count = 0
        user_reference_images = user_reference_images or {}
        mode = "user_reference" if user_reference_images else "prompt_only"
        logger.info("アセット生成を開始 (モード: %s)", mode)

        # ユーザー参照画像の存在チェック
        for name, ref_path in user_reference_images.items():
            if not ref_path.exists():
                msg = f"ユーザー参照画像が見つかりません: {name} -> {ref_path}"
                raise FileNotFoundError(msg)

        # 1. キャラクター画像生成（キャラクター間は並列、ビュー間は順次）
        semaphore = asyncio.Semaphore(_MAX_CONCURRENCY)
        character_tasks = [
            self._generate_character_with_semaphore(
                semaphore,
                character,
                output_dir / "character" / character.name,
                user_reference_images.get(character.name),
            )
            for character in characters
        ]
        character_assets = await asyncio.gather(*character_tasks)

        # 2. 小物画像生成（並列、重複排除）
        seen_props: set[str] = set()
        unique_props: list[PropSpec] = []
        for prop in props:
            if prop.name not in seen_props:
                seen_props.add(prop.name)
                unique_props.append(prop)

        prop_tasks = [
            self._generate_prop_with_semaphore(
                semaphore,
                prop.name,
                prop.image_prompt,
                output_dir / "props",
            )
            for prop in unique_props
        ]
        prop_assets = await asyncio.gather(*prop_tasks)

        # 3. 背景画像生成（並列）
        bg_tasks = [
            self._generate_background_with_semaphore(
                semaphore,
                scene,
                output_dir / "backgrounds",
            )
            for scene in scenes
        ]
        background_assets = await asyncio.gather(*bg_tasks)

        asset_set = AssetSet(
            characters=list(character_assets),
            props=list(prop_assets),
            backgrounds=list(background_assets),
        )

        # メタデータ JSON の保存
        self._save_metadata(output_dir, mode)

        logger.info(
            "アセット生成完了: キャラクター=%d, 小物=%d, 背景=%d, API呼び出し=%d",
            len(asset_set.characters),
            len(asset_set.props),
            len(asset_set.backgrounds),
            self._api_call_count,
        )
        return asset_set

    async def generate_character(
        self,
        character: CharacterSpec,
        output_dir: Path,
        reference_image: Path | None = None,
    ) -> CharacterAsset:
        """1キャラクターのリファレンス画像セットを生成する.

        モードA（reference_image=None）:
        1. 正面画像を生成（プロンプトのみ）
        2. 正面画像を参照画像として横向き画像を生成
        3. 正面画像を参照画像として背面画像を生成
        4. 正面画像を参照画像として各表情バリエーションを生成

        モードB（reference_image指定あり）:
        1. ユーザー画像を参照画像として正面画像を生成
        2. ユーザー画像 + 正面画像を参照画像として横向き画像を生成
        3. ユーザー画像 + 正面画像を参照画像として背面画像を生成
        4. ユーザー画像 + 正面画像を参照画像として各表情バリエーションを生成
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        expressions_dir = output_dir / "expressions"
        expressions_dir.mkdir(parents=True, exist_ok=True)

        has_user_ref = reference_image is not None
        logger.info("キャラクター画像生成開始: %s (参照画像: %s)", character.name, "あり" if has_user_ref else "なし")

        # 正面画像の生成
        front_path = output_dir / "front.png"
        if has_user_ref:
            # モードB: ユーザー参照画像から正面を生成
            prompt = self._prompt_builder.build_character_prompt(character, "front", has_reference=True)
            await self._client.generate_with_reference(prompt, [reference_image], front_path)
        else:
            # モードA: プロンプトのみで正面を生成
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

        # 表情バリエーションの生成
        expressions: dict[str, Path] = {}
        for expression in _DEFAULT_EXPRESSIONS:
            expr_path = expressions_dir / f"{expression}.png"
            prompt = self._prompt_builder.build_expression_prompt(character, expression, has_reference=True)

            ref_images = [front_path]
            if has_user_ref:
                ref_images = [reference_image, front_path]

            await self._client.generate_with_reference(prompt, ref_images, expr_path)
            self._api_call_count += 1
            expressions[expression] = expr_path

        logger.info("キャラクター画像生成完了: %s", character.name)
        return CharacterAsset(
            character_name=character.name,
            front_view=view_paths["front"],
            side_view=view_paths["side"],
            back_view=view_paths["back"],
            expressions=expressions,
        )

    async def generate_prop(
        self,
        name: str,
        description: str,
        output_dir: Path,
    ) -> PropAsset:
        """小物の画像を生成する."""
        output_dir.mkdir(parents=True, exist_ok=True)
        filename = _sanitize_filename(name)
        output_path = output_dir / f"{filename}.png"

        prompt = self._prompt_builder.build_prop_prompt(name, description)
        await self._client.generate(prompt, output_path)
        self._api_call_count += 1

        logger.info("小物画像生成完了: %s", name)
        return PropAsset(name=name, image_path=output_path)

    async def generate_background(
        self,
        scene: SceneSpec,
        output_dir: Path,
    ) -> BackgroundAsset:
        """シーンの背景画像を生成する."""
        output_dir.mkdir(parents=True, exist_ok=True)
        output_path = output_dir / f"scene_{scene.scene_number:02d}.png"

        prompt = self._prompt_builder.build_background_prompt(scene)
        await self._client.generate(prompt, output_path)
        self._api_call_count += 1

        logger.info("背景画像生成完了: scene_%02d", scene.scene_number)
        return BackgroundAsset(
            scene_number=scene.scene_number,
            description=scene.situation,
            image_path=output_path,
        )

    async def _generate_character_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        character: CharacterSpec,
        output_dir: Path,
        reference_image: Path | None,
    ) -> CharacterAsset:
        async with semaphore:
            return await self.generate_character(character, output_dir, reference_image)

    async def _generate_prop_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        name: str,
        image_prompt: str,
        output_dir: Path,
    ) -> PropAsset:
        async with semaphore:
            return await self.generate_prop(name, image_prompt, output_dir)

    async def _generate_background_with_semaphore(
        self,
        semaphore: asyncio.Semaphore,
        scene: SceneSpec,
        output_dir: Path,
    ) -> BackgroundAsset:
        async with semaphore:
            return await self.generate_background(scene, output_dir)

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
