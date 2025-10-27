# 📘 機能設計書

**システム名称:** 1 日 1 トレード AI システム（Phase 1：方向予測モデル構築）

---

## 1. システム構成概要

### 1.1 全体構造図

```
┌─────────────────────────────┐
│      daily_trade (プロジェクトルート)        │
│─────────────────────────────│
│  ├── data/                        # 生データ・特徴量・モデル格納先
│  ├── logs/                        # 実行ログ
│  ├── config/                      # YAML設定ファイル
│  ├── src/daily_trade              # ソースコード
│  │   ├── data/                    # データパイプライン関連
│  │   │   ├── __init__.py          # パッケージ化
│  │   │   ├── loader.py            # DataLoader（yfinance API）
│  │   │   ├── preprocessor.py      # Preprocessor（異常値処理）
│  │   │   └── feature_builder.py   # FeatureBuilder（テクニカル指標）
│  │   ├── data_pipeline.py         # 統合インポート（後方互換性）
│  │   ├── target_generator.py      # TargetGenerator
│  │   ├── model_direction.py       # DirectionModel (LightGBM)
│  │   ├── utils/logger.py          # Loggingユーティリティ
│  │   └── scripts/
│  │        ├── build_dataset.py    # CLI: データ取得～特徴量生成
│  │        └── train_model.py      # CLI: 学習～評価～モデル保存
│  └── tests/                       # pytestユニットテスト
└─────────────────────────────┘
```

---

## 2. クラス設計

### 2.1 `DataLoader`

| 項目         | 内容                                                                      |
| ------------ | ------------------------------------------------------------------------- |
| 役割         | yfinance を用いて指定銘柄の OHLCV（日足）データを取得し、標準化して返す   |
| クラス名     | `DataLoader`                                                              |
| ファイルパス | `src/daily_trade/data/loader.py`                                          |
| 設定クラス   | `LoadConfig`                                                              |
| 主要メソッド | `load_ohlcv(symbols: List[str]) -> pd.DataFrame`                          |
| 入力         | 銘柄コードリスト、期間設定                                                |
| 出力         | DataFrame: `timestamp, symbol, open, high, low, close, adj_close, volume` |
| ライブラリ   | `yfinance`, `pandas`, `tenacity`                                          |
| エラー処理   | tenacity 使用リトライ 3 回、失敗時はログ警告                              |
| 保存先       | `./data/ohlcv/`（Parquet 形式）                                           |

#### 擬似コード・使用例

```python
# 統合インポート（推奨）
from daily_trade.data_pipeline import DataLoader, LoadConfig

# 個別インポート（詳細制御時）
from daily_trade.data.loader import DataLoader, LoadConfig

class DataLoader:
    def __init__(self, cfg: LoadConfig):
        self.cfg = cfg

    def load_ohlcv(self, symbols):
        frames = []
        for s in symbols:
            df = yf.download(...)
            df = self._clean(df)
            frames.append(df.assign(symbol=s))
        return pd.concat(frames)
```

---

### 2.2 `Preprocessor`

| 項目         | 内容                                                          |
| ------------ | ------------------------------------------------------------- |
| 役割         | データの異常値・欠損値の補正、日付整列、Winsorize 処理        |
| クラス名     | `Preprocessor`                                                |
| ファイルパス | `src/daily_trade/data/preprocessor.py`                        |
| 設定クラス   | `PreprocessConfig`                                            |
| 主要メソッド | `clean(df: pd.DataFrame) -> pd.DataFrame`                     |
| 処理概要     | volume=0 の除外、値幅異常のクリッピング、timestamp 昇順ソート |
| ライブラリ   | `pandas`, `scipy.stats`                                       |
| 出力         | 加工済 DataFrame                                              |

---

### 2.3 `FeatureBuilder`

| 項目           | 内容                                           |
| -------------- | ---------------------------------------------- |
| 役割           | OHLCV データから方向予測モデル用の特徴量を生成 |
| クラス名       | `FeatureBuilder`                               |
| ファイルパス   | `src/daily_trade/data/feature_builder.py`      |
| 設定クラス     | `FeatureConfig`                                |
| 主要メソッド   | `build(df: pd.DataFrame) -> pd.DataFrame`      |
| 出力           | 特徴量付き DataFrame（37 種類の特徴量）        |
| 依存ライブラリ | `ta`, `numpy`, `pandas`                        |

#### 主要特徴量一覧（37 種類）

| 種別           | 名称                                                                                           | 算出方法                                |
| -------------- | ---------------------------------------------------------------------------------------------- | --------------------------------------- |
| トレンド       | sma_5, sma_10, sma_20, sma_50, ema_21, slope_20, slope_pct_20                                  | 移動平均、価格勾配                      |
| ボラティリティ | atr_14, atr_pct_14, stdev_20, bb_upper_20, bb_lower_20, bb_middle_20, bb_width_20, bb_pband_20 | ATR、ボリンジャーバンド                 |
| 出来高         | vol_ratio_20, tov_ratio_20, vpt, obv                                                           | 出来高比、VPT、OBV                      |
| モメンタム     | ret_1d, ret_5d, ret_10d, rsi_14, macd, macd_signal, macd_hist, stoch_k, stoch_d                | リターン、RSI、MACD、ストキャスティクス |
| テクニカル     | williams_r, cci, adx, adx_pos, adx_neg                                                         | ウィリアムズ%R、CCI、ADX                |
| 季節性         | dow, month, quarter, day_of_month                                                              | 曜日、月、四半期、日付                  |

#### 出力カラム例

`[timestamp, symbol, open, high, low, close, adj_close, volume, ret_1d, sma_20, atr_14, vol_ratio_20, dow, month, ...]`

---

### 2.4 `TargetGenerator`

| 項目         | 内容                                                                    |
| ------------ | ----------------------------------------------------------------------- |
| 役割         | 翌日リターンと方向ラベルを作成                                          |
| クラス名     | `TargetGenerator`                                                       |
| ファイルパス | `src/daily_trade/target_generator.py`                                   |
| 設定クラス   | `TargetConfig`                                                          |
| 主要メソッド | `make_targets(df: pd.DataFrame, margin_pct: float) -> pd.DataFrame`     |
| 処理概要     | `next_ret = (next_close / close - 1)`、`y_up = (next_ret > margin_pct)` |
| 出力         | `next_ret, y_up`を含む DataFrame                                        |
| 注意点       | 翌日データがない行は除外、時系列順序保持                                |

#### 主要機能

- **翌日リターン計算**: `next_ret = (next_close / close - 1)` の正確な実装
- **方向ラベル生成**: 指定されたマージン閾値による二値分類ラベル
- **データ品質管理**: 外れ値検出・除去、欠損値処理
- **時系列整合性**: 銘柄別処理でのデータ漏洩防止
- **統計サマリー**: up_rate、リターン分布の詳細ログ出力

---

### 2.5 `DirectionModel`

| 項目             | 内容                                                                      |
| ---------------- | ------------------------------------------------------------------------- |
| 役割             | 特徴量から翌日上昇確率を予測するモデル                                    |
| クラス名         | `DirectionModel`                                                          |
| 設定クラス       | `ModelConfig`                                                             |
| 主要メソッド     | `fit(X, y)`, `predict_proba(X)`, `evaluate(X, y)`, `cross_validate(X, y)` |
| 使用アルゴリズム | LightGBM（二値分類）                                                      |
| 評価指標         | ROC-AUC, Accuracy, Precision, Recall                                      |
| 検証方式         | TimeSeriesSplit（3 分割）                                                 |
| 保存             | `model.pkl`（pickle 化）                                                  |

**実装ファイル**: `src/daily_trade/model_direction.py`

**設定クラス**: `ModelConfig`

- LightGBM パラメータ: num_leaves, learning_rate, feature_fraction 等
- 交差検証設定: cv_splits, test_size_ratio
- 評価設定: pos_label, average

**主要機能**:

- 欠損値自動処理（前方補完 →0 埋め）
- TimeSeriesSplit 交差検証
- 特徴量重要度計算・表示
- モデル保存・読み込み

#### 評価例

```python
AUC = 0.585 ± 0.030, Accuracy = 0.753 ± 0.032
Feature importances:
['ret_1d', 'adx_pos', 'tov_ratio_20', 'atr_pct_14', 'adx_neg', ...]
```

---

### 2.6 `Logger`

| 項目     | 内容                                                         |
| -------- | ------------------------------------------------------------ |
| 役割     | 処理進捗・警告・エラーを統一形式で出力                       |
| クラス名 | `AppLogger`                                                  |
| 出力形式 | `[YYYY-MM-DD HH:MM:SS] LEVEL: message`                       |
| 保存先   | `./logs/run_YYYYMMDD.log`                                    |
| 使用例   | `logger.info("Features built for 5 symbols (records=6200)")` |

---

## 3. CLI 設計

### 3.1 `build_dataset.py`

| 項目       | 内容                                                              |
| ---------- | ----------------------------------------------------------------- |
| 目的       | データ取得～特徴量生成～ターゲット作成                            |
| 入力       | YAML 設定 or CLI 引数                                             |
| 出力       | `daily_ohlcv_features.parquet`                                    |
| 使用クラス | `DataLoader`, `Preprocessor`, `FeatureBuilder`, `TargetGenerator` |

**実装ファイル**: `src/daily_trade/scripts/build_dataset.py`

**主要機能**:

- マルチ銘柄データ取得
- 自動前処理・異常値処理
- 43 種類の特徴量生成
- ターゲット作成（margin_pct 対応）
- 詳細統計レポート出力

**コマンド例**:

```bash
# CLI引数指定
PYTHONPATH=./src python -m daily_trade.scripts.build_dataset \
  --symbols AAPL MSFT GOOGL \
  --start 2020-01-01 --end 2025-01-01 \
  --margin 0.01 --output ./data/dataset.parquet

# YAML設定ファイル
PYTHONPATH=./src python -m daily_trade.scripts.build_dataset \
  --config build_config.yaml
```

---

### 3.2 `train_model.py`

| 項目 | 内容                                                     |
| ---- | -------------------------------------------------------- |
| 目的 | 特徴量データを読み込み、方向予測モデルを学習・評価・保存 |
| 入力 | `daily_ohlcv_features.parquet`                           |
| 出力 | `direction_model.pkl`, 評価レポート（JSON）              |

**実装ファイル**: `src/daily_trade/scripts/train_model.py`

**主要機能**:

- 自動欠損値処理
- TimeSeriesSplit 交差検証
- LightGBM モデル学習
- 特徴量重要度分析
- JSON 評価レポート生成

**コマンド例**:

```bash
# CLI引数指定
PYTHONPATH=./src python -m daily_trade.scripts.train_model \
  --input ./data/dataset.parquet \
  --output ./models/model.pkl \
  --cv-splits 3 --n-estimators 100

# YAML設定ファイル
PYTHONPATH=./src python -m daily_trade.scripts.train_model \
  --config train_config.yaml
```

---

## 4. データフロー詳細

```mermaid
flowchart TD
A[DataLoader] --> B[Preprocessor]
B --> C[FeatureBuilder]
C --> D[TargetGenerator]
D --> E[DirectionModel.fit()]
E --> F[モデル評価/保存]
```

### 4.1 ファイル構造の変更について

データパイプライン関連のクラスは保守性向上のため以下のように分割しました：

- **src/daily_trade/data/loader.py**: `DataLoader`, `LoadConfig`
- **src/daily_trade/data/preprocessor.py**: `Preprocessor`, `PreprocessConfig`
- **src/daily_trade/data/feature_builder.py**: `FeatureBuilder`, `FeatureConfig`
- **src/daily_trade/data/**init**.py**: パッケージ化
- **src/daily_trade/data_pipeline.py**: 統合インポート（後方互換性）

既存コードでは引き続き `from daily_trade.data_pipeline import ...` が使用可能です。

---

## 5. データスキーマ

| カラム                            | 型                  | 説明           |
| --------------------------------- | ------------------- | -------------- |
| timestamp                         | datetime64[ns, JST] | 取引日         |
| symbol                            | str                 | 銘柄コード     |
| open, high, low, close, adj_close | float               | 価格データ     |
| volume                            | int                 | 出来高         |
| ret_1d, ret_5d, ret_10d           | float               | リターン率     |
| sma_20, ema_21, atr_14, stdev_20  | float               | テクニカル指標 |
| vol_ratio_20, tov_ratio_20        | float               | 出来高関連指標 |
| dow, month                        | int                 | 曜日・月       |
| next_ret                          | float               | 翌日リターン   |
| y_up                              | int(0/1)            | 翌日上昇ラベル |

---

## 6. モデル設定例 (`config/model.yaml`)

```yaml
model:
  name: "lightgbm_direction"
  type: "LGBMClassifier"
  params:
    learning_rate: 0.03
    n_estimators: 600
    num_leaves: 63
    subsample: 0.8
    colsample_bytree: 0.8
    random_state: 42
cv:
  method: "TimeSeriesSplit"
  n_splits: 5
metrics:
  - auc
  - accuracy
  - precision
  - recall
```

---

## 7. エラーハンドリング仕様

| ケース           | 対応                               |
| ---------------- | ---------------------------------- |
| API エラー       | リトライ 3 回後にログ警告          |
| NaN 多数         | 該当銘柄を除外（ログ出力）         |
| ファイル保存失敗 | フルパスと例外メッセージをログ出力 |
| モデル訓練失敗   | 設定・データ形状をダンプして保存   |

---

## 8. ログ出力例

```
[2025-10-25 10:03:21] INFO: Start DataLoader (symbols=5)
[2025-10-25 10:03:23] WARN: Missing data for 6758.T on 2021-12-30
[2025-10-25 10:03:25] INFO: Features built (records=6200)
[2025-10-25 10:03:26] INFO: Train fold 1/5 AUC=0.561
[2025-10-25 10:03:31] INFO: CV AUC mean=0.573 model saved to direction_model.pkl
```

---

## 9. テスト項目一覧

| テスト区分 | 内容             | 確認項目                     |
| ---------- | ---------------- | ---------------------------- |
| 単体       | FeatureBuilder   | 特徴量の NA 率／範囲／符号   |
| 単体       | TargetGenerator  | `next_ret`のずれ、`y_up`の値 |
| 結合       | build_dataset.py | ファイル生成とサイズ         |
| 結合       | train_model.py   | モデル出力と AUC 算出        |
| 回帰       | 全体             | 再実行で同一 AUC±0.001 以内  |

---

## 10. 完成条件（Done Criteria）

- [x] クラス構成・入出力が定義どおり動作
- [x] CLI でデータ生成～学習まで完走
- [x] モデル AUC>0.55
- [x] 主要特徴量 20 種以上を t 時点で算出
- [x] ログ・成果物が正しく生成

---

## 11. 将来拡張設計（Phase 2 以降）

| 機能                | 目的                         | 実装予定モジュール        |
| ------------------- | ---------------------------- | ------------------------- |
| LiquidityForecaster | 出来高分位推定（薄商い除外） | `liquidity_forecaster.py` |
| UniverseFilter      | ATR・出来高基準の銘柄選抜    | `universe_filter.py`      |
| Scorer              | 上昇確率 × 流動性でスコア化  | `scorer.py`               |
| SignalGenerator     | エントリー候補 1 銘柄選出    | `signal_generator.py`     |
| Backtester          | トレードシミュレーション     | `backtester.py`           |
