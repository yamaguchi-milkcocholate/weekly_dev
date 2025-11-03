# Daily Trade 実験サイクル手順書

> **目的**: 継続的な実験サイクルによる予測モデル最適化フロー  
> **基本サイクル**: 目的設定 → パラメータ調整 → 実行 → 結果分析 → 次回計画 → 循環  
> **作成日**: 2025-11-03

## 📋 目次

1. [実験サイクルフロー](#実験サイクルフロー)
2. [サイクル各段階の詳細手順](#サイクル各段階の詳細手順)
3. [実験記録管理](#実験記録管理)
4. [サイクル継続のための Tips](#サイクル継続のための-tips)
5. [実験終了判定](#実験終了判定)

---

## 🔄 実験サイクルフロー

### **基本サイクル構造**

```
1. 実験目的設定    2. パラメータ調整    3. 実行・計測      4. 結果分析
   ↑                 ↓                  ↓                ↓
   └─ 6. 次回計画 ← 5. 改善仮説立案 ←─────┘
```

### **各段階の成果物**

| 段階              | 成果物         | ファイル保存先                         |
| ----------------- | -------------- | -------------------------------------- |
| 1. 目的設定       | 実験計画書     | `experiments/exp_{id}_plan.yaml`       |
| 2. パラメータ調整 | 設定ファイル   | `config/exp_{id}_*.yaml`               |
| 3. 実行・計測     | 実行ログ・結果 | `models/exp_{id}_report.json`          |
| 4. 結果分析       | 分析レポート   | `experiments/exp_{id}_analysis.yaml`   |
| 5. 改善仮説       | 次回仮説       | `experiments/exp_{id}_hypothesis.yaml` |
| 6. 次回計画       | 次回実験計画   | `experiments/exp_{next_id}_plan.yaml`  |

---

## 📝 サイクル各段階の詳細手順

### **Stage 1: 実験目的設定**

#### **初回実験時**

```yaml
# experiments/exp_001_plan.yaml
experiment_id: "exp_001_baseline"
date: "2025-11-03"
cycle_phase: "initial"

# 実験目的
objective: "ベースライン性能確立"
success_criteria:
  primary: "AUC > 0.52（統計的有意性確保）"
  secondary: "CV標準偏差 < 0.02（安定性確保）"

# 背景・動機
background: "モデル最適化の開始点として、現在設定での性能を測定"
expected_outcome: "後続実験の比較基準となるベースライン確立"

# 実験範囲
scope:
  parameters: "現在の設定値をそのまま使用"
  data_range: "2020-01-01 to 2024-12-31（5年間）"
  validation: "5-fold CV"
```

#### **継続実験時**

```yaml
# experiments/exp_002_plan.yaml
experiment_id: "exp_002_sma_enhancement"
date: "2025-11-03"
cycle_phase: "optimization"

# 前回実験参照
previous_exp: "exp_001_baseline"
previous_result: "AUC: 0.524, 目標クリア"

# 実験目的
objective: "SMA期間拡張による長期トレンド捕捉改善"
success_criteria:
  primary: "AUC > 0.534（前回比+0.01以上）"
  secondary: "特徴量重要度でSMA系が上位維持"

# 改善仮説
hypothesis: "より多様なSMA期間により、異なる時間軸のトレンドを捕捉可能"
rationale: "前回結果でSMA_20が重要度2位、期間拡張で更なる改善期待"
```

### **Stage 2: パラメータ調整**

#### **設定ファイル準備**

```bash
# 実験専用設定ファイル作成
cp config/model_config.yaml config/exp_002_model_config.yaml
cp train_config.yaml config/exp_002_train_config.yaml

# パラメータ変更記録
echo "# exp_002: SMA期間拡張" >> config/exp_002_model_config.yaml
echo "# sma_windows: [5, 10, 20, 50] → [5, 10, 20, 50, 100, 200]" >> config/exp_002_model_config.yaml
```

#### **変更内容記録**

```yaml
# experiments/exp_002_params.yaml
parameter_changes:
  changed:
    feature_generation:
      sma_windows: [5, 10, 20, 50, 100, 200] # 従来: [5, 10, 20, 50]

  fixed:
    model_params:
      learning_rate: 0.05
      num_leaves: 31
      n_estimators: 100

# 変更理由
change_rationale:
  sma_windows: "長期トレンド（100日、200日）追加でトレンド捕捉強化"
```

### **Stage 3: 実行・計測**

#### **実行コマンド**

```bash
# 実験実行スクリプト作成
cat > experiments/run_exp_002.sh << 'EOF'
#!/bin/bash
set -e

echo "=== Experiment 002: SMA Enhancement ==="
echo "Start Time: $(date)"

# Step 1: データセット構築
echo "Building dataset..."
YESTERDAY=$(date -v-1d +%Y-%m-%d)
ONE_YEAR_AGO=$(date -v-1y +%Y-%m-%d)
PYTHONPATH=./src uv run python -m daily_trade.scripts.build_dataset \
  --config config/dataset_config.yaml \
  --start $ONE_YEAR_AGO --end $YESTERDAY \
  --output ./data/dataset.parquet

# Step 2: モデル学習
echo "Training model..."
PYTHONPATH=./src uv run python -m daily_trade.scripts.train_model \
  --config config/exp_002_model_config.yaml

# Step 3: 結果保存
echo "Saving results..."
cp models/latest_model_report.json models/exp_002_report.json

echo "End Time: $(date)"
echo "=== Experiment 002 Complete ==="
EOF

chmod +x experiments/run_exp_002.sh

# 実行
./experiments/run_exp_002.sh
```

#### **実行時間計測**

```bash
# 実行時間記録
start_time=$(date +%s)
./experiments/run_exp_002.sh
end_time=$(date +%s)
execution_time=$((end_time - start_time))

echo "execution_time: ${execution_time}s" >> experiments/exp_002_execution.yaml
```

### **Stage 4: 結果分析**

#### **結果データ抽出**

```bash
# models/exp_002_report.json から主要メトリクス抽出
cat models/exp_002_report.json | jq '{
  auc: .auc,
  accuracy: .accuracy,
  cv_mean: .cv_auc_mean,
  cv_std: .cv_auc_std,
  top_features: .feature_importance | to_entries | sort_by(-.value) | .[0:5]
}' > experiments/exp_002_metrics.json
```

#### **分析レポート作成**

```yaml
# experiments/exp_002_analysis.yaml
experiment_id: "exp_002_sma_enhancement"
analysis_date: "2025-11-03"

# 結果比較
results:
  current:
    auc: 0.534
    cv_mean: 0.531
    cv_std: 0.015
  baseline:
    auc: 0.524
    cv_mean: 0.521
    cv_std: 0.018
  improvement:
    auc_delta: +0.010
    cv_std_delta: -0.003

# 成功判定
success_evaluation:
  primary_criteria: "✅ AUC 0.534 > 0.534（目標達成）"
  secondary_criteria: "✅ SMA_100が重要度4位に登場"
  overall: "SUCCESS"

# 観察事項
observations:
  positive:
    - "AUC 1.0%向上（統計的有意）"
    - "CV標準偏差改善（安定性向上）"
    - "SMA_100, SMA_200が重要度上位に"
  negative:
    - "学習時間15%増加"
    - "メモリ使用量若干増"
  neutral:
    - "他の特徴量重要度に大きな変化なし"

# 仮説検証
hypothesis_validation:
  original: "より多様なSMA期間により、異なる時間軸のトレンドを捕捉可能"
  result: "✅ 検証成功 - 長期SMA（100, 200日）が重要度上位に登場"
  evidence: "SMA_100: 重要度4位、SMA_200: 重要度7位"
```

### **Stage 5: 改善仮説立案**

#### **次回改善仮説**

```yaml
# experiments/exp_002_hypothesis.yaml
next_hypotheses:
  hypothesis_1:
    target: "EMA期間拡張"
    rationale: "SMAで効果確認、EMAでも同様の効果期待"
    priority: "high"
    expected_gain: "AUC +0.005-0.015"

  hypothesis_2:
    target: "RSI期間調整"
    rationale: "モメンタム系でRSI_14のみ、多様化余地あり"
    priority: "medium"
    expected_gain: "AUC +0.003-0.010"

  hypothesis_3:
    target: "LightGBM学習率調整"
    rationale: "特徴量増加で学習率最適化が必要"
    priority: "low"
    expected_gain: "AUC +0.001-0.005"

# 次回実験選択
selected_hypothesis: "hypothesis_1"
selection_reason: "SMAで最も効果があったパターンを他指標にも適用"
```

### **Stage 6: 次回計画策定**

#### **次回実験計画**

```yaml
# experiments/exp_003_plan.yaml
experiment_id: "exp_003_ema_enhancement"
date: "2025-11-03"
cycle_phase: "optimization"

# 前回実験参照
previous_exp: "exp_002_sma_enhancement"
previous_result: "AUC: 0.534, 目標達成"

# 実験目的
objective: "EMA期間拡張による短期トレンド捕捉改善"
success_criteria:
  primary: "AUC > 0.544（前回比+0.01以上）"
  secondary: "EMA系特徴量の重要度向上"

# 改善仮説
hypothesis: "SMA拡張成功を受け、EMAでも同様の効果を期待"
rationale: "EMAは短期変動に敏感で、SMAと補完的な効果期待"

# 実験計画
planned_changes:
  feature_generation:
    ema_windows: [12, 21, 50, 100] # 従来: [21]
  keep_previous:
    sma_windows: [5, 10, 20, 50, 100, 200] # exp_002の成果を維持

# リスク要因
risks:
  - "特徴量数増加による過学習"
  - "計算時間の更なる増加"

# 対策
mitigation:
  - "正則化パラメータ調整準備"
  - "実行時間監視"
```

---

## 📊 実験記録管理

### **ディレクトリ構造**

```
daily_trade/
├── experiments/           # 実験管理ディレクトリ
│   ├── exp_001_baseline/     # 実験1関連ファイル
│   │   ├── plan.yaml         # 実験計画
│   │   ├── params.yaml       # パラメータ変更記録
│   │   ├── analysis.yaml     # 結果分析
│   │   ├── hypothesis.yaml   # 次回仮説
│   │   └── run.sh           # 実行スクリプト
│   ├── exp_002_sma_enhancement/
│   ├── exp_003_ema_enhancement/
│   └── experiment_log.md     # 全実験の要約ログ
├── config/
│   ├── exp_001_*.yaml       # 実験別設定ファイル
│   ├── exp_002_*.yaml
│   └── ...
└── models/
    ├── exp_001_report.json  # 実験別結果レポート
    ├── exp_002_report.json
    └── ...
```

### **実験ログ管理**

#### **全実験要約ログ**

```markdown
# experiments/experiment_log.md

## 実験サイクル記録

### exp_001_baseline (2025-11-03)

- **目的**: ベースライン確立
- **結果**: AUC 0.524 ✅
- **次回**: SMA 期間拡張

### exp_002_sma_enhancement (2025-11-03)

- **目的**: SMA 期間拡張
- **変更**: sma_windows 追加 [100, 200]
- **結果**: AUC 0.534 (+0.010) ✅
- **次回**: EMA 期間拡張

### exp_003_ema_enhancement (2025-11-04)

- **目的**: EMA 期間拡張
- **変更**: ema_windows 追加 [12, 50, 100]
- **結果**: AUC 0.541 (+0.007) ✅
- **次回**: RSI 期間調整
```

#### **成果追跡スプレッドシート**

```yaml
# experiments/results_tracking.yaml
experiment_tracking:
  exp_001:
    auc: 0.524
    improvement: "baseline"
    status: "completed"
  exp_002:
    auc: 0.534
    improvement: +0.010
    status: "completed"
  exp_003:
    auc: 0.541
    improvement: +0.007
    status: "completed"

# 累積改善
total_improvement: +0.017
best_auc: 0.541
target_auc: 0.580
remaining_gap: 0.039
```

---

## 🎯 サイクル継続のための Tips

### **実験効率化**

#### **1. 並行実験管理**

```bash
# 複数実験の並行準備
mkdir -p experiments/{exp_004_rsi,exp_005_lightgbm,exp_006_features}

# 仮説の事前準備
for exp in exp_004_rsi exp_005_lightgbm exp_006_features; do
  cp experiments/hypothesis_template.yaml experiments/${exp}/plan.yaml
done
```

#### **2. 高速検証サイクル**

```yaml
# experiments/quick_validation.yaml
quick_settings:
  data_range: "2024-01-01 to 2024-12-31" # 1年のみ
  symbols: ["AAPL", "MSFT", "GOOGL"] # 3銘柄のみ
  cv_splits: 3 # 3分割CV
  n_estimators: 50 # 推定器数削減

purpose: "新仮説の高速検証（10分以内）"
usage: "本格実験前の仮説スクリーニング"
```

#### **3. 自動化スクリプト**

```bash
# experiments/auto_cycle.sh
#!/bin/bash

# 実験サイクル自動化
run_experiment_cycle() {
  local exp_id=$1
  local config_file=$2

  echo "=== Starting Experiment Cycle: ${exp_id} ==="

  # 1. 実行
  ./experiments/run_${exp_id}.sh

  # 2. 結果抽出
  python scripts/extract_results.py ${exp_id}

  # 3. 分析レポート生成
  python scripts/generate_analysis.py ${exp_id}

  # 4. 次回仮説生成
  python scripts/generate_hypothesis.py ${exp_id}

  # 5. ログ更新
  python scripts/update_experiment_log.py ${exp_id}

  echo "=== Experiment Cycle Complete: ${exp_id} ==="
}
```

### **品質管理**

#### **1. 実験チェックリスト**

```yaml
# experiments/quality_checklist.yaml
pre_experiment:
  - "[ ] 実験計画書作成済み"
  - "[ ] 成功基準明確化"
  - "[ ] パラメータ変更記録"
  - "[ ] 実行スクリプト準備"

post_experiment:
  - "[ ] 結果メトリクス抽出"
  - "[ ] 統計的有意性確認"
  - "[ ] 前回比較実施"
  - "[ ] 次回仮説立案"
  - "[ ] 実験ログ更新"
```

#### **2. 品質基準**

```yaml
# experiments/quality_standards.yaml
statistical_requirements:
  minimum_auc_improvement: 0.005
  significance_level: 0.05
  cv_stability_threshold: 0.02

documentation_requirements:
  plan_completeness: "目的・仮説・成功基準必須"
  analysis_depth: "定量・定性両面の評価"
  hypothesis_specificity: "具体的な数値目標設定"

reproducibility_requirements:
  config_versioning: "実験別設定ファイル保存"
  command_recording: "実行コマンド記録"
  environment_snapshot: "依存関係記録"
```

---

## 🏁 実験終了判定

### **終了基準**

#### **成功終了**

```yaml
success_criteria:
  primary_goal: "AUC > 0.580達成"
  stability: "連続3実験で改善なし"
  practical_limit: "計算時間 > 30分"

success_actions:
  - "最終モデル本番デプロイ準備"
  - "実験総括レポート作成"
  - "次期改善テーマ設定"
```

#### **早期終了**

```yaml
early_termination:
  no_improvement: "連続5実験で改善なし"
  performance_degradation: "ベースライン比 -0.01以下"
  resource_constraints: "実用性限界到達"

termination_actions:
  - "実験中断要因分析"
  - "代替アプローチ検討"
  - "実験戦略見直し"
```

### **最終レポート**

```yaml
# experiments/final_report.yaml
experiment_summary:
  total_experiments: 12
  duration: "2週間"
  best_auc: 0.587
  total_improvement: +0.063

key_discoveries:
  - "SMA/EMA期間拡張が最も効果的"
  - "RSI期間は14が最適"
  - "学習率0.03が最適解"

lessons_learned:
  - "特徴量工学が性能に最も寄与"
  - "過度な複雑化は効果低い"
  - "ドメイン知識の重要性"

next_phase:
  - "アンサンブル手法検討"
  - "新しい特徴量設計"
  - "リアルタイム予測最適化"
```

---

このフローに従って継続的な実験サイクルを回し、予測モデルの性能を体系的に向上させてください。
