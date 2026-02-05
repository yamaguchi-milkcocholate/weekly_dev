#!/usr/bin/env python3
"""複数の物件条件でメッシュ坪単価マップを一括生成

このスクリプトは、築年数・面積などのバリエーションを定義し、
各条件でメッシュ坪単価マップを一括生成します。
単一条件の生成にも対応しています。
"""

import logging
from pathlib import Path

from real_state_geo_core.ml.mesh_price_estimator import MeshPriceEstimator

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    """複数の物件条件でメッシュ坪単価マップを一括生成します。"""
    # プロジェクトルートとパス設定
    project_root = Path(__file__).parent.parent
    model_path = project_root / "outputs" / "price_estimator_model.pkl"
    mesh_master_path = project_root / "data" / "processed" / "mesh_master_tokyo23_multi.csv"
    stats_path = project_root / "outputs" / "aggregated_stats_2025.csv"

    # 必須ファイルの存在確認
    if not model_path.exists():
        logger.error(f"学習済みモデルが見つかりません: {model_path}")
        logger.info("先に train_price_estimator.py を実行してモデルを作成してください。")
        return

    if not mesh_master_path.exists():
        logger.error(f"メッシュマスターが見つかりません: {mesh_master_path}")
        logger.info("先に generate_mesh_master.py を実行してメッシュマスターを作成してください。")
        return

    if not stats_path.exists():
        logger.error(f"集約統計量マスターが見つかりません: {stats_path}")
        logger.info("先に prepare_aggregated_stats_2025.py を実行してください。")
        return

    # エスティメーター初期化
    logger.info("=== MeshPriceEstimator 初期化 ===")
    estimator = MeshPriceEstimator(
        model_path=model_path,
        mesh_master_path=mesh_master_path,
        stats_path=stats_path,
    )

    # バリエーション定義
    # 単一条件の場合は1つだけ、複数条件の場合は複数定義
    variations = [
        # デフォルト条件
        {
            "age_range": (1, 5),
            "area_sqm": 70.0,
            "structure": "RC",
            "name": "age1-5_area70_RC",
        },
        # 築年数バリエーション
        {
            "age_range": (5, 10),
            "area_sqm": 70.0,
            "structure": "RC",
            "name": "age5-10_area70_RC",
        },
        {
            "age_range": (10, 15),
            "area_sqm": 70.0,
            "structure": "RC",
            "name": "age10-15_area70_RC",
        },
        {
            "age_range": (15, 20),
            "area_sqm": 70.0,
            "structure": "RC",
            "name": "age15-20_area70_RC",
        },
        # 面積バリエーション
        {
            "age_range": (1, 5),
            "area_sqm": 60.0,
            "structure": "RC",
            "name": "age1-5_area60_RC",
        },
        {
            "age_range": (1, 5),
            "area_sqm": 80.0,
            "structure": "RC",
            "name": "age1-5_area80_RC",
        },
        {
            "age_range": (1, 5),
            "area_sqm": 90.0,
            "structure": "RC",
            "name": "age1-5_area90_RC",
        },
        {
            "age_range": (1, 5),
            "area_sqm": 100.0,
            "structure": "RC",
            "name": "age1-5_area100_RC",
        },
        # 組み合わせバリエーション
        {
            "age_range": (5, 10),
            "area_sqm": 80.0,
            "structure": "RC",
            "name": "age5-10_area80_RC",
        },
        {
            "age_range": (10, 15),
            "area_sqm": 90.0,
            "structure": "RC",
            "name": "age10-15_area90_RC",
        },
    ]

    # バッチ生成実行
    logger.info(f"\n=== バッチ生成開始: {len(variations)}パターン ===")
    success_count = 0
    failed_count = 0

    for i, variation in enumerate(variations, 1):
        logger.info(f"\n[{i}/{len(variations)}] {variation['name']} の生成開始")

        try:
            output_path = project_root / "outputs" / f"mesh_price_map_2025_{variation['name']}.csv"
            metadata_path = (
                project_root / "outputs" / f"mesh_price_map_2025_{variation['name']}_metadata.json"
            )

            estimator.generate_mesh_price_map(
                target_year=2025,
                age_range=variation["age_range"],
                area_sqm=variation["area_sqm"],
                structure=variation.get("structure", "RC"),
                renovation=variation.get("renovation", "なし"),
                city_planning=variation.get("city_planning", "第一種住居地域"),
                output_path=output_path,
                metadata_path=metadata_path,
                max_stations=3,
            )

            logger.info(f"✓ {variation['name']} の生成完了")
            success_count += 1

        except Exception as e:
            logger.error(f"✗ {variation['name']} の生成失敗: {e}")
            failed_count += 1

    # サマリー表示
    logger.info("\n=== バッチ生成完了 ===")
    logger.info(f"成功: {success_count}件")
    logger.info(f"失敗: {failed_count}件")
    logger.info(f"合計: {len(variations)}件")


if __name__ == "__main__":
    main()
