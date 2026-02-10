"""RealEstateAggregatorの実データでの検証テスト."""

import os

from dotenv import load_dotenv

from real_state_geo_core.data.fetcher import RealEstateDataFetcher
from real_state_geo_core.processing.aggregator import RealEstateAggregator

# .envファイルから環境変数を読み込み
load_dotenv()

api_key = os.getenv("REINFOLIB_API_KEY")
if not api_key:
    print("エラー: REINFOLIB_API_KEYが設定されていません")
    exit(1)

print("=== 江東区2024年データの取得 ===")
fetcher = RealEstateDataFetcher(api_key=api_key)
api_response = fetcher.fetch_real_estate(year="2024", city_code="13108")

if not api_response:
    print("エラー: APIからのデータ取得に失敗しました")
    exit(1)

df = fetcher.clean_real_estate_data(api_response)
if df is None or len(df) == 0:
    print("エラー: データのクリーニングに失敗しました")
    exit(1)

print(f"取得したデータ件数: {len(df)}件")
print()

print("=== 地域別集計（外れ値除外あり）===")
aggregator = RealEstateAggregator(df)
result = aggregator.aggregate_by_region(
    group_by="DistrictName", metrics=["mean", "median", "count"], price_unit="both", exclude_outliers=True
)

# 上位10地区を表示
print("坪単価上位10地区:")
print(result.sort("price_per_tsubo_mean", descending=True).head(10))
print()

print("=== 全体統計サマリー ===")
df_with_price = aggregator.calculate_sqm_price(df)
stats_sqm = aggregator.get_summary_statistics(df_with_price, "price_per_sqm")
print("㎡単価の統計:")
for key, value in stats_sqm.items():
    if key == "count":
        print(f"  {key}: {value:.0f}件")
    else:
        print(f"  {key}: {value:,.2f}円/㎡")

df_with_tsubo = aggregator.calculate_tsubo_price(df)
stats_tsubo = aggregator.get_summary_statistics(df_with_tsubo, "price_per_tsubo")
print("\n坪単価の統計:")
for key, value in stats_tsubo.items():
    if key == "count":
        print(f"  {key}: {value:.0f}件")
    else:
        print(f"  {key}: {value:,.2f}円/坪")

print("\n実データでの検証が完了しました。")
