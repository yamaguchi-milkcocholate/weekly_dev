import gzip
import json
import logging

from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import requests


class RealEstateDataFetcher:
    """
    不動産・駅・区境界など各種データ取得を一手に担う統合クラス。

    Attributes:
        api_key (str): 不動産情報ライブラリAPIのキー。
        mapbox_token (str, optional): Mapboxのトークン。
    """

    def __init__(self, api_key: str, mapbox_token: str | None = None) -> None:
        """
        Args:
            api_key (str): 不動産情報ライブラリAPIのキー。
            mapbox_token (str, optional): Mapboxのトークン。
        """
        self.api_key: str = api_key
        self.mapbox_token: str | None = mapbox_token

    def fetch_real_estate(self, year: str, city_code: str) -> dict[str, Any] | None:
        """
        不動産情報ライブラリAPIから取引データを取得します。

        Args:
            year (str): 取得対象の年。
            city_code (str): 市区町村コード（5桁）。

        Returns:
            dict: APIレスポンスのJSONデータ。失敗時はNone。
        """
        url = "https://www.reinfolib.mlit.go.jp/ex-api/external/XIT001"
        # APIリクエストパラメータを構築
        params = {"year": year, "city": city_code, "priceClassification": "01"}
        headers = {"Ocp-Apim-Subscription-Key": self.api_key}
        try:
            # APIへGETリクエスト
            response = requests.get(url, params=params, headers=headers, timeout=30)
            if response.status_code != 200:
                # ステータスコードが200以外の場合は警告
                logging.warning(f"API Error: {response.status_code}, Response: {response.text[:200]}")
                return None
            try:
                # 通常のJSONレスポンスをパース
                return response.json()
            except json.JSONDecodeError:
                # gzip圧縮されている場合のデコード処理
                try:
                    content = gzip.decompress(response.content)
                    return json.loads(content.decode("utf-8"))
                except (OSError, json.JSONDecodeError) as e:
                    logging.error(f"レスポンスのデコードに失敗: {e}")
                    return None
        except requests.RequestException as e:
            # 通信例外時はエラーログ
            logging.error(f"APIリクエスト例外: {e}")
            return None

    def clean_real_estate_data(self, api_response: dict[str, Any]) -> pl.DataFrame | None:
        """
        APIレスポンスをPolars DataFrameに変換し、クリーニングします。

        Args:
            api_response (dict): APIから取得したレスポンスJSON。

        Returns:
            pl.DataFrame: クリーニング済みのPolars DataFrame。失敗時はNone。
        """
        # APIレスポンスにデータがなければNoneを返す
        if not api_response or "data" not in api_response:
            logging.warning("APIレスポンスにデータがありません")
            return None
        # レスポンスのdata部分をPolars DataFrameに変換
        df = pl.DataFrame(api_response["data"])
        # 数値カラム（カンマ区切り文字列）をfloat型に変換
        for col_name in ["TradePrice", "Area", "UnitPrice"]:
            if col_name in df.columns:
                df = df.with_columns(pl.col(col_name).cast(pl.Utf8).str.replace(",", "").cast(pl.Float64, strict=False))
        # 必須カラム（取引価格・面積）の欠損値を除去
        filter_expr = None
        for col in ["TradePrice", "Area"]:
            if col in df.columns:
                expr = pl.col(col).is_not_null()
                filter_expr = expr if filter_expr is None else filter_expr & expr
        if filter_expr is not None:
            df = df.filter(filter_expr)
        return df

    def fetch_station_master(self, csv_path: str) -> dict[str, tuple]:
        """
        駅データCSVを読み込み、駅名正規化・座標マスタ（駅名→座標）を作成します。

        Args:
            csv_path (str): 駅データCSVファイルのパス。

        Returns:
            dict: 駅名（正規化済み）をキー、(緯度, 経度)のタプルを値とする辞書。
        """
        path = Path(csv_path)
        # 駅データCSVの存在確認
        if not path.exists():
            logging.warning(f"駅データCSVが見つかりません: {path}")
            return {}
        # CSVをPolars DataFrameで読み込み
        station_df = pl.read_csv(path)
        # 東京都（都道府県コード=13）の駅のみ抽出
        if "pref_cd" in station_df.columns:
            station_df = station_df.filter(pl.col("pref_cd") == 13)

        def normalize_station_name(name: str | None) -> str:
            """
            駅名の全角空白除去・正規化
            """
            if name is None:
                return ""
            return str(name).replace("　", " ").strip()

        # 駅名を正規化した新カラムを追加
        if "station_name" in station_df.columns:
            station_df = station_df.with_columns(
                pl.col("station_name")
                .map_elements(normalize_station_name, return_dtype=pl.Utf8)
                .alias("station_name_norm")
            )
        # 駅名→(緯度, 経度)の辞書を作成
        station_lookup: dict[str, tuple] = {}
        for row in station_df.select(["station_name_norm", "lat", "lon"]).to_dicts():
            name = row["station_name_norm"]
            if name and name not in station_lookup:
                try:
                    station_lookup[name] = (float(row["lat"]), float(row["lon"]))
                except (TypeError, ValueError):
                    # 緯度・経度が不正な場合はスキップ
                    continue
        return station_lookup

    def fetch_boundary_geojson(self, ward_code: str, save_path: str | None = None) -> dict[str, Any] | None:
        """
        区境界GeoJSONを取得し、必要に応じて保存します。

        Args:
            ward_code (str): 区の市区町村コード（5桁）。
            save_path (str, optional): 保存先パス。指定しない場合はダウンロードのみ。

        Returns:
            dict: 区境界のGeoJSONデータ。失敗時はNone。
        """
        url = f"https://raw.githubusercontent.com/niiyz/JapanCityGeoJson/master/geojson/pref/13/{ward_code}.json"
        if save_path:
            path = Path(save_path)
            try:
                from urllib.request import urlretrieve

                # GeoJSONファイルをダウンロードして保存
                urlretrieve(url, path)
                with path.open(encoding="utf-8") as f:
                    return json.load(f)
            except (OSError, json.JSONDecodeError) as e:
                logging.error(f"GeoJSON取得・保存失敗: {e}")
                return None
        else:
            try:
                # GeoJSONを直接取得
                response = requests.get(url, timeout=30)
                if response.status_code == 200:
                    return response.json()
                logging.warning(f"GeoJSON取得失敗: {response.status_code}")
                return None
            except requests.RequestException as e:
                logging.error(f"GeoJSONリクエスト例外: {e}")
                return None

    def geocode_random(
        self, area_sqm: float, center_lat: float, center_lon: float, max_radius_km: float = 3.0
    ) -> dict[str, float]:
        """
        区の中心座標周辺にランダムな座標を生成します。

        Args:
            area_sqm (float): 物件面積（㎡）。
            center_lat (float): 区の中心緯度。
            center_lon (float): 区の中心経度。
            max_radius_km (float, optional): 最大半径（km）。デフォルト3.0。

        Returns:
            dict: {"latitude": float, "longitude": float} の座標辞書。
        """
        # 面積が大きいほど中心寄りに分布するよう半径を調整
        area_factor = min(area_sqm / 100.0, 1.0)
        # ランダムな半径（km）を生成
        radius_km = np.random.uniform(0, max_radius_km) * (1.5 - area_factor * 0.5)
        # ランダムな方向（角度）を生成
        angle = np.random.uniform(0, 2 * np.pi)
        # 緯度・経度方向のオフセットを計算
        lat_offset = (radius_km / 111.0) * np.cos(angle)
        lon_offset = (radius_km / 91.0) * np.sin(angle)
        # 中心座標にオフセットを加算して返却
        return {"latitude": center_lat + lat_offset, "longitude": center_lon + lon_offset}

    def fetch_real_estate_multi_year(
        self, start_year: int, end_year: int, city_code: str, max_workers: int = 5
    ) -> pl.DataFrame | None:
        """
        複数年にわたる不動産取引データを並行取得し、統合DataFrameを返します。

        Args:
            start_year (int): 開始年（例: 2020）。
            end_year (int): 終了年（例: 2024）。
            city_code (str): 市区町村コード（5桁）。
            max_workers (int, optional): 並行取得スレッド数。デフォルト5。

        Returns:
            pl.DataFrame | None: 全年統合後のDataFrame。取得失敗時はNone。

        Raises:
            ValueError: start_year > end_year の場合。
        """
        if start_year > end_year:
            raise ValueError("start_yearはend_year以下である必要があります")

        # 年ごとにAPIリクエストを並行実行
        def fetch_and_clean_year(year_int: int) -> pl.DataFrame | None:
            """指定年のデータを取得しクリーニングして返す"""
            year_str = str(year_int)
            logging.info(f"{year_str}年のデータ取得開始（市区町村コード: {city_code}）")
            api_response = self.fetch_real_estate(year_str, city_code)
            if api_response is None:
                logging.warning(f"{year_str}年のデータ取得失敗")
                return None
            df = self.clean_real_estate_data(api_response)
            if df is None or df.height == 0:
                logging.warning(f"{year_str}年のデータがクリーニング後に空です")
                return None
            # 年カラムを追加（文字列型）
            df = df.with_columns(pl.lit(year_str).alias("Year"))
            logging.info(f"{year_str}年のデータ取得完了（{df.height}件）")
            return df

        # ThreadPoolExecutorで並行処理
        dataframes: list[pl.DataFrame] = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # 各年のFutureオブジェクトを作成
            future_to_year = {
                executor.submit(fetch_and_clean_year, year): year for year in range(start_year, end_year + 1)
            }
            # 完了したタスクから順次結果を取得
            for future in as_completed(future_to_year):
                year = future_to_year[future]
                try:
                    df = future.result()
                    if df is not None and df.height > 0:
                        dataframes.append(df)
                except Exception as e:
                    logging.error(f"{year}年のデータ取得中に例外が発生: {e}")

        # 全年データを縦方向に結合
        if not dataframes:
            logging.warning("全年のデータ取得に失敗しました")
            return None

        combined_df = pl.concat(dataframes, how="vertical_relaxed")
        logging.info(f"全{len(dataframes)}年分のデータを統合（合計{combined_df.height}件）")
        return combined_df
