"""
東京23区メッシュマスター生成スクリプト

Usage:
    python scripts/generate_mesh_master.py
"""

import logging

from pathlib import Path

from real_state_geo_core.data.mesh_builder import MeshMasterBuilder

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main() -> None:
    """メッシュマスター生成のメイン処理"""
    # プロジェクトルートディレクトリ
    project_root = Path(__file__).parent.parent

    # 駅データCSVのパス
    station_csv_path = project_root / "data" / "station" / "station20251211free.csv"

    # 行政区域GeoJSONディレクトリのパス（JapanCityGeoJsonから取得したファイルを配置）
    boundary_geojson_dir = project_root / "data" / "boundary"

    # 出力CSVのパス
    output_path = project_root / "data" / "tokyo_23_mesh_master.csv"

    # メッシュサイズ（メートル）
    mesh_size_m = 100.0

    # MeshMasterBuilderを初期化
    builder = MeshMasterBuilder(
        station_csv_path=station_csv_path, boundary_geojson_dir=boundary_geojson_dir, mesh_size_m=mesh_size_m
    )

    # メッシュマスターを生成
    mesh_master_df = builder.build_mesh_master(output_path=output_path)

    # 結果を表示
    logging.info(f"生成されたメッシュ数: {mesh_master_df.height}")
    logging.info(f"カラム: {mesh_master_df.columns}")
    logging.info(f"最初の5件:\n{mesh_master_df.head()}")


if __name__ == "__main__":
    main()
