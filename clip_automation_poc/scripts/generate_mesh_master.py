"""
東京23区メッシュマスター生成スクリプト

Usage:
    # 徒歩圏内全駅モード（デフォルト: 徒歩30分以内）
    python scripts/generate_mesh_master.py

    # 最寄駅1つのみモード
    python scripts/generate_mesh_master.py --mode single

    # 徒歩圏内全駅モード（徒歩20分以内）
    python scripts/generate_mesh_master.py --mode multi --max-walk-minutes 20
"""

import argparse
import logging

from pathlib import Path

from real_state_geo_core.data.mesh_builder import MeshMasterBuilder

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")


def main() -> None:
    """メッシュマスター生成のメイン処理"""
    # コマンドライン引数のパース
    parser = argparse.ArgumentParser(description="東京23区メッシュマスター生成")
    parser.add_argument(
        "--mode",
        type=str,
        default="multi",
        choices=["single", "multi"],
        help="駅紐付けモード: single=最寄駅1つ、multi=徒歩圏内全駅（デフォルト: multi）",
    )
    parser.add_argument(
        "--max-walk-minutes",
        type=float,
        default=30.0,
        help="最大徒歩分数（multiモードの場合のみ有効、デフォルト: 30.0）",
    )
    parser.add_argument(
        "--mesh-size",
        type=float,
        default=100.0,
        help="メッシュサイズ（メートル、デフォルト: 100.0）",
    )
    args = parser.parse_args()

    # プロジェクトルートディレクトリ
    project_root = Path(__file__).parent.parent

    # 駅データCSVのパス
    station_csv_path = project_root / "data" / "station" / "station20251211free.csv"

    # 行政区域GeoJSONディレクトリのパス（JapanCityGeoJsonから取得したファイルを配置）
    boundary_geojson_dir = project_root / "data" / "boundary"

    # 出力CSVのパス（モードによってファイル名を変更）
    if args.mode == "single":
        output_filename = "tokyo_23_mesh_master_single.csv"
    else:
        output_filename = f"tokyo_23_mesh_master_multi_{int(args.max_walk_minutes)}min.csv"
    output_path = project_root / "data" / output_filename

    # MeshMasterBuilderを初期化
    builder = MeshMasterBuilder(
        station_csv_path=station_csv_path, boundary_geojson_dir=boundary_geojson_dir, mesh_size_m=args.mesh_size
    )

    # メッシュマスターを生成
    logging.info(f"モード: {args.mode}, 最大徒歩分数: {args.max_walk_minutes}分")
    mesh_master_df = builder.build_mesh_master(
        output_path=output_path, max_walk_minutes=args.max_walk_minutes, mode=args.mode
    )

    # 結果を表示
    logging.info(f"生成されたレコード数: {mesh_master_df.height}")
    logging.info(f"カラム: {mesh_master_df.columns}")
    logging.info(f"最初の5件:\n{mesh_master_df.head()}")


if __name__ == "__main__":
    main()
