import logging

from pathlib import Path
from typing import Any

import geopandas as gpd
import numpy as np
import polars as pl

from scipy.spatial import cKDTree
from shapely.geometry import Point


class MeshMasterBuilder:
    """
    東京23区を100m四方のメッシュで分割し、各メッシュ中心点に行政情報と最寄駅情報を付与するクラス。

    Attributes:
        station_csv_path (Path): 駅データCSVファイルのパス。
        boundary_geojson_dir (Path): 行政区域GeoJSONファイルが格納されたディレクトリのパス。
        mesh_size_m (float): メッシュのサイズ（メートル単位）。デフォルトは100.0。
    """

    # 地球の半径（km）- Haversine距離計算用
    EARTH_RADIUS_KM = 6371.0

    # 東京23区の市区町村コードリスト
    TOKYO_23KU_CODES = [
        "13101",  # 千代田区
        "13102",  # 中央区
        "13103",  # 港区
        "13104",  # 新宿区
        "13105",  # 文京区
        "13106",  # 台東区
        "13107",  # 墨田区
        "13108",  # 江東区
        "13109",  # 品川区
        "13110",  # 目黒区
        "13111",  # 大田区
        "13112",  # 世田谷区
        "13113",  # 渋谷区
        "13114",  # 中野区
        "13115",  # 杉並区
        "13116",  # 豊島区
        "13117",  # 北区
        "13118",  # 荒川区
        "13119",  # 板橋区
        "13120",  # 練馬区
        "13121",  # 足立区
        "13122",  # 葛飾区
        "13123",  # 江戸川区
    ]

    def __init__(self, station_csv_path: Path, boundary_geojson_dir: Path, mesh_size_m: float = 100.0) -> None:
        """
        Args:
            station_csv_path (Path): 駅データCSVファイルのパス。
            boundary_geojson_dir (Path): 行政区域GeoJSONファイルが格納されたディレクトリのパス。
            mesh_size_m (float, optional): メッシュのサイズ（メートル単位）。デフォルトは100.0。
        """
        self.station_csv_path: Path = station_csv_path
        self.boundary_geojson_dir: Path = boundary_geojson_dir
        self.mesh_size_m: float = mesh_size_m

    def _load_station_data(self) -> pl.DataFrame:
        """
        駅データCSVを読み込み、東京都内の駅のみに絞り込みます。

        Returns:
            pl.DataFrame: 駅名、緯度、経度を含むPolars DataFrame。

        Raises:
            FileNotFoundError: 駅データCSVが存在しない場合。
        """
        if not self.station_csv_path.exists():
            raise FileNotFoundError(f"駅データCSVが見つかりません: {self.station_csv_path}")

        # CSVを読み込み
        station_df = pl.read_csv(self.station_csv_path)

        # 東京都（都道府県コード=13）の駅のみ抽出
        if "pref_cd" in station_df.columns:
            station_df = station_df.filter(pl.col("pref_cd") == 13)

        # 必要なカラムのみ選択
        required_cols = ["station_name", "lat", "lon"]
        if all(col in station_df.columns for col in required_cols):
            station_df = station_df.select(required_cols)
        else:
            raise ValueError(f"駅データCSVに必要なカラム {required_cols} が存在しません")

        # 欠損値を除去
        station_df = station_df.drop_nulls()

        logging.info(f"駅データを読み込みました: {station_df.height}件")
        return station_df

    def _load_boundary_polygons(self) -> gpd.GeoDataFrame:
        """
        東京23区の行政区域GeoJSONを読み込み、統合したGeoDataFrameを返します。

        Returns:
            gpd.GeoDataFrame: 市区町村名、地区名、ジオメトリを含むGeoDataFrame。

        Raises:
            FileNotFoundError: 必要なGeoJSONファイルが見つからない場合。
        """
        gdfs: list[gpd.GeoDataFrame] = []

        for ward_code in self.TOKYO_23KU_CODES:
            geojson_path = self.boundary_geojson_dir / f"{ward_code}.json"

            if not geojson_path.exists():
                logging.warning(f"GeoJSONファイルが見つかりません: {geojson_path}")
                continue

            # GeoJSONを読み込み
            gdf = gpd.read_file(geojson_path)

            # CRS（座標参照系）を設定（WGS84）
            if gdf.crs is None:
                gdf = gdf.set_crs("EPSG:4326")

            gdfs.append(gdf)

        if not gdfs:
            raise FileNotFoundError("東京23区のGeoJSONファイルが1つも見つかりませんでした")

        # 全区のGeoDataFrameを統合
        combined_gdf = gpd.pd.concat(gdfs, ignore_index=True)
        logging.info(f"行政区域データを読み込みました: {len(combined_gdf)}件のポリゴン")

        return combined_gdf

    def _generate_mesh_grid(self, bounds: tuple[float, float, float, float]) -> gpd.GeoDataFrame:
        """
        バウンディングボックス内に指定サイズのメッシュ格子点を生成します。

        Args:
            bounds (tuple[float, float, float, float]): (minx, miny, maxx, maxy)のバウンディングボックス。

        Returns:
            gpd.GeoDataFrame: メッシュ中心点のGeoDataFrame（geometry, latitude, longitude）。
        """
        minx, miny, maxx, maxy = bounds

        # メッシュサイズを度数に変換（概算）
        # 緯度1度 ≒ 111km、経度1度 ≒ 91km（東京付近）
        lat_step = self.mesh_size_m / 1000.0 / 111.0
        lon_step = self.mesh_size_m / 1000.0 / 91.0

        # 格子点を生成
        lats = np.arange(miny, maxy, lat_step)
        lons = np.arange(minx, maxx, lon_step)

        # メッシュグリッドを作成
        lon_grid, lat_grid = np.meshgrid(lons, lats)

        # 平坦化して座標リストを作成
        lat_flat = lat_grid.flatten()
        lon_flat = lon_grid.flatten()

        # Point型ジオメトリを生成
        points = [Point(lon, lat) for lon, lat in zip(lon_flat, lat_flat, strict=True)]

        # GeoDataFrameを作成
        mesh_gdf = gpd.GeoDataFrame({"latitude": lat_flat, "longitude": lon_flat, "geometry": points}, crs="EPSG:4326")

        logging.info(f"メッシュ格子点を生成しました: {len(mesh_gdf)}点")
        return mesh_gdf

    def _filter_and_attach_info(self, mesh_gdf: gpd.GeoDataFrame, boundary_gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
        """
        メッシュ格子点を23区内に絞り込み、同時に行政情報を付与します。

        Args:
            mesh_gdf (gpd.GeoDataFrame): メッシュ格子点のGeoDataFrame。
            boundary_gdf (gpd.GeoDataFrame): 行政区域ポリゴンのGeoDataFrame。

        Returns:
            gpd.GeoDataFrame: 23区内のメッシュ格子点に行政情報が付与されたGeoDataFrame。
        """
        # 空間結合（点がポリゴン内に含まれるもののみ抽出、同時に行政属性を付与）
        joined_gdf = gpd.sjoin(mesh_gdf, boundary_gdf, how="inner", predicate="within")

        logging.info(f"23区内のメッシュ格子点をフィルタリングしました: {len(joined_gdf)}点")

        # GeoJSONのカラム名を確認（国土数値情報の標準形式）
        # N03_001: 都道府県名
        # N03_004: 市区町村名
        # N03_007: 市区町村コード

        city_col = None
        if "N03_004" in joined_gdf.columns:
            city_col = "N03_004"
        elif "city_name" in joined_gdf.columns:
            city_col = "city_name"

        # 市区町村名を設定
        if city_col is None:
            joined_gdf["city_name"] = ""
            logging.warning("市区町村名のカラムが見つかりませんでした")
        else:
            joined_gdf = joined_gdf.rename(columns={city_col: "city_name"})

        # 地区名は空文字列（GeoJSONに含まれていないため）
        joined_gdf["district_name"] = ""

        # 必要なカラムのみ選択
        result_gdf = joined_gdf[["latitude", "longitude", "city_name", "district_name", "geometry"]].copy()

        logging.info("行政情報を付与しました")
        return result_gdf

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        2点間のHaversine距離（大圏距離）をメートル単位で計算します。

        Args:
            lat1 (float): 地点1の緯度。
            lon1 (float): 地点1の経度。
            lat2 (float): 地点2の緯度。
            lon2 (float): 地点2の経度。

        Returns:
            float: 距離（メートル）。
        """
        # ラジアンに変換
        lat1_rad = np.radians(lat1)
        lon1_rad = np.radians(lon1)
        lat2_rad = np.radians(lat2)
        lon2_rad = np.radians(lon2)

        # 緯度・経度の差分
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad

        # Haversine公式
        a = np.sin(dlat / 2) ** 2 + np.cos(lat1_rad) * np.cos(lat2_rad) * np.sin(dlon / 2) ** 2
        c = 2 * np.arctan2(np.sqrt(a), np.sqrt(1 - a))

        # 距離（メートル）
        distance_m = self.EARTH_RADIUS_KM * c * 1000.0

        return distance_m

    def _calculate_nearest_station(self, mesh_gdf: gpd.GeoDataFrame, station_df: pl.DataFrame) -> pl.DataFrame:
        """
        各メッシュ点から最寄駅を検索し、距離と徒歩分数を計算します。

        Args:
            mesh_gdf (gpd.GeoDataFrame): メッシュ格子点のGeoDataFrame。
            station_df (pl.DataFrame): 駅データのPolars DataFrame。

        Returns:
            pl.DataFrame: メッシュマスターのPolars DataFrame。
        """
        # 駅の座標をNumPy配列に変換
        station_coords = station_df.select(["lat", "lon"]).to_numpy()
        station_names = station_df["station_name"].to_list()

        # cKDTreeを構築（高速な最近傍探索）
        tree = cKDTree(station_coords)

        # メッシュ点の座標をNumPy配列に変換
        mesh_coords = mesh_gdf[["latitude", "longitude"]].to_numpy()

        # 最寄駅を検索（距離はHaversineで再計算するため、ここでは使用しない）
        _, indices = tree.query(mesh_coords)

        # 結果を格納するリスト
        results: list[dict[str, Any]] = []

        for i, (lat, lon) in enumerate(mesh_coords):
            nearest_station_idx = indices[i]
            nearest_station_name = station_names[nearest_station_idx]
            nearest_station_lat = station_coords[nearest_station_idx][0]
            nearest_station_lon = station_coords[nearest_station_idx][1]

            # Haversine距離で正確な距離を計算
            distance_m = self._haversine_distance(lat, lon, nearest_station_lat, nearest_station_lon)

            # 徒歩分数を計算（80m/分）
            walk_minutes = round(distance_m / 80.0, 1)

            # メッシュIDを生成（緯度_経度の形式）
            mesh_id = f"{lat:.6f}_{lon:.6f}"

            # 市区町村名と地区名を取得
            city_name = mesh_gdf.iloc[i]["city_name"]
            district_name = mesh_gdf.iloc[i]["district_name"]

            results.append(
                {
                    "mesh_id": mesh_id,
                    "latitude": lat,
                    "longitude": lon,
                    "city_name": city_name,
                    "district_name": district_name,
                    "station_name": nearest_station_name,
                    "distance_m": round(distance_m, 1),
                    "walk_minutes": walk_minutes,
                }
            )

        # Polars DataFrameに変換
        result_df = pl.DataFrame(results)

        logging.info(f"最寄駅情報を計算しました: {result_df.height}件")
        return result_df

    def district_namebuild_mesh_master(self, output_path: Path) -> pl.DataFrame:
        """
        東京23区のメッシュマスターを生成し、CSVファイルに保存します。

        Args:
            output_path (Path): 出力CSVファイルのパス。

        Returns:
            pl.DataFrame: 生成されたメッシュマスターのPolars DataFrame。

        Raises:
            FileNotFoundError: 必要なデータファイルが見つからない場合。
        """
        logging.info("メッシュマスター生成を開始します")

        # Step 1: 駅データを読み込み
        station_df = self._load_station_data()

        # Step 2: 行政区域ポリゴンを読み込み
        boundary_gdf = self._load_boundary_polygons()

        # Step 3: バウンディングボックスを取得
        bounds = boundary_gdf.total_bounds  # (minx, miny, maxx, maxy)
        logging.info(f"バウンディングボックス: {bounds}")

        # Step 4: メッシュ格子点を生成
        mesh_gdf = self._generate_mesh_grid(bounds)

        # Step 5: 23区内の点のみに絞り込み、行政情報を付与
        mesh_gdf = self._filter_and_attach_info(mesh_gdf, boundary_gdf)

        # Step 6: 最寄駅と徒歩分数を計算
        mesh_master_df = self._calculate_nearest_station(mesh_gdf, station_df)

        # Step 7: CSVに保存
        mesh_master_df.write_csv(output_path)
        logging.info(f"メッシュマスターをCSVに保存しました: {output_path}")

        return mesh_master_df
