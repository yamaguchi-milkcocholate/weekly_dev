# 東京23区メッシュマスター生成ガイド

## 概要

東京23区を100m四方のメッシュで分割し、各メッシュ中心点に以下の情報を付与したマスターテーブルを生成します：

- 市区町村名
- 地区名
- 最寄駅名
- 駅からの直線距離（メートル）
- 徒歩分数（距離÷80m/分）

## 必要なデータ

### 1. 駅データCSV

ekidata.jpから取得した駅データCSVを配置してください。

**配置場所:** `data/station/station20251211free.csv`

**取得元:** https://ekidata.jp/

### 2. 行政区域GeoJSON

東京23区の行政区域GeoJSONファイルを配置してください。

**配置場所:** `data/boundary/`

**ファイル名形式:** `{市区町村コード}.json` (例: `13101.json`, `13102.json`, ...)

**取得元:** https://github.com/niiyz/JapanCityGeoJson

**必要なファイル:**

```
data/boundary/13101.json  # 千代田区
data/boundary/13102.json  # 中央区
data/boundary/13103.json  # 港区
...（全23区分）
data/boundary/13123.json  # 江戸川区
```

**取得方法:**

```bash
# 各区のGeoJSONをダウンロード
curl -o data/boundary/13101.json https://raw.githubusercontent.com/niiyz/JapanCityGeoJson/master/geojson/pref/13/13101.json
curl -o data/boundary/13102.json https://raw.githubusercontent.com/niiyz/JapanCityGeoJson/master/geojson/pref/13/13102.json
# ... 全23区分
```

## 使用方法

### 1. 依存関係のインストール

```bash
uv sync
```

### 2. メッシュマスター生成

```bash
python scripts/generate_mesh_master.py
```

### 3. 出力ファイル

生成されたメッシュマスターは以下に保存されます：

**出力先:** `data/tokyo_23_mesh_master.csv`

## 出力データ構造

| カラム名      | 型    | 説明                            |
| ------------- | ----- | ------------------------------- |
| mesh_id       | str   | ユニークなメッシュID            |
| latitude      | float | メッシュ中心の緯度              |
| longitude     | float | メッシュ中心の経度              |
| city_name     | str   | 市区町村名（例: 千代田区）      |
| district_name | str   | 地区名（例: 飯田橋）            |
| station_name  | str   | 最寄駅名（例: 飯田橋）          |
| distance_m    | float | 駅からの直線距離（メートル）    |
| walk_minutes  | float | 徒歩分数（distance_m ÷ 80m/分） |

## プログラムから使用する

```python
from pathlib import Path
from real_state_geo_core.data.mesh_builder import MeshMasterBuilder

# パス設定
station_csv_path = Path("data/station/station20251211free.csv")
boundary_geojson_dir = Path("data/boundary")
output_path = Path("data/tokyo_23_mesh_master.csv")

# メッシュマスター生成
builder = MeshMasterBuilder(
    station_csv_path=station_csv_path,
    boundary_geojson_dir=boundary_geojson_dir,
    mesh_size_m=100.0  # メッシュサイズ（メートル）
)

mesh_master_df = builder.build_mesh_master(output_path=output_path)

# 結果確認
print(f"生成されたメッシュ数: {mesh_master_df.height}")
print(mesh_master_df.head())
```

## パフォーマンス

- 東京23区を100mメッシュで分割すると、約6万〜8万点のメッシュが生成されます
- cKDTreeを使用した高速な最近傍探索により、数分以内に処理が完了します
- メモリ使用量は約500MB〜1GB程度です

## トラブルシューティング

### GeoJSONファイルが見つからない

```
FileNotFoundError: 東京23区のGeoJSONファイルが1つも見つかりませんでした
```

→ `data/boundary/` ディレクトリに23区分のGeoJSONファイルを配置してください。

### 駅データCSVが見つからない

```
FileNotFoundError: 駅データCSVが見つかりません: data/station/station20251211free.csv
```

→ ekidata.jpから駅データCSVをダウンロードし、`data/station/` に配置してください。

### カラムが見つからない

```
ValueError: 駅データCSVに必要なカラム ['station_name', 'lat', 'lon'] が存在しません
```

→ 駅データCSVのフォーマットを確認し、必要なカラムが含まれているか確認してください。
