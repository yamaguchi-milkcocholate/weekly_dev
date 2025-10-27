#!/usr/bin/env python3
"""
build_dataset.py - データセット構築CLI

データ取得から特徴量生成、ターゲット作成までの全パイプラインを実行し、
機械学習用データセットを構築します。

Usage:
    python -m daily_trade.scripts.build_dataset --config config.yaml
    python -m daily_trade.scripts.build_dataset --symbols AAPL MSFT --start 2020-01-01 --end 2025-01-01
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path
from typing import List, Optional

import yaml

from daily_trade.data.feature_builder import FeatureBuilder, FeatureConfig
from daily_trade.data.loader import DataLoader, LoadConfig
from daily_trade.data.preprocessor import PreprocessConfig, Preprocessor
from daily_trade.target_generator import TargetConfig, TargetGenerator
from daily_trade.utils.logger import AppLogger


def load_config_from_yaml(config_path: str) -> dict:
    """YAML設定ファイルを読み込み"""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_output_path(
    base_dir: str = "./data", filename: str = "daily_ohlcv_features.parquet"
) -> Path:
    """出力パスを作成"""
    output_dir = Path(base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / filename


def build_dataset(
    symbols: List[str],
    start_date: str,
    end_date: str,
    interval: str = "1d",
    margin_pct: float = 0.01,
    output_path: Optional[str] = None,
    winsorize_pct: float = 0.01,
    min_trading_days: int = 100,
) -> str:
    """
    データセット構築メイン処理

    Args:
        symbols: 銘柄コードリスト
        start_date: 開始日 (YYYY-MM-DD)
        end_date: 終了日 (YYYY-MM-DD)
        interval: データ間隔 (1d, 1wk, 1mo)
        margin_pct: 上昇判定マージン (0.01 = 1%)
        output_path: 出力ファイルパス
        winsorize_pct: Winsorize処理の閾値
        min_trading_days: 最小取引日数

    Returns:
        出力ファイルパス
    """
    logger = AppLogger()
    logger.info("=== データセット構築開始 ===")
    logger.info(f"銘柄: {symbols}")
    logger.info(f"期間: {start_date} ～ {end_date}")
    logger.info(f"マージン: {margin_pct:.1%}")

    # 出力パス決定
    if output_path is None:
        output_path = create_output_path()
    else:
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        # 1. データ取得
        logger.info("1. データ取得開始...")
        loader_config = LoadConfig(start=start_date, end=end_date, interval=interval)
        loader = DataLoader(loader_config)
        raw_data = loader.load_ohlcv(symbols)
        logger.info(f"Raw data: {raw_data.shape}")

        # 2. 前処理
        logger.info("2. 前処理開始...")
        preprocess_config = PreprocessConfig(
            winsorize_limits=(winsorize_pct, 1.0 - winsorize_pct),
            min_trading_days=min_trading_days,
        )
        preprocessor = Preprocessor(preprocess_config)
        clean_data = preprocessor.clean(raw_data)
        logger.info(f"Clean data: {clean_data.shape}")

        # 3. 特徴量生成
        logger.info("3. 特徴量生成開始...")
        feature_config = FeatureConfig()
        feature_builder = FeatureBuilder(feature_config)
        feature_data = feature_builder.build(clean_data)
        logger.info(
            f"Feature data: {feature_data.shape}, columns: {len(feature_data.columns)}"
        )

        # 4. ターゲット生成
        logger.info("4. ターゲット生成開始...")
        target_config = TargetConfig(margin_pct=margin_pct)
        target_generator = TargetGenerator(target_config)
        final_data = target_generator.make_targets(feature_data)
        logger.info(f"Final data: {final_data.shape}")

        # 5. データ保存
        logger.info("5. データ保存開始...")
        final_data.to_parquet(output_path, index=False)
        logger.info(f"データセット保存完了: {output_path}")

        # 6. 統計サマリー
        logger.info("6. データセット統計:")
        logger.info(f"  総レコード数: {len(final_data):,}")
        logger.info(f"  銘柄数: {final_data['symbol'].nunique()}")
        logger.info(
            f"  期間: {final_data['timestamp'].min()} ～ {final_data['timestamp'].max()}"
        )
        logger.info(
            f"  特徴量数: {len([col for col in final_data.columns if col not in ['symbol', 'timestamp', 'next_ret', 'y_up']])}"
        )
        logger.info(f"  上昇率: {final_data['y_up'].mean():.1%}")

        # 銘柄別統計
        symbol_stats = (
            final_data.groupby("symbol")
            .agg({"y_up": ["count", "mean"], "next_ret": ["mean", "std"]})
            .round(3)
        )
        logger.info("7. 銘柄別統計:")
        for symbol in symbol_stats.index:
            count = symbol_stats.loc[symbol, ("y_up", "count")]
            up_rate = symbol_stats.loc[symbol, ("y_up", "mean")]
            mean_ret = symbol_stats.loc[symbol, ("next_ret", "mean")]
            std_ret = symbol_stats.loc[symbol, ("next_ret", "std")]
            logger.info(
                f"  {symbol}: {count}日, 上昇率={up_rate:.1%}, リターン={mean_ret:.3f}±{std_ret:.3f}"
            )

        logger.info("=== データセット構築完了 ===")
        return str(output_path)

    except Exception as e:
        logger.error(f"データセット構築エラー: {e}")
        raise


def main():
    """CLI メイン処理"""
    parser = argparse.ArgumentParser(
        description="データセット構築CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # YAML設定ファイルから実行
  python -m daily_trade.scripts.build_dataset --config config.yaml
  
  # CLI引数で直接指定
  python -m daily_trade.scripts.build_dataset \\
    --symbols AAPL MSFT GOOGL \\
    --start 2020-01-01 \\
    --end 2025-01-01 \\
    --margin 0.01 \\
    --output ./data/dataset.parquet
        """,
    )

    # 設定ファイル
    parser.add_argument("--config", "-c", type=str, help="YAML設定ファイルパス")

    # データ取得設定
    parser.add_argument(
        "--symbols",
        "-s",
        type=str,
        nargs="+",
        help="銘柄コードリスト (例: AAPL MSFT GOOGL)",
    )

    parser.add_argument("--start", type=str, help="開始日 (YYYY-MM-DD)")

    parser.add_argument("--end", type=str, help="終了日 (YYYY-MM-DD)")

    parser.add_argument(
        "--interval",
        type=str,
        default="1d",
        choices=["1d", "1wk", "1mo"],
        help="データ間隔 (デフォルト: 1d)",
    )

    # ターゲット設定
    parser.add_argument(
        "--margin",
        type=float,
        default=0.01,
        help="上昇判定マージン (デフォルト: 0.01 = 1%%)",
    )

    # 前処理設定
    parser.add_argument(
        "--winsorize",
        type=float,
        default=0.01,
        help="Winsorize閾値 (デフォルト: 0.01 = 1%%)",
    )

    parser.add_argument(
        "--min-days", type=int, default=100, help="最小取引日数 (デフォルト: 100)"
    )

    # 出力設定
    parser.add_argument(
        "--output",
        "-o",
        type=str,
        help="出力ファイルパス (デフォルト: ./data/daily_ohlcv_features.parquet)",
    )

    # ログ設定
    parser.add_argument("--verbose", "-v", action="store_true", help="詳細ログ出力")

    args = parser.parse_args()

    try:
        # 設定読み込み
        if args.config:
            # YAML設定ファイルから読み込み
            config = load_config_from_yaml(args.config)
            symbols = config.get("symbols", [])
            start_date = config.get("start_date")
            end_date = config.get("end_date")
            interval = config.get("interval", "1d")
            margin_pct = config.get("margin_pct", 0.01)
            output_path = config.get("output_path")
            winsorize_pct = config.get("winsorize_pct", 0.01)
            min_trading_days = config.get("min_trading_days", 100)
        else:
            # CLI引数から読み込み
            symbols = args.symbols
            start_date = args.start
            end_date = args.end
            interval = args.interval
            margin_pct = args.margin
            output_path = args.output
            winsorize_pct = args.winsorize
            min_trading_days = args.min_days

        # 必須パラメータチェック
        if not symbols:
            parser.error("銘柄コード (--symbols) は必須です")
        if not start_date:
            parser.error("開始日 (--start) は必須です")
        if not end_date:
            parser.error("終了日 (--end) は必須です")

        # 日付フォーマットチェック
        try:
            datetime.strptime(start_date, "%Y-%m-%d")
            datetime.strptime(end_date, "%Y-%m-%d")
        except ValueError as e:
            parser.error(f"日付フォーマットエラー: {e}")

        # データセット構築実行
        output_file = build_dataset(
            symbols=symbols,
            start_date=start_date,
            end_date=end_date,
            interval=interval,
            margin_pct=margin_pct,
            output_path=output_path,
            winsorize_pct=winsorize_pct,
            min_trading_days=min_trading_days,
        )

        print(f"✅ データセット構築完了: {output_file}")

    except Exception as e:
        print(f"❌ エラー: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
