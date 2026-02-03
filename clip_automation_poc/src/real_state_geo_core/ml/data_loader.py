"""データローダー: ML用データセットの読み込みと前処理"""

import logging

from pathlib import Path

import polars as pl

from sklearn.model_selection import TimeSeriesSplit


def load_ml_dataset(csv_path: str) -> pl.DataFrame:
    """
    ML用データセットを読み込み、基本的な前処理を行います。

    Args:
        csv_path (str): ML用データセットのCSVファイルパス。

    Returns:
        pl.DataFrame: 読み込み済みのDataFrame。

    Raises:
        FileNotFoundError: ファイルが見つからない場合。
        ValueError: データが空の場合。
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"ML用データセットが見つかりません: {csv_path}")

    logging.info(f"データセット読み込み開始: {csv_path}")
    df = pl.read_csv(csv_path)

    if df.height == 0:
        raise ValueError("データセットが空です")

    # transaction_dateをDatetime型に変換
    if "transaction_date" in df.columns:
        df = df.with_columns(pl.col("transaction_date").str.to_datetime())

    # 目的変数（坪単価）の欠損値・異常値を除去
    if "tsubo_price" in df.columns:
        df = df.filter(
            pl.col("tsubo_price").is_not_null()
            & (pl.col("tsubo_price") > 0)
            & (pl.col("tsubo_price") < 10_000_000)  # 上限1,000万円/坪
        )

    # 数値カラムを適切な型に変換
    numeric_cols = ["CoverageRatio", "FloorAreaRatio", "Area", "Age", "BuildingYear", "TimeToNearestStation"]
    for col in numeric_cols:
        if col in df.columns:
            df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False))

    # transaction_dateでソート（時系列分析の前提）
    df = df.sort("transaction_date")

    logging.info(f"データセット読み込み完了: {df.height}件")
    return df


def prepare_features(
    df: pl.DataFrame, target_col: str = "tsubo_price", exclude_cols: list[str] | None = None
) -> tuple[pl.DataFrame, pl.Series]:
    """
    特徴量と目的変数を分離し、モデル学習用に準備します。

    Args:
        df (pl.DataFrame): 元のDataFrame。
        target_col (str, optional): 目的変数のカラム名。デフォルトは"tsubo_price"。
        exclude_cols (list[str], optional): 特徴量から除外するカラムのリスト。

    Returns:
        Tuple[pl.DataFrame, pl.Series]: (特徴量DataFrame, 目的変数Series)。
    """
    if exclude_cols is None:
        exclude_cols = ["transaction_date", target_col]
    else:
        exclude_cols = list(set(exclude_cols + [target_col]))

    # 目的変数を取得
    y = df[target_col]

    # 特徴量を取得（除外カラムを除く）
    feature_cols = [col for col in df.columns if col not in exclude_cols]
    X = df.select(feature_cols)

    logging.info(f"特徴量数: {len(feature_cols)}, データ件数: {X.height}")
    return X, y


def create_time_series_split(
    df: pl.DataFrame, n_splits: int = 5, test_year: int = 2025
) -> tuple[pl.DataFrame, pl.DataFrame, TimeSeriesSplit]:
    """
    時系列交差検証用のデータ分割を行います。

    Args:
        df (pl.DataFrame): 元のDataFrame（transaction_dateでソート済み）。
        n_splits (int, optional): TimeSeriesSplitの分割数。デフォルトは5。
        test_year (int, optional): テストデータとして分離する年。デフォルトは2025。

    Returns:
        Tuple[pl.DataFrame, pl.DataFrame, TimeSeriesSplit]:
            (Train/Validデータ, Testデータ, TimeSeriesSplitオブジェクト)。
    """
    # Year列を確認してホールドアウト分割
    if "Year" in df.columns:
        train_valid_df = df.filter(pl.col("Year") < test_year)
        test_df = df.filter(pl.col("Year") == test_year)
    else:
        # Year列がない場合はtransaction_dateから判定
        df = df.with_columns(pl.col("transaction_date").dt.year().alias("Year"))
        train_valid_df = df.filter(pl.col("Year") < test_year)
        test_df = df.filter(pl.col("Year") == test_year)

    logging.info(f"Train/Valid: {train_valid_df.height}件, Test: {test_df.height}件")

    # TimeSeriesSplitを作成
    tscv = TimeSeriesSplit(n_splits=n_splits, gap=0)

    return train_valid_df, test_df, tscv
