# 仕様書: メッシュマスター複数駅紐付け機能

## 1. 概要

### 1.1 目的

東京23区の100mメッシュマスターに対して、徒歩30分以内の駅を**すべて**紐付け、駅ごとの徒歩分数を提供する。これにより、各メッシュの交通アクセスの詳細な分析が可能になる。

### 1.2 背景

従来の実装では、各メッシュに最も近い駅1つのみが紐付けられていた。しかし、不動産分析においては、複数路線へのアクセス可能性が重要な要素となるため、徒歩圏内のすべての駅を把握する必要がある。

### 1.3 スコープ

| 項目               | 範囲                                     |
| ------------------ | ---------------------------------------- |
| **対象エリア**     | 東京23区                                 |
| **メッシュサイズ** | 100m四方                                 |
| **徒歩圏定義**     | 30分以内（距離: 2,400m以内）             |
| **徒歩速度**       | 80m/分（不動産業界標準）                 |
| **出力形式**       | 縦持ち（1メッシュ×N駅 = N行）           |
| **距離計算方法**   | Haversine距離（大圏距離、メートル単位）  |

---

## 2. 現状の実装 (As Is)

### 2.1 処理フロー

```
1. メッシュ格子点生成 (100m間隔)
   ↓
2. 23区内のメッシュにフィルタリング (spatial join)
   ↓
3. 行政情報付与 (市区町村名、地区名)
   ↓
4. 最寄駅検索 (cKDTree.query) ← 1駅のみ
   ↓
5. Haversine距離・徒歩分数計算
   ↓
6. CSVに保存 (横持ち: 1メッシュ1行)
```

### 2.2 現在のデータ構造

**クラス**: `MeshMasterBuilder` (`src/real_state_geo_core/data/mesh_builder.py:14-344`)

**出力スキーマ** (1メッシュ1行):

```python
{
    "mesh_id": str,           # メッシュID (例: "35.681234_139.767890")
    "latitude": float,        # メッシュ中心緯度
    "longitude": float,       # メッシュ中心経度
    "city_name": str,         # 市区町村名 (例: "千代田区")
    "district_name": str,     # 地区名 (空文字列)
    "station_name": str,      # 最寄駅名 (例: "東京")
    "distance_m": float,      # 距離 (メートル、小数第1位)
    "walk_minutes": float,    # 徒歩分数 (小数第1位)
}
```

### 2.3 最寄駅検索の実装 (現在)

**メソッド**: `_calculate_nearest_station()` (mesh_builder.py:241-304)

**処理内容**:

1. 駅座標を NumPy 配列に変換
2. cKDTree で空間インデックスを構築
3. `tree.query(mesh_coords)` で**最近傍の1駅**を検索
4. Haversine距離で正確な距離を再計算
5. 徒歩分数を計算 (`distance_m / 80.0`)

**制約**:

- `tree.query()` のデフォルトパラメータでは `k=1`（最近傍1点のみ）
- 複数駅の取得には `k` パラメータまたは範囲検索が必要

---

## 3. 追加機能の設計 (To Be)

### 3.1 要件

1. **複数駅の紐付け**: 各メッシュから徒歩30分以内（2,400m以内）の駅を**すべて**検索
2. **出力形式変更**: 縦持ち形式（1メッシュ×N駅 = N行のレコード）
3. **徒歩分数の提供**: 各駅までの徒歩分数を個別に計算
4. **駅の順序**: 距離の近い順にソート

### 3.2 処理フロー (変更後)

```
1. メッシュ格子点生成 (100m間隔)
   ↓
2. 23区内のメッシュにフィルタリング (spatial join)
   ↓
3. 行政情報付与 (市区町村名、地区名)
   ↓
4. 徒歩圏内駅検索 (cKDTree.query_ball_point) ← ✨ NEW
   ↓  - 距離2,400m以内の駅をすべて取得
   ↓  - 各駅までのHaversine距離・徒歩分数を計算
   ↓  - 距離順にソート
   ↓
5. 縦持ちDataFrameに変換 (1メッシュ×N駅) ← ✨ NEW
   ↓
6. CSVに保存
```

### 3.3 新しいメソッド設計

#### 3.3.1 `_calculate_nearby_stations()` (新規作成)

**シグネチャ**:

```python
def _calculate_nearby_stations(
    self,
    mesh_gdf: gpd.GeoDataFrame,
    station_df: pl.DataFrame,
    max_walk_minutes: float = 30.0
) -> pl.DataFrame:
```

**パラメータ**:

- `mesh_gdf`: メッシュ格子点のGeoDataFrame
- `station_df`: 駅データのPolars DataFrame
- `max_walk_minutes`: 最大徒歩分数（デフォルト: 30.0）

**戻り値**:

- `pl.DataFrame`: 縦持ち形式のメッシュマスター

**処理内容**:

1. 徒歩分数を距離に変換: `max_distance_m = max_walk_minutes * 80.0`
2. 駅座標を NumPy 配列に変換
3. cKDTree を構築
4. **範囲検索**: `tree.query_ball_point(mesh_coords, r=max_distance_m)` を使用
   - 戻り値: 各メッシュに対する駅インデックスのリスト
5. 各メッシュについて:
   - 範囲内の駅それぞれについて:
     - Haversine距離を計算
     - 徒歩分数を計算
     - レコードをリストに追加
   - 駅がない場合はスキップ（またはNullレコード追加）
6. 距離順にソート
7. Polars DataFrameに変換

**注意事項**:

- `query_ball_point()` はユークリッド距離ベースの範囲検索のため、実際のHaversine距離と若干の誤差が生じる
- 高精度が必要な場合は、範囲を広めに設定（例: 2,500m）し、Haversine距離で再フィルタリング

#### 3.3.2 既存メソッドの変更

**`build_mesh_master()`** の変更:

- Step 6 の `_calculate_nearest_station()` を `_calculate_nearby_stations()` に置き換え
- パラメータ `max_walk_minutes` を追加（デフォルト: 30.0）

**シグネチャ変更**:

```python
def build_mesh_master(
    self,
    output_path: Path,
    max_walk_minutes: float = 30.0  # ✨ NEW
) -> pl.DataFrame:
```

### 3.4 出力データ構造 (変更後)

**縦持ち形式** (1メッシュ×N駅):

```python
{
    "mesh_id": str,           # メッシュID
    "latitude": float,        # メッシュ中心緯度
    "longitude": float,       # メッシュ中心経度
    "city_name": str,         # 市区町村名
    "district_name": str,     # 地区名
    "station_name": str,      # 駅名 (N駅分のレコード)
    "distance_m": float,      # 距離 (メートル、小数第1位)
    "walk_minutes": float,    # 徒歩分数 (小数第1位)
}
```

**出力例**:

```csv
mesh_id,latitude,longitude,city_name,district_name,station_name,distance_m,walk_minutes
35.681234_139.767890,35.681234,139.767890,千代田区,,東京,200.5,2.5
35.681234_139.767890,35.681234,139.767890,千代田区,,有楽町,450.2,5.6
35.681234_139.767890,35.681234,139.767890,千代田区,,京橋,680.0,8.5
35.682000_139.768000,35.682000,139.768000,千代田区,,東京,150.3,1.9
35.682000_139.768000,35.682000,139.768000,千代田区,,日本橋,800.0,10.0
```

**変更点**:

- 同じ `mesh_id` が複数行に出現
- 駅ごとに異なる `station_name`, `distance_m`, `walk_minutes` を持つ
- 距離の近い順にソートされている

---

## 4. 技術仕様

### 4.1 使用ライブラリ

| ライブラリ          | 用途                                 |
| ------------------- | ------------------------------------ |
| `scipy.spatial`     | cKDTree（空間インデックス、範囲検索）|
| `numpy`             | 数値計算、配列処理                   |
| `polars`            | DataFrame処理、CSV入出力             |
| `geopandas`         | 空間結合、ジオメトリ処理             |

### 4.2 主要アルゴリズム

#### 4.2.1 範囲検索 (cKDTree.query_ball_point)

**公式ドキュメント**: [scipy.spatial.cKDTree.query_ball_point](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.query_ball_point.html)

**シグネチャ**:

```python
tree.query_ball_point(x, r, p=2.0, eps=0, workers=1, return_sorted=None, return_length=False)
```

**パラメータ**:

- `x`: クエリ点の座標配列（形状: `(n, 2)` - 緯度・経度）
- `r`: 検索半径（メートル単位ではなく度数単位に変換が必要）
- `p`: ミンコフスキー距離のべき数（デフォルト: 2.0 = ユークリッド距離）

**注意点**:

- cKDTreeはユークリッド距離で動作するため、緯度・経度の度数ベースの計算となる
- 精度を向上させるには、半径を度数に変換:
  ```python
  # 2,400mを度数に変換（東京付近の概算）
  # 緯度1度 ≈ 111km、経度1度 ≈ 91km
  r_lat = 2400.0 / 1000.0 / 111.0  # ≈ 0.0216度
  r_lon = 2400.0 / 1000.0 / 91.0   # ≈ 0.0264度
  r = max(r_lat, r_lon)  # 安全マージンとして大きい方を使用
  ```

#### 4.2.2 Haversine距離計算 (既存実装を再利用)

**メソッド**: `_haversine_distance()` (mesh_builder.py:209-239)

**計算式**:

```
a = sin²(Δlat/2) + cos(lat1) * cos(lat2) * sin²(Δlon/2)
c = 2 * arctan2(√a, √(1-a))
distance = R * c  (R = 6371km = 地球の半径)
```

**精度**:

- 球面三角法による大圏距離
- 誤差: 数メートル以下（東京23区程度の範囲では十分）

### 4.3 パフォーマンス考慮事項

#### 4.3.1 計算量

| 項目                    | 現在 (最近傍1駅)  | 変更後 (範囲内全駅) |
| ----------------------- | ----------------- | ------------------- |
| 空間インデックス構築    | O(N log N)        | O(N log N)          |
| クエリ処理              | O(M log N)        | O(M log N)          |
| Haversine距離計算       | O(M)              | O(M × K)            |
| 出力レコード数          | M                 | M × K               |

**記号**:

- N: 駅数（東京都内 ≈ 500駅）
- M: メッシュ数（東京23区 ≈ 60,000メッシュ）
- K: 徒歩圏内の平均駅数（推定: 5〜10駅）

**推定処理時間**:

- 現在: 約10秒（M = 60,000、N = 500）
- 変更後: 約30〜60秒（K = 5〜10と仮定）

#### 4.3.2 メモリ使用量

- 現在: 約10MB（60,000行 × 8カラム）
- 変更後: 約50〜100MB（300,000〜600,000行 × 8カラム）

**対策**:

- Polars の lazy evaluation を活用
- CSV出力時のストリーミング書き込み

---

## 5. 実装計画

### 5.1 実装手順

#### Step 1: 新メソッド `_calculate_nearby_stations()` の作成

- cKDTree.query_ball_point による範囲検索の実装
- Haversine距離の計算
- 縦持ちDataFrameの生成
- 距離順ソート

#### Step 2: `build_mesh_master()` の変更

- パラメータ `max_walk_minutes` の追加
- `_calculate_nearest_station()` から `_calculate_nearby_stations()` への置き換え

#### Step 3: ユニットテスト作成

- 範囲検索の正確性検証
- 縦持ち形式の出力検証
- エッジケース（駅がない場合、1駅のみの場合）

#### Step 4: 実行スクリプト更新

- `scripts/aggregate_mesh_price.py` 等での利用例追加
- README.md の更新

### 5.2 実装コード例

```python
def _calculate_nearby_stations(
    self,
    mesh_gdf: gpd.GeoDataFrame,
    station_df: pl.DataFrame,
    max_walk_minutes: float = 30.0
) -> pl.DataFrame:
    """
    各メッシュ点から徒歩圏内の駅をすべて検索し、距離と徒歩分数を計算します。

    Args:
        mesh_gdf (gpd.GeoDataFrame): メッシュ格子点のGeoDataFrame。
        station_df (pl.DataFrame): 駅データのPolars DataFrame。
        max_walk_minutes (float): 最大徒歩分数（デフォルト: 30.0）。

    Returns:
        pl.DataFrame: 縦持ち形式のメッシュマスター。
    """
    # 最大距離を計算（メートル）
    max_distance_m = max_walk_minutes * 80.0

    # 駅の座標をNumPy配列に変換
    station_coords = station_df.select(["lat", "lon"]).to_numpy()
    station_names = station_df["station_name"].to_list()

    # cKDTreeを構築
    tree = cKDTree(station_coords)

    # メッシュ点の座標をNumPy配列に変換
    mesh_coords = mesh_gdf[["latitude", "longitude"]].to_numpy()

    # 範囲検索の半径を度数に変換（東京付近の概算）
    r_degrees = max_distance_m / 1000.0 / 111.0 * 1.2  # 安全マージン20%

    # 範囲検索: 各メッシュの徒歩圏内の駅インデックスを取得
    indices_list = tree.query_ball_point(mesh_coords, r=r_degrees)

    # 結果を格納するリスト
    results: list[dict[str, Any]] = []

    for i, (lat, lon) in enumerate(mesh_coords):
        nearby_station_indices = indices_list[i]

        # メッシュIDを生成
        mesh_id = f"{lat:.6f}_{lon:.6f}"

        # 市区町村名と地区名を取得
        city_name = mesh_gdf.iloc[i]["city_name"]
        district_name = mesh_gdf.iloc[i]["district_name"]

        # 駅ごとの距離を計算
        station_distances = []
        for station_idx in nearby_station_indices:
            station_lat = station_coords[station_idx][0]
            station_lon = station_coords[station_idx][1]

            # Haversine距離で正確な距離を計算
            distance_m = self._haversine_distance(lat, lon, station_lat, station_lon)

            # 最大距離で再フィルタリング
            if distance_m <= max_distance_m:
                walk_minutes = round(distance_m / 80.0, 1)
                station_distances.append({
                    "station_idx": station_idx,
                    "distance_m": round(distance_m, 1),
                    "walk_minutes": walk_minutes,
                })

        # 距離順にソート
        station_distances.sort(key=lambda x: x["distance_m"])

        # 各駅についてレコードを追加
        for sd in station_distances:
            station_name = station_names[sd["station_idx"]]
            results.append({
                "mesh_id": mesh_id,
                "latitude": lat,
                "longitude": lon,
                "city_name": city_name,
                "district_name": district_name,
                "station_name": station_name,
                "distance_m": sd["distance_m"],
                "walk_minutes": sd["walk_minutes"],
            })

    # Polars DataFrameに変換
    result_df = pl.DataFrame(results)

    logging.info(f"徒歩圏内駅情報を計算しました: {result_df.height}件（メッシュ数: {len(mesh_coords)}）")
    return result_df
```

### 5.3 既存メソッドの廃止について

**`_calculate_nearest_station()`** (mesh_builder.py:241-304)

**選択肢**:

1. **削除**: 新メソッドのみに統一
2. **保持**: 後方互換性のため残す（非推奨マークを付与）

**推奨**: 保持（後方互換性のため）

- `build_mesh_master()` に `mode="single"` または `mode="multi"` パラメータを追加
- デフォルトは `mode="multi"` とする

---

## 6. テストケース

### 6.1 ユニットテスト

#### Test 1: 範囲検索の正確性

- 入力: 駅A(35.681, 139.767)、メッシュB(35.681, 139.770)（距離 ≈ 270m）
- 期待結果: 徒歩30分以内として検出される

#### Test 2: 距離フィルタリング

- 入力: 駅A(35.681, 139.767)、メッシュC(35.700, 139.767)（距離 ≈ 2,100m）
- 期待結果: 徒歩30分以内として検出される

#### Test 3: 範囲外のフィルタリング

- 入力: 駅A(35.681, 139.767)、メッシュD(35.720, 139.767)（距離 ≈ 4,300m）
- 期待結果: 検出されない

#### Test 4: 縦持ち形式の検証

- 入力: メッシュEに3駅が徒歩圏内
- 期待結果: 3行のレコードが生成される

#### Test 5: 駅がない場合

- 入力: メッシュFに徒歩圏内の駅がない
- 期待結果: レコードが生成されない（または0行）

### 6.2 統合テスト

#### Test 6: 東京23区全体のメッシュマスター生成

- 入力: 全23区、約60,000メッシュ
- 期待結果:
  - CSVファイルが正常に生成される
  - 処理時間が60秒以内
  - ファイルサイズが100MB以下

---

## 7. 未実装・今後の課題

### 7.1 優先度: 高

1. **並行処理の導入**
   - メッシュを分割して並行計算（multiprocessing）
   - 処理時間の短縮（目標: 30秒以内）

2. **駅の重複排除**
   - 同一駅が複数行に出現する場合の処理
   - 駅名の正規化（例: "東京駅" → "東京"）

### 7.2 優先度: 中

3. **路線情報の追加**
   - 駅データに路線名を追加（例: "JR山手線", "東京メトロ丸ノ内線"）
   - 複数路線がある駅の処理

4. **徒歩速度のカスタマイズ**
   - パラメータで徒歩速度を変更可能にする（デフォルト: 80m/分）

### 7.3 優先度: 低

5. **駅の利用者数による重み付け**
   - 主要駅を優先的に表示

6. **GeoParquetフォーマットでの出力**
   - 空間インデックスを含む効率的な保存形式

---

## 8. 影響範囲

### 8.1 変更が必要なファイル

| ファイル                                      | 変更内容                                   |
| --------------------------------------------- | ------------------------------------------ |
| `src/real_state_geo_core/data/mesh_builder.py` | `_calculate_nearby_stations()` 追加        |
|                                               | `build_mesh_master()` パラメータ追加       |
| `scripts/visualize_mesh_colored.py`           | 新しい縦持ち形式への対応（必要に応じて）   |
| `scripts/aggregate_mesh_price.py`             | 新しい縦持ち形式への対応（必要に応じて）   |
| `docs/SYSTEM_DESIGN.md`                       | メッシュマスター仕様の更新                 |

### 8.2 下流への影響

**データ利用側の変更**:

- メッシュマスターを読み込むスクリプトは、縦持ち形式への対応が必要
- 集計処理では `group_by("mesh_id")` でグルーピングが必要

**例** (変更前):

```python
mesh_df = pl.read_csv("data/processed/mesh_master_tokyo23.csv")
# mesh_df: 60,000行 × 8カラム
```

**例** (変更後):

```python
mesh_df = pl.read_csv("data/processed/mesh_master_tokyo23.csv")
# mesh_df: 300,000〜600,000行 × 8カラム（縦持ち）

# 最寄駅のみ取得する場合
nearest_stations = mesh_df.group_by("mesh_id").agg(
    pl.all().sort_by("distance_m").first()
)
```

---

## 9. 参考資料

### 9.1 技術ドキュメント

- [scipy.spatial.cKDTree.query_ball_point](https://docs.scipy.org/doc/scipy/reference/generated/scipy.spatial.cKDTree.query_ball_point.html)
- [Haversine距離計算](https://en.wikipedia.org/wiki/Haversine_formula)
- [不動産業界の徒歩分数基準](https://www.fudousan.or.jp/kijun/hyouji/)（公正競争規約: 80m/分）

### 9.2 既存仕様書

- `docs/SYSTEM_DESIGN.md` — システム全体の設計書
- `CLAUDE.md` — プロジェクト概要

---

## 付録A: データサンプル

### A.1 出力CSV例（縦持ち形式）

**ファイル**: `data/processed/mesh_master_tokyo23_multi.csv`

```csv
mesh_id,latitude,longitude,city_name,district_name,station_name,distance_m,walk_minutes
35.681234_139.767890,35.681234,139.767890,千代田区,,東京,200.5,2.5
35.681234_139.767890,35.681234,139.767890,千代田区,,有楽町,450.2,5.6
35.681234_139.767890,35.681234,139.767890,千代田区,,京橋,680.0,8.5
35.681234_139.767890,35.681234,139.767890,千代田区,,日本橋,1200.0,15.0
35.682000_139.768000,35.682000,139.768000,千代田区,,東京,150.3,1.9
35.682000_139.768000,35.682000,139.768000,千代田区,,日本橋,800.0,10.0
35.682000_139.768000,35.682000,139.768000,千代田区,,有楽町,950.0,11.9
```

### A.2 統計情報

| 項目                         | 値（推定）       |
| ---------------------------- | ---------------- |
| メッシュ数                   | 約60,000         |
| 駅数（東京都内）             | 約500            |
| 1メッシュあたりの平均駅数    | 5〜10駅          |
| 総レコード数                 | 300,000〜600,000 |
| CSVファイルサイズ            | 50〜100MB        |

---

## 変更履歴

| バージョン | 日付       | 変更内容                 | 作成者 |
| ---------- | ---------- | ------------------------ | ------ |
| 1.0        | 2026-01-31 | 初版作成                 | Claude |
