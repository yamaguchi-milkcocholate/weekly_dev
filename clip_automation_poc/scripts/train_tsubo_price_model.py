#!/usr/bin/env python3
"""
坪単価予測モデル学習スクリプト

設計書に基づき、以下の3ステップを実行します:
1. 構造分析 (LightGBM) - 立地・物件スペックの影響度分析
2. マクロトレンド分析 (Prophet) - 市場全体の価格推移
3. ハイブリッド予測 (Prophet + LightGBM) - 時系列交差検証と最終予測

使用方法:
    python scripts/train_tsubo_price_model.py

出力:
    outputs/feature_importance.csv - 特徴量重要度
    outputs/market_trend_prophet.csv - 市場トレンド推移
    outputs/hybrid_prediction_results.csv - ハイブリッド予測結果
    outputs/cv_metrics.csv - 交差検証メトリクス
"""

import logging

from pathlib import Path

from real_state_geo_core.ml.data_loader import create_time_series_split, load_ml_dataset, prepare_features
from real_state_geo_core.ml.hybrid_predictor import HybridPredictor
from real_state_geo_core.ml.prophet_analyzer import ProphetTrendAnalyzer
from real_state_geo_core.ml.structure_analyzer import StructureAnalyzer

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
    logging.info("=== 坪単価予測モデル学習開始 ===")

    # 設定
    RANDOM_STATE = 42
    DATA_PATH = project_root / "data" / "ml_dataset" / "tokyo_23_ml_dataset.csv"
    OUTPUT_DIR = project_root / "outputs"
    OUTPUT_DIR.mkdir(exist_ok=True)

    # ===== Step 0: データ読み込み =====
    logging.info("Step 0: データ読み込み")
    df = load_ml_dataset(str(DATA_PATH))
    logging.info(f"データ件数: {df.height}件")

    # ===== Step 0.5: データ分割 =====
    logging.info("Step 0.5: データ分割（時系列）")
    train_valid_df, test_df, tscv = create_time_series_split(df, n_splits=5, test_year=2025)

    # ===== Step 1: 構造分析（LightGBM） =====
    logging.info("\n=== Step 1: 構造分析（LightGBM） ===")
    structure_analyzer = StructureAnalyzer(random_state=RANDOM_STATE)

    # 特徴量準備（transaction_dateを除外）
    X_structure, y_structure = prepare_features(
        train_valid_df, target_col="tsubo_price", exclude_cols=["transaction_date"]
    )

    # モデル学習
    structure_analyzer.fit(X_structure, y_structure)

    # 特徴量重要度を保存
    structure_analyzer.save_feature_importance(str(OUTPUT_DIR / "feature_importance.csv"))

    # トップ10特徴量を表示
    logging.info("\n上位10特徴量:")
    top_features = structure_analyzer.get_top_features(n=10)
    for idx, row in top_features.iterrows():
        logging.info(f"  {idx + 1}. {row['feature_name']}: {row['importance_gain']:.2f} ({row['category']})")

    # ===== Step 2: マクロトレンド分析（Prophet） =====
    logging.info("\n=== Step 2: マクロトレンド分析（Prophet - 区ごと） ===")
    prophet_analyzer = ProphetTrendAnalyzer(random_state=RANDOM_STATE)

    # 区ごとにモデル学習
    prophet_analyzer.fit(
        train_valid_df,
        date_col="transaction_date",
        target_col="tsubo_price",
        municipality_col="Municipality",
    )

    # 将来12ヶ月の予測（区ごと）
    forecast_df = prophet_analyzer.forecast_future(periods=12, freq="MS")

    # 市場トレンドを保存
    prophet_analyzer.save_forecast(forecast_df, str(OUTPUT_DIR / "market_trend_prophet.csv"), include_history=True)

    # ===== Step 3: ハイブリッド予測（Prophet + LightGBM） =====
    logging.info("\n=== Step 3: ハイブリッド予測（区ごとProphet + LightGBM） ===")
    hybrid_predictor = HybridPredictor(random_state=RANDOM_STATE)

    # 時系列交差検証
    logging.info("時系列交差検証実行中...")
    cv_metrics = hybrid_predictor.cross_validate(
        train_valid_df,
        tscv,
        target_col="tsubo_price",
        date_col="transaction_date",
        municipality_col="Municipality",
    )

    # 交差検証メトリクスを保存
    hybrid_predictor.save_cv_metrics(cv_metrics, str(OUTPUT_DIR / "cv_metrics.csv"))

    # 平均スコアを表示
    logging.info("\n交差検証平均スコア:")
    logging.info(f"  RMSE: {cv_metrics['rmse'].mean():.2f} ± {cv_metrics['rmse'].std():.2f}")
    logging.info(f"  MAE: {cv_metrics['mae'].mean():.2f} ± {cv_metrics['mae'].std():.2f}")
    logging.info(f"  MAPE: {cv_metrics['mape'].mean():.2f}% ± {cv_metrics['mape'].std():.2f}%")

    # ===== 最終モデル学習（全Train/Validデータ） =====
    logging.info("\n最終モデル学習中...")
    hybrid_predictor.fit(
        train_valid_df,
        target_col="tsubo_price",
        date_col="transaction_date",
        municipality_col="Municipality",
    )

    # ===== Testデータ（2025年）で評価 =====
    if test_df.height > 0:
        logging.info("\nTestデータ（2025年）で評価中...")
        test_metrics = hybrid_predictor.evaluate(
            test_df, target_col="tsubo_price", date_col="transaction_date", municipality_col="Municipality"
        )
        logging.info(f"  RMSE: {test_metrics['rmse']:.2f}")
        logging.info(f"  MAE: {test_metrics['mae']:.2f}")
        logging.info(f"  MAPE: {test_metrics['mape']:.2f}%")

        # Testデータの予測結果を保存
        hybrid_predictor.save_predictions(
            test_df,
            str(OUTPUT_DIR / "hybrid_prediction_results.csv"),
            target_col="tsubo_price",
            date_col="transaction_date",
            municipality_col="Municipality",
            include_actuals=True,
        )
    else:
        logging.warning("Testデータが空のため、評価をスキップします")

    logging.info("\n=== 坪単価予測モデル学習完了 ===")
    logging.info(f"出力ディレクトリ: {OUTPUT_DIR}")


if __name__ == "__main__":
    main()
