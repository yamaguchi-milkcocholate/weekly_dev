"""全動画生成AIの一括実行スクリプト.

Usage:
    # GCSバケット指定で自動アップロード（推奨）
    uv run python poc/video_ai/run_generation.py \
        --gcs-bucket YOUR_BUCKET \
        [--ais veo,kling,luma,runway] \
        [--veo-project-id YOUR_GCP_PROJECT]

    # 既にアップロード済みの画像URLを直接指定
    uv run python poc/video_ai/run_generation.py \
        --image-url https://storage.googleapis.com/YOUR_BUCKET/front.png \
        [--ais veo,kling,luma,runway] \
        [--veo-project-id YOUR_GCP_PROJECT]
"""

import argparse
import asyncio
import json
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from clients import (
    KlingClient,
    LumaClient,
    RunwayClient,
    VeoClient,
    VideoGenerationRequest,
    VideoGenerationResult,
    VideoGeneratorClient,
)
from gcs import upload_reference_image

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

PROMPT = (
    "A young Japanese office lady walking through a modern city street, "
    "carrying a coffee cup, natural daylight, cinematic lighting, "
    "vertical video 9:16 aspect ratio"
)

BASE_DIR = Path(__file__).resolve().parent


def build_clients(ais: list[str], veo_project_id: str | None) -> dict[str, VideoGeneratorClient]:
    clients: dict[str, VideoGeneratorClient] = {}
    for ai in ais:
        match ai:
            case "veo":
                if not veo_project_id:
                    logger.warning("Skipping Veo: --veo-project-id not specified")
                    continue
                clients["veo"] = VeoClient(project_id=veo_project_id, output_dir=str(BASE_DIR / "generated" / "veo"))
            case "kling":
                clients["kling"] = KlingClient(output_dir=str(BASE_DIR / "generated" / "kling"))
            case "luma":
                clients["luma"] = LumaClient(output_dir=str(BASE_DIR / "generated" / "luma"))
            case "runway":
                clients["runway"] = RunwayClient(output_dir=str(BASE_DIR / "generated" / "runway"))
            case _:
                logger.warning("Unknown AI: %s (skipping)", ai)
    return clients


async def run_single(name: str, client: VideoGeneratorClient, request: VideoGenerationRequest) -> dict:
    logger.info("=== %s: generation started ===", name)
    try:
        result: VideoGenerationResult = await client.generate(request)
        logger.info("=== %s: done in %.1fs -> %s ===", name, result.generation_time_sec, result.video_path)
        return {"ai": name, "status": "success", "result": result.model_dump(mode="json")}
    except Exception as e:
        logger.error("=== %s: FAILED — %s ===", name, e)
        return {"ai": name, "status": "error", "error": str(e)}


def resolve_image_url(image_url: str | None, gcs_bucket: str | None, reference_image: Path) -> str:
    """画像URLを解決する。GCSバケット指定時はアップロードして公開URLを取得する."""
    if image_url:
        return image_url
    if gcs_bucket:
        if not reference_image.exists():
            raise FileNotFoundError(f"Reference image not found: {reference_image}")
        logger.info("Uploading %s to GCS bucket '%s'...", reference_image, gcs_bucket)
        return upload_reference_image(reference_image, gcs_bucket)
    raise ValueError("Either --image-url or --gcs-bucket must be specified")


async def main(
    ais: list[str],
    veo_project_id: str | None,
    reference_image: Path,
    image_url: str | None = None,
    gcs_bucket: str | None = None,
) -> None:
    url = resolve_image_url(image_url, gcs_bucket, reference_image)
    logger.info("Image URL: %s", url)

    clients = build_clients(ais, veo_project_id)
    if not clients:
        logger.error("No clients configured. Check API keys and arguments.")
        return

    request = VideoGenerationRequest(
        reference_image_path=reference_image,
        prompt=PROMPT,
        duration_sec=5,
        aspect_ratio="9:16",
    )
    request_with_url = request.model_copy(update={"metadata": {"image_url": url}})

    # 逐次実行（API同時呼び出しでレート制限を避ける）
    results = []
    for name, client in clients.items():
        result = await run_single(name, client, request_with_url if name != "veo" else request)
        results.append(result)

    # 結果サマリーを保存
    summary_path = BASE_DIR / "generated" / "generation_summary.json"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    logger.info("Summary saved: %s", summary_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="動画生成AI一括実行")
    url_group = parser.add_mutually_exclusive_group(required=True)
    url_group.add_argument("--image-url", help="リファレンス画像の公開URL (既にホスティング済みの場合)")
    url_group.add_argument("--gcs-bucket", help="GCSバケット名 (ローカル画像を自動アップロード)")
    parser.add_argument("--reference-image", default=str(BASE_DIR / "reference" / "front.png"), help="ローカルのリファレンス画像パス")
    parser.add_argument("--ais", default="veo,kling,luma,runway", help="実行するAI (カンマ区切り)")
    parser.add_argument("--veo-project-id", default=None, help="GCPプロジェクトID (Veo用)")
    args = parser.parse_args()

    asyncio.run(main(
        ais=[a.strip() for a in args.ais.split(",")],
        veo_project_id=args.veo_project_id,
        reference_image=Path(args.reference_image),
        image_url=args.image_url,
        gcs_bucket=args.gcs_bucket,
    ))
