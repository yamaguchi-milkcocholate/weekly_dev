#!/usr/bin/env python3
"""train_model.py - モデル学習CLI.

特徴量データセットを読み込み、方向予測モデルの学習・評価・保存を実行します。

Usage:
    python -m daily_trade.scripts.train_model --input dataset.parquet --output model.pkl
    python -m daily_trade.scripts.train_model --config train_config.yaml
"""

import argparse
import json
import math
from pathlib import Path
from typing import Optional

import pandas as pd
import yaml

from daily_trade.model_direction import DirectionModel, ModelConfig
from daily_trade.utils.logger import AppLogger


def load_config_from_yaml(config_path: str) -> dict:
    """YAML設定ファイルを読み込み."""
    config_file = Path(config_path)
    with config_file.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_dataset(file_path: str) -> tuple[pd.DataFrame, list[str]]:
    """データセットを読み込み."""
    logger = AppLogger()
    logger.info(f"データセット読み込み: {file_path}")

    file_path = Path(file_path).resolve()

    if not file_path.exists():
        raise FileNotFoundError(f"ファイルが見つかりません: {file_path}")

    df = pd.read_parquet(file_path)
    logger.info(f"データセット形状: {df.shape}")
    logger.info(f"列: {list(df.columns)}")

    with Path.open(file_path.with_suffix(".features.txt"), "r", encoding="utf-8") as f:
        feature_columns = [line.strip() for line in f.readlines()]

    logger.info(f"特徴量数: {len(feature_columns)}")
    return df, feature_columns


def prepare_model_data(df: pd.DataFrame, feature_cols: list[str]) -> tuple[pd.DataFrame, pd.Series]:
    """モデル学習用データを準備."""
    logger = AppLogger()

    df = df.sort_values(["timestamp", "symbol"]).reset_index(drop=True)
    num_drops = df["contains_leading_nan"].sum()
    logger.info(f"先頭欠損行数: {num_drops} / {len(df)}")

    x = df.loc[~df["contains_leading_nan"], feature_cols].copy()
    y = df.loc[~df["contains_leading_nan"], "y_up"].copy()
    symbol = df.loc[~df["contains_leading_nan"], "symbol"].copy()

    # symbolをカテゴリ変数として処理
    # symbolをカテゴリ型に変換
    x["symbol"] = x["symbol"].astype("category")

    # LightGBM用にカテゴリコードに変換
    x["symbol"] = x["symbol"].cat.codes

    logger.info(f"銘柄数: {len(df['symbol'].unique())}")
    logger.info(f"銘柄一覧: {sorted(df['symbol'].unique())}")

    logger.info(f"特徴量数: {len(feature_cols)}")
    logger.info(f"サンプル数: {len(x)}")
    logger.info(f"正例率: {y.mean():.3f}")

    # 欠損値チェック
    null_counts = x.isnull().sum()
    if null_counts.any():
        logger.warning(f"特徴量欠損値: {null_counts[null_counts > 0].to_dict()}")

    return x, y, symbol


def save_evaluation_report(
    metrics: dict[str, float],
    cv_scores: dict[str, list],
    cv_symbol_df: pd.DataFrame,
    feature_importance: dict[str, float],
    output_path: str,
) -> None:
    """評価レポートをJSON形式で保存."""
    logger = AppLogger()

    # numpy型をPython標準型に変換
    def convert_numpy_types(obj):
        if hasattr(obj, "item"):
            return obj.item()
        if isinstance(obj, dict):
            return {k: convert_numpy_types(v) for k, v in obj.items()}
        if isinstance(obj, list):
            return [convert_numpy_types(item) for item in obj]
        return obj

    cv_symbol_means = cv_symbol_df.drop(columns=["fold"]).groupby("symbol").mean().to_dict(orient="index")

    report = {
        "evaluation_metrics": convert_numpy_types(metrics),
        "cross_validation": {
            "summary": {
                metric: {
                    "mean": float(pd.Series(scores).mean()),
                    "std": float(pd.Series(scores).std()),
                    "scores": [float(score) for score in scores],
                }
                for metric, scores in cv_scores.items()
            },
            "per_symbol": cv_symbol_means,
        },
        "feature_importance": convert_numpy_types(feature_importance),
        "metadata": {
            "timestamp": pd.Timestamp.now().isoformat(),
            "model_type": "LightGBM",
            "validation_method": "TimeSeriesSplit",
        },
    }

    report_path = Path(output_path).parent / f"{Path(output_path).stem}_report.json"

    with report_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)

    logger.info(f"評価レポート保存: {report_path}")


def train_model(
    input_path: str,
    output_path: str,
    model_config: Optional[ModelConfig] = None,
    cv_splits: int = 3,
    save_report: bool = True,
) -> str:
    """モデル学習メイン処理.

    Args:
        input_path: 入力データセットパス
        output_path: 出力モデルパス
        model_config: モデル設定
        cv_splits: 交差検証分割数
        save_report: 評価レポート保存フラグ
        include_symbol: 銘柄をカテゴリ変数として特徴量に含めるか

    Returns:
        出力モデルパス
    """
    logger = AppLogger()
    logger.info("=== モデル学習開始 ===")

    try:
        # 1. データセット読み込み
        df, feature_columns = load_dataset(input_path)

        # 2. モデル学習用データ準備
        x, y, symbols = prepare_model_data(df, feature_columns)

        # 3. モデル設定
        if model_config is None:
            model_config = ModelConfig(cv_splits=cv_splits)
        else:
            model_config.cv_splits = cv_splits

        model = DirectionModel(model_config)

        # 4. 交差検証
        logger.info("交差検証実行...")
        cv_scores, cv_symbol_df = model.cross_validate(x, y, symbols)

        # 5. モデル学習
        logger.info("モデル学習開始...")
        n_estimators = math.floor(pd.Series(cv_scores["best_iteration"]).median())
        model.fit(x, y, n_estimators=n_estimators)

        # 6. モデル評価
        logger.info("モデル評価...")
        metrics = model.evaluate(x, y)

        # 7. 特徴量重要度
        feature_importance = model.get_feature_importance(top_n=20)

        # 8. モデル保存
        logger.info(f"モデル保存: {output_path}")
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        model.save_model(output_path)

        # 9. 評価レポート保存
        if save_report:
            save_evaluation_report(metrics, cv_scores, cv_symbol_df, feature_importance, output_path)

        # 10. 結果サマリー
        logger.info("=== 学習結果サマリー ===")
        logger.info(f"AUC: {metrics['auc']:.3f}")
        logger.info(f"Accuracy: {metrics['accuracy']:.3f}")
        logger.info(f"CV AUC: {pd.Series(cv_scores['auc']).mean():.3f} ± {pd.Series(cv_scores['auc']).std():.3f}")

        logger.info("主要特徴量 (Top 10):")
        for i, (feature, importance) in enumerate(list(feature_importance.items())[:10], 1):
            logger.info(f"  {i:2d}. {feature}: {importance:.1f}")

        logger.info("=== モデル学習完了 ===")
        return str(output_path)

    except Exception as e:
        logger.error(f"モデル学習エラー: {e}")
        raise


def main():
    """CLI メイン処理."""
    parser = argparse.ArgumentParser(
        description="モデル学習CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # 基本的な使用方法
  python -m daily_trade.scripts.train_model \\
    --input ./data/daily_ohlcv_features.parquet \\
    --output ./models/direction_model.pkl

  # YAML設定ファイルから実行
  python -m daily_trade.scripts.train_model --config train_config.yaml

  # 交差検証分割数を指定
  python -m daily_trade.scripts.train_model \\
    --input dataset.parquet \\
    --output model.pkl \\
    --cv-splits 5
        """,
    )

    # 設定ファイル
    parser.add_argument("--config", "-c", type=str, help="YAML設定ファイルパス", required=True)

    # 入出力設定
    parser.add_argument("--input", "-i", type=str, help="入力データセットパス (.parquet)")

    parser.add_argument("--output", "-o", type=str, help="出力モデルパス (.pkl)")

    # 出力設定
    parser.add_argument("--no-report", action="store_true", help="評価レポート出力を無効化")

    parser.add_argument("--verbose", "-v", action="store_true", help="詳細ログ出力")

    args = parser.parse_args()

    # YAML設定ファイルから読み込み
    config = load_config_from_yaml(args.config)
    input_path = config.get("input_path")
    output_path = config.get("output_path")
    cv_splits = config.get("cv_splits", 3)

    # モデル設定
    model_params = config.get("model_params", {})
    model_config = ModelConfig(light_gbm_params=model_params, cv_splits=cv_splits)

    save_report = not config.get("no_report", False)

    # モデル学習実行
    model_file = train_model(
        input_path=input_path,
        output_path=output_path,
        model_config=model_config,
        cv_splits=cv_splits,
        save_report=save_report,
    )

    print(f"✅ モデル学習完了: {model_file}")


if __name__ == "__main__":
    main()
