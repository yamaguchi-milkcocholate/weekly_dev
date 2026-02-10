"""不動産データの地域別集計・坪単価計算モジュール."""

from typing import Literal

import polars as pl


class RealEstateAggregator:
    """
    不動産データを地域別に集計し、坪単価を計算するクラス.

    Attributes:
        df (pl.DataFrame): 集計対象のPolars DataFrame.
        tsubo_conversion (float): 坪変換係数（1坪 = 3.30579㎡）.
    """

    def __init__(self, df: pl.DataFrame, tsubo_conversion: float = 3.30579) -> None:
        """
        RealEstateAggregatorを初期化します.

        Args:
            df (pl.DataFrame): 集計対象のPolars DataFrame.
                必須カラム: TradePrice, Area
            tsubo_conversion (float, optional): 坪変換係数. デフォルト: 3.30579

        Raises:
            ValueError: 必須カラム（TradePrice, Area）が存在しない場合.
        """
        required_columns = ["TradePrice", "Area"]
        missing_columns = [col for col in required_columns if col not in df.columns]
        if missing_columns:
            raise ValueError(f"必須カラムが不足しています: {missing_columns}")

        self.df = df
        self.tsubo_conversion = tsubo_conversion

    def calculate_sqm_price(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        ㎡単価を計算します.

        Args:
            df (pl.DataFrame): 計算対象のDataFrame（TradePriceとAreaカラムを含む）.

        Returns:
            pl.DataFrame: price_per_sqmカラムが追加されたDataFrame.
        """
        return df.with_columns((pl.col("TradePrice") / pl.col("Area")).alias("price_per_sqm"))

    def calculate_tsubo_price(self, df: pl.DataFrame) -> pl.DataFrame:
        """
        坪単価を計算します.

        Args:
            df (pl.DataFrame): 計算対象のDataFrame（TradePriceとAreaカラムを含む）.

        Returns:
            pl.DataFrame: price_per_tsuboカラムが追加されたDataFrame.
        """
        return df.with_columns(
            ((pl.col("TradePrice") / pl.col("Area")) * self.tsubo_conversion).alias("price_per_tsubo")
        )

    def aggregate_by_region(
        self,
        group_by: str | list[str] = "DistrictName",
        metrics: list[str] | None = None,
        price_unit: Literal["yen_per_sqm", "yen_per_tsubo", "both"] = "both",
        exclude_outliers: bool = False,
        percentile_range: tuple[float, float] = (0.05, 0.95),
    ) -> pl.DataFrame:
        """
        地域別に不動産データを集計します.

        Args:
            group_by (str | list[str], optional): 集計キー（カラム名）.
                デフォルト: "DistrictName"
            metrics (list[str] | None, optional): 計算する統計指標.
                指定可能: ["mean", "median", "min", "max", "std", "count"]
                デフォルト: None（すべての指標を計算）
            price_unit (Literal["yen_per_sqm", "yen_per_tsubo", "both"], optional):
                単価の種類. デフォルト: "both"
            exclude_outliers (bool, optional): 外れ値を除外するか. デフォルト: False
            percentile_range (tuple[float, float], optional): 外れ値除外の範囲.
                デフォルト: (0.05, 0.95)

        Returns:
            pl.DataFrame: 集計結果のDataFrame.

        Raises:
            ValueError: group_byで指定されたカラムが存在しない場合.
        """
        # group_byのバリデーション
        group_columns = [group_by] if isinstance(group_by, str) else group_by
        missing_group_columns = [col for col in group_columns if col not in self.df.columns]
        if missing_group_columns:
            raise ValueError(f"集計キーカラムが存在しません: {missing_group_columns}")

        # metricsのデフォルト値設定
        if metrics is None:
            metrics = ["mean", "median", "min", "max", "std", "count"]

        # データのコピーを作成
        df_work = self.df.clone()

        # 単価カラムの追加
        if price_unit in ["yen_per_sqm", "both"]:
            df_work = self.calculate_sqm_price(df_work)
        if price_unit in ["yen_per_tsubo", "both"]:
            df_work = self.calculate_tsubo_price(df_work)

        # 外れ値除外
        if exclude_outliers:
            lower_percentile, upper_percentile = percentile_range
            if price_unit in ["yen_per_sqm", "both"]:
                quantiles_sqm = df_work.select(
                    pl.col("price_per_sqm").quantile(lower_percentile).alias("lower"),
                    pl.col("price_per_sqm").quantile(upper_percentile).alias("upper"),
                ).row(0)
                df_work = df_work.filter(
                    (pl.col("price_per_sqm") >= quantiles_sqm[0]) & (pl.col("price_per_sqm") <= quantiles_sqm[1])
                )
            elif price_unit == "yen_per_tsubo":
                quantiles_tsubo = df_work.select(
                    pl.col("price_per_tsubo").quantile(lower_percentile).alias("lower"),
                    pl.col("price_per_tsubo").quantile(upper_percentile).alias("upper"),
                ).row(0)
                df_work = df_work.filter(
                    (pl.col("price_per_tsubo") >= quantiles_tsubo[0])
                    & (pl.col("price_per_tsubo") <= quantiles_tsubo[1])
                )

        # 集計式の構築
        agg_expressions = []

        # countは常に追加
        if "count" in metrics:
            agg_expressions.append(pl.len().alias("count"))

        # 各単価種別に対して統計指標を計算
        price_columns = []
        if price_unit in ["yen_per_sqm", "both"]:
            price_columns.append("price_per_sqm")
        if price_unit in ["yen_per_tsubo", "both"]:
            price_columns.append("price_per_tsubo")

        for price_col in price_columns:
            for metric in metrics:
                if metric == "mean":
                    agg_expressions.append(pl.col(price_col).mean().alias(f"{price_col}_{metric}"))
                elif metric == "median":
                    agg_expressions.append(pl.col(price_col).median().alias(f"{price_col}_{metric}"))
                elif metric == "min":
                    agg_expressions.append(pl.col(price_col).min().alias(f"{price_col}_{metric}"))
                elif metric == "max":
                    agg_expressions.append(pl.col(price_col).max().alias(f"{price_col}_{metric}"))
                elif metric == "std":
                    agg_expressions.append(pl.col(price_col).std().alias(f"{price_col}_{metric}"))

        # 集計実行
        result = df_work.group_by(group_columns).agg(agg_expressions)

        return result

    def get_summary_statistics(self, df: pl.DataFrame, price_column: str = "price_per_sqm") -> dict[str, float]:
        """
        全体統計のサマリーを取得します.

        Args:
            df (pl.DataFrame): 統計を計算するDataFrame.
            price_column (str, optional): 統計対象のカラム名.
                デフォルト: "price_per_sqm"

        Returns:
            dict[str, float]: 統計値を格納した辞書.
                キー: mean, median, min, max, std, count

        Raises:
            ValueError: price_columnが存在しない場合.
        """
        if price_column not in df.columns:
            raise ValueError(f"カラムが存在しません: {price_column}")

        stats = df.select(
            pl.col(price_column).mean().alias("mean"),
            pl.col(price_column).median().alias("median"),
            pl.col(price_column).min().alias("min"),
            pl.col(price_column).max().alias("max"),
            pl.col(price_column).std().alias("std"),
            pl.len().alias("count"),
        ).row(0)

        return {
            "mean": float(stats[0]) if stats[0] is not None else 0.0,
            "median": float(stats[1]) if stats[1] is not None else 0.0,
            "min": float(stats[2]) if stats[2] is not None else 0.0,
            "max": float(stats[3]) if stats[3] is not None else 0.0,
            "std": float(stats[4]) if stats[4] is not None else 0.0,
            "count": float(stats[5]) if stats[5] is not None else 0.0,
        }

    def aggregate_by_region_timeseries(
        self,
        year_column: str = "Year",
        group_by: str | list[str] = "DistrictName",
        metrics: list[str] | None = None,
        price_unit: Literal["yen_per_sqm", "yen_per_tsubo", "both"] = "both",
        exclude_outliers: bool = False,
        percentile_range: tuple[float, float] = (0.05, 0.95),
        calculate_yoy: bool = True,
    ) -> pl.DataFrame:
        """
        時系列×地域別に不動産データを集計し、前年比変化率を計算します.

        Args:
            year_column (str, optional): 年を示すカラム名. デフォルト: "Year"
            group_by (str | list[str], optional): 集計キー（カラム名）.
                デフォルト: "DistrictName"
            metrics (list[str] | None, optional): 計算する統計指標.
                指定可能: ["mean", "median", "min", "max", "std", "count"]
                デフォルト: None（すべての指標を計算）
            price_unit (Literal["yen_per_sqm", "yen_per_tsubo", "both"], optional):
                単価の種類. デフォルト: "both"
            exclude_outliers (bool, optional): 外れ値を除外するか. デフォルト: False
            percentile_range (tuple[float, float], optional): 外れ値除外の範囲.
                デフォルト: (0.05, 0.95)
            calculate_yoy (bool, optional): 前年比（YoY）変化率を計算するか. デフォルト: True

        Returns:
            pl.DataFrame: 時系列×地域別の集計結果DataFrame.
                calculate_yoy=Trueの場合、*_yoy_changeカラムが追加されます.

        Raises:
            ValueError: 必須カラム（year_column, group_by）が存在しない場合.
        """
        # year_columnの存在確認
        if year_column not in self.df.columns:
            raise ValueError(f"年カラムが存在しません: {year_column}")

        # group_byのバリデーション
        group_columns = [group_by] if isinstance(group_by, str) else group_by
        missing_group_columns = [col for col in group_columns if col not in self.df.columns]
        if missing_group_columns:
            raise ValueError(f"集計キーカラムが存在しません: {missing_group_columns}")

        # metricsのデフォルト値設定
        if metrics is None:
            metrics = ["mean", "median", "min", "max", "std", "count"]

        # データのコピーを作成
        df_work = self.df.clone()

        # 単価カラムの追加
        if price_unit in ["yen_per_sqm", "both"]:
            df_work = self.calculate_sqm_price(df_work)
        if price_unit in ["yen_per_tsubo", "both"]:
            df_work = self.calculate_tsubo_price(df_work)

        # 外れ値除外（年×地域ごとに実施）
        if exclude_outliers:
            lower_percentile, upper_percentile = percentile_range
            price_columns = []
            if price_unit in ["yen_per_sqm", "both"]:
                price_columns.append("price_per_sqm")
            if price_unit in ["yen_per_tsubo", "both"]:
                price_columns.append("price_per_tsubo")

            # 各グループごとに外れ値を除外
            for price_col in price_columns:
                # グループごとに分位点を計算
                quantiles = (
                    df_work.group_by([year_column] + group_columns)
                    .agg(
                        [
                            pl.col(price_col).quantile(lower_percentile).alias("lower"),
                            pl.col(price_col).quantile(upper_percentile).alias("upper"),
                        ]
                    )
                    .select([year_column] + group_columns + ["lower", "upper"])
                )
                # 元データと結合してフィルタリング
                df_work = df_work.join(quantiles, on=[year_column] + group_columns, how="left")
                df_work = df_work.filter(
                    (pl.col(price_col) >= pl.col("lower")) & (pl.col(price_col) <= pl.col("upper"))
                )
                df_work = df_work.drop(["lower", "upper"])

        # 集計式の構築
        agg_expressions = []

        # countは常に追加
        if "count" in metrics:
            agg_expressions.append(pl.len().alias("count"))

        # 各単価種別に対して統計指標を計算
        price_columns = []
        if price_unit in ["yen_per_sqm", "both"]:
            price_columns.append("price_per_sqm")
        if price_unit in ["yen_per_tsubo", "both"]:
            price_columns.append("price_per_tsubo")

        for price_col in price_columns:
            for metric in metrics:
                if metric == "mean":
                    agg_expressions.append(pl.col(price_col).mean().alias(f"{price_col}_{metric}"))
                elif metric == "median":
                    agg_expressions.append(pl.col(price_col).median().alias(f"{price_col}_{metric}"))
                elif metric == "min":
                    agg_expressions.append(pl.col(price_col).min().alias(f"{price_col}_{metric}"))
                elif metric == "max":
                    agg_expressions.append(pl.col(price_col).max().alias(f"{price_col}_{metric}"))
                elif metric == "std":
                    agg_expressions.append(pl.col(price_col).std().alias(f"{price_col}_{metric}"))

        # 時系列×地域で集計実行
        result = df_work.group_by([year_column] + group_columns).agg(agg_expressions)

        # 前年比変化率の計算
        if calculate_yoy:
            result = self._calculate_yoy_change(result, year_column, group_columns, price_columns, metrics)

        # 年でソート
        result = result.sort([year_column] + group_columns)

        return result

    def _calculate_yoy_change(
        self,
        df: pl.DataFrame,
        year_column: str,
        group_columns: list[str],
        price_columns: list[str],
        metrics: list[str],
    ) -> pl.DataFrame:
        """
        前年比（Year-over-Year）変化率を計算します.

        Args:
            df (pl.DataFrame): 集計済みDataFrame（年×地域別統計）.
            year_column (str): 年カラム名.
            group_columns (list[str]): グルーピングカラムのリスト.
            price_columns (list[str]): 単価カラムのリスト（price_per_sqm等）.
            metrics (list[str]): 統計指標リスト（mean, median等）.

        Returns:
            pl.DataFrame: 前年比カラムが追加されたDataFrame.
        """
        # 年カラムを整数型に変換（計算用）
        df = df.with_columns(pl.col(year_column).cast(pl.Int32).alias("_year_int"))

        # 前年データを結合するための準備
        df_prev = df.clone().with_columns((pl.col("_year_int") + 1).alias("_year_int"))

        # 前年比を計算する対象カラムを特定
        yoy_columns = []
        for price_col in price_columns:
            for metric in metrics:
                if metric != "count":  # countは前年比計算対象外
                    col_name = f"{price_col}_{metric}"
                    if col_name in df.columns:
                        yoy_columns.append(col_name)

        # 前年データの接尾辞付きリネーム
        rename_dict = {col: f"{col}_prev" for col in yoy_columns}
        df_prev = df_prev.select([c for c in df_prev.columns if c in (["_year_int"] + group_columns + yoy_columns)])
        df_prev = df_prev.rename(rename_dict)

        # 現年データと前年データを結合
        df = df.join(df_prev, on=["_year_int"] + group_columns, how="left")

        # 前年比変化率を計算（(current - prev) / prev * 100）
        for col in yoy_columns:
            col_prev = f"{col}_prev"
            col_yoy = f"{col}_yoy_change"
            if col_prev in df.columns:
                df = df.with_columns(((pl.col(col) - pl.col(col_prev)) / pl.col(col_prev) * 100.0).alias(col_yoy))

        # 一時カラムと前年カラムを削除
        drop_cols = ["_year_int"] + [f"{col}_prev" for col in yoy_columns if f"{col}_prev" in df.columns]
        df = df.drop([c for c in drop_cols if c in df.columns])

        return df
