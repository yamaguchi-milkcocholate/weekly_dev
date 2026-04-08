---
name: floor_plan_to_video_sub_trace
description: カラーPNG間取り画像からクリーンなSVG間取り図を生成する。potraceによるベクタートレースと視覚的フィルタリング（不要パス除去）を統合した一気通貫スキル。間取り図のSVG化、PNG間取りからSVGへの変換、potraceトレース、間取りSVGの生成に関連するタスクで必ずこのスキルを参照すること。
argument-hint: [間取りPNG] [出力ディレクトリ(省略可)]
allowed-tools: Bash(uv run *), Bash(python3 *), Bash(magick *), Bash(potrace *), Bash(mkdir *), Bash(ls *), Bash(cp *), Bash(rm *), Bash(mv *)
---

# カラーPNG → クリーンSVG間取り図

カラーPNG間取り画像を入力し、potraceによるベクタートレース + 不要パスの視覚的フィルタリングを一気通貫で実行して、構造要素（壁・柱・ドア弧）のみのクリーンSVGを出力する。

## なぜこのアプローチか

間取り図のPNG画像にはテキスト、家具アイコン、方位記号など多くの要素が含まれる。potraceでベクター化した後、画像を見て不要パスを判断・除去することで、後続の要素分類（`floor_plan_to_video_sub_elements`）に適したクリーンなSVGを生成する。

## 前提条件

- ImageMagick（`magick` コマンド）
- potrace（`potrace` コマンド）

```bash
# インストール確認
potrace --version && magick --version
```

## コマンド実行ルール

変数代入（`OUTDIR=...`等）とコマンド（`magick`, `uv run`等）は必ず別の行で実行すること。同一行に書くと `allowed-tools` のパターンマッチが効かず許可プロンプトが出る。

## スクリプト

`.claude/skills/floor_plan_to_video_sub_trace/scripts/svg_trace_tools.py` を使用する。

| サブコマンド | 用途 |
|---|---|
| `index` | SVGパスにID付与 + BBox情報JSON + アノテーションプレビュー生成 |
| `annotate` | ID付きアノテーションプレビュー生成 |
| `remove` | 指定パスIDを削除 |
| `keep` | 指定パスIDのみ保持 |

## 入力 / 出力

- **入力**: カラーPNG間取り画像
- **出力ディレクトリ**: 引数で指定可能、省略時は入力PNGと同じディレクトリ

**最終成果物**（`{output_dir}/` 直下）:
- `{stem}_floor_plan.svg` — 構造要素のみのクリーンSVG
- `{stem}_floor_plan_preview.png` — 最終プレビュー

**中間成果物**（`{output_dir}/work/` 配下、処理過程で自動生成）:
- `{stem}_trace_{N}.svg` / `{stem}_trace_{N}_preview.png` — 閾値別のpotraceトレース結果
- `{stem}_trace.svg` — 選択された閾値のトレースSVG
- `{stem}_trace_indexed.svg` — ID付与済みSVG
- `{stem}_trace_paths.json` — パスBBox情報JSON
- `{stem}_trace_indexed_annotated.png` — アノテーション付きプレビュー
- `{stem}_trace_indexed_walls.svg` — フィルタリング後SVG

## 実行手順

### Step 1: 入力画像の確認

入力PNGを読み取り、以下を確認:
- 壁線の太さ・コントラスト
- 背景色（白/カラー/グレー）
- 文字・家具アイコンの量

→ 報告: 「画像サイズ: {W}x{H}px、背景: {色}、壁線: {太い/細い}」

### Step 2: 動的閾値選択

入力画像の特性に応じて最適なpotrace閾値を選択する。固定値ではなく、複数の閾値でトレースして比較する。

**2-1: 候補閾値でのトレース実行**

4つの閾値（50%, 60%, 70%, 80%）で一括変換:

```bash
INPUT="<間取りPNGパス>"
OUTDIR="<出力ディレクトリ>"
WORKDIR="$OUTDIR/work"
STEM="<ファイル名（拡張子なし）>"
mkdir -p "$WORKDIR"

for THR in 50 60 70 80; do
  magick "$INPUT" -colorspace Gray -threshold "${THR}%" pbm:- | potrace -s -o "$WORKDIR/${STEM}_trace_${THR}.svg"
  magick -background white -density 150 "$WORKDIR/${STEM}_trace_${THR}.svg" "$WORKDIR/${STEM}_trace_${THR}_preview.png"
done
```

**2-2: プレビュー比較と閾値選択**

4つのプレビューPNGを読み取り、以下の基準で最適な閾値を判定:

| 評価基準 | 理想的な状態 |
|---------|-----------|
| 壁線の再現性 | 外壁・内壁の輪郭が途切れずに連続 |
| ノイズ量 | 背景の斑点・ムラが最小限 |
| 文字の残存 | 文字が残っても可（後で除去）、ただし壁線と融合して分離不能になる閾値は避ける |
| ドア弧の再現 | 弧線が認識可能な程度に残っている |

**判定の目安**:

| 間取り図の特性 | 最適閾値の傾向 |
|---|---|
| 線が太く高コントラスト・白背景 | 50-60% |
| 線が細い・グレー要素あり | 70-80% |
| カラー背景（部屋ごとに色分け） | 60-70% |
| 背景ノイズが多い | 40-50% |

自動判定に自信がない場合はユーザーに4つのプレビューを提示して選択を求める。

**2-3: 不採用の閾値ファイルを削除**

選択した閾値以外の中間ファイルを削除:

```bash
# 例: 70%を選択した場合
rm "$WORKDIR/${STEM}_trace_50.svg" "$WORKDIR/${STEM}_trace_50_preview.png"
rm "$WORKDIR/${STEM}_trace_60.svg" "$WORKDIR/${STEM}_trace_60_preview.png"
rm "$WORKDIR/${STEM}_trace_80.svg" "$WORKDIR/${STEM}_trace_80_preview.png"
mv "$WORKDIR/${STEM}_trace_70.svg" "$WORKDIR/${STEM}_trace.svg"
```

→ 報告: 「閾値{N}%を選択。potrace SVG生成完了: {path}」

### Step 3: パスIDの付与とプレビュー生成

```bash
uv run .claude/skills/floor_plan_to_video_sub_trace/scripts/svg_trace_tools.py index "$WORKDIR/${STEM}_trace.svg" -o "$WORKDIR"
```

出力:
- `{stem}_trace_indexed.svg` — ID付与済みSVG
- `{stem}_trace_paths.json` — BBox情報JSON
- `{stem}_trace_indexed_annotated.png` — アノテーション付きプレビュー

→ アノテーションプレビューPNGを読み取り、各パスの内容を視覚的に把握する。

### Step 4: 不要パスの特定と除去

プレビュー画像を見て、以下の判断基準で各パスを分類する:

| 視覚的特徴 | 判断 | 例 |
|---|---|---|
| 漢字・カナ・英数字の形状 | **削除** | 「洋室」「LDK」「PS」「約6帖」 |
| 矢印・方位記号 | **削除** | N矢印 |
| 家具・設備の形状 | **削除** | 浴槽、トイレ、キッチン、ソファ |
| 寸法線・引き出し線 | **削除** | 矢印付きの直線 |
| 太い直線・矩形の構造体 | **保持** | 壁線 |
| 小さい正方形の構造体 | **保持** | 柱 |
| ドアの弧（開閉軌跡） | **保持** | 扇型の弧線（floor_plan_to_video_sub_elementsで使用） |
| 部屋を区切る線 | **保持** | 間仕切り壁 |

**注意**: 1つのpathに壁と非壁が混在する場合がある（potraceの構造上、接触する要素が1パスになる）。BBoxが大きい場合は壁を含む可能性が高いため安易に削除しない。

**パスの除去実行**:

削除対象が多い場合（保持対象が少ない場合）は `keep` を使用:
```bash
uv run .claude/skills/floor_plan_to_video_sub_trace/scripts/svg_trace_tools.py keep "$WORKDIR/${STEM}_trace_indexed.svg" --ids path_001,path_002,... -o "$WORKDIR"
```

削除対象が少ない場合は `remove` を使用:
```bash
uv run .claude/skills/floor_plan_to_video_sub_trace/scripts/svg_trace_tools.py remove "$WORKDIR/${STEM}_trace_indexed.svg" --ids path_045,path_046,... -o "$WORKDIR"
```

→ 出力されたプレビューPNGを読み取り、結果を確認。

### Step 5: 反復修正

プレビューを確認し、まだ不要パスが残っている場合:
1. 残った不要パスのIDを特定
2. 生成されたSVGに対して再度 `remove` を実行
3. プレビューで確認

壁線が欠けてしまった場合:
1. Step 4に戻り、保持IDリストを修正して再実行

### Step 6: クリーンSVG確定

構造要素のみが残ったプレビューを確認し、最終ファイルをリネーム:

```bash
cp "$WORKDIR/${STEM}_trace_indexed_walls.svg" "$OUTDIR/${STEM}_floor_plan.svg"
magick -background white -density 150 "$OUTDIR/${STEM}_floor_plan.svg" "$OUTDIR/${STEM}_floor_plan_preview.png"
```

→ 報告: 「クリーンSVG生成完了: {path}。残存パス数: {N}個」

## 既知の制約

- BBoxの計算はベジェ曲線の制御点を含むため、実際の描画範囲より大きくなる場合がある
- アノテーションラベルが密集して読みにくい場合は、paths.jsonのBBox情報と合わせて判断する
- potraceのSVGでは壁と接触する文字が1つのpathに含まれることがある。その場合はpathレベルでの分離が困難なため、保持して後工程で対処する

## 後続ワークフロー

生成されたクリーンSVG（`{stem}_floor_plan.svg`）は `floor_plan_to_video_sub_elements` スキルの入力として使用する。
