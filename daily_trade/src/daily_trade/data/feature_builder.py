"""FeatureBuilder for generating technical indicators from OHLCV data.

This module provides the FeatureBuilder class for creating technical analysis
features from stock price data.
"""

from dataclasses import dataclass

import numpy as np
import pandas as pd
import ta

from daily_trade.utils.logger import get_logger


@dataclass
class FeatureConfig:
    """Configuration class for FeatureBuilder."""

    # Moving Averages
    sma_windows: list[int] = None
    ema_windows: list[int] = None

    # Volatility indicators
    atr_window: int = 14
    stdev_window: int = 20

    # Volume indicators
    volume_ratio_window: int = 20

    # Momentum indicators
    return_windows: list[int] = None

    # Technical indicators
    rsi_window: int = 14
    macd_windows: tuple = (12, 26, 9)
    bollinger_window: int = 20
    bollinger_std: float = 2.0

    # Slope calculation
    slope_window: int = 20

    def __post_init__(self):
        """Set default values for list fields."""
        if self.sma_windows is None:
            self.sma_windows = [5, 10, 20, 50]
        if self.ema_windows is None:
            self.ema_windows = [21]
        if self.return_windows is None:
            self.return_windows = [1, 5, 10]


class FeatureBuilder:
    """
    FeatureBuilder for generating technical indicators from OHLCV data.

    Features:
    - Trend indicators (SMA, EMA, slope)
    - Volatility indicators (ATR, Bollinger Bands, standard deviation)
    - Volume indicators (volume ratio, turnover ratio)
    - Momentum indicators (returns, RSI, MACD)
    - Seasonality features (day of week, month)

    All features use only information up to time t (no future leakage).
    """

    def __init__(self, config: FeatureConfig):
        """
        Initialize FeatureBuilder.

        Args:
            config: FeatureConfig instance with feature generation parameters
        """
        self.config = config
        self.logger = get_logger()

    def build(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        """
        Build technical features from OHLCV data.

        Args:
            df: Preprocessed OHLCV DataFrame

        Returns:
            DataFrame with added technical features
            List of new feature column names
        """
        self.logger.info(f"Start feature building for {len(df)} records")

        if df.empty:
            self.logger.warning("Empty DataFrame provided for feature building")
            return df

        # Make a copy to avoid modifying original data
        df_features = df.copy()

        # Validate required columns
        required_columns = [
            "open",
            "high",
            "low",
            "close",
            "volume",
            "timestamp",
            "symbol",
        ]
        missing_columns = [col for col in required_columns if col not in df_features.columns]
        if missing_columns:
            raise ValueError(f"Missing required columns: {missing_columns}")

        # Use adj_close if available, otherwise use close
        price_column = "adj_close" if "adj_close" in df_features.columns else "close"
        self.logger.info(f"Using {price_column} for price-based calculations")

        # Build features by symbol to ensure no cross-contamination
        feature_frames = []
        for symbol in df_features["symbol"].unique():
            symbol_data = df_features[df_features["symbol"] == symbol].copy()
            symbol_data_with_features, new_columns_ = self._build_features_for_symbol(symbol_data, price_column)
            feature_frames.append(symbol_data_with_features)

        # Combine all symbols
        df_combined = pd.concat(feature_frames, ignore_index=True)

        # Sort by timestamp and symbol
        df_combined = df_combined.sort_values(["timestamp", "symbol"]).reset_index(drop=True)

        new_columns = new_columns_

        self.logger.info(f"Feature building completed: {len(new_columns)} new features generated")
        self.logger.info(f"New features: {sorted(new_columns)}")

        return df_combined, new_columns

    def _build_features_for_symbol(self, df: pd.DataFrame, price_column: str) -> pd.DataFrame:
        """Build features for a single symbol."""
        # Sort by timestamp to ensure proper ordering
        df = df.sort_values("timestamp").reset_index(drop=True)

        feature_columns = ["symbol"]

        # 1. Trend indicators
        df, new_columns = self._add_trend_features(df, price_column)
        feature_columns.extend(new_columns)

        # 2. Volatility indicators
        df, new_columns = self._add_volatility_features(df, price_column)
        feature_columns.extend(new_columns)

        # 3. Volume indicators
        df, new_columns = self._add_volume_features(df, price_column)
        feature_columns.extend(new_columns)

        # 4. Momentum indicators
        df, new_columns = self._add_momentum_features(df, price_column)
        feature_columns.extend(new_columns)

        # 5. Technical indicators
        df, new_columns = self._add_technical_features(df)
        feature_columns.extend(new_columns)

        # 6. Seasonality features
        df, new_columns = self._add_seasonality_features(df)
        feature_columns.extend(new_columns)

        # 7. Flag leading NaNs
        df = self._flag_leading_nans(df, feature_columns)

        self.logger.info(f"Total new features for symbol {df['symbol'].iloc[0]}: {feature_columns}")

        return df, feature_columns

    def _add_trend_features(self, df: pd.DataFrame, price_column: str) -> tuple[pd.DataFrame, list[str]]:
        """Add trend-based features."""
        price_series = df[price_column]

        prev_columns = df.columns.tolist()

        # Simple Moving Averages
        for window in self.config.sma_windows:
            df[f"sma_{window}"] = ta.trend.SMAIndicator(close=price_series, window=window).sma_indicator()

        # Exponential Moving Averages
        for window in self.config.ema_windows:
            df[f"ema_{window}"] = ta.trend.EMAIndicator(close=price_series, window=window).ema_indicator()

        # Price slope (linear regression slope)
        df[f"slope_{self.config.slope_window}"] = self._calculate_slope(price_series, self.config.slope_window)

        # Slope as percentage
        df[f"slope_pct_{self.config.slope_window}"] = df[f"slope_{self.config.slope_window}"] / price_series

        post_columns = df.columns.tolist()
        new_columns = sorted(set(post_columns) - set(prev_columns))
        self.logger.info(f"New features added in _add_trend_features: {sorted(new_columns)}")

        return df, new_columns

    def _add_volatility_features(self, df: pd.DataFrame, price_column: str) -> tuple[pd.DataFrame, list[str]]:
        """Add volatility-based features."""
        prev_columns = df.columns.tolist()

        # Average True Range
        atr_indicator = ta.volatility.AverageTrueRange(
            high=df["high"],
            low=df["low"],
            close=df["close"],
            window=self.config.atr_window,
        )
        df[f"atr_{self.config.atr_window}"] = atr_indicator.average_true_range()

        # ATR as percentage of price
        df[f"atr_pct_{self.config.atr_window}"] = df[f"atr_{self.config.atr_window}"] / df["close"]

        # Rolling standard deviation of returns
        returns = df[price_column].pct_change()
        df[f"stdev_{self.config.stdev_window}"] = returns.rolling(window=self.config.stdev_window, min_periods=1).std()

        # Bollinger Bands
        bollinger = ta.volatility.BollingerBands(
            close=df[price_column],
            window=self.config.bollinger_window,
            window_dev=self.config.bollinger_std,
        )
        df[f"bb_upper_{self.config.bollinger_window}"] = bollinger.bollinger_hband()
        df[f"bb_lower_{self.config.bollinger_window}"] = bollinger.bollinger_lband()
        df[f"bb_middle_{self.config.bollinger_window}"] = bollinger.bollinger_mavg()
        df[f"bb_width_{self.config.bollinger_window}"] = bollinger.bollinger_wband()
        df[f"bb_pband_{self.config.bollinger_window}"] = bollinger.bollinger_pband()

        post_columns = df.columns.tolist()
        new_columns = sorted(set(post_columns) - set(prev_columns))
        self.logger.info(f"New features added in _add_volatility_features: {sorted(new_columns)}")

        return df, new_columns

    def _add_volume_features(self, df: pd.DataFrame, price_column: str) -> tuple[pd.DataFrame, list[str]]:
        """Add volume-based features."""
        prev_columns = df.columns.tolist()

        # Volume ratio (current volume / average volume)
        df[f"vol_ratio_{self.config.volume_ratio_window}"] = (
            df["volume"] / df["volume"].rolling(window=self.config.volume_ratio_window, min_periods=1).mean()
        )

        # Turnover ratio (turnover / average turnover)
        turnover = df[price_column] * df["volume"]
        df[f"tov_ratio_{self.config.volume_ratio_window}"] = (
            turnover / turnover.rolling(window=self.config.volume_ratio_window, min_periods=1).mean()
        )

        # Volume-Price Trend (VPT)
        df["vpt"] = ta.volume.VolumePriceTrendIndicator(
            close=df[price_column], volume=df["volume"]
        ).volume_price_trend()

        # On-Balance Volume (OBV)
        df["obv"] = ta.volume.OnBalanceVolumeIndicator(close=df[price_column], volume=df["volume"]).on_balance_volume()
        post_columns = df.columns.tolist()
        new_columns = sorted(set(post_columns) - set(prev_columns))
        self.logger.info(f"New features added in _add_volume_features: {sorted(new_columns)}")

        return df, new_columns

    def _add_momentum_features(self, df: pd.DataFrame, price_column: str) -> tuple[pd.DataFrame, list[str]]:
        """Add momentum-based features."""
        prev_columns = df.columns.tolist()

        # Price returns for different periods
        for window in self.config.return_windows:
            df[f"ret_{window}d"] = df[price_column].pct_change(periods=window)

        # RSI (Relative Strength Index)
        df[f"rsi_{self.config.rsi_window}"] = ta.momentum.RSIIndicator(
            close=df[price_column], window=self.config.rsi_window
        ).rsi()

        # MACD
        macd_fast, macd_slow, macd_signal = self.config.macd_windows
        macd_indicator = ta.trend.MACD(
            close=df[price_column],
            window_fast=macd_fast,
            window_slow=macd_slow,
            window_sign=macd_signal,
        )
        df["macd"] = macd_indicator.macd()
        df["macd_signal"] = macd_indicator.macd_signal()
        df["macd_hist"] = macd_indicator.macd_diff()

        # Stochastic Oscillator
        stoch_indicator = ta.momentum.StochasticOscillator(high=df["high"], low=df["low"], close=df["close"])
        df["stoch_k"] = stoch_indicator.stoch()
        df["stoch_d"] = stoch_indicator.stoch_signal()

        post_columns = df.columns.tolist()
        new_columns = sorted(set(post_columns) - set(prev_columns))
        self.logger.info(f"New features added in _add_momentum_features: {sorted(new_columns)}")

        return df, new_columns

    def _add_technical_features(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        """Add additional technical indicators."""
        prev_columns = df.columns.tolist()

        # Check if we have enough data for indicators
        min_periods_required = 14  # Most indicators need at least 14 periods

        if len(df) < min_periods_required:
            self.logger.warning(f"Insufficient data ({len(df)} periods) for some technical indicators. Skipping...")
            # Add placeholder columns with NaN
            df["williams_r"] = np.nan
            df["cci"] = np.nan
            df["adx"] = np.nan
            df["adx_pos"] = np.nan
            df["adx_neg"] = np.nan
            return df

        try:
            # Williams %R
            df["williams_r"] = ta.momentum.WilliamsRIndicator(
                high=df["high"], low=df["low"], close=df["close"]
            ).williams_r()
        except Exception as e:
            self.logger.warning(f"Failed to calculate Williams %R: {e}")
            df["williams_r"] = np.nan

        try:
            # Commodity Channel Index (CCI)
            df["cci"] = ta.trend.CCIIndicator(high=df["high"], low=df["low"], close=df["close"]).cci()
        except Exception as e:
            self.logger.warning(f"Failed to calculate CCI: {e}")
            df["cci"] = np.nan

        try:
            # Average Directional Index (ADX)
            adx_indicator = ta.trend.ADXIndicator(high=df["high"], low=df["low"], close=df["close"])
            df["adx"] = adx_indicator.adx()
            df["adx_pos"] = adx_indicator.adx_pos()
            df["adx_neg"] = adx_indicator.adx_neg()
        except Exception as e:
            self.logger.warning(f"Failed to calculate ADX: {e}")
            df["adx"] = np.nan
            df["adx_pos"] = np.nan
            df["adx_neg"] = np.nan

        post_columns = df.columns.tolist()
        new_columns = sorted(set(post_columns) - set(prev_columns))
        self.logger.info(f"New features added in _add_technical_features: {sorted(new_columns)}")

        return df, new_columns

    def _add_seasonality_features(self, df: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
        """Add seasonality features."""
        prev_columns = df.columns.tolist()

        # Day of week (0=Monday, 6=Sunday)
        df["dow"] = df["timestamp"].dt.weekday

        # Month (1-12) 非定常のため廃止
        # df["month"] = df["timestamp"].dt.month

        # Quarter (1-4) 非定常のため廃止
        # df["quarter"] = df["timestamp"].dt.quarter

        # Day of month (1-31)
        df["day_of_month"] = df["timestamp"].dt.day

        # 前日がデータにあるか
        prev_series = df["timestamp"].shift(1)
        df["prev_day"] = prev_series == (df["timestamp"] - pd.Timedelta(days=1))

        # 翌日がデータにあるか
        next_series = df["timestamp"].shift(-1)
        df["next_day"] = next_series == (df["timestamp"] + pd.Timedelta(days=1))

        post_columns = df.columns.tolist()
        new_columns = sorted(set(post_columns) - set(prev_columns))
        self.logger.info(f"New features added in _add_seasonality_features: {sorted(new_columns)}")

        return df, new_columns

    def _calculate_slope(self, price_series: pd.Series, window: int) -> pd.Series:
        """Calculate rolling linear regression slope."""

        def rolling_slope(x):
            if len(x) < 2:
                return np.nan
            # Use simple difference approximation for speed
            return (x.iloc[-1] - x.iloc[0]) / len(x)

        return price_series.rolling(window=window, min_periods=2).apply(rolling_slope, raw=False)

    def _flag_leading_nans(self, df: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
        """先頭からNanが続く限りTrueとなるフラグを追加"""
        is_leading_nan_columns = []
        for col in feature_columns:
            nan_mask = df[col].isna()
            leading_nan_mask = nan_mask.cumprod().astype(bool)
            df[f"{col}_is_leading_nan"] = leading_nan_mask
            is_leading_nan_columns.append(f"{col}_is_leading_nan")

        contains_leading_nan = df[is_leading_nan_columns].any(axis=1)
        df["contains_leading_nan"] = contains_leading_nan
        df.drop(columns=is_leading_nan_columns, inplace=True)

        return df
