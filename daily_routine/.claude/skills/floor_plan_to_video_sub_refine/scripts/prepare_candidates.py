"""戦略探索の候補ディレクトリを準備する.

各候補ディレクトリに共有入力ファイルへのsymlinkを張り、
placement_engine.py が独立して実行できる環境を作る。

Usage:
    uv run python poc/3dcg_poc3/prepare_candidates.py <output_dir> --candidates a b c
"""

import argparse
import logging
from pathlib import Path

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# --- Pydantic モデル ---


class CandidateStrategy(BaseModel):
    """1候補の戦略メタデータ."""

    id: str = Field(description="候補ID (a, b, c)")
    name: str = Field(description="戦略名 (例: '西壁集約型')")
    description: str = Field(description="戦略の定性的説明")
    engine_result: str = Field(default="N/A", description="PASS / FAIL / ERROR")
    overall_score: float | None = Field(default=None, description="デザインスコア")
    selected: bool = Field(default=False, description="ユーザーが選択したか")


class CandidateComparison(BaseModel):
    """候補戦略の比較メタデータ."""

    strategies: list[CandidateStrategy] = Field(description="候補戦略リスト")
    winner: str | None = Field(default=None, description="選択された候補ID")
    reason: str = Field(default="", description="選択理由")


# --- symlink対象ファイル ---

_SHARED_FILES = [
    "assets.json",
    "room_info.json",
    "walls.json",
    "floor_plan_complete.svg",
    "floor_plan_complete.png",
    "scoring_criteria.json",
]


def prepare_candidates(output_dir: Path, candidate_ids: list[str]) -> Path:
    """候補ディレクトリを作成し、共有ファイルへのsymlinkを張る.

    Returns:
        candidates_dir のパス
    """
    candidates_dir = output_dir / "candidates"
    candidates_dir.mkdir(parents=True, exist_ok=True)

    for cid in candidate_ids:
        cand_dir = candidates_dir / cid
        cand_dir.mkdir(parents=True, exist_ok=True)

        for filename in _SHARED_FILES:
            src = output_dir / filename
            dst = cand_dir / filename
            if dst.exists() or dst.is_symlink():
                dst.unlink()
            if src.exists():
                # 相対symlinkで張る（../../filename）
                dst.symlink_to(Path("../..") / filename)
                logger.info("symlink: %s -> %s", dst, src)
            else:
                logger.warning("共有ファイルが見つかりません: %s", src)

        print(f"  候補 {cid}: {cand_dir}")

    print(f"=== {len(candidate_ids)}候補のディレクトリを準備しました ===")
    return candidates_dir


def main() -> None:
    """CLI エントリポイント."""
    parser = argparse.ArgumentParser(description="戦略探索の候補ディレクトリ準備")
    parser.add_argument("output_dir", type=Path, help="出力ディレクトリ")
    parser.add_argument(
        "--candidates",
        nargs="+",
        default=["a", "b", "c"],
        help="候補ID (デフォルト: a b c)",
    )

    args = parser.parse_args()

    if not args.output_dir.is_dir():
        print(f"ERROR: {args.output_dir} はディレクトリではありません")
        raise SystemExit(1)

    prepare_candidates(args.output_dir, args.candidates)


if __name__ == "__main__":
    main()
