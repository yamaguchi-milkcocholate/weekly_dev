"""
機械学習用データセット作成スクリプト

ローカルCSVファイルから不動産取引データを読み込み、坪単価予測のための
機械学習用データセットをCSV形式で出力します。

Data Source:
    data/Tokyo_20053_20253_utf8.csv (2005-2025年の東京不動産取引データ)

Usage:
    # デフォルト設定で実行（2023-2024年、東京23区全体）
    python scripts/create_ml_dataset.py

    # 期間と出力先をカスタマイズ
    python scripts/create_ml_dataset.py --start-year 2020 --end-year 2024 \\
        --output-path data/ml_dataset/tokyo_2020-2024.csv

    # 特定区のみ取得（例: 千代田区 + 港区）
    python scripts/create_ml_dataset.py --city-codes "13101,13103"
"""

import argparse
import logging
import re
import sys

from pathlib import Path

import polars as pl

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 東京23区の市区町村コード一覧
TOKYO_23_CITY_CODES = [
    "13101",  # 千代田区
    "13102",  # 中央区
    "13103",  # 港区
    "13104",  # 新宿区
    "13105",  # 文京区
    "13106",  # 台東区
    "13107",  # 墨田区
    "13108",  # 江東区
    "13109",  # 品川区
    "13110",  # 目黒区
    "13111",  # 大田区
    "13112",  # 世田谷区
    "13113",  # 渋谷区
    "13114",  # 中野区
    "13115",  # 杉並区
    "13116",  # 豊島区
    "13117",  # 北区
    "13118",  # 荒川区
    "13119",  # 板橋区
    "13120",  # 練馬区
    "13121",  # 足立区
    "13122",  # 葛飾区
    "13123",  # 江戸川区
]


def parse_period_year(period_str: str) -> int | None:
    """
    Period文字列から年を抽出します。

    Args:
        period_str (str): 取引時期の文字列（例: "2024年第1四半期"）

    Returns:
        int | None: 抽出された年（例: 2024）。パース失敗時はNone。
    """
    if not period_str or not isinstance(period_str, str):
        return None
    match = re.search(r"(\d{4})年", period_str)
    if match:
        return int(match.group(1))
    return None


def convert_building_year(year_str: str) -> int | None:
    """
    建築年を和暦から西暦に変換します。

    Args:
        year_str (str): 建築年の文字列（例: "昭和50年", "平成10年", "2010", "2010年"）

    Returns:
        int | None: 西暦年（例: 1975, 1998, 2010）。変換失敗時はNone。
    """
    if not year_str or year_str == "":
        return None

    year_str = str(year_str).strip()

    # 西暦+「年」の形式（例: "2010年"）
    match = re.match(r"^(\d{4})年?$", year_str)
    if match:
        return int(match.group(1))

    # 和暦の変換（例: "昭和50年", "平成10年", "令和3年"）
    match = re.search(r"(昭和|平成|令和)(\d+)年?", year_str)
    if match:
        era, year = match.groups()
        year = int(year)
        if era == "昭和":
            return 1925 + year
        elif era == "平成":
            return 1988 + year
        elif era == "令和":
            return 2018 + year

    return None


def load_from_csv(csv_path: Path, start_year: int, end_year: int, city_codes: list[str]) -> pl.DataFrame | None:
    """
    ローカルCSVファイルから不動産取引データを読み込み、フィルタリングします。

    Args:
        csv_path (Path): CSVファイルのパス
        start_year (int): 開始年
        end_year (int): 終了年
        city_codes (list[str]): 市区町村コードのリスト

    Returns:
        pl.DataFrame | None: フィルタリング済みDataFrame。失敗時はNone。
    """
    # 1. ファイル存在確認
    if not csv_path.exists():
        logging.error(f"CSVファイルが見つかりません: {csv_path}")
        return None

    # 2. CSV読み込み
    try:
        # 型推論の問題を避けるため、数値カラムを明示的に文字列として読み込む
        df = pl.read_csv(
            csv_path,
            encoding="utf-8",
            infer_schema_length=0,  # すべてのカラムを文字列として読み込む
        )
        logging.info(f"CSVファイルを読み込みました: {csv_path} ({df.height}件)")
    except Exception as e:
        logging.error(f"CSVファイルの読み込みに失敗しました: {e}")
        return None

    # 3. 必須カラムの存在確認
    required_columns = [
        "種類",
        "市区町村コード",
        "取引価格（総額）",
        "面積（㎡）",
        "取引時期",
        "最寄駅：名称",
        "最寄駅：距離（分）",
    ]
    missing_columns = [col for col in required_columns if col not in df.columns]
    if missing_columns:
        logging.error(f"必須カラムが不足しています: {missing_columns}")
        return None

    # 4. カラム名を英語に変換（APIレスポンスと統一）
    column_mapping = {
        "種類": "Type",
        "価格情報区分": "PriceCategory",
        "市区町村コード": "MunicipalityCode",
        "都道府県名": "Prefecture",
        "市区町村名": "Municipality",
        "地区名": "DistrictName",
        "最寄駅：名称": "NearestStation",
        "最寄駅：距離（分）": "TimeToNearestStation",
        "取引価格（総額）": "TradePrice",
        "間取り": "FloorPlan",
        "面積（㎡）": "Area",
        "建築年": "BuildingYear",
        "建物の構造": "Structure",
        "用途": "Use",
        "今後の利用目的": "FuturePurpose",
        "都市計画": "CityPlanning",
        "建ぺい率（％）": "CoverageRatio",
        "容積率（％）": "FloorAreaRatio",
        "取引時期": "Period",
        "改装": "Renovation",
        "取引の事情等": "Remarks",
    }
    df = df.rename(column_mapping)

    # 5. 数値カラムの型変換（カンマ除去 → float）
    for col_name in ["TradePrice", "Area", "CoverageRatio", "FloorAreaRatio"]:
        if col_name in df.columns:
            df = df.with_columns(pl.col(col_name).cast(pl.Utf8).str.replace_all(",", "").cast(pl.Float64, strict=False))

    # 6. TimeToNearestStation を整数型に変換
    if "TimeToNearestStation" in df.columns:
        df = df.with_columns(
            pl.col("TimeToNearestStation").cast(pl.Utf8).str.replace_all(",", "").cast(pl.Int64, strict=False)
        )

    # 7. Period から Year を抽出（フィルタリング用）
    df = df.with_columns(pl.col("Period").map_elements(parse_period_year, return_dtype=pl.Int64).alias("YearExtracted"))

    # 8. 年度でフィルタリング
    df = df.filter((pl.col("YearExtracted") >= start_year) & (pl.col("YearExtracted") <= end_year))
    logging.info(f"年度フィルタリング後（{start_year}〜{end_year}年）: {df.height}件")

    # 9. 市区町村コードでフィルタリング
    df = df.filter(pl.col("MunicipalityCode").is_in(city_codes))
    logging.info(f"市区町村コードフィルタリング後: {df.height}件")

    # 10. TotalFloorArea を Area と同じ値で設定（マンションの場合）
    if "Area" in df.columns:
        df = df.with_columns(pl.col("Area").alias("TotalFloorArea"))

    # 11. データ件数チェック
    if df.height == 0:
        logging.warning("フィルタリング後のデータが0件です")
        return None

    return df


def filter_data(df: pl.DataFrame) -> pl.DataFrame:
    """
    データをフィルタリングします。

    - Type == "中古マンション等" のみ
    - TradePrice, Area が null でない行のみ

    Args:
        df (pl.DataFrame): 元のDataFrame

    Returns:
        pl.DataFrame: フィルタリング後のDataFrame

    Raises:
        SystemExit: 必須カラムが存在しない場合、またはフィルタリング後のデータが0件の場合
    """
    # 必須カラムの存在確認
    required_cols = ["TradePrice", "Area", "Type"]
    missing_cols = [col for col in required_cols if col not in df.columns]
    if missing_cols:
        logging.error(f"必須カラムが不足しています: {missing_cols}")
        sys.exit(1)

    logging.info(f"フィルタリング前: {df.height}件")

    # Type == "中古マンション等" のみ
    df = df.filter(pl.col("Type") == "中古マンション等")
    logging.info(f"Type='中古マンション等' フィルタリング後: {df.height}件")

    # 必須カラムのnull除去
    df = df.filter((pl.col("TradePrice").is_not_null()) & (pl.col("Area").is_not_null()))
    logging.info(f"TradePrice, Area のnull除去後: {df.height}件")

    if df.height == 0:
        logging.error("フィルタリング後のデータが0件です。Type='中古マンション等' のデータが存在しません。")
        sys.exit(1)

    return df


def engineer_features(df: pl.DataFrame) -> pl.DataFrame:
    """
    特徴量エンジニアリングを実行します。

    - 坪単価算出（tsubo_price）
    - Year抽出（Period文字列から）
    - 建築年の和暦→西暦変換
    - 築年数算出（Age = Year - BuildingYear）
    - transaction_date生成（Year-01-01）

    Args:
        df (pl.DataFrame): フィルタリング済みDataFrame

    Returns:
        pl.DataFrame: 特徴量エンジニアリング後のDataFrame
    """
    logging.info("特徴量エンジニアリングを開始")

    # 坪単価算出: UnitPrice が null の場合、TradePrice / (Area * 0.3025) で算出
    if "UnitPrice" in df.columns:
        df = df.with_columns(
            pl.when(pl.col("UnitPrice").is_null())
            .then(pl.col("TradePrice") / (pl.col("Area") * 0.3025))
            .otherwise(pl.col("UnitPrice"))
            .alias("tsubo_price")
        )
    else:
        df = df.with_columns((pl.col("TradePrice") / (pl.col("Area") * 0.3025)).alias("tsubo_price"))

    # Period から Year を抽出
    df = df.with_columns(pl.col("Period").map_elements(parse_period_year, return_dtype=pl.Int64).alias("Year"))

    # BuildingYear の和暦→西暦変換
    if "BuildingYear" in df.columns:
        df = df.with_columns(
            pl.col("BuildingYear")
            .map_elements(convert_building_year, return_dtype=pl.Int64)
            .alias("BuildingYear_clean")
        )

        # 築年数算出: Age = Year - BuildingYear
        df = df.with_columns((pl.col("Year") - pl.col("BuildingYear_clean")).alias("Age"))

        # BuildingYear を西暦に上書き
        df = df.with_columns(pl.col("BuildingYear_clean").alias("BuildingYear")).drop("BuildingYear_clean")
    else:
        # BuildingYear カラムが存在しない場合は Age を null にする
        df = df.with_columns(pl.lit(None, dtype=pl.Int64).alias("Age"))

    # transaction_date 生成（Year-01-01）
    df = df.with_columns(pl.datetime(pl.col("Year"), 1, 1).alias("transaction_date"))

    logging.info("特徴量エンジニアリング完了")

    return df


def validate_data(df: pl.DataFrame) -> None:
    """
    データを検証し、統計情報をログ出力します。

    - レコード数チェック
    - 欠損率計算・ログ出力
    - 時系列ソート確認

    Args:
        df (pl.DataFrame): 検証対象のDataFrame
    """
    logging.info("=" * 60)
    logging.info("データセット統計情報")
    logging.info("=" * 60)

    # レコード数チェック
    if df.height < 100:
        logging.warning(f"レコード数が少ないです: {df.height}件（機械学習には最低100件以上推奨）")
    else:
        logging.info(f"レコード数: {df.height}件")

    # カラム数
    logging.info(f"カラム数: {len(df.columns)}")

    # 時系列範囲
    if "transaction_date" in df.columns:
        min_date = df["transaction_date"].min()
        max_date = df["transaction_date"].max()
        logging.info(f"取引期間: {min_date} 〜 {max_date}")

    # 欠損率計算
    logging.info("\nカラム別欠損率:")
    null_counts = df.null_count()
    for col in df.columns:
        null_count = null_counts[col][0]
        rate = (null_count / df.height) * 100
        logging.info(f"  {col}: {rate:.2f}%")

    # 目的変数の統計
    if "tsubo_price" in df.columns:
        logging.info("\n目的変数（tsubo_price）の統計:")
        logging.info(f"  平均: {df['tsubo_price'].mean():.0f}円/坪")
        logging.info(f"  中央値: {df['tsubo_price'].median():.0f}円/坪")
        logging.info(f"  標準偏差: {df['tsubo_price'].std():.0f}円/坪")
        logging.info(f"  最小値: {df['tsubo_price'].min():.0f}円/坪")
        logging.info(f"  最大値: {df['tsubo_price'].max():.0f}円/坪")

    logging.info("=" * 60)


def save_to_csv(df: pl.DataFrame, output_path: Path) -> None:
    """
    DataFrameをCSV形式で保存します。

    Args:
        df (pl.DataFrame): 保存対象のDataFrame
        output_path (Path): 出力先パス
    """
    # 出力ディレクトリの作成（存在しない場合）
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # 出力カラムの選択と順序指定
    output_columns = [
        "transaction_date",
        "Year",
        "tsubo_price",
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
    ]

    # 存在するカラムのみを選択（一部カラムが存在しない場合に対応）
    available_columns = [col for col in output_columns if col in df.columns]

    # 時系列でソート
    df_sorted = df.sort("transaction_date")

    # CSV出力
    df_sorted.select(available_columns).write_csv(output_path)
    logging.info(f"データセットを保存しました: {output_path}")
    logging.info(f"保存カラム数: {len(available_columns)}")


def main() -> None:
    """機械学習用データセット作成のメイン処理"""
    # コマンドライン引数のパース
    parser = argparse.ArgumentParser(description="機械学習用データセット作成")
    parser.add_argument("--start-year", type=int, default=2023, help="データ取得開始年（デフォルト: 2023）")
    parser.add_argument("--end-year", type=int, default=2024, help="データ取得終了年（デフォルト: 2024）")
    parser.add_argument(
        "--city-codes",
        type=str,
        default=",".join(TOKYO_23_CITY_CODES),
        help="市区町村コード（カンマ区切り、デフォルト: 東京23区全体）",
    )
    parser.add_argument(
        "--output-path",
        type=str,
        default="data/ml_dataset/tokyo_23_ml_dataset.csv",
        help="出力CSVパス（デフォルト: data/ml_dataset/tokyo_23_ml_dataset.csv）",
    )
    args = parser.parse_args()

    # プロジェクトルートディレクトリ
    project_root = Path(__file__).parent.parent

    # 出力パスを絶対パスに変換
    output_path = project_root / args.output_path

    # 市区町村コードをリストに変換
    city_codes = [code.strip() for code in args.city_codes.split(",")]

    # CSVファイルパスの設定
    csv_path = project_root / "data" / "Tokyo_20053_20253_utf8.csv"

    # CSVからデータ読み込み
    logging.info(f"CSVファイルからデータ読み込み開始: {args.start_year}年〜{args.end_year}年")
    df = load_from_csv(csv_path, args.start_year, args.end_year, city_codes)

    if df is None or df.height == 0:
        logging.error("データ取得に失敗しました。APIキーと市区町村コードを確認してください。")
        sys.exit(1)

    # データフィルタリング
    df = filter_data(df)

    # 特徴量エンジニアリング
    df = engineer_features(df)

    # データ検証
    validate_data(df)

    # CSV出力
    save_to_csv(df, output_path)

    logging.info("処理が正常に完了しました")


if __name__ == "__main__":
    main()
