"""ハイブリッド予測: Prophet（トレンド）+ LightGBM（残差）による坪単価予測"""

import logging

from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from sklearn.metrics import mean_absolute_error, mean_squared_error

from real_state_geo_core.ml.prophet_analyzer import ProphetTrendAnalyzer
from real_state_geo_core.ml.structure_analyzer import StructureAnalyzer


class HybridPredictor:
    """
    Prophet（トレンド）とLightGBM（残差）を組み合わせたハイブリッド予測モデル。

    予測価格 = トレンド(Prophet) + 物件固有価値(LGBM)
    """

    def __init__(self, random_state: int = 42):
        """
        Args:
            random_state (int, optional): 乱数シード。デフォルトは42。
        """
        self.random_state = random_state
        self.prophet_model = ProphetTrendAnalyzer(random_state=random_state)
        self.lgbm_model = StructureAnalyzer(random_state=random_state)
        self.is_fitted = False

    def fit(
        self,
        df: pl.DataFrame,
        target_col: str = "tsubo_price",
        date_col: str = "transaction_date",
        categorical_cols: list[str] | None = None,
        lgbm_params: dict | None = None,
    ) -> None:
        """
        ハイブリッドモデルを学習します。

        手順:
        1. Prophetで市場トレンドを学習
        2. 実測値からトレンドを引いた残差を計算
        3. LGBMで残差を学習

        Args:
            df (pl.DataFrame): 学習用DataFrame。
            target_col (str, optional): 目的変数カラム名。デフォルトは"tsubo_price"。
            date_col (str, optional): 日付カラム名。デフォルトは"transaction_date"。
            categorical_cols (list[str], optional): カテゴリカル変数のリスト。
            lgbm_params (dict, optional): LightGBMのパラメータ。
        """
        logging.info("ハイブリッドモデル学習開始")

        # Step 1: Prophetでトレンドを学習
        self.prophet_model.fit(df, date_col=date_col, target_col=target_col)

        # Step 2: トレンド予測と残差計算
        trend_pred = self.prophet_model.predict(df, date_col=date_col)
        residual = df[target_col] - trend_pred

        # Step 3: LGBMで残差を学習
        # 特徴量を準備（日付と目的変数を除外）
        exclude_cols = [date_col, target_col]
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        X = df.select(feature_cols)

        self.lgbm_model.fit(X, residual, categorical_cols=categorical_cols, lgbm_params=lgbm_params)

        self.is_fitted = True
        logging.info("ハイブリッドモデル学習完了")

    def predict(self, df: pl.DataFrame, date_col: str = "transaction_date") -> tuple[pl.Series, pl.Series, pl.Series]:
        """
        ハイブリッドモデルで予測を行います。

        Args:
            df (pl.DataFrame): 予測対象DataFrame。
            date_col (str, optional): 日付カラム名。デフォルトは"transaction_date"。

        Returns:
            Tuple[pl.Series, pl.Series, pl.Series]:
                (最終予測値, トレンド成分, 残差成分)

        Raises:
            ValueError: モデルが学習されていない場合。
        """
        if not self.is_fitted:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")

        # Prophetでトレンド予測
        trend_pred = self.prophet_model.predict(df, date_col=date_col)

        # LGBMで残差予測
        exclude_cols = [date_col, "tsubo_price"]
        feature_cols = [col for col in df.columns if col not in exclude_cols]
        X = df.select(feature_cols)
        residual_pred = self.lgbm_model.predict(X)

        # 最終予測 = トレンド + 残差
        final_pred = trend_pred + residual_pred

        return final_pred, trend_pred, residual_pred

    def evaluate(
        self, df: pl.DataFrame, target_col: str = "tsubo_price", date_col: str = "transaction_date"
    ) -> dict[str, float]:
        """
        モデルの性能を評価します。

        Args:
            df (pl.DataFrame): 評価用DataFrame（実測値を含む）。
            target_col (str, optional): 目的変数カラム名。デフォルトは"tsubo_price"。
            date_col (str, optional): 日付カラム名。デフォルトは"transaction_date"。

        Returns:
            dict[str, float]: RMSE, MAE, MAPEを含む辞書。
        """
        final_pred, _, _ = self.predict(df, date_col=date_col)
        y_true = df[target_col].to_numpy()
        y_pred = final_pred.to_numpy()

        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_true, y_pred)
        mape = (abs((y_true - y_pred) / y_true)).mean() * 100

        return {"rmse": rmse, "mae": mae, "mape": mape}

    def save_predictions(
        self,
        df: pl.DataFrame,
        output_path: str,
        target_col: str = "tsubo_price",
        date_col: str = "transaction_date",
        include_actuals: bool = True,
    ) -> None:
        """
        予測結果をCSVファイルとして保存します。

        Args:
            df (pl.DataFrame): 予測対象DataFrame。
            output_path (str): 出力先ファイルパス。
            target_col (str, optional): 目的変数カラム名。デフォルトは"tsubo_price"。
            date_col (str, optional): 日付カラム名。デフォルトは"transaction_date"。
            include_actuals (bool, optional): 実測値を含めるか。デフォルトはTrue。

        Raises:
            ValueError: モデルが学習されていない場合。
        """
        if not self.is_fitted:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # 予測実行
        final_pred, trend_pred, residual_pred = self.predict(df, date_col=date_col)

        # 結果をDataFrameに統合
        result_df = df.select(
            [
                date_col,
                "NearestStation",
                "DistrictName",
                "Age",
            ]
        ).with_columns(
            [
                pl.Series("predicted_total", final_pred),
                pl.Series("component_trend", trend_pred),
                pl.Series("component_structure", residual_pred),
            ]
        )

        # 実測値と誤差を追加
        if include_actuals and target_col in df.columns:
            result_df = result_df.with_columns(
                [
                    df[target_col].alias("actual_price"),
                    (df[target_col] - final_pred).abs().alias("error_abs"),
                ]
            )
        else:
            result_df = result_df.with_columns(
                [
                    pl.lit(None).alias("actual_price"),
                    pl.lit(None).alias("error_abs"),
                ]
            )

        # CSV保存
        result_df.write_csv(path)
        logging.info(f"ハイブリッド予測結果を保存しました: {output_path}")

    def cross_validate(
        self,
        df: pl.DataFrame,
        tscv,
        target_col: str = "tsubo_price",
        date_col: str = "transaction_date",
        categorical_cols: list[str] | None = None,
        lgbm_params: dict | None = None,
    ) -> pd.DataFrame:
        """
        時系列交差検証を実行し、各Foldの評価指標を返します。

        Args:
            df (pl.DataFrame): 学習用DataFrame。
            tscv: TimeSeriesSplitオブジェクト。
            target_col (str, optional): 目的変数カラム名。デフォルトは"tsubo_price"。
            date_col (str, optional): 日付カラム名。デフォルトは"transaction_date"。
            categorical_cols (list[str], optional): カテゴリカル変数のリスト。
            lgbm_params (dict, optional): LightGBMのパラメータ。

        Returns:
            pd.DataFrame: 各Foldの評価指標を含むDataFrame。
        """
        logging.info("時系列交差検証開始")
        cv_results = []

        for fold_id, (train_idx, valid_idx) in enumerate(tscv.split(df)):
            logging.info(f"Fold {fold_id + 1}/{tscv.n_splits} 開始")

            # データ分割
            train_df = df[train_idx]
            valid_df = df[valid_idx]

            # 各Fold用のモデルを作成
            fold_predictor = HybridPredictor(random_state=self.random_state)

            # モデル学習
            fold_predictor.fit(
                train_df,
                target_col=target_col,
                date_col=date_col,
                categorical_cols=categorical_cols,
                lgbm_params=lgbm_params,
            )

            # 検証データで評価
            metrics = fold_predictor.evaluate(valid_df, target_col=target_col, date_col=date_col)

            # 結果を記録
            cv_results.append(
                {
                    "fold_id": fold_id,
                    "train_start": train_df[date_col].min(),
                    "train_end": train_df[date_col].max(),
                    "valid_start": valid_df[date_col].min(),
                    "valid_end": valid_df[date_col].max(),
                    "rmse": metrics["rmse"],
                    "mae": metrics["mae"],
                    "mape": metrics["mape"],
                }
            )

            logging.info(
                f"Fold {fold_id + 1} - RMSE: {metrics['rmse']:.2f}, MAE: {metrics['mae']:.2f}, MAPE: {metrics['mape']:.2f}%"
            )

        cv_df = pd.DataFrame(cv_results)
        logging.info("時系列交差検証完了")
        return cv_df

    def save_cv_metrics(self, cv_df: pd.DataFrame, output_path: str) -> None:
        """
        交差検証の評価指標をCSVファイルとして保存します。

        Args:
            cv_df (pd.DataFrame): 交差検証結果のDataFrame。
            output_path (str): 出力先ファイルパス。
        """
        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        cv_df.to_csv(path, index=False)
        logging.info(f"交差検証メトリクスを保存しました: {output_path}")
