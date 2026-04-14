"""Visual Core のデフォルト実装."""

import json
import logging
from datetime import datetime
from pathlib import Path

from daily_routine.config.manager import GlobalConfig
from daily_routine.pipeline.base import StepEngine
from daily_routine.schemas.asset import AssetSet, KeyframeAsset
from daily_routine.schemas.pipeline_io import VisualInput
from daily_routine.schemas.storyboard import Storyboard
from daily_routine.schemas.visual import VideoClip, VideoClipSet
from daily_routine.utils.uploader import GcsUploader
from daily_routine.visual.base import VisualEngine
from daily_routine.visual.clients.base import VideoGenerationRequest
from daily_routine.visual.clients.runway import RunwayClient

logger = logging.getLogger(__name__)


class DefaultVisualEngine(StepEngine[VisualInput, VideoClipSet], VisualEngine):
    """Visual Core のデフォルト実装."""

    def __init__(
        self,
        api_key: str = "",
        gcs_bucket: str = "",
        video_model: str = "gen4_turbo",
        provider_name: str = "runway",
    ) -> None:
        if api_key and gcs_bucket:
            uploader = GcsUploader(bucket_name=gcs_bucket)
            self._client = RunwayClient(api_key=api_key, uploader=uploader, model=video_model)
        else:
            self._client = None  # type: ignore[assignment]
        self._provider_name = provider_name

    @classmethod
    def from_components(cls, client: "RunwayClient", provider_name: str = "runway") -> "DefaultVisualEngine":
        """テスト用DI: 構築済みクライアントを注入する."""
        instance = cls.__new__(cls)
        instance._client = client
        instance._provider_name = provider_name
        return instance

    async def execute(self, input_data: VisualInput, project_dir: Path) -> VideoClipSet:
        """VisualInput から動画クリップを生成する."""
        output_dir = project_dir / "clips"
        return await self.generate_clips(input_data.storyboard, input_data.assets, output_dir)

    def save_output(self, project_dir: Path, output: VideoClipSet) -> None:
        """VideoClipSet を JSON として永続化する."""
        clips_dir = project_dir / "clips"
        clips_dir.mkdir(parents=True, exist_ok=True)
        (clips_dir / "clip_set.json").write_text(output.model_dump_json(indent=2), encoding="utf-8")

    def load_output(self, project_dir: Path) -> VideoClipSet:
        """永続化済みの VideoClipSet を読み込む."""
        path = project_dir / "clips" / "clip_set.json"
        if not path.exists():
            msg = f"VideoClipSet ファイルが見つかりません: {path}"
            raise FileNotFoundError(msg)
        return VideoClipSet.model_validate_json(path.read_text(encoding="utf-8"))

    async def generate_clips(
        self,
        storyboard: Storyboard,
        assets: AssetSet,
        output_dir: Path,
    ) -> VideoClipSet:
        """全カットの動画クリップを生成する.

        処理フロー:
        1. Storyboard から全カットを展開
        2. 各カットで generate_cut_clip を順次呼び出し
        3. VideoClipSet を構築して返す
        """
        output_dir.mkdir(parents=True, exist_ok=True)

        all_cuts = [cut for scene in storyboard.scenes for cut in scene.cuts]
        total_cuts = len(all_cuts)
        clips: list[VideoClip] = []

        for i, cut in enumerate(all_cuts, start=1):
            output_path = output_dir / f"{cut.cut_id}.mp4"

            # キーフレーム画像を取得（KEYFRAME ステップで生成済み）
            keyframe = self._find_keyframe(assets, cut.cut_id, cut.scene_number)

            logger.info("カット %d/%d (%s) の動画生成を開始します", i, total_cuts, cut.cut_id)

            clip_path = await self.generate_cut_clip(
                cut_id=cut.cut_id,
                prompt=cut.motion_prompt,
                reference_image=keyframe.image_path,
                duration_sec=int(cut.duration_sec),
                output_path=output_path,
            )

            result = self._last_result

            clips.append(
                VideoClip(
                    scene_number=cut.scene_number,
                    clip_path=clip_path,
                    duration_sec=cut.duration_sec,
                    model_name=result.model_name,
                    cost_usd=result.cost_usd,
                    generation_time_sec=result.generation_time_sec,
                )
            )

            logger.info(
                "カット %d/%d 完了 (%.1f秒, $%.2f)",
                i,
                total_cuts,
                result.generation_time_sec,
                result.cost_usd or 0,
            )

        total_cost = sum(c.cost_usd for c in clips if c.cost_usd is not None)
        clip_set = VideoClipSet(
            clips=clips,
            total_cost_usd=total_cost,
            provider=self._provider_name,
        )

        # metadata.json を保存
        self._save_metadata(output_dir, clip_set, storyboard)

        return clip_set

    async def generate_cut_clip(
        self,
        cut_id: str,
        prompt: str,
        reference_image: Path,
        duration_sec: int,
        output_path: Path,
    ) -> Path:
        """単一カットの動画クリップを生成する."""
        if not reference_image.exists():
            msg = f"リファレンス画像が存在しません: {reference_image}"
            raise FileNotFoundError(msg)

        request = VideoGenerationRequest(
            reference_image_path=reference_image,
            prompt=prompt,
            duration_sec=duration_sec,
            aspect_ratio="9:16",
        )

        result = await self._client.generate(request, output_path)
        self._last_result = result
        return result.video_path

    # --- アイテム単位実行 ---

    @property
    def supports_items(self) -> bool:
        """アイテム単位実行に対応する."""
        return True

    def list_items(self, input_data: VisualInput, project_dir: Path) -> list[str]:
        """全カットIDをアイテムIDとして返す."""
        return [cut.cut_id for scene in input_data.storyboard.scenes for cut in scene.cuts]

    async def execute_item(self, item_id: str, input_data: VisualInput, project_dir: Path) -> None:
        """指定 cut_id の動画クリップ1本を生成し、VideoClipSet に追記保存する."""
        output_dir = project_dir / "clips"
        output_dir.mkdir(parents=True, exist_ok=True)

        # 既存の VideoClipSet を読み込み（なければ空で作成）
        try:
            clip_set = self.load_output(project_dir)
        except FileNotFoundError:
            clip_set = VideoClipSet(clips=[], total_cost_usd=0.0, provider=self._provider_name)

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

        keyframe = self._find_keyframe(input_data.assets, target_cut.cut_id, target_cut.scene_number)
        output_path = output_dir / f"{target_cut.cut_id}.mp4"

        clip_path = await self.generate_cut_clip(
            cut_id=target_cut.cut_id,
            prompt=target_cut.motion_prompt,
            reference_image=keyframe.image_path,
            duration_sec=int(target_cut.duration_sec),
            output_path=output_path,
        )

        result = self._last_result

        new_clip = VideoClip(
            scene_number=target_cut.scene_number,
            clip_path=clip_path,
            duration_sec=target_cut.duration_sec,
            model_name=result.model_name,
            cost_usd=result.cost_usd,
            generation_time_sec=result.generation_time_sec,
        )

        # 既存の同一 cut_id のクリップを置換、なければ追加
        replaced = False
        for i, clip in enumerate(clip_set.clips):
            if clip.clip_path.stem == item_id:
                clip_set.clips[i] = new_clip
                replaced = True
                break
        if not replaced:
            clip_set.clips.append(new_clip)

        clip_set.total_cost_usd = sum(c.cost_usd for c in clip_set.clips if c.cost_usd is not None)
        self.save_output(project_dir, clip_set)
        logger.info("クリップ '%s' を生成・保存しました", item_id)

    @staticmethod
    def _find_keyframe(assets: AssetSet, cut_id: str, scene_number: int) -> KeyframeAsset:
        """AssetSetからキーフレームを取得する（cut_id 優先、scene_number フォールバック）."""
        for kf in assets.keyframes:
            if kf.cut_id and kf.cut_id == cut_id:
                return kf
        for kf in assets.keyframes:
            if kf.scene_number == scene_number:
                return kf
        msg = f"キーフレーム画像が見つかりません: cut_id={cut_id}, scene_{scene_number}"
        raise FileNotFoundError(msg)

    def _save_metadata(self, output_dir: Path, clip_set: VideoClipSet, storyboard: Storyboard) -> None:
        """メタデータJSONを保存する."""
        metadata = {
            "provider": clip_set.provider,
            "model_name": clip_set.clips[0].model_name if clip_set.clips else "",
            "total_cuts": len(clip_set.clips),
            "total_cost_usd": clip_set.total_cost_usd,
            "total_generation_time_sec": sum(
                c.generation_time_sec for c in clip_set.clips if c.generation_time_sec is not None
            ),
            "generated_at": datetime.now().isoformat(timespec="seconds"),
        }
        metadata_path = output_dir / "metadata.json"
        metadata_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2))
        logger.info("メタデータを保存しました: %s", metadata_path)


def create_visual_engine(config: GlobalConfig) -> DefaultVisualEngine:
    """設定に基づいてVisualEngineを構築する.

    Args:
        config: グローバル設定

    Returns:
        プロバイダに応じたVisualEngineインスタンス

    Raises:
        ValueError: 不明なプロバイダ、または必要な設定が不足
    """
    provider = config.visual.provider

    if provider == "runway":
        api_key = config.api_keys.runway
        if not api_key:
            msg = "Runway APIキーが設定されていません（環境変数 DAILY_ROUTINE_API_KEY_RUNWAY）"
            raise ValueError(msg)

        gcs_bucket = config.visual.runway.gcs_bucket
        if not gcs_bucket:
            msg = "GCSバケット名が設定されていません（visual.runway.gcs_bucket）"
            raise ValueError(msg)

        return DefaultVisualEngine(
            api_key=api_key,
            gcs_bucket=gcs_bucket,
            video_model=config.visual.runway.video_model,
            provider_name="runway",
        )

    msg = f"不明な動画生成プロバイダです: {provider}"
    raise ValueError(msg)
