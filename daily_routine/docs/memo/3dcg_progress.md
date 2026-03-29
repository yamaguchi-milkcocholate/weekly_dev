# 3DCG パイプライン PoC 進捗整理

更新日: 2026-03-29

## 全体像

「間取り図 → 3D空間構築 → 家具配置 → レンダリング → スタイル転写」の一気通貫パイプライン。

## PoC一覧と進捗

| # | テーマ | 実装場所 | メモ | 状況 |
|---|--------|----------|------|------|
| 1 | 3D空間データ構築 | `poc/3dcg_poc1/` | `3dcg_poc_1.md`, `_1_1.md` | 完了 |
| 2 | 画像→3Dアセット抽出 | `poc/3dcg_poc2/` | `3dcg_poc_2.md` | 完了 |
| 3 | レイアウト提案 | `poc/3dcg_poc3/` | `3dcg_poc_3.md` | 完了 |
| 4 | 3D空間へのアセット配置 | `poc/3dcg_poc4/` | `3dcg_poc_4.md` | 完了・スキル化済 |
| 5 | 任意カメラ位置レンダリング | `poc/3dcg_poc5/` | `3dcg_poc_5.md` | 完了・スキル化済 |
| 6 | テクスチャ/雰囲気適用 | `poc/3dcg_poc6/` | `3dcg_poc_6.md` | **次にやる**（技術選定完了） |

### 派生PoC（間取り→3D変換）

| テーマ | 実装場所 | 状況 |
|--------|----------|------|
| PNG→SVG変換 (potrace) | `poc/3dcg_poc_inkspace/` | 完了・スキル化済 |
| SVG→Blender 3D壁生成 | `poc/3dcg_poc_blender/` | potraceベースは壁分離不可で断念 |
| PNG背景SVG+rect配置 | `poc/3dcg_poc_blender/memo2.md` | 手作業調整で実用可能 |

### スキル化状況

| スキル | 元PoC | 内容 |
|--------|-------|------|
| `blender-placement` | PoC 4 | GLB測定→front方向判定→配置→視覚的評価の一気通貫 |
| `blender-camera-render` | PoC 5 | カメラ位置抽出→EEVEE+HDRI一括レンダリング |

## 各PoCの結論

### PoC 1: 3D空間データ構築
- Gemini APIは日本語間取り図の認識精度が不十分
- Blender手動トレース + MASt3Rでのテクスチャ補完に方針転換
- 間取りPNG→壁rect SVGはClaude Codeの視覚認識+手作業調整で実用レベル

### PoC 2: 画像→3Dアセット抽出
- Tripo AI APIでEC画像→GLB変換に成功（5アセット検証済）
- 出力: `poc/3dcg_poc2/output/` にGLBファイル（bed, desk, chair, counter, closet, dining_table）

### PoC 3: レイアウト提案
- Claude Codeで間取り画像+寸法JSON+アセットBBoxから配置座標を生成
- 幾何学的な衝突回避はOK、ただし**生活動線の考慮が弱い**（空間充填優先）
- 出力: `poc/3dcg_poc3/output/layout_proposal.json`（10アセットの配置座標・向き）

### PoC 4: 3D空間へのアセット配置 — 完了
- Blender+bpyでGLBアセットの自動配置を実現
- front方向の自律判定（スケール比率による検証）を含む配置パイプラインを構築
- 3回のPatchで接地不良・scale歪み・front方向誤判定を解消
- `blender-placement` スキルとして汎用化済み
- 成果物: `poc/3dcg_poc4/output/scene.blend`（配置済みシーン）

### PoC 5: 任意カメラ位置レンダリング — 完了
- EEVEE + HDRI環境照明（Material Preview相当）方式を採用
- Workbench（グレー単色で判別困難）、Cycles+ライト（壁法線が外向きで真っ暗）を試行して不採用
- マテリアルなしオブジェクトへの一時マテリアル付与、俯瞰カメラ時の天井自動非表示を実装
- `blender-camera-render` スキルとして汎用化済み
- 成果物: `poc/3dcg_poc5/output/renders/`（複数カメラアングルのレンダリング画像）

### PoC 6: テクスチャ/雰囲気適用 ← 次のステップ
- 技術調査で方針転換: ControlNet+IP-Adapter（OSS）→ 大手商用API中心に変更
- 3つの要件: 構造の忠実性、スタイルの一貫性、リアルな質感
- 検証対象: Runway Gen-4、Kling、LUMA Ray
  - いずれも明示的な構造制約APIはないが、モデルの内部理解による構造維持を期待
  - References/Element Binding/style_ref等のスタイル参照機能あり
- 補助検討: FLUX（Depth API対応）、Wan VACE（Depth条件付き動画生成、OSS）
- Phase 1: 同一入力での比較検証 → Phase 2: マルチショット一貫性 → Phase 3: 動画生成

## 次のアクション

1. **PoC 6 Phase 1実装**: 3Dレンダリング画像+イメージ画像をRunway/Kling/LUMAに入力し構造維持・スタイル反映を比較
2. PoC 6 Phase 2: 有望サービスで複数カメラアングルの一貫性検証
3. PoC 6 Phase 3: カメラパスに沿った動画生成の検証
