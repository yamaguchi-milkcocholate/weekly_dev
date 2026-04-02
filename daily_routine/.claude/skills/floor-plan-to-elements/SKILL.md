---
name: floor-plan-to-elements
description: 間取りPNG画像から壁・柱の要素別SVGまでを一気通貫で生成する統合パイプライン。floor-plan-trace（PNG→クリーンSVG）とfloor-plan-elements（SVG→要素rect）を順次実行する。間取り図の壁rect生成、PNG間取りからSVG要素への変換、間取り画像の壁抽出を一括実行したいときに必ずこのスキルを参照すること。
argument-hint: [workdir]
allowed-tools: Bash(uv run *), Bash(python3 *), Bash(magick *), Bash(potrace *)
---

# 間取りPNG → 要素別SVG 統合パイプライン

カラーPNG間取り画像から壁・柱の`<rect>`要素を持つSVGまでを一気通貫で生成する。内部で `floor-plan-trace` と `floor-plan-elements` を順次実行する。

## 前提条件

- ImageMagick（`magick` コマンド）
- potrace（`potrace` コマンド）

```bash
potrace --version && magick --version
```

## 入力 / 出力

**引数**: `[workdir]` — 作業ディレクトリのパス

**入力**: `{workdir}/input/` に間取りPNG画像を事前配置すること。画像名はStep 0で確認する。

**ディレクトリ構造**:

```
{workdir}/
├── input/
│   └── {image_name}.png          ← ユーザーが事前配置
├── output/                       ← 最終成果物
│   ├── {stem}_floor_plan.svg     ← Phase 1: クリーンSVG
│   ├── {stem}_floor_plan_preview.png
│   ├── {stem}_elements.svg       ← Phase 2: 要素別SVG
│   └── {stem}_elements_preview.png
└── work/                         ← 中間成果物
    ├── trace/                    ← Phase 1 の中間ファイル
    └── elements/                 ← Phase 2 の中間ファイル
```

## コマンド実行ルール

変数代入（`WORKDIR=...`等）とコマンド（`magick`, `uv run`等）は必ず別の行で実行すること。同一行に書くと `allowed-tools` のパターンマッチが効かず許可プロンプトが出る。

```bash
# NG: 変数代入とコマンドを同一行に書かない
WORKDIR="/path/to" magick -background white ...

# OK: 変数を先に設定してからコマンドを実行
WORKDIR="/path/to"
magick -background white ...
```

## 使用スクリプト

| スクリプト | 所属スキル | サブコマンド |
|-----------|-----------|------------|
| `.claude/skills/floor-plan-trace/scripts/svg_trace_tools.py` | floor-plan-trace | `index`, `remove`, `keep` |
| `.claude/skills/floor-plan-elements/scripts/element_tools.py` | floor-plan-elements | `template`, `scan` |

## 実行手順

### Step 0: workdir構造確認

1. `{workdir}/input/` の存在と中の画像ファイルを確認
2. 画像が複数ある場合、ユーザーに処理対象を確認
3. `{workdir}/output/` と `{workdir}/work/trace/` と `{workdir}/work/elements/` を作成

```bash
WORKDIR="<workdirパス>"
ls "$WORKDIR/input/"
mkdir -p "$WORKDIR/output" "$WORKDIR/work/trace" "$WORKDIR/work/elements"
```

→ 報告: 「入力画像: {image_name}.png を確認」

---

### Phase 1: カラーPNG → クリーンSVG

**`floor-plan-trace` スキルの手順に従って実行する。** ただしパスを以下のように読み替える:

| floor-plan-trace の変数 | 本スキルでの値 |
|---|---|
| `$INPUT` | `$WORKDIR/input/{image_name}.png` |
| `$OUTDIR` | `$WORKDIR/output` |
| `$WORKDIR`（中間） | `$WORKDIR/work/trace` |

**実行する手順**:

1. **動的閾値選択**: 4つの閾値（50%, 60%, 70%, 80%）でpotrace変換を `work/trace/` に出力し、プレビューを比較して最適な閾値を選択
2. **パスID付与**: `svg_trace_tools.py index` で `work/trace/` にインデックスSVG生成
3. **不要パス除去**: プレビューを見て `keep` / `remove` で壁・柱・ドア弧以外を除去
4. **反復修正**: プレビュー確認→修正を繰り返す
5. **クリーンSVG確定**: 最終SVGを `output/{stem}_floor_plan.svg` にコピー

```bash
cp "$WORKDIR/work/trace/${STEM}_trace_indexed_walls.svg" "$WORKDIR/output/${STEM}_floor_plan.svg"
magick -background white -density 150 "$WORKDIR/output/${STEM}_floor_plan.svg" "$WORKDIR/output/${STEM}_floor_plan_preview.png"
```

→ 報告: 「Phase 1完了。クリーンSVG: output/{stem}_floor_plan.svg」

---

### Phase 2: クリーンSVG → 要素別SVG

**`floor-plan-elements` スキルの手順に従って実行する。** ただしパスを以下のように読み替える:

| floor-plan-elements の変数 | 本スキルでの値 |
|---|---|
| 入力SVG | `$WORKDIR/output/{stem}_floor_plan.svg` |
| `$OUTDIR` | `$WORKDIR/output` |
| `$WORKDIR`（中間） | `$WORKDIR/work/elements` |
| 原図PNG | `$WORKDIR/input/{image_name}.png` |

**実行する手順**:

1. **SVG→PNG変換**: クリーンSVGを `work/elements/` にPNG化
2. **テンプレート生成**: `element_tools.py template` で背景埋め込みSVG生成
3. **特徴点検出**: `element_tools.py scan` で端点・交差点検出
4. **ピクセル分析**: 水平/垂直スキャン、壁厚計測、柱候補検出
5. **イテレーション型要素配置**: 外壁→内壁→柱→修正のループ（サブエージェントレビュー付き）
6. **最終出力**: 確定版を `output/{stem}_elements.svg` にコピー

```bash
cp "$WORKDIR/work/elements/${STEM}_elements_iter{N}.svg" "$WORKDIR/output/${STEM}_elements.svg"
magick -background white -density 150 "$WORKDIR/output/${STEM}_elements.svg" "$WORKDIR/output/${STEM}_elements_preview.png"
```

→ 報告: 「Phase 2完了。要素SVG: output/{stem}_elements.svg。壁: {N}個, 柱: {N}個」

---

## 完了報告

両Phase完了後、最終成果物の一覧を報告:

```
output/
├── {stem}_floor_plan.svg         ← クリーンSVG間取り図
├── {stem}_floor_plan_preview.png
├── {stem}_elements.svg           ← 壁・柱の要素別SVG
└── {stem}_elements_preview.png
```

## 後続ワークフロー

- 要素SVGをBlenderにインポート → extrude → 3Dモデル化
- `layout-floor-plan-annotate` スキルでの部屋定義に接続
- `layout-pipeline` スキルでの家具配置パイプラインに接続
