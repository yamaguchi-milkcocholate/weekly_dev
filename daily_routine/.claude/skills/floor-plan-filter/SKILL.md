---
name: floor-plan-filter
description: potrace生成SVGから不要パス（文字・家具・方位記号・ドア弧）を視覚的に判断して削除し、壁線のみのクリーンSVGを生成する。SVGパスのフィルタリング、壁線の抽出、間取りSVGのクリーンアップに関連するタスクで必ずこのスキルを参照すること。floor-plan-traceがPNG→SVG変換を行うのに対し、このスキルはSVG内の不要要素を除去する。
argument-hint: [SVGファイルパス] [出力ディレクトリ(省略可)]
---

# SVGパスの視覚的フィルタリング

potrace生成SVGから壁線以外の不要要素を、**画像を見て判断→XMLから削除**する反復ワークフローで除去する。

## 前提条件

- potrace生成のSVG（`<g>` 内に複数 `<path>` を持つ構造）
- ImageMagick（`magick` コマンド）がインストール済み
- `scripts/svg_path_analyzer.py` が存在すること

## 入力 / 出力

- **入力**: potrace生成SVG（任意のパス）
- **出力**:
  - `{stem}_indexed.svg` — ID付与済みSVG
  - `{stem}_paths.json` — パスBBox情報
  - `{stem}_indexed_annotated.png` — アノテーション付きプレビュー
  - `{stem}_walls.svg` — クリーンSVG（壁線のみ）

## 実行手順

### Step 1: パスIDの付与とプレビュー生成

```bash
uv run scripts/svg_path_analyzer.py index <SVGファイル> -o <出力ディレクトリ>
```

出力:
- ID付与済みSVG
- BBox情報JSON
- アノテーション付きプレビューPNG

→ **プレビューPNGを読み取り**、各パスの内容を視覚的に把握する。

### Step 2: 不要パスの特定

プレビュー画像を見て、以下の判断基準で各パスを分類する:

| 視覚的特徴 | 判断 | 例 |
|---|---|---|
| 漢字・カナ・英数字の形状 | **削除** | 「洋室」「LDK」「PS」「約6帖」 |
| 矢印・方位記号 | **削除** | N矢印 |
| 家具・設備の形状 | **削除** | 浴槽、トイレ、キッチン、ソファ |
| ドアの弧（開閉軌跡） | **削除** | 扇型の弧線 |
| 太い直線・矩形の構造体 | **保持** | 壁線、柱 |
| 部屋を区切る線 | **保持** | 間仕切り壁 |

**注意**: 1つのpathに壁と非壁が混在する場合がある。その場合はBBoxが大きい（壁全体を含む）ため、安易に削除しない。

### Step 3: パスの削除と確認

削除対象が多い場合（保持対象が少ない場合）は `keep` を使用:
```bash
uv run scripts/svg_path_analyzer.py keep <indexed.svg> --ids path_001,path_002,... -o <出力ディレクトリ>
```

削除対象が少ない場合は `remove` を使用:
```bash
uv run scripts/svg_path_analyzer.py remove <indexed.svg> --ids path_045,path_046,... -o <出力ディレクトリ>
```

→ 出力されたプレビューPNGを読み取り、結果を確認。

### Step 4: 反復修正

プレビューを確認し、まだ不要パスが残っている場合:
1. 残った不要パスのIDを特定
2. 生成されたSVGに対して再度 `remove` を実行
3. プレビューで確認

壁線が欠けてしまった場合:
1. Step 3に戻り、保持IDリストを修正して再実行

### Step 5: クリーンSVG確定

壁線のみが残ったプレビューを確認し、`_walls.svg` を最終成果物とする。

## 既知の制約

- BBoxの計算はベジェ曲線の制御点を含むため、実際の描画範囲より大きくなる場合がある
- アノテーションラベルが密集して読みにくい場合は、paths.jsonのBBox情報と合わせて判断する
- potraceのSVGでは壁と接触する文字が1つのpathに含まれることがある。その場合はpathレベルでの分離が困難なため、保持して後工程で対処する

## 後続ワークフロー

生成されたクリーンSVG（`_walls.svg`）は以下で使用:
- Blenderへのインポート（`bpy.ops.import_curve.svg()`）→ 3D壁モデル化
