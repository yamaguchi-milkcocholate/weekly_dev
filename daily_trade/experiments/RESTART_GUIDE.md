# 🔄 実験再開ガイド

実験セッションを中断・再開するためのクイックガイド

## ⚡ 即座に状況確認

```bash
# 1. プロジェクトディレクトリに移動
cd /Users/yamaguchiteppei/opt/post/weekly_dev/daily_trade

# 2. 現在の実験状況を確認
cat experiments/STATUS.yaml

# 3. 最新の実験結果を確認
tail -50 experiments/EXPERIMENT_LOG.md
```

## 🎯 現在の状況 (2025-11-03)

- **完了済み**: 実験 001 (ベースライン) - AUC 0.605 (CV), 0.725 (final)
- **次のステップ**: 実験 002 (早期停止修正)
- **課題**: 早期停止が早すぎる、CV 信頼性低下、過学習の可能性

## 🚀 次の実験実行

```bash
# 実験002の実行
cd /Users/yamaguchiteppei/opt/post/weekly_dev/daily_trade
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model --config config/exp_002_early_stopping_fix.yaml
```

## 📋 実験前チェックリスト

- [ ] `STATUS.yaml`で現在状況確認
- [ ] `EXPERIMENT_LOG.md`で前回の課題確認
- [ ] データが最新か確認 (`ls -la data/ohlcv/`)
- [ ] 設定ファイルが存在するか確認
- [ ] 作業ディレクトリが正しいか確認

## 🔍 トラブルシューティング

### 問題: "ModuleNotFoundError"

```bash
# 解決: PYTHONPATH設定確認
echo $PYTHONPATH
cd /Users/yamaguchiteppei/opt/post/weekly_dev/daily_trade
export PYTHONPATH=./src
```

### 問題: "設定ファイルが見つからない"

```bash
# 解決: ファイル存在確認
ls -la config/exp_*
pwd  # 正しいディレクトリにいるか確認
```

### 問題: "実験の続きが分からない"

```bash
# 解決: ステータス確認
cat experiments/STATUS.yaml | grep -A5 "next_action"
grep -A10 "## 📈 実験記録" experiments/EXPERIMENT_LOG.md
```

## 📁 重要ファイル構成

```
daily_trade/
├── experiments/
│   ├── STATUS.yaml           # 実験進捗状況
│   ├── EXPERIMENT_LOG.md     # 詳細な実験記録
│   └── RESTART_GUIDE.md      # このファイル
├── config/
│   ├── exp_001_model_config.yaml
│   └── exp_002_early_stopping_fix.yaml
├── models/
│   ├── exp_001_model.pkl
│   └── exp_001_model_report.json
└── data/ohlcv/
    └── latest_dataset.parquet
```

## 🎯 実験優先順位

1. **exp_002** (緊急) - 早期停止修正
2. **exp_003** (重要) - 特徴量拡張
3. **exp_004** (重要) - パラメータ最適化
4. **exp_005** (通常) - データ期間拡張
5. **exp_006** (通常) - 銘柄セグメント
