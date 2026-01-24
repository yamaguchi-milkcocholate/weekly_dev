"""時系列推移の可視化スクリプト.

複数年のデータを年ごとにpydeck可視化し、HTML出力する。
"""

import logging
import os

from pathlib import Path

import numpy as np
import polars as pl
import pydeck as pdk

from dotenv import load_dotenv

from real_state_geo_core.data.fetcher import RealEstateDataFetcher

# ロギング設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 環境変数の読み込み
load_dotenv()
API_KEY = os.getenv("REINFOLIB_API_KEY", "")
MAPBOX_TOKEN = os.getenv("MAPBOX_TOKEN")

# 港区の設定
WARD_CODE = "13103"
WARD_NAME = "港区"
CENTER_LAT = 35.6580
CENTER_LON = 139.7514

# 可視化期間
START_YEAR = 2020
END_YEAR = 2024


def price_to_color(price_per_sqm: float, min_price: float, max_price: float) -> list[int]:
    """
    単価を色（RGB）に変換.

    寒色（青）→暖色（赤→黄）のグラデーション
    低価格: [0, 100, 255] (青)
    中価格: [200, 0, 255] (紫)
    高価格: [255, 200, 0] (黄)

    Args:
        price_per_sqm (float): ㎡単価.
        min_price (float): 最小単価.
        max_price (float): 最大単価.

    Returns:
        list[int]: RGBA配列 [R, G, B, A].
    """
    # 正規化（0.0～1.0）
    normalized = (price_per_sqm - min_price) / (max_price - min_price + 1e-10)
    normalized = float(np.clip(normalized, 0, 1))

    # 3段階グラデーション
    if normalized < 0.5:
        # 青→紫（0.0～0.5）
        t = normalized * 2.0
        r = int(200 * t)
        g = int(100 * (1 - t))
        b = 255
    else:
        # 紫→黄（0.5～1.0）
        t = (normalized - 0.5) * 2.0
        r = int(200 + 55 * t)
        g = int(200 * t)
        b = int(255 * (1 - t))

    return [r, g, b, 200]


def convert_for_pydeck_with_color(df: pl.DataFrame, min_price: float, max_price: float) -> list[dict]:
    """
    polars DataFrameをpydeck用に変換し、色情報を付与.

    Args:
        df (pl.DataFrame): 変換対象のDataFrame.
        min_price (float): 色計算用の最小単価.
        max_price (float): 色計算用の最大単価.

    Returns:
        list[dict]: pydeck用のレコードリスト.
    """
    # 必要カラムの選択
    required_cols = ["longitude", "latitude", "price_per_sqm", "TradePrice", "Area", "DistrictName", "BuildingYear"]
    existing_cols = [col for col in required_cols if col in df.columns]

    df_selected = df.select(existing_cols)

    # 型変換
    df_selected = df_selected.with_columns(
        [
            pl.col("longitude").cast(pl.Float64),
            pl.col("latitude").cast(pl.Float64),
            pl.col("price_per_sqm").cast(pl.Float64),
            pl.col("TradePrice").cast(pl.Float64),
            pl.col("Area").cast(pl.Float64),
        ]
    )

    # 文字列カラムの型変換
    for col in ["DistrictName", "BuildingYear"]:
        if col in df_selected.columns:
            df_selected = df_selected.with_columns(pl.col(col).cast(pl.Utf8))

    # elevation（高さ）とcolor（色）を追加
    df_selected = df_selected.with_columns(
        [
            (pl.col("TradePrice") / 1_000_000).alias("elevation"),  # 百万円単位
            pl.col("price_per_sqm")
            .map_elements(lambda x: price_to_color(x, min_price, max_price), return_dtype=pl.List(pl.Int32))
            .alias("color"),
        ]
    )

    return df_selected.to_dicts()


def create_pydeck_visualization(
    data_records: list[dict],
    year: str,
    output_path: Path,
    boundary_geojson: dict | None = None,
) -> None:
    """
    pydeckで3D可視化を作成しHTML出力.

    Args:
        data_records (list[dict]): pydeck用データレコード.
        year (str): 年（タイトル用）.
        output_path (Path): HTML出力先パス.
        boundary_geojson (dict | None, optional): 区境界GeoJSON. デフォルト: None
    """
    # ColumnLayer（取引データ）
    column_layer = pdk.Layer(
        "ColumnLayer",
        data=data_records,
        get_position=["longitude", "latitude"],
        get_elevation="elevation",
        elevation_scale=1,
        radius=30,
        get_fill_color="color",
        pickable=True,
        auto_highlight=True,
    )

    layers = [column_layer]

    # GeoJsonLayer（区境界）
    if boundary_geojson:
        boundary_layer = pdk.Layer(
            "GeoJsonLayer",
            data=boundary_geojson,
            get_line_color=[180, 180, 200, 200],
            get_fill_color=[0, 0, 0, 0],
            line_width_min_pixels=2,
        )
        layers.append(boundary_layer)

    # ViewState（斜め45度からの視点）
    view_state = pdk.ViewState(
        latitude=CENTER_LAT,
        longitude=CENTER_LON,
        zoom=13,
        pitch=45,
        bearing=20,
    )

    # LightingEffect（陰影効果）
    lighting_effect = {
        "@@type": "LightingEffect",
        "ambientLight": {"@@type": "AmbientLight", "color": [255, 255, 255], "intensity": 1.0},
        "directionalLights": [
            {
                "@@type": "DirectionalLight",
                "color": [255, 255, 255],
                "intensity": 2.0,
                "direction": [-1, -3, -1],
            }
        ],
    }

    # ツールチップ
    tooltip = {
        "text": "地区: {DistrictName}\n価格: {TradePrice}円\n面積: {Area}㎡\n築年: {BuildingYear}\n単価: {price_per_sqm}円/㎡"
    }

    # マップスタイル（Mapboxダークまたはフォールバック）
    if MAPBOX_TOKEN:
        map_style = "mapbox://styles/mapbox/dark-v11"
    else:
        map_style = "https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json"
        logging.warning("MAPBOX_TOKENが未設定のため、Cartoマップを使用します")

    # Deckオブジェクト作成
    deck_params = {
        "map_provider": "mapbox",
        "layers": layers,
        "initial_view_state": view_state,
        "effects": [lighting_effect],
        "tooltip": tooltip,
        "map_style": map_style,
    }

    # MapboxトークンがあればAPI keyとして設定
    if MAPBOX_TOKEN:
        deck_params["api_keys"] = {"mapbox": MAPBOX_TOKEN}

    deck = pdk.Deck(**deck_params)

    # HTML出力
    output_path.parent.mkdir(parents=True, exist_ok=True)
    deck.to_html(str(output_path))
    logging.info(f"{year}年の可視化を保存: {output_path}")


def main() -> None:
    """時系列可視化のメイン処理."""
    # データフェッチャーの初期化
    fetcher = RealEstateDataFetcher(api_key=API_KEY, mapbox_token=MAPBOX_TOKEN)

    # 複数年データの取得
    logging.info(f"{START_YEAR}年～{END_YEAR}年のデータを取得中...")
    multi_year_df = fetcher.fetch_real_estate_multi_year(START_YEAR, END_YEAR, WARD_CODE)

    if multi_year_df is None or multi_year_df.height == 0:
        logging.error("データの取得に失敗しました")
        return

    logging.info(f"取得完了: {multi_year_df.height}件のデータ")

    # 中古マンションのみフィルタ
    multi_year_df = multi_year_df.filter(pl.col("Type").str.contains("中古マンション等"))
    logging.info(f"フィルタ後: {multi_year_df.height}件")

    # 単価計算
    multi_year_df = multi_year_df.with_columns((pl.col("TradePrice") / pl.col("Area")).alias("price_per_sqm"))

    # 座標生成（ランダムジオコーディング）
    def geocode_with_default(area: float | None) -> dict[str, float]:
        """デフォルト面積を設定してジオコード."""
        return fetcher.geocode_random(area or 50.0, CENTER_LAT, CENTER_LON)

    multi_year_df = multi_year_df.with_columns(
        pl.struct(["Area"])
        .map_elements(
            lambda x: geocode_with_default(x["Area"]),
            return_dtype=pl.Struct([pl.Field("latitude", pl.Float64), pl.Field("longitude", pl.Float64)]),
        )
        .alias("geo")
    ).unnest("geo")

    # 区境界GeoJSONの取得
    boundary_geojson = fetcher.fetch_boundary_geojson(WARD_CODE)

    # 全データの単価範囲を計算（色スケール統一のため）
    price_stats = multi_year_df.select(
        pl.col("price_per_sqm").quantile(0.1).alias("min_price"),
        pl.col("price_per_sqm").quantile(0.9).alias("max_price"),
    ).row(0)
    min_price = float(price_stats[0])
    max_price = float(price_stats[1])
    logging.info(f"単価範囲（10-90パーセンタイル）: {min_price:,.0f}円/㎡ ～ {max_price:,.0f}円/㎡")

    # 年ごとに可視化
    output_dir = Path("output/timeseries_pydeck")
    output_dir.mkdir(parents=True, exist_ok=True)

    for year in range(START_YEAR, END_YEAR + 1):
        year_str = str(year)
        logging.info(f"{year_str}年の可視化を作成中...")

        # 該当年のデータを抽出
        year_df = multi_year_df.filter(pl.col("Year") == year_str)

        if year_df.height == 0:
            logging.warning(f"{year_str}年のデータが空です。スキップします")
            continue

        logging.info(f"{year_str}年: {year_df.height}件")

        # pydeck用データ変換
        data_records = convert_for_pydeck_with_color(year_df, min_price, max_price)

        # HTML出力パス
        output_path = output_dir / f"pydeck_{WARD_NAME}_{year_str}.html"

        # 可視化作成
        create_pydeck_visualization(data_records, year_str, output_path, boundary_geojson)

    logging.info(f"すべての可視化が完了しました: {output_dir}")
    logging.info(f"生成されたファイル数: {len(list(output_dir.glob('*.html')))}")


if __name__ == "__main__":
    main()
