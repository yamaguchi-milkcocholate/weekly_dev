---
name: floor_plan_to_video_sub_annotate
description: SVGからdrawioテンプレートを生成し、ユーザーの手作業アノテーション後にroom_info.jsonと完成版SVGに統合する。間取り図に部屋・ドア・窓・設備・配置不可領域を定義したい、drawioでの空間アノテーション、drawioファイルからroom_info.jsonを生成したいときに使用する。drawio、部屋定義、空間アノテーション、room_info、floor_plan_completeに関連するタスクで必ずこのスキルを参照すること。
argument-hint: <出力ディレクトリ> [integrate]
---

# floor_plan_to_video_sub_annotate

間取りSVGにユーザーが空間情報（部屋・ドア・窓・固定設備・配置不可領域）を定義するためのdrawioテンプレートを生成し、完了後に実座標データとして統合するスキル。

## モード

- **`<出力ディレクトリ>`**: テンプレート生成モード（出力ディレクトリ内のfloor_plan.svgを読む）
- **`<出力ディレクトリ> integrate`**: 統合モード（drawio → room_info.json + floor_plan_complete.svg）

全入出力ファイルは指定された出力ディレクトリ内に配置する。

---

## テンプレート生成モード（引数なし）

### 入力

- `floor_plan.svg` — Phase 1で生成された間取りSVG
- `floor_plan_meta.json` — SVGの座標メタデータ（あれば）

### 出力

- `floor_plan_rooms.drawio` — アノテーション用drawioファイル

### 処理手順

#### Step 1: SVGをBase64エンコード

```python
import base64
from pathlib import Path

svg_content = Path("floor_plan.svg").read_text()
svg_b64 = base64.b64encode(svg_content.encode()).decode()
```

#### Step 2: drawioテンプレートXMLを生成

drawioのXML構造:
1. SVG画像をBase64でbackground imageとして埋め込み（ロック状態、位置: x=50, y=50, w=800, h=960）
2. 凡例パーツ5種をテンプレートセルとして配置（固定IDで後から除外可能にする）

#### Step 3: 凡例パーツの定義

ユーザーがコピー&配置する5種のパーツ:

| # | パーツ | fillColor | strokeColor | 用途 |
|---|--------|-----------|-------------|------|
| ① 部屋 | `#BBDEFB` | `#1976D2` | 部屋の範囲と名前を定義 |
| ② ドア | `#E91E63` | — | ドアの位置を示す |
| ③ 窓 | `#00BCD4` | — | 窓の位置を示す |
| ④ 固定設備 | `#E1BEE7` | `#7B1FA2` | キッチン・収納等の固定設備 |
| ⑤ 配置不可 | `#FFEBEE` | `#F44336` (dashed=1) | 通路・収納前等、家具を置けない領域 |

#### Step 4: ユーザーへの案内

drawioファイルを生成後、ユーザーに以下を案内する:

1. drawio.ioまたはdraw.ioデスクトップアプリで開く
2. 凡例パーツをコピーして、SVGの壁にピッタリ合わせて矩形を配置
3. 各矩形にラベルを記入:
   - 部屋: 部屋名（例: 寝室、リビング）
   - 固定設備: 設備名（例: キッチン、収納）
   - 配置不可: 理由（例: 通路、通路(50%空いていれば良い)、収納前）
4. **配置不可領域の「50%ルール」**: ラベルに「50%」を含めると、面積の50%までは家具が重なってもOKとなる

**操作Tips**: drawioのグリッドは10px単位。Alt+ドラッグで1px単位の細かい配置が可能。

---

## 統合モード（`integrate`引数あり）

### 入力

- `floor_plan_rooms.drawio` — ユーザーがアノテーション済みのdrawioファイル
- `walls.json` — 壁座標データ
- `floor_plan_meta.json` — SVGの座標メタデータ（あれば。なければデフォルト値を使用）

### 出力

- `room_info.json` — 部屋・設備・配置不可領域の実座標データ
- `floor_plan_complete.svg` — 壁データ+空間情報を統合した完成版SVG

### 処理手順

#### Step 3-1: drawioからデータ抽出

drawioのXMLをパースし、テンプレートセル（凡例の固定ID）を除外してユーザー追加セルを抽出する。

**タイプ判定**: セルのstyleに含まれる色コードで判定:

```python
COLOR_TYPE_MAP = {
    "BBDEFB": "room", "1976D2": "room",
    "E91E63": "door",
    "00BCD4": "window",
    "E1BEE7": "fixture", "7B1FA2": "fixture",
    "FFEBEE": "no_place", "F44336": "no_place",
}
```

各セルから取得する情報:
- `type`: 色コードから判定したタイプ
- `label`: セルのテキスト内容
- `drawio_px`: {x, y, w, h} — drawio上のピクセル座標

#### Step 3-2: 座標変換（drawio px → 実座標m）

SVGのviewBoxと表示サイズをそのまま使えるため、変換は正確:

```python
# デフォルト値（floor_plan_meta.jsonがあればそちらを使用）
VIEWBOX = {"x": -3, "y": -5.5, "w": 10, "h": 12}
IMAGE_POS = {"x": 50, "y": 50, "w": 800, "h": 960}

def drawio_to_real(drawio_x, drawio_y, drawio_w, drawio_h):
    real_x = VIEWBOX["x"] + (drawio_x - IMAGE_POS["x"]) / IMAGE_POS["w"] * VIEWBOX["w"]
    real_y_top = -VIEWBOX["y"] - (drawio_y - IMAGE_POS["y"]) / IMAGE_POS["h"] * VIEWBOX["h"]
    real_w = drawio_w / IMAGE_POS["w"] * VIEWBOX["w"]
    real_h = drawio_h / IMAGE_POS["h"] * VIEWBOX["h"]
    return {
        "x_min": real_x,
        "x_max": real_x + real_w,
        "y_min": real_y_top - real_h,  # Blender Y: 下が小さい
        "y_max": real_y_top,
        "width": real_w,
        "depth": real_h,
    }
```

#### Step 3-3: room_info.json のスキーマ

```json
[
  {
    "type": "room",
    "label": "寝室",
    "drawio_px": {"x": 100, "y": 80, "w": 230, "h": 120},
    "real_m": {
      "x_min": -2.2, "x_max": 0.688,
      "y_min": 2.55, "y_max": 4.05,
      "width": 2.89, "depth": 1.5
    }
  }
]
```

#### Step 3-4: 完成版SVG生成

`walls.json`の壁データと`room_info.json`の空間情報を統合したSVGを生成:

- 壁・柱を描画（walls.jsonから）
- 部屋矩形（青半透明）+ ラベル
- 固定設備（紫半透明）+ ラベル
- 配置不可領域（赤破線）+ ラベル
- ドア・窓の位置
- グリッド線（1m間隔）+ 軸ラベル

このSVGは後続のfloor_plan_to_video_sub_refineスキルでClaude Codeが画像として読んで空間を認識する基盤となる。

---

## 既知の問題

### SVG画像のdrawio上での位置ずれ

drawioにSVG画像を埋め込んだ際、画像の表示位置が期待値とずれることがある。

- 症状: drawio上で壁にピッタリ配置した矩形の座標変換で誤差が発生（例: 実際1.9mが1.5mに）
- 原因候補: drawioのSVGレンダリング時のパディングまたはスケーリングのずれ
- 対策: drawio上の基準点を2点以上取ってアフィン変換で補正するか、ユーザーに確認
