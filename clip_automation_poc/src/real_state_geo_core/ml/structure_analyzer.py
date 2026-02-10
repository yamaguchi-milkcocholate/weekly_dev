"""構造分析: LightGBMによる立地・物件スペックの影響度分析"""

import logging

from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import polars as pl

from sklearn.metrics import mean_absolute_error, mean_squared_error


class StructureAnalyzer:
    """
    LightGBMを使用して、立地・物件スペックが坪単価に与える影響を分析します。
    時系列要素を除いた純粋な構造分析を行います。
    """

    def __init__(self, random_state: int = 42):
        """
        Args:
            random_state (int, optional): 乱数シード。デフォルトは42。
        """
        self.random_state = random_state
        self.model: lgb.LGBMRegressor | None = None
        self.feature_importance_df: pd.DataFrame | None = None
        self.categorical_features: list[str] = []

    def fit(
        self,
        X: pl.DataFrame,
        y: pl.Series,
        categorical_cols: list[str] | None = None,
        lgbm_params: dict | None = None,
    ) -> None:
        """
        LightGBMモデルを学習します。

        Args:
            X (pl.DataFrame): 特徴量DataFrame。
            y (pl.Series): 目的変数Series（坪単価）。
            categorical_cols (list[str], optional): カテゴリカル変数のリスト。
            lgbm_params (dict, optional): LightGBMのパラメータ。
        """
        if categorical_cols is None:
            # デフォルトのカテゴリカル変数
            categorical_cols = [
                "NearestStation",
                "DistrictName",
                "Municipality",
                "Structure",
                "CityPlanning",
                "Renovation",
                "FloorPlan",
            ]

        self.categorical_features = [col for col in categorical_cols if col in X.columns]

        # Polars → Pandas変換（LightGBMはPandas推奨）
        X_pd = X.to_pandas()
        y_pd = y.to_pandas()

        # カテゴリカル変数を'category'型に変換
        for col in self.categorical_features:
            if col in X_pd.columns:
                X_pd[col] = X_pd[col].astype("category")

        # LightGBMパラメータ設定
        if lgbm_params is None:
            lgbm_params = {
                "objective": "regression",
                "metric": "rmse",
                "verbosity": -1,
                "random_state": self.random_state,
                "n_estimators": 500,
                "learning_rate": 0.05,
                "max_depth": 8,
                "num_leaves": 31,
                "min_child_samples": 20,
                "subsample": 0.8,
                "colsample_bytree": 0.8,
                "reg_alpha": 0.1,
                "reg_lambda": 0.1,
            }

        logging.info("LightGBMモデル学習開始")
        self.model = lgb.LGBMRegressor(**lgbm_params)
        self.model.fit(X_pd, y_pd, categorical_feature=self.categorical_features)
        logging.info("LightGBMモデル学習完了")

        # 特徴量重要度を取得
        self._calculate_feature_importance(X_pd)

    def predict(self, X: pl.DataFrame) -> pl.Series:
        """
        学習済みモデルで予測を行います。

        Args:
            X (pl.DataFrame): 特徴量DataFrame。

        Returns:
            pl.Series: 予測値。

        Raises:
            ValueError: モデルが学習されていない場合。
        """
        if self.model is None:
            raise ValueError("モデルが学習されていません。fit()を先に実行してください。")

        X_pd = X.to_pandas()

        # カテゴリカル変数を'category'型に変換
        for col in self.categorical_features:
            if col in X_pd.columns:
                X_pd[col] = X_pd[col].astype("category")

        predictions = self.model.predict(X_pd)
        return pl.Series(predictions)

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

    def _calculate_feature_importance(self, X_pd: pd.DataFrame) -> None:
        """
        特徴量重要度を計算し、DataFrameとして保存します。

        Args:
            X_pd (pd.DataFrame): 特徴量のPandas DataFrame。
        """
        if self.model is None:
            return

        importance_gain = self.model.booster_.feature_importance(importance_type="gain")
        importance_split = self.model.booster_.feature_importance(importance_type="split")

        self.feature_importance_df = pd.DataFrame(
            {
                "feature_name": X_pd.columns,
                "importance_gain": importance_gain,
                "importance_split": importance_split,
            }
        )

        # 重要度でソート
        self.feature_importance_df = self.feature_importance_df.sort_values(
            "importance_gain", ascending=False
        ).reset_index(drop=True)

        # カテゴリ分類を追加
        def categorize_feature(feature_name: str) -> str:
            """特徴量を「Location」「Property」「Macro」に分類"""
            location_keywords = ["Station", "District", "Municipality", "Planning"]
            property_keywords = ["Area", "Age", "Building", "Structure", "Floor", "Renovation"]

            if any(kw in feature_name for kw in location_keywords):
                return "Location"
            elif any(kw in feature_name for kw in property_keywords):
                return "Property"
            else:
                return "Macro"

        self.feature_importance_df["category"] = self.feature_importance_df["feature_name"].apply(categorize_feature)

        logging.info("特徴量重要度の計算完了")

    def save_feature_importance(self, output_path: str) -> None:
        """
        特徴量重要度をCSVファイルとして保存します。

        Args:
            output_path (str): 出力先ファイルパス。

        Raises:
            ValueError: 特徴量重要度が計算されていない場合。
        """
        if self.feature_importance_df is None:
            raise ValueError("特徴量重要度が計算されていません。fit()を先に実行してください。")

        path = Path(output_path)
        path.parent.mkdir(parents=True, exist_ok=True)

        # importance_gain を importance にリネーム
        output_df = self.feature_importance_df[["feature_name", "importance_gain", "category"]].copy()
        output_df.columns = ["feature_name", "importance", "category"]

        output_df.to_csv(path, index=False)
        logging.info(f"特徴量重要度を保存しました: {output_path}")

    def get_top_features(self, n: int = 10) -> pd.DataFrame:
        """
        上位N個の重要な特徴量を取得します。

        Args:
            n (int, optional): 取得する特徴量の数。デフォルトは10。

        Returns:
            pd.DataFrame: 上位N個の特徴量のDataFrame。

        Raises:
            ValueError: 特徴量重要度が計算されていない場合。
        """
        if self.feature_importance_df is None:
            raise ValueError("特徴量重要度が計算されていません。fit()を先に実行してください。")

        return self.feature_importance_df.head(n)
