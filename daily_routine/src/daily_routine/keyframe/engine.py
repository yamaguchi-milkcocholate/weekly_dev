"""Runway Gen-4 Image を使ったキーフレーム生成エンジン."""

import logging
from pathlib import Path

from daily_routine.pipeline.base import StepEngine
from daily_routine.schemas.asset import AssetSet, KeyframeAsset
from daily_routine.schemas.pipeline_io import KeyframeInput
from daily_routine.schemas.storyboard import Storyboard
from daily_routine.visual.clients.gen4_image import ImageGenerationRequest, RunwayImageClient

from .base import KeyframeEngineBase

logger = logging.getLogger(__name__)


class RunwayKeyframeEngine(StepEngine[KeyframeInput, AssetSet], KeyframeEngineBase):
    """Runway Gen-4 Image を使ったキーフレーム生成エンジン."""

    def __init__(self, api_key: str = "", gcs_bucket: str = "", image_model: str = "gen4_image_turbo") -> None:
        if api_key and gcs_bucket:
            from daily_routine.utils.uploader import GcsUploader

            uploader = GcsUploader(bucket_name=gcs_bucket)
            self._image_client = RunwayImageClient(api_key=api_key, uploader=uploader, model=image_model)
        else:
            self._image_client = None  # type: ignore[assignment]

    @classmethod
    def from_components(cls, image_client: RunwayImageClient) -> "RunwayKeyframeEngine":
        """テスト用DI: 構築済みクライアントを注入する."""
        instance = cls.__new__(cls)
        instance._image_client = image_client
        return instance

    async def execute(self, input_data: KeyframeInput, project_dir: Path) -> AssetSet:
        """キーフレーム画像を生成する."""
        output_dir = project_dir / "assets" / "keyframes"
        return await self.generate_keyframes(
            storyboard=input_data.storyboard,
            assets=input_data.assets,
            output_dir=output_dir,
        )

    async def generate_keyframes(
        self,
        storyboard: Storyboard,
        assets: AssetSet,
        output_dir: Path,
    ) -> AssetSet:
        """全カットのキーフレーム画像を生成する."""
        output_dir.mkdir(parents=True, exist_ok=True)

        if not assets.characters:
            msg = "キャラクターアセットが存在しません"
            raise ValueError(msg)

        reference_image = assets.characters[0].front_view
        all_cuts = [cut for scene in storyboard.scenes for cut in scene.cuts]
        total_cuts = len(all_cuts)

        keyframes: list[KeyframeAsset] = []
        for i, cut in enumerate(all_cuts, start=1):
            keyframe_path = output_dir / f"{cut.cut_id}.png"

            logger.info("キーフレーム %d/%d (%s) の生成を開始します", i, total_cuts, cut.cut_id)

            request = ImageGenerationRequest(
                prompt=cut.keyframe_prompt,
                reference_images={"char": reference_image},
            )
            result = await self._image_client.generate(request, keyframe_path)

            keyframes.append(
                KeyframeAsset(
                    scene_number=cut.scene_number,
                    image_path=result.image_path,
                    prompt=cut.keyframe_prompt,
                )
            )

            logger.info(
                "キーフレーム %d/%d 完了 ($%.2f)",
                i,
                total_cuts,
                result.cost_usd or 0,
            )

        return assets.model_copy(update={"keyframes": keyframes})

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
