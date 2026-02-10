"""地域別統計の時系列推移を可視化するスクリプト.

個別の取引レコードではなく、地域ごとに集計した統計値（平均単価、中央値等）を可視化する。
各地区が1本の柱として表現され、高さ＝平均単価、色＝前年比変化率となる。
"""

import logging
import os

from pathlib import Path

import numpy as np
import polars as pl
import pydeck as pdk

from dotenv import load_dotenv

from real_state_geo_core.data.fetcher import RealEstateDataFetcher
from real_state_geo_core.processing.aggregator import RealEstateAggregator

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

# 地区名と代表座標のマッピング（港区の主要地区）
DISTRICT_COORDS = {
    "赤坂": (35.6733, 139.7369),
    "麻布十番": (35.6551, 139.7372),
    "六本木": (35.6627, 139.7293),
    "白金": (35.6411, 139.7214),
    "高輪": (35.6391, 139.7386),
    "芝": (35.6495, 139.7475),
    "新橋": (35.6657, 139.7575),
    "浜松町": (35.6551, 139.7569),
    "虎ノ門": (35.6687, 139.7504),
    "愛宕": (35.6619, 139.7493),
    "芝浦": (35.6464, 139.7498),
    "台場": (35.6267, 139.7744),
    "港南": (35.6297, 139.7477),
    "三田": (35.6484, 139.7425),
    "西麻布": (35.6596, 139.7241),
    "南麻布": (35.6490, 139.7283),
    "元麻布": (35.6544, 139.7311),
    "東麻布": (35.6571, 139.7401),
}


def yoy_change_to_color(yoy_change: float | None) -> list[int]:
    """
    前年比変化率を色（RGB）に変換.

    マイナス（下落）: 青系
    ゼロ（横ばい）: 白
    プラス（上昇）: 赤系

    Args:
        yoy_change (float | None): 前年比変化率（%）.

    Returns:
        list[int]: RGBA配列 [R, G, B, A].
    """
    if yoy_change is None:
        # データなし（初年度等）は灰色
        return [100, 100, 100, 200]

    # ±10%の範囲で正規化
    normalized = np.clip(yoy_change / 10.0, -1.0, 1.0)

    if normalized < 0:
        # 下落: 青系（-10% = 濃い青、0% = 白）
        t = abs(normalized)
        r = int(255 * (1 - t * 0.7))
        g = int(255 * (1 - t * 0.5))
        b = 255
    else:
        # 上昇: 赤系（0% = 白、+10% = 濃い赤）
        t = normalized
        r = 255
        g = int(255 * (1 - t * 0.5))
        b = int(255 * (1 - t * 0.7))

    return [r, g, b, 200]


def price_to_color(price_mean: float, min_price: float, max_price: float) -> list[int]:
    """
    平均単価を色（RGB）に変換.

    寒色（青）→暖色（赤→黄）のグラデーション

    Args:
        price_mean (float): 平均㎡単価.
        min_price (float): 最小単価.
        max_price (float): 最大単価.

    Returns:
        list[int]: RGBA配列 [R, G, B, A].
    """
    # 正規化（0.0～1.0）
    normalized = (price_mean - min_price) / (max_price - min_price + 1e-10)
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


def convert_aggregated_for_pydeck(
    stats_df: pl.DataFrame,
    year: str,
    min_price: float,
    max_price: float,
    color_mode: str = "price",
) -> list[dict]:
    """
    集計済み統計DataFrameをpydeck用に変換.

    Args:
        stats_df (pl.DataFrame): 地域別統計DataFrame.
        year (str): 対象年.
        min_price (float): 色計算用の最小単価.
        max_price (float): 色計算用の最大単価.
        color_mode (str, optional): 色モード（"price"=単価、"yoy"=前年比）. デフォルト: "price"

    Returns:
        list[dict]: pydeck用のレコードリスト.
    """
    # 該当年のデータを抽出
    year_stats = stats_df.filter(pl.col("Year") == year)

    if year_stats.height == 0:
        return []

    # pydeck用レコードを作成
    records = []
    for row in year_stats.to_dicts():
        district_name = row.get("DistrictName", "不明")

        # 地区の代表座標を取得
        if district_name in DISTRICT_COORDS:
            lat, lon = DISTRICT_COORDS[district_name]
        else:
            # 未知の地区は港区中心にプロット
            lat, lon = CENTER_LAT, CENTER_LON
            logging.warning(f"地区 '{district_name}' の座標が未定義です。中心座標を使用します")

        # 平均単価を高さに変換（100万円/㎡単位）
        price_mean = row.get("price_per_sqm_mean", 0.0)
        elevation = price_mean / 1_000_000.0  # 例: 1,500,000円/㎡ → 高さ1.5

        # 色の計算
        if color_mode == "yoy":
            yoy_change = row.get("price_per_sqm_mean_yoy_change")
            color = yoy_change_to_color(yoy_change)
        else:
            color = price_to_color(price_mean, min_price, max_price)

        # 件数を半径に反映（件数が多いほど太い柱）
        count = row.get("count", 1)
        radius = 50 + min(count, 200) * 0.5  # 基本半径50m、最大150m

        records.append(
            {
                "longitude": lon,
                "latitude": lat,
                "elevation": elevation,
                "color": color,
                "radius": radius,
                "district_name": district_name,
                "price_mean": price_mean,
                "price_median": row.get("price_per_sqm_median", 0.0),
                "count": count,
                "yoy_change": row.get("price_per_sqm_mean_yoy_change"),
            }
        )

    return records


def create_pydeck_visualization(
    data_records: list[dict],
    year: str,
    output_path: Path,
    color_mode: str = "price",
    boundary_geojson: dict | None = None,
) -> None:
    """
    pydeckで地域別統計の3D可視化を作成しHTML出力.

    Args:
        data_records (list[dict]): pydeck用データレコード.
        year (str): 年（タイトル用）.
        output_path (Path): HTML出力先パス.
        color_mode (str, optional): 色モード. デフォルト: "price"
        boundary_geojson (dict | None, optional): 区境界GeoJSON. デフォルト: None
    """
    # ColumnLayer（地域別統計）
    column_layer = pdk.Layer(
        "ColumnLayer",
        data=data_records,
        get_position=["longitude", "latitude"],
        get_elevation="elevation",
        elevation_scale=1,
        get_radius="radius",
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

    # ツールチップ（色モードに応じて変更）
    if color_mode == "yoy":
        tooltip_text = (
            "地区: {district_name}\n平均単価: {price_mean:.0f}円/㎡\n"
            + "中央値: {price_median:.0f}円/㎡\n件数: {count}\n前年比: {yoy_change:.2f}%"
        )
    else:
        tooltip_text = (
            "地区: {district_name}\n平均単価: {price_mean:.0f}円/㎡\n中央値: {price_median:.0f}円/㎡\n件数: {count}"
        )

    tooltip = {"text": tooltip_text}

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
    """地域別統計の時系列可視化メイン処理."""
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

    # Aggregatorで地域別統計を計算
    logging.info("地域別統計を計算中...")
    aggregator = RealEstateAggregator(multi_year_df)
    timeseries_stats = aggregator.aggregate_by_region_timeseries(
        year_column="Year",
        group_by="DistrictName",
        metrics=["mean", "median", "count"],
        price_unit="yen_per_sqm",  # ㎡単価のみ
        exclude_outliers=True,
        percentile_range=(0.05, 0.95),
        calculate_yoy=True,  # 前年比計算
    )

    logging.info(f"統計計算完了: {timeseries_stats.height}レコード（年×地区）")
    logging.info(f"地区数: {timeseries_stats.select('DistrictName').unique().height}")

    # 区境界GeoJSONの取得
    boundary_geojson = fetcher.fetch_boundary_geojson(WARD_CODE)

    # 全年の平均単価範囲を計算（色スケール統一のため）
    price_range = timeseries_stats.select(
        pl.col("price_per_sqm_mean").min().alias("min_price"),
        pl.col("price_per_sqm_mean").max().alias("max_price"),
    ).row(0)
    min_price = float(price_range[0])
    max_price = float(price_range[1])
    logging.info(f"平均単価範囲: {min_price:,.0f}円/㎡ ～ {max_price:,.0f}円/㎡")

    # 年ごとに可視化（価格モード）
    output_dir_price = Path("output/timeseries_aggregated_price")
    output_dir_price.mkdir(parents=True, exist_ok=True)

    # 年ごとに可視化（前年比モード）
    output_dir_yoy = Path("output/timeseries_aggregated_yoy")
    output_dir_yoy.mkdir(parents=True, exist_ok=True)

    for year in range(START_YEAR, END_YEAR + 1):
        year_str = str(year)
        logging.info(f"{year_str}年の可視化を作成中...")

        # pydeck用データ変換（価格モード）
        data_records_price = convert_aggregated_for_pydeck(
            timeseries_stats, year_str, min_price, max_price, color_mode="price"
        )

        if not data_records_price:
            logging.warning(f"{year_str}年のデータが空です。スキップします")
            continue

        logging.info(f"{year_str}年: {len(data_records_price)}地区")

        # 価格モードのHTML出力
        output_path_price = output_dir_price / f"pydeck_{WARD_NAME}_{year_str}_price.html"
        create_pydeck_visualization(
            data_records_price, year_str, output_path_price, color_mode="price", boundary_geojson=boundary_geojson
        )

        # 前年比モードのデータ変換と出力（2年目以降のみ）
        if year > START_YEAR:
            data_records_yoy = convert_aggregated_for_pydeck(
                timeseries_stats, year_str, min_price, max_price, color_mode="yoy"
            )
            output_path_yoy = output_dir_yoy / f"pydeck_{WARD_NAME}_{year_str}_yoy.html"
            create_pydeck_visualization(
                data_records_yoy, year_str, output_path_yoy, color_mode="yoy", boundary_geojson=boundary_geojson
            )

    logging.info("すべての可視化が完了しました")
    logging.info(f"価格モード: {output_dir_price}")
    logging.info(f"前年比モード: {output_dir_yoy}")


if __name__ == "__main__":
    main()
