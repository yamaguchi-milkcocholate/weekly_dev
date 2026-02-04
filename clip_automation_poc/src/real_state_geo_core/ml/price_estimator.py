"""坪単価相場推定モデル: LightGBMによる立地・物件情報からの価格推定"""

import logging

from pathlib import Path

import numpy as np
import pandas as pd
import polars as pl

from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error


class PriceEstimator:
    """
    LightGBMを用いた坪単価相場推定モデル。

    立地情報（最寄駅、区、徒歩時間等）、物件スペック（築年数、面積等）、取引時点から
    坪単価を推定します。
    """

    def __init__(self, random_state: int = 42, lgbm_params: dict | None = None):
        """
        Args:
            random_state (int, optional): 乱数シード。デフォルトは42。
            lgbm_params (dict, optional): LightGBMのパラメータ。
        """
        self.random_state = random_state

        # デフォルトパラメータ
        default_params = {
            "objective": "regression",
            "metric": "rmse",
            "verbosity": -1,
            "random_state": random_state,
            "n_estimators": 1000,
            "learning_rate": 0.05,
            "num_leaves": 31,
            "max_depth": -1,
            "min_child_samples": 20,
            "subsample": 0.8,
            "subsample_freq": 1,
            "colsample_bytree": 0.8,
            "reg_alpha": 0.1,
            "reg_lambda": 0.1,
        }

        if lgbm_params is not None:
            default_params.update(lgbm_params)

        self.lgbm_params = default_params
        self.model = None
        self.categorical_features = None
        self.feature_importance_df = None

    def fit(
        self,
        X: pl.DataFrame,
        y: pl.Series,
        categorical_cols: list[str] | None = None,
        eval_set: tuple[pl.DataFrame, pl.Series] | None = None,
    ) -> None:
        """
        モデルを学習します。

        Args:
            X (pl.DataFrame): 特徴量DataFrame。
            y (pl.Series): 目的変数Series。
            categorical_cols (list[str], optional): カテゴリカル変数のリスト。
            eval_set (tuple, optional): 検証用データ (X_valid, y_valid)。
        """
        logging.info("LightGBMモデル学習開始")

        # カテゴリカル変数の指定
        if categorical_cols is None:
            categorical_cols = [
                "NearestStation",
                "DistrictName",
                "Municipality",
                "Structure",
                "CityPlanning",
                "Renovation",
                "FloorPlan",
                "Purpose",
                "Direction",
                "Classification",
                "CityPlanningArea",
                "Breadth",
            ]
        self.categorical_features = [col for col in categorical_cols if col in X.columns]

        # Polars → Pandas変換（LightGBM用）
        X_pd = X.to_pandas()
        y_pd = y.to_pandas()

        # カテゴリカル変数をcategory型に変換
        for col in self.categorical_features:
            X_pd[col] = X_pd[col].astype("category")

        # モデル学習
        self.model = LGBMRegressor(**self.lgbm_params)

        if eval_set is not None:
            X_valid_pd = eval_set[0].to_pandas()
            y_valid_pd = eval_set[1].to_pandas()
            for col in self.categorical_features:
                if col in X_valid_pd.columns:
                    X_valid_pd[col] = X_valid_pd[col].astype("category")
            eval_set_pd = [(X_valid_pd, y_valid_pd)]
        else:
            eval_set_pd = None

        self.model.fit(
            X_pd,
            y_pd,
            categorical_feature=self.categorical_features,
            eval_set=eval_set_pd,
        )

        # 特徴量重要度を計算
        self._compute_feature_importance(X_pd)

        logging.info("LightGBMモデル学習完了")

    def predict(self, X: pl.DataFrame) -> pl.Series:
        """
        予測を行います。

        Args:
            X (pl.DataFrame): 特徴量DataFrame。

        Returns:
            pl.Series: 予測値Series。

        Raises:
            ValueError: モデルが学習されていない場合。
        """
        if self.model is None:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")

        # Polars → Pandas変換
        X_pd = X.to_pandas()

        # カテゴリカル変数をcategory型に変換
        for col in self.categorical_features:
            if col in X_pd.columns:
                X_pd[col] = X_pd[col].astype("category")

        # 予測
        y_pred = self.model.predict(X_pd)

        return pl.Series(y_pred)

    def _compute_feature_importance(self, X_pd: pd.DataFrame) -> None:
        """特徴量重要度を計算します（内部処理）"""
        importance_gain = self.model.booster_.feature_importance(importance_type="gain")
        importance_split = self.model.booster_.feature_importance(importance_type="split")

        self.feature_importance_df = pd.DataFrame(
            {
                "feature_name": X_pd.columns,
                "importance_gain": importance_gain,
                "importance_split": importance_split,
            }
        ).sort_values("importance_gain", ascending=False)

    def get_feature_importance(self) -> pd.DataFrame:
        """
        特徴量重要度を取得します。

        Returns:
            pd.DataFrame: 特徴量重要度のDataFrame（importance_gain降順）。
        """
        if self.feature_importance_df is None:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")
        return self.feature_importance_df

    def save_feature_importance(self, output_path: str) -> None:
        """
        特徴量重要度をCSVファイルとして保存します。

        Args:
            output_path (str): 出力先ファイルパス。
        """
        if self.feature_importance_df is None:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        self.feature_importance_df.to_csv(path, index=False)
        logging.info(f"特徴量重要度を保存しました: {output_path}")

    def evaluate(self, X: pl.DataFrame, y: pl.Series) -> dict[str, float]:
        """
        モデルの性能を評価します。

        Args:
            X (pl.DataFrame): 特徴量DataFrame。
            y (pl.Series): 目的変数Series。

        Returns:
            dict[str, float]: RMSE, MAE, MAPEを含む辞書。
        """
        y_pred = self.predict(X)
        y_true = y.to_numpy()
        y_pred_np = y_pred.to_numpy()

        mse = mean_squared_error(y_true, y_pred_np)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_true, y_pred_np)
        mape = (abs((y_true - y_pred_np) / y_true)).mean() * 100

        return {"rmse": rmse, "mae": mae, "mape": mape}

    def cross_validate(
        self,
        df: pl.DataFrame,
        gkf,
        groups: pl.Series,
        target_col: str = "tsubo_price",
        categorical_cols: list[str] | None = None,
    ) -> pd.DataFrame:
        """
        GroupKFold交差検証を実行し、各Foldの評価指標を返します。

        Args:
            df (pl.DataFrame): 学習用DataFrame（特徴量を含む）。
            gkf: GroupKFoldオブジェクト。
            groups (pl.Series): グループラベル（Municipality等）。
            target_col (str, optional): 目的変数カラム名。デフォルトは"tsubo_price"。
            categorical_cols (list[str], optional): カテゴリカル変数のリスト。

        Returns:
            pd.DataFrame: 各Foldの評価指標を含むDataFrame。
        """
        logging.info("GroupKFold交差検証開始")
        cv_results = []

        # 特徴量と目的変数を分離
        from real_state_geo_core.ml.data_loader import prepare_features

        X, y = prepare_features(df, target_col=target_col, exclude_cols=["transaction_date"])
        groups_np = groups.to_numpy()

        for fold_id, (train_idx, valid_idx) in enumerate(gkf.split(X, y, groups=groups_np)):
            logging.info(f"Fold {fold_id + 1}/{gkf.n_splits} 開始")

            # データ分割
            X_train = X[train_idx]
            y_train = y[train_idx]
            X_valid = X[valid_idx]
            y_valid = y[valid_idx]

            # モデル学習
            fold_model = PriceEstimator(random_state=self.random_state, lgbm_params=self.lgbm_params)
            fold_model.fit(X_train, y_train, categorical_cols=categorical_cols, eval_set=(X_valid, y_valid))

            # 検証データで評価
            metrics = fold_model.evaluate(X_valid, y_valid)

            # 結果を記録
            cv_results.append(
                {
                    "fold_id": fold_id,
                    "rmse": metrics["rmse"],
                    "mae": metrics["mae"],
                    "mape": metrics["mape"],
                }
            )

            logging.info(
                f"Fold {fold_id + 1} - RMSE: {metrics['rmse']:.2f}, "
                + f"MAE: {metrics['mae']:.2f}, MAPE: {metrics['mape']:.2f}%"
            )

        cv_df = pd.DataFrame(cv_results)
        logging.info("GroupKFold交差検証完了")
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

    def save_predictions(
        self,
        df: pl.DataFrame,
        output_path: str,
        target_col: str = "tsubo_price",
        include_actuals: bool = True,
    ) -> None:
        """
        予測結果をCSVファイルとして保存します。

        Args:
            df (pl.DataFrame): 予測対象DataFrame（特徴量を含む）。
            output_path (str): 出力先ファイルパス。
            target_col (str, optional): 目的変数カラム名。デフォルトは"tsubo_price"。
            include_actuals (bool, optional): 実測値を含めるか。デフォルトはTrue。
        """
        if self.model is None:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # 特徴量を準備
        from real_state_geo_core.ml.data_loader import prepare_features

        X, y = prepare_features(df, target_col=target_col, exclude_cols=["transaction_date"])

        # 予測実行
        y_pred = self.predict(X)

        # 結果をDataFrameに統合
        result_df = df.select(
            ["transaction_date", "NearestStation", "DistrictName", "Municipality", "Age", "Area"]
        ).with_columns([pl.Series("predicted_price", y_pred)])

        # 実測値と誤差を追加
        if include_actuals and target_col in df.columns:
            result_df = result_df.with_columns(
                [
                    df[target_col].alias("actual_price"),
                    (df[target_col] - y_pred).abs().alias("error_abs"),
                    ((df[target_col] - y_pred).abs() / df[target_col] * 100).alias("error_pct"),
                ]
            )

        # CSV保存
        result_df.write_csv(path)
        logging.info(f"予測結果を保存しました: {output_path}")
