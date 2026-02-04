"""データローダー: ML用データセットの読み込みと前処理"""

import logging

from pathlib import Path

import polars as pl

from sklearn.model_selection import GroupKFold


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
        df = df.filter(pl.col("tsubo_price").is_not_null() & (pl.col("tsubo_price") > 0))

        # 外れ値除去: 上位1%と下位1%を除外
        lower_bound = df["tsubo_price"].quantile(0.01)
        upper_bound = df["tsubo_price"].quantile(0.99)
        logging.info(f"坪単価の範囲: {lower_bound:.2f} 〜 {upper_bound:.2f}")

        df = df.filter((pl.col("tsubo_price") >= lower_bound) & (pl.col("tsubo_price") <= upper_bound))
        logging.info(f"外れ値除去後のデータ件数: {df.height}件")

    # 数値カラムを適切な型に変換
    numeric_cols = ["CoverageRatio", "FloorAreaRatio", "Area", "Age", "BuildingYear", "TimeToNearestStation"]
    for col in numeric_cols:
        if col in df.columns:
            df = df.with_columns(pl.col(col).cast(pl.Float64, strict=False))

    # transaction_dateでソート（時系列分析の前提）
    df = df.sort("transaction_date")

    logging.info(f"データセット読み込み完了: {df.height}件")
    return df


def add_time_features(df: pl.DataFrame, date_col: str = "transaction_date") -> pl.DataFrame:
    """
    時点関連の特徴量を追加します。

    Args:
        df (pl.DataFrame): 元のDataFrame。
        date_col (str, optional): 日付カラム名。デフォルトは"transaction_date"。

    Returns:
        pl.DataFrame: 時点特徴量を追加したDataFrame。
    """
    df = df.with_columns(
        [
            pl.col(date_col).dt.year().alias("Year"),
            pl.col(date_col).dt.month().alias("Month"),
            pl.col(date_col).dt.quarter().alias("Quarter"),
        ]
    )
    return df


def add_aggregated_features(
    train_df: pl.DataFrame,
    target_df: pl.DataFrame,
    target_col: str = "tsubo_price",
    agg_keys: list[str] | None = None,
) -> pl.DataFrame:
    """
    年ごとの集約統計量を特徴量として追加します。

    Args:
        train_df (pl.DataFrame): 訓練データ（集約統計量の計算元）。
        target_df (pl.DataFrame): 特徴量を追加する対象のDataFrame。
        target_col (str, optional): 集約対象のカラム名。デフォルトは"tsubo_price"。
        agg_keys (list[str], optional): 集約キーのリスト。デフォルトは["Municipality", "NearestStation"]。

    Returns:
        pl.DataFrame: 集約統計量を追加したDataFrame。
    """
    if agg_keys is None:
        agg_keys = ["Municipality", "NearestStation"]

    result_df = target_df

    for key in agg_keys:
        if key not in train_df.columns or key not in target_df.columns:
            logging.warning(f"集約キー '{key}' が見つかりません。スキップします。")
            continue

        # 年ごとの平均値・中央値を計算
        stats = (
            train_df.group_by([key, "Year"])
            .agg(
                [
                    pl.col(target_col).mean().alias(f"{key}_Year_mean_price"),
                    pl.col(target_col).median().alias(f"{key}_Year_median_price"),
                ]
            )
            .sort([key, "Year"])
        )

        # target_dfに結合（left join）
        result_df = result_df.join(stats, on=[key, "Year"], how="left")

    logging.info(f"集約統計量を追加しました: {agg_keys}")
    return result_df


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


def create_group_kfold_split(
    df: pl.DataFrame, n_splits: int = 5, test_ratio: float = 0.2, group_col: str = "Municipality"
) -> tuple[pl.DataFrame, pl.DataFrame, GroupKFold]:
    """
    GroupKFold交差検証用のデータ分割を行います。

    Args:
        df (pl.DataFrame): 元のDataFrame。
        n_splits (int, optional): GroupKFoldの分割数。デフォルトは5。
        test_ratio (float, optional): テストデータの割合。デフォルトは0.2。
        group_col (str, optional): グループ化するカラム名。デフォルトは"Municipality"。

    Returns:
        Tuple[pl.DataFrame, pl.DataFrame, GroupKFold]:
            (Trainデータ, Testデータ, GroupKFoldオブジェクト)。
    """
    # ランダムにテストデータを分割（20%）
    import numpy as np

    np.random.seed(42)
    indices = np.arange(df.height)
    np.random.shuffle(indices)

    test_size = int(df.height * test_ratio)
    test_indices = indices[:test_size]
    train_indices = indices[test_size:]

    test_df = df[test_indices]
    train_df = df[train_indices]

    logging.info(f"Train: {train_df.height}件, Test: {test_df.height}件")

    # GroupKFoldを作成
    gkf = GroupKFold(n_splits=n_splits)

    return train_df, test_df, gkf
