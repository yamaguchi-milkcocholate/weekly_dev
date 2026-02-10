"""メッシュ坪単価推定モジュール

東京23区の100mメッシュごとに、LightGBMモデルを用いて2025年の坪単価相場を推定します。
各メッシュの最寄り3駅の予測値を平均することで、より安定した推定を実現します。
"""

import json
import logging
import pickle
from datetime import datetime
from pathlib import Path

import polars as pl

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


class MeshPriceEstimator:
    """メッシュ坪単価推定クラス

    学習済みLightGBMモデルとメッシュマスターを用いて、
    東京23区の100mメッシュごとに坪単価を推定します。
    """

    def __init__(
        self,
        model_path: str | Path,
        mesh_master_path: str | Path,
        stats_path: str | Path,
    ) -> None:
        """
        Args:
            model_path: 学習済みモデルのパス（pickle形式）
            mesh_master_path: メッシュマスターのパス（CSV形式）
            stats_path: 集約統計量マスターのパス（CSV形式、2025年データ）
        """
        self.model_path = Path(model_path)
        self.mesh_master_path = Path(mesh_master_path)
        self.stats_path = Path(stats_path)

        # データ読み込み
        logger.info("データ読み込み開始")
        self._load_model()
        self._load_mesh_master()
        self._load_stats()
        logger.info("データ読み込み完了")

    def _load_model(self) -> None:
        """学習済みモデルを読み込みます。"""
        if not self.model_path.exists():
            raise FileNotFoundError(f"モデルファイルが見つかりません: {self.model_path}")

        with open(self.model_path, "rb") as f:
            self.model = pickle.load(f)

        logger.info(f"モデル読み込み完了: {self.model_path}")

    def _load_mesh_master(self) -> None:
        """メッシュマスターを読み込みます。"""
        if not self.mesh_master_path.exists():
            raise FileNotFoundError(f"メッシュマスターが見つかりません: {self.mesh_master_path}")

        self.mesh_master = pl.read_csv(self.mesh_master_path)
        logger.info(f"メッシュマスター読み込み完了: {self.mesh_master.height:,}件")

    def _load_stats(self) -> None:
        """集約統計量マスターを読み込みます。"""
        if not self.stats_path.exists():
            raise FileNotFoundError(f"集約統計量マスターが見つかりません: {self.stats_path}")

        self.stats = pl.read_csv(self.stats_path)
        logger.info(f"集約統計量マスター読み込み完了: {self.stats.height:,}件")

    def generate_mesh_price_map(
        self,
        target_year: int = 2025,
        age_range: tuple[int, int] = (1, 5),
        area_sqm: float = 70.0,
        structure: str = "RC",
        renovation: str = "なし",
        city_planning: str = "第一種住居地域",
        output_path: str | Path | None = None,
        metadata_path: str | Path | None = None,
        max_stations: int = 3,
    ) -> pl.DataFrame:
        """メッシュ坪単価マップを生成します。

        Args:
            target_year: 対象年（デフォルト: 2025）
            age_range: 築年数範囲（年）（デフォルト: (1, 5)）
            area_sqm: 専有面積（平米）（デフォルト: 70.0）
            structure: 建物構造（デフォルト: "RC"）
            renovation: 改装の有無（デフォルト: "なし"）
            city_planning: 用途地域（デフォルト: "第一種住居地域"）
            output_path: 出力CSVパス（Noneの場合は保存しない）
            metadata_path: メタデータJSONパス（Noneの場合は保存しない）
            max_stations: 使用する最寄り駅数（デフォルト: 3）

        Returns:
            pl.DataFrame: メッシュ坪単価マップ
        """
        logger.info("=== メッシュ坪単価マップ生成開始 ===")
        logger.info(f"対象年: {target_year}, 築年数: {age_range}, 面積: {area_sqm}㎡")
        logger.info(f"構造: {structure}, 改装: {renovation}, 用途地域: {city_planning}")

        # Step 1: 最寄りN駅の抽出
        logger.info(f"Step 1: 最寄り{max_stations}駅の抽出中...")
        mesh_stations = self._extract_top_stations(self.mesh_master, max_stations)
        logger.info(f"メッシュ数: {mesh_stations['mesh_id'].n_unique():,}件")

        # Step 2: 特徴量生成
        logger.info("Step 2: 特徴量生成中...")
        features_df = self._create_features(
            mesh_stations,
            target_year,
            age_range,
            area_sqm,
            structure,
            renovation,
            city_planning,
        )
        logger.info(f"特徴量生成完了: {features_df.height:,}件")

        # Step 3: 予測と集約
        logger.info("Step 3: 予測と集約中...")
        result_df = self._predict_and_aggregate(features_df, max_stations)
        logger.info(f"予測完了: {result_df.height:,}メッシュ")

        # Step 4: 保存
        if output_path is not None:
            output_path = Path(output_path)
            output_path.parent.mkdir(parents=True, exist_ok=True)
            result_df.write_csv(output_path)
            logger.info(f"結果を保存しました: {output_path}")

        if metadata_path is not None:
            metadata = {
                "target_year": target_year,
                "age_range": list(age_range),
                "area_sqm": area_sqm,
                "structure": structure,
                "renovation": renovation,
                "city_planning": city_planning,
                "month": 6,
                "quarter": 2,
                "model_file": str(self.model_path),
                "mesh_master_file": str(self.mesh_master_path),
                "aggregated_stats_file": str(self.stats_path),
                "generation_timestamp": datetime.now().isoformat(),
                "total_meshes": self.mesh_master["mesh_id"].n_unique(),
                "meshes_with_prediction": result_df.height,
                "max_stations_used": max_stations,
            }
            self._save_metadata(metadata, metadata_path)
            logger.info(f"メタデータを保存しました: {metadata_path}")

        logger.info("=== メッシュ坪単価マップ生成完了 ===")
        return result_df

    def _extract_top_stations(self, mesh_df: pl.DataFrame, max_stations: int = 3) -> pl.DataFrame:
        """各メッシュの最寄りN駅を抽出します。

        Args:
            mesh_df: メッシュマスターDataFrame
            max_stations: 抽出する最寄り駅数

        Returns:
            pl.DataFrame: 最寄りN駅を抽出したDataFrame
        """
        # 各メッシュについて距離順にソートし、上位N駅を抽出
        top_stations = (
            mesh_df.sort(["mesh_id", "distance_m"])
            .group_by("mesh_id")
            .agg(
                [
                    pl.col("latitude").first(),
                    pl.col("longitude").first(),
                    pl.col("city_name").first(),
                    pl.col("district_name").first(),
                    pl.col("station_name").head(max_stations),
                    pl.col("distance_m").head(max_stations),
                    pl.col("walk_minutes").head(max_stations),
                ]
            )
        )

        # リスト形式を展開（縦持ち形式に戻す）
        exploded = top_stations.explode(["station_name", "distance_m", "walk_minutes"])

        # 駅番号を付与（1, 2, 3）
        exploded = exploded.with_columns(
            pl.col("station_name").rank(method="dense").over("mesh_id").alias("station_rank")
        )

        return exploded

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
        """特徴量を生成します。

        Args:
            mesh_stations: 最寄り駅情報を含むDataFrame
            target_year: 対象年
            age_range: 築年数範囲
            area_sqm: 専有面積
            structure: 建物構造
            renovation: 改装の有無
            city_planning: 用途地域

        Returns:
            pl.DataFrame: 特徴量DataFrame
        """
        # 築年数の中央値を計算
        age_midpoint = (age_range[0] + age_range[1]) // 2
        building_year = target_year - age_midpoint

        # 時点特徴量（固定値）
        month = 6
        quarter = 2

        # 特徴量を追加
        # 不足している特徴量にはデフォルト値を設定
        features_df = mesh_stations.with_columns(
            [
                pl.lit(target_year).alias("Year"),
                pl.lit(month).alias("Month"),
                pl.lit(quarter).alias("Quarter"),
                pl.lit(area_sqm).alias("Area"),
                pl.lit(area_sqm).alias("TotalFloorArea"),  # デフォルト: Area と同じ
                pl.lit(age_midpoint).alias("Age"),
                pl.lit(building_year).alias("BuildingYear"),
                pl.lit("3LDK").alias("FloorPlan"),  # デフォルト値
                pl.lit(structure).alias("Structure"),
                pl.lit(renovation).alias("Renovation"),
                pl.lit(city_planning).alias("CityPlanning"),
                pl.lit(60.0).alias("CoverageRatio"),  # デフォルト値（%）
                pl.lit(200.0).alias("FloorAreaRatio"),  # デフォルト値（%）
                pl.col("station_name").alias("NearestStation"),
                pl.col("walk_minutes").round(0).cast(pl.Int64).alias("TimeToNearestStation"),
                pl.col("city_name").alias("Municipality"),
                pl.col("district_name").alias("DistrictName"),
            ]
        )

        # 集約統計量をマージ
        # Municipality × Year の統計量
        municipality_stats = self.stats.select(
            [
                "Municipality",
                "Year",
                "Municipality_Year_mean_price",
                "Municipality_Year_median_price",
            ]
        ).unique()

        # NearestStation × Year の統計量
        station_stats = self.stats.select(
            [
                "NearestStation",
                "Year",
                "NearestStation_Year_mean_price",
                "NearestStation_Year_median_price",
            ]
        ).unique()

        # 左結合でマージ
        features_df = features_df.join(
            municipality_stats, on=["Municipality", "Year"], how="left"
        ).join(station_stats, on=["NearestStation", "Year"], how="left")

        # 欠損値のチェック（警告のみ）
        null_counts = features_df.null_count()
        total_nulls = sum(null_counts.row(0))
        if total_nulls > 0:
            logger.warning(f"集約統計量に欠損値があります（合計: {total_nulls}件）")

        return features_df

    def _predict_and_aggregate(self, features_df: pl.DataFrame, max_stations: int) -> pl.DataFrame:
        """予測と平均化を実行します。

        Args:
            features_df: 特徴量DataFrame
            max_stations: 使用する最寄り駅数

        Returns:
            pl.DataFrame: メッシュ単位で集約された予測結果
        """
        # モデルの入力特徴量名を取得
        if hasattr(self.model, "feature_name_"):
            model_features = self.model.feature_name_
        else:
            # フォールバック: 一般的な特徴量リスト（モデル学習時と同じ順序）
            model_features = [
                "Year",
                "Area",
                "TotalFloorArea",
                "Age",
                "BuildingYear",
                "FloorPlan",
                "TimeToNearestStation",
                "NearestStation",
                "DistrictName",
                "CoverageRatio",
                "FloorAreaRatio",
                "Renovation",
                "Municipality",
                "Structure",
                "CityPlanning",
                "Month",
                "Quarter",
                "Municipality_Year_mean_price",
                "Municipality_Year_median_price",
                "NearestStation_Year_mean_price",
                "NearestStation_Year_median_price",
            ]

        # 特徴量を選択してPandasに変換
        X = features_df.select(model_features).to_pandas()

        # カテゴリカル変数をcategory型に変換
        categorical_cols = [
            "FloorPlan",
            "NearestStation",
            "DistrictName",
            "Renovation",
            "Municipality",
            "Structure",
            "CityPlanning",
        ]
        for col in categorical_cols:
            if col in X.columns:
                X[col] = X[col].astype("category")

        # 予測実行
        predictions = self.model.predict(X)

        # 予測結果を追加
        features_df = features_df.with_columns(pl.Series("predicted_price", predictions))

        # メッシュ単位で集約（駅ごとの予測値を平均）
        aggregated = features_df.group_by("mesh_id").agg(
            [
                pl.col("latitude").first(),
                pl.col("longitude").first(),
                pl.col("Municipality").first().alias("city_name"),
                pl.col("DistrictName").first().alias("district_name"),
                pl.col("predicted_price").mean().alias("predicted_price"),
                pl.col("NearestStation").head(max_stations),
                pl.col("distance_m").head(max_stations),
                pl.col("walk_minutes").head(max_stations),
                pl.col("predicted_price").alias("predicted_prices").head(max_stations),
                pl.col("station_rank").count().alias("num_stations_used"),
            ]
        )

        # 駅情報を横持ちに展開
        result_rows = []
        for row in aggregated.iter_rows(named=True):
            result_row = {
                "mesh_id": row["mesh_id"],
                "latitude": row["latitude"],
                "longitude": row["longitude"],
                "city_name": row["city_name"],
                "district_name": row["district_name"],
                "predicted_price": row["predicted_price"],
                "num_stations_used": row["num_stations_used"],
            }

            # 駅1〜3の情報を展開
            stations = row["NearestStation"]
            distances = row["distance_m"]
            walk_mins = row["walk_minutes"]
            prices = row["predicted_prices"]

            for i in range(max_stations):
                if i < len(stations):
                    result_row[f"station_{i+1}_name"] = stations[i]
                    result_row[f"station_{i+1}_distance_m"] = distances[i]
                    result_row[f"station_{i+1}_walk_minutes"] = walk_mins[i]
                    result_row[f"station_{i+1}_predicted_price"] = prices[i]
                else:
                    result_row[f"station_{i+1}_name"] = None
                    result_row[f"station_{i+1}_distance_m"] = None
                    result_row[f"station_{i+1}_walk_minutes"] = None
                    result_row[f"station_{i+1}_predicted_price"] = None

            result_rows.append(result_row)

        result_df = pl.DataFrame(result_rows)
        return result_df

    def _save_metadata(self, metadata: dict, metadata_path: str | Path) -> None:
        """メタデータをJSONで保存します。

        Args:
            metadata: メタデータ辞書
            metadata_path: 保存先パス
        """
        metadata_path = Path(metadata_path)
        metadata_path.parent.mkdir(parents=True, exist_ok=True)

        with open(metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=2)
