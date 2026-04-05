---
name: floor_plan_to_video_sub_status
description: 3DCGレイアウトパイプラインのマスタースキル。現在の進捗状態を自動判定し、次に実行すべきフェーズとスキルを案内する。パイプライン全体の統括、途中再開、進捗確認に使用する。レイアウトパイプラインの開始、途中再開、進捗確認、次のステップの案内に関連するタスクで必ずこのスキルを参照すること。
argument-hint: <出力ディレクトリ>
---

# floor_plan_to_video_sub_status

3DCGレイアウトパイプラインの全体統括スキル。ファイルの存在状況から現在のフェーズを自動判定し、次に実行すべきスキルを案内する。

## パイプライン全体図

```
Phase 1: PNG → SVG → 要素別SVG
    │  スキル: /floor_plan_to_video_sub_trace → /floor_plan_to_video_sub_elements
    ▼
Phase 2-3: SVG → drawio → room_info.json + floor_plan_complete.svg
    │  スキル: /floor_plan_to_video_sub_annotate → (手作業) → /floor_plan_to_video_sub_annotate integrate
    ▼
Phase 4: アセット情報の準備
    │  スキル: /floor_plan_to_video_sub_assets
    ▼
Phase 5: リファレンス調査 + スコア基準作成（任意）
    │  スキル: /floor_plan_to_video_sub_research
    ▼
Phase 6: レイアウト提案（refineループ）
    │  スキル: /floor_plan_to_video_sub_refine
    │  ┌──────────────────────────────┐
    │  │ 6a: 配置  ─→ エンジン        │
    │  │ 6b: 評価  ←─ SVG + Geminiスコア │
    │  │ 6c: 修正  ─→ 6aに戻る        │
    │  └──────────────────────────────┘
    ▼
Phase 7: レンダリング確認
       スキル: /floor_plan_to_video_sub_render
```

---

## 実行手順

### Step 1: 状態判定

出力ディレクトリ（引数で指定）内のファイル存在を確認し、現在のフェーズを判定する。

```
チェック対象ファイル → フェーズ判定:

floor_plan.svg + walls.json          → Phase 1 完了
floor_plan_rooms.drawio              → Phase 2 完了（drawioテンプレート生成済み）
room_info.json + floor_plan_complete.svg → Phase 3 完了
assets.json + life_scenarios.json    → Phase 4 完了
scoring_criteria.json                → Phase 5 完了（任意）
placement_plan.json                  → Phase 6 進行中
layout_proposal.svg + layout_proposal.json → Phase 6 配置結果あり
```

### Step 2: 状態の提示

判定結果をユーザーに提示する:

```
=== レイアウトパイプライン状態 ===

✓ Phase 1: 間取り抽出（floor_plan.svg, walls.json）
✓ Phase 2-3: 空間アノテーション（room_info.json, floor_plan_complete.svg）
✓ Phase 4: アセット準備（assets.json, life_scenarios.json）
✗ Phase 5: リファレンス調査（任意）
✗ Phase 6: レイアウト提案
✗ Phase 7: レンダリング確認

→ 次のステップ: /floor_plan_to_video_sub_research（任意）または /floor_plan_to_video_sub_refine を実行してください
```

### Step 3: 次のスキルの案内

未完了の最初のフェーズに対応するスキルを案内する:

| フェーズ | 不足ファイル | 案内するスキル | コマンド例 |
|---------|------------|--------------|----------|
| Phase 1 | floor_plan.svg | floor_plan_to_video_sub_extract | `/floor_plan_to_video_sub_extract <workdir>` |
| Phase 2 | floor_plan_rooms.drawio | floor_plan_to_video_sub_annotate | `/floor_plan_to_video_sub_annotate` |
| Phase 3 | room_info.json | floor_plan_to_video_sub_annotate | `/floor_plan_to_video_sub_annotate integrate` |
| Phase 4 | assets.json | floor_plan_to_video_sub_assets | `/floor_plan_to_video_sub_assets` |
| Phase 5 | scoring_criteria.json | floor_plan_to_video_sub_research | `/floor_plan_to_video_sub_research`（任意） |
| Phase 6 | placement_plan.json | floor_plan_to_video_sub_refine | `/floor_plan_to_video_sub_refine` |
| Phase 7 | （配置確定後） | floor_plan_to_video_sub_render | `/floor_plan_to_video_sub_render` |

### Step 4: 前提ファイル不足の警告

スキップされたフェーズがある場合（例: Phase 1をスキップしてPhase 3を実行しようとした場合）、前提ファイルが不足していることを警告する。

---

## 各フェーズの入出力一覧

| Phase | 入力 | 出力 | 手動作業 |
|-------|------|------|---------|
| 1 | .blend | floor_plan.svg, walls.json, floor_plan_meta.json | なし |
| 2 | floor_plan.svg | floor_plan_rooms.drawio | drawioで部屋・設備を記入 |
| 3 | drawio, walls.json | room_info.json, floor_plan_complete.svg | なし |
| 4 | complete.svg, room_info.json | assets.json, life_scenarios.json | 対話で家具情報を提供 |
| 5 | complete.svg, assets.json, room_info.json | scoring_criteria.json, layout_design_principles.md | 対話で重視観点を提供 |
| 6 | complete.svg, assets.json, room_info.json, walls.json, life_scenarios.json | placement_plan.json, layout_proposal.svg, layout_proposal.json | 評価・フィードバック |
| 7 | .blend, layout_proposal.json, GLB files, assets.json | レンダリング画像 | 確認 |

---

## よくある問題と対処法

### Q: 途中から始められる？
A: 必要な入力ファイルが揃っていれば、どのフェーズからでも開始できる。このスキルで状態を確認し、不足ファイルを特定できる。

### Q: 配置がうまくいかない
A: `/floor_plan_to_video_sub_refine`で壁面インベントリを再確認し、壁面割り当てを見直す。

### Q: drawioの座標がずれる
A: `floor_plan_to_video_sub_annotate`スキルの既知の問題を参照。SVG画像のdrawio上での位置ずれが原因の可能性がある。

### Q: 配置エンジンがFAILする
A: `placement_plan.json`の座標を修正する。エラーメッセージに衝突相手が表示されるので、その障害物を避ける座標に調整する。
