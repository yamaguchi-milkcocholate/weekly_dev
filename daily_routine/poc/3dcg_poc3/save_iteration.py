"""Refineループのイテレーション記録.

各バージョンのスナップショットを iterations/vN/ に保存し、
HISTORY.md にサマリーと各バージョンの詳細を人が読める形式で出力する。

Usage:
    uv run python poc/3dcg_poc3/save_iteration.py <output_dir> <version> [--feedback "..."] [--changes "..."]
    uv run python poc/3dcg_poc3/save_iteration.py <output_dir> v0_candidates --candidates-dir

Input:
    - {output_dir}/placement_plan.json — 配置計画（必須）
    - {output_dir}/layout_proposal.json — 配置結果（任意）
    - {output_dir}/layout_proposal.png — 配置画像（任意）
    - {output_dir}/design_scores.json — デザインスコア（任意）
    - {output_dir}/candidates/ — 戦略候補ディレクトリ（--candidates-dir時）

Output:
    - {output_dir}/iterations/vN/ — スナップショット
    - {output_dir}/iterations/v0_candidates/ — 候補アーカイブ（--candidates-dir時）
    - {output_dir}/iterations/HISTORY.md — 全バージョンの履歴
"""

import argparse
import json
import logging
import re
import shutil
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- Pydantic モデル ---


class LowScoreCriterion(BaseModel):
    """スコア0.7未満の観点."""

    id: str = Field(description="観点ID")
    label: str = Field(description="観点名")
    score: float = Field(description="スコア")
    suggestion: str = Field(description="改善提案")


class IterationRecord(BaseModel):
    """1イテレーションの記録."""

    version: str = Field(description="バージョン（例: v1）")
    timestamp: str = Field(description="ISO 8601タイムスタンプ")
    strategy: str = Field(default="", description="placement_plan.jsonのstrategyから取得")
    overall_score: float | None = Field(default=None, description="design_scores.jsonのoverall_score")
    low_score_criteria: list[LowScoreCriterion] = Field(default_factory=list, description="スコア0.7未満の観点")
    engine_result: str = Field(default="N/A", description="PASS or FAIL")
    changes: str = Field(default="", description="前バージョンからの変更サマリー")
    user_feedback: str = Field(default="", description="ユーザーのフィードバック")


# --- コピー対象ファイル ---

_COPY_FILES = [
    "placement_plan.json",
    "layout_proposal.json",
    "layout_proposal.png",
    "design_scores.json",
]


def _collect_record(version_dir: Path, version: str) -> IterationRecord:
    """vN/ ディレクトリからIterationRecordを構築する."""
    # メタファイルがあれば読み込む
    meta_path = version_dir / "iteration_meta.json"
    if meta_path.exists():
        with open(meta_path) as f:
            return IterationRecord.model_validate_json(f.read())

    # なければJSONファイルから構築
    record = IterationRecord(
        version=version,
        timestamp=datetime.now(tz=UTC).isoformat(),
    )

    # placement_plan.json から strategy を取得
    plan_path = version_dir / "placement_plan.json"
    if plan_path.exists():
        with open(plan_path) as f:
            plan = json.load(f)
        record.strategy = plan.get("strategy", "")

    # design_scores.json からスコアを取得
    scores_path = version_dir / "design_scores.json"
    if scores_path.exists():
        with open(scores_path) as f:
            scores = json.load(f)
        record.overall_score = scores.get("overall_score")
        for criterion in scores.get("criteria", []):
            if criterion.get("score", 1.0) < 0.7:
                record.low_score_criteria.append(
                    LowScoreCriterion(
                        id=criterion["id"],
                        label=criterion.get("label", criterion["id"]),
                        score=criterion["score"],
                        suggestion=criterion.get("suggestion", ""),
                    )
                )

    # layout_proposal.json からエンジン結果を判定
    proposal_path = version_dir / "layout_proposal.json"
    if proposal_path.exists():
        with open(proposal_path) as f:
            proposals = json.load(f)
        has_issues = any(item.get("issues") for item in proposals)
        record.engine_result = "FAIL" if has_issues else "PASS"

    return record


def _version_sort_key(version: str) -> int:
    """v1, v2, ... をソートするためのキー."""
    match = re.match(r"v(\d+)", version)
    return int(match.group(1)) if match else 0


def _render_candidates_section(iterations_dir: Path) -> list[str]:
    """v0_candidates/comparison.json から戦略比較セクションを生成する."""
    comparison_path = iterations_dir / "v0_candidates" / "comparison.json"
    if not comparison_path.exists():
        return []

    with open(comparison_path) as f:
        data = json.load(f)

    strategies = data.get("strategies", [])
    if not strategies:
        return []

    lines: list[str] = []
    lines.append("## 戦略比較 (v0)")
    lines.append("")
    lines.append("| 候補 | 戦略名 | エンジン | スコア | 選択 |")
    lines.append("|------|--------|----------|--------|------|")

    for s in strategies:
        score_str = f"{s['overall_score']:.2f}" if s.get("overall_score") is not None else "-"
        selected_str = "**Winner**" if s.get("selected") else ""
        engine = s.get("engine_result", "N/A")
        lines.append(f"| {s['id'].upper()} | {s['name']} | {engine} | {score_str} | {selected_str} |")

    reason = data.get("reason", "")
    if reason:
        lines.append("")
        lines.append(f"**選択理由**: {reason}")

    # 各候補の画像
    lines.append("")
    for s in strategies:
        cid = s["id"]
        lines.append(f"![候補{cid.upper()}](v0_candidates/{cid}/layout_proposal.png)")
    lines.append("")
    lines.append("---")
    lines.append("")

    return lines


def _render_history_md(records: list[IterationRecord], iterations_dir: Path | None = None) -> str:
    """全IterationRecordからHISTORY.mdの内容を生成する."""
    lines: list[str] = []

    # ヘッダー
    lines.append("# レイアウトRefine履歴")
    lines.append("")

    # 戦略比較セクション（v0_candidatesが存在する場合）
    if iterations_dir is not None:
        lines.extend(_render_candidates_section(iterations_dir))

    # サマリーテーブル
    lines.append("## サマリー")
    lines.append("")
    lines.append("| Version | スコア | エンジン | 主な変更 |")
    lines.append("|---------|--------|----------|----------|")

    # サマリーはバージョン昇順
    for record in sorted(records, key=lambda r: _version_sort_key(r.version)):
        score_str = f"{record.overall_score:.2f}" if record.overall_score is not None else "-"
        changes_short = record.changes[:40] if record.changes else ("初回配置" if record.version == "v1" else "")
        lines.append(f"| {record.version} | {score_str} | {record.engine_result} | {changes_short} |")

    lines.append("")
    lines.append("---")
    lines.append("")

    # 各バージョン詳細（新しい順）
    for record in sorted(records, key=lambda r: _version_sort_key(r.version), reverse=True):
        lines.append(f"## {record.version} ({record.timestamp})")
        lines.append("")

        if record.strategy:
            # 長い戦略は先頭80文字に切り詰め
            strategy_display = record.strategy[:80] + ("..." if len(record.strategy) > 80 else "")
            lines.append(f"**戦略**: {strategy_display}")

        lines.append(f"**エンジン結果**: {record.engine_result}")

        if record.overall_score is not None:
            lines.append(f"**デザインスコア**: {record.overall_score:.2f}")
            for lc in record.low_score_criteria:
                lines.append(f"  - ⚠ {lc.label}: {lc.score:.2f} — {lc.suggestion}")

        if record.user_feedback:
            lines.append(f"**ユーザーFB**: {record.user_feedback}")

        if record.changes:
            lines.append(f"**変更内容**: {record.changes}")

        lines.append("")
        lines.append(f"![{record.version}]({record.version}/layout_proposal.png)")
        lines.append("")

    return "\n".join(lines)


def save_iteration(
    output_dir: Path,
    version: str,
    *,
    feedback: str = "",
    changes: str = "",
) -> None:
    """イテレーションのスナップショットを保存し、HISTORY.mdを更新する."""
    iterations_dir = output_dir / "iterations"
    version_dir = iterations_dir / version

    # 1. ディレクトリ作成
    version_dir.mkdir(parents=True, exist_ok=True)

    # 2. ファイルコピー
    copied = []
    for filename in _COPY_FILES:
        src = output_dir / filename
        if src.exists():
            shutil.copy2(src, version_dir / filename)
            copied.append(filename)

    if not copied:
        logger.warning("コピー対象ファイルが見つかりません: %s", output_dir)
        print(f"WARNING: {output_dir} にコピー対象ファイルがありません")
        return

    # 3. レコード構築
    record = _collect_record(version_dir, version)
    if feedback:
        record.user_feedback = feedback
    if changes:
        record.changes = changes

    # メタファイル保存
    meta_path = version_dir / "iteration_meta.json"
    with open(meta_path, "w") as f:
        f.write(record.model_dump_json(indent=2))

    # 4. 全バージョンスキャン → HISTORY.md 再生成
    all_records: list[IterationRecord] = []
    for vdir in sorted(iterations_dir.iterdir()):
        if vdir.is_dir() and re.match(r"v\d+", vdir.name):
            r = _collect_record(vdir, vdir.name)
            all_records.append(r)

    history_md = _render_history_md(all_records, iterations_dir)
    history_path = iterations_dir / "HISTORY.md"
    history_path.write_text(history_md, encoding="utf-8")

    # 5. 結果報告
    print(f"=== イテレーション記録: {version} ===")
    print(f"  保存先: {version_dir}")
    print(f"  コピー: {', '.join(copied)}")
    if record.overall_score is not None:
        print(f"  スコア: {record.overall_score:.2f}")
    print(f"  エンジン: {record.engine_result}")
    if feedback:
        print(f"  FB: {feedback}")
    if changes:
        print(f"  変更: {changes}")
    print(f"  履歴: {history_path}")


def save_candidates(output_dir: Path) -> None:
    """candidates/ を iterations/v0_candidates/ にアーカイブする.

    symlinkは実体ファイルとしてコピーし、自己完結したアーカイブを作る。
    """
    candidates_dir = output_dir / "candidates"
    if not candidates_dir.is_dir():
        print(f"ERROR: {candidates_dir} が見つかりません")
        raise SystemExit(1)

    iterations_dir = output_dir / "iterations"
    dest_dir = iterations_dir / "v0_candidates"

    # 既存があれば削除して再作成
    if dest_dir.exists():
        shutil.rmtree(dest_dir)

    # symlinkを実体としてコピー（follow_symlinks=True がデフォルト）
    shutil.copytree(candidates_dir, dest_dir, symlinks=False)

    # HISTORY.md を再生成
    all_records: list[IterationRecord] = []
    for vdir in sorted(iterations_dir.iterdir()):
        if vdir.is_dir() and re.match(r"v\d+", vdir.name):
            r = _collect_record(vdir, vdir.name)
            all_records.append(r)

    history_md = _render_history_md(all_records, iterations_dir)
    history_path = iterations_dir / "HISTORY.md"
    history_path.write_text(history_md, encoding="utf-8")

    print("=== 候補アーカイブ: v0_candidates ===")
    print(f"  保存先: {dest_dir}")
    # 候補一覧
    for cand_dir in sorted(dest_dir.iterdir()):
        if cand_dir.is_dir():
            engine = "N/A"
            proposal_path = cand_dir / "layout_proposal.json"
            if proposal_path.exists():
                with open(proposal_path) as f:
                    proposals = json.load(f)
                has_issues = any(item.get("issues") for item in proposals)
                engine = "FAIL" if has_issues else "PASS"
            print(f"  候補 {cand_dir.name}: エンジン={engine}")
    print(f"  履歴: {history_path}")


def main() -> None:
    """CLI エントリポイント."""
    parser = argparse.ArgumentParser(description="Refineループのイテレーション記録")
    parser.add_argument("output_dir", type=Path, help="出力ディレクトリ")
    parser.add_argument("version", help="バージョン（例: v1, v0_candidates）")
    parser.add_argument("--feedback", default="", help="ユーザーのフィードバック")
    parser.add_argument("--changes", default="", help="前バージョンからの変更サマリー")
    parser.add_argument("--candidates-dir", action="store_true", help="candidates/をアーカイブ")

    args = parser.parse_args()

    if not args.output_dir.is_dir():
        print(f"ERROR: {args.output_dir} はディレクトリではありません")
        raise SystemExit(1)

    if args.candidates_dir:
        save_candidates(args.output_dir)
    else:
        save_iteration(
            args.output_dir,
            args.version,
            feedback=args.feedback,
            changes=args.changes,
        )


if __name__ == "__main__":
    main()
