"""メッシュ坪単価データローダー"""

import json
import logging

from pathlib import Path
from typing import Any

import polars as pl

logger = logging.getLogger(__name__)


class MeshPriceDataLoader:
    """メッシュ坪単価データの読み込みと管理を行うクラス"""

    def __init__(self, output_dir: str | Path) -> None:
        """
        Args:
            output_dir: メッシュ価格マップが保存されているディレクトリ
        """
        self.output_dir = Path(output_dir)
        self.available_maps: dict[str, dict[str, Any]] = {}
        self._scan_available_maps()

    def _scan_available_maps(self) -> None:
        """利用可能なメッシュ価格マップをスキャンします。"""
        pattern = "mesh_price_map_2025_*_metadata.json"
        metadata_files = list(self.output_dir.glob(pattern))

        logger.info(f"メタデータファイルを検索中: {pattern}")
        logger.info(f"見つかったファイル数: {len(metadata_files)}件")

        for metadata_path in metadata_files:
            try:
                with open(metadata_path, encoding="utf-8") as f:
                    metadata = json.load(f)

                # ファイル名からキーを抽出（例: age1-5_area70_RC）
                map_key = metadata_path.stem.replace("mesh_price_map_2025_", "").replace("_metadata", "")

                # CSVファイルパスを追加
                csv_path = metadata_path.parent / f"mesh_price_map_2025_{map_key}.csv"

                if csv_path.exists():
                    metadata["csv_path"] = str(csv_path)
                    metadata["map_key"] = map_key
                    self.available_maps[map_key] = metadata
                    logger.info(f"マップ登録: {map_key}")
                else:
                    logger.warning(f"CSVファイルが見つかりません: {csv_path}")

            except Exception as e:
                logger.error(f"メタデータ読み込みエラー: {metadata_path} - {e}")

        logger.info(f"登録されたマップ数: {len(self.available_maps)}件")

    def get_available_conditions(self) -> dict[str, list]:
        """利用可能な物件条件の一覧を取得します。

        Returns:
            dict: 築年数範囲、面積のリスト
        """
        age_ranges = set()
        areas = set()

        for metadata in self.available_maps.values():
            age_range = tuple(metadata["age_range"])
            area = metadata["area_sqm"]
            age_ranges.add(age_range)
            areas.add(area)

        return {
            "age_ranges": sorted(age_ranges),
            "areas": sorted(areas),
        }

    def get_map_key(self, age_range: tuple[int, int], area_sqm: float, structure: str = "RC") -> str | None:
        """指定された条件に対応するマップキーを取得します。

        Args:
            age_range: 築年数範囲
            area_sqm: 専有面積（平米）
            structure: 建物構造

        Returns:
            str | None: マップキー（見つからない場合はNone）
        """
        for map_key, metadata in self.available_maps.items():
            if (
                tuple(metadata["age_range"]) == age_range
                and metadata["area_sqm"] == area_sqm
                and metadata["structure"] == structure
            ):
                return map_key
        return None

    def load_mesh_price_data(self, map_key: str) -> pl.DataFrame | None:
        """指定されたマップキーのメッシュ価格データを読み込みます。

        Args:
            map_key: マップキー

        Returns:
            pl.DataFrame | None: メッシュ価格データ（見つからない場合はNone）
        """
        if map_key not in self.available_maps:
            logger.error(f"マップキーが見つかりません: {map_key}")
            return None

        csv_path = self.available_maps[map_key]["csv_path"]
        logger.info(f"データ読み込み中: {csv_path}")

        try:
            df = pl.read_csv(csv_path)
            logger.info(f"データ読み込み完了: {df.height:,}件")
            return df
        except Exception as e:
            logger.error(f"データ読み込みエラー: {csv_path} - {e}")
            return None

    def get_metadata(self, map_key: str) -> dict[str, Any] | None:
        """指定されたマップキーのメタデータを取得します。

        Args:
            map_key: マップキー

        Returns:
            dict | None: メタデータ（見つからない場合はNone）
        """
        return self.available_maps.get(map_key)

    def prepare_pydeck_data(self, df: pl.DataFrame) -> list[dict]:
        """PyDeck用のデータを準備します。

        Args:
            df: メッシュ価格データ

        Returns:
            list[dict]: PyDeck用データ
        """
        # 必要なカラムのみ選択してPandas DataFrameに変換

        def format_price(price: float) -> str:
            """価格を読みやすい形式にフォーマットします。"""
            if price >= 1e8:
                return f"{price / 1e8:.2f}億円"
            elif price >= 1e4:
                return f"{price / 1e4:.0f}万円"
            else:
                return f"{price:.0f}円"

        pydeck_df = (
            df.with_columns(
                pl.col("predicted_price").map_elements(lambda x: format_price(x)).alias("predicted_price_str")
            )
            .select(
                [
                    "mesh_id",
                    "latitude",
                    "longitude",
                    "predicted_price",
                    "predicted_price_str",
                    "city_name",
                    "district_name",
                ]
            )
            .to_pandas()
        )

        # リストに変換して返す
        return pydeck_df.to_dict("records")
