"""Feature engineering utilities for experiment 005.

This module provides advanced feature engineering capabilities including:
- Interaction features based on financial theory
- Nonlinear transformations
- Domain-specific financial indicators
"""

from typing import Any, Dict, List

import numpy as np
import pandas as pd

from daily_trade.utils.logger import get_logger


class AdvancedFeatureEngineer:
    """Advanced feature engineering for financial time series."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize with feature engineering configuration."""
        self.config = config
        self.logger = get_logger()

    def engineer_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Apply all feature engineering steps."""
        self.logger.info("Starting advanced feature engineering")

        df_engineered = df.copy()

        # 1. Lag features (time series)
        if "lag_features" in self.config:
            df_engineered = self._add_lag_features(df_engineered)

        # 2. Interaction features
        if "interaction_features" in self.config:
            df_engineered = self._add_interaction_features(df_engineered)

        # 3. Nonlinear transformations
        if "nonlinear_transforms" in self.config:
            df_engineered = self._add_nonlinear_transforms(df_engineered)

        # 4. Domain-specific features
        if "domain_features" in self.config:
            df_engineered = self._add_domain_features(df_engineered)

        self.logger.info(f"Feature engineering completed. Shape: {df_engineered.shape}")
        return df_engineered

    def _add_lag_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add lag features for time series analysis."""
        lag_config = self.config["lag_features"]

        # Ensure data is sorted by timestamp and symbol
        df = df.sort_values(["symbol", "timestamp"]).reset_index(drop=True)

        lag_features = lag_config.get("features", [])
        lag_periods = lag_config.get("periods", [1, 2, 3, 5])

        for feature in lag_features:
            if feature not in df.columns:
                self.logger.warning(f"Skipping lag feature {feature}: column not found")
                continue

            for lag in lag_periods:
                lag_col_name = f"{feature}_lag_{lag}"
                # Create lag within each symbol group
                df[lag_col_name] = df.groupby("symbol")[feature].shift(lag)
                self.logger.info(f"Added lag feature: {lag_col_name}")

        # Add rolling statistics for lag features
        if lag_config.get("rolling_stats", False):
            window_sizes = lag_config.get("rolling_windows", [3, 5, 10])

            for feature in lag_features:
                if feature not in df.columns:
                    continue

                for window in window_sizes:
                    # Rolling mean
                    rolling_mean_name = f"{feature}_rolling_mean_{window}"
                    df[rolling_mean_name] = (
                        df.groupby("symbol")[feature]
                        .rolling(window=window, min_periods=1)
                        .mean()
                        .reset_index(0, drop=True)
                    )

                    # Rolling std
                    rolling_std_name = f"{feature}_rolling_std_{window}"
                    df[rolling_std_name] = (
                        df.groupby("symbol")[feature]
                        .rolling(window=window, min_periods=1)
                        .std()
                        .reset_index(0, drop=True)
                    )

                    self.logger.info(f"Added rolling features: {rolling_mean_name}, {rolling_std_name}")

        # Add momentum features (rate of change)
        if lag_config.get("momentum_features", False):
            momentum_periods = lag_config.get("momentum_periods", [2, 5, 10])

            for feature in lag_features:
                if feature not in df.columns:
                    continue

                for period in momentum_periods:
                    momentum_name = f"{feature}_momentum_{period}"
                    lag_feature = df.groupby("symbol")[feature].shift(period)
                    df[momentum_name] = (df[feature] - lag_feature) / (lag_feature + 1e-8)
                    self.logger.info(f"Added momentum feature: {momentum_name}")

        return df

    def _add_interaction_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add interaction features based on financial theory."""
        interactions = self.config["interaction_features"]

        for feature_pair in interactions:
            if len(feature_pair) != 2:
                continue

            feat1, feat2 = feature_pair
            if feat1 not in df.columns or feat2 not in df.columns:
                self.logger.warning(f"Skipping interaction {feat1} x {feat2}: missing columns")
                continue

            # Multiplicative interaction
            interaction_name = f"{feat1}_x_{feat2}"
            df[interaction_name] = df[feat1] * df[feat2]

            # Ratio interaction (avoid division by zero)
            ratio_name = f"{feat1}_div_{feat2}"
            df[ratio_name] = df[feat1] / (df[feat2] + 1e-8)

            self.logger.info(f"Added interaction features: {interaction_name}, {ratio_name}")

        return df

    def _add_nonlinear_transforms(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add nonlinear transformations."""
        transforms = self.config["nonlinear_transforms"]

        # Log transformation
        if "log_features" in transforms:
            for feature in transforms["log_features"]:
                if feature not in df.columns:
                    continue

                # Ensure positive values for log
                positive_values = df[feature] + 1e-8
                df[f"{feature}_log"] = np.log(np.abs(positive_values))
                self.logger.info(f"Added log transform: {feature}_log")

        # Square root transformation
        if "sqrt_features" in transforms:
            for feature in transforms["sqrt_features"]:
                if feature not in df.columns:
                    continue

                # Ensure non-negative values for sqrt
                non_negative = np.abs(df[feature])
                df[f"{feature}_sqrt"] = np.sqrt(non_negative)
                self.logger.info(f"Added sqrt transform: {feature}_sqrt")

        # Rank transformation
        if "rank_features" in transforms:
            for feature in transforms["rank_features"]:
                if feature not in df.columns:
                    continue

                # Apply rank transformation within each symbol
                df[f"{feature}_rank"] = df.groupby("symbol")[feature].rank(pct=True)
                self.logger.info(f"Added rank transform: {feature}_rank")

        return df

    def _add_domain_features(self, df: pd.DataFrame) -> pd.DataFrame:
        """Add domain-specific financial features."""
        domain_config = self.config["domain_features"]

        # Momentum strength: deviation from RSI neutral (50)
        if domain_config.get("momentum_strength", False):
            if "rsi_14" in df.columns:
                df["momentum_strength"] = np.abs(df["rsi_14"] - 50)
                self.logger.info("Added momentum_strength feature")

        # Volatility regime: percentile rank of ATR
        if domain_config.get("volatility_regime", False):
            if "atr_pct_14" in df.columns:
                df["volatility_regime"] = df.groupby("symbol")["atr_pct_14"].rank(pct=True)
                self.logger.info("Added volatility_regime feature")

        # Trend consistency: alignment between slope and MACD
        if domain_config.get("trend_consistency", False):
            if all(col in df.columns for col in ["slope_pct_20", "macd"]):
                slope_sign = np.sign(df["slope_pct_20"])
                macd_sign = np.sign(df["macd"])
                df["trend_consistency"] = (slope_sign == macd_sign).astype(int)
                self.logger.info("Added trend_consistency feature")

        # Volume spike: significant volume increase
        if domain_config.get("volume_spike", False):
            if "vol_ratio_20" in df.columns:
                df["volume_spike"] = (df["vol_ratio_20"] > 2.0).astype(int)
                self.logger.info("Added volume_spike feature")

        # Oversold condition
        if domain_config.get("oversold_oversold", False):
            if "rsi_14" in df.columns:
                df["oversold"] = (df["rsi_14"] < 30).astype(int)
                self.logger.info("Added oversold feature")

        # Overbought condition
        if domain_config.get("overbought", False):
            if "rsi_14" in df.columns:
                df["overbought"] = (df["rsi_14"] > 70).astype(int)
                self.logger.info("Added overbought feature")

        # Technical score: composite of multiple indicators
        if domain_config.get("technical_score", False):
            self._add_technical_score(df)

        # Risk score: composite of volatility measures
        if domain_config.get("risk_score", False):
            self._add_risk_score(df)

        return df

    def _add_technical_score(self, df: pd.DataFrame) -> None:
        """Add composite technical score."""
        score_components = []

        # RSI component (0-1, neutral at 0.5)
        if "rsi_14" in df.columns:
            rsi_norm = df["rsi_14"] / 100
            score_components.append(rsi_norm)

        # MACD component (normalized)
        if "macd" in df.columns:
            macd_rank = df.groupby("symbol")["macd"].rank(pct=True)
            score_components.append(macd_rank)

        # Bollinger position component
        if "bb_pband_20" in df.columns:
            score_components.append(df["bb_pband_20"])

        # Stochastic component
        if "stoch_k" in df.columns:
            stoch_norm = df["stoch_k"] / 100
            score_components.append(stoch_norm)

        if score_components:
            df["technical_score"] = np.mean(score_components, axis=0)
            self.logger.info("Added technical_score feature")

    def _add_risk_score(self, df: pd.DataFrame) -> None:
        """Add composite risk score."""
        risk_components = []

        # ATR component (normalized by symbol)
        if "atr_pct_14" in df.columns:
            atr_rank = df.groupby("symbol")["atr_pct_14"].rank(pct=True)
            risk_components.append(atr_rank)

        # Standard deviation component
        if "stdev_20" in df.columns:
            stdev_rank = df.groupby("symbol")["stdev_20"].rank(pct=True)
            risk_components.append(stdev_rank)

        # Bollinger width component
        if "bb_width_20" in df.columns:
            bb_width_rank = df.groupby("symbol")["bb_width_20"].rank(pct=True)
            risk_components.append(bb_width_rank)

        if risk_components:
            df["risk_score"] = np.mean(risk_components, axis=0)
            self.logger.info("Added risk_score feature")


class FeatureSelector:
    """Feature selection utilities."""

    def __init__(self, config: Dict[str, Any]):
        """Initialize with feature selection configuration."""
        self.config = config
        self.logger = get_logger()

    def select_features(self, df: pd.DataFrame, feature_cols: List[str]) -> List[str]:
        """Apply feature selection steps."""
        self.logger.info(f"Starting feature selection from {len(feature_cols)} features")

        selected_features = feature_cols.copy()

        # 1. Exclude predefined features
        if "exclude_features" in self.config:
            excluded = self.config["exclude_features"]
            selected_features = [f for f in selected_features if f not in excluded]
            self.logger.info(f"Excluded {len(excluded)} predefined features")

        # 2. Correlation filtering
        if "correlation_threshold" in self.config:
            selected_features = self._correlation_filter(df, selected_features)

        self.logger.info(f"Feature selection completed: {len(selected_features)} features selected")
        return selected_features

    def _correlation_filter(self, df: pd.DataFrame, features: List[str]) -> List[str]:
        """Remove highly correlated features."""
        threshold = self.config["correlation_threshold"]

        # Calculate correlation matrix for available features
        available_features = [f for f in features if f in df.columns]
        if len(available_features) < 2:
            return available_features

        corr_matrix = df[available_features].corr().abs()

        # Find highly correlated pairs
        to_remove = set()
        for i in range(len(corr_matrix.columns)):
            for j in range(i + 1, len(corr_matrix.columns)):
                if corr_matrix.iloc[i, j] > threshold:
                    # Remove the feature with lower variance (more likely to be redundant)
                    var_i = df[corr_matrix.columns[i]].var()
                    var_j = df[corr_matrix.columns[j]].var()

                    if var_i < var_j:
                        to_remove.add(corr_matrix.columns[i])
                    else:
                        to_remove.add(corr_matrix.columns[j])

        selected_features = [f for f in available_features if f not in to_remove]
        self.logger.info(f"Removed {len(to_remove)} highly correlated features (threshold={threshold})")

        return selected_features
