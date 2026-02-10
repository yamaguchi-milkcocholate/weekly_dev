#!/usr/bin/env python3
"""2025年の集約統計量を算出するスクリプト

このスクリプトは、data/ml_dataset/tokyo_23_ml_dataset.csv から2025年のデータを抽出し、
Municipality × Year および NearestStation × Year で集約統計量（平均・中央値）を計算します。
"""

import logging
from pathlib import Path

import polars as pl

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """2025年の集約統計量を算出してCSV出力します。"""
    project_root = Path(__file__).parent.parent
    dataset_path = project_root / "data" / "ml_dataset" / "tokyo_23_ml_dataset.csv"
    output_dir = project_root / "outputs"
    output_path = output_dir / "aggregated_stats_2025.csv"

    # 出力ディレクトリ作成
    output_dir.mkdir(parents=True, exist_ok=True)

    logger.info(f"データ読み込み開始: {dataset_path}")

    # データ読み込み
    if not dataset_path.exists():
        logger.error(f"データセットが見つかりません: {dataset_path}")
        raise FileNotFoundError(f"データセットが見つかりません: {dataset_path}")

    df = pl.read_csv(dataset_path)
    logger.info(f"データセット読み込み完了: {df.height:,}件")

    # transaction_dateをDatetime型に変換（String型の場合）
    if df["transaction_date"].dtype == pl.String or df["transaction_date"].dtype == pl.Utf8:
        df = df.with_columns(pl.col("transaction_date").str.to_datetime())

    # 2025年のデータのみ抽出
    df_2025 = df.filter(pl.col("transaction_date").dt.year() == 2025)
    logger.info(f"2025年のデータ件数: {df_2025.height:,}件")

    if df_2025.height == 0:
        logger.warning("2025年のデータが見つかりません。処理を終了します。")
        return

    # Year列を追加
    df_2025 = df_2025.with_columns(pl.col("transaction_date").dt.year().alias("Year"))

    # Municipality × Year の集約
    logger.info("Municipality × Year の集約統計量を計算中...")
    municipality_stats = df_2025.group_by(["Municipality", "Year"]).agg(
        [
            pl.col("tsubo_price").mean().alias("Municipality_Year_mean_price"),
            pl.col("tsubo_price").median().alias("Municipality_Year_median_price"),
            pl.col("tsubo_price").count().alias("Municipality_Year_count"),
        ]
    )
    logger.info(f"Municipality × Year 集約: {municipality_stats.height}件")

    # NearestStation × Year の集約
    logger.info("NearestStation × Year の集約統計量を計算中...")
    station_stats = df_2025.group_by(["NearestStation", "Year"]).agg(
        [
            pl.col("tsubo_price").mean().alias("NearestStation_Year_mean_price"),
            pl.col("tsubo_price").median().alias("NearestStation_Year_median_price"),
            pl.col("tsubo_price").count().alias("NearestStation_Year_count"),
        ]
    )
    logger.info(f"NearestStation × Year 集約: {station_stats.height}件")

    # 両方の統計量を結合（Municipality + NearestStation + Year）
    # outer joinで全組み合わせを保持
    stats_df = municipality_stats.join(station_stats, on="Year", how="outer")

    # 保存
    stats_df.write_csv(output_path)
    logger.info(f"集約統計量を保存しました: {output_path}")
    logger.info(f"合計レコード数: {stats_df.height:,}件")

    # サマリー表示
    logger.info("\n=== 集約統計量サマリー ===")
    logger.info(f"Municipality種別数: {municipality_stats.height}")
    logger.info(f"NearestStation種別数: {station_stats.height}")
    logger.info(f"出力レコード数: {stats_df.height}")


if __name__ == "__main__":
    main()
