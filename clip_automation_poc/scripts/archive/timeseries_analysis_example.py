"""時系列統計分析の使用例."""

import logging
import os

from pathlib import Path

import polars as pl

from dotenv import load_dotenv

from real_state_geo_core.data.fetcher import RealEstateDataFetcher
from real_state_geo_core.processing.aggregator import RealEstateAggregator

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 環境変数の読み込み
load_dotenv()
API_KEY = os.getenv("REINFOLIB_API_KEY", "")


def main() -> None:
    """時系列統計分析のサンプル実行."""
    # データフェッチャーの初期化
    fetcher = RealEstateDataFetcher(api_key=API_KEY)

    # 港区（市区町村コード: 13103）の2020年～2024年のデータを取得
    city_code = "13103"
    start_year = 2020
    end_year = 2024

    logging.info(f"{start_year}年～{end_year}年の不動産データを取得中...")
    multi_year_df = fetcher.fetch_real_estate_multi_year(start_year, end_year, city_code)

    if multi_year_df is None or multi_year_df.height == 0:
        logging.error("データの取得に失敗しました")
        return

    logging.info(f"取得完了: {multi_year_df.height}件のデータ")

    # Aggregatorの初期化
    aggregator = RealEstateAggregator(multi_year_df)

    # 時系列×地域別の統計を計算（前年比付き）
    logging.info("時系列×地域別統計を計算中...")
    timeseries_stats = aggregator.aggregate_by_region_timeseries(
        year_column="Year",
        group_by="DistrictName",  # 地区名で集計
        metrics=["mean", "median", "count"],  # 平均、中央値、件数
        price_unit="both",  # ㎡単価と坪単価の両方
        exclude_outliers=True,  # 外れ値を除外
        percentile_range=(0.05, 0.95),  # 上下5%を外れ値として除外
        calculate_yoy=True,  # 前年比変化率を計算
    )

    # 結果を表示
    print("\n=== 時系列×地域別統計（前年比付き） ===")
    print(timeseries_stats)

    # CSVに保存
    output_dir = Path("output/timeseries")
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"timeseries_stats_{city_code}_{start_year}_{end_year}.csv"
    timeseries_stats.write_csv(output_path)
    logging.info(f"結果をCSVに保存: {output_path}")

    # 特定地区の時系列推移を抽出（例: 赤坂）
    if "DistrictName" in timeseries_stats.columns:
        akasaka_trend = timeseries_stats.filter(pl.col("DistrictName") == "赤坂")
        if akasaka_trend.height > 0:
            print("\n=== 赤坂の時系列推移 ===")
            print(akasaka_trend.select(["Year", "DistrictName", "price_per_sqm_mean", "price_per_sqm_mean_yoy_change"]))


if __name__ == "__main__":
    main()
