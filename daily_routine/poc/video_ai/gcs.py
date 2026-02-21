"""GCSへのリファレンス画像アップロードユーティリティ.

Usage:
    # 単体実行: reference/ 内の画像をGCSにアップロードし公開URLを表示
    uv run python poc/video_ai/gcs.py --bucket YOUR_BUCKET

    # プログラムから利用
    from gcs import upload_reference_image
    url = upload_reference_image(Path("reference/front.png"), "my-bucket")
"""

import argparse
import logging
from pathlib import Path

from google.cloud import storage

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(name)s] %(levelname)s: %(message)s")
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent
GCS_PREFIX = "poc/video_ai/reference"


def upload_reference_image(local_path: Path, bucket_name: str, prefix: str = GCS_PREFIX) -> str:
    """ローカル画像をGCSにアップロードし、公開URLを返す."""
    client = storage.Client()
    bucket = client.bucket(bucket_name)

    blob_name = f"{prefix}/{local_path.name}"
    blob = bucket.blob(blob_name)
    blob.upload_from_filename(str(local_path))
    blob.make_public()

    public_url = blob.public_url
    logger.info("Uploaded %s -> %s", local_path, public_url)
    return public_url


def upload_all_references(bucket_name: str, reference_dir: Path | None = None) -> dict[str, str]:
    """reference/ ディレクトリ内の全PNG画像をアップロードし、{ファイル名: URL} を返す."""
    ref_dir = reference_dir or (BASE_DIR / "reference")
    images = sorted(ref_dir.glob("*.png"))
    if not images:
        raise FileNotFoundError(f"No PNG images found in {ref_dir}")

    urls: dict[str, str] = {}
    for img in images:
        url = upload_reference_image(img, bucket_name)
        urls[img.name] = url

    logger.info("Uploaded %d images to gs://%s/%s/", len(urls), bucket_name, GCS_PREFIX)
    return urls


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="リファレンス画像をGCSにアップロード")
    parser.add_argument("--bucket", required=True, help="GCSバケット名")
    parser.add_argument("--reference-dir", default=str(BASE_DIR / "reference"), help="リファレンス画像ディレクトリ")
    args = parser.parse_args()

    urls = upload_all_references(args.bucket, Path(args.reference_dir))
    print("\n=== アップロード結果 ===")
    for name, url in urls.items():
        print(f"  {name}: {url}")
