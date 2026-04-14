"""PoC: Tripo AI API経由で画像から3Dモデル(GLB)を生成する。

使い方:
    uv run python poc/3dcg_poc2/tripo_image_to_3d.py poc/3dcg_poc2/input/desk.png

環境変数:
    DAILY_ROUTINE_API_KEY_TRIPO: Tripo AIのAPIキー（tsk_で始まる）
"""

import sys
import time
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

API_BASE = "https://api.tripo3d.ai/v2/openapi"
POLL_INTERVAL = 5
MAX_POLL_COUNT = 60


def get_api_key() -> str:
    import os

    key = os.environ.get("DAILY_ROUTINE_API_KEY_TRIPO")
    if not key:
        print("ERROR: 環境変数 DAILY_ROUTINE_API_KEY_TRIPO を設定してください")
        sys.exit(1)
    return key


def upload_image(client: httpx.Client, image_path: Path) -> str:
    """ローカル画像をTripo APIにアップロードしてトークンを取得する。"""
    mime_map = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png", ".webp": "image/webp"}
    mime_type = mime_map.get(image_path.suffix.lower(), "image/jpeg")

    resp = client.post(
        f"{API_BASE}/upload",
        files={"file": (image_path.name, image_path.read_bytes(), mime_type)},
    )
    resp.raise_for_status()
    data = resp.json()
    print(f"[OK] 画像アップロード完了: {data['data']['image_token']}")
    return data["data"]["image_token"]


def create_task(client: httpx.Client, image_token: str) -> str:
    """Image-to-3Dタスクを作成してtask_idを返す。"""
    payload = {
        "type": "image_to_model",
        "file": {"type": "png", "file_token": image_token},
    }
    resp = client.post(f"{API_BASE}/task", json=payload)
    if resp.status_code != 200:
        print(f"ERROR: HTTP {resp.status_code}: {resp.text}")
        sys.exit(1)
    data = resp.json()

    if data.get("code") != 0:
        print(f"ERROR: タスク作成失敗: {data}")
        sys.exit(1)

    task_id = data["data"]["task_id"]
    print(f"[OK] タスク作成完了: {task_id}")
    return task_id


def poll_task(client: httpx.Client, task_id: str) -> dict:
    """タスク完了までポーリングする。"""
    for i in range(MAX_POLL_COUNT):
        resp = client.get(f"{API_BASE}/task/{task_id}")
        resp.raise_for_status()
        data = resp.json()["data"]
        status = data["status"]
        progress = data.get("progress", 0)

        print(f"  [{i + 1}/{MAX_POLL_COUNT}] status={status} progress={progress}")

        if status == "success":
            return data
        if status in ("failed", "cancelled", "unknown"):
            print(f"ERROR: タスク失敗: {data}")
            sys.exit(1)

        time.sleep(POLL_INTERVAL)

    print("ERROR: タイムアウト（5分超過）")
    sys.exit(1)


def download_file(client: httpx.Client, url: str, output_path: Path) -> None:
    """ファイルをダウンロードする。"""
    resp = client.get(url, follow_redirects=True)
    resp.raise_for_status()
    output_path.write_bytes(resp.content)
    size_mb = len(resp.content) / (1024 * 1024)
    print(f"[OK] ダウンロード完了: {output_path} ({size_mb:.1f} MB)")


def main():
    if len(sys.argv) < 2:
        print("使い方: uv run python poc/3dcg_poc2/tripo_image_to_3d.py <画像ファイルパス>")
        sys.exit(1)

    image_path = Path(sys.argv[1])
    if not image_path.exists():
        print(f"ERROR: ファイルが見つかりません: {image_path}")
        sys.exit(1)

    output_dir = Path("poc/3dcg_poc2/output")
    output_dir.mkdir(parents=True, exist_ok=True)

    api_key = get_api_key()
    headers = {"Authorization": f"Bearer {api_key}"}

    with httpx.Client(headers=headers, timeout=120) as client:
        # 1. 画像アップロード
        image_token = upload_image(client, image_path)

        # 2. タスク作成
        task_id = create_task(client, image_token)

        # 3. ポーリング
        print("3Dモデル生成中...")
        result = poll_task(client, task_id)

        # 4. GLBダウンロード
        print(f"出力データ: {result['output']}")
        model_url = result["output"].get("model") or result["output"].get("pbr_model") or result["output"].get("base_model")
        output_path = output_dir / f"{image_path.stem}.glb"
        download_file(client, model_url, output_path)

        # プレビュー画像もあればダウンロード
        rendered_image = result["output"].get("rendered_image")
        if rendered_image:
            preview_path = output_dir / f"{image_path.stem}_preview.webp"
            download_file(client, rendered_image, preview_path)

    print(f"\n完了! GLBファイル: {output_path}")


if __name__ == "__main__":
    main()
