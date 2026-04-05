---
name: floor-plan-elements
description: クリーンSVG間取り図をPNG化し、ピクセルデータ分析で壁・柱の建築要素を個別の<rect>要素としてSVG化する。反復ループとサブエージェントレビューで品質を担保する。間取り図の要素抽出、壁rect配置、柱検出、PNG間取り図からSVG要素生成に関連するタスクで必ずこのスキルを参照すること。floor-plan-traceがPNG→クリーンSVGを生成するのに対し、このスキルはSVGから建築要素を個別rect化する。
argument-hint: [クリーンSVG] [原図PNG(省略可)] [出力ディレクトリ(省略可)]
allowed-tools: Bash(uv run *), Bash(python3 *), Bash(magick *)
---

# SVG間取り図 → 要素別SVG

クリーンSVG間取り図（`floor-plan-trace`出力）をPNG化し、ピクセルデータ分析で壁・柱の建築要素を検出して、個別の`<rect>`要素としてSVGに配置する。

## なぜこのアプローチか

potraceのSVG出力は「面の塗りつぶし」構造（even-odd fill rule）のため、壁・ドア弧・柱が1つの複合パスに結合され、個別分離が構造的に不可能。代わりにPNG画像を直接分析し、要素を個別の`<rect>`として新規生成する。

Blenderは`<rect>`をインポート可能（4点の閉じたパスに変換）、`<image>`は無視されるため、背景画像付きSVGでの編集・確認が可能。

## 前提条件

- `floor-plan-trace` で生成されたクリーンSVG（`{stem}_floor_plan.svg`）
- ImageMagick（`magick`コマンド）がインストール済み

## コマンド実行ルール

変数代入（`OUTDIR=...`等）とコマンド（`magick`, `uv run`等）は必ず別の行で実行すること。同一行に書くと `allowed-tools` のパターンマッチが効かず許可プロンプトが出る。

## スクリプト

`.claude/skills/floor-plan-elements/scripts/element_tools.py` を使用する。

| サブコマンド | 用途 |
|---|---|
| `template` | PNG背景埋め込みSVGテンプレート生成（walls/pillars/doors/glass_doors/windows/fixturesの6グループ） |
| `scan` | PNG画像から壁の特徴点（端点・交差点）を検出 |

## 入力 / 出力

- **入力**:
  - クリーンSVG間取り図（`{stem}_floor_plan.svg`）— `floor-plan-trace`の出力
  - 原図PNG（省略可）— 部屋名・設備名の参照用
- **出力ディレクトリ**: 引数で指定可能、省略時は入力SVGと同じディレクトリ

**最終成果物**（`{output_dir}/` 直下）:
- `{stem}_elements.svg` — 要素rect配置済みSVG（グループ別）
- `{stem}_elements_preview.png` — プレビューPNG

**中間成果物**（`{output_dir}/work/` 配下、処理過程で自動生成）:
- `{stem}_floor_plan_render.png` — SVG→PNG変換結果
- `{stem}_template.svg` — 背景画像埋め込みテンプレート
- `{stem}_keypoints.json` — 特徴点データ
- `{stem}_keypoints_preview.png` — 特徴点可視化画像
- `{stem}_elements_iter{N}.svg` / `{stem}_elements_iter{N}_preview.png` — 各イテレーションの配置結果

## 要素カテゴリ

| カテゴリ | SVGグループ | 検出方法 | rect色 |
|---------|-----------|---------|--------|
| 壁 (wall) | `<g id="walls">` | ピクセルスキャン: 水平/垂直の長い黒セグメント | fill="rgba(255,0,0,0.3)" stroke="red" |
| 柱 (pillar) | `<g id="pillars">` | ピクセルスキャン: 小さい正方形に近い黒領域 | fill="rgba(0,128,0,0.3)" stroke="green" |
| ドア (door) | `<g id="doors">` | 原図目視: ドア弧記号 | fill="rgba(0,0,255,0.3)" stroke="blue" |
| ガラスドア (glass_door) | `<g id="glass_doors">` | 原図目視: 引き戸記号+外壁 | fill="rgba(0,255,255,0.3)" stroke="cyan" |
| 窓 (window) | `<g id="windows">` | 原図目視: 二重線記号 | fill="rgba(0,255,0,0.3)" stroke="lime" |
| 設備 (fixture) | `<g id="fixtures">` | 原図目視 | 未定義 |

## 全体フロー

```
Step 1: 入力確認 + SVG→PNG変換
Step 2: テンプレート生成
Step 3: 特徴点検出
Step 4: ピクセル分析（壁セグメント計測）
Step 5: イテレーション型要素配置
  ├─ Iteration 1: 外壁 → レビュー（サブエージェント）
  ├─ Iteration 2: 内壁 → レビュー
  ├─ Iteration 3: 柱 → レビュー
  ├─ Iteration 4: ドア・ガラスドア・窓 → レビュー
  ├─ Iteration N: 修正・追加 → レビュー
  └─ 完了条件を満たしたら終了
Step 6: 最終出力
```

## 実行手順

### Step 1: 入力確認 + SVG→PNG変換

入力SVGの存在を確認し、作業ディレクトリを作成してPNGに変換する。

```bash
OUTDIR="<出力ディレクトリ>"
WORKDIR="$OUTDIR/work"
mkdir -p "$WORKDIR"
magick -background white -density 150 "{floor_plan_svg}" "$WORKDIR/{stem}_floor_plan_render.png"
```

→ 報告: 「入力SVG確認。PNG変換完了: {W}x{H}px」

### Step 2: テンプレート生成

PNG画像を背景として埋め込んだSVGテンプレートを生成する。

```bash
uv run .claude/skills/floor-plan-elements/scripts/element_tools.py template "$WORKDIR/{stem}_floor_plan_render.png" -o "$WORKDIR"
```

出力: `{stem}_template.svg`（PNG背景埋め込み + 空のwalls/pillars/doors/glass_doors/windows/fixturesグループ）

→ 報告: 「テンプレートSVG生成完了。画像サイズ: {W}x{H}px」

### Step 3: 特徴点検出

ピクセルデータから壁の特徴点を検出する。

```bash
uv run .claude/skills/floor-plan-elements/scripts/element_tools.py scan "$WORKDIR/{stem}_floor_plan_render.png" -o "$WORKDIR"
```

出力:
- `{stem}_keypoints.json` — 特徴点リスト
- `{stem}_keypoints_preview.png` — 特徴点可視化画像

**検出後の確認**:
1. `_keypoints_preview.png` を読み取り、特徴点の位置を確認する
2. 赤い点（端点）が壁の行き止まりに正しく配置されているか
3. 青い点（交差点）が壁の接合部に正しく配置されているか

→ 報告: 「特徴点検出完了。端点: {N}個, 交差点: {N}個」

### Step 4: ピクセル分析

壁線PNGを直接スキャンし、壁セグメントの正確な座標と厚さを計測する。

**4-1: 水平スキャン**

`uv run python3` インラインスクリプトで、主要なy座標における水平方向の黒ピクセルセグメントを検出する。

```python
from PIL import Image
import numpy as np

img = Image.open("$WORKDIR/{stem}_floor_plan_render.png").convert("L")
arr = np.array(img)
walls = arr < 128  # 黒ピクセル = 壁

# 指定yでの水平セグメント検出（長さ20px以上）
for y in [主要なy座標リスト]:
    row = walls[y]
    # 連続する黒ピクセルの開始・終了位置を取得
    # → segments: [(x_start, x_end), ...]
```

スキャン対象のy座標は、特徴点のy座標クラスタ（±5px）と、画像の上端・下端付近を選ぶ。

**4-2: 垂直スキャン**

同様に、主要なx座標における垂直方向のセグメントを検出する。

**4-3: 壁厚計測**

各壁セグメントについて、垂直方向（水平壁の場合）または水平方向（垂直壁の場合）のピクセル幅を計測し、壁厚を決定する。

- 外壁: 概ね16-18px
- 内壁: 概ね8-13px
- 薄い仕切り: 4-5px

**4-4: 柱候補の検出**

壁の交差部付近で、正方形に近い小さい黒領域を検出する。柱は壁厚より大きく、壁長さより小さい正方形的な領域として特定する。

```python
# 柱の候補: アスペクト比が1に近く、面積が壁厚^2〜壁厚^2*4の矩形
# 壁交差部（2方向以上の壁が接合する点）の付近を重点スキャン
```

**4-5: 結果のまとめ**

分析結果を整理し、以下の情報を把握する:
- 各壁セグメントの座標範囲（x_start, x_end または y_start, y_end）
- 壁厚（ピクセル）
- 壁のカテゴリ（外壁/内壁/薄い仕切り）
- 柱候補の位置と大きさ

→ 報告: 「ピクセル分析完了。水平セグメント: {N}個, 垂直セグメント: {N}個, 柱候補: {N}個」

### Step 5: イテレーション型要素配置

要素の配置・プレビュー生成・レビューを繰り返し、段階的に品質を上げる。

#### イテレーション共通フロー

```
1. 配置: 対象カテゴリの要素rectをSVGに追加/修正（uv run python3 スクリプト）
2. プレビュー生成: magick でSVG→PNG変換
3. レビュー: サブエージェント（Agent tool）でプレビューを評価
4. 判定: PASS → 次のイテレーション or 完了 / NEEDS_FIX → 修正して再レビュー
```

#### Iteration 1: 外壁配置

Step 4のピクセル分析結果から、外壁（建物の外周を構成する壁）を配置する。

**配置対象**: 北壁（上辺）、東壁（右辺）、南壁（下辺）、西壁（左辺）、段差接続壁

**配置方法**:
`uv run python3` インラインスクリプトで、テンプレートSVGの `<g id="walls" />` を `<g id="walls">...rects...</g>` に置換する。

**rectの属性**:
```xml
<rect id="wall_001" x="144" y="83" width="652" height="17"
      fill="rgba(255,0,0,0.3)" stroke="red" stroke-width="1.5"
      data-label="北側外壁"/>
```

**プレビュー生成**:
```bash
magick -background white -density 150 {svg_path} {preview_png_path}
```

**レビュー**: → 「レビューサブエージェント」を参照

→ 報告: 「Iteration 1完了。外壁{N}個を配置」

#### Iteration 2: 内壁配置

部屋を仕切る主要な内壁を追加配置する。

**配置対象**: 部屋間の仕切り壁、ホール・玄関の区画壁、水回りの区画壁

→ 報告: 「Iteration 2完了。内壁{N}個を追加。累計壁数{N}個」

#### Iteration 3: 柱配置

Step 4-4で検出した柱候補を配置する。

**配置対象**: 壁交差部の柱、独立柱

**配置方法**:
`<g id="pillars">` 内にrect要素を追加:
```xml
<rect id="pillar_001" x="143" y="82" width="18" height="18"
      fill="rgba(0,128,0,0.3)" stroke="green" stroke-width="1.5"
      data-label="北西角柱"/>
```

**レビュー時の確認ポイント**:
- 壁の交差部に正しく配置されているか
- 壁rectと柱rectが適切に接続しているか
- 独立柱（壁に接しない柱）が見落とされていないか

→ 報告: 「Iteration 3完了。柱{N}個を配置」

#### Iteration 4: ドア・ガラスドア・窓配置

原図PNG（カラー間取り）を読み取り、壁の切れ目（開口部）に対応する要素を配置する。ピクセル分析では検出できないため、原図の記号を目視で判断する。

**分類基準**:
- **door**: ドア弧（円弧）記号あり。木製・不透過。室内間仕切りの開口部
- **glass_door**: 引き戸記号あり。ガラス・透過。ベランダ等への出入り口（掃き出し窓）
- **window**: 二重線記号あり。ガラス・透過。通行不可の腰高以上の開口部
- 判断に迷う場合は `glass_doors` に寄せる（Cyclesの光透過確保を優先）

**配置方法**:
各グループにrect要素を追加。壁の切れ目に隙間なく配置する。

```xml
<!-- door -->
<rect id="door_001" x="272" y="173" width="118" height="14"
      fill="rgba(0,0,255,0.3)" stroke="blue" stroke-width="1.5"
      data-label="玄関ドア"/>
<!-- glass_door -->
<rect id="glass_door_001" x="386" y="1432" width="150" height="9"
      fill="rgba(0,255,255,0.3)" stroke="cyan" stroke-width="1.5"
      data-label="ベランダ掃き出し窓(左)"/>
<!-- window -->
<rect id="window_001" x="508" y="86" width="188" height="9"
      fill="rgba(0,255,0,0.3)" stroke="lime" stroke-width="1.5"
      data-label="北側窓"/>
```

→ 報告: 「Iteration 4完了。ドア{N}個, ガラスドア{N}個, 窓{N}個を配置」

#### Iteration 5以降: 修正・追加

レビューサブエージェントの指摘に基づき、以下を実施:
- **missing**: 欠けている要素のrectを追加
- **misaligned**: ずれているrectの座標を修正
- **false_positive**: 誤配置されたrectを削除
- **wrong_category**: カテゴリ誤りのrectを正しいグループに移動

→ 報告: 「Iteration {N}完了。修正{N}件」

#### 完了条件

以下のいずれかを満たしたらイテレーション終了:
- レビューサブエージェントが `"status": "PASS"` を返す
- priority=high の issue が0件
- 最大7イテレーション（無限ループ防止）

---

### レビューサブエージェント

各イテレーション後に **Agent tool** でサブエージェントを起動し、配置結果をレビューさせる。

**Agent プロンプトテンプレート**:

```
あなたは建築要素（壁・柱・ドア・ガラスドア・窓）の配置レビューエージェントです。
プレビューPNG・壁線PNG・原図PNGを読み取り、要素rectの配置品質を評価してください。

## 入力ファイル
- プレビューPNG（要素rect重畳）: {preview_png_path}
- 壁線PNG（背景参照）: {floor_plan_render_png_path}
- 原図PNG（部屋名・ドア弧参照）: {original_png_path}
- 現在の要素数: 壁{wall_count}個, 柱{pillar_count}個, ドア{door_count}個, ガラスドア{glass_door_count}個, 窓{window_count}個
- イテレーション: {iteration_number}

## レビュー基準

### 壁 (walls)
1. 位置一致: 壁rectが背景の黒い壁線と正確に重なっているか
2. 網羅性: 全ての壁線がrectでカバーされているか
3. 誤検出: 壁以外の要素にrectが重なっていないか
4. 厚さ: 外壁は16-18px、内壁は8-13pxが目安
5. 接続: T字・L字接合部でrectが正しく繋がっているか

### 柱 (pillars)
1. 位置: 壁の交差部に正しく配置されているか
2. サイズ: 壁厚に合った正方形サイズか
3. 漏れ: 交差部に柱が見落とされていないか

### ドア (doors) / ガラスドア (glass_doors) / 窓 (windows)
1. 位置: 壁の切れ目（開口部）に正しく配置されているか
2. 分類: ドア弧=door、引き戸+外壁=glass_door、二重線=windowの対応が正しいか
3. 網羅性: 原図の全開口部がカバーされているか
4. 光透過の区別: ガラス要素（glass_door/window）と不透過要素（door）が正しく分離されているか

## 確認手順
1. プレビューPNGを読み取り、各色のrectと背景の壁線の一致を確認
2. 壁線PNGを読み取り、rectでカバーされていない壁線を探す
3. 原図PNGを読み取り、部屋のレイアウトを参照
4. 問題をリストアップ

## 出力形式

以下のJSON形式で報告すること（JSON以外の出力は不要）:

{
  "status": "PASS" または "NEEDS_FIX",
  "issues": [
    {
      "type": "missing" | "misaligned" | "false_positive" | "thickness" | "wrong_category",
      "category": "wall" | "pillar" | "door" | "glass_door" | "window",
      "description": "具体的な問題の説明（位置情報を含む）",
      "priority": "high" | "medium" | "low",
      "suggested_fix": "修正案（座標値を含む場合は明記）"
    }
  ],
  "summary": "全体の評価サマリー（1-2文）"
}
```

**レビュー結果の処理（親エージェント側）**:
- `"status": "PASS"` → 次のイテレーション or Step 6
- `"status": "NEEDS_FIX"` → issues の内容に基づき修正イテレーションを実施

---

### Step 6: 最終出力

全イテレーション完了後、最終ファイルを `$OUTDIR` 直下に保存する。

1. 要素rect確定版SVGを `$OUTDIR/{stem}_elements.svg` として保存
2. プレビューPNGを `$OUTDIR/{stem}_elements_preview.png` として保存

```bash
cp "$WORKDIR/{stem}_elements_iter{N}.svg" "$OUTDIR/{stem}_elements.svg"
magick -background white -density 150 "$OUTDIR/{stem}_elements.svg" "$OUTDIR/{stem}_elements_preview.png"
```

→ 報告: 「要素配置完了。壁: {N}個, 柱: {N}個, ドア: {N}個, ガラスドア: {N}個, 窓: {N}個。{output_path}」

## 壁rectの配置基準

### 壁の認定基準

- 水平または垂直の直線であること（斜め壁は対象外）
- 両端が特徴点で定義されること
- 壁厚は元画像の黒ピクセル幅から自動計測（概ね8-18px）

### Blenderインポート時の変換

Blenderに取り込む前に `fill` を `#000000`（黒）に変更する。`<image>`要素はBlenderが無視するため、手動削除不要。

## 既知の制約

- スケルトン化アルゴリズムの特性上、ドア弧や曲線部分にも特徴点（交差点）が誤検出される。壁の直線上にある特徴点のみを使用すること
- 壁厚が一定でない場合（外壁と内壁で異なる等）、手動で壁厚を調整する必要がある
- 斜め壁には対応していない（水平・垂直の壁のみ）
- 特徴点検出の精度は入力画像の品質に依存する。ノイズの多い画像ではクラスタリング半径の調整が必要
## 後続ワークフロー

- 要素rect確定版SVGをBlenderにインポート → extrude → 3Dモデル化
- `layout-floor-plan-annotate`スキルでの部屋定義に接続
- `layout-pipeline`スキルでの家具配置パイプラインに接続
