---
name: viz-pydeck
description: Pydeck + Mapboxを用いた、地理空間データのモダンなUI風可視化
---

# 前提スキル (Base Skills)

このスキルを実行する際は、**必ず `python-pro` スキルを同時に参照し**、そこで定義されたコーディング規約（型ヒント、Docstring、pathlib使用など）を遵守してください。

# デザイン指針

- **ベースマップ:** 原則として `mapbox://styles/mapbox/dark-v11` または `satellite-streets-v12` を使用し、データの発光を引き立てる。
- **配色:** データ値（地価等）は、寒色から暖色へのグラデーション（例: 青→紫→赤→黄）を使用し、不透明度（opacity）を0.8程度に設定して地図を透かす。
- **照明:** `lighting_effect` を必ず有効にし、3Dの柱（ColumnLayer/HexagonLayer）に陰影をつけることで立体感を出す。

# 実装ルール

- **インタラクション:** ツールチップ（pickable=True）を設定し、マウスオーバーで詳細情報を表示させる。
- **ビュー設定:** `pdk.ViewState` では、真上（pitch=0）ではなく、斜め45度（pitch=45）からの視点をデフォルトとし、建物の高さを強調する。
- **出力:** HTMLファイルとしてエクスポートし、ブラウザでのスムーズな動作を最優先する。
- **Deckオブジェクト**: 必ず`map_provider`を設定する。

```python
deck_params = {
    "map_provider": "mapbox",
    "layers": layers,
    "initial_view_state": view_state,
    "effects": [lighting_effect],
    "tooltip": tooltip,
    "map_style": map_style,
}
deck = pdk.Deck(**deck_params)
```
