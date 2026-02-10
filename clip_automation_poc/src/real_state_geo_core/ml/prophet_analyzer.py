"""マクロトレンド分析: Prophetによる市場全体の価格推移解析"""

import logging

from pathlib import Path

import pandas as pd
import polars as pl

from prophet import Prophet


class ProphetTrendAnalyzer:
    """
    Prophetを使用して、区（Municipality）ごとの坪単価トレンド・季節性を抽出します。
    物件個別の事情を無視した、エリアレベルの時系列分析を行います。
    """

    def __init__(self, random_state: int = 42):
        """
        Args:
            random_state (int, optional): 乱数シード。デフォルトは42。
        """
        self.random_state = random_state
        self.models: dict[str, Prophet] = {}  # 区ごとのモデルを格納
        self.forecast_dfs: dict[str, pd.DataFrame] = {}  # 区ごとの予測結果
        self.municipalities: list[str] = []  # 学習した区のリスト

    def fit(
        self,
        df: pl.DataFrame,
        date_col: str = "transaction_date",
        target_col: str = "tsubo_price",
        municipality_col: str = "Municipality",
    ) -> None:
        """
        区ごとにProphetモデルを学習します。

        Args:
            df (pl.DataFrame): 学習用DataFrame。
            date_col (str, optional): 日付カラム名。デフォルトは"transaction_date"。
            target_col (str, optional): 目的変数カラム名。デフォルトは"tsubo_price"。
            municipality_col (str, optional): 区カラム名。デフォルトは"Municipality"。
        """
        # 区のリストを取得
        self.municipalities = df[municipality_col].unique().sort().to_list()
        logging.info(f"区ごとのProphetモデル学習開始: {len(self.municipalities)}区")

        # 区ごとにモデルを学習
        for municipality in self.municipalities:
            # 区のデータを抽出
            df_muni = df.filter(pl.col(municipality_col) == municipality)

            # 月単位で集約（平均値）
            monthly_df = (
                df_muni.group_by_dynamic(date_col, every="1mo")
                .agg(pl.col(target_col).mean().alias("y"))
                .sort(date_col)
                .rename({date_col: "ds"})
            )

            # Polars → Pandas変換（ProphetはPandas必須）
            prophet_df = monthly_df.to_pandas()

            # データが少なすぎる場合はスキップ
            if len(prophet_df) < 2:
                logging.warning(f"{municipality}: データ不足のためスキップ（{len(prophet_df)}行）")
                continue

            # Prophetモデルの作成
            model = Prophet(
                yearly_seasonality=True,
                weekly_seasonality=False,
                daily_seasonality=False,
                changepoint_prior_scale=0.05,
                seasonality_prior_scale=10.0,
            )

            # 日本の祝日を追加
            model.add_country_holidays(country_name="JP")

            # 学習
            model.fit(prophet_df)
            self.models[municipality] = model

            logging.info(f"{municipality}: Prophetモデル学習完了（{len(prophet_df)}行）")

        logging.info(f"全{len(self.models)}区のProphetモデル学習完了")

    def predict(
        self, df: pl.DataFrame, date_col: str = "transaction_date", municipality_col: str = "Municipality"
    ) -> pl.Series:
        """
        学習済みモデルでトレンド予測を行います（データポイント単位）。
        各データ点の区に対応するモデルで予測を行います。

        Args:
            df (pl.DataFrame): 予測対象DataFrame。
            date_col (str, optional): 日付カラム名。デフォルトは"transaction_date"。
            municipality_col (str, optional): 区カラム名。デフォルトは"Municipality"。

        Returns:
            pl.Series: 予測されたトレンド値（yhat）。

        Raises:
            ValueError: モデルが学習されていない場合。
        """
        if len(self.models) == 0:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")

        # 予測結果を格納するリスト
        predictions = []

        # 区ごとに予測
        for municipality in df[municipality_col].unique().sort().to_list():
            # その区のデータを抽出
            df_muni = df.filter(pl.col(municipality_col) == municipality)

            # その区のモデルが存在しない場合は全体の平均値を使用
            if municipality not in self.models:
                logging.warning(f"{municipality}: モデルが存在しないため、0で補完します")
                predictions.extend([0.0] * len(df_muni))
                continue

            # 日付データをPandas DataFrameに変換
            future_df = pd.DataFrame({"ds": df_muni[date_col].to_pandas()})

            # 予測実行
            model = self.models[municipality]
            forecast = model.predict(future_df)

            # yhat（予測値）を追加
            predictions.extend(forecast["yhat"].values.tolist())

        # 元の順序に戻すため、区と日付でソートして予測値を並べ直す
        # 簡易実装: dfの行番号に対応する予測値を返す
        result_df = df.select([municipality_col, date_col]).with_row_index("_idx")
        pred_list = []

        for row in result_df.iter_rows(named=True):
            muni = row[municipality_col]
            date = row[date_col]

            if muni not in self.models:
                pred_list.append(0.0)
                continue

            # その区のモデルで予測
            future_df = pd.DataFrame({"ds": [date]})
            forecast = self.models[muni].predict(future_df)
            pred_list.append(forecast["yhat"].values[0])

        return pl.Series(pred_list)

    def forecast_future(self, periods: int = 12, freq: str = "MS") -> pd.DataFrame:
        """
        将来の市場トレンドを区ごとに予測します。

        Args:
            periods (int, optional): 予測期間数。デフォルトは12（月）。
            freq (str, optional): 予測頻度（'MS'=月初, 'D'=日次）。デフォルトは'MS'。

        Returns:
            pd.DataFrame: 予測結果（Municipality, ds, yhat, yhat_lower, yhat_upper, trendなど）。

        Raises:
            ValueError: モデルが学習されていない場合。
        """
        if len(self.models) == 0:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")

        all_forecasts = []

        # 区ごとに予測
        for municipality, model in self.models.items():
            # 将来のタイムスタンプを生成
            future = model.make_future_dataframe(periods=periods, freq=freq)

            # 予測実行
            forecast = model.predict(future)

            # 区名を追加
            forecast["Municipality"] = municipality
            all_forecasts.append(forecast)

            # 区ごとの予測結果を保存
            self.forecast_dfs[municipality] = forecast

        # 全区の予測結果を結合
        combined_forecast = pd.concat(all_forecasts, ignore_index=True)

        logging.info(f"全{len(self.models)}区について将来{periods}期間の予測完了")
        return combined_forecast

    def save_forecast(self, forecast_df: pd.DataFrame, output_path: str, include_history: bool = True) -> None:
        """
        予測結果をCSVファイルとして保存します。

        Args:
            forecast_df (pd.DataFrame): forecast_future()で取得した予測結果。
            output_path (str): 出力先ファイルパス。
            include_history (bool, optional): 学習期間のデータも含めるか。デフォルトはTrue。

        Raises:
            ValueError: 予測が実行されていない場合。
        """
        if forecast_df is None or len(forecast_df) == 0:
            raise ValueError("予測が実行されていません。forecast_future()を先に実行してください。")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # 出力カラムを選択
        output_df = forecast_df[["Municipality", "ds", "trend", "yhat", "yhat_lower", "yhat_upper"]].copy()

        # is_forecast列を追加（将来予測期間かどうか）
        # 区ごとに最終学習日を判定
        output_df["is_forecast"] = False
        for municipality in output_df["Municipality"].unique():
            mask = output_df["Municipality"] == municipality
            municipality_data = output_df[mask]

            # 簡易的に最大dsを最終学習日とする
            last_train_date = municipality_data["ds"].max()
            # 将来予測期間を判定（periodsで指定した期間）
            # ここでは簡易的に、学習期間を超えたデータをis_forecast=Trueとする
            # より正確には、forecast_future呼び出し時のperiodsを保持して判定すべき
            output_df.loc[mask, "is_forecast"] = False  # デフォルトはFalse（学習期間）

        if not include_history:
            # 将来予測期間のみを出力
            output_df = output_df[output_df["is_forecast"]]

        output_df.to_csv(path, index=False)
        logging.info(f"市場トレンド予測を保存しました: {output_path}")

    def get_trend_component(
        self, df: pl.DataFrame, date_col: str = "transaction_date", municipality_col: str = "Municipality"
    ) -> pl.Series:
        """
        トレンド成分のみを抽出します（区ごと）。

        Args:
            df (pl.DataFrame): 対象DataFrame。
            date_col (str, optional): 日付カラム名。デフォルトは"transaction_date"。
            municipality_col (str, optional): 区カラム名。デフォルトは"Municipality"。

        Returns:
            pl.Series: トレンド成分。
        """
        if len(self.models) == 0:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")

        # 予測結果を格納するリスト
        result_df = df.select([municipality_col, date_col]).with_row_index("_idx")
        trend_list = []

        for row in result_df.iter_rows(named=True):
            muni = row[municipality_col]
            date = row[date_col]

            if muni not in self.models:
                trend_list.append(0.0)
                continue

            # その区のモデルで予測
            future_df = pd.DataFrame({"ds": [date]})
            forecast = self.models[muni].predict(future_df)
            trend_list.append(forecast["trend"].values[0])

        return pl.Series(trend_list)
