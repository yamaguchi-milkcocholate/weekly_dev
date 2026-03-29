"""Gemini Pro 3.0 によるレイアウトデザインスコアリング.

配置結果画像をGemini Pro 3.0に送信し、scoring_criteria.json の各観点で評価する。
衝突・動線の決定論的検証は placement_engine.py が担当し、
このスクリプトはデザイン品質の定性的評価を担当する。

Usage:
    uv run python scripts/layout_scorer.py <output_dir>

Input:
    - {output_dir}/layout_proposal.png — 配置結果画像
    - {output_dir}/scoring_criteria.json — スコアリング基準（standard + custom）
    - {output_dir}/room_info.json — 部屋情報（コンテキスト用）

Output:
    - {output_dir}/design_scores.json — 評価結果
    - コンソールにスコアサマリーを出力
"""

import json
import sys
from datetime import UTC, datetime
from pathlib import Path

from google import genai
from google.genai import types
from pydantic import BaseModel, Field

# --- Pydantic スキーマ（Gemini の構造化出力用）---


class LowScoreAsset(BaseModel):
    """スコアを下げている家具."""

    asset: str = Field(description="家具名（例: closet_1）")
    reason: str = Field(description="なぜこの家具がスコアを下げているか（日本語）")


class CriterionResult(BaseModel):
    """1つの評価観点の結果."""

    id: str = Field(description="観点ID")
    label: str = Field(description="観点名")
    score: float = Field(description="0.0〜1.0のスコア（1.0が最良）")
    low_score_assets: list[LowScoreAsset] = Field(
        default_factory=list,
        description="スコアを下げている家具のリスト（スコア0.7未満の場合）",
    )
    suggestion: str = Field(description="改善提案（日本語）")


class DesignScores(BaseModel):
    """デザインスコア全体."""

    overall_score: float = Field(description="全観点の重み付き平均スコア")
    criteria: list[CriterionResult] = Field(description="各観点の評価結果")


# --- メイン処理 ---

_SYSTEM_PROMPT = """\
あなたはインテリアデザインの専門家です。
間取り図と家具配置の画像を分析し、指定された評価観点ごとにスコアリングしてください。

## 評価の指針

1. 画像をよく観察し、各家具の位置・向き・周囲の空間を把握してください
2. 各評価観点について、0.0〜1.0のスコアを付けてください（1.0が最良）
3. スコアが0.7未満の観点では、どの家具が原因かを特定してください
4. 改善提案は具体的に（どの家具をどこに移動すべきか）記述してください
5. overall_scoreは各観点のスコアの重み付き平均を計算してください

## スコアリングの基準

- 1.0: 理想的。プロのインテリアデザイナーの配置
- 0.8: 良好。大きな問題なし
- 0.6: 改善の余地あり。明確な違和感がある
- 0.4: 問題あり。実生活で不便が生じるレベル
- 0.2: 深刻な問題。レイアウトとして不適切
- 0.0: 完全に不適切

## 注意事項

- 画像中の色付きの矩形が家具です。ラベルが付いています
- 緑色の領域は歩行可能領域です
- オレンジ色は狭い通路、赤色は到達不能領域です
- 壁は黒い線で描画されています
- 日本語で回答してください
"""


def _load_api_key() -> str:
    """環境変数からGoogle AI APIキーを取得する."""
    import os

    from dotenv import load_dotenv

    # プロジェクトルートの.envを読み込む
    repo_root = Path(__file__).resolve().parents[1]
    load_dotenv(repo_root / ".env")

    key = os.environ.get("DAILY_ROUTINE_API_KEY_GOOGLE_AI", "")
    if not key:
        print("ERROR: DAILY_ROUTINE_API_KEY_GOOGLE_AI が設定されていません", file=sys.stderr)
        sys.exit(1)
    return key


def _build_criteria_text(scoring_criteria: dict) -> str:
    """scoring_criteria.json から評価観点テキストを構築する."""
    lines = []
    all_criteria = []

    for criterion in scoring_criteria.get("criteria", {}).get("standard", []):
        all_criteria.append(criterion)
    for criterion in scoring_criteria.get("criteria", {}).get("custom", []):
        criterion["_custom"] = True
        all_criteria.append(criterion)

    for i, c in enumerate(all_criteria, 1):
        tag = " [ユーザー重視]" if c.get("_custom") else ""
        lines.append(f"### 観点{i}: {c['label']}{tag}")
        lines.append(f"- ID: {c['id']}")
        lines.append(f"- 説明: {c['description']}")
        lines.append(f"- 重み: {c.get('weight', 1.0)}")
        if "target_assets" in c:
            lines.append(f"- 対象家具: {', '.join(c['target_assets'])}")
        lines.append("")

    return "\n".join(lines)


def _build_room_summary(room_info: list[dict]) -> str:
    """room_info.json から部屋情報の要約を構築する."""
    lines = []
    for item in room_info:
        item_type = item.get("type", "")
        label = item.get("label", "")
        real_m = item.get("real_m", {})
        if item_type == "room":
            w = real_m.get("x_max", 0) - real_m.get("x_min", 0)
            h = real_m.get("y_max", 0) - real_m.get("y_min", 0)
            lines.append(f"- {label}: {w:.1f}m × {h:.1f}m")
        elif item_type == "fixture":
            lines.append(f"- 設備: {label}")
        elif item_type == "door":
            lines.append(f"- ドア: {label}")
    return "\n".join(lines)


def run(output_dir: Path) -> DesignScores:
    """デザインスコアリングを実行する."""
    # ファイル読み込み
    image_path = output_dir / "layout_proposal.png"
    criteria_path = output_dir / "scoring_criteria.json"
    room_info_path = output_dir / "room_info.json"

    if not image_path.exists():
        print(f"ERROR: {image_path} が見つかりません", file=sys.stderr)
        sys.exit(1)
    if not criteria_path.exists():
        print(f"ERROR: {criteria_path} が見つかりません", file=sys.stderr)
        sys.exit(1)

    with open(criteria_path) as f:
        scoring_criteria = json.load(f)

    room_info = []
    if room_info_path.exists():
        with open(room_info_path) as f:
            room_info = json.load(f)

    # Gemini クライアント初期化
    api_key = _load_api_key()
    client = genai.Client(api_key=api_key)

    # プロンプト構築
    criteria_text = _build_criteria_text(scoring_criteria)
    room_summary = _build_room_summary(room_info)

    user_prompt = f"""\
以下の間取り図と家具配置画像を評価してください。

## 部屋情報
{room_summary}

## 評価観点
{criteria_text}

画像を詳細に分析し、各観点についてスコアと改善提案を返してください。
"""

    # 画像を読み込み
    image_bytes = image_path.read_bytes()

    print("=== デザインスコア (Gemini Pro 3.0) ===")
    print(f"  画像: {image_path}")
    print(f"  基準: {criteria_path}")
    print("  評価中...")
    print()

    # Gemini API 呼び出し
    response = client.models.generate_content(
        model="gemini-3-pro-image-preview",
        contents=[
            types.Part.from_bytes(data=image_bytes, mime_type="image/png"),
            user_prompt,
        ],
        config=types.GenerateContentConfig(
            system_instruction=_SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=DesignScores,
        ),
    )

    scores = DesignScores.model_validate_json(response.text)

    # コンソール出力
    for cr in scores.criteria:
        is_custom = any(c["id"] == cr.id for c in scoring_criteria.get("criteria", {}).get("custom", []))
        tag = " [custom]" if is_custom else ""
        warn = " \u26a0" if cr.score < 0.7 else ""
        print(f"  {cr.label}:{' ' * max(1, 14 - len(cr.label) * 2)}{cr.score:.2f}{warn}{tag}")
        for asset in cr.low_score_assets:
            print(f"    \u2192 {asset.asset}: {asset.reason}")

    print(f"  {'---':>16}")
    print(f"  {'総合スコア:':<14}{scores.overall_score:.2f}")

    # 改善提案サマリー
    low_criteria = [cr for cr in scores.criteria if cr.score < 0.7]
    if low_criteria:
        print()
        print("  改善提案:")
        for i, cr in enumerate(low_criteria, 1):
            print(f"  {i}. {cr.suggestion}")

    # JSON出力
    output = {
        "model": "gemini-3-pro-image-preview",
        "timestamp": datetime.now(tz=UTC).isoformat(),
        "overall_score": scores.overall_score,
        "criteria": [cr.model_dump() for cr in scores.criteria],
    }

    scores_path = output_dir / "design_scores.json"
    with open(scores_path, "w") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print()
    print(f"  結果を保存: {scores_path}")

    return scores


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: uv run python scripts/layout_scorer.py <output_dir>", file=sys.stderr)
        sys.exit(1)

    output_dir = Path(sys.argv[1])
    if not output_dir.is_dir():
        print(f"ERROR: {output_dir} はディレクトリではありません", file=sys.stderr)
        sys.exit(1)

    run(output_dir)
