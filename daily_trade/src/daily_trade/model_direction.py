"""DirectionModel - 翌日上昇確率予測モデル.

LightGBMを使用した二値分類モデルで、特徴量から翌日の株価上昇確率を予測します。
TimeSeriesSplitによる交差検証でモデルの汎化性能を評価します。
"""

from copy import deepcopy
from pathlib import Path
import pickle
from typing import Optional, Union

import lightgbm as lgb
import numpy as np
import pandas as pd
from pydantic import BaseModel, Field
from sklearn.metrics import accuracy_score, average_precision_score, precision_score, recall_score, roc_auc_score
from sklearn.model_selection import TimeSeriesSplit

from .utils.logger import AppLogger


class ModelConfig(BaseModel):
    """DirectionModel設定."""

    # LightGBMパラメータ
    class LightGBMParams(BaseModel):
        num_leaves: int = Field(default=31, description="LightGBMの葉ノード数")
        learning_rate: float = Field(default=0.05, description="学習率")
        feature_fraction: float = Field(default=0.8, description="特徴量サンプリング率")
        bagging_fraction: float = Field(default=0.8, description="データサンプリング率")
        bagging_freq: int = Field(default=5, description="バギング頻度")
        min_child_samples: int = Field(default=20, description="子ノードの最小サンプル数")
        reg_alpha: float = Field(default=0.1, description="L1正則化パラメータ")
        reg_lambda: float = Field(default=0.1, description="L2正則化パラメータ")
        random_state: int = Field(default=42, description="乱数シード")
        n_estimators: int = Field(default=100, description="推定器数")
        early_stopping_rounds: int = Field(default=10, description="早期停止ラウンド数")

    light_gbm_params: LightGBMParams = Field(default_factory=LightGBMParams, description="LightGBMパラメータ")

    # 交差検証
    cv_splits: int = Field(default=5, description="交差検証の分割数")
    test_size_ratio: float = Field(default=0.2, description="テストサイズ比率")

    # 評価
    pos_label: int = Field(default=1, description="ポジティブラベル")
    average: str = Field(default="binary", description="平均化方法")

    # ファイル保存
    model_file: str = Field(default="model.pkl", description="モデルファイル名")

    class Config:
        """Pydantic設定."""

        extra = "forbid"  # 未定義フィールドを禁止
        validate_assignment = True  # 代入時バリデーション


class DirectionModel:
    """翌日上昇確率予測モデル."""

    def __init__(self, config: ModelConfig = None):
        """初期化.

        Args:
            config: モデル設定
        """
        self.config = config or ModelConfig()
        self.logger = AppLogger()
        self.model: Optional[lgb.LGBMClassifier] = None
        self.feature_names: Optional[list[str]] = None
        self.feature_importances_: Optional[dict[str, float]] = None
        self.cv_scores_: Optional[dict[str, list[float]]] = None

    def fit(self, X: pd.DataFrame, y: pd.Series, n_estimators: int) -> "DirectionModel":
        """モデル学習

        Args:
            X: 特徴量データ
            y: ターゲット（0: 下落, 1: 上昇）
            n_estimators: 学習器数

        Returns:
            学習済みモデル
        """
        self.logger.info(f"DirectionModel学習開始: X.shape={X.shape}, y分布={y.value_counts().to_dict()}")

        # 特徴量名保存
        self.feature_names = list(X.columns)

        # データ検証
        self._validate_data(X, y)

        # 欠損値処理
        if X.isnull().any().any():
            self.logger.info("欠損値を前方補完で処理します")
            X = X.ffill().fillna(0)  # 前方補完 → 0埋め

        # LightGBMモデル構築
        lgb_params = self.config.light_gbm_params.model_dump()
        lgb_params["n_estimators"] = n_estimators
        self.model = lgb.LGBMClassifier(objective="binary", metric="auc", **lgb_params, importance_type="gain")

        # 学習実行
        self.model.fit(
            X,
            y,
            # 同じオブジェクトを渡すとvalid aucが計算されないため、deepcopyで回避
            eval_set=[(deepcopy(X), deepcopy(y))],
            callbacks=[
                lgb.early_stopping(lgb_params["early_stopping_rounds"]),
                lgb.log_evaluation(1),
            ],
        )

        # 特徴量重要度計算
        self._calculate_feature_importance()

        self.logger.info(f"DirectionModel学習完了: best_iteration={self.model.best_iteration_}")

        return self

    def predict_proba(self, X: pd.DataFrame) -> np.ndarray:
        """上昇確率予測

        Args:
            X: 特徴量データ

        Returns:
            各クラスの予測確率 (N, 2)
        """
        if self.model is None:
            raise ValueError("モデルが学習されていません。先にfit()を実行してください。")

        # 特徴量順序確認
        if list(X.columns) != self.feature_names:
            self.logger.warning("特徴量の順序が学習時と異なります")
            X = X[self.feature_names]

        return self.model.predict_proba(X)

    def predict(self, X: pd.DataFrame) -> np.ndarray:
        """予測ラベル取得

        Args:
            X: 特徴量データ

        Returns:
            予測ラベル (0: 下落, 1: 上昇)
        """
        return self.model.predict(X)

    def evaluate(self, X: pd.DataFrame, y: pd.Series) -> dict[str, float]:
        """モデル評価

        Args:
            X: 特徴量データ
            y: 正解ラベル

        Returns:
            評価指標辞書
        """
        if self.model is None:
            raise ValueError("モデルが学習されていません。先にfit()を実行してください。")

        # 予測実行
        y_pred = self.predict(X)
        y_proba = self.predict_proba(X)[:, 1]  # 上昇確率

        # 評価指標計算
        metrics = {
            "auc": roc_auc_score(y, y_proba),
            "accuracy": accuracy_score(y, y_pred),
            "precision": precision_score(y, y_pred, average=self.config.average, zero_division=0),
            "recall": recall_score(y, y_pred, average=self.config.average, zero_division=0),
            "average_precision": average_precision_score(y, y_proba),
            "n_samples": len(y),
            "pos_ratio": y.mean(),
        }

        self.logger.info(f"評価結果: AUC={metrics['auc']:.3f}, Accuracy={metrics['accuracy']:.3f}")

        return metrics

    def cross_validate(self, X: pd.DataFrame, y: pd.Series, symbols: pd.Series) -> dict[str, list[float]]:
        """TimeSeriesSplit交差検証

        Args:
            X: 特徴量データ
            y: ターゲット
            symbols: 銘柄シンボルデータ

        Returns:
            各FoldのスコアDict
        """
        self.logger.info(f"TimeSeriesSplit交差検証開始: {self.config.cv_splits}分割")

        # 時系列分割
        tscv = TimeSeriesSplit(n_splits=self.config.cv_splits)

        scores = {
            "auc": [],
            "accuracy": [],
            "precision": [],
            "recall": [],
            "average_precision": [],
            "best_iteration": [],
        }
        symbol_scores = []
        for fold, (train_idx, val_idx) in enumerate(tscv.split(X)):
            self.logger.info(f"Fold {fold + 1}/{self.config.cv_splits}: train={len(train_idx)}, val={len(val_idx)}")

            # データ分割
            X_train, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_train, y_val = y.iloc[train_idx], y.iloc[val_idx]
            symbol_val = symbols.iloc[val_idx]

            # モデル学習
            lgb_params = self.config.light_gbm_params.model_dump()
            fold_model = lgb.LGBMClassifier(
                objective="binary", metric="auc", **lgb_params, importance_type="gain", verbose=-1
            )

            fold_model.fit(
                X_train,
                y_train,
                eval_set=[(X_val, y_val)],
                callbacks=[
                    lgb.early_stopping(lgb_params["early_stopping_rounds"]),
                    lgb.log_evaluation(0),
                ],
            )

            # 検証
            y_pred = fold_model.predict(X_val)
            y_proba = fold_model.predict_proba(X_val)[:, 1]

            # スコア計算
            fold_scores = {
                "auc": roc_auc_score(y_val, y_proba),
                "accuracy": accuracy_score(y_val, y_pred),
                "precision": precision_score(y_val, y_pred, average=self.config.average, zero_division=0),
                "recall": recall_score(y_val, y_pred, average=self.config.average, zero_division=0),
                "average_precision": average_precision_score(y_val, y_proba),
                "best_iteration": fold_model.best_iteration_,
            }

            for symbol in sorted(symbol_val.unique()):
                symbol_mask = symbol_val == symbol
                symbol_y_val, symbol_y_pred, symbol_y_proba = (
                    y_val[symbol_mask],
                    y_pred[symbol_mask],
                    y_proba[symbol_mask],
                )
                symbol_scores.append(
                    {
                        "fold": fold + 1,
                        "symbol": symbol,
                        "auc": roc_auc_score(symbol_y_val, symbol_y_proba),
                        "accuracy": accuracy_score(symbol_y_val, symbol_y_pred),
                        "precision": precision_score(
                            symbol_y_val, symbol_y_pred, average=self.config.average, zero_division=0
                        ),
                        "recall": recall_score(
                            symbol_y_val, symbol_y_pred, average=self.config.average, zero_division=0
                        ),
                        "average_precision": average_precision_score(symbol_y_val, symbol_y_proba),
                    }
                )

            # スコア記録
            for metric, score in fold_scores.items():
                scores[metric].append(score)

            self.logger.info(f"Fold {fold + 1} スコア: " + ", ".join([f"{k}={v:.3f}" for k, v in fold_scores.items()]))

        # 平均スコア計算
        mean_scores = {metric: np.mean(values) for metric, values in scores.items()}
        std_scores = {metric: np.std(values) for metric, values in scores.items()}

        # 銘柄別スコア計算
        symbol_df = pd.DataFrame(symbol_scores)

        self.logger.info("交差検証完了:")
        for metric in scores:
            self.logger.info(f"  {metric}: {mean_scores[metric]:.3f} ± {std_scores[metric]:.3f}")

        # スコア保存
        self.cv_scores_ = scores

        return scores, symbol_df

    def get_feature_importance(self, top_n: int = 20) -> dict[str, float]:
        """特徴量重要度取得

        Args:
            top_n: 上位N個の特徴量

        Returns:
            特徴量重要度辞書（降順）
        """
        if self.feature_importances_ is None:
            raise ValueError("特徴量重要度が計算されていません。先にfit()を実行してください。")

        # 上位N個取得
        sorted_importance = sorted(self.feature_importances_.items(), key=lambda x: x[1], reverse=True)

        return dict(sorted_importance[:top_n])

    def save_model(self, file_path: Union[str, Path]) -> None:
        """モデル保存

        Args:
            file_path: 保存先パス
        """
        if self.model is None:
            raise ValueError("保存するモデルがありません。先にfit()を実行してください。")

        save_data = {
            "model": self.model,
            "config": self.config,
            "feature_names": self.feature_names,
            "feature_importances_": self.feature_importances_,
            "cv_scores_": self.cv_scores_,
        }

        with Path.open(file_path, "wb") as f:
            pickle.dump(save_data, f)

        self.logger.info(f"モデル保存完了: {file_path}")

    def load_model(self, file_path: Union[str, Path]) -> "DirectionModel":
        """モデル読み込み

        Args:
            file_path: モデルファイルパス

        Returns:
            読み込み済みモデル
        """
        with Path.open(file_path, "rb") as f:
            save_data = pickle.load(f)

        self.model = save_data["model"]
        self.config = save_data["config"]
        self.feature_names = save_data["feature_names"]
        self.feature_importances_ = save_data.get("feature_importances_")
        self.cv_scores_ = save_data.get("cv_scores_")

        self.logger.info(f"モデル読み込み完了: {file_path}")

        return self

    def _validate_data(self, X: pd.DataFrame, y: pd.Series) -> None:
        """データ検証"""
        # 欠損値チェック（警告のみ）
        null_features = X.isnull().sum()
        if null_features.any():
            self.logger.warning(f"特徴量に欠損値があります: {null_features[null_features > 0].to_dict()}")

        if y.isnull().any():
            raise ValueError("ターゲットに欠損値があります")

        # ターゲット値チェック
        unique_y = set(y.unique())
        if not unique_y.issubset({0, 1}):
            raise ValueError(f"ターゲットは0,1のみ対応しています: {unique_y}")

        # サンプル数チェック
        if len(X) < 100:
            self.logger.warning(f"サンプル数が少ないです: {len(X)}")

        # クラス不均衡チェック
        pos_ratio = y.mean()
        if pos_ratio < 0.1 or pos_ratio > 0.9:
            self.logger.warning(f"クラス不均衡があります: pos_ratio={pos_ratio:.3f}")

    def _calculate_feature_importance(self) -> None:
        """特徴量重要度計算"""
        if self.model is None or self.feature_names is None:
            return

        importances = self.model.feature_importances_
        self.feature_importances_ = dict(zip(self.feature_names, importances))

        # ログ出力
        top_features = self.get_feature_importance(top_n=10)
        self.logger.info("主要特徴量:")
        for feature, importance in top_features.items():
            self.logger.info(f"  {feature}: {importance:.3f}")
