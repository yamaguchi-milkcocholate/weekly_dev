"""Preprocessor for cleaning and standardizing OHLCV data.

This module provides the Preprocessor class for data cleaning, outlier handling,
and quality validation.
"""

from dataclasses import dataclass
from typing import Dict

import pandas as pd
from scipy import stats

from ..utils.logger import get_logger


@dataclass
class PreprocessConfig:
    """Configuration class for Preprocessor."""

    remove_zero_volume: bool = True
    winsorize_enabled: bool = True
    winsorize_limits: tuple = (0.01, 0.99)  # 1st and 99th percentiles
    outlier_detection_window: int = 60  # days for outlier detection
    outlier_threshold: float = 10.0  # sigma threshold
    min_trading_days: int = 20  # minimum trading days required per symbol


class Preprocessor:
    """
    Preprocessor for cleaning and standardizing OHLCV data.

    Features:
    - Remove zero volume days
    - Outlier detection and winsorization
    - Data validation and quality checks
    - Timestamp sorting and duplicate removal
    - Corporate action detection
    """

    def __init__(self, config: PreprocessConfig):
        """
        Initialize Preprocessor.

        Args:
            config: PreprocessConfig instance with preprocessing parameters
        """
        self.config = config
        self.logger = get_logger()

    def clean(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Clean and preprocess the OHLCV data.

        Args:
            df: Raw OHLCV DataFrame from DataLoader

        Returns:
            Cleaned and preprocessed DataFrame
        """
        self.logger.info(f"Start preprocessing {len(df)} records")

        if df.empty:
            self.logger.warning("Empty DataFrame provided for preprocessing")
            return df

        # Make a copy to avoid modifying original data
        df_clean = df.copy()

        # 1. Sort by timestamp and symbol
        df_clean = self._sort_data(df_clean)

        # 2. Remove duplicates
        df_clean = self._remove_duplicates(df_clean)

        # 3. Remove zero volume days
        if self.config.remove_zero_volume:
            df_clean = self._remove_zero_volume(df_clean)

        # 4. Detect and handle outliers
        if self.config.winsorize_enabled:
            df_clean = self._handle_outliers(df_clean)

        # 5. Validate minimum trading days
        df_clean = self._validate_min_trading_days(df_clean)

        # 6. Final validation
        self._final_validation(df_clean)

        self.logger.info(f"Preprocessing completed: {len(df_clean)} records remaining")

        return df_clean

    def _sort_data(self, df: pd.DataFrame) -> pd.DataFrame:
        """Sort data by timestamp and symbol."""
        return df.sort_values(["timestamp", "symbol"]).reset_index(drop=True)

    def _remove_duplicates(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove duplicate records."""
        before_count = len(df)
        df_clean = df.drop_duplicates(subset=["timestamp", "symbol"], keep="first")
        after_count = len(df_clean)

        if before_count != after_count:
            removed = before_count - after_count
            self.logger.warning(f"Removed {removed} duplicate records")

        return df_clean.reset_index(drop=True)

    def _remove_zero_volume(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove days with zero volume."""
        if "volume" not in df.columns:
            self.logger.warning("Volume column not found, skipping zero volume removal")
            return df

        before_count = len(df)
        df_clean = df[df["volume"] > 0].copy()
        after_count = len(df_clean)

        if before_count != after_count:
            removed = before_count - after_count
            self.logger.info(f"Removed {removed} zero volume records")

            # Log by symbol
            zero_volume_by_symbol = df[df["volume"] == 0]["symbol"].value_counts()
            for symbol, count in zero_volume_by_symbol.items():
                self.logger.info(f"  {symbol}: {count} zero volume days removed")

        return df_clean.reset_index(drop=True)

    def _handle_outliers(self, df: pd.DataFrame) -> pd.DataFrame:
        """Detect and handle outliers using winsorization."""
        df_clean = df.copy()

        price_columns = ["open", "high", "low", "close", "adj_close"]
        available_price_cols = [col for col in price_columns if col in df.columns]

        if not available_price_cols:
            self.logger.warning("No price columns found for outlier handling")
            return df_clean

        # Process each symbol separately
        for symbol in df_clean["symbol"].unique():
            symbol_mask = df_clean["symbol"] == symbol
            symbol_data = df_clean[symbol_mask].copy()

            if len(symbol_data) < self.config.outlier_detection_window:
                continue

            # Detect outliers and apply winsorization
            for col in available_price_cols:
                original_values = symbol_data[col].copy()

                # Calculate rolling statistics for outlier detection
                rolling_median = original_values.rolling(
                    window=self.config.outlier_detection_window, min_periods=10
                ).median()
                rolling_std = original_values.rolling(window=self.config.outlier_detection_window, min_periods=10).std()

                # Detect extreme outliers
                outlier_threshold = self.config.outlier_threshold
                upper_bound = rolling_median + outlier_threshold * rolling_std
                lower_bound = rolling_median - outlier_threshold * rolling_std

                outliers = (original_values > upper_bound) | (original_values < lower_bound)
                outlier_count = outliers.sum()

                if outlier_count > 0:
                    self.logger.warning(f"Found {outlier_count} outliers in {col} for {symbol}")

                    # Apply winsorization to the entire series
                    winsorized_values = stats.mstats.winsorize(
                        original_values.dropna(), limits=self.config.winsorize_limits
                    )

                    # Update the dataframe
                    valid_indices = original_values.dropna().index
                    df_clean.loc[symbol_mask & df_clean.index.isin(valid_indices), col] = winsorized_values

                    self.logger.info(f"Applied winsorization to {col} for {symbol}")

        return df_clean

    def _validate_min_trading_days(self, df: pd.DataFrame) -> pd.DataFrame:
        """Remove symbols with insufficient trading days."""
        before_symbols = df["symbol"].nunique()

        # Count trading days per symbol
        symbol_counts = df["symbol"].value_counts()
        valid_symbols = symbol_counts[symbol_counts >= self.config.min_trading_days].index

        df_clean = df[df["symbol"].isin(valid_symbols)].copy()
        after_symbols = df_clean["symbol"].nunique()

        if before_symbols != after_symbols:
            removed_symbols = before_symbols - after_symbols
            self.logger.warning(
                f"Removed {removed_symbols} symbols with insufficient trading days "
                f"(< {self.config.min_trading_days} days)"
            )

            # Log removed symbols
            removed_symbol_list = set(df["symbol"].unique()) - set(valid_symbols)
            for symbol in removed_symbol_list:
                count = symbol_counts[symbol]
                self.logger.info(f"  Removed {symbol}: only {count} trading days")

        return df_clean.reset_index(drop=True)

    def _final_validation(self, df: pd.DataFrame) -> None:
        """Perform final validation checks."""
        if df.empty:
            self.logger.warning("Final result is empty after preprocessing")
            return

        # Check for any remaining invalid OHLC relationships
        if all(col in df.columns for col in ["open", "high", "low", "close"]):
            invalid_ohlc = (
                (df["high"] < df["low"])
                | (df["high"] < df[["open", "close"]].max(axis=1))
                | (df["low"] > df[["open", "close"]].min(axis=1))
            ).sum()

            if invalid_ohlc > 0:
                self.logger.error(f"Found {invalid_ohlc} invalid OHLC relationships after preprocessing")

        self.logger.info("Final preprocessing summary by symbol:")
        for symbol in df["symbol"].unique():
            symbol_data = df[df["symbol"] == symbol]
            count = len(symbol_data)
            date_range = f"{symbol_data['timestamp'].min().date()} to {symbol_data['timestamp'].max().date()}"
            avg_volume = symbol_data["volume"].mean()

            self.logger.info(f"  {symbol}: {count} days, {date_range}, avg volume: {avg_volume:,.0f}")

    def get_preprocessing_stats(self, df_before: pd.DataFrame, df_after: pd.DataFrame) -> Dict:
        """
        Get preprocessing statistics.

        Args:
            df_before: DataFrame before preprocessing
            df_after: DataFrame after preprocessing

        Returns:
            Dictionary with preprocessing statistics
        """
        stats_dict = {
            "records_before": len(df_before),
            "records_after": len(df_after),
            "records_removed": len(df_before) - len(df_after),
            "removal_rate": (len(df_before) - len(df_after)) / len(df_before) if len(df_before) > 0 else 0,
            "symbols_before": df_before["symbol"].nunique() if not df_before.empty else 0,
            "symbols_after": df_after["symbol"].nunique() if not df_after.empty else 0,
            "symbols_removed": (df_before["symbol"].nunique() - df_after["symbol"].nunique())
            if not df_before.empty and not df_after.empty
            else 0,
        }

        return stats_dict
