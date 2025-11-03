
# 昨日の日付を取得
YESTERDAY=$(date -v-1d +%Y-%m-%d)
# 1年前の日付を取得
ONE_YEAR_AGO=$(date -v-1y +%Y-%m-%d)

echo $ONE_YEAR_AGO ~ $YESTERDAY

uv run python -m daily_trade.scripts.build_dataset \
  --config ./config/dataset_config.yaml \
  --start $ONE_YEAR_AGO \
  --end $YESTERDAY \
  --output ./data/ohlcv/latest_dataset.parquet
