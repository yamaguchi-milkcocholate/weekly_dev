"""PoC 9: V2Vスタイル転写スクリプト.

Blenderウォークスルー動画をLuma Modify / Runway Gen-4 Alephに送り、
スタイル転写（re-skinning + 生活感追加）を検証する。

Usage:
    # GCSに動画をアップロード後、Luma V2Vを実行
    uv run python poc/3dcg_poc9/run_v2v.py \
        --video poc/3dcg_poc9/output/walkthrough_cam1_cam2.mp4 \
        --gcs-bucket YOUR_BUCKET \
        --service luma \
        --prompt "Transform to photorealistic interior..." \
        --output-dir poc/3dcg_poc9/output/v2v_luma

    # Runway V2Vを実行
    uv run python poc/3dcg_poc9/run_v2v.py \
        --video poc/3dcg_poc9/output/walkthrough_cam1_cam2.mp4 \
        --gcs-bucket YOUR_BUCKET \
        --service runway \
        --prompt "Transform to photorealistic interior..." \
        --output-dir poc/3dcg_poc9/output/v2v_runway

    # スタイル参照画像を指定（Luma: first_frame, Runway: references）
    uv run python poc/3dcg_poc9/run_v2v.py \
        --video poc/3dcg_poc9/output/walkthrough_cam1_cam2.mp4 \
        --gcs-bucket YOUR_BUCKET \
        --service luma \
        --style-image poc/3dcg_poc8/output/カメラ1.png \
        --prompt "..." \
        --output-dir poc/3dcg_poc9/output/v2v_luma
"""

import argparse
import asyncio
import logging
import os
import subprocess
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

GCS_PREFIX = "poc/3dcg_poc9"


def upload_to_gcs(local_path: Path, bucket_name: str) -> str:
    """ローカルファイルをGCSにアップロードし、公開URLを返す."""
    gcs_dest = f"gs://{bucket_name}/{GCS_PREFIX}/{local_path.name}"
    cmd = ["gcloud", "storage", "cp", str(local_path), gcs_dest]
    logger.info("$ %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"GCSアップロード失敗: {result.stderr.strip()}")
    public_url = f"https://storage.googleapis.com/{bucket_name}/{GCS_PREFIX}/{local_path.name}"
    logger.info("アップロード完了: %s", public_url)
    return public_url


# --- Luma V2V ---

async def run_luma_v2v(
    video_url: str,
    prompt: str,
    output_dir: Path,
    mode: str = "adhere_1",
    style_image_url: str | None = None,
) -> Path:
    """Luma Modify Video APIでV2Vスタイル転写を実行する."""
    api_key = os.environ["DAILY_ROUTINE_API_KEY_LUMA"]
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    base_url = "https://api.lumalabs.ai/dream-machine/v1"

    payload: dict = {
        "prompt": prompt,
        "model": "ray-2",
        "mode": mode,
        "media": {"url": video_url},
    }
    if style_image_url:
        payload["first_frame"] = {"url": style_image_url}

    start = time.time()
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        resp = await client.post(f"{base_url}/generations/video/modify", json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.error("Luma API エラー: status=%d, body=%s", resp.status_code, resp.text)
        resp.raise_for_status()
        generation_id = resp.json()["id"]
        logger.info("Luma V2V 開始: id=%s, mode=%s", generation_id, mode)

        # ポーリング
        video_download_url = None
        for _ in range(120):
            await asyncio.sleep(5)
            resp = await client.get(f"{base_url}/generations/{generation_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            state = data["state"]
            if state == "completed":
                video_download_url = data["assets"]["video"]
                break
            if state == "failed":
                raise RuntimeError(f"Luma V2V 失敗: {data.get('failure_reason')}")
            logger.debug("Luma polling... state=%s", state)

        if not video_download_url:
            raise TimeoutError("Luma V2V タイムアウト（10分）")

    elapsed = time.time() - start
    logger.info("Luma V2V 完了: %.1f秒", elapsed)

    # 動画ダウンロード
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"luma_{mode}.mp4"
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        resp = await client.get(video_download_url)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)

    logger.info("保存: %s", output_path)
    return output_path


# --- Runway V2V ---

async def run_runway_v2v(
    video_url: str,
    prompt: str,
    output_dir: Path,
    model: str = "gen4_aleph",
    style_image_url: str | None = None,
) -> Path:
    """Runway Video-to-Video APIでV2Vスタイル転写を実行する."""
    api_key = os.environ["DAILY_ROUTINE_API_KEY_RUNWAY"]
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Runway-Version": "2024-11-06",
    }
    base_url = "https://api.dev.runwayml.com/v1"

    payload: dict = {
        "model": model,
        "videoUri": video_url,
        "promptText": prompt,
    }
    if style_image_url:
        payload["references"] = [{"uri": style_image_url, "type": "image"}]

    start = time.time()
    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        resp = await client.post(f"{base_url}/video_to_video", json=payload, headers=headers)
        if resp.status_code >= 400:
            logger.error("Runway API エラー: status=%d, body=%s", resp.status_code, resp.text)
        resp.raise_for_status()
        task_id = resp.json()["id"]
        logger.info("Runway V2V 開始: id=%s, model=%s", task_id, model)

        # ポーリング
        video_download_url = None
        for _ in range(120):
            await asyncio.sleep(5)
            resp = await client.get(f"{base_url}/tasks/{task_id}", headers=headers)
            resp.raise_for_status()
            data = resp.json()
            status = data["status"]
            if status == "SUCCEEDED":
                video_download_url = data["output"][0]
                break
            if status == "FAILED":
                raise RuntimeError(f"Runway V2V 失敗: {data.get('failure')}")
            logger.debug("Runway polling... status=%s", status)

        if not video_download_url:
            raise TimeoutError("Runway V2V タイムアウト（10分）")

    elapsed = time.time() - start
    logger.info("Runway V2V 完了: %.1f秒", elapsed)

    # 動画ダウンロード
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"runway_{model}.mp4"
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        resp = await client.get(video_download_url)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)

    logger.info("保存: %s", output_path)
    return output_path


async def main() -> None:
    load_dotenv()
    parser = argparse.ArgumentParser(description="PoC 9: V2Vスタイル転写")
    parser.add_argument("--video", type=Path, required=True, help="入力動画パス")
    parser.add_argument("--video-url", type=str, default=None, help="入力動画URL（GCSアップロード済みの場合）")
    parser.add_argument("--gcs-bucket", type=str, default=None, help="GCSバケット名（動画をアップロード）")
    parser.add_argument("--service", choices=["luma", "runway"], required=True, help="V2Vサービス")
    parser.add_argument("--prompt", type=str, required=True, help="スタイル転写プロンプト")
    parser.add_argument("--style-image", type=Path, default=None, help="スタイル参照画像パス")
    parser.add_argument("--style-image-url", type=str, default=None, help="スタイル参照画像URL")
    parser.add_argument("--mode", type=str, default="adhere_1", help="Lumaモード（adhere_1〜3, flex_1〜3）")
    parser.add_argument("--model", type=str, default="gen4_aleph", help="Runwayモデル")
    parser.add_argument("--output-dir", type=Path, required=True, help="出力ディレクトリ")
    args = parser.parse_args()

    # 動画URL
    video_url = args.video_url
    if not video_url:
        if not args.gcs_bucket:
            raise ValueError("--video-url または --gcs-bucket が必要です")
        video_url = upload_to_gcs(args.video, args.gcs_bucket)

    # スタイル参照画像URL
    style_image_url = args.style_image_url
    if args.style_image and not style_image_url:
        if not args.gcs_bucket:
            raise ValueError("スタイル画像のアップロードに --gcs-bucket が必要です")
        style_image_url = upload_to_gcs(args.style_image, args.gcs_bucket)

    if args.service == "luma":
        await run_luma_v2v(video_url, args.prompt, args.output_dir, mode=args.mode, style_image_url=style_image_url)
    else:
        await run_runway_v2v(video_url, args.prompt, args.output_dir, model=args.model, style_image_url=style_image_url)


if __name__ == "__main__":
    asyncio.run(main())
