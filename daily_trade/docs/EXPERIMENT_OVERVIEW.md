# Daily Trade 実験仕様書

> **目的**: 実験サイクル（設定変更 → 実行 → 検証）による予測モデル最適化  
> **実験手順**: BUILD_DATASET.md → TRAIN_MODEL → 結果検証 → パラメータ調整  
> **更新日**: 2025-11-03

## 📋 目次

1. [実験ワークフロー](#実験ワークフロー)
2. [データセット構築の実験パラメータ](#データセット構築の実験パラメータ)
3. [モデル学習の実験パラメータ](#モデル学習の実験パラメータ)
4. [実験実行コマンド](#実験実行コマンド)
5. [実験記録テンプレート](#実験記録テンプレート)

## 実験ワークフロー

### 🔄 **基本実験サイクル**

```
1. パラメータ調整 → 2. データセット構築 → 3. モデル学習 → 4. 結果評価 → 1に戻る
   (設定ファイル)     (build_dataset.py)    (train_model.py)   (AUC確認)
```

### **実験で使用するファイル**

**設定ファイル**:

- `daily_trade/config/model_config.yaml` - モデル学習設定（LightGBM パラメータ含む）
- `daily_trade/config/dataset_config.yaml` - データセット構築設定

**実行コマンド**:

```bash
# Step 0: 作業ディレクトリ移動（必須）
cd /path/to/daily_trade

# Step 1: データセット構築（設定ファイル必須）
# 最近1年間のデータを使用
YESTERDAY=$(date -v-1d +%Y-%m-%d)
ONE_YEAR_AGO=$(date -v-1y +%Y-%m-%d)
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config config/dataset_config.yaml \
  --start $ONE_YEAR_AGO \
  --end $YESTERDAY \
  --output ./data/dataset.parquet

# Step 2: モデル学習
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --config config/model_config.yaml
```

**出力確認**:

- `daily_trade/models/*_report.json` - 学習結果レポート
- `daily_trade/logs/run_*.log` - 実行ログ

---

## データセット構築の実験パラメータ

### 🔄 **変更対象: 特徴量生成パラメータ（ソースコード変更が必要）**

これらのパラメータは実験で調整し、モデル性能への影響を検証する対象です。

#### **🚀 実験優先度順**

#### **🔥 最高優先度 - トレンド系特徴量**

```python
# daily_trade/src/daily_trade/data/feature_builder.py の FeatureConfig クラス
sma_windows: list[int] = [5, 10, 20, 50]     # SMA期間リスト
ema_windows: list[int] = [21]                # EMA期間リスト
slope_window: int = 20                       # 価格傾き期間
```

**実験候補値**:

```python
# 短期重視
sma_windows: [3, 7, 14, 30]
ema_windows: [12, 21]
slope_window: 10

# 標準設定（現在値）
sma_windows: [5, 10, 20, 50]
ema_windows: [21]
slope_window: 20

# 長期重視
sma_windows: [10, 20, 50, 100, 200]
ema_windows: [26, 50]
slope_window: 30
```

#### **⚡ 高優先度 - モメンタム系特徴量**

```python
return_windows: list[int] = [1, 5, 10]       # リターン期間リスト
rsi_window: int = 14                         # RSI期間
macd_windows: tuple = (12, 26, 9)           # MACD設定(fast, slow, signal)
```

**実験候補値**:

```python
# 短期重視
return_windows: [1, 2, 3, 5]
rsi_window: 9
macd_windows: (8, 17, 9)

# 標準設定（現在値）
return_windows: [1, 5, 10]
rsi_window: 14
macd_windows: (12, 26, 9)

# 長期重視
return_windows: [1, 5, 10, 20]
rsi_window: 21
macd_windows: (19, 39, 9)
```

#### **中優先度 - ボラティリティ・出来高系特徴量**

```python
atr_window: int = 14                         # ATR期間
stdev_window: int = 20                       # 標準偏差期間
bollinger_window: int = 20                   # ボリンジャーバンド期間
bollinger_std: float = 2.0                   # BB標準偏差倍数
volume_ratio_window: int = 20                # 出来高比率期間
```

**実験候補値**:

```python
# 保守的設定
atr_window: 21
bollinger_std: 1.5

# 標準設定（現在値）
atr_window: 14
bollinger_std: 2.0

# アグレッシブ設定
atr_window: 10
bollinger_std: 2.5
```

### 🔒 **固定対象: その他全パラメータ**

以下のパラメータは実験中は固定値として使用します。

#### **データ取得関連（固定）**

```yaml
symbol_category: ["popular"] # 人気銘柄に固定
interval: "1d" # 日次データに固定
validate_symbols: true # 検証は有効に固定
```

#### **期間設定（固定）**

```bash
# 最近1年間のデータを使用（実験間の一貫性確保）
YESTERDAY=$(date -v-1d +%Y-%m-%d)      # 昨日まで
ONE_YEAR_AGO=$(date -v-1y +%Y-%m-%d)   # 1年前から
```

#### **ターゲット生成（固定）**

```yaml
margin_pct: 0.01 # 1%マージンに固定
min_return_threshold: -0.5 # -50%に固定
max_return_threshold: 0.5 # +50%に固定
remove_incomplete_days: true # 除去有効に固定
```

#### **前処理パラメータ（固定）**

```yaml
winsorize_pct: 0.01 # 1%に固定
min_trading_days: 100 # 100日に固定
remove_zero_volume: true # 除去有効に固定
winsorize_enabled: true # 処理有効に固定
outlier_detection_window: 60 # 60日に固定
outlier_threshold: 10.0 # 10σに固定
```

#### **出力設定（固定）**

```yaml
output_path: "./data/dataset.parquet" # 固定パス
```

---

## モデル学習の実験パラメータ

### 🔄 **変更対象: LightGBM パラメータ**

これらのパラメータは実験で調整し、モデル性能への影響を検証する対象です。

#### **🚀 実験優先度順**

#### **🔥 最高優先度 - モデル性能に直結**

```yaml
# config/model_config.yaml の model_params セクション
learning_rate: 0.05 # 学習率 (0.01-0.2)
num_leaves: 31 # 葉数 (15-127)
n_estimators: 100 # 推定器数 (50-500)
```

**実験候補値**:

```yaml
# 慎重学習設定
learning_rate: 0.01
num_leaves: 15
n_estimators: 200

# 標準設定（現在値）
learning_rate: 0.05
num_leaves: 31
n_estimators: 100

# 高速学習設定
learning_rate: 0.1
num_leaves: 63
n_estimators: 50

# アグレッシブ設定
learning_rate: 0.2
num_leaves: 127
n_estimators: 500
```

#### **⚡ 高優先度 - 過学習制御**

```yaml
min_child_samples: 20 # 最小サンプル数 (10-100)
reg_alpha: 0.1 # L1正則化 (0.0-1.0)
reg_lambda: 0.1 # L2正則化 (0.0-1.0)
feature_fraction: 0.8 # 特徴量サンプリング (0.6-1.0)
```

**実験候補値**:

```yaml
# 汎化重視設定
min_child_samples: 50
reg_alpha: 0.5
reg_lambda: 0.5
feature_fraction: 0.6

# 標準設定（現在値）
min_child_samples: 20
reg_alpha: 0.1
reg_lambda: 0.1
feature_fraction: 0.8

# 精度重視設定
min_child_samples: 10
reg_alpha: 0.0
reg_lambda: 0.0
feature_fraction: 1.0
```

#### **🔧 中優先度 - 安定性調整**

```yaml
bagging_fraction: 0.8 # データサンプリング (0.7-0.9)
bagging_freq: 5 # Bagging頻度
early_stopping_rounds: 10 # Early stopping
```

### 🔒 **固定対象: その他全パラメータ**

以下のパラメータは実験中は固定値として使用します。

#### **データ設定（固定）**

```yaml
input_path: "./data/dataset.parquet" # 固定入力パス
output_path: "./models/direction_model.pkl" # 固定出力パス
```

#### **検証設定（固定）**

```yaml
cv_splits: 5 # 5分割交差検証に固定
```

#### **その他設定（固定）**

```yaml
no_report: false # レポート出力有効に固定
```

---

## 🎯 実験実行コマンド

実験は以下の 2 段階で実行します：

### **Step 1: データセット構築（変更パラメータに応じて）**

特徴量生成パラメータを変更した場合のみ実行：

```bash
cd /path/to/daily_trade

# 基本実行（最近1年間）
YESTERDAY=$(date -v-1d +%Y-%m-%d)
ONE_YEAR_AGO=$(date -v-1y +%Y-%m-%d)
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config config/dataset_config.yaml \
  --start $ONE_YEAR_AGO --end $YESTERDAY \
  --output ./data/dataset.parquet

# デバッグモード（詳細ログ）
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config config/dataset_config.yaml \
  --start $ONE_YEAR_AGO --end $YESTERDAY \
  --output ./data/dataset.parquet --verbose
```

**実行要否判定**:

- ✅ 特徴量ウィンドウサイズ変更 → **再実行必要**
- ✅ 各種期間パラメータ変更 → **再実行必要**
- ❌ LightGBM パラメータのみ変更 → **再実行不要**

### **Step 2: モデル学習（LightGBM パラメータ変更時は必須）**

```bash
# config/model_config.yaml の model_params セクションを編集後実行
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --config config/model_config.yaml

# 出力確認
cat models/latest_model_report.json
```

### **🔄 効率的な実験ワークフロー**

#### **パターン A: 特徴量実験**

```bash
# 1. config/model_config.yaml 編集（特徴量パラメータ）
# 2. データセット再構築（最近1年間）
YESTERDAY=$(date -v-1d +%Y-%m-%d)
ONE_YEAR_AGO=$(date -v-1y +%Y-%m-%d)
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config config/dataset_config.yaml \
  --start $ONE_YEAR_AGO --end $YESTERDAY \
  --output ./data/dataset.parquet

# 3. モデル学習（設定はそのまま）
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --config config/model_config.yaml
```

#### **パターン B: LightGBM 実験**

```bash
# 1. config/model_config.yaml 編集（model_paramsセクション）
# 2. モデル学習のみ実行（データセット再利用）
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --config config/model_config.yaml
```

#### **パターン C: フル実験**

```bash
# 1. 両方の設定ファイル編集
# 2. データセット構築（最近1年間）
YESTERDAY=$(date -v-1d +%Y-%m-%d)
ONE_YEAR_AGO=$(date -v-1y +%Y-%m-%d)
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config config/dataset_config.yaml \
  --start $ONE_YEAR_AGO --end $YESTERDAY \
  --output ./data/dataset.parquet

# 3. モデル学習
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --config config/model_config.yaml
```

---

## 📊 実験記録テンプレート

### **実験前記録**

```yaml
experiment_id: "exp_001_sma_windows"
date: "2025-01-XX"
goal: "SMAウィンドウ数を増やして予測精度向上"
hypothesis: "より多くの期間のSMAを追加することで長期トレンドを捉えやすくなる"

# 変更パラメータ
changed_params:
  feature_generation:
    sma_windows: [5, 10, 20, 50, 100, 200] # 従来: [10, 20, 50, 100, 200]

# 固定パラメータ
fixed_params:
  model_params:
    learning_rate: 0.05
    num_leaves: 31
    n_estimators: 100
```

### **実行コマンド記録**

```bash
# Step 1: データセット再構築（特徴量変更のため必要）
YESTERDAY=$(date -v-1d +%Y-%m-%d)
ONE_YEAR_AGO=$(date -v-1y +%Y-%m-%d)
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config config/dataset_config.yaml \
  --start $ONE_YEAR_AGO --end $YESTERDAY \
  --output ./data/dataset.parquet

# Step 2: モデル学習
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --config config/model_config.yaml
```

python src/daily*trade/scripts/train_model.py --config config/exp*{id}\_model_config.yaml

```

```

### **実験後記録**

```yaml
# 結果メトリクス
results:
  accuracy: 0.657
  precision: 0.651
  recall: 0.623
  f1_score: 0.637

# 実行時間
execution_time:
  dataset_build: "12分30秒"
  model_training: "3分45秒"

# 観察事項
observations:
  - "SMA期間追加により精度が0.02向上"
  - "学習時間は許容範囲内"
  - "特徴量重要度でSMA_5が上位に"

# 次回実験案
next_experiments:
  - "EMAウィンドウも同様に追加"
  - "RSI期間の調整"
```

build_command: |
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
 --config dataset_config.yaml \
 --start 2022-01-01 --end 2024-12-31 \
 --output ./data/baseline.parquet

train_command: |
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
 --config train_config.yaml

# 設定ファイル内容

dataset_config:
margin_pct: 0.01
symbol_category: ["popular"]
winsorize_pct: 0.01
min_trading_days: 100
validate_symbols: true

train_config:
learning_rate: 0.05
num_leaves: 31
n_estimators: 100

````

#### **実験後記録**

```yaml
# 結果 (models/*_report.jsonから取得)
results:
  auc: 0.524
  accuracy: 0.512
  cv_auc_mean: 0.519
  cv_auc_std: 0.012
  training_time: "3分"

# Top特徴量
top_features:
  - "ret_1d: 45.2"
  - "sma_20: 23.1"
  - "rsi_14: 18.7"

# 次のアクション
next_action: "margin_pct=0.005で精度向上を狙う"
````

### 🎯 **成功判定基準**

**ベースライン目標**:

- AUC > 0.52 (統計的有意性)
- CV 標準偏差 < 0.02 (安定性)

**改善目標**:

- AUC > 0.55 (実用レベル)
- 学習時間 < 10 分 (実用性)

**最終目標**:

- AUC > 0.58 (商用レベル)
- 全銘柄で AUC > 0.53 (堅牢性)

---

## 実験効率化の Tips

### ⚡ **高速実験のコツ**

1. **最初は短期データ**: `--start 2024-01-01 --end 2024-12-31`
2. **検証スキップ**: `--no-validate`
3. **最小取引日数削減**: `--min-days 20`
4. **少数銘柄**: popular カテゴリ(20 銘柄)で開始

### 📝 **実験管理のコツ**

1. **実験 ID ルール**: `exp_{番号}_{目的}_{日付}`
2. **設定ファイル保存**: 各実験用に config 複製
3. **結果保存**: models/ディレクトリに実験 ID 付きで保存

このドキュメントで効率的な実験サイクルを実行してください。
