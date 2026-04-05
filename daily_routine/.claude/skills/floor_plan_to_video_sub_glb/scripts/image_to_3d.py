"""画像からTripo AI APIで3Dモデル（GLB）を生成する。

単一画像・マルチビュー（最大4画角）に対応し、複数オブジェクトを並列変換する。

使い方:
    uv run python .claude/skills/floor_plan_to_video_sub_glb/scripts/image_to_3d.py input/objects/
    uv run python .claude/skills/floor_plan_to_video_sub_glb/scripts/image_to_3d.py input/objects/ --output-dir output/models/
    uv run python .claude/skills/floor_plan_to_video_sub_glb/scripts/image_to_3d.py input/objects/ --max-concurrent 5

入力ディレクトリ構造:
    input_dir/
    ├── chair/
    │   ├── front.png    # 正面（必須 or 唯一の画像）
    │   ├── left.jpg     # 左側面（任意）
    │   ├── back.png     # 背面（任意）
    │   └── right.webp   # 右側面（任意）
    └── desk/
        └── photo.png    # 1枚 → 単一画像モード

環境変数:
    DAILY_ROUTINE_API_KEY_TRIPO: Tripo AIのAPIキー（tsk_で始まる）
"""

import argparse
import asyncio
import logging
import os
import sys
from pathlib import Path

import httpx
from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

BASE_URL = "https://api.tripo3d.ai/v2/openapi"
POLL_INTERVAL = 5
MAX_POLL_COUNT = 60
HTTP_TIMEOUT = 120
DEFAULT_MAX_CONCURRENT = 3

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MIME_MAP = {
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    ".webp": "image/webp",
}
VIEW_ORDER = ["front", "left", "back", "right"]


def get_api_key() -> str:
    key = os.environ.get("DAILY_ROUTINE_API_KEY_TRIPO")
    if not key:
        logger.error("環境変数 DAILY_ROUTINE_API_KEY_TRIPO が未設定です")
        sys.exit(1)
    return key


def classify_views(image_dir: Path) -> dict[str, Path]:
    """ディレクトリ内の画像をビュー名に分類する。

    ファイル名のプレフィックスで判定。front/left/back/rightに一致しない画像は
    未分類として扱う。画像が1枚のみの場合はfrontとして返す。
    """
    images: list[Path] = sorted(p for p in image_dir.iterdir() if p.is_file() and p.suffix.lower() in IMAGE_EXTENSIONS)
    if not images:
        return {}

    views: dict[str, Path] = {}
    unclassified: list[Path] = []

    for img in images:
        stem_lower = img.stem.lower()
        matched = False
        for view_name in VIEW_ORDER:
            if stem_lower.startswith(view_name):
                if view_name not in views:
                    views[view_name] = img
                    matched = True
                    break
                else:
                    logger.warning(
                        "%s に %s ビューが複数あります。最初のファイルを使用します",
                        image_dir.name,
                        view_name,
                    )
                    matched = True
                    break
        if not matched:
            unclassified.append(img)

    # 画像が1枚のみでfrontがない場合、その画像をfrontとして扱う
    if not views and len(unclassified) == 1:
        views["front"] = unclassified[0]
        unclassified.clear()

    # frontがないがマルチ画像がある場合、最初の未分類をfrontにする
    if "front" not in views and unclassified:
        logger.warning(
            "%s にfrontプレフィックスの画像がありません。%s をfrontとして使用します",
            image_dir.name,
            unclassified[0].name,
        )
        views["front"] = unclassified.pop(0)

    if unclassified:
        logger.warning(
            "%s にビュー未分類の画像があります（無視）: %s",
            image_dir.name,
            [p.name for p in unclassified],
        )

    return views


async def upload_image(client: httpx.AsyncClient, image_path: Path) -> str:
    """画像をTripo APIにアップロードしてトークンを取得する。"""
    mime_type = MIME_MAP.get(image_path.suffix.lower(), "image/jpeg")
    resp = await client.post(
        f"{BASE_URL}/upload",
        files={"file": (image_path.name, image_path.read_bytes(), mime_type)},
    )
    resp.raise_for_status()
    data = resp.json()
    token = data["data"]["image_token"]
    logger.info("画像アップロード完了: %s → %s", image_path.name, token[:16])
    return token


async def create_single_task(client: httpx.AsyncClient, image_token: str) -> str:
    """単一画像のimage_to_modelタスクを作成する。"""
    payload = {
        "type": "image_to_model",
        "file": {"type": "png", "file_token": image_token},
    }
    resp = await client.post(f"{BASE_URL}/task", json=payload)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        msg = f"タスク作成失敗: {data}"
        raise RuntimeError(msg)
    return data["data"]["task_id"]


async def create_multiview_task(client: httpx.AsyncClient, view_tokens: list[dict]) -> str:
    """マルチビューのmultiview_to_modelタスクを作成する。"""
    payload = {
        "type": "multiview_to_model",
        "files": view_tokens,
    }
    resp = await client.post(f"{BASE_URL}/task", json=payload)
    resp.raise_for_status()
    data = resp.json()
    if data.get("code") != 0:
        msg = f"タスク作成失敗: {data}"
        raise RuntimeError(msg)
    return data["data"]["task_id"]


async def poll_task(client: httpx.AsyncClient, task_id: str, object_name: str) -> dict:
    """タスク完了までポーリングする。"""
    for i in range(MAX_POLL_COUNT):
        resp = await client.get(f"{BASE_URL}/task/{task_id}")
        resp.raise_for_status()
        data = resp.json()["data"]
        status = data["status"]
        progress = data.get("progress", 0)

        logger.info("[%s] %d/%d status=%s progress=%s", object_name, i + 1, MAX_POLL_COUNT, status, progress)

        if status == "success":
            return data
        if status in ("failed", "cancelled", "unknown"):
            msg = f"タスク失敗 ({object_name}): status={status}"
            raise RuntimeError(msg)

        await asyncio.sleep(POLL_INTERVAL)

    msg = f"タイムアウト ({object_name}): {MAX_POLL_COUNT * POLL_INTERVAL}秒超過"
    raise RuntimeError(msg)


async def download_file(client: httpx.AsyncClient, url: str, output_path: Path) -> None:
    """ファイルをダウンロードする。"""
    resp = await client.get(url, follow_redirects=True)
    resp.raise_for_status()
    output_path.write_bytes(resp.content)
    size_mb = len(resp.content) / (1024 * 1024)
    logger.info("ダウンロード完了: %s (%.1f MB)", output_path.name, size_mb)


async def process_object(
    client: httpx.AsyncClient,
    object_dir: Path,
    output_dir: Path,
    semaphore: asyncio.Semaphore,
) -> bool:
    """1オブジェクトの画像→3D変換を実行する。"""
    object_name = object_dir.name

    views = classify_views(object_dir)
    if not views:
        logger.warning("%s に画像がありません。スキップします", object_name)
        return False

    async with semaphore:
        try:
            logger.info("=== %s: 変換開始 (%d画角) ===", object_name, len(views))

            if len(views) == 1:
                # 単一画像モード
                image_path = next(iter(views.values()))
                token = await upload_image(client, image_path)
                task_id = await create_single_task(client, token)
                logger.info("[%s] 単一画像モードでタスク作成: %s", object_name, task_id)
            else:
                # マルチビューモード: 画角ごとにアップロードしてトークンリスト作成
                view_tokens: list[dict] = []
                for view_name in VIEW_ORDER:
                    if view_name in views:
                        image_path = views[view_name]
                        token = await upload_image(client, image_path)
                        ext = image_path.suffix.lstrip(".").lower()
                        if ext == "jpeg":
                            ext = "jpg"
                        view_tokens.append({"type": ext, "file_token": token})
                    else:
                        # Tripo APIは配列インデックスで画角を判定するため、
                        # 欠けている画角はスキップせずNoneで埋める必要があるか確認
                        # → APIドキュメントによると、提供された画像のみで構成可能
                        pass

                task_id = await create_multiview_task(client, view_tokens)
                logger.info(
                    "[%s] マルチビューモードでタスク作成: %s (画角: %s)",
                    object_name,
                    task_id,
                    [v for v in VIEW_ORDER if v in views],
                )

            # ポーリング
            result = await poll_task(client, task_id, object_name)

            # GLBダウンロード
            output = result["output"]
            model_url = output.get("model") or output.get("pbr_model") or output.get("base_model")
            if not model_url:
                logger.error("[%s] モデルURLが取得できません: %s", object_name, output)
                return False

            glb_path = output_dir / f"{object_name}.glb"
            await download_file(client, model_url, glb_path)

            # プレビュー画像
            rendered_image = output.get("rendered_image")
            if rendered_image:
                preview_path = output_dir / f"{object_name}_preview.webp"
                await download_file(client, rendered_image, preview_path)

            logger.info("=== %s: 変換完了 ===", object_name)
            return True

        except Exception:
            logger.exception("[%s] 変換失敗", object_name)
            return False


async def run(input_dir: Path, output_dir: Path, max_concurrent: int) -> None:
    """全オブジェクトを並列変換する。"""
    # オブジェクトディレクトリを収集
    object_dirs = sorted(d for d in input_dir.iterdir() if d.is_dir() and not d.name.startswith("."))
    if not object_dirs:
        logger.error("入力ディレクトリにオブジェクトフォルダがありません: %s", input_dir)
        sys.exit(1)

    logger.info("変換対象: %d オブジェクト, 並列数: %d", len(object_dirs), max_concurrent)

    output_dir.mkdir(parents=True, exist_ok=True)
    api_key = get_api_key()
    headers = {"Authorization": f"Bearer {api_key}"}
    semaphore = asyncio.Semaphore(max_concurrent)

    async with httpx.AsyncClient(headers=headers, timeout=HTTP_TIMEOUT) as client:
        tasks = [process_object(client, obj_dir, output_dir, semaphore) for obj_dir in object_dirs]
        results = await asyncio.gather(*tasks)

    success_count = sum(1 for r in results if r)
    total_count = len(results)
    logger.info("完了: %d/%d オブジェクト成功", success_count, total_count)

    if success_count == 0:
        sys.exit(1)


def main() -> None:
    parser = argparse.ArgumentParser(description="画像からTripo AI APIで3Dモデル（GLB）を生成")
    parser.add_argument("input_dir", type=Path, help="入力ディレクトリ（オブジェクトごとのサブディレクトリを含む）")
    parser.add_argument(
        "--output-dir", type=Path, default=None, help="出力ディレクトリ（デフォルト: input_dir/output/）"
    )
    parser.add_argument(
        "--max-concurrent", type=int, default=DEFAULT_MAX_CONCURRENT, help="最大並列数（デフォルト: 3）"
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    input_dir = args.input_dir.resolve()
    if not input_dir.is_dir():
        logger.error("入力ディレクトリが存在しません: %s", input_dir)
        sys.exit(1)

    output_dir = (args.output_dir or input_dir / "output").resolve()

    asyncio.run(run(input_dir, output_dir, args.max_concurrent))


if __name__ == "__main__":
    main()
