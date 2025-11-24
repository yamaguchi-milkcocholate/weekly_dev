# 📊 build_dataset.py 実行手順書

`build_dataset.py`は、株価データの取得から特徴量生成、機械学習用データセット構築までの全パイプラインを自動化する CLI ツールです。

## 🚀 クイックスタート

### 最小限の実行例

```bash
# 基本的な実行（設定ファイル必須）
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config dataset_config.yaml \
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

### パターン 1: 設定ファイル使用（推奨）

#### 基本実行

```bash
# build_config.yamlを用意して実行
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config build_config.yaml \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --output ./data/dataset_2024.parquet
```

#### 設定ファイル例 (`build_config.yaml`)

```yaml
# === 銘柄設定 ===
symbol_category: ["popular"] # 銘柄カテゴリ指定
# symbols: ["AAPL", "MSFT", "GOOGL"]  # または手動銘柄指定

# === データ期間 === (CLIで上書き可能)
# start_date: "2024-01-01"
# end_date: "2024-12-31"
interval: "1d"

# === ターゲット設定 ===
margin_pct: 0.01 # 方向判定マージン

# === 前処理設定 ===
winsorize_pct: 0.01 # 外れ値処理強度
min_trading_days: 100 # 最小取引日数

# === その他設定 ===
output_path: "./data/dataset.parquet"
validate_symbols: true
```

#### 複数カテゴリの組み合わせ

```yaml
# 多様なポートフォリオ設定例
symbol_category: ["popular", "etf", "jp_major"]
margin_pct: 0.01
winsorize_pct: 0.01
min_trading_days: 50
validate_symbols: true
```

### パターン 2: 銘柄カテゴリ確認

```bash
# 利用可能な銘柄カテゴリを確認
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset --list-categories
```

## ⚙️ 主要オプション詳細

### 🎯 必須オプション

| オプション | 説明              | 例                           |
| ---------- | ----------------- | ---------------------------- |
| `--config` | YAML 設定ファイル | `--config build_config.yaml` |

### 📅 期間設定オプション（設定ファイルを上書き）

| オプション | 説明   | 形式       | 例                   |
| ---------- | ------ | ---------- | -------------------- |
| `--start`  | 開始日 | YYYY-MM-DD | `--start 2024-01-01` |
| `--end`    | 終了日 | YYYY-MM-DD | `--end 2024-12-31`   |

### � 出力オプション

| オプション          | 説明                 | 例                                |
| ------------------- | -------------------- | --------------------------------- |
| `--output`          | 出力ファイルパス     | `--output ./data/dataset.parquet` |
| `--list-categories` | 銘柄カテゴリ一覧表示 | `--list-categories`               |

### 🔧 設定ファイル内パラメータ

| パラメータ         | 説明             | デフォルト | 推奨範囲         |
| ------------------ | ---------------- | ---------- | ---------------- |
| `symbol_category`  | 銘柄カテゴリ     | -          | ["popular"]      |
| `symbols`          | 手動銘柄指定     | []         | ["AAPL", "MSFT"] |
| `margin_pct`       | 上昇判定マージン | 0.01       | 0.0-0.02         |
| `winsorize_pct`    | 外れ値処理閾値   | 0.01       | 0.005-0.02       |
| `min_trading_days` | 最小取引日数     | 100        | 50-200           |
| `validate_symbols` | 銘柄有効性検証   | true       | true/false       |

## 🎯 実用的な使用ケース

### ケース 1: 日々のデータ更新

```bash
# 設定ファイルで銘柄設定、CLIで期間指定
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config build_config.yaml \
  --start 2024-01-01 \
  --end $(date +%Y-%m-%d) \
  --output ./data/daily_update.parquet
```

### ケース 2: バックテスト用データ準備

```yaml
# backtest_config.yaml
symbol_category: ["popular", "dow30"]
margin_pct: 0.01
min_trading_days: 200
validate_symbols: true
```

```bash
# 長期間のバックテスト用データ
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config backtest_config.yaml \
  --start 2020-01-01 \
  --end 2024-12-31 \
  --output ./data/backtest_5years.parquet
```

### ケース 3: 高速プロトタイピング

```yaml
# prototype_config.yaml
symbol_category: ["popular"]
margin_pct: 0.01
min_trading_days: 20
validate_symbols: false
```

```bash
# 検証なしで高速実行
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config prototype_config.yaml \
  --start 2024-10-01 \
  --end 2024-12-31 \
  --output ./data/prototype.parquet
```

### ケース 4: 特定セクター分析

```yaml
# tech_sector_config.yaml
symbol_category: ["sp500_tech"]
margin_pct: 0.02
winsorize_pct: 0.005
min_trading_days: 100
```

```bash
# テクノロジーセクター特化
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config tech_sector_config.yaml \
  --start 2024-01-01 \
  --end 2024-12-31 \
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

#### 2. 設定ファイルが見つからない

```bash
# エラー: No such file or directory: 'build_config.yaml'
# 対処: 設定ファイルの作成または正しいパス指定
ls build_config.yaml  # ファイル存在確認
```

#### 3. 銘柄データ取得失敗

```yaml
# エラー: 有効な銘柄が見つかりませんでした
# 対処: 設定ファイルでvalidate_symbolsをfalseに設定
validate_symbols: false
```

#### 4. 最小取引日数不足

```yaml
# エラー: Final result is empty after preprocessing
# 対処: min_trading_daysを下げる
min_trading_days: 10
```

#### 5. ファイル権限エラー

```bash
# エラー: Permission denied
# 対処: 出力ディレクトリの権限確認
mkdir -p ./data
chmod 755 ./data
```

## 📈 パフォーマンス最適化

### 高速化のコツ

1. **検証スキップ**: 設定ファイルで `validate_symbols: false`
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

### 設定ファイルテンプレート

#### 本番環境用設定 (`production_config.yaml`)

```yaml
# 本番環境用データセット構築設定
symbol_category: ["popular", "dow30"]
margin_pct: 0.01
winsorize_pct: 0.005
min_trading_days: 150
validate_symbols: true
output_path: "./data/production_dataset.parquet"
interval: "1d"
```

#### 開発環境用設定 (`development_config.yaml`)

```yaml
# 開発・実験用設定
symbol_category: ["popular"]
margin_pct: 0.015
winsorize_pct: 0.02
min_trading_days: 20
validate_symbols: false
output_path: "./data/dev_dataset.parquet"
interval: "1d"
```

#### 実験用設定 (`experiment_config.yaml`)

```yaml
# 実験パラメータ調整用
symbol_category: ["popular"]
margin_pct: 0.01 # ここを変更して実験
winsorize_pct: 0.01 # ここを変更して実験
min_trading_days: 100
validate_symbols: true
output_path: "./data/experiment_dataset.parquet"
interval: "1d"
```

## 📋 チェックリスト

### 実行前チェック

- [ ] 環境変数 `PYTHONPATH=./src` が設定済み
- [ ] **設定ファイル** (`build_config.yaml`) が存在し適切に設定済み
- [ ] 出力ディレクトリが存在し、書き込み権限がある
- [ ] 必要な銘柄カテゴリが設定ファイルに定義済み
- [ ] インターネット接続が安定している（yfinance API 用）

### 実行後チェック

- [ ] 出力ファイルが正常に生成された
- [ ] ログにエラーメッセージがない
- [ ] データセット統計が期待値内
- [ ] 特徴量数が 43 個になっている
- [ ] ターゲット変数 `y_up` の分布が妥当

## 🤝 サポート

### ヘルプの表示

```bash
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset --help
```

### 設定ファイル例の確認

```bash
# 銘柄カテゴリ一覧を確認
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset --list-categories

# 設定ファイルサンプルを参考に作成
cat > build_config.yaml << EOF
symbol_category: ["popular"]
margin_pct: 0.01
winsorize_pct: 0.01
min_trading_days: 100
validate_symbols: true
output_path: "./data/dataset.parquet"
interval: "1d"
EOF
```

---

**更新日**: 2025 年 10 月 27 日  
**作成者**: AI Trading System Team  
**バージョン**: 1.0.0
