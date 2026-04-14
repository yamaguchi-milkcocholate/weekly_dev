"""Seamless Keyframe PoC Phase 4: 環境変更検証（Kontext vs Gemini）.

plan4.md に基づき、FLUX Kontext と Gemini で
人物をそのままに背景環境だけを変更する検証を行う。

Usage:
    uv run python poc/seamless/run_plan4.py --dry-run
    uv run python poc/seamless/run_plan4.py --patterns E-A,E-B
    uv run python poc/seamless/run_plan4.py --patterns E-C,E-D
    uv run python poc/seamless/run_plan4.py
"""

import argparse
import base64
import json
import logging
import os
import sys
import time
from dataclasses import dataclass
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
GENERATED_DIR = BASE_DIR / "generated" / "plan4"
REPO_ROOT = Path(__file__).resolve().parents[2]

SEED_CAPTURE = REPO_ROOT / "seeds" / "captures" / "tamachan_life_" / "6.png"
SAKURA_REF = BASE_DIR / "reference" / "sakura.jpg"

# --- BFL (Kontext) 定数 ---
BFL_API_BASE = "https://api.bfl.ai"
BFL_POLL_INTERVAL = 1.0
BFL_POLL_TIMEOUT = 300.0
COST_KONTEXT_PRO = 0.04
COST_KONTEXT_MAX = 0.08

# --- Gemini 定数 ---
GEMINI_MODEL = "gemini-3-pro-image-preview"
GEMINI_BASE_URL = "https://generativelanguage.googleapis.com/v1beta"
COST_GEMINI = 0.04


# =============================================================================
# データモデル
# =============================================================================


class ApiProvider(str, Enum):
    KONTEXT_PRO = "kontext_pro"
    KONTEXT_MAX = "kontext_max"
    GEMINI = "gemini"


@dataclass
class Plan4Pattern:
    """Phase 4 実験パターン."""

    id: str
    name: str
    provider: ApiProvider
    prompt: str
    use_sakura_ref: bool = False
    cost: float = 0.0
    description: str = ""


# =============================================================================
# プロンプト定義（plan4.md 準拠）
# =============================================================================

PROMPT_TEXT_ONLY = (
    "Change the background of this image to a riverside walkway lined with "
    "blooming pink cherry blossom trees under a clear blue sky. "
    "Keep the person, pose, outfit, and camera angle completely unchanged. "
    "Bright natural daylight, vivid spring atmosphere. "
    "Single person only, solo."
)

PROMPT_KONTEXT_MAX_REF = (
    "Place the person from image_1 into the scene from image_2. "
    "Keep the same person, pose, outfit, and camera angle from image_1. "
    "Use the cherry blossom riverside environment, lighting, and atmosphere from image_2. "
    "Single person only, solo."
)

PROMPT_GEMINI_REF = (
    "Change the background of this image to match the environment shown in the reference photo. "
    "Keep the person, pose, outfit, and camera angle completely unchanged. "
    "Use the cherry blossom riverside environment, lighting, and atmosphere from the reference photo. "
    "Single person only, solo."
)

# =============================================================================
# パターン定義
# =============================================================================

ALL_PATTERNS: list[Plan4Pattern] = [
    Plan4Pattern(
        id="E-A",
        name="Kontext Pro: テキストのみ",
        provider=ApiProvider.KONTEXT_PRO,
        prompt=PROMPT_TEXT_ONLY,
        use_sakura_ref=False,
        cost=COST_KONTEXT_PRO,
        description="seed キャプチャを入力し、プロンプトで背景変更を指示",
    ),
    Plan4Pattern(
        id="E-B",
        name="Kontext Max: 環境参照あり",
        provider=ApiProvider.KONTEXT_MAX,
        prompt=PROMPT_KONTEXT_MAX_REF,
        use_sakura_ref=True,
        cost=COST_KONTEXT_MAX,
        description="seed キャプチャ + sakura.jpg を入力し、環境の転写を指示",
    ),
    Plan4Pattern(
        id="E-C",
        name="Gemini: テキストのみ",
        provider=ApiProvider.GEMINI,
        prompt=PROMPT_TEXT_ONLY,
        use_sakura_ref=False,
        cost=COST_GEMINI,
        description="seed キャプチャを入力し、プロンプトで背景変更を指示",
    ),
    Plan4Pattern(
        id="E-D",
        name="Gemini: 環境参照あり",
        provider=ApiProvider.GEMINI,
        prompt=PROMPT_GEMINI_REF,
        use_sakura_ref=True,
        cost=COST_GEMINI,
        description="seed キャプチャ + sakura.jpg を入力し、環境の転写を指示",
    ),
]


def get_patterns_by_ids(ids: list[str]) -> list[Plan4Pattern]:
    id_set = {i.strip() for i in ids}
    return [p for p in ALL_PATTERNS if p.id in id_set]


# =============================================================================
# BFL (Kontext) API
# =============================================================================


def get_bfl_api_key() -> str:
    load_dotenv()
    key = os.environ.get("DAILY_ROUTINE_API_KEY_BFL")
    if not key:
        logger.error("DAILY_ROUTINE_API_KEY_BFL が設定されていません")
        sys.exit(1)
    return key


def encode_image_base64(file_path: Path) -> str:
    data = file_path.read_bytes()
    return base64.b64encode(data).decode("utf-8")


def bfl_generate(
    client: httpx.Client,
    api_key: str,
    pattern: Plan4Pattern,
    seed_b64: str,
    sakura_b64: str | None,
    output_path: Path,
) -> dict:
    """BFL Kontext API で画像を生成する."""
    endpoint = (
        "v1/flux-kontext-max" if pattern.provider == ApiProvider.KONTEXT_MAX else "v1/flux-kontext-pro"
    )

    payload: dict = {"prompt": pattern.prompt, "seed": 42}

    if pattern.provider == ApiProvider.KONTEXT_MAX:
        payload["input_image"] = seed_b64
        if pattern.use_sakura_ref and sakura_b64:
            payload["input_image_2"] = sakura_b64
    else:
        payload["input_image"] = seed_b64

    logger.info("  BFL API リクエスト送信中... (%s)", endpoint)
    resp = client.post(
        f"{BFL_API_BASE}/{endpoint}",
        json=payload,
        headers={"x-key": api_key},
    )
    if resp.status_code >= 400:
        logger.error("  BFL API エラー: status=%d, body=%s", resp.status_code, resp.text)
    resp.raise_for_status()

    polling_url = resp.json()["polling_url"]
    logger.info("  リクエスト送信完了, ポーリング開始...")

    # ポーリング
    start = time.monotonic()
    while time.monotonic() - start < BFL_POLL_TIMEOUT:
        time.sleep(BFL_POLL_INTERVAL)
        resp = client.get(polling_url)
        resp.raise_for_status()
        data = resp.json()
        status = data.get("status")

        if status == "Ready":
            output_url = data["result"]["sample"]
            logger.info("  生成完了")
            break
        if status in ("Error", "Failed", "Request Moderated"):
            raise RuntimeError(f"BFL API エラー: {data}")
        logger.info("  ポーリング中... (status: %s)", status)
    else:
        raise TimeoutError(f"BFL API タイムアウト ({BFL_POLL_TIMEOUT}s)")

    # ダウンロード
    output_path.parent.mkdir(parents=True, exist_ok=True)
    from urllib.request import urlretrieve

    urlretrieve(output_url, output_path)
    logger.info("  画像を保存しました: %s", output_path)

    return {
        "output_url": output_url,
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
    pattern: Plan4Pattern,
    output_path: Path,
) -> dict:
    """Gemini API で画像を生成する."""
    parts = []

    # 入力画像（seed キャプチャ）
    parts.append(encode_image_for_gemini(SEED_CAPTURE))
    logger.info("  seed キャプチャを入力")

    # 環境参照画像
    if pattern.use_sakura_ref:
        parts.append(encode_image_for_gemini(SAKURA_REF))
        logger.info("  環境参照画像 (sakura.jpg) を入力")

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
    parser = argparse.ArgumentParser(description="Seamless PoC Phase 4: 環境変更検証")
    parser.add_argument(
        "--patterns",
        type=str,
        default=None,
        help="実行パターンをカンマ区切りで指定 (例: E-A,E-C)。指定なしで全パターン",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="プロンプト確認・コスト見積もりのみ（API 呼び出しなし）",
    )
    return parser.parse_args()


def print_dry_run(patterns: list[Plan4Pattern]) -> None:
    logger.info("=" * 80)
    logger.info("ドライラン: Phase 4 プロンプト確認・コスト見積もり")
    logger.info("=" * 80)
    logger.info("Seed キャプチャ: %s", SEED_CAPTURE)
    logger.info("環境参照画像: %s", SAKURA_REF)
    logger.info("")

    for pattern in patterns:
        logger.info("-" * 60)
        logger.info("[%s] %s (%s)", pattern.id, pattern.name, pattern.provider.value)
        logger.info("  説明: %s", pattern.description)
        logger.info("  コスト: $%.2f", pattern.cost)
        logger.info("  環境参照: %s", "あり (sakura.jpg)" if pattern.use_sakura_ref else "なし")
        logger.info("  プロンプト: %s", pattern.prompt)

    logger.info("")
    logger.info("=" * 80)
    total_cost = sum(p.cost for p in patterns)
    logger.info("合計: %d パターン, 推定コスト: $%.2f", len(patterns), total_cost)
    logger.info("=" * 80)


def run_pattern(
    pattern: Plan4Pattern,
    bfl_client: httpx.Client | None,
    bfl_api_key: str | None,
    seed_b64: str | None,
    sakura_b64: str | None,
    gemini_client: httpx.Client | None,
    gemini_api_key: str | None,
) -> dict:
    output_path = GENERATED_DIR / pattern.id / "output.png"

    logger.info("-" * 60)
    logger.info("[%s] %s を実行中...", pattern.id, pattern.name)

    try:
        if pattern.provider in (ApiProvider.KONTEXT_PRO, ApiProvider.KONTEXT_MAX):
            step_result = bfl_generate(bfl_client, bfl_api_key, pattern, seed_b64, sakura_b64, output_path)
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
    needs_bfl = any(p.provider in (ApiProvider.KONTEXT_PRO, ApiProvider.KONTEXT_MAX) for p in patterns)
    needs_gemini = any(p.provider == ApiProvider.GEMINI for p in patterns)

    bfl_client = None
    bfl_api_key = None
    seed_b64 = None
    sakura_b64 = None
    gemini_client = None
    gemini_api_key = None

    if needs_bfl:
        bfl_api_key = get_bfl_api_key()
        bfl_client = httpx.Client(
            headers={"x-key": bfl_api_key},
            timeout=httpx.Timeout(30.0, read=60.0),
        )
        logger.info("参照画像を Base64 エンコード中...")
        seed_b64 = encode_image_base64(SEED_CAPTURE)
        sakura_b64 = encode_image_base64(SAKURA_REF)

    if needs_gemini:
        gemini_api_key = get_gemini_api_key()
        gemini_client = httpx.Client(timeout=httpx.Timeout(120.0))

    logger.info("=" * 80)
    total_cost = sum(p.cost for p in patterns)
    logger.info("Phase 4 実験開始: %d パターン, 推定コスト: $%.2f", len(patterns), total_cost)

    results = []
    try:
        for pattern in patterns:
            result = run_pattern(
                pattern, bfl_client, bfl_api_key, seed_b64, sakura_b64, gemini_client, gemini_api_key
            )
            results.append(result)
    finally:
        if bfl_client:
            bfl_client.close()
        if gemini_client:
            gemini_client.close()

    # ログ保存
    log_path = GENERATED_DIR / "experiment_log.json"
    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_data = {
        "experiment": "seamless_poc_phase4",
        "timestamp": datetime.now().isoformat(),
        "seed_image": str(SEED_CAPTURE),
        "sakura_ref": str(SAKURA_REF),
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
