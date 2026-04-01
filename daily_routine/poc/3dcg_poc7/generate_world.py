"""World Labs APIでマルチ画像からワールドを生成する."""

import json
import logging
import os
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# プロジェクトルートの.envを読み込み
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

API_KEY = os.environ["DAILY_ROUTINE_API_KEY_WORLD_LABS"]
BASE_URL = "https://api.worldlabs.ai/marble/v1"
HEADERS = {
    "WLT-Api-Key": API_KEY,
    "Content-Type": "application/json",
}

INPUT_DIR = Path(__file__).parent / "input"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# カメラ→azimuthマッピング（Blenderのカメラ配置に基づく）
CAMERA_AZIMUTH_MAP = {
    "カメラ1.png": 0,    # front: 廊下→デスク方面
    "カメラ2.png": 45,   # front-right: デスク＋寝室
    "カメラ3.png": 90,   # right: 寝室クローズアップ
    "カメラ4.png": 180,  # back: ダイニング＋クローゼット方面
    "カメラ5.png": 225,  # back-left: 俯瞰気味の全体像
    # カメラ6は真上からのトップビューなので除外
}


def upload_image(client: httpx.Client, file_path: Path) -> str:
    """画像をWorld Labsにアップロードし、media_asset_idを返す."""
    logger.info("アップロード準備: %s", file_path.name)

    # Step 1: 署名付きURL取得
    resp = client.post(
        f"{BASE_URL}/media-assets:prepare_upload",
        headers=HEADERS,
        json={
            "file_name": file_path.name,
            "content_type": "image/png",
            "kind": "image",
        },
    )
    resp.raise_for_status()
    data = resp.json()

    media_asset_id = data["media_asset"]["media_asset_id"]
    upload_url = data["upload_info"]["upload_url"]
    required_headers = data["upload_info"].get("required_headers", {})

    # Step 2: 画像をアップロード
    logger.info("アップロード中: %s → %s", file_path.name, media_asset_id)
    with open(file_path, "rb") as f:
        upload_resp = client.put(
            upload_url,
            headers=required_headers,
            content=f.read(),
        )
    upload_resp.raise_for_status()
    logger.info("アップロード完了: %s", file_path.name)

    return media_asset_id


def generate_world(
    client: httpx.Client,
    image_assets: list[dict],
    *,
    model: str = "Marble 0.1-mini",
    text_prompt: str = "",
) -> str:
    """マルチ画像からワールドを生成し、operation_idを返す."""
    multi_image_prompt = [
        {
            "azimuth": asset["azimuth"],
            "content": {
                "source": "media_asset",
                "media_asset_id": asset["media_asset_id"],
            },
        }
        for asset in image_assets
    ]

    body = {
        "display_name": "PoC7 Interior Walkthrough",
        "model": model,
        "world_prompt": {
            "type": "multi-image",
            "multi_image_prompt": multi_image_prompt,
        },
    }
    if text_prompt:
        body["world_prompt"]["text_prompt"] = text_prompt

    logger.info("ワールド生成リクエスト送信（model=%s, 画像数=%d）", model, len(image_assets))
    logger.info("リクエストボディ:\n%s", json.dumps(body, indent=2, ensure_ascii=False))

    resp = client.post(
        f"{BASE_URL}/worlds:generate",
        headers=HEADERS,
        json=body,
        timeout=60,
    )
    if resp.status_code != 200:
        logger.error("ワールド生成エラー: %d %s", resp.status_code, resp.text)
        resp.raise_for_status()
    data = resp.json()

    operation_id = data.get("operation_id") or data.get("name", "").split("/")[-1]
    logger.info("ワールド生成開始: operation_id=%s", operation_id)
    logger.info("レスポンス:\n%s", json.dumps(data, indent=2, ensure_ascii=False))

    return data


def poll_operation(client: httpx.Client, operation_id: str, *, interval: int = 10, timeout: int = 600) -> dict:
    """オペレーションの完了をポーリングで待機."""
    logger.info("ポーリング開始: operation_id=%s（間隔%d秒、タイムアウト%d秒）", operation_id, interval, timeout)
    start = time.time()

    while time.time() - start < timeout:
        resp = client.get(
            f"{BASE_URL}/operations/{operation_id}",
            headers=HEADERS,
        )
        resp.raise_for_status()
        data = resp.json()

        if data.get("done"):
            logger.info("ワールド生成完了")
            return data

        elapsed = int(time.time() - start)
        logger.info("生成中... (%d秒経過)", elapsed)
        time.sleep(interval)

    msg = f"タイムアウト: {timeout}秒以内に完了しませんでした"
    raise TimeoutError(msg)


def download_assets(client: httpx.Client, result: dict) -> None:
    """生成されたアセットをダウンロード."""
    assets = result.get("response", {}).get("world", {}).get("assets", {})
    if not assets:
        # レスポンス構造が異なる場合の対応
        logger.warning("assetsが見つかりません。レスポンス全体:\n%s", json.dumps(result, indent=2, ensure_ascii=False))
        return

    downloads = {}

    # Gaussian Splat (SPZ)
    splats = assets.get("splats", {})
    for url in splats.get("spz_urls", []):
        downloads["world.spz"] = url

    # メッシュ (GLB)
    mesh = assets.get("mesh", {})
    if mesh.get("collider_mesh_url"):
        downloads["world_mesh.glb"] = mesh["collider_mesh_url"]

    # パノラマ
    imagery = assets.get("imagery", {})
    if imagery.get("pano_url"):
        downloads["world_pano.jpg"] = imagery["pano_url"]

    # サムネイル
    if assets.get("thumbnail_url"):
        downloads["thumbnail.jpg"] = assets["thumbnail_url"]

    for filename, url in downloads.items():
        logger.info("ダウンロード中: %s", filename)
        resp = client.get(url)
        resp.raise_for_status()
        output_path = OUTPUT_DIR / filename
        output_path.write_bytes(resp.content)
        logger.info("保存: %s (%d bytes)", output_path, len(resp.content))


def main() -> None:
    """メイン処理."""
    with httpx.Client(timeout=httpx.Timeout(120)) as client:
        # Step 1: 画像アップロード
        image_assets = []
        for filename, azimuth in CAMERA_AZIMUTH_MAP.items():
            file_path = INPUT_DIR / filename
            if not file_path.exists():
                logger.warning("画像が見つかりません: %s", file_path)
                continue

            media_asset_id = upload_image(client, file_path)
            image_assets.append({
                "filename": filename,
                "media_asset_id": media_asset_id,
                "azimuth": azimuth,
            })

        logger.info("アップロード完了: %d枚", len(image_assets))

        # Step 2: ワールド生成
        result = generate_world(
            client,
            image_assets,
            model="Marble 0.1-mini",
            text_prompt="A modern minimalist Japanese apartment interior with warm wood flooring, white walls, natural lighting",
        )

        # レスポンスを保存
        result_path = OUTPUT_DIR / "generate_response.json"
        result_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        logger.info("生成レスポンス保存: %s", result_path)

        # Step 3: ポーリング（operation_idがある場合）
        operation_id = result.get("operation_id") or result.get("name", "").split("/")[-1]
        if operation_id and not result.get("done"):
            final_result = poll_operation(client, operation_id)
            final_path = OUTPUT_DIR / "final_result.json"
            final_path.write_text(json.dumps(final_result, indent=2, ensure_ascii=False))
            logger.info("最終結果保存: %s", final_path)

            # Step 4: アセットダウンロード
            download_assets(client, final_result)
        elif result.get("done"):
            download_assets(client, result)

        logger.info("処理完了")


if __name__ == "__main__":
    main()
