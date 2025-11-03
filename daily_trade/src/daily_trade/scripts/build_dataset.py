#!/usr/bin/env python3
"""build_dataset.py - データセット構築CLI.

データ取得から特徴量生成、ターゲット作成までの全パイプラインを実行し、
機械学習用データセットを構築します。

Usage:
    python -m daily_trade.scripts.build_dataset --config config.yaml
    python -m daily_trade.scripts.build_dataset --symbols AAPL MSFT --start 2020-01-01 --end 2025-01-01
"""

import argparse
from datetime import datetime
from pathlib import Path
import sys
from typing import Optional

import yaml
import yfinance as yf

from daily_trade.data.feature_builder import FeatureBuilder, FeatureConfig
from daily_trade.data.loader import DataLoader, LoadConfig
from daily_trade.data.preprocessor import PreprocessConfig, Preprocessor
from daily_trade.target_generator import TargetConfig, TargetGenerator
from daily_trade.utils.logger import AppLogger


def load_symbols_config(config_path: Optional[str] = None) -> dict:
    """銘柄設定ファイルを読み込み.

    Args:
        config_path: 設定ファイルパス（指定なしの場合はデフォルトパス）

    Returns:
        銘柄設定辞書
    """
    if config_path is None:
        # プロジェクトルートからの相対パス
        project_root = Path(__file__).parent.parent.parent.parent
        config_path = project_root / "config" / "symbols.yaml"

    config_file = Path(config_path)
    if not config_file.exists():
        raise FileNotFoundError(f"銘柄設定ファイルが見つかりません: {config_path}")

    with config_file.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def get_symbols_from_categories(categories: list[str], remove_duplicates: bool = True) -> list[str]:
    """複数のカテゴリから銘柄リストを取得・統合.

    Args:
        categories: 銘柄カテゴリのリスト
        remove_duplicates: 重複銘柄を除去するかどうか

    Returns:
        統合された銘柄コードリスト
    """
    logger = AppLogger()
    all_symbols = []
    category_details = {}

    # 各カテゴリから銘柄を取得
    for category in categories:
        symbols = get_predefined_symbols(category)
        all_symbols.extend(symbols)
        category_details[category] = len(symbols)
        logger.info(f"カテゴリ '{category}' から {len(symbols)} 銘柄を取得")

    # 重複除去
    if remove_duplicates:
        unique_symbols = list(dict.fromkeys(all_symbols))  # 順序を保持しつつ重複除去
        duplicate_count = len(all_symbols) - len(unique_symbols)
        if duplicate_count > 0:
            logger.info(f"重複銘柄 {duplicate_count} 個を除去")
        all_symbols = unique_symbols

    logger.info(f"最終銘柄数: {len(all_symbols)}")

    # カテゴリ別の詳細をログ出力
    for category, count in category_details.items():
        logger.info(f"  {category}: {count}銘柄")

    return all_symbols


def get_predefined_symbols(category: str = "popular", include_details: bool = False) -> list[str] | dict:
    """事前定義された銘柄リストを取得.

    Args:
        category: 銘柄カテゴリ
            - "popular": 人気米国株 (FAANG + 主要銘柄)
            - "dow30": ダウ平均構成銘柄 (代表的な30銘柄)
            - "sp500_tech": S&P500テクノロジーセクター主要銘柄
            - "etf": 主要ETF
            - "jp_major": 日本主要銘柄
        include_details: 企業名とセクター情報も含めて返すかどうか

    Returns:
        銘柄コードリスト または 詳細情報付き辞書
    """
    try:
        symbols_config = load_symbols_config()
        category_data = symbols_config["symbol_categories"].get(category)

        if not category_data:
            # フォールバック: 人気銘柄を返す
            category_data = symbols_config["symbol_categories"]["popular"]

        if include_details:
            return {"description": category_data["description"], "symbols": category_data["symbols"]}
        return [item["symbol"] for item in category_data["symbols"]]

    except Exception as e:
        logger = AppLogger()
        logger.error(f"銘柄設定ファイル読み込みエラー: {e}")

        # フォールバック: ハードコードされた人気銘柄
        fallback_symbols = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "NFLX", "V", "JPM"]

        if include_details:
            return {
                "description": "フォールバック: 主要米国株",
                "symbols": [{"symbol": s, "name": "N/A", "sector": "N/A"} for s in fallback_symbols],
            }
        return fallback_symbols


def fetch_symbols_from_yfinance(tickers: list[str], validate: bool = True) -> list[str]:
    """yfinanceから銘柄情報を取得して有効性を検証.

    Args:
        tickers: 検証対象の銘柄コードリスト
        validate: 銘柄の有効性を検証するかどうか

    Returns:
        有効な銘柄コードリスト
    """
    if not validate:
        return tickers

    logger = AppLogger()
    logger.info(f"銘柄有効性検証開始: {len(tickers)}銘柄")

    valid_symbols = []

    for ticker in tickers:
        try:
            # yfinanceで銘柄情報を取得
            stock = yf.Ticker(ticker)
            info = stock.info

            # 基本情報が取得できるかチェック
            if info and "symbol" in info:
                valid_symbols.append(ticker)
                logger.info(f"✅ {ticker}: {info.get('shortName', 'N/A')}")
            else:
                logger.warning(f"❌ {ticker}: 銘柄情報取得失敗")

        except Exception as e:
            logger.warning(f"❌ {ticker}: エラー - {str(e)[:50]}")
            continue

    logger.info(f"有効銘柄数: {len(valid_symbols)}/{len(tickers)}")
    return valid_symbols


def list_available_symbol_categories() -> None:
    """利用可能な銘柄カテゴリを表示."""
    try:
        symbols_config = load_symbols_config()
        categories = symbols_config["symbol_categories"]

        print("📋 利用可能な銘柄カテゴリ:")
        for key, category_data in categories.items():
            description = category_data["description"]
            symbols = [item["symbol"] for item in category_data["symbols"]]
            count = len(symbols)

            print(f"  {key:12}: {description} - {count}銘柄")

            # 最初の10銘柄を表示（企業名付き）
            display_symbols = []
            for item in category_data["symbols"][:10]:
                symbol = item["symbol"]
                name = item["name"]
                # 企業名が長い場合は短縮
                if len(name) > 25:
                    short_name = name[:22] + "..."
                else:
                    short_name = name
                display_symbols.append(f"{symbol}({short_name})")

            display_text = " ".join(display_symbols)
            if len(symbols) > 10:
                display_text += " ..."

            print(f"               {display_text}")
            print()

    except Exception as e:
        print(f"❌ 設定ファイル読み込みエラー: {e}")
        print("デフォルトカテゴリを表示します...")

        # フォールバック表示
        fallback_categories = {
            "popular": "人気米国株 (FAANG + 主要銘柄) - 10銘柄",
            "dow30": "ダウ平均構成銘柄 - 30銘柄",
            "sp500_tech": "S&P500テクノロジーセクター主要銘柄 - 20銘柄",
            "etf": "主要ETF - 15銘柄",
            "jp_major": "日本主要銘柄 - 15銘柄",
        }

        print("📋 利用可能な銘柄カテゴリ:")
        for key, description in fallback_categories.items():
            symbols = get_predefined_symbols(key)
            print(f"  {key:12}: {description}")
            print(f"               {' '.join(symbols[:10])}" + (" ..." if len(symbols) > 10 else ""))
            print()


def load_config_from_yaml(config_path: str) -> dict:
    """YAML設定ファイルを読み込み."""
    config_file = Path(config_path)
    with config_file.open(encoding="utf-8") as f:
        return yaml.safe_load(f)


def create_output_path(base_dir: str = "./data", filename: str = "daily_ohlcv_features.parquet") -> Path:
    """出力パスを作成."""
    output_dir = Path(base_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    return output_dir / filename


def _log_dataset_stats(logger: AppLogger, final_data) -> None:
    """データセット統計をログ出力."""
    logger.info("6. データセット統計:")
    logger.info(f"  総レコード数: {len(final_data):,}")
    logger.info(f"  銘柄数: {final_data['symbol'].nunique()}")
    logger.info(f"  期間: {final_data['timestamp'].min()} - {final_data['timestamp'].max()}")
    feature_cols = [col for col in final_data.columns if col not in ["symbol", "timestamp", "next_ret", "y_up"]]
    logger.info(f"  特徴量数: {len(feature_cols)}")
    logger.info(f"  上昇率: {final_data['y_up'].mean():.1%}")


def _log_symbol_stats(logger: AppLogger, final_data) -> None:
    """銘柄別統計をログ出力."""
    symbol_stats = final_data.groupby("symbol").agg({"y_up": ["count", "mean"], "next_ret": ["mean", "std"]}).round(3)
    logger.info("7. 銘柄別統計:")
    for symbol in symbol_stats.index:
        count = symbol_stats.loc[symbol, ("y_up", "count")]
        up_rate = symbol_stats.loc[symbol, ("y_up", "mean")]
        mean_ret = symbol_stats.loc[symbol, ("next_ret", "mean")]
        std_ret = symbol_stats.loc[symbol, ("next_ret", "std")]
        logger.info(f"  {symbol}: {count}日, 上昇率={up_rate:.1%}, リターン={mean_ret:.3f}±{std_ret:.3f}")


def build_dataset(
    symbols: list[str],
    start_date: str,
    end_date: str,
    interval: str = "1d",
    margin_pct: float = 0.01,
    output_path: Optional[str] = None,
    winsorize_pct: float = 0.01,
    min_trading_days: int = 100,
) -> str:
    """データセット構築メイン処理.

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
    logger.info(f"期間: {start_date} - {end_date}")
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
        feature_data, feature_columns = feature_builder.build(clean_data)
        logger.info(f"Feature data: {feature_data.shape}, columns: {len(feature_columns)}")

        # 4. ターゲット生成
        logger.info("4. ターゲット生成開始...")
        target_config = TargetConfig(margin_pct=margin_pct)
        target_generator = TargetGenerator(target_config)
        final_data = target_generator.make_targets(feature_data)
        logger.info(f"Final data: {final_data.shape}")

        # 5. データ保存
        logger.info("5. データ保存開始...")
        final_data.to_parquet(output_path, index=False)
        with Path.open(output_path.with_suffix(".features.txt"), "w", encoding="utf-8") as f:
            for col in feature_columns:
                f.write(f"{col}\n")
        logger.info(f"特徴量リスト保存: {output_path.with_suffix('.features.txt')}")
        logger.info(f"データセット保存完了: {output_path}")

        # 6. 統計サマリー
        _log_dataset_stats(logger, final_data)

        # 7. 銘柄別統計
        _log_symbol_stats(logger, final_data)

        logger.info("=== データセット構築完了 ===")
        return str(output_path)

    except Exception as e:
        logger.error(f"データセット構築エラー: {e}")
        raise


def main():
    """CLI メイン処理."""
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

  # 事前定義銘柄カテゴリを使用
  python -m daily_trade.scripts.build_dataset \\
    --symbol-category popular \\
    --start 2020-01-01 \\
    --end 2025-01-01

  # 複数カテゴリを組み合わせ
  python -m daily_trade.scripts.build_dataset \\
    --symbol-category popular etf \\
    --start 2020-01-01 \\
    --end 2025-01-01

  # 銘柄カテゴリ一覧を表示
  python -m daily_trade.scripts.build_dataset --list-categories

  # 銘柄検証をスキップして高速実行
  python -m daily_trade.scripts.build_dataset \\
    --symbols AAPL MSFT GOOGL \\
    --no-validate \\
    --start 2020-01-01 \\
    --end 2025-01-01
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

    parser.add_argument(
        "--symbol-category",
        type=str,
        nargs="+",
        choices=["popular", "dow30", "sp500_tech", "etf", "jp_major"],
        help="事前定義された銘柄カテゴリから選択 (複数指定可能、--list-categories で一覧表示)",
    )

    parser.add_argument(
        "--list-categories",
        action="store_true",
        help="利用可能な銘柄カテゴリを表示して終了",
    )

    parser.add_argument(
        "--validate-symbols",
        action="store_true",
        default=True,
        help="yfinanceで銘柄の有効性を検証 (デフォルト: True)",
    )

    parser.add_argument(
        "--no-validate",
        action="store_true",
        help="銘柄の有効性検証をスキップ",
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

    parser.add_argument("--min-days", type=int, default=100, help="最小取引日数 (デフォルト: 100)")

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
        # --list-categories オプションの処理
        if args.list_categories:
            list_available_symbol_categories()
            return

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
            validate_symbols = config.get("validate_symbols", True)
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
            validate_symbols = args.validate_symbols and not args.no_validate

        # 銘柄リストの決定
        if args.symbol_category:
            # 事前定義カテゴリから取得
            if len(args.symbol_category) == 1:
                # 単一カテゴリ
                symbols = get_predefined_symbols(args.symbol_category[0])
                print(f"📋 銘柄カテゴリ '{args.symbol_category[0]}' から {len(symbols)} 銘柄を選択")
            else:
                # 複数カテゴリ
                symbols = get_symbols_from_categories(args.symbol_category)
                category_list = ", ".join(args.symbol_category)
                print(f"📋 銘柄カテゴリ [{category_list}] から {len(symbols)} 銘柄を選択")
                print(f"   (重複除去後の最終銘柄数: {len(symbols)})")
        elif not symbols:
            parser.error("銘柄コード (--symbols) または銘柄カテゴリ (--symbol-category) は必須です")

        # 銘柄の有効性検証
        if validate_symbols:
            symbols = fetch_symbols_from_yfinance(symbols, validate=True)
            if not symbols:
                parser.error("有効な銘柄が見つかりませんでした")

        # 必須パラメータチェック
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
