"""マクロトレンド分析: Prophetによる市場全体の価格推移解析"""

import logging

from pathlib import Path

import pandas as pd
import polars as pl

from prophet import Prophet


class ProphetTrendAnalyzer:
    """
    Prophetを使用して、市場全体の坪単価トレンド・季節性を抽出します。
    物件個別の事情を無視した、マクロレベルの時系列分析を行います。
    """

    def __init__(self, random_state: int = 42):
        """
        Args:
            random_state (int, optional): 乱数シード。デフォルトは42。
        """
        self.random_state = random_state
        self.model: Prophet | None = None
        self.forecast_df: pd.DataFrame | None = None

    def fit(self, df: pl.DataFrame, date_col: str = "transaction_date", target_col: str = "tsubo_price") -> None:
        """
        Prophetモデルを学習します。

        Args:
            df (pl.DataFrame): 学習用DataFrame。
            date_col (str, optional): 日付カラム名。デフォルトは"transaction_date"。
            target_col (str, optional): 目的変数カラム名。デフォルトは"tsubo_price"。
        """
        # 月単位で集約（平均値）
        monthly_df = (
            df.group_by_dynamic(date_col, every="1mo")
            .agg(pl.col(target_col).mean().alias("y"))
            .sort(date_col)
            .rename({date_col: "ds"})
        )

        # Polars → Pandas変換（ProphetはPandas必須）
        prophet_df = monthly_df.to_pandas()

        # Prophetモデルの作成
        self.model = Prophet(
            yearly_seasonality=True,
            weekly_seasonality=False,
            daily_seasonality=False,
            changepoint_prior_scale=0.05,
            seasonality_prior_scale=10.0,
        )

        # 日本の祝日を追加
        self.model.add_country_holidays(country_name="JP")

        logging.info("Prophetモデル学習開始")
        self.model.fit(prophet_df)
        logging.info("Prophetモデル学習完了")

    def predict(self, df: pl.DataFrame, date_col: str = "transaction_date") -> pl.Series:
        """
        学習済みモデルでトレンド予測を行います（データポイント単位）。

        Args:
            df (pl.DataFrame): 予測対象DataFrame。
            date_col (str, optional): 日付カラム名。デフォルトは"transaction_date"。

        Returns:
            pl.Series: 予測されたトレンド値（yhat）。

        Raises:
            ValueError: モデルが学習されていない場合。
        """
        if self.model is None:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")

        # 日付データをPandas DataFrameに変換
        future_df = pd.DataFrame({"ds": df[date_col].to_pandas()})

        # 予測実行
        forecast = self.model.predict(future_df)

        # yhat（予測値）を返す
        return pl.Series(forecast["yhat"].values)

    def forecast_future(self, periods: int = 12, freq: str = "MS") -> pd.DataFrame:
        """
        将来の市場トレンドを予測します。

        Args:
            periods (int, optional): 予測期間数。デフォルトは12（月）。
            freq (str, optional): 予測頻度（'MS'=月初, 'D'=日次）。デフォルトは'MS'。

        Returns:
            pd.DataFrame: 予測結果（ds, yhat, yhat_lower, yhat_upper, trendなど）。

        Raises:
            ValueError: モデルが学習されていない場合。
        """
        if self.model is None:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")

        # 将来のタイムスタンプを生成
        future = self.model.make_future_dataframe(periods=periods, freq=freq)

        # 予測実行
        self.forecast_df = self.model.predict(future)

        logging.info(f"将来{periods}期間の予測完了")
        return self.forecast_df

    def save_forecast(self, output_path: str, include_history: bool = True) -> None:
        """
        予測結果をCSVファイルとして保存します。

        Args:
            output_path (str): 出力先ファイルパス。
            include_history (bool, optional): 学習期間のデータも含めるか。デフォルトはTrue。

        Raises:
            ValueError: 予測が実行されていない場合。
        """
        if self.forecast_df is None:
            raise ValueError("予測が実行されていません。forecast_future()を先に実行してください。")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # 出力カラムを選択
        output_df = self.forecast_df[["ds", "trend", "yhat", "yhat_lower", "yhat_upper"]].copy()

        # is_forecast列を追加（将来予測期間かどうか）
        if include_history:
            # 最終学習日を取得（簡易的に最大dsとする）
            last_train_date = self.forecast_df["ds"].max()
            output_df["is_forecast"] = output_df["ds"] > last_train_date
        else:
            output_df["is_forecast"] = True

        output_df.to_csv(path, index=False)
        logging.info(f"市場トレンド予測を保存しました: {output_path}")

    def get_trend_component(self, df: pl.DataFrame, date_col: str = "transaction_date") -> pl.Series:
        """
        トレンド成分のみを抽出します。

        Args:
            df (pl.DataFrame): 対象DataFrame。
            date_col (str, optional): 日付カラム名。デフォルトは"transaction_date"。

        Returns:
            pl.Series: トレンド成分。
        """
        if self.model is None:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")

        future_df = pd.DataFrame({"ds": df[date_col].to_pandas()})
        forecast = self.model.predict(future_df)

        return pl.Series(forecast["trend"].values)
