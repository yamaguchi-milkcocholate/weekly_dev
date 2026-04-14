"""Kling V3 Omni V2Vフォトリアル動画変換スクリプト.

カメラカット動画（3Dレンダリング）をKling V3 Omni V2V APIでフォトリアルに変換する。

Usage:
    uv run python .claude/skills/floor_plan_to_video_sub_photoreal/scripts/run_kling_v2v.py \
        --video input/cut_living.mp4 \
        --gcs-bucket my-bucket \
        --prompt "Real estate listing video of @Video1..." \
        --output-dir output

    # スタイル参照画像付き
    uv run python .claude/skills/floor_plan_to_video_sub_photoreal/scripts/run_kling_v2v.py \
        --video input/cut_living.mp4 \
        --gcs-bucket my-bucket \
        --prompt "Real estate listing video of @Video1, styled after @Image1..." \
        --style-image input/style_ref.png \
        --output-dir output
"""

import argparse
import asyncio
import json
import logging
import os
import subprocess
import time
from pathlib import Path

import httpx
import jwt
from dotenv import load_dotenv


def _find_dotenv() -> Path | None:
    """親ディレクトリを最大10階層さかのぼって.envを探す."""
    d = Path(__file__).resolve().parent
    for _ in range(10):
        if (d / ".env").exists():
            return d / ".env"
        if d.parent == d:
            break
        d = d.parent
    return None

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_URL = "https://api-singapore.klingai.com/v1"
TOKEN_EXPIRE_SECONDS = 1800
CLOCK_SKEW_SECONDS = 5
POLL_INTERVAL = 5
MAX_POLL_COUNT = 120


def generate_jwt(access_key: str, secret_key: str) -> str:
    """Access KeyとSecret KeyからJWTトークンを生成する."""
    now = int(time.time())
    headers = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "iss": access_key,
        "exp": now + TOKEN_EXPIRE_SECONDS,
        "nbf": now - CLOCK_SKEW_SECONDS,
    }
    return jwt.encode(payload, secret_key, headers=headers)


def upload_to_gcs(local_path: Path, bucket_name: str, prefix: str = "v2v") -> str:
    """ローカルファイルをGCSにアップロードし、公開URLを返す."""
    gcs_dest = f"gs://{bucket_name}/{prefix}/{local_path.name}"
    cmd = ["gcloud", "storage", "cp", str(local_path), gcs_dest]
    logger.info("$ %s", " ".join(cmd))
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"GCSアップロード失敗: {result.stderr.strip()}")
    public_url = f"https://storage.googleapis.com/{bucket_name}/{prefix}/{local_path.name}"
    logger.info("アップロード完了: %s", public_url)
    return public_url


async def run_v2v(
    video_url: str,
    prompt: str,
    output_dir: Path,
    *,
    negative_prompt: str = "",
    style_image_url: str | None = None,
    cfg_scale: float = 0.5,
    duration: str = "5",
    aspect_ratio: str = "auto",
) -> dict:
    """Kling V3 Omni V2V APIを実行し、フォトリアル動画を生成する."""
    access_key = os.environ["DAILY_ROUTINE_API_KEY_KLING_AK"]
    secret_key = os.environ["DAILY_ROUTINE_API_KEY_KLING_SK"]
    token = generate_jwt(access_key, secret_key)
    auth_headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    payload: dict = {
        "model_name": "kling-v3-omni",
        "prompt": prompt,
        "video_list": [
            {
                "video_url": video_url,
                "refer_type": "base",
                "keep_original_sound": "no",
            }
        ],
        "cfg_scale": cfg_scale,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "mode": "pro",
    }
    if negative_prompt:
        payload["negative_prompt"] = negative_prompt
    if style_image_url:
        payload["image_list"] = [{"image_url": style_image_url}]

    start = time.time()

    async with httpx.AsyncClient(timeout=httpx.Timeout(600.0)) as client:
        # V2V生成リクエスト
        resp = await client.post(f"{BASE_URL}/videos/omni-video", json=payload, headers=auth_headers)
        if resp.status_code >= 400:
            logger.error("Kling API エラー: status=%d, body=%s", resp.status_code, resp.text)
        resp.raise_for_status()
        task_id = resp.json()["data"]["task_id"]
        logger.info("Kling V2V 開始: task_id=%s", task_id)

        # ポーリング
        video_download_url = None
        for i in range(MAX_POLL_COUNT):
            await asyncio.sleep(POLL_INTERVAL)
            # トークン再生成（長時間ポーリング対策）
            if i % 60 == 59:
                token = generate_jwt(access_key, secret_key)
                auth_headers["Authorization"] = f"Bearer {token}"

            resp = await client.get(f"{BASE_URL}/videos/omni-video/{task_id}", headers=auth_headers)
            resp.raise_for_status()
            data = resp.json()["data"]
            status = data["task_status"]

            if status == "succeed":
                video_download_url = data["task_result"]["videos"][0]["url"]
                break
            if status == "failed":
                raise RuntimeError(f"Kling V2V 失敗: {data.get('task_status_msg')}")
            logger.debug("ポーリング中... status=%s (%d/%d)", status, i + 1, MAX_POLL_COUNT)

        if not video_download_url:
            raise TimeoutError("Kling V2V タイムアウト（10分）")

    elapsed = time.time() - start
    logger.info("Kling V2V 完了: %.1f秒", elapsed)

    # 動画ダウンロード
    output_dir.mkdir(parents=True, exist_ok=True)
    input_video_url = payload["video_list"][0]["video_url"]
    output_path = output_dir / f"{Path(input_video_url).stem}_photorealistic.mp4"
    async with httpx.AsyncClient(timeout=httpx.Timeout(120.0)) as client:
        resp = await client.get(video_download_url)
        resp.raise_for_status()
        output_path.write_bytes(resp.content)

    logger.info("保存: %s", output_path)

    # 実行ログ
    duration_sec = int(duration)
    cost_usd = duration_sec * 0.168  # Professional 1080p
    execution_log = {
        "task_id": task_id,
        "video_url": input_video_url,
        "style_image_url": style_image_url,
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "refer_type": "base",
        "cfg_scale": cfg_scale,
        "duration": duration,
        "aspect_ratio": aspect_ratio,
        "elapsed_seconds": round(elapsed, 1),
        "estimated_cost_usd": round(cost_usd, 3),
        "output_path": str(output_path),
    }
    log_path = output_dir / "execution_log.json"
    log_path.write_text(json.dumps(execution_log, ensure_ascii=False, indent=2))
    logger.info("実行ログ: %s", log_path)

    return execution_log


async def main() -> None:
    load_dotenv(dotenv_path=_find_dotenv())
    parser = argparse.ArgumentParser(description="Kling V3 Omni V2V フォトリアル変換")
    parser.add_argument("--video", type=Path, required=True, help="入力動画パス")
    parser.add_argument("--video-url", type=str, default=None, help="入力動画URL（GCSアップロード済みの場合）")
    parser.add_argument("--gcs-bucket", type=str, default=None, help="GCSバケット名")
    parser.add_argument("--gcs-prefix", type=str, default="v2v", help="GCSアップロード先のprefix")
    parser.add_argument("--prompt", type=str, required=True, help="V2Vプロンプト")
    parser.add_argument("--negative-prompt", type=str, default="", help="negative prompt")
    parser.add_argument("--style-image", type=Path, default=None, help="スタイル参照画像パス")
    parser.add_argument("--style-image-url", type=str, default=None, help="スタイル参照画像URL")
    parser.add_argument("--cfg-scale", type=float, default=0.5, help="cfg_scale (0-1)")
    parser.add_argument("--duration", type=str, default="5", help="出力秒数 (3-15)")
    parser.add_argument("--aspect-ratio", type=str, default="auto", help="アスペクト比")
    parser.add_argument("--output-dir", type=Path, required=True, help="出力ディレクトリ")
    args = parser.parse_args()

    # 動画URL
    video_url = args.video_url
    if not video_url:
        if not args.gcs_bucket:
            raise ValueError("--video-url または --gcs-bucket が必要です")
        if not args.video.exists():
            raise FileNotFoundError(f"動画ファイルが見つかりません: {args.video}")
        video_url = upload_to_gcs(args.video, args.gcs_bucket, prefix=args.gcs_prefix)

    # スタイル参照画像URL
    style_image_url = args.style_image_url
    if args.style_image and not style_image_url:
        if not args.gcs_bucket:
            raise ValueError("スタイル画像のアップロードに --gcs-bucket が必要です")
        if not args.style_image.exists():
            raise FileNotFoundError(f"スタイル画像が見つかりません: {args.style_image}")
        style_image_url = upload_to_gcs(args.style_image, args.gcs_bucket, prefix=args.gcs_prefix)

    await run_v2v(
        video_url=video_url,
        prompt=args.prompt,
        output_dir=args.output_dir,
        negative_prompt=args.negative_prompt,
        style_image_url=style_image_url,
        cfg_scale=args.cfg_scale,
        duration=args.duration,
        aspect_ratio=args.aspect_ratio,
    )


if __name__ == "__main__":
    asyncio.run(main())
