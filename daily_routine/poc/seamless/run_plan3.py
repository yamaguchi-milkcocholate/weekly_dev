"""Seamless Keyframe PoC Phase 3: Runway / Gemini 比較検証.

plan3.md に基づき、Runway Gen-4 Image と Gemini で
人物差し替え + ポーズ変更（自撮り化）を検証する。

Usage:
    uv run python poc/seamless/run_plan3.py --dry-run
    uv run python poc/seamless/run_plan3.py --patterns R-A,R-B
    uv run python poc/seamless/run_plan3.py --patterns G-A,G-B
    uv run python poc/seamless/run_plan3.py
"""

import argparse
import base64
import json
import logging
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

import httpx
from dotenv import load_dotenv

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).parent
GENERATED_DIR = BASE_DIR / "generated" / "plan3"
REPO_ROOT = Path(__file__).resolve().parents[2]

SEED_CAPTURE = REPO_ROOT / "seeds" / "captures" / "tamachan_life_" / "6.png"
CHARACTER_REF = BASE_DIR / "reference" / "front.png"

# --- Runway 定数 ---
RUNWAY_BASE_URL = "https://api.dev.runwayml.com/v1"
RUNWAY_MODEL = "gen4_image"
RUNWAY_POLL_INTERVAL = 5.0
RUNWAY_POLL_TIMEOUT = 300.0
RUNWAY_COST_PER_IMAGE = 0.05  # 720p

# --- Gemini 定数 ---
GEMINI_MODEL = "gemini-3-pro-image-preview"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
GEMINI_COST_PER_IMAGE = 0.04


# =============================================================================
# データモデル
# =============================================================================


class ApiProvider(str, Enum):
    RUNWAY = "runway"
    GEMINI = "gemini"


@dataclass
class Plan3Pattern:
    """Phase 3 実験パターン."""

    id: str
    name: str
    provider: ApiProvider
    prompt: str
    use_seed_capture: bool = True
    use_character_ref: bool = False
    cost: float = 0.0
    description: str = ""


# =============================================================================
# プロンプト定義（plan3.md 準拠）
# =============================================================================

PROMPTS = {
    "R-A": (
        "@char takes a selfie with her smartphone in @location, "
        "arm extended forward, front camera perspective, "
        "slightly above eye level, gentle smile. "
        "Lifestyle photography, natural lighting."
    ),
    "R-B": (
        "@char takes a selfie with her smartphone in an underground walkway, "
        "arm extended forward, front camera perspective, "
        "slightly above eye level, gentle smile. "
        "Fluorescent overhead lighting, tiled floor, wide corridor. "
        "Lifestyle photography."
    ),
    "G-A": (
        "Change the person in this image to a young Japanese woman, mid 20s, slender build, "
        "wavy dark brown shoulder-length hair, soft round eyes, fair skin, "
        "wearing a beige V-neck blouse, light gray pencil skirt, "
        "a delicate gold necklace, beige flat shoes. "
        "She holds a smartphone in her right hand, arm extended forward, "
        "taking a selfie with the front camera, smiling gently at the phone screen. "
        "The camera angle is slightly above eye level, as seen from the phone's perspective. "
        "Keep the same background environment and lighting. "
        "Single person only, solo."
    ),
    "G-B": (
        "Change the person in this image to the woman shown in the reference photo. "
        "She holds a smartphone in her right hand, arm extended forward, "
        "taking a selfie with the front camera, smiling gently at the phone screen. "
        "The camera angle is slightly above eye level, as seen from the phone's perspective. "
        "Keep the same background environment and lighting. "
        "Maintain the same facial features, hairstyle, and outfit as the reference photo. "
        "Single person only, solo."
    ),
}

# =============================================================================
# パターン定義
# =============================================================================

ALL_PATTERNS: list[Plan3Pattern] = [
    Plan3Pattern(
        id="R-A",
        name="Runway: @char + @location",
        provider=ApiProvider.RUNWAY,
        prompt=PROMPTS["R-A"],
        use_seed_capture=True,
        use_character_ref=True,
        cost=RUNWAY_COST_PER_IMAGE,
        description="seed キャプチャを @location、彩花を @char として参照 + 自撮りポーズをプロンプト指示",
    ),
    Plan3Pattern(
        id="R-B",
        name="Runway: @char のみ",
        provider=ApiProvider.RUNWAY,
        prompt=PROMPTS["R-B"],
        use_seed_capture=False,
        use_character_ref=True,
        cost=RUNWAY_COST_PER_IMAGE,
        description="彩花を @char として参照 + 環境・ポーズをプロンプトで記述",
    ),
    Plan3Pattern(
        id="G-A",
        name="Gemini: I2I テキスト指示のみ",
        provider=ApiProvider.GEMINI,
        prompt=PROMPTS["G-A"],
        use_seed_capture=True,
        use_character_ref=False,
        cost=GEMINI_COST_PER_IMAGE,
        description="seed キャプチャを入力 + 人物差し替え・ポーズ変更を指示（FLUX P-A と同等）",
    ),
    Plan3Pattern(
        id="G-B",
        name="Gemini: 参照画像 + テキスト指示",
        provider=ApiProvider.GEMINI,
        prompt=PROMPTS["G-B"],
        use_seed_capture=True,
        use_character_ref=True,
        cost=GEMINI_COST_PER_IMAGE,
        description="seed キャプチャ + 彩花の参照画像を入力 + ポーズ変更を指示",
    ),
]


def get_patterns_by_ids(ids: list[str]) -> list[Plan3Pattern]:
    id_set = {i.strip() for i in ids}
    return [p for p in ALL_PATTERNS if p.id in id_set]


# =============================================================================
# Runway Gen-4 Image API
# =============================================================================


def get_runway_api_key() -> str:
    load_dotenv()
    key = os.environ.get("DAILY_ROUTINE_API_KEY_RUNWAY")
    if not key:
        logger.error("DAILY_ROUTINE_API_KEY_RUNWAY が設定されていません")
        sys.exit(1)
    return key


def runway_build_headers(api_key: str) -> dict[str, str]:
    return {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
        "X-Runway-Version": "2024-11-06",
    }


def runway_upload_image(client: httpx.Client, image_path: Path, headers: dict[str, str]) -> str:
    """Runway にローカル画像をアップロードし、URL を返す.

    Runway Gen-4 Image は referenceImages に URL を要求するため、
    GCS にアップロードする代わりに data URI を直接使用する。
    """
    data = image_path.read_bytes()
    suffix = image_path.suffix.lstrip(".")
    mime = f"image/{suffix}" if suffix != "jpg" else "image/jpeg"
    data_uri = f"data:{mime};base64,{base64.b64encode(data).decode('utf-8')}"
    return data_uri


def runway_generate(
    client: httpx.Client,
    headers: dict[str, str],
    pattern: Plan3Pattern,
    output_path: Path,
) -> dict:
    """Runway Gen-4 Image で画像を生成する.

    src/daily_routine/visual/clients/gen4_image.py のパターンを参考に、
    同期版として実装。
    """
    reference_images = []

    if pattern.use_character_ref:
        char_uri = runway_upload_image(client, CHARACTER_REF, headers)
        reference_images.append({"uri": char_uri, "tag": "char"})
        logger.info("  キャラクター参照画像を準備: @char")

    if pattern.use_seed_capture:
        location_uri = runway_upload_image(client, SEED_CAPTURE, headers)
        reference_images.append({"uri": location_uri, "tag": "location"})
        logger.info("  シーン参照画像を準備: @location")

    payload = {
        "model": RUNWAY_MODEL,
        "promptText": pattern.prompt,
        "ratio": "1080:1920",
        "referenceImages": reference_images,
    }

    logger.info("  Runway API リクエスト送信中...")
    resp = client.post(f"{RUNWAY_BASE_URL}/text_to_image", json=payload, headers=headers)
    if resp.status_code >= 400:
        logger.error("  Runway API エラー: status=%d, body=%s", resp.status_code, resp.text)
    resp.raise_for_status()
    task_id = resp.json()["id"]
    logger.info("  タスク作成完了: %s", task_id)

    # ポーリング
    start = time.monotonic()
    while time.monotonic() - start < RUNWAY_POLL_TIMEOUT:
        time.sleep(RUNWAY_POLL_INTERVAL)
        resp = client.get(f"{RUNWAY_BASE_URL}/tasks/{task_id}", headers=headers)
        resp.raise_for_status()
        data = resp.json()
        status = data["status"]

        if status == "SUCCEEDED":
            image_url = data["output"][0]
            logger.info("  生成完了: %s", task_id)
            break
        if status == "FAILED":
            raise RuntimeError(f"Runway 生成失敗: {data.get('failure')}")
        logger.info("  ポーリング中... (status: %s)", status)
    else:
        raise TimeoutError(f"Runway タイムアウト ({RUNWAY_POLL_TIMEOUT}s)")

    # ダウンロード
    output_path.parent.mkdir(parents=True, exist_ok=True)
    resp = client.get(image_url)
    resp.raise_for_status()
    output_path.write_bytes(resp.content)
    logger.info("  画像を保存しました: %s", output_path)

    return {
        "output_url": image_url,
        "output_path": str(output_path),
        "cost_usd": pattern.cost,
        "status": "success",
    }


# =============================================================================
# Gemini API
# =============================================================================


def get_gemini_api_key() -> str:
    load_dotenv()
    key = os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI")
    if not key:
        logger.error("DAILY_ROUTINE_API_KEY_GOOGLE_AI が設定されていません")
        sys.exit(1)
    return key


def encode_image_for_gemini(image_path: Path) -> dict:
    """Gemini API 用の inline_data パートを構築する."""
    data = image_path.read_bytes()
    suffix = image_path.suffix.lstrip(".")
    mime = f"image/{suffix}" if suffix != "jpg" else "image/jpeg"
    return {
        "inline_data": {
            "mime_type": mime,
            "data": base64.b64encode(data).decode("utf-8"),
        }
    }


def gemini_generate(
    client: httpx.Client,
    api_key: str,
    pattern: Plan3Pattern,
    output_path: Path,
) -> dict:
    """Gemini で画像を生成する.

    src/daily_routine/asset/client.py の GeminiImageClient を参考に、
    httpx 同期版・直接 REST API 呼び出しとして実装。
    """
    parts = []

    # 入力画像（seed キャプチャ）
    if pattern.use_seed_capture:
        parts.append(encode_image_for_gemini(SEED_CAPTURE))
        logger.info("  seed キャプチャを入力")

    # 参照画像（キャラクター）
    if pattern.use_character_ref:
        parts.append(encode_image_for_gemini(CHARACTER_REF))
        logger.info("  キャラクター参照画像を入力")

    # テキストプロンプト
    parts.append({"text": pattern.prompt})

    payload = {
        "contents": [{"parts": parts}],
        "generationConfig": {
            "responseModalities": ["TEXT", "IMAGE"],
        },
    }

    url = f"{GEMINI_BASE_URL}/models/{GEMINI_MODEL}:generateContent"
    logger.info("  Gemini API リクエスト送信中...")
    resp = client.post(
        url,
        json=payload,
        headers={"x-goog-api-key": api_key},
    )
    if resp.status_code >= 400:
        logger.error("  Gemini API エラー: status=%d, body=%s", resp.status_code, resp.text)
    resp.raise_for_status()

    # レスポンスから画像を抽出
    result = resp.json()
    image_data = _extract_gemini_image(result)
    if image_data is None:
        raise RuntimeError("Gemini: 画像が生成されませんでした")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(image_data)
    logger.info("  画像を保存しました: %s", output_path)

    return {
        "output_path": str(output_path),
        "cost_usd": pattern.cost,
        "status": "success",
    }


def _extract_gemini_image(result: dict) -> bytes | None:
    """Gemini レスポンスから画像バイナリを抽出する."""
    candidates = result.get("candidates", [])
    for candidate in candidates:
        content = candidate.get("content", {})
        parts = content.get("parts", [])
        for part in parts:
            if "inlineData" in part:
                return base64.b64decode(part["inlineData"]["data"])
    return None


# =============================================================================
# メイン処理
# =============================================================================


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seamless PoC Phase 3: Runway / Gemini 比較検証")
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="実行パターンをカンマ区切りで指定 (例: R-A,G-A)。指定なしで全パターン",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="プロンプト確認・コスト見積もりのみ（API 呼び出しなし）",
    )
    return parser.parse_args()


def print_dry_run(patterns: list[Plan3Pattern]) -> None:
    logger.info("=" * 80)
    logger.info("ドライラン: Phase 3 プロンプト確認・コスト見積もり")
    logger.info("=" * 80)
    logger.info("Seed キャプチャ: %s", SEED_CAPTURE)
    logger.info("キャラクター参照: %s", CHARACTER_REF)
    logger.info("")

    for pattern in patterns:
        logger.info("-" * 60)
        logger.info("[%s] %s (%s)", pattern.id, pattern.name, pattern.provider.value)
        logger.info("  説明: %s", pattern.description)
        logger.info("  コスト: $%.2f", pattern.cost)

        input_sources = []
        if pattern.use_seed_capture:
            input_sources.append("seed キャプチャ")
        if pattern.use_character_ref:
            input_sources.append("キャラクター参照")
        logger.info("  入力: %s", " + ".join(input_sources) if input_sources else "なし（T2I）")
        logger.info("  プロンプト: %s", pattern.prompt)

    logger.info("")
    logger.info("=" * 80)
    total_cost = sum(p.cost for p in patterns)
    logger.info("合計: %d パターン, 推定コスト: $%.2f", len(patterns), total_cost)
    logger.info("=" * 80)


def run_pattern(
    pattern: Plan3Pattern,
    runway_client: httpx.Client | None,
    runway_headers: dict[str, str] | None,
    gemini_client: httpx.Client | None,
    gemini_api_key: str | None,
) -> dict:
    """1パターンを実行し、結果を返す."""
    output_path = GENERATED_DIR / pattern.id / "output.png"

    logger.info("-" * 60)
    logger.info("[%s] %s を実行中...", pattern.id, pattern.name)

    try:
        if pattern.provider == ApiProvider.RUNWAY:
            step_result = runway_generate(runway_client, runway_headers, pattern, output_path)
        else:
            step_result = gemini_generate(gemini_client, gemini_api_key, pattern, output_path)

        return {
            "pattern_id": pattern.id,
            "pattern_name": pattern.name,
            "provider": pattern.provider.value,
            "description": pattern.description,
            "prompt": pattern.prompt,
            **step_result,
        }
    except Exception:
        logger.exception("[%s] 失敗", pattern.id)
        return {
            "pattern_id": pattern.id,
            "pattern_name": pattern.name,
            "provider": pattern.provider.value,
            "description": pattern.description,
            "prompt": pattern.prompt,
            "status": "failed",
        }


def main() -> None:
    args = parse_args()

    if args.patterns:
        patterns = get_patterns_by_ids(args.patterns.split(","))
        if not patterns:
            logger.error("指定されたパターンが見つかりません: %s", args.patterns)
            sys.exit(1)
    else:
        patterns = ALL_PATTERNS

    if args.dry_run:
        print_dry_run(patterns)
        return

    # 必要な API クライアントのみ初期化
    needs_runway = any(p.provider == ApiProvider.RUNWAY for p in patterns)
    needs_gemini = any(p.provider == ApiProvider.GEMINI for p in patterns)

    runway_client = None
    runway_headers = None
    gemini_client = None
    gemini_api_key = None

    if needs_runway:
        runway_api_key = get_runway_api_key()
        runway_headers = runway_build_headers(runway_api_key)
        runway_client = httpx.Client(timeout=httpx.Timeout(30.0, read=120.0))

    if needs_gemini:
        gemini_api_key = get_gemini_api_key()
        gemini_client = httpx.Client(timeout=httpx.Timeout(120.0))

    logger.info("=" * 80)
    total_cost = sum(p.cost for p in patterns)
    logger.info("Phase 3 実験開始: %d パターン, 推定コスト: $%.2f", len(patterns), total_cost)

    results = []
    try:
        for pattern in patterns:
            result = run_pattern(pattern, runway_client, runway_headers, gemini_client, gemini_api_key)
            results.append(result)
    finally:
        if runway_client:
            runway_client.close()
        if gemini_client:
            gemini_client.close()

    # ログ保存
    log_path = GENERATED_DIR / "experiment_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "experiment": "seamless_poc_phase3",
        "timestamp": datetime.now().isoformat(),
        "seed_image": str(SEED_CAPTURE),
        "character_ref": str(CHARACTER_REF),
        "patterns": results,
    }
    log_path.write_text(json.dumps(log_data, ensure_ascii=False, indent=2))
    logger.info("実験ログを保存しました: %s", log_path)

    # サマリ
    logger.info("=" * 80)
    logger.info("実験結果サマリ:")
    success = sum(1 for r in results if r["status"] == "success")
    failed = sum(1 for r in results if r["status"] == "failed")
    actual_cost = sum(r.get("cost_usd", 0) for r in results if r["status"] == "success")
    logger.info("  成功: %d, 失敗: %d", success, failed)
    logger.info("  実コスト: $%.2f", actual_cost)
    logger.info("=" * 80)


if __name__ == "__main__":
    main()
