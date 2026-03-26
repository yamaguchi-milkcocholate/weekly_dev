---
name: floor-plan-walls
description: フィルタ済み壁線PNGから特徴点を検出し、特徴点間を繋ぐ壁rectをSVGに配置する。ピクセルデータ分析で座標精度を担保し、反復ループで品質を改善する。間取り図の壁rect配置、壁の長方形オブジェクト生成、PNG間取り図からSVG壁要素の作成に関連するタスクで必ずこのスキルを参照すること。floor-plan-filterがSVG内の不要パスを除去するのに対し、このスキルはPNG画像から新規に壁rect要素を生成する。
argument-hint: [壁線PNG] [原図PNG(省略可)] [出力ディレクトリ(省略可)]
---

# 壁rectの配置

フィルタ済み壁線PNGから壁の特徴点（端点・交差点・角点）をピクセルデータから検出し、特徴点間を繋ぐ`<rect>`要素としてSVGに配置する。

## なぜこのアプローチか

potraceのSVG出力は「面の塗りつぶし」構造（even-odd fill rule）のため、壁・ドア弧・設備が1つの複合パスに結合され、個別分離が構造的に不可能。代わりにPNG画像を直接分析し、壁を個別の`<rect>`要素として新規生成する。

Blenderは`<rect>`をインポート可能（4点の閉じたパスに変換）、`<image>`は無視されるため、背景画像付きSVGでの編集・確認が可能。

## 前提条件

- `floor-plan-filter` で生成された壁線PNG（`{stem}_indexed_walls_preview.png`）
- `scripts/svg_path_analyzer.py` が存在すること
- ImageMagick（`magick`コマンド）がインストール済み

## 入力 / 出力

- **入力**:
  - 壁線PNG（`_indexed_walls_preview.png`）— テキスト除去済みの壁線のみの画像
  - 原図PNG（省略可）— 部屋名・設備名の参照用
- **出力**:
  - `{stem}_walls_final.svg` — 壁rect配置済みSVG（背景画像付き）
  - `{stem}_walls_final_preview.png` — プレビューPNG

## 全体フロー

```
Step 1: 入力確認 + テンプレート生成
Step 2: 特徴点検出
Step 3: ピクセル分析（壁セグメント計測）
Step 4: イテレーション型壁配置
  ├─ Iteration 1: 外壁 → レビュー（サブエージェント）
  ├─ Iteration 2: 主要内壁 → レビュー（サブエージェント）
  ├─ Iteration N: 修正・追加 → レビュー（サブエージェント）
  └─ 完了条件を満たしたら終了
Step 5: 最終出力
```

## 壁rectの配置基準

### 壁の認定基準

- 水平または垂直の直線であること（斜め壁は対象外）
- 両端が特徴点で定義されること
- 壁厚は元画像の黒ピクセル幅から自動計測（概ね8-18px）

### rectの属性

```xml
<rect id="wall_001" x="144" y="83" width="652" height="17"
      fill="rgba(255,0,0,0.3)" stroke="red" stroke-width="1.5"
      data-label="北側外壁"/>
```

- `fill="rgba(255,0,0,0.3)"` — 半透明赤（背景画像が見える）
- `stroke="red"` — 枠線（位置確認用）
- `data-label` — 壁の説明（任意）

### Blenderインポート時の変換

Blenderに取り込む前に `fill` を `#000000`（黒）に変更する。`<image>`要素はBlenderが無視するため、手動削除不要。

## 実行手順

### Step 1: 入力ファイル確認とテンプレート生成

入力ファイルの存在を確認し、SVGテンプレートを生成する。

```bash
uv run scripts/svg_path_analyzer.py template {walls_preview_png} -o {output_dir}
```

出力: `{stem}_template.svg`（PNG背景埋め込み + 空のwalls/doors/fixturesグループ）

→ 報告: 「テンプレートSVG生成完了。画像サイズ: {W}x{H}px」

### Step 2: 特徴点検出

ピクセルデータから壁の特徴点を検出する。

```bash
uv run scripts/svg_path_analyzer.py scan {walls_preview_png} -o {output_dir}
```

出力:
- `{stem}_keypoints.json` — 特徴点リスト
- `{stem}_keypoints_preview.png` — 特徴点可視化画像

**検出後の確認**:
1. `_keypoints_preview.png` を読み取り、特徴点の位置を確認する
2. 赤い点（端点）が壁の行き止まりに正しく配置されているか
3. 青い点（交差点）が壁の接合部に正しく配置されているか
4. ドア弧や設備部分に誤検出がないか

→ 報告: 「特徴点検出完了。端点: {N}個, 交差点: {N}個」

### Step 3: ピクセル分析

壁線PNGを直接スキャンし、壁セグメントの正確な座標と厚さを計測する。特徴点だけでは壁の連続性や厚さが分からないため、ピクセルレベルの分析が必須。

**3-1: 水平スキャン**

`uv run python3` インラインスクリプトで、主要なy座標における水平方向の黒ピクセルセグメントを検出する。

```python
from PIL import Image
import numpy as np

img = Image.open("{walls_preview_png}").convert("L")
arr = np.array(img)
walls = arr < 128  # 黒ピクセル = 壁

# 指定yでの水平セグメント検出（長さ20px以上）
for y in [主要なy座標リスト]:
    row = walls[y]
    # 連続する黒ピクセルの開始・終了位置を取得
    # → segments: [(x_start, x_end), ...]
```

スキャン対象のy座標は、特徴点のy座標クラスタ（±5px）と、画像の上端・下端付近を選ぶ。

**3-2: 垂直スキャン**

同様に、主要なx座標における垂直方向のセグメントを検出する。

**3-3: 壁厚計測**

各壁セグメントについて、垂直方向（水平壁の場合）または水平方向（垂直壁の場合）のピクセル幅を計測し、壁厚を決定する。

- 外壁: 概ね16-18px
- 内壁: 概ね8-13px
- 薄い仕切り: 4-5px

**3-4: 結果のまとめ**

分析結果を整理し、以下の情報を把握する:
- 各壁セグメントの座標範囲（x_start, x_end または y_start, y_end）
- 壁厚（ピクセル）
- 壁のカテゴリ（外壁/内壁/薄い仕切り）

→ 報告: 「ピクセル分析完了。水平セグメント: {N}個, 垂直セグメント: {N}個」

### Step 4: イテレーション型壁配置

壁rectの配置・プレビュー生成・レビューを繰り返し、段階的に品質を上げる。

#### イテレーション共通フロー

```
1. 配置: 対象カテゴリの壁rectをSVGに追加/修正（uv run python3 スクリプト）
2. プレビュー生成: magick でSVG→PNG変換
3. レビュー: サブエージェント（Agent tool）でプレビューを評価
4. 判定: PASS → 次のイテレーション or 完了 / NEEDS_FIX → 修正して再レビュー
```

#### Iteration 1: 外壁配置

Step 3のピクセル分析結果から、外壁（建物の外周を構成する壁）を配置する。

**配置対象**:
- 北壁（上辺）
- 東壁（右辺）
- 南壁（下辺）
- 西壁（左辺、段差がある場合は各段）
- 段差接続壁（西壁のステップ部分等）

**配置方法**:
`uv run python3` インラインスクリプトで、テンプレートSVGの `<g id="walls" />` を `<g id="walls">...rects...</g>` に置換する。

**プレビュー生成**:
```bash
magick -background white -density 150 {svg_path} {preview_png_path}
```

**レビュー**: → 「レビューサブエージェント」を参照

→ 報告: 「Iteration 1完了。外壁{N}個を配置」

#### Iteration 2: 主要内壁配置

レビュー結果を踏まえ、部屋を仕切る主要な内壁を追加配置する。

**配置対象**:
- 部屋間の仕切り壁（水平・垂直）
- ホール・玄関の区画壁
- 水回り（トイレ・洗面・浴室）の区画壁
- LDKの北壁・南壁

**配置方法**:
既存のSVGを読み込み、`<g id="walls">` 内に追加のrect要素を挿入する。

**プレビュー生成** → **レビュー**

→ 報告: 「Iteration 2完了。内壁{N}個を追加。累計{N}個」

#### Iteration 3以降: 修正・追加

レビューサブエージェントの指摘に基づき、以下を実施:
- **missing**: 欠けている壁のrectを追加
- **misaligned**: ずれているrectの座標を修正
- **false_positive**: 壁以外に配置されたrectを削除

**修正後** → **プレビュー生成** → **レビュー**

→ 報告: 「Iteration {N}完了。修正{N}件。累計壁数{N}個」

#### 完了条件

以下のいずれかを満たしたらイテレーション終了:
- レビューサブエージェントが `"status": "PASS"` を返す
- priority=high の issue が0件
- 最大5イテレーション（無限ループ防止）

---

### レビューサブエージェント

各イテレーション後に **Agent tool** でサブエージェントを起動し、配置結果をレビューさせる。メインエージェントのコンテキストを消費せずに、画像ベースの詳細レビューを実行できる。

**Agent プロンプトテンプレート**:

```
あなたは壁rect配置のレビューエージェントです。
プレビューPNG・壁線PNG・原図PNGを読み取り、壁rectの配置品質を評価してください。

## 入力ファイル
- プレビューPNG（壁rect重畳）: {preview_png_path}
- 壁線PNG（背景参照）: {walls_preview_png_path}
- 原図PNG（部屋名参照）: {original_png_path}
- 現在の壁数: {wall_count}個
- イテレーション: {iteration_number}

## レビュー基準

1. **位置一致**: 壁rectが背景の黒い壁線と正確に重なっているか
2. **網羅性**: 全ての壁線がrectでカバーされているか（特に原図の部屋境界を参考に）
3. **誤検出**: 壁以外の要素（ドア弧・設備・家具）にrectが重なっていないか
4. **厚さ**: 外壁は16-18px、内壁は8-13pxが目安
5. **接続**: 壁同士のT字・L字接合部でrectが正しく繋がっているか

## 確認手順

1. プレビューPNGを読み取り、赤い壁rectと黒い壁線の一致を確認
2. 壁線PNGを読み取り、rectでカバーされていない壁線を探す
3. 原図PNGを読み取り、各部屋（玄関・ホール・トイレ・洗面室・浴室・LDK等）の境界にrectがあるか確認
4. 問題をリストアップ

## 出力形式

以下のJSON形式で報告すること（JSON以外の出力は不要）:

{
  "status": "PASS" または "NEEDS_FIX",
  "issues": [
    {
      "type": "missing" | "misaligned" | "false_positive" | "thickness",
      "description": "具体的な問題の説明（位置情報を含む）",
      "priority": "high" | "medium" | "low",
      "suggested_fix": "修正案（座標値を含む場合は明記）"
    }
  ],
  "summary": "全体の評価サマリー（1-2文）"
}
```

**サブエージェントの起動コード（親エージェント側）**:

```
Agent tool を使用:
- description: "壁rect配置レビュー Iteration {N}"
- prompt: 上記テンプレートに実際のパスと値を埋め込んだもの
```

**レビュー結果の処理（親エージェント側）**:
- `"status": "PASS"` → 次のイテレーション or Step 5
- `"status": "NEEDS_FIX"` → issues の内容に基づき修正イテレーションを実施

---

### Step 5: 最終出力

全イテレーション完了後、最終ファイルを保存する。

1. 壁rect確定版SVGを `{stem}_walls_final.svg` として保存
2. プレビューPNGを `{stem}_walls_final_preview.png` として保存

→ 報告: 「壁rect配置完了。最終壁数: {N}個。{output_path}」

## 既知の制約

- スケルトン化アルゴリズムの特性上、ドア弧や設備の曲線部分にも特徴点（交差点）が誤検出される。壁の直線上にある特徴点のみを使用すること
- 壁厚が一定でない場合（外壁と内壁で異なる等）、手動で壁厚を調整する必要がある
- 斜め壁には対応していない（水平・垂直の壁のみ）
- 特徴点検出の精度は入力画像の品質に依存する。ノイズの多い画像ではクラスタリング半径の調整が必要

## 後続ワークフロー

- 壁rect確定版SVGをBlenderにインポート → extrude → 3Dモデル化
- ドア・設備のrect/path配置（同様のアプローチで別カテゴリを配置）
- `layout-pipeline`スキルでの家具配置パイプラインに接続
