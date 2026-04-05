# PoC0: floor-plan-to-elements 統合パイプライン検証

## 概要

`floor-plan-to-elements` スキルの動作検証。カラーPNG間取り画像から壁・柱の要素別SVGまでを一気通貫で生成する統合パイプラインの初回実行。

## 検証内容

### 入力

- `input/madori_1ldk_1.png`（548×1113px、1LDK、白背景、カラー間取り図）

### 実行したスキル

`/floor-plan-to-elements poc/3dcg_poc0/1`

内部で以下の2スキルを順次実行:

1. **Phase 1: floor-plan-trace** — カラーPNG → potrace → フィルタリング → クリーンSVG
2. **Phase 2: floor-plan-elements** — クリーンSVG → PNG化 → ピクセル分析 → 壁・柱rect配置

### 出力

| ファイル                                      | 内容                                           |
| --------------------------------------------- | ---------------------------------------------- |
| `output/madori_1ldk_1_floor_plan.svg`         | Phase 1成果物: 壁線・ドア弧のみのクリーンSVG   |
| `output/madori_1ldk_1_floor_plan_preview.png` | Phase 1プレビュー                              |
| `output/madori_1ldk_1_elements.svg`           | Phase 2成果物: 壁44個 + 柱7個のrect配置済みSVG |
| `output/madori_1ldk_1_elements_preview.png`   | Phase 2プレビュー                              |

### 中間成果物

- `work/trace/` — Phase 1の中間ファイル（閾値選択済みSVG、ID付与済みSVG、パスJSON等）
- `work/elements/` — Phase 2の中間ファイル（テンプレートSVG、特徴点JSON、イテレーション1〜4のSVG/プレビュー）

## 結果

### Phase 1: floor-plan-trace

- 動的閾値選択で最適な閾値を自動判定
- テキスト（「洋室」「LDK」等）、家具アイコン、方位記号を除去
- 壁線・ドア弧・柱の構造要素のみ残した

### Phase 2: floor-plan-elements

- 4イテレーションで壁・柱を配置
  - Iteration 1: 外壁
  - Iteration 2: 内壁
  - Iteration 3: 柱
  - Iteration 4: 修正・追加
- 最終結果: **壁44個、柱7個**
- 壁rectは背景の壁線と概ね一致
- 柱は壁交差部に配置

### 評価

- Phase 1のフィルタリング精度は良好。壁・ドア弧が正しく残り、テキスト・家具が除去された
- Phase 2の壁rect配置は外壁・主要内壁をカバー。ピクセルレベルの精度も概ね合致
- 柱の検出（7個）は壁交差部の主要箇所を捉えている

## ディレクトリ構造

```
poc/3dcg_poc0/1/
├── input/
│   └── madori_1ldk_1.png          ← カラー間取り画像
├── output/
│   ├── madori_1ldk_1_floor_plan.svg
│   ├── madori_1ldk_1_floor_plan_preview.png
│   ├── madori_1ldk_1_elements.svg
│   └── madori_1ldk_1_elements_preview.png
└── work/
    ├── trace/                     ← Phase 1中間
    │   ├── madori_1ldk_1_trace.svg
    │   ├── madori_1ldk_1_trace_indexed.svg
    │   ├── madori_1ldk_1_trace_indexed_annotated.png
    │   ├── madori_1ldk_1_trace_indexed_walls.svg
    │   ├── madori_1ldk_1_trace_paths.json
    │   └── ...
    └── elements/                  ← Phase 2中間
        ├── madori_1ldk_1_floor_plan_render.png
        ├── madori_1ldk_1_floor_plan_render_template.svg
        ├── madori_1ldk_1_floor_plan_render_keypoints.json
        ├── madori_1ldk_1_floor_plan_render_elements_iter{1-4}.svg
        └── ...
```

## 技術的な処理の流れ

### Phase 1: floor-plan-trace（カラーPNG → クリーンSVG）

```
カラーPNG間取り画像
  │
  ▼ Step 1: 入力画像確認
  │  画像サイズ・背景色・壁線の太さを把握
  │
  ▼ Step 2: 動的閾値選択（potrace）
  │  4つの閾値（50%, 60%, 70%, 80%）で一括トレース
  │  ┌──────────────────────────────────────────────────┐
  │  │ magick → グレースケール化 → 閾値でPBM二値化       │
  │  │ potrace → PBMからSVGベクター生成                  │
  │  │ ×4回（各閾値）→ プレビュー比較 → 最適閾値を選択  │
  │  └──────────────────────────────────────────────────┘
  │  評価基準: 壁線の連続性、ノイズ量、文字と壁線の分離度、ドア弧の再現性
  │
  ▼ Step 3: パスID付与
  │  svg_trace_tools.py index
  │  → SVG内の各pathにユニークID（path_001, path_002...）を付与
  │  → BBox情報JSON + アノテーション付きプレビュー生成
  │
  ▼ Step 4: 不要パスの視覚的フィルタリング
  │  アノテーションプレビューを目視確認し、パスを分類
  │  ┌────────────────────────────────────────────┐
  │  │ 保持: 壁線、柱、ドア弧（構造要素）        │
  │  │ 削除: テキスト、家具、方位記号、寸法線     │
  │  └────────────────────────────────────────────┘
  │  svg_trace_tools.py keep/remove でパスを選別
  │
  ▼ Step 5: 反復修正（必要に応じて）
  │
  ▼ Step 6: クリーンSVG確定
  │
  ◆ 出力: {stem}_floor_plan.svg（構造要素のみ）
```

**ポイント**: potraceは「面の塗りつぶし」（even-odd fill rule）でSVGを生成する。壁・ドア弧・柱が接触していると1つの複合パスに結合されるため、パスレベルでの個別分離は構造的に不可能。ここではパス単位の粗い除去（テキストや家具の塊を除去）のみ行い、個別要素の分離はPhase 2で別アプローチを取る。

### Phase 2: floor-plan-elements（クリーンSVG → 要素別rect SVG）

```
クリーンSVG（Phase 1出力）
  │
  ▼ Step 1: SVG → PNG変換
  │  magick -density 150 でラスタライズ
  │
  ▼ Step 2: テンプレートSVG生成
  │  element_tools.py template
  │  → PNG背景を<image>で埋め込み + 空の要素グループ4つ
  │    <g id="walls" />, <g id="pillars" />,
  │    <g id="doors" />, <g id="fixtures" />
  │
  ▼ Step 3: 特徴点検出
  │  element_tools.py scan
  │  ┌─────────────────────────────────────────────────────────┐
  │  │ Zhang-Suen法でスケルトン化（壁線を1px幅の骨格に変換）   │
  │  │ → 骨格画素の近傍パターン分析                            │
  │  │ → 端点（赤）: 壁の行き止まり                            │
  │  │ → 交差点（青）: 壁のT字・L字・十字接合部                │
  │  │ → クラスタリングでノイズ除去                             │
  │  └─────────────────────────────────────────────────────────┘
  │
  ▼ Step 4: ピクセル分析（壁セグメント計測）
  │  PIL + NumPyによるインラインPythonスクリプト
  │  ┌─────────────────────────────────────────────────────────┐
  │  │ 4-1: 水平スキャン — 特徴点y座標での横方向黒セグメント   │
  │  │ 4-2: 垂直スキャン — 特徴点x座標での縦方向黒セグメント   │
  │  │ 4-3: 壁厚計測 — 各セグメントの垂直/水平方向のpx幅       │
  │  │      外壁: 16-18px, 内壁: 8-13px, 薄い仕切り: 4-5px    │
  │  │ 4-4: 柱候補検出 — 壁交差部の正方形的な黒領域            │
  │  └─────────────────────────────────────────────────────────┘
  │
  ▼ Step 5: イテレーション型要素配置（最大7回）
  │  ┌──────────────────────────────────────────────────────┐
  │  │ 各イテレーション:                                    │
  │  │  1. Pythonスクリプトで<rect>要素をSVGに追加/修正     │
  │  │  2. magickでプレビューPNG生成                        │
  │  │  3. サブエージェント（Agent tool）がプレビューを評価  │
  │  │  4. PASS → 次へ / NEEDS_FIX → 修正して再レビュー    │
  │  ├──────────────────────────────────────────────────────┤
  │  │ 実行順序:                                            │
  │  │  Iter 1: 外壁（建物外周の壁rect配置）               │
  │  │  Iter 2: 内壁（部屋間の仕切り壁rect追加）           │
  │  │  Iter 3: 柱（壁交差部の正方形rect配置）             │
  │  │  Iter 4+: レビュー指摘に基づく修正・追加             │
  │  └──────────────────────────────────────────────────────┘
  │
  ▼ Step 6: 最終出力
  │
  ◆ 出力: {stem}_elements.svg
     壁: <rect fill="rgba(255,0,0,0.3)" stroke="red" />
     柱: <rect fill="rgba(0,128,0,0.3)" stroke="green" />
```

**ポイント**: Phase 1のpotraceでは壁が複合パスに結合されて個別分離できなかった問題を、PNG画像のピクセル直接分析で解決する。壁線の黒ピクセルを水平/垂直にスキャンし、座標・厚さを計測して独立した`<rect>`として新規生成する。Blenderは`<rect>`をインポート可能（4点の閉じたパスに変換）、`<image>`要素は無視されるため、背景画像付きのまま編集・確認ができる。

## 使用スキル

| スキル                 | パス                                             |
| ---------------------- | ------------------------------------------------ |
| floor-plan-to-elements | `.claude/skills/floor-plan-to-elements/SKILL.md` |
| floor-plan-trace       | `.claude/skills/floor-plan-trace/SKILL.md`       |
| floor-plan-elements    | `.claude/skills/floor-plan-elements/SKILL.md`    |
