# 仕様書：pydeck によるメッシュデータ検証（徒歩分数＋駅別色分け）

## 1. 目的

作成された `tokyo_23_mesh_master.csv` を 3D 可視化し、以下の 2 点を同時に検証する。

- **起伏**: 徒歩分数（`walk_minutes`）が正しく勾配を作っているか。
- **勢力圏**: 各メッシュが「最も近い駅」に正しく紐付けられ、駅ごとの境界が妥当か。

## 2. 実装環境

- **言語**: Python 3.10+
- **ライブラリ**: `pandas`, `pydeck`

## 3. 入力データ

- **ファイル名**: `tokyo_23_mesh_master.csv`
- **主要カラム**: `latitude`, `longitude`, `walk_minutes`, `station_name`

## 4. 実装詳細

### Step 1: データのロードと色割り当て（新規追加）

- `pandas` でデータを読み込む。
- **駅別カラーマップの作成**:
- ユニークな `station_name` のリストを取得する。
- 各駅に対して、ランダムまたはカラーパレット（例：`matplotlib` の `tab20` 等）を用いて一意の **RGB カラー [R, G, B]** を割り当てる。
- データフレームに `color` カラム（RGBのリスト）を追加する。
- _ヒント_: 駅数が多い（数百駅）ため、ハッシュ値を用いて色を生成するか、パレットをループさせて色の重複を避けるロジックにすること。

### Step 2: pydeck レイヤーの設定

- **Layer Type**: `ColumnLayer`
- **配置**:
- `get_position`: `[longitude, latitude]`
- `get_elevation`: `walk_minutes`
- `elevation_scale`: 30〜50（視覚効果に応じて調整）
- `radius`: 50〜80

- **カラー設定（変更）**:
- `get_fill_color`: **`color`（Step 1 で割り当てた駅ごとの色）**。
- `pickable`: True（クリック可能にする）

### Step 3: ビューポートと UI

- **初期視点**: 東京23区中心、ピッチ 45度。
- **Tooltip**:
- `駅名: {station_name}`
- `徒歩: {walk_minutes} 分`
- `住所: {city_name} {district_name}`

### Step 4: ファイル出力

- `mesh_verification_colored.html` として保存。

## 5. 検証ポイント（期待される結果）

- **色の境界線**: 同じ色のメッシュ群が、その駅を囲むように「島」状に集まっていること。
- **地形の谷**: 各色の「島」の中心（駅の所在地）が最も低く（ に近く）、島の間（駅間）が盛り上がっていること。
- **孤立点**: 別の駅の色の島の中に、ポツンと違う色のメッシュが混ざっていないか（計算ミスがないか）。

---
