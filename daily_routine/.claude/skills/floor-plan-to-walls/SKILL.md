---
name: floor-plan-to-walls
description: 間取りPNG画像から壁rect SVGまでを一気通貫で生成する統合パイプライン。PNG→potrace SVG→不要パス除去→壁rect配置の全工程を実行する。間取り図の壁rect生成、PNG間取りからSVG壁データ作成、間取り画像の壁抽出に関連するタスクで必ずこのスキルを参照すること。
argument-hint: [間取りPNG] [原図PNG(省略可)] [出力ディレクトリ(省略可)]
---

# 間取りPNG → 壁rect SVG 統合パイプライン

間取りPNG画像から壁の`<rect>`要素を持つSVGを生成する統合スキル。
3フェーズのパイプラインで処理し、Phase 2・3はサブスキルに委譲する。

```
Phase 1: ベクタートレース（potrace）     ← 本スキル内で実行
Phase 2: パスフィルタリング              ← floor-plan-filter に委譲
Phase 3: 壁rect配置                     ← floor-plan-walls に委譲
```

## 前提条件

- ImageMagick（`magick` コマンド）
- potrace（`potrace` コマンド）
- `scripts/svg_path_analyzer.py` が存在すること

```bash
# インストール確認
potrace --version && magick --version
```

## 入力 / 出力

- **入力**: 間取りPNG画像（壁線・部屋名・設備等が含まれた原図）
- **出力**:
  - `{stem}_walls_final.svg` — 壁rect配置済みSVG（背景画像付き）
  - `{stem}_walls_final_preview.png` — プレビューPNG

## 引数の解釈

```
/floor-plan-to-walls <間取りPNG> [原図PNG] [出力ディレクトリ]
```

- 間取りPNG: 必須。処理対象の間取り画像
- 原図PNG: 省略可。Phase 3のレビューで部屋名参照に使用。省略時は間取りPNGを兼用
- 出力ディレクトリ: 省略時は間取りPNGと同階層

---

## Phase 1: ベクタートレース（potrace）

間取りPNGをImageMagickで2値化し、potraceでSVGに変換する。

### Step 1-1: 入力画像の確認

入力PNGを読み取り、以下を確認:
- 壁線の太さ・コントラスト
- 背景色（白背景が理想）
- 文字・家具アイコンの存在

### Step 1-2: 変換実行

```bash
INPUT="<間取りPNGパス>"
OUTDIR="<出力ディレクトリ>"
STEM="<ファイル名（拡張子なし）>"
mkdir -p "$OUTDIR"

# デフォルト閾値70%で変換
magick "$INPUT" -colorspace Gray -threshold 70% pbm:- | potrace -s -o "$OUTDIR/${STEM}_trace.svg"
```

**閾値の選び方:**

| 間取り図の特性 | 推奨閾値 |
|---|---|
| 線が太く高コントラスト | 50-60% |
| 線が細い・グレー要素あり | 70-80% |
| 背景ノイズがある | 40-50% |

迷った場合は **70%** をデフォルトとする。

### Step 1-3: プレビュー確認

```bash
magick -background white -density 150 "$OUTDIR/${STEM}_trace.svg" "$OUTDIR/${STEM}_trace_preview.png"
```

プレビューPNGを読み取り、壁線の再現性を確認。問題があれば閾値を変えて再実行。

→ 報告: 「Phase 1完了。potrace SVG生成: {path}」

---

## Phase 2: パスフィルタリング

**`floor-plan-filter` スキルの手順に従って実行する。**

### 入力
- Phase 1で生成した `{stem}_trace.svg`

### 実行
`floor-plan-filter` スキルの Step 1〜5 を実行:
1. `uv run scripts/svg_path_analyzer.py index` でパスID付与
2. プレビュー画像を見て不要パス（文字・家具・ドア弧）を特定
3. `keep` or `remove` でパスを削除
4. プレビューで確認、反復修正
5. 壁線のみのクリーンSVG確定

### 出力
- `{stem}_trace_indexed.svg` — ID付与済みSVG
- `{stem}_trace_indexed_walls.svg` — 壁線のみSVG
- `{stem}_trace_indexed_walls_preview.png` — 壁線プレビューPNG

→ 報告: 「Phase 2完了。壁線PNG生成: {path}」

---

## Phase 3: 壁rect配置

**`floor-plan-walls` スキルの手順に従って実行する。**

### 入力
- Phase 2で生成した壁線プレビューPNG（`_indexed_walls_preview.png`）
- 原図PNG（Phase 3のレビューで部屋名参照に使用）

### 実行
`floor-plan-walls` スキルの Step 1〜5 を実行:
1. テンプレートSVG生成
2. 特徴点検出
3. ピクセル分析（壁セグメント計測）
4. イテレーション型壁配置（外壁→内壁→修正、レビューサブエージェント使用）
5. 最終出力

### 出力
- `{stem}_walls_final.svg` — 壁rect配置済みSVG
- `{stem}_walls_final_preview.png` — 最終プレビューPNG

→ 報告: 「Phase 3完了。壁rect SVG生成: {path}。最終壁数: {N}個」

---

## 完了報告

全フェーズ完了後、以下をまとめて報告:

```
パイプライン完了:
- 入力: {入力PNGパス}
- 壁rect SVG: {_walls_final.svg パス}
- プレビュー: {_walls_final_preview.png パス}
- 壁数: {N}個（外壁: {N}, 内壁: {N}）
```

## 後続ワークフロー

- `layout-floor-plan-annotate` スキルで部屋・ドア・窓・設備を定義 → `room_info.json` 生成
- Blenderインポート前に壁rectの `fill` を `#000000` に変更
- Blenderで `<rect>` を4点の閉じたパスとしてインポート → extrude → 3Dモデル化
