# システム設計書：Urban Dynamics PoC

## 1. 概要

### 1.1 目的

国土交通省の不動産取引データ（不動産情報ライブラリAPI）を用いて、不動産取引価格を3D可視化し、最終的にYouTube Shorts動画を生成するPoCを構築する。

### 1.2 スコープ（PoC範囲）

| 項目         | PoC範囲                               | 将来対応         |
| ------------ | ------------------------------------- | ---------------- |
| データソース | 不動産情報ライブラリAPI（実装済み）   | 全国対応拡張     |
| 対象エリア   | 東京23区任意選択可能（実装済み）      | 全国展開         |
| 可視化       | pydeck（実装済み）/ PyVista（未実装） | 動画出力対応     |
| AI強化       | Runway API（未実装）                  | 自動パイプライン |
| 自動化       | セミ自動（HTML可視化まで実装済み）    | フル自動         |

### 1.3 出力仕様（YouTube Shorts）

| 項目           | 値                      |
| -------------- | ----------------------- |
| 解像度         | 1080 x 1920 (9:16 縦型) |
| フレームレート | 30fps                   |
| 動画長         | 60秒                    |
| 形式           | MP4 (H.264)             |

---

## 2. システム構成図

```
┌─────────────────────────────────────────────────────────────────────┐
│                    PoC Pipeline (実装状況)                          │
└─────────────────────────────────────────────────────────────────────┘

  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   1. Data    │     │  2. Analyze  │     │ 3. Visualize │
  │   Extract ✅ │────▶│  & Clean ✅  │────▶│ (3D Map) ✅  │
  └──────────────┘     └──────────────┘     └──────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
  不動産API (✅)        polars処理 (✅)      pydeck ColumnLayer (✅)
  複数年並行取得 (✅)   数値変換 (✅)         色・高さマッピング (✅)
  駅マスタCSV (✅)      単価計算 (✅)         HTML出力 (✅)
  区境界GeoJSON (✅)    欠損値除去 (✅)       PyVista (⬜)
  ジオコード (✅)       座標生成 (✅)         フレーム出力 (⬜)
                      地域別集計 (✅)
                      時系列集計 (✅)
                      前年比計算 (✅)

                                               │
                                               ▼
  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
  │   6. Export  │     │  5. Compose  │     │  4. Enhance  │
  │  (Final) ⬜  │◀────│  (FFmpeg) ⬜ │◀────│ (Runway) ⬜  │
  └──────────────┘     └──────────────┘     └──────────────┘
         │                    │                    │
         ▼                    ▼                    ▼
    YouTube Shorts       動画結合              Video-to-Video
    1080x1920           テキスト合成            質感向上
    30fps / 60s         BGM合成               Gen-3 API

凡例: ✅ 実装済み  ⬜ 未実装
```

### データフロー詳細（実装済み部分）

#### フロー A: 単年可視化（従来）

```
不動産情報ライブラリAPI
    │
    ▼ fetch_real_estate()
JSON/gzip レスポンス
    │
    ▼ clean_real_estate_data()
polars.DataFrame
    │  ├─ TradePrice (Float64)
    │  ├─ Area (Float64)
    │  ├─ DistrictName (Utf8)
    │  └─ ... (27カラム)
    │
    ▼ フィルタ・加工（Notebook内）
    │  ├─ Type="中古マンション等"で絞り込み
    │  ├─ price_per_sqm = TradePrice / Area
    │  ├─ geocode_random() で座標生成
    │  ├─ elevation = TradePrice / 1e6
    │  └─ color = price_to_color(price_per_sqm)
    │
    ▼ convert_for_pydeck()
list[dict] (JSON serializable)
    │
    ▼ pydeck.Deck()
    │  ├─ ColumnLayer (取引データ)
    │  └─ GeoJsonLayer (区境界)
    │
    ▼ deck.to_html()
output/pydeck_江東区_2024.html
```

#### フロー B: 時系列統計分析 ✅ **NEW**

```
不動産情報ライブラリAPI（複数年）
    │
    ▼ fetch_real_estate_multi_year(2020, 2024, "13103")
    │  ├─ ThreadPoolExecutor で並行取得
    │  ├─ 各年に "Year" カラムを追加
    │  └─ vertical_relaxed で結合
    │
polars.DataFrame (複数年統合)
    │  ├─ Year: "2020", "2021", ..., "2024"
    │  ├─ TradePrice (Float64)
    │  ├─ Area (Float64)
    │  ├─ DistrictName (Utf8)
    │  └─ ... (27カラム)
    │
    ▼ RealEstateAggregator(df)
    │
    ▼ aggregate_by_region_timeseries()
    │  ├─ calculate_sqm_price() / calculate_tsubo_price()
    │  ├─ 外れ値除外（グループごとに分位点計算）
    │  ├─ Year × DistrictName で集計
    │  │   └─ mean, median, min, max, std, count
    │  └─ _calculate_yoy_change()
    │      ├─ 前年データとself-join
    │      └─ (current - prev) / prev * 100
    │
polars.DataFrame (時系列集計結果)
    │  ├─ Year (Utf8)
    │  ├─ DistrictName (Utf8)
    │  ├─ count (Int64)
    │  ├─ price_per_sqm_mean (Float64)
    │  ├─ price_per_sqm_mean_yoy_change (Float64) ✨
    │  ├─ price_per_sqm_median (Float64)
    │  ├─ price_per_sqm_median_yoy_change (Float64) ✨
    │  ├─ price_per_tsubo_mean (Float64)
    │  ├─ price_per_tsubo_mean_yoy_change (Float64) ✨
    │  └─ ...
    │
    ▼ write_csv()
output/timeseries/timeseries_stats_13103_2020_2024.csv
```

---

## 3. 処理フロー詳細

各 Phase の「処理」は必ず現状の実装状況（`現状の実装`）と、設計上必要な残タスク（`未実装 / 今後`）を分けて記載します。

### Phase 1: データ取得 (Extract) ✅

**実装クラス:** `RealEstateDataFetcher` (`src/real_state_geo_core/data/fetcher.py:13-295`)

**実装済み処理:**

1. **`fetch_real_estate(year, city_code)`** (fetcher.py:31-67)
   - 不動産情報ライブラリAPIから取引データを取得
   - JSONレスポンスとgzip圧縮レスポンスの両方に対応
   - パラメータ:
     - `year`: 取得対象年（例: "2024"）
     - `city_code`: 市区町村コード5桁（例: "13103" = 港区）
     - `priceClassification`: "01"（不動産取引価格情報）固定
   - エラーハンドリング: HTTPステータスコード確認、JSON/gzipデコード失敗時のログ出力
   - 戻り値: `dict[str, Any]` または `None`

2. **`fetch_station_master(csv_path)`** (fetcher.py:99-145)
   - 駅データ.jp CSVを読み込み、駅名正規化と座標マスタを作成
   - 東京都（都道府県コード=13）の駅のみフィルタリング
   - 全角空白除去・文字列正規化を実施
   - 戻り値: `dict[str, tuple]` 形式（駅名 → (緯度, 経度)）
   - 緯度・経度が不正な場合はスキップ

3. **`fetch_boundary_geojson(ward_code, save_path)`** (fetcher.py:147-181)
   - JapanCityGeoJson（GitHub）から区境界GeoJSONを取得・保存
   - `save_path`指定時はファイル保存、未指定時は辞書として返却
   - エラーハンドリング: HTTP 404、JSON デコード失敗時のログ出力

4. **`geocode_random(area_sqm, center_lat, center_lon, max_radius_km)`** (fetcher.py:183-208)
   - 区の中心座標周辺にランダムな座標を生成（可視化用の散布）
   - 面積に応じて半径を調整（大きい物件ほど中心寄り）
   - 緯度・経度のオフセット計算（緯度1度≒111km、経度1度≒91km）
   - 戻り値: `dict[str, float]` 形式（latitude, longitude）

5. **`fetch_real_estate_multi_year(start_year, end_year, city_code, max_workers=5)`** (fetcher.py:210-295) ✅ **NEW**
   - **複数年の不動産データを並行取得**
   - ThreadPoolExecutorによる高速並行処理（デフォルト5スレッド）
   - パラメータ:
     - `start_year`: 開始年（int型、例: 2020）
     - `end_year`: 終了年（int型、例: 2024）
     - `city_code`: 市区町村コード5桁
     - `max_workers`: 並行スレッド数（デフォルト: 5）
   - 各年のデータに自動的に`Year`カラムを追加（文字列型）
   - 全年データを縦方向に統合（`vertical_relaxed`モード）
   - エラーハンドリング: 各年の取得失敗を個別にログ出力、成功分のみ統合
   - 戻り値: `pl.DataFrame` または `None`（全年失敗時）

**未実装 / 今後:**

- 駅データCSVの自動ダウンロード・UTF-8正規化
- データキャッシュ機構（Parquet保存等）

**入力例:**

- API: `https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001?year=2024&city=13103`
- 駅CSV: `data/station/station20251211free.csv`
- 境界JSON: `https://raw.githubusercontent.com/niiyz/JapanCityGeoJson/master/geojson/pref/13/13103.json`

**出力例:**

```python
# fetch_real_estate の戻り値
{
    "status": 200,
    "data": [
        {
            "TradePrice": "50000000",
            "Area": "60.5",
            "DistrictName": "赤坂",
            "Type": "中古マンション等",
            ...
        }
    ]
}

# fetch_station_master の戻り値
{
    "赤坂": (35.6733, 139.7369),
    "六本木": (35.6627, 139.7293),
    ...
}
```

---

### Phase 2: データ加工・集計 (Analyze & Clean) ✅

**実装クラス:**

- `RealEstateDataFetcher` (`src/real_state_geo_core/data/fetcher.py`)
- `RealEstateAggregator` (`src/real_state_geo_core/processing/aggregator.py`) ✅ **NEW**

**実装済み処理:**

#### 2.1 データクリーニング（RealEstateDataFetcher）

1. **`clean_real_estate_data(api_response)`** (fetcher.py:69-97)
   - APIレスポンスの `data` 部分を `polars.DataFrame` に変換
   - 数値カラムのクリーニング:
     - カンマ区切り文字列を除去（例: "50,000,000" → "50000000"）
     - `TradePrice`, `Area`, `UnitPrice` を `Float64` 型に変換
     - strict=False により不正値はNullとして処理
   - 必須カラム（`TradePrice`, `Area`）の欠損値を除去
   - エラーハンドリング: データがない場合は警告ログ出力
   - 戻り値: `pl.DataFrame` または `None`

#### 2.2 地域別統計・時系列分析（RealEstateAggregator）✅ **NEW**

**実装クラス:** `RealEstateAggregator` (`src/real_state_geo_core/processing/aggregator.py:8-382`)

**初期化:**

- **`__init__(df, tsubo_conversion=3.30579)`** (aggregator.py:17-35)
  - 必須カラム（`TradePrice`, `Area`）のバリデーション
  - 坪変換係数の設定（デフォルト: 1坪 = 3.30579㎡）
  - 戻り値: なし（初期化のみ）

**単価計算メソッド:**

2. **`calculate_sqm_price(df)`** (aggregator.py:37-47)
   - ㎡単価を計算（円/㎡）
   - 計算式: `TradePrice / Area`
   - 戻り値: `price_per_sqm`カラムが追加されたDataFrame

3. **`calculate_tsubo_price(df)`** (aggregator.py:49-61)
   - 坪単価を計算（円/坪）
   - 計算式: `(TradePrice / Area) * tsubo_conversion`
   - 戻り値: `price_per_tsubo`カラムが追加されたDataFrame

**地域別集計メソッド:**

4. **`aggregate_by_region(group_by, metrics, price_unit, exclude_outliers, percentile_range)`** (aggregator.py:63-162)
   - 地域別に不動産データを集計
   - パラメータ:
     - `group_by`: 集計キー（単一または複数カラム、デフォルト: "DistrictName"）
     - `metrics`: 統計指標リスト（["mean", "median", "min", "max", "std", "count"]）
     - `price_unit`: 単価種別（"yen_per_sqm", "yen_per_tsubo", "both"）
     - `exclude_outliers`: 外れ値除外フラグ（デフォルト: False）
     - `percentile_range`: 外れ値除外の範囲（デフォルト: (0.05, 0.95) = 上下5%除外）
   - 処理内容:
     - グループごとに平均、中央値、最小、最大、標準偏差、件数を計算
     - 外れ値除外時は分位点でフィルタリング
   - 戻り値: 集計結果DataFrame（カラム例: `price_per_sqm_mean`, `price_per_tsubo_median`）

**時系列集計メソッド:**✅ **NEW**

5. **`aggregate_by_region_timeseries(year_column, group_by, metrics, price_unit, exclude_outliers, percentile_range, calculate_yoy)`** (aggregator.py:164-286)
   - **時系列×地域の2軸で統計を集計**
   - パラメータ:
     - `year_column`: 年カラム名（デフォルト: "Year"）
     - `group_by`: 集計キー（デフォルト: "DistrictName"）
     - `metrics`: 統計指標リスト
     - `price_unit`: 単価種別
     - `exclude_outliers`: 外れ値除外フラグ
     - `percentile_range`: 外れ値除外範囲
     - `calculate_yoy`: 前年比変化率の計算フラグ（デフォルト: True）
   - 処理内容:
     - 年×地域の組み合わせごとに統計を計算
     - 外れ値除外はグループごとに適用
     - 前年比変化率（YoY）を自動計算
   - 戻り値: 時系列集計DataFrame（YoY付き、例: `price_per_sqm_mean_yoy_change`）

6. **`_calculate_yoy_change(df, year_column, group_columns, price_columns, metrics)`** (aggregator.py:288-346) (内部メソッド)
   - **前年比変化率（Year-over-Year）を計算**
   - 処理内容:
     - 年カラムを整数型に変換
     - 前年データと結合（self-join）
     - 変化率の計算式: `(current - prev) / prev * 100`
     - 前年データがない場合はNull
   - 戻り値: YoYカラムが追加されたDataFrame

**統計サマリメソッド:**

7. **`get_summary_statistics(df, price_column)`** (aggregator.py:348-382)
   - 全体統計のサマリーを辞書形式で取得
   - パラメータ:
     - `df`: 統計計算対象のDataFrame
     - `price_column`: 統計対象カラム（デフォルト: "price_per_sqm"）
   - 戻り値: `dict[str, float]`（キー: mean, median, min, max, std, count）

#### 2.3 Jupyter Notebook内の追加処理（可視化前処理）

**処理内容** (`notebooks/01_pydeck_experiment.ipynb`)

- データ型フィルタリング: `Type`カラムで「中古マンション等」に絞り込み
- 単価計算: `price_per_sqm = TradePrice / Area`（円/㎡）
- 座標生成: `geocode_random` を使用して各レコードに緯度・経度を付与
- 可視化用カラム追加:
  - `elevation`: 取引価格を百万円単位に変換（3D高さ）
  - `color`: 単価を正規化してRGB配列に変換（シアン→マゼンタのグラデーション）
- 統計情報の計算: 平均価格、中央値、最大値、単価統計

**実装例（Notebookより抜粋）:**

```python
# 型フィルタ
df = df.filter(pl.col("Type").str.contains("中古マンション等"))

# 数値変換
for col_name in ["TradePrice", "Area", "UnitPrice"]:
    if col_name in df.columns:
        df = df.with_columns(
            pl.col(col_name)
            .cast(pl.Utf8)
            .str.replace(",", "")
            .cast(pl.Float64, strict=False)
        )

# 単価計算（Aggregatorクラス利用推奨）
df = df.with_columns(
    (pl.col("TradePrice") / pl.col("Area")).alias("price_per_sqm")
)

# 座標生成
df = df.with_columns(
    pl.struct(["Area"])
    .map_elements(
        lambda x: geocode_random(x["Area"] or 50.0, center_lat, center_lon),
        return_dtype=pl.Struct([
            pl.Field("latitude", pl.Float64),
            pl.Field("longitude", pl.Float64)
        ])
    )
    .alias("geo")
).unnest("geo")
```

**時系列分析の実装例（RealEstateAggregator使用）:** ✅ **NEW**

```python
from real_state_geo_core.data.fetcher import RealEstateDataFetcher
from real_state_geo_core.processing.aggregator import RealEstateAggregator

# 複数年データの取得
fetcher = RealEstateDataFetcher(api_key=API_KEY)
multi_year_df = fetcher.fetch_real_estate_multi_year(
    start_year=2020,
    end_year=2024,
    city_code="13103"  # 港区
)

# 時系列×地域別集計（前年比付き）
aggregator = RealEstateAggregator(multi_year_df)
timeseries_stats = aggregator.aggregate_by_region_timeseries(
    year_column="Year",
    group_by="DistrictName",
    metrics=["mean", "median", "count"],
    price_unit="both",
    exclude_outliers=True,
    percentile_range=(0.05, 0.95),
    calculate_yoy=True  # 前年比変化率を計算
)

# 出力例:
# Year | DistrictName | price_per_sqm_mean | price_per_sqm_mean_yoy_change | count
# -----|--------------|-------------------|-------------------------------|------
# 2020 | 赤坂         | 1500000          | null                          | 120
# 2021 | 赤坂         | 1545000          | 3.0                           | 135
# 2022 | 赤坂         | 1620000          | 4.85                          | 142
```

**未実装 / 今後:**

- 厳密なジオコーディング:
  - 地区名+最寄駅の組み合わせマッチング
  - Google Geocoding API等の外部API連携
- 時系列処理の拡張:
  - `Period`カラムのパース（"2024年第3四半期" → "2024Q3"）
  - 四半期ごとの集約・トレンド分析
  - 移動平均・季節調整
- データ品質向上:
  - 建築年の補完・正規化
  - 地価指数との相関分析
- 永続化:
  - Parquet形式での保存
  - データバージョニング

**出力スキーマ（実装済み）:**

**単年データ（従来）:**

```python
{
    "Type": str,                    # 物件種別
    "DistrictName": str,            # 地区名
    "TradePrice": float,            # 取引価格（円）
    "Area": float,                  # 面積（㎡）
    "UnitPrice": float,             # 単価（API提供）
    "BuildingYear": str,            # 建築年
    "latitude": float,              # 緯度（生成済み）
    "longitude": float,             # 経度（生成済み）
    "price_per_sqm": float,         # 単価（計算済み、円/㎡）
    "elevation": float,             # 高さ（可視化用、百万円単位）
    "color": list[int],             # RGB色配列（可視化用）
}
```

**複数年データ（fetch_real_estate_multi_year）:** ✅ **NEW**

```python
{
    "Year": str,                    # 年（例: "2024"）
    "Type": str,                    # 物件種別
    "DistrictName": str,            # 地区名
    "TradePrice": float,            # 取引価格（円）
    "Area": float,                  # 面積（㎡）
    "UnitPrice": float,             # 単価（API提供）
    "BuildingYear": str,            # 建築年
    ...                             # その他のカラム
}
```

**時系列集計結果（aggregate_by_region_timeseries）:** ✅ **NEW**

```python
{
    "Year": str,                                # 年
    "DistrictName": str,                        # 地区名
    "count": int,                               # 取引件数
    "price_per_sqm_mean": float,                # ㎡単価平均
    "price_per_sqm_median": float,              # ㎡単価中央値
    "price_per_sqm_mean_yoy_change": float,     # ㎡単価平均の前年比（%）✅ NEW
    "price_per_sqm_median_yoy_change": float,   # ㎡単価中央値の前年比（%）✅ NEW
    "price_per_tsubo_mean": float,              # 坪単価平均
    "price_per_tsubo_median": float,            # 坪単価中央値
    "price_per_tsubo_mean_yoy_change": float,   # 坪単価平均の前年比（%）✅ NEW
    "price_per_tsubo_median_yoy_change": float, # 坪単価中央値の前年比（%）✅ NEW
}
```

---

### Phase 3: 可視化 (Visualize) ✅ (一部)

**実装モジュール:**

- `src/real_state_geo_core/visualization/pydeck.py`
- `notebooks/01_pydeck_experiment.ipynb`

**実装済み処理:**

1. **`convert_for_pydeck(df)`** (pydeck.py:4-41)
   - `polars.DataFrame` を pydeck 用の `list[dict]` に変換
   - 必要カラムの抽出:
     - 座標: `longitude`, `latitude`
     - 可視化: `elevation`, `color`
     - 属性: `DistrictName`, `TradePrice`, `Area`, `BuildingYear`
   - 型変換:
     - 数値カラム → `Float64`
     - 文字列カラム → `Utf8`
   - 戻り値: `list[dict]`（JSON シリアライズ可能な形式）

2. **Jupyter Notebook内の3D可視化実装** (01_pydeck_experiment.ipynb)
   - **ColumnLayer構築:**
     ```python
     pdk.Layer(
         "ColumnLayer",
         data=data_records,
         get_position=["longitude", "latitude"],
         get_elevation="elevation",           # 取引価格（百万円単位）
         elevation_scale=1,
         radius=30,                           # 柱の半径（メートル）
         get_fill_color="color",              # 単価に基づくグラデーション
         pickable=True,
         auto_highlight=True,
     )
     ```
   - **GeoJsonLayer（区境界）:**
     ```python
     pdk.Layer(
         "GeoJsonLayer",
         data=boundary_geojson,
         get_line_color=[180, 180, 200, 200],
         get_fill_color=[0, 0, 0, 0],         # 塗りつぶしなし
         line_width_min_pixels=2,
     )
     ```
   - **マッププロバイダー選択機能:**
     - Mapbox（要トークン）
     - Carto（日本語対応、トークン不要）
   - **ViewState設定:**
     - `latitude`, `longitude`: データの中心座標
     - `zoom`: 13（区レベル）
     - `pitch`: 60（3D視点）
     - `bearing`: 20（方位角）
   - **ツールチップ:**
     ```python
     tooltip={
         "text": "地区: {DistrictName}\n価格: {TradePrice}円\n面積: {Area}㎡\n築年: {BuildingYear}"
     }
     ```
   - **HTML出力:**
     ```python
     deck.to_html(str(output_path))
     # 出力例: output/pydeck_江東区_2024.html
     ```

**色マッピングアルゴリズム（Notebookより）:**

```python
def price_to_color(price_per_sqm, min_price, max_price):
    """単価を色（RGB）に変換
    シアン(0, 255, 255) → マゼンタ(255, 0, 255) のグラデーション
    """
    normalized = (price_per_sqm - min_price) / (max_price - min_price + 1e-10)
    normalized = float(np.clip(normalized, 0, 1))

    r = int(255 * normalized)
    g = int(255 * (1 - normalized))
    b = 255
    return [r, g, b, 200]

# 外れ値除外（10-90パーセンタイル）
min_price = df_geo.select(pl.col("price_per_sqm").quantile(0.1)).item()
max_price = df_geo.select(pl.col("price_per_sqm").quantile(0.9)).item()
```

**未実装 / 今後:**

- **フレーム出力（動画化のための連番画像生成）:**
  - Playwright によるHTMLスクリーンショット自動取得
  - 複数年データの時系列フレーム生成
  - カメラアングル・視点の自動遷移
- **可視化パラメータ管理:**
  - YAML設定ファイルでの色・高さ・半径の管理
  - 複数可視化スタイルのプリセット
- **パフォーマンス最適化:**
  - 大規模データセット（1万件以上）のクラスタリング
  - WebGL負荷軽減

**出力例（実装済み）:**

- `output/pydeck_江東区_2024.html` — インタラクティブな3D地図（WebGLベース）

**出力例（未実装）:**

- `output/frames_pydeck/{year}_{frame:04d}.png` — 動画用連番フレーム

---

### Phase 3B: PyVista版可視化 ⬜（未実装）

**計画内容:**

1. PyVistaによる3Dメッシュ化・レンダリング
2. 地図タイル取得（contextily等）
3. カスタムシェーダー・テクスチャ適用

**出力例:** `output/frames_pyvista/{year}_{frame:04d}.png`

**メリット:**

- オフラインレンダリングによる高品質な画像生成
- カメラパスの完全制御

**検討事項:**

- pydeck（WebGL）との比較検証が必要

---

### Phase 4: AI強化 (Enhance) ⬜（未実装）

**計画内容:**

1. Playwright等でHTMLフレーム出力 → 連番PNG生成
2. FFmpegでPNGシーケンスを一時動画化
3. Runway Gen-3（Video-to-Video）APIに送信
   - 画質・質感の強化
   - シネマティックな雰囲気付与
4. 強化済み動画を取得

**必要な実装:**

- Runway API認証・アップロード処理
- ジョブステータスポーリング
- 動画ダウンロード・保存

**出力例:** `output/enhanced/enhanced_{segment}.mp4`

**コスト試算:**

- Runway Gen-3: $0.05/秒程度（60秒 = $3）

---

### Phase 5: 動画合成 (Compose) ⬜（未実装）

**計画内容:**

1. FFmpegによる動画結合
   ```bash
   ffmpeg -f concat -i filelist.txt -c copy output.mp4
   ```
2. テキストオーバーレイ
   - 西暦カウンター（例: "1995年 → 2024年"）
   - エリア名（例: "東京都港区"）
   - データソース表記（例: "出典: 国土交通省"）
3. BGM合成（オプション）
   - 著作権フリーBGMの選定
   - 音量調整（-20dB程度）

**FFmpegフィルタ例:**

```bash
ffmpeg -i input.mp4 -vf "drawtext=text='%{eif\:1995+t\:d}年':x=50:y=50:fontsize=72:fontcolor=white" output.mp4
```

**出力例:** `output/composed/composed.mp4`

---

### Phase 6: 最終出力 (Export) ⬜（未実装）

**計画内容:**

1. YouTube Shorts仕様への最終エンコード
   ```bash
   ffmpeg -i composed.mp4 \
       -vf "scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2" \
       -r 30 -t 60 -c:v libx264 -preset slow -crf 18 -c:a aac -b:a 192k \
       final.mp4
   ```
2. メタデータ付与
   - タイトル
   - 説明文
   - タグ（#不動産 #データ可視化 等）

**仕様確認:**

- 解像度: 1080x1920 (9:16)
- フレームレート: 30fps
- 動画長: 60秒以内
- コーデック: H.264
- 音声: AAC 192kbps

**出力例:** `output/final/urban_dynamics_港区_2024.mp4`

---

## 4. ディレクトリ構成

```
clip_automation_poc/
├── docs/
│   ├── PLANNING.md                          # 企画書（マーケティング・スケジュール）
│   └── SYSTEM_DESIGN.md                     # 技術仕様書（本ドキュメント）
├── data/
│   ├── raw/                                 # 生データ保存先
│   ├── processed/                           # 加工済みデータ（GeoJSON等）
│   ├── station/
│   │   └── station20251211free.csv          # 駅データ.jp CSVマスタ
│   └── utf8/                                # UTF-8正規化後のCSV
├── src/
│   └── real_state_geo_core/                 # メインPythonパッケージ
│       ├── __init__.py
│       ├── utils.py                         # 共通ユーティリティ（拡張用）
│       ├── data/
│       │   ├── __init__.py
│       │   └── fetcher.py                   # RealEstateDataFetcher クラス
│       ├── processing/                      # データ処理モジュール ✅ NEW
│       │   ├── __init__.py
│       │   └── aggregator.py                # RealEstateAggregator クラス（統計・時系列分析）
│       └── visualization/
│           ├── __init__.py
│           └── pydeck.py                    # convert_for_pydeck 関数
├── examples/                                # 使用例スクリプト ✅ NEW
│   └── timeseries_analysis_example.py       # 時系列分析の実行例
├── output/
│   ├── pydeck_*.html                        # 可視化HTML（実装済み）✅
│   ├── timeseries/                          # 時系列統計CSV出力先 ✅ NEW
│   │   └── timeseries_stats_*.csv           # 時系列集計結果（前年比付き）
│   ├── frames_pydeck/                       # 動画用フレーム（未実装）⬜
│   ├── frames_pyvista/                      # PyVistaフレーム（未実装）⬜
│   ├── enhanced/                            # Runway AI強化済み動画（未実装）⬜
│   ├── composed/                            # テキスト合成後動画（未実装）⬜
│   └── final/                               # 最終出力動画（未実装）⬜
├── notebooks/
│   └── 01_pydeck_experiment.ipynb           # pydeck可視化実験（実装済み）✅
├── .env                                     # 環境変数（API KEY, TOKEN）
├── .gitignore
├── CLAUDE.md                                # Claudeへの指示書
├── README.md
├── pyproject.toml                           # Python依存関係・Ruff設定
└── uv.lock                                  # uvロックファイル
```

**実装状況の凡例:**

- ✅ 実装済み
- ⬜ 未実装

---

## 5. 技術スタック

### 5.1 コア技術

| カテゴリ             | 技術                               | 用途                                           | 実装状況 |
| -------------------- | ---------------------------------- | ---------------------------------------------- | -------- |
| **言語**             | Python 3.13                        | メイン開発言語                                 | ✅       |
| **パッケージ管理**   | uv                                 | 高速な依存関係管理                             | ✅       |
| **データ処理**       | Polars                             | 高速データフレーム処理                         | ✅       |
| **API通信**          | requests                           | 不動産情報ライブラリAPI呼び出し                | ✅       |
| **3D可視化**         | pydeck                             | WebGL/Deck.gl による地理空間3D可視化           | ✅       |
| **地図タイル**       | Mapbox / Carto                     | 背景地図タイル（Carto=日本語対応）             | ✅       |
| **ジオコーディング** | 駅データ.jp CSV + カスタムロジック | 駅座標マスタとランダムオフセットによる座標生成 | ✅       |
| **行政境界データ**   | JapanCityGeoJson（GitHub）         | 区境界GeoJSONの取得                            | ✅       |
| **Jupyter**          | JupyterLab                         | インタラクティブな実験・検証                   | ✅       |
| **リント/フォーマ**  | Ruff                               | 高速なコード品質チェック                       | ✅       |
| **並行処理**         | concurrent.futures                 | ThreadPoolExecutorによる並行API呼び出し        | ✅       |
| **3D可視化（代替）** | PyVista                            | 3Dメッシュ可視化（検討中）                     | ⬜       |
| **動画処理**         | FFmpeg                             | 動画結合・エンコード                           | ⬜       |
| **AI拡張**           | Runway Gen-3 API                   | Video-to-Video による画質強化                  | ⬜       |
| **スクリーンショ**   | Playwright                         | HTML可視化からのフレーム出力                   | ⬜       |

### 5.2 主要ライブラリ（pyproject.tomlより）

```toml
[project.dependencies]
jupyterlab = ">=4.5.2"
pandas = ">=3.0.0"
numpy = ">=2.0.0"
pydeck = ">=0.9.0"
pyarrow = ">=18.0.0"
python-dotenv = ">=1.2.1"
polars = ">=1.37.1"

[dependency-groups.dev]
ruff = ">=0.14.10"
```

### 5.3 外部データソース

| データソース         | URL/パス                               | 用途                 | 取得方法                   |
| -------------------- | -------------------------------------- | -------------------- | -------------------------- |
| 不動産情報ライブラリ | `https://www.reinfolib.mlit.go.jp/`    | 不動産取引価格データ | API（要キー）              |
| 駅データ.jp          | `data/station/station20251211free.csv` | 駅名→緯度経度マスタ  | 手動ダウンロード           |
| JapanCityGeoJson     | `github.com/niiyz/JapanCityGeoJson`    | 市区町村境界GeoJSON  | 自動ダウンロード（実装済） |
| Mapbox/Carto         | Mapbox API / Carto CDN                 | 地図タイル           | API経由（トークン任意）    |

## 6. 設定ファイル仕様

### 6.1 環境変数 (.env)

**必須:**

```bash
REINFOLIB_API_KEY=your_api_key_here
```

**オプション:**

```bash
MAPBOX_TOKEN=your_mapbox_token_here
```

- `REINFOLIB_API_KEY`: 不動産情報ライブラリAPIのサブスクリプションキー（Azure API Management）
- `MAPBOX_TOKEN`: Mapbox地図タイル用トークン（未設定時はCartoにフォールバック）

### 6.2 Ruff設定 (pyproject.toml)

```toml
[tool.ruff]
line-length = 120              # 行の長さ制限
target-version = "py313"       # Pythonターゲットバージョン

select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "C4",   # flake8-comprehensions
    "UP",   # pyupgrade
]

ignore = ["E501"]              # 行の長さ制限はline-lengthで管理

[tool.ruff.format]
quote-style = "double"         # ダブルクォート
indent-style = "space"         # スペースインデント
```

### 6.3 東京23区コード定義 (Notebook内)

```python
TOKYO_23_WARDS = {
    "千代田区": "13101",
    "中央区": "13102",
    "港区": "13103",
    "新宿区": "13104",
    # ... 全23区
    "江戸川区": "13123",
}
```

### 6.4 区中心座標定義 (Notebook内)

```python
WARD_CENTER_COORDS = {
    "台東区": (35.7121, 139.7797),
    "港区": (35.6580, 139.7514),
    # ... 全23区
    "江東区": (35.6731, 139.8170),
}
```

**今後の改善案:**

- YAML設定ファイルへの統合
- 可視化パラメータ（色、高さスケール、半径等）の外部化

---

## 7. 主要機能（実装済み）

### 7.1 データ取得機能 ✅

- ✅ 不動産情報ライブラリAPI連携（gzip対応）
- ✅ 駅座標マスタ作成（駅データ.jp CSV読み込み、正規化）
- ✅ 区境界GeoJSON自動取得（JapanCityGeoJson）
- ✅ ランダムジオコーディング（面積ベースの座標散布）
- ✅ **複数年データの並行取得** (`fetch_real_estate_multi_year`) ✨ **NEW**

### 7.2 データ加工・集計機能 ✅

- ✅ Polars DataFrameへの変換
- ✅ 数値カラムのクリーニング（カンマ除去、型変換）
- ✅ 欠損値除去
- ✅ 単価計算（円/㎡、円/坪の両方対応）
- ✅ 統計情報算出（平均、中央値、最小、最大、標準偏差、件数）
- ✅ **地域別集計** (`aggregate_by_region`)
- ✅ **時系列×地域別集計** (`aggregate_by_region_timeseries`) ✨ **NEW**
- ✅ **前年比変化率（YoY）の自動計算** ✨ **NEW**
- ✅ **外れ値除外機能**（分位点ベース）

### 7.3 可視化機能 ✅

- ✅ pydeck ColumnLayer による3D可視化
- ✅ 取引価格に基づく高さマッピング
- ✅ 単価に基づく色マッピング（シアン→マゼンタグラデーション）
- ✅ 区境界GeoJsonLayerの重ね合わせ
- ✅ Mapbox / Carto地図タイル選択機能
- ✅ インタラクティブツールチップ（地区名、価格、面積、築年）
- ✅ HTML出力

### 7.4 使いやすさ ✅

- ✅ 東京23区任意選択可能
- ✅ 年度指定可能
- ✅ Jupyter Notebookによるインタラクティブな実験環境
- ✅ エラーハンドリング・ログ出力

## 8. 未実装機能と今後の課題

### 8.1 優先度：高

1. **フレーム出力機能（動画化のための基盤）**
   - Playwright によるHTMLスクリーンショット自動取得
   - 複数年データの時系列フレーム生成
   - カメラアングル自動遷移

2. **厳密なジオコーディング**
   - 地区名+最寄駅の組み合わせマッチング
   - Google Geocoding API等の外部API連携
   - ジオコーディング精度の評価

3. **動画合成パイプライン（Phase 5）**
   - FFmpegによるフレーム結合
   - テキストオーバーレイ（年カウンター、エリア名）
   - BGM合成

### 8.2 優先度：中

4. **時系列処理の拡張**
   - 取引時期パース（"2024年第3四半期" → "2024Q3"）
   - 四半期ごとの集約・トレンド分析
   - 移動平均・季節調整機能

5. **データ品質向上**
   - 外れ値除去（IQR法、Zスコア等）
   - 建築年の補完・正規化

6. **Parquet永続化**
   - 加工済みデータのParquet保存
   - データバージョニング

### 8.3 優先度：低（将来拡張）

7. **PyVista版可視化（Phase 3B）**
   - 3Dメッシュ化・レンダリング
   - 地図タイル取得（contextily等）

8. **Runway AI強化（Phase 4）**
   - Video-to-Video API連携
   - 画質・質感の強化

9. **全国対応**
   - 市区町村コードの拡張
   - 地方都市の中心座標定義

10. **可視化パラメータ管理**
    - YAML設定ファイル化
    - 複数スタイルプリセット

## 9. 技術的な制約・既知の問題

### 9.1 ジオコーディングの精度

- **現状:** 区の中心座標からランダムオフセットによる座標生成
- **影響:** 実際の物件位置と異なる可能性が高い
- **対策案:** 地区名マスタ・最寄駅情報を活用した推定精度向上

### 9.2 大規模データのパフォーマンス

- **現状:** 1,000〜2,000件程度のデータで動作確認
- **懸念:** 1万件以上のデータでWebGL負荷増大の可能性
- **対策案:** クラスタリング、LOD（Level of Detail）実装

### 9.3 区境界データの欠損

- **問題:** 一部の区でGeoJSONが404エラー（例: 江東区）
- **影響:** 区境界が表示されない
- **対策案:** 代替データソース（国土地理院等）の検討

## 10. PoCの成功基準

### 10.1 達成済み基準 ✅

- ✅ APIからデータ取得が可能
- ✅ 任意の区のデータを可視化できる
- ✅ 3D表現で取引価格・単価を直感的に理解できる
- ✅ インタラクティブな操作が可能

### 10.2 次のマイルストーン

- ⬜ 動画ファイル（MP4）の自動生成
- ⬜ 60秒のYouTube Shorts形式（1080x1920）への出力
- ⬜ 複数年データの時系列アニメーション

---

## 付録A: 参考リンク

### データソース

- [不動産情報ライブラリ](https://www.reinfolib.mlit.go.jp/) — 国土交通省 不動産取引価格情報API
- [駅データ.jp](https://ekidata.jp/) — 駅座標CSVマスタ
- [JapanCityGeoJson](https://github.com/niiyz/JapanCityGeoJson) — 市区町村境界GeoJSON
- [Mapbox](https://www.mapbox.com/) — 地図タイルプロバイダー
- [Carto](https://carto.com/basemaps/) — 日本語対応地図タイル

### 技術ドキュメント

- [Polars](https://docs.pola.rs/) — 高速データフレームライブラリ
- [pydeck](https://pydeck.gl/) — Deck.gl Python バインディング
- [PyVista](https://docs.pyvista.org/) — 3D可視化ライブラリ（検討中）
- [Runway API](https://docs.runwayml.com/) — AI動画生成API（未実装）
- [FFmpeg](https://ffmpeg.org/ffmpeg-filters.html) — 動画処理（未実装）
- [Playwright](https://playwright.dev/python/) — ブラウザ自動化（未実装）

### ツール

- [uv](https://github.com/astral-sh/uv) — 高速Pythonパッケージマネージャー
- [Ruff](https://docs.astral.sh/ruff/) — 高速リンター・フォーマッター

## 付録B: 実装コードリファレンス

### クラス・関数一覧

| モジュール                                          | 要素                              | 行番号  | 概要                                         |
| --------------------------------------------------- | --------------------------------- | ------- | -------------------------------------------- |
| `src/real_state_geo_core/data/fetcher.py`           | `RealEstateDataFetcher`           | 13-295  | データ取得統合クラス                         |
| 同上                                                | `fetch_real_estate()`             | 31-67   | 不動産取引データAPI取得                      |
| 同上                                                | `clean_real_estate_data()`        | 69-97   | DataFrame変換・クリーニング                  |
| 同上                                                | `fetch_station_master()`          | 99-145  | 駅座標マスタ作成                             |
| 同上                                                | `fetch_boundary_geojson()`        | 147-181 | 区境界GeoJSON取得                            |
| 同上                                                | `geocode_random()`                | 183-208 | ランダム座標生成                             |
| 同上                                                | `fetch_real_estate_multi_year()`  | 210-295 | 複数年データの並行取得 ✅ NEW                |
| `src/real_state_geo_core/processing/aggregator.py` | `RealEstateAggregator`            | 8-382   | データ集計・統計分析クラス ✅ NEW            |
| 同上                                                | `calculate_sqm_price()`           | 37-47   | ㎡単価計算 ✅ NEW                            |
| 同上                                                | `calculate_tsubo_price()`         | 49-61   | 坪単価計算 ✅ NEW                            |
| 同上                                                | `aggregate_by_region()`           | 63-162  | 地域別統計集計 ✅ NEW                        |
| 同上                                                | `aggregate_by_region_timeseries()`| 164-286 | 時系列×地域別統計集計（前年比付き）✅ NEW    |
| 同上                                                | `_calculate_yoy_change()`         | 288-346 | 前年比変化率計算（内部メソッド）✅ NEW       |
| 同上                                                | `get_summary_statistics()`        | 348-382 | 全体統計サマリー取得 ✅ NEW                  |
| `src/real_state_geo_core/visualization/pydeck.py`  | `convert_for_pydeck()`            | 4-41    | pydeck用データ変換                           |
| `examples/timeseries_analysis_example.py`          | `main()`                          | —       | 時系列分析の使用例 ✅ NEW                    |
| `notebooks/01_pydeck_experiment.ipynb`             | セル全体                          | —       | 統合可視化ワークフロー（実験用）             |

### 使用例

#### 基本的な使い方（単年データ取得）

```python
from real_state_geo_core.data.fetcher import RealEstateDataFetcher
from real_state_geo_core.visualization.pydeck import convert_for_pydeck
import os

# 初期化
fetcher = RealEstateDataFetcher(
    api_key=os.getenv("REINFOLIB_API_KEY"),
    mapbox_token=os.getenv("MAPBOX_TOKEN")
)

# データ取得
api_response = fetcher.fetch_real_estate(year="2024", city_code="13103")
df = fetcher.clean_real_estate_data(api_response)

# 駅マスタ読み込み
station_lookup = fetcher.fetch_station_master("data/station/station20251211free.csv")

# 可視化用データ変換
data_records = convert_for_pydeck(df)
```

#### 時系列分析の使い方 ✅ **NEW**

```python
from real_state_geo_core.data.fetcher import RealEstateDataFetcher
from real_state_geo_core.processing.aggregator import RealEstateAggregator
import os

# データフェッチャーの初期化
fetcher = RealEstateDataFetcher(api_key=os.getenv("REINFOLIB_API_KEY"))

# 複数年データの並行取得（2020年～2024年、港区）
multi_year_df = fetcher.fetch_real_estate_multi_year(
    start_year=2020,
    end_year=2024,
    city_code="13103"
)

# Aggregatorの初期化
aggregator = RealEstateAggregator(multi_year_df)

# 時系列×地域別統計を計算（前年比付き）
timeseries_stats = aggregator.aggregate_by_region_timeseries(
    year_column="Year",
    group_by="DistrictName",  # 地区名で集計
    metrics=["mean", "median", "count"],
    price_unit="both",  # ㎡単価と坪単価の両方
    exclude_outliers=True,  # 外れ値除外
    percentile_range=(0.05, 0.95),  # 上下5%を除外
    calculate_yoy=True  # 前年比変化率を計算
)

# CSV保存
timeseries_stats.write_csv("output/timeseries/stats.csv")

# 特定地区の時系列推移を抽出
akasaka_trend = timeseries_stats.filter(pl.col("DistrictName") == "赤坂")
print(akasaka_trend.select(["Year", "price_per_sqm_mean", "price_per_sqm_mean_yoy_change"]))
```

詳細は `examples/timeseries_analysis_example.py` を参照してください。
