# 🤖 train_model.py 実行手順書

`train_model.py`は、`build_dataset.py`で作成したデータセットを使用して、株価の翌日上昇確率を予測する LightGBM モデルの学習・評価・保存を行う CLI ツールです。

## 🚀 クイックスタート

### 最小限の実行例

```bash
# 基本的な実行
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --input ./data/daily_ohlcv_features.parquet \
  --output ./models/direction_model.pkl
```

## 📋 事前準備

### 1. 環境設定

```bash
# プロジェクトルートに移動
cd /path/to/daily_trade

# 依存パッケージの確認
uv sync

# モデル保存ディレクトリの作成
mkdir -p ./models
```

### 2. データセットの準備

モデル学習には`build_dataset.py`で作成したデータセットが必要です：

```bash
# データセットが存在しない場合は作成
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbol-category popular \
  --start 2024-01-01 \
  --end 2024-12-31 \
  --output ./data/daily_ohlcv_features.parquet
```

### 3. データセット要件の確認

学習に必要な列が含まれているか確認：

```bash
# データセット内容の確認
PYTHONPATH=./src uv run python -c "
import pandas as pd
df = pd.read_parquet('./data/daily_ohlcv_features.parquet')
print('データ形状:', df.shape)
print('必須列の確認:')
required_cols = ['symbol', 'timestamp', 'y_up', 'next_ret']
for col in required_cols:
    exists = col in df.columns
    print(f'  {col}: {'✅' if exists else '❌'}')
print('特徴量数:', len([c for c in df.columns if c not in required_cols]))
"
```

## 💼 実行パターン

### パターン 1: コマンドライン引数指定（基本）

#### シンプルな実行

```bash
# 最小限の設定で実行
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --input ./data/daily_ohlcv_features.parquet \
  --output ./models/direction_model.pkl
```

#### パラメータ調整付き実行

```bash
# LightGBMパラメータを調整して実行
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --input ./data/daily_ohlcv_features.parquet \
  --output ./models/tuned_model.pkl \
  --cv-splits 5 \
  --num-leaves 50 \
  --learning-rate 0.1 \
  --n-estimators 200 \
  --verbose
```

### パターン 2: YAML 設定ファイル使用（推奨）

#### 設定ファイルの作成

```yaml
# config/model_config.yaml
# 入出力設定
input_path: "./data/daily_ohlcv_features.parquet"
output_path: "./models/production_model.pkl"

# 交差検証設定
cv_splits: 5

# LightGBMモデル設定
model_params:
  num_leaves: 50
  learning_rate: 0.1
  n_estimators: 200
  feature_fraction: 0.8
  bagging_fraction: 0.8
  bagging_freq: 5
  min_child_samples: 20
  reg_alpha: 0.1
  reg_lambda: 0.1
  random_state: 42

# 出力設定
no_report: false
```

#### 設定ファイルでの実行

```bash
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --config config/model_config.yaml
```

### パターン 3: 高性能設定

```bash
# 高性能モデル設定（時間がかかります）
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --input ./data/daily_ohlcv_features.parquet \
  --output ./models/high_performance_model.pkl \
  --cv-splits 10 \
  --num-leaves 100 \
  --learning-rate 0.05 \
  --n-estimators 500 \
  --verbose
```

### パターン 4: 高速プロトタイピング

```bash
# 高速実行（評価レポート無し）
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --input ./data/daily_ohlcv_features.parquet \
  --output ./models/quick_model.pkl \
  --cv-splits 2 \
  --n-estimators 50 \
  --no-report
```

## ⚙️ 主要オプション詳細

### 🎯 入出力オプション

| オプション | 説明                  | 例                                  |
| ---------- | --------------------- | ----------------------------------- |
| `--input`  | 入力データセットパス  | `--input ./data/features.parquet`   |
| `--output` | 出力モデルパス        | `--output ./models/model.pkl`       |
| `--config` | YAML 設定ファイルパス | `--config config/model_config.yaml` |

### 🔧 モデル設定オプション

| オプション        | 説明             | デフォルト | 例                    |
| ----------------- | ---------------- | ---------- | --------------------- |
| `--cv-splits`     | 交差検証分割数   | 3          | `--cv-splits 5`       |
| `--num-leaves`    | LightGB 木の葉数 | 31         | `--num-leaves 50`     |
| `--learning-rate` | 学習率           | 0.05       | `--learning-rate 0.1` |
| `--n-estimators`  | 決定木の数       | 100        | `--n-estimators 200`  |

### 📊 出力オプション

| オプション    | 説明                     | デフォルト |
| ------------- | ------------------------ | ---------- |
| `--no-report` | 評価レポート出力を無効化 | False      |
| `--verbose`   | 詳細ログ出力             | False      |

## 🎯 実用的な使用ケース

### ケース 1: 本番環境モデル学習

```bash
# 本番環境用の高品質モデル
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --input ./data/production_dataset.parquet \
  --output ./models/production_model_$(date +%Y%m%d).pkl \
  --cv-splits 10 \
  --num-leaves 100 \
  --learning-rate 0.05 \
  --n-estimators 300 \
  --verbose
```

### ケース 2: ハイパーパラメータ実験

```bash
# 複数の設定で実験
for lr in 0.05 0.1 0.15; do
  for leaves in 31 50 100; do
    echo "学習率: $lr, 葉数: $leaves"
    PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
      --input ./data/experiment_data.parquet \
      --output ./models/exp_lr${lr}_leaves${leaves}.pkl \
      --learning-rate $lr \
      --num-leaves $leaves \
      --n-estimators 100 \
      --no-report
  done
done
```

### ケース 3: 定期再学習

```bash
#!/bin/bash
# daily_retrain.sh - 定期再学習スクリプト

# 最新データでデータセット更新
TODAY=$(date +%Y-%m-%d)
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --symbol-category popular \
  --start 2024-01-01 \
  --end $TODAY \
  --output ./data/latest_dataset.parquet

# モデル再学習
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --input ./data/latest_dataset.parquet \
  --output ./models/daily_model_$TODAY.pkl \
  --config config/production_config.yaml
```

### ケース 4: 異なるデータセットでの比較

```bash
# 複数期間のモデル比較
datasets=("2024_q1.parquet" "2024_q2.parquet" "2024_full.parquet")

for dataset in "${datasets[@]}"; do
  echo "データセット: $dataset で学習中..."
  PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
    --input "./data/$dataset" \
    --output "./models/model_${dataset%.parquet}.pkl" \
    --cv-splits 5 \
    --verbose
done
```

## 📊 出力ファイル構造

### 生成されるファイル

#### 1. モデルファイル (`.pkl`)

```
./models/direction_model.pkl    # 学習済みモデル（pickle形式）
```

#### 2. 評価レポート (`.json`)

```
./models/direction_model_report.json    # 詳細な評価結果
```

### 評価レポートの内容

```json
{
  "evaluation_metrics": {
    "auc": 0.752,
    "accuracy": 0.689,
    "precision": 0.671,
    "recall": 0.634
  },
  "cross_validation": {
    "auc": {
      "mean": 0.748,
      "std": 0.012,
      "scores": [0.745, 0.752, 0.747, 0.751, 0.746]
    },
    "accuracy": {
      "mean": 0.685,
      "std": 0.008,
      "scores": [0.682, 0.689, 0.684, 0.688, 0.683]
    }
  },
  "feature_importance": {
    "rsi_14": 1256.2,
    "ret_1d": 1123.8,
    "sma_20": 987.4,
    "volume_ratio_20": 856.1,
    ...
  },
  "metadata": {
    "timestamp": "2024-10-31T15:30:45",
    "model_type": "LightGBM",
    "validation_method": "TimeSeriesSplit"
  }
}
```

## 📈 モデル性能の評価指標

### 主要指標

- **AUC (Area Under Curve)**: 0.5-1.0（高いほど良い）
- **Accuracy**: 精度（正答率）
- **Precision**: 適合率（予測した上昇の的中率）
- **Recall**: 再現率（実際の上昇をどれだけ捉えたか）

### 目標値の目安

| 指標      | 良好   | 優秀   | 説明                      |
| --------- | ------ | ------ | ------------------------- |
| AUC       | > 0.65 | > 0.75 | ランダムより優位性がある  |
| Accuracy  | > 0.60 | > 0.70 | ランダム(50%)より高い精度 |
| Precision | > 0.60 | > 0.70 | 上昇予測の信頼性          |
| Recall    | > 0.60 | > 0.70 | 上昇機会の捕捉率          |

## 🚨 トラブルシューティング

### よくあるエラーと対処法

#### 1. ModuleNotFoundError

```bash
# エラー: ModuleNotFoundError: No module named 'daily_trade'
# 対処: PYTHONPATHの設定確認
export PYTHONPATH=./src
```

#### 2. ファイルが見つからない

```bash
# エラー: FileNotFoundError: ファイルが見つかりません
# 対処: パスの確認とデータセット作成
ls -la ./data/daily_ohlcv_features.parquet
# ファイルがない場合はbuild_datasetを実行
```

#### 3. メモリ不足

```bash
# エラー: MemoryError
# 対処: データセットサイズの削減またはパラメータ調整
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --input ./data/small_dataset.parquet \
  --output ./models/model.pkl \
  --n-estimators 50    # 木の数を削減
  --num-leaves 20      # 葉数を削減
```

#### 4. 学習性能が低い

```bash
# 対処: ハイパーパラメータの調整
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --input ./data/features.parquet \
  --output ./models/improved_model.pkl \
  --cv-splits 10           # 交差検証を増やす
  --num-leaves 100         # 複雑度を上げる
  --learning-rate 0.02     # 学習率を下げる
  --n-estimators 500       # 木の数を増やす
```

#### 5. 過学習の兆候

**症状**: 学習データの AUC は高いが、交差検証の AUC が低い

```bash
# 対処: 正則化の強化
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --input ./data/features.parquet \
  --output ./models/regularized_model.pkl \
  --num-leaves 20          # 複雑度を下げる
  --learning-rate 0.05     # 適度な学習率
  --n-estimators 100       # 木の数を適度に
```

## 📈 パフォーマンス最適化

### 高速化のコツ

1. **交差検証分割数の調整**: `--cv-splits 2`で高速化
2. **木の数の削減**: `--n-estimators 50`で高速化
3. **評価レポートのスキップ**: `--no-report`で高速化
4. **並列処理**: LightGBM は自動で並列処理

### メモリ使用量の目安

| データセットサイズ | 推定メモリ | 推奨設定                   |
| ------------------ | ---------- | -------------------------- |
| < 100MB            | ~1GB       | デフォルト設定             |
| 100-500MB          | ~4GB       | `num_leaves=50`            |
| 500MB-1GB          | ~8GB       | `num_leaves=31, n_est=100` |
| > 1GB              | > 16GB     | `num_leaves=20, n_est=50`  |

## 🔧 設定ファイル管理

### 環境別設定テンプレート

#### 開発環境用設定

```yaml
# config/dev_config.yaml
input_path: "./data/dev_dataset.parquet"
output_path: "./models/dev_model.pkl"
cv_splits: 3
model_params:
  num_leaves: 31
  learning_rate: 0.1
  n_estimators: 50
no_report: true
```

#### 本番環境用設定

```yaml
# config/prod_config.yaml
input_path: "./data/production_dataset.parquet"
output_path: "./models/production_model.pkl"
cv_splits: 10
model_params:
  num_leaves: 100
  learning_rate: 0.05
  n_estimators: 300
  feature_fraction: 0.8
  bagging_fraction: 0.8
  reg_alpha: 0.1
  reg_lambda: 0.1
no_report: false
```

#### 実験用設定

```yaml
# config/experiment_config.yaml
input_path: "./data/experiment_dataset.parquet"
output_path: "./models/experiment_model.pkl"
cv_splits: 5
model_params:
  num_leaves: 50
  learning_rate: 0.08
  n_estimators: 200
  feature_fraction: 0.9
  bagging_fraction: 0.9
no_report: false
```

## 📋 チェックリスト

### 実行前チェック

- [ ] 環境変数 `PYTHONPATH=./src` が設定済み
- [ ] 入力データセットファイルが存在
- [ ] データセットに必要な列（`y_up`, `next_ret`）が含まれている
- [ ] 出力ディレクトリ（`./models`）が存在
- [ ] 十分なメモリとディスク容量がある

### 実行後チェック

- [ ] モデルファイル（`.pkl`）が正常に生成された
- [ ] 評価レポート（`.json`）が生成された（`--no-report`未指定時）
- [ ] ログにエラーメッセージがない
- [ ] AUC が 0.5 以上（ランダムより優秀）
- [ ] 交差検証スコアが安定している

## 🤝 サポート

### ログの確認

```bash
# 詳細ログで実行
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --input ./data/features.parquet \
  --output ./models/model.pkl \
  --verbose
```

### ヘルプの表示

```bash
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model --help
```

### モデル性能の確認

```bash
# 評価レポートの確認
cat ./models/direction_model_report.json | jq '.evaluation_metrics'

# 特徴量重要度の確認
cat ./models/direction_model_report.json | jq '.feature_importance' | head -20
```

## 📚 次のステップ

### モデル活用

1. **予測の実行**: 学習済みモデルを使った予測
2. **モデルの検証**: 新しいデータでの性能検証
3. **本番環境デプロイ**: API やバッチ処理での活用

### 継続的改善

1. **定期再学習**: 新しいデータでのモデル更新
2. **ハイパーパラメータ最適化**: Optuna 等を使った自動最適化
3. **特徴量エンジニアリング**: 新しい特徴量の追加

---

**更新日**: 2025 年 10 月 31 日  
**作成者**: AI Trading System Team  
**バージョン**: 1.0.0
