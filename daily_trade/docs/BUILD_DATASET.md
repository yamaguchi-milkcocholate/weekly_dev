# 📊 build_dataset.py 実行手順書

`build_dataset.py`は、株価データの取得から特徴量生成、機械学習用データセット構築までの全パイプラインを自動化する CLI ツールです。

## 🚀 クイックスタート

### 最小限の実行例

```bash
# 基本的な実行
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbol-category popular \
  --start 2024-01-01 \
  --end 2024-12-31
```

## 📋 事前準備

### 1. 環境設定

```bash
# プロジェクトルートに移動
cd /path/to/daily_trade

# 依存パッケージの確認
uv sync
```

### 2. 利用可能な銘柄カテゴリの確認

```bash
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset --list-categories
```

**出力例:**

```
📋 利用可能な銘柄カテゴリ:
  popular     : 人気米国株 (FAANG + 主要銘柄) - 20銘柄
               AAPL(Apple Inc.) AMZN(Amazon.com Inc.) GOOGL(Alphabet Inc.) ...

  dow30       : ダウ平均構成銘柄 (代表的な30銘柄) - 30銘柄
               AAPL(Apple Inc.) MSFT(Microsoft Corporation) ...

  sp500_tech  : S&P500テクノロジーセクター主要銘柄 - 20銘柄
               AAPL(Apple Inc.) MSFT(Microsoft Corporation) ...

  etf         : 主要ETF - 15銘柄
               SPY(SPDR S&P 500 ETF Trust) QQQ(Invesco QQQ Trust) ...

  jp_major    : 日本主要銘柄 - 15銘柄
               7203.T(トヨタ自動車株式会社) 6758.T(ソニーグループ株式会社) ...
```

## 💼 実行パターン

### パターン 1: 事前定義銘柄カテゴリを使用（推奨）

#### 単一カテゴリ

```bash
# 人気米国株での実行
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbol-category popular \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --output ./data/popular_2024.parquet
```

#### 複数カテゴリの組み合わせ

```bash
# 人気株 + ETFの組み合わせ
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbol-category popular etf \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --output ./data/mixed_portfolio_2024.parquet
```

#### 多様なポートフォリオ

```bash
# 米国株 + 日本株 + ETFの包括的ポートフォリオ
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbol-category popular dow30 jp_major etf \
  --start 2023-01-01 \
  --end 2024-12-31 \
  --min-days 50 \
  --output ./data/global_portfolio.parquet
```

### パターン 2: 手動銘柄指定

```bash
# 特定銘柄のみ
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbols AAPL MSFT GOOGL AMZN NVDA \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --validate-symbols \
  --output ./data/tech_giants_2024.parquet
```

### パターン 3: YAML 設定ファイル使用

#### 設定ファイル作成例 (`config/build_config.yaml`)

```yaml
# データセット構築設定
symbols:
  - AAPL
  - MSFT
  - GOOGL
start_date: "2024-01-01"
end_date: "2024-12-31"
interval: "1d"
margin_pct: 0.01
output_path: "./data/custom_dataset.parquet"
winsorize_pct: 0.01
min_trading_days: 100
validate_symbols: true
```

#### 設定ファイルでの実行

```bash
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config config/build_config.yaml
```

## ⚙️ 主要オプション詳細

### 🎯 銘柄選択オプション

| オプション          | 説明                 | 例                              |
| ------------------- | -------------------- | ------------------------------- |
| `--symbols`         | 手動銘柄指定         | `--symbols AAPL MSFT GOOGL`     |
| `--symbol-category` | 事前定義カテゴリ選択 | `--symbol-category popular etf` |
| `--list-categories` | カテゴリ一覧表示     | `--list-categories`             |

### 📅 期間設定オプション

| オプション   | 説明       | 形式       | 例                   |
| ------------ | ---------- | ---------- | -------------------- |
| `--start`    | 開始日     | YYYY-MM-DD | `--start 2024-01-01` |
| `--end`      | 終了日     | YYYY-MM-DD | `--end 2024-12-31`   |
| `--interval` | データ間隔 | 1d/1wk/1mo | `--interval 1d`      |

### 🔧 前処理オプション

| オプション    | 説明             | デフォルト | 例                 |
| ------------- | ---------------- | ---------- | ------------------ |
| `--margin`    | 上昇判定マージン | 0.01 (1%)  | `--margin 0.015`   |
| `--winsorize` | 外れ値処理閾値   | 0.01 (1%)  | `--winsorize 0.02` |
| `--min-days`  | 最小取引日数     | 100 日     | `--min-days 50`    |

### ✅ 検証オプション

| オプション           | 説明                     | デフォルト |
| -------------------- | ------------------------ | ---------- |
| `--validate-symbols` | 銘柄有効性検証           | True       |
| `--no-validate`      | 検証スキップ（高速実行） | False      |

### 📁 出力オプション

| オプション  | 説明             | デフォルト                            |
| ----------- | ---------------- | ------------------------------------- |
| `--output`  | 出力ファイルパス | `./data/daily_ohlcv_features.parquet` |
| `--verbose` | 詳細ログ出力     | False                                 |

## 🎯 実用的な使用ケース

### ケース 1: 日々のデータ更新

```bash
# 前日までのデータで更新
TODAY=$(date +%Y-%m-%d)
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbol-category popular \
  --start 2024-01-01 \
  --end $TODAY \
  --output ./data/daily_update.parquet
```

### ケース 2: バックテスト用データ準備

```bash
# 長期間のバックテスト用データ
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbol-category popular dow30 \
  --start 2020-01-01 \
  --end 2024-12-31 \
  --min-days 200 \
  --output ./data/backtest_5years.parquet
```

### ケース 3: 高速プロトタイピング

```bash
# 検証なしで高速実行
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbol-category popular \
  --start 2024-10-01 \
  --end 2024-12-31 \
  --no-validate \
  --min-days 20 \
  --output ./data/prototype.parquet
```

### ケース 4: 特定セクター分析

```bash
# テクノロジーセクター特化
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbol-category sp500_tech \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --margin 0.02 \
  --output ./data/tech_sector_2024.parquet
```

## 📊 出力データ構造

### 生成される特徴量（43 種類）

#### 価格関連指標

- **基本統計**: `ret_1d`, `ret_5d`, `ret_10d` (リターン率)
- **移動平均**: `sma_5`, `sma_10`, `sma_20`, `sma_50`, `ema_21`
- **トレンド**: `slope_20`, `slope_pct_20`

#### ボラティリティ指標

- **ATR**: `atr_14`, `atr_pct_14`
- **ボリンジャーバンド**: `bb_upper_20`, `bb_lower_20`, `bb_middle_20`, `bb_width_20`, `bb_pband_20`
- **標準偏差**: `stdev_20`

#### 出来高指標

- **出来高比**: `vol_ratio_20`, `tov_ratio_20`
- **蓄積分布**: `vpt`, `obv`

#### モメンタム指標

- **RSI**: `rsi_14`
- **MACD**: `macd`, `macd_signal`, `macd_hist`
- **ストキャスティクス**: `stoch_k`, `stoch_d`

#### その他テクニカル指標

- **ウィリアムズ%R**: `williams_r`
- **CCI**: `cci`
- **ADX**: `adx`, `adx_pos`, `adx_neg`

#### 時間的特徴量

- **日付関連**: `dow`, `month`, `quarter`, `day_of_month`

#### ターゲット変数

- **翌日リターン**: `next_ret`
- **上昇フラグ**: `y_up` (1: 上昇, 0: 下降/横ばい)

### データセットサンプル

```
timestamp           symbol  open    high    low     close   next_ret  y_up  ret_1d   sma_20    ...
2024-01-02 14:00:00 AAPL   185.64  186.89  185.55  185.64   0.0123    1    0.0056   184.23    ...
2024-01-02 14:00:00 MSFT   376.04  378.53  375.21  376.04  -0.0087    0    0.0091   374.87    ...
```

## 🚨 トラブルシューティング

### よくあるエラーと対処法

#### 1. ModuleNotFoundError

```bash
# エラー: ModuleNotFoundError: No module named 'daily_trade'
# 対処: PYTHONPATHの設定確認
export PYTHONPATH=./src
```

#### 2. 銘柄データ取得失敗

```bash
# エラー: 有効な銘柄が見つかりませんでした
# 対処: 銘柄コードの確認、または--no-validateオプション使用
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbols INVALID_SYMBOL \
  --no-validate \
  --start 2024-01-01 --end 2024-12-31
```

#### 3. 最小取引日数不足

```bash
# エラー: Final result is empty after preprocessing
# 対処: --min-daysオプションで閾値を下げる
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbol-category popular \
  --start 2024-11-01 --end 2024-12-31 \
  --min-days 10
```

#### 4. ファイル権限エラー

```bash
# エラー: Permission denied
# 対処: 出力ディレクトリの権限確認
mkdir -p ./data
chmod 755 ./data
```

## 📈 パフォーマンス最適化

### 高速化のコツ

1. **検証スキップ**: `--no-validate`で銘柄検証をスキップ
2. **期間短縮**: 必要最小限の期間に絞る
3. **銘柄数制限**: 大量銘柄を避ける
4. **並列実行**: 複数期間の場合は並列実行を検討

### メモリ使用量の目安

| 銘柄数   | 期間 | 推定メモリ使用量 | 推定実行時間 |
| -------- | ---- | ---------------- | ------------ |
| 20 銘柄  | 1 年 | ~500MB           | ~2 分        |
| 50 銘柄  | 2 年 | ~2GB             | ~5 分        |
| 100 銘柄 | 5 年 | ~8GB             | ~15 分       |

## 🔧 設定ファイル管理

### 銘柄設定ファイル (`config/symbols.yaml`)

新しい銘柄カテゴリを追加する場合:

```yaml
symbol_categories:
  custom_tech:
    description: "カスタムテック銘柄"
    symbols:
      - symbol: "AAPL"
        name: "Apple Inc."
        sector: "Technology"
      - symbol: "MSFT"
        name: "Microsoft Corporation"
        sector: "Technology"
```

### 実行設定テンプレート

#### 本番環境用設定

```yaml
# production_config.yaml
symbols: [] # カテゴリ指定のため空
start_date: "2023-01-01"
end_date: "2024-12-31"
interval: "1d"
margin_pct: 0.01
output_path: "./data/production_dataset.parquet"
winsorize_pct: 0.005
min_trading_days: 150
validate_symbols: true
```

#### 開発環境用設定

```yaml
# development_config.yaml
symbols: ["AAPL", "MSFT", "GOOGL"]
start_date: "2024-10-01"
end_date: "2024-12-31"
interval: "1d"
margin_pct: 0.015
output_path: "./data/dev_dataset.parquet"
winsorize_pct: 0.02
min_trading_days: 20
validate_symbols: false
```

## 📋 チェックリスト

### 実行前チェック

- [ ] 環境変数 `PYTHONPATH=./src` が設定済み
- [ ] 出力ディレクトリが存在し、書き込み権限がある
- [ ] 必要な銘柄カテゴリが設定ファイルに定義済み
- [ ] 期間設定が適切（開始日 < 終了日）
- [ ] インターネット接続が安定している（yfinance API 用）

### 実行後チェック

- [ ] 出力ファイルが正常に生成された
- [ ] ログにエラーメッセージがない
- [ ] データセット統計が期待値内
- [ ] 特徴量数が 43 個になっている
- [ ] ターゲット変数 `y_up` の分布が妥当

## 🤝 サポート

### ログの確認

```bash
# 詳細ログで実行
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbol-category popular \
  --start 2024-01-01 --end 2024-12-31 \
  --verbose
```

### ヘルプの表示

```bash
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset --help
```

---

**更新日**: 2025 年 10 月 27 日  
**作成者**: AI Trading System Team  
**バージョン**: 1.0.0
