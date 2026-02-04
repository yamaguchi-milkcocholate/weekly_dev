#!/usr/bin/env python3
"""
坪単価相場推定モデル学習スクリプト

設計書に基づき、以下のステップを実行します:
1. データ読み込みと外れ値除去
2. 時点特徴量の追加（Year, Month, Quarter）
3. データ分割（Train/Test, GroupKFold）
4. 集約統計量の追加（Municipality × Year, NearestStation × Year）
5. LightGBMモデルの学習と交差検証
6. 最終モデルの評価と予測結果の保存

使用方法:
    python scripts/train_price_estimator.py

出力:
    outputs/feature_importance.csv - 特徴量重要度
    outputs/cv_metrics.csv - 交差検証メトリクス
    outputs/prediction_results.csv - テストデータの予測結果
"""

import logging

from pathlib import Path

from real_state_geo_core.ml.data_loader import (
    add_aggregated_features,
    add_time_features,
    create_group_kfold_split,
    load_ml_dataset,
    prepare_features,
)
from real_state_geo_core.ml.price_estimator import PriceEstimator

# プロジェクトルートの設定
project_root = Path(__file__).resolve().parent.parent

# ロギング設定
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)


def main():
    """メイン処理"""
    logging.info("=== 坪単価相場推定モデル学習開始 ===")

    # 設定
    RANDOM_STATE = 42
    DATA_PATH = project_root / "data" / "ml_dataset" / "tokyo_23_ml_dataset.csv"
    OUTPUT_DIR = project_root / "outputs"
    OUTPUT_DIR.mkdir(exist_ok=True)

    # ===== Step 1: データ読み込みと外れ値除去 =====
    logging.info("Step 1: データ読み込みと外れ値除去")
    df = load_ml_dataset(str(DATA_PATH))
    logging.info(f"データ件数: {df.height}件")

    # ===== Step 2: 時点特徴量の追加 =====
    logging.info("\nStep 2: 時点特徴量の追加")
    df = add_time_features(df, date_col="transaction_date")

    # ===== Step 3: データ分割 =====
    logging.info("\nStep 3: データ分割（GroupKFold）")
    train_df, test_df, gkf = create_group_kfold_split(df, n_splits=5, test_ratio=0.2, group_col="Municipality")

    # ===== Step 4: 集約統計量の追加 =====
    logging.info("\nStep 4: 集約統計量の追加")
    train_df = add_aggregated_features(
        train_df, train_df, target_col="tsubo_price", agg_keys=["Municipality", "NearestStation"]
    )
    test_df = add_aggregated_features(
        train_df, test_df, target_col="tsubo_price", agg_keys=["Municipality", "NearestStation"]
    )

    # ===== Step 5: 交差検証 =====
    logging.info("\n=== Step 5: GroupKFold交差検証 ===")
    estimator = PriceEstimator(random_state=RANDOM_STATE)

    cv_metrics = estimator.cross_validate(
        train_df,
        gkf,
        groups=train_df["Municipality"],
        target_col="tsubo_price",
    )

    # 交差検証メトリクスを保存
    estimator.save_cv_metrics(cv_metrics, str(OUTPUT_DIR / "cv_metrics.csv"))

    # 平均スコアを表示
    logging.info("\n交差検証平均スコア:")
    logging.info(f"  RMSE: {cv_metrics['rmse'].mean():.2f} ± {cv_metrics['rmse'].std():.2f}")
    logging.info(f"  MAE: {cv_metrics['mae'].mean():.2f} ± {cv_metrics['mae'].std():.2f}")
    logging.info(f"  MAPE: {cv_metrics['mape'].mean():.2f}% ± {cv_metrics['mape'].std():.2f}%")

    # ===== 最終モデル学習（全Trainデータ） =====
    logging.info("\n最終モデル学習中...")
    X_train, y_train = prepare_features(train_df, target_col="tsubo_price", exclude_cols=["transaction_date"])
    estimator.fit(X_train, y_train)

    # 特徴量重要度を保存
    estimator.save_feature_importance(str(OUTPUT_DIR / "feature_importance.csv"))

    # トップ10特徴量を表示
    logging.info("\n上位10特徴量:")
    top_features = estimator.get_feature_importance().head(10)
    for idx, row in top_features.iterrows():
        logging.info(f"  {idx + 1}. {row['feature_name']}: {row['importance_gain']:.2f}")

    # ===== Testデータで評価 =====
    if test_df.height > 0:
        logging.info("\nTestデータで評価中...")
        X_test, y_test = prepare_features(test_df, target_col="tsubo_price", exclude_cols=["transaction_date"])
        test_metrics = estimator.evaluate(X_test, y_test)
        logging.info(f"  RMSE: {test_metrics['rmse']:.2f}")
        logging.info(f"  MAE: {test_metrics['mae']:.2f}")
        logging.info(f"  MAPE: {test_metrics['mape']:.2f}%")

        # Testデータの予測結果を保存
        estimator.save_predictions(
            test_df,
            str(OUTPUT_DIR / "prediction_results.csv"),
            target_col="tsubo_price",
            include_actuals=True,
        )
    else:
        logging.warning("Testデータが空のため、評価をスキップします")

    logging.info("\n=== 坪単価相場推定モデル学習完了 ===")
    logging.info(f"出力ディレクトリ: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
