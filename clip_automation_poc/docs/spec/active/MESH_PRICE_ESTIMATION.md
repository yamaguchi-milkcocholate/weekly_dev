# 仕様書: メッシュ坪単価推定機能

## 1. 概要

### 1.1 目的

東京23区の100mメッシュごとに、機械学習モデル（LightGBM）を用いて**2025年の坪単価相場を推定**し、地理空間データとして出力する。これにより、PyDeckやStreamlit等のBIツールで価格分布のヒートマップを可視化できるようにする。

### 1.2 背景

本機能は、以下2つの既存機能を統合することで実現される:

1. **坪単価推定モデル** (`AREA_PRICE_PREDCTION.md`):
   - LightGBMによる立地・物件条件からの坪単価予測モデル
   - 学習済みモデル（`outputs/price_estimator_model.pkl`）を使用

2. **メッシュマスター** (`MESH_MULTI_STATION.md`):
   - 東京23区の100mメッシュに複数駅を紐付けたマスターデータ
   - 各メッシュから徒歩30分以内の駅情報を保持（縦持ち形式）

### 1.3 スコープ

| 項目               | 範囲                                     |
| ------------------ | ---------------------------------------- |
| **対象エリア**     | 東京23区                                 |
| **メッシュサイズ** | 100m四方                                 |
| **対象年**         | 2025年                                   |
| **物件条件**       | ユーザー指定可能（築年数、面積、構造等） |
| **駅選択ロジック** | 最寄り3駅の平均値                        |
| **出力形式**       | CSV/JSON（Pydeck/Streamlit対応）         |

---

## 2. 入力データ

### 2.1 学習済みモデル

**ファイル**: `outputs/price_estimator_model.pkl`

- **形式**: pickleファイル
- **モデル**: LightGBM Regressor
- **入力特徴量**:
  - 時点特徴量: `Year`, `Month`, `Quarter`
  - 物件特徴量: `Area`, `Age`, `BuildingYear`, `Structure`, `Renovation`
  - 立地特徴量: `NearestStation`, `TimeToNearestStation`, `Municipality`, `DistrictName`, `CityPlanning`
  - 集約統計量: `Municipality_Year_mean_price`, `Municipality_Year_median_price`, `NearestStation_Year_mean_price`, `NearestStation_Year_median_price`
- **出力**: 坪単価（float）

### 2.2 メッシュマスター

**ファイル**: `data/processed/mesh_master_tokyo23_multi.csv`

**スキーマ**:

```python
{
    "mesh_id": str,           # メッシュID (例: "35.681234_139.767890")
    "latitude": float,        # メッシュ中心緯度
    "longitude": float,       # メッシュ中心経度
    "city_name": str,         # 市区町村名 (例: "千代田区")
    "district_name": str,     # 地区名
    "station_name": str,      # 駅名
    "distance_m": float,      # 駅までの距離 (メートル)
    "walk_minutes": float,    # 徒歩分数
}
```

**データ形式**: 縦持ち（1メッシュ×N駅）、距離の近い順にソート済み

### 2.3 集約統計量データ

**ファイル**: `data/ml_dataset/tokyo_23_ml_dataset.csv` から2025年の集計値を算出

**算出方法**:

```python
# 2025年のデータから集約統計量を計算
dataset_df = pl.read_csv("data/ml_dataset/tokyo_23_ml_dataset.csv")

# 2025年のデータのみ抽出
df_2025 = dataset_df.filter(pl.col("transaction_date").dt.year() == 2025)

# Municipality × Year の集約
municipality_stats = df_2025.group_by(["Municipality", "Year"]).agg([
    pl.col("tsubo_price").mean().alias("Municipality_Year_mean_price"),
    pl.col("tsubo_price").median().alias("Municipality_Year_median_price"),
])

# NearestStation × Year の集約
station_stats = df_2025.group_by(["NearestStation", "Year"]).agg([
    pl.col("tsubo_price").mean().alias("NearestStation_Year_mean_price"),
    pl.col("tsubo_price").median().alias("NearestStation_Year_median_price"),
])
```

**保存先**: `outputs/aggregated_stats_2025.csv`

### 2.4 物件条件設定

ユーザーが指定可能なパラメータ:

| パラメータ名   | 型            | デフォルト値 | 説明                                     |
| -------------- | ------------- | ------------ | ---------------------------------------- |
| `target_year`  | int           | 2025         | 対象年                                   |
| `age_range`    | tuple[int, int] | (1, 5)       | 築年数範囲（年）                         |
| `area_sqm`     | float         | 70.0         | 専有面積（平米）                         |
| `structure`    | str           | "RC"         | 建物構造（RC, SRC, S等）                 |
| `renovation`   | str           | "なし"       | 改装の有無                               |
| `city_planning`| str           | "第一種住居地域" | 用途地域                             |

**補足**: `BuildingYear` は `target_year - age_range[0]` で計算される（築年数範囲の最小値を使用）。

---

## 3. 処理フロー

### 3.1 全体フロー

```
Step 1: データ読み込み
   ├── 学習済みモデル（pickle）
   ├── メッシュマスター（CSV）
   └── 集約統計量マスター（CSV） ← 2025年データから算出
   ↓
Step 2: 物件条件の設定
   ├── ユーザー指定パラメータの取得
   └── 固定値の設定（Year=2025, Month=6, Quarter=2）
   ↓
Step 3: メッシュ単位の特徴量生成
   ├── 最寄り3駅の抽出（メッシュIDでグルーピング）
   └── 駅ごとに特徴量を生成（3パターン）
   ↓
Step 4: 坪単価の予測
   ├── 3駅分のデータでモデル予測
   └── 3つの予測値の平均を計算
   ↓
Step 5: 結果の集約と出力
   ├── メッシュIDごとに集約
   ├── 地理空間情報（緯度・経度）を付与
   └── CSV/JSONで保存
```

### 3.2 Step 3: メッシュ単位の特徴量生成（詳細）

各メッシュについて、以下の処理を行う:

#### 3.2.1 最寄り3駅の抽出

```python
# メッシュマスターを読み込み（距離順にソート済み）
mesh_df = pl.read_csv("data/processed/mesh_master_tokyo23_multi.csv")

# 各メッシュの最寄り3駅を取得
top3_stations = mesh_df.group_by("mesh_id").agg(
    pl.all().sort_by("distance_m").head(3)
)
```

**エッジケース**:
- 駅が3駅未満の場合: 存在する駅のみを使用（1駅または2駅の平均）
- 駅が0駅の場合: そのメッシュは予測対象外（結果から除外）

#### 3.2.2 特徴量の生成

各駅に対して、以下の特徴量を生成:

```python
{
    # 時点特徴量（固定）
    "Year": 2025,
    "Month": 6,
    "Quarter": 2,

    # 物件特徴量（ユーザー指定）
    "Area": 70.0,  # 専有面積（平米）
    "Age": 3,      # 築年数範囲の中央値（例: 1-5年 → 3年）
    "BuildingYear": 2022,  # 2025 - 3
    "Structure": "RC",
    "Renovation": "なし",

    # 立地特徴量（メッシュ・駅情報から取得）
    "NearestStation": "東京",  # 駅名
    "TimeToNearestStation": 2.5,  # 徒歩分数（四捨五入）
    "Municipality": "千代田区",
    "DistrictName": "",
    "CityPlanning": "第一種住居地域",

    # 集約統計量（2025年データから計算済み）
    "Municipality_Year_mean_price": 1800000.0,
    "Municipality_Year_median_price": 1750000.0,
    "NearestStation_Year_mean_price": 1900000.0,
    "NearestStation_Year_median_price": 1850000.0,
}
```

**注意点**:
- `TimeToNearestStation` は整数値に丸める（モデル学習時のデータ型に合わせる）
- 集約統計量は**2025年のデータから計算されたマスター**（`outputs/aggregated_stats_2025.csv`）から取得

---

## 4. 駅選択ロジック: 最寄り3駅の平均

### 4.1 計算方法

各メッシュについて、以下のステップで坪単価を計算:

1. 最寄り3駅を距離順に抽出
2. 各駅について、上記の特徴量を生成
3. モデルで3つの坪単価を予測
4. **3つの予測値の平均**を、そのメッシュの坪単価とする

**計算式**:

```python
predicted_price_mesh = (price_station1 + price_station2 + price_station3) / 3
```

### 4.2 エッジケースの処理

| ケース         | 処理方法                                     |
| -------------- | -------------------------------------------- |
| 駅が3駅以上    | 最寄り3駅の平均を使用                        |
| 駅が2駅        | 2駅の平均を使用                              |
| 駅が1駅        | 1駅のみの予測値を使用（平均なし）            |
| 駅が0駅        | 予測対象外（結果から除外）                   |

### 4.3 重み付け平均の検討（将来拡張）

現在は単純平均だが、将来的には距離による重み付け平均も検討可能:

```python
# 距離の逆数で重み付け
weights = [1 / d for d in distances[:3]]
weights_normalized = [w / sum(weights) for w in weights]

predicted_price_mesh = sum(p * w for p, w in zip(prices, weights_normalized))
```

**現行版では実装しない**（シンプルさを優先）。

---

## 5. 集約統計量の準備

### 5.1 2025年の集約統計量算出

**スクリプト**: `scripts/prepare_aggregated_stats_2025.py`

```python
#!/usr/bin/env python3
"""2025年の集約統計量を算出するスクリプト"""

import polars as pl
from pathlib import Path

def main():
    project_root = Path(__file__).parent.parent
    dataset_path = project_root / "data" / "ml_dataset" / "tokyo_23_ml_dataset.csv"
    output_path = project_root / "outputs" / "aggregated_stats_2025.csv"

    # データ読み込み
    df = pl.read_csv(dataset_path)

    # 2025年のデータのみ抽出
    df_2025 = df.filter(pl.col("transaction_date").dt.year() == 2025)

    print(f"2025年のデータ件数: {df_2025.height}件")

    # Year列を追加
    df_2025 = df_2025.with_columns(
        pl.col("transaction_date").dt.year().alias("Year")
    )

    # Municipality × Year の集約
    municipality_stats = df_2025.group_by(["Municipality", "Year"]).agg([
        pl.col("tsubo_price").mean().alias("Municipality_Year_mean_price"),
        pl.col("tsubo_price").median().alias("Municipality_Year_median_price"),
    ])

    # NearestStation × Year の集約
    station_stats = df_2025.group_by(["NearestStation", "Year"]).agg([
        pl.col("tsubo_price").mean().alias("NearestStation_Year_mean_price"),
        pl.col("tsubo_price").median().alias("NearestStation_Year_median_price"),
    ])

    # 結合
    stats_df = municipality_stats.join(
        station_stats,
        on="Year",
        how="outer"
    )

    # 保存
    stats_df.write_csv(output_path)
    print(f"集約統計量を保存しました: {output_path}")

if __name__ == "__main__":
    main()
```

### 5.2 集約統計量のマージ処理

予測時に、特徴量DataFrameに集約統計量をマージする:

```python
# 集約統計量マスター読み込み
stats_df = pl.read_csv("outputs/aggregated_stats_2025.csv")

# 特徴量DataFrameにマージ
features_df = features_df.join(
    stats_df.select(["Municipality", "Year", "Municipality_Year_mean_price", "Municipality_Year_median_price"]),
    on=["Municipality", "Year"],
    how="left"
).join(
    stats_df.select(["NearestStation", "Year", "NearestStation_Year_mean_price", "NearestStation_Year_median_price"]),
    on=["NearestStation", "Year"],
    how="left"
)
```

---

## 6. 出力データスキーマ

### 6.1 メッシュ坪単価マップ (`outputs/mesh_price_map_2025.csv`)

**用途**: PyDeck/Streamlitでのヒートマップ可視化

| カラム名                  | 型     | 説明                                     |
| ------------------------- | ------ | ---------------------------------------- |
| `mesh_id`                 | String | メッシュID (例: "35.681234_139.767890")  |
| `latitude`                | Float  | メッシュ中心緯度                         |
| `longitude`               | Float  | メッシュ中心経度                         |
| `city_name`               | String | 市区町村名 (例: "千代田区")              |
| `district_name`           | String | 地区名                                   |
| `predicted_price`         | Float  | 予測坪単価（3駅の平均）                  |
| `station_1_name`          | String | 最寄り駅1                                |
| `station_1_distance_m`    | Float  | 駅1までの距離（メートル）                |
| `station_1_walk_minutes`  | Float  | 駅1までの徒歩分数                        |
| `station_1_predicted_price` | Float | 駅1の予測坪単価                          |
| `station_2_name`          | String | 最寄り駅2（存在しない場合は空文字列）    |
| `station_2_distance_m`    | Float  | 駅2までの距離（存在しない場合はNaN）     |
| `station_2_walk_minutes`  | Float  | 駅2までの徒歩分数                        |
| `station_2_predicted_price` | Float | 駅2の予測坪単価                          |
| `station_3_name`          | String | 最寄り駅3                                |
| `station_3_distance_m`    | Float  | 駅3までの距離                            |
| `station_3_walk_minutes`  | Float  | 駅3までの徒歩分数                        |
| `station_3_predicted_price` | Float | 駅3の予測坪単価                          |
| `num_stations_used`       | Int    | 平均計算に使用した駅数（1〜3）           |

### 6.2 物件条件メタデータ (`outputs/mesh_price_map_2025_metadata.json`)

**用途**: 生成時の条件を記録

```json
{
  "target_year": 2025,
  "age_range": [1, 5],
  "area_sqm": 70.0,
  "structure": "RC",
  "renovation": "なし",
  "city_planning": "第一種住居地域",
  "month": 6,
  "quarter": 2,
  "model_file": "outputs/price_estimator_model.pkl",
  "mesh_master_file": "data/processed/mesh_master_tokyo23_multi.csv",
  "aggregated_stats_file": "outputs/aggregated_stats_2025.csv",
  "generation_timestamp": "2025-02-05T12:00:00+09:00",
  "total_meshes": 60000,
  "meshes_with_prediction": 58500
}
```

---

## 7. 実装仕様

### 7.1 クラス設計

**クラス名**: `MeshPriceEstimator`

**ファイルパス**: `src/real_state_geo_core/ml/mesh_price_estimator.py`

**メソッド**:

```python
class MeshPriceEstimator:
    """メッシュ坪単価推定クラス"""

    def __init__(
        self,
        model_path: str | Path,
        mesh_master_path: str | Path,
        stats_path: str | Path,
    ):
        """
        Args:
            model_path: 学習済みモデルのパス
            mesh_master_path: メッシュマスターのパス
            stats_path: 集約統計量マスターのパス（2025年）
        """
        pass

    def generate_mesh_price_map(
        self,
        target_year: int = 2025,
        age_range: tuple[int, int] = (1, 5),
        area_sqm: float = 70.0,
        structure: str = "RC",
        renovation: str = "なし",
        city_planning: str = "第一種住居地域",
        output_path: str | Path = "outputs/mesh_price_map_2025.csv",
        metadata_path: str | Path = "outputs/mesh_price_map_2025_metadata.json",
        max_stations: int = 3,
    ) -> pl.DataFrame:
        """
        メッシュ坪単価マップを生成します。

        Args:
            target_year: 対象年
            age_range: 築年数範囲（年）
            area_sqm: 専有面積（平米）
            structure: 建物構造
            renovation: 改装の有無
            city_planning: 用途地域
            output_path: 出力CSVパス
            metadata_path: メタデータJSONパス
            max_stations: 使用する最寄り駅数（デフォルト: 3）

        Returns:
            pl.DataFrame: メッシュ坪単価マップ
        """
        pass

    def _extract_top_stations(
        self, mesh_df: pl.DataFrame, max_stations: int = 3
    ) -> pl.DataFrame:
        """各メッシュの最寄りN駅を抽出します。"""
        pass

    def _create_features(
        self,
        mesh_stations: pl.DataFrame,
        target_year: int,
        age_range: tuple[int, int],
        area_sqm: float,
        structure: str,
        renovation: str,
        city_planning: str,
    ) -> pl.DataFrame:
        """特徴量を生成します。"""
        pass

    def _predict_and_aggregate(
        self, features_df: pl.DataFrame
    ) -> pl.DataFrame:
        """予測と平均化を実行します。"""
        pass

    def _save_metadata(
        self, metadata: dict, metadata_path: str | Path
    ) -> None:
        """メタデータをJSONで保存します。"""
        pass
```

### 7.2 実行スクリプト

**ファイル名**: `scripts/generate_mesh_price_map.py`

**使用例**:

```python
#!/usr/bin/env python3
"""メッシュ坪単価マップ生成スクリプト"""

from pathlib import Path
from real_state_geo_core.ml.mesh_price_estimator import MeshPriceEstimator

def main():
    # パス設定
    project_root = Path(__file__).parent.parent
    model_path = project_root / "outputs" / "price_estimator_model.pkl"
    mesh_master_path = project_root / "data" / "processed" / "mesh_master_tokyo23_multi.csv"
    stats_path = project_root / "outputs" / "aggregated_stats_2025.csv"

    # エスティメーター初期化
    estimator = MeshPriceEstimator(
        model_path=model_path,
        mesh_master_path=mesh_master_path,
        stats_path=stats_path,
    )

    # メッシュ坪単価マップ生成
    mesh_price_map = estimator.generate_mesh_price_map(
        target_year=2025,
        age_range=(1, 5),
        area_sqm=70.0,
        structure="RC",
        renovation="なし",
        city_planning="第一種住居地域",
        output_path=project_root / "outputs" / "mesh_price_map_2025.csv",
        metadata_path=project_root / "outputs" / "mesh_price_map_2025_metadata.json",
    )

    print(f"メッシュ坪単価マップを生成しました: {mesh_price_map.height}件")

if __name__ == "__main__":
    main()
```

---

## 8. パラメータバリエーションの生成

### 8.1 築年数バリエーション

複数の築年数範囲で坪単価マップを生成する:

```python
age_ranges = [
    (1, 5),    # 築浅
    (5, 10),   # 築浅〜築10年
    (10, 15),  # 築10〜15年
    (15, 20),  # 築15〜20年
    (20, 30),  # 築20〜30年
]

for age_range in age_ranges:
    output_path = f"outputs/mesh_price_map_2025_age_{age_range[0]}_{age_range[1]}.csv"
    estimator.generate_mesh_price_map(
        age_range=age_range,
        output_path=output_path,
    )
```

### 8.2 面積バリエーション

```python
areas = [60.0, 70.0, 80.0, 90.0, 100.0]

for area in areas:
    output_path = f"outputs/mesh_price_map_2025_area_{int(area)}.csv"
    estimator.generate_mesh_price_map(
        area_sqm=area,
        output_path=output_path,
    )
```

### 8.3 バッチ生成スクリプト

**ファイル名**: `scripts/generate_mesh_price_variations.py`

**使用例**:

```python
#!/usr/bin/env python3
"""複数の物件条件でメッシュ坪単価マップを一括生成"""

from pathlib import Path
from real_state_geo_core.ml.mesh_price_estimator import MeshPriceEstimator

def main():
    # エスティメーター初期化
    project_root = Path(__file__).parent.parent
    estimator = MeshPriceEstimator(
        model_path=project_root / "outputs" / "price_estimator_model.pkl",
        mesh_master_path=project_root / "data" / "processed" / "mesh_master_tokyo23_multi.csv",
        stats_path=project_root / "outputs" / "aggregated_stats_2025.csv",
    )

    # バリエーション定義
    variations = [
        {"age_range": (1, 5), "area_sqm": 70.0, "name": "age1-5_area70"},
        {"age_range": (5, 10), "area_sqm": 70.0, "name": "age5-10_area70"},
        {"age_range": (1, 5), "area_sqm": 80.0, "name": "age1-5_area80"},
        {"age_range": (5, 10), "area_sqm": 80.0, "name": "age5-10_area80"},
    ]

    for variation in variations:
        output_path = project_root / "outputs" / f"mesh_price_map_2025_{variation['name']}.csv"
        metadata_path = project_root / "outputs" / f"mesh_price_map_2025_{variation['name']}_metadata.json"

        estimator.generate_mesh_price_map(
            age_range=variation["age_range"],
            area_sqm=variation["area_sqm"],
            output_path=output_path,
            metadata_path=metadata_path,
        )

        print(f"✓ {variation['name']}")

if __name__ == "__main__":
    main()
```

---

## 9. パフォーマンス考慮事項

### 9.1 処理時間の見積もり

| 項目                          | 件数     | 処理時間（推定） |
| ----------------------------- | -------- | ---------------- |
| メッシュマスター読み込み      | 600,000行| 1秒              |
| 最寄り3駅抽出                 | 60,000メッシュ | 2秒              |
| 特徴量生成                    | 180,000件（60,000×3）| 3秒              |
| モデル予測                    | 180,000件| 10秒             |
| 平均計算と集約                | 60,000メッシュ | 2秒              |
| CSV出力                       | 60,000行 | 1秒              |
| **合計**                      | -        | **約20秒**       |

### 9.2 メモリ使用量

- メッシュマスター: 約100MB（縦持ち形式）
- 特徴量DataFrame: 約50MB
- 予測結果: 約10MB
- **合計**: 約160MB

### 9.3 最適化手法

#### 9.3.1 並行処理

メッシュを分割して並行処理:

```python
import polars as pl
from multiprocessing import Pool

def process_mesh_batch(mesh_ids: list[str]) -> pl.DataFrame:
    """メッシュのバッチ処理"""
    pass

# メッシュを1000件ずつに分割
mesh_batches = [mesh_ids[i:i+1000] for i in range(0, len(mesh_ids), 1000)]

# 並行処理
with Pool(processes=4) as pool:
    results = pool.map(process_mesh_batch, mesh_batches)

# 結合
final_result = pl.concat(results)
```

**効果**: 処理時間を約1/4に短縮（4コア使用時）

#### 9.3.2 Polars lazy evaluation

```python
# Lazy DataFrameで処理を最適化
mesh_df = pl.scan_csv("data/processed/mesh_master_tokyo23_multi.csv")

result = (
    mesh_df
    .group_by("mesh_id")
    .agg(pl.all().sort_by("distance_m").head(3))
    .collect()  # 最後に一括実行
)
```

---

## 10. 可視化との連携

### 10.1 PyDeckでのヒートマップ表示

**スクリプト例**: `scripts/visualize_mesh_price_heatmap.py`

```python
import pydeck as pdk
import polars as pl

# メッシュ坪単価マップ読み込み
mesh_price_df = pl.read_csv("outputs/mesh_price_map_2025.csv")

# PyDeck用に変換
layer = pdk.Layer(
    "HeatmapLayer",
    data=mesh_price_df.to_pandas(),
    get_position=["longitude", "latitude"],
    get_weight="predicted_price",
    radiusPixels=50,
)

view_state = pdk.ViewState(
    latitude=35.681,
    longitude=139.767,
    zoom=11,
    pitch=0,
)

r = pdk.Deck(
    layers=[layer],
    initial_view_state=view_state,
    map_style="mapbox://styles/mapbox/dark-v10",
)

r.to_html("outputs/mesh_price_heatmap_2025.html")
```

### 10.2 Streamlitでのインタラクティブ表示

**スクリプト例**: `scripts/streamlit_mesh_price_explorer.py`

```python
import streamlit as st
import polars as pl
import pydeck as pdk

st.title("東京23区 坪単価マップ")

# サイドバーで物件条件を選択
age_range = st.sidebar.slider("築年数", 1, 30, (1, 5))
area_sqm = st.sidebar.slider("面積（平米）", 50, 120, 70)

# 対応するCSVファイルを読み込み
file_name = f"outputs/mesh_price_map_2025_age_{age_range[0]}_{age_range[1]}_area_{int(area_sqm)}.csv"
mesh_price_df = pl.read_csv(file_name)

# ヒートマップ表示
st.pydeck_chart(pdk.Deck(
    layers=[pdk.Layer(
        "HeatmapLayer",
        data=mesh_price_df.to_pandas(),
        get_position=["longitude", "latitude"],
        get_weight="predicted_price",
    )],
    initial_view_state=pdk.ViewState(
        latitude=35.681,
        longitude=139.767,
        zoom=11,
    ),
))
```

---

## 11. テストケース

### 11.1 ユニットテスト

#### Test 1: 最寄り3駅の抽出

- 入力: メッシュID "35.681234_139.767890" に5駅が紐付いている
- 期待結果: 最寄り3駅が距離順に抽出される

#### Test 2: 駅が2駅の場合

- 入力: メッシュID "35.700000_139.800000" に2駅のみ
- 期待結果: 2駅の平均が計算される、`num_stations_used = 2`

#### Test 3: 駅が0駅の場合

- 入力: メッシュID "35.720000_139.850000" に駅なし
- 期待結果: 結果から除外される

#### Test 4: 特徴量の生成

- 入力: 物件条件（築年数1-5年、面積70平米等）
- 期待結果: 正しい特徴量辞書が生成される

#### Test 5: 集約統計量の取得

- 入力: 区名="千代田区", 駅名="東京", Year=2025
- 期待結果: 対応する統計量が正しく取得される

### 11.2 統合テスト

#### Test 6: エンドツーエンドのマップ生成

- 入力: 全メッシュマスター（60,000メッシュ）
- 期待結果:
  - CSVファイルが生成される
  - 約58,000件のメッシュが出力される（駅なしメッシュは除外）
  - 処理時間が30秒以内

---

## 12. 技術要件

- **言語**: Python 3.x
- **ライブラリ**:
  - `polars` (データ処理)
  - `pandas` (LightGBM入力用)
  - `lightgbm` (推論)
  - `pydeck` (可視化)
  - `streamlit` (インタラクティブ表示)
- **再現性**: 予測時の `random_state` は不要（推論のみ）
- **エラーハンドリング**: 駅なしメッシュ、統計量なしケースに対応
- **ディレクトリ**: `outputs/` フォルダが存在しない場合は自動生成

---

## 13. 影響範囲

### 13.1 新規作成ファイル

| ファイルパス                                          | 説明                               |
| ----------------------------------------------------- | ---------------------------------- |
| `scripts/prepare_aggregated_stats_2025.py`            | 2025年集約統計量算出スクリプト     |
| `src/real_state_geo_core/ml/mesh_price_estimator.py` | メッシュ坪単価推定クラス           |
| `scripts/generate_mesh_price_map.py`                  | メッシュ坪単価マップ生成スクリプト |
| `scripts/generate_mesh_price_variations.py`           | バッチ生成スクリプト               |
| `scripts/visualize_mesh_price_heatmap.py`             | PyDeck可視化スクリプト             |
| `scripts/streamlit_mesh_price_explorer.py`            | Streamlitアプリ                    |

### 13.2 依存ファイル

| ファイルパス                                      | 役割                       |
| ------------------------------------------------- | -------------------------- |
| `outputs/price_estimator_model.pkl`               | 学習済みモデル             |
| `data/processed/mesh_master_tokyo23_multi.csv`    | メッシュマスター           |
| `data/ml_dataset/tokyo_23_ml_dataset.csv`         | 元データ（2025年データ含む）|
| `outputs/aggregated_stats_2025.csv`               | 集約統計量マスター（2025年）|

---

## 14. 未実装・今後の課題

### 14.1 優先度: 高

1. **物件条件のプリセット**
   - 「ファミリー向け（築5年、80平米）」等のプリセット提供
   - 複数条件の一括生成

2. **エラーハンドリングの強化**
   - 集約統計量が存在しない駅・区への対応
   - 補完または除外のロジック実装

### 14.2 優先度: 中

3. **距離による重み付け平均**
   - 単純平均ではなく、距離の逆数で重み付け
   - より精緻な坪単価推定

4. **GeoParquet形式での出力**
   - 空間インデックス付きの効率的な保存形式
   - PyDeckとの高速連携

### 14.3 優先度: 低

5. **リアルタイム予測API**
   - FastAPIでRESTfulなエンドポイント提供
   - 緯度・経度から即座に坪単価を返す

6. **時系列アニメーション**
   - 2005年〜2025年の坪単価変動をアニメーション表示

---

## 15. 参考資料

### 15.1 関連設計書

- `docs/spec/active/AREA_PRICE_PREDCTION.md` — 坪単価推定モデル
- `docs/spec/active/MESH_MULTI_STATION.md` — メッシュマスター構築

### 15.2 技術ドキュメント

- [LightGBM Documentation](https://lightgbm.readthedocs.io/)
- [Polars Documentation](https://pola-rs.github.io/polars/)
- [Pydeck Documentation](https://deckgl.readthedocs.io/)

---

## 変更履歴

| バージョン | 日付       | 変更内容 | 作成者 |
| ---------- | ---------- | -------- | ------ |
| 1.0        | 2026-02-05 | 初版作成 | Claude |
