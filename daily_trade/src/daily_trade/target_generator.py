"""TargetGenerator for creating prediction targets from OHLCV data.

This module provides the TargetGenerator class for creating next-day return
and direction labels for machine learning model training.
"""

from dataclasses import dataclass
from typing import Optional

import pandas as pd

from .utils.logger import get_logger


@dataclass
class TargetConfig:
    """Configuration class for TargetGenerator."""

    margin_pct: float = (
        0.0  # Threshold for direction classification (e.g., 0.15 for 15bps)
    )
    min_return_threshold: float = -0.5  # Minimum return threshold (e.g., -50%)
    max_return_threshold: float = 0.5  # Maximum return threshold (e.g., +50%)
    remove_incomplete_days: bool = True  # Remove rows without next day data


class TargetGenerator:
    """
    TargetGenerator for creating prediction targets from price data.

    Features:
    - Calculate next-day returns: next_ret = (next_close / close - 1)
    - Generate direction labels: y_up = (next_ret > margin_pct)
    - Handle missing data and outliers
    - Remove incomplete days (last day without next price)

    All calculations preserve temporal order and avoid future leakage.
    """

    def __init__(self, config: Optional[TargetConfig] = None):
        """
        Initialize TargetGenerator.

        Args:
            config: TargetConfig instance with target generation parameters
        """
        self.config = config or TargetConfig()
        self.logger = get_logger()

    def make_targets(
        self, df: pd.DataFrame, margin_pct: Optional[float] = None
    ) -> pd.DataFrame:
        """
        Create next-day return and direction targets from OHLCV data.

        Args:
            df: DataFrame with OHLCV data from FeatureBuilder
            margin_pct: Override margin percentage for direction classification.
                       If None, uses config.margin_pct

        Returns:
            DataFrame with added columns: next_ret, y_up
            Rows without next-day data are removed.

        Raises:
            ValueError: If required columns are missing
            ValueError: If no valid targets can be created
        """
        self.logger.info(f"Start target generation for {len(df)} records")

        if df.empty:
            self.logger.warning("Empty DataFrame provided for target generation")
            return df

        # Make a copy to avoid modifying original data
        df_targets = df.copy()

        # Validate required columns
        required_columns = ["timestamp", "symbol", "close"]
        missing_columns = [
            col for col in required_columns if col not in df_targets.columns
        ]
        if missing_columns:
            raise ValueError(
                f"Missing required columns for target generation: {missing_columns}"
            )

        # Use provided margin_pct or config default
        effective_margin = (
            margin_pct if margin_pct is not None else self.config.margin_pct
        )
        self.logger.info(
            f"Using margin threshold: {effective_margin:.4f} ({effective_margin * 100:.2f}%)"
        )

        # Sort by symbol and timestamp to ensure proper temporal order
        df_targets = df_targets.sort_values(["symbol", "timestamp"]).reset_index(
            drop=True
        )

        # Calculate targets by symbol to prevent cross-contamination
        target_frames = []
        for symbol in df_targets["symbol"].unique():
            symbol_data = df_targets[df_targets["symbol"] == symbol].copy()
            symbol_with_targets = self._create_targets_for_symbol(
                symbol_data, effective_margin
            )
            target_frames.append(symbol_with_targets)

        # Combine all symbols
        df_combined = pd.concat(target_frames, ignore_index=True)

        # Sort by timestamp and symbol for consistent output
        df_combined = df_combined.sort_values(["timestamp", "symbol"]).reset_index(
            drop=True
        )

        # Log summary statistics
        self._log_target_statistics(df_combined, df)

        return df_combined

    def _create_targets_for_symbol(
        self, df: pd.DataFrame, margin_pct: float
    ) -> pd.DataFrame:
        """Create targets for a single symbol."""
        # Sort by timestamp to ensure proper ordering
        df = df.sort_values("timestamp").reset_index(drop=True)

        symbol = df["symbol"].iloc[0]

        # Use adj_close if available, otherwise use close
        price_column = "adj_close" if "adj_close" in df.columns else "close"
        self.logger.debug(f"Using {price_column} for target calculation for {symbol}")

        # Calculate next-day return
        df["next_ret"] = (
            df[price_column].pct_change(periods=1).shift(-1)
        )  # Shift back to align with current day

        # Alternative calculation for clarity: next_ret = (next_close / close - 1)
        # This is equivalent but more explicit
        next_prices = df[price_column].shift(-1)
        df["next_ret"] = (next_prices / df[price_column]) - 1.0

        # Apply return thresholds to remove extreme outliers
        if self.config.min_return_threshold is not None:
            extreme_low = df["next_ret"] < self.config.min_return_threshold
            if extreme_low.sum() > 0:
                self.logger.warning(
                    f"Clipping {extreme_low.sum()} extreme low returns for {symbol}"
                )
                df.loc[extreme_low, "next_ret"] = self.config.min_return_threshold

        if self.config.max_return_threshold is not None:
            extreme_high = df["next_ret"] > self.config.max_return_threshold
            if extreme_high.sum() > 0:
                self.logger.warning(
                    f"Clipping {extreme_high.sum()} extreme high returns for {symbol}"
                )
                df.loc[extreme_high, "next_ret"] = self.config.max_return_threshold

        # Create direction label: 1 if next_ret > margin_pct, 0 otherwise
        df["y_up"] = (df["next_ret"] > margin_pct).astype(int)

        # Remove rows without next-day data (typically the last row)
        if self.config.remove_incomplete_days:
            valid_mask = df["next_ret"].notna()
            removed_count = (~valid_mask).sum()
            if removed_count > 0:
                self.logger.debug(
                    f"Removing {removed_count} incomplete days for {symbol}"
                )
            df = df[valid_mask].copy()

        return df

    def _log_target_statistics(
        self, df_with_targets: pd.DataFrame, df_original: pd.DataFrame
    ) -> None:
        """Log summary statistics about generated targets."""
        if df_with_targets.empty:
            self.logger.warning("No valid targets generated")
            return

        original_count = len(df_original)
        final_count = len(df_with_targets)
        removed_count = original_count - final_count

        self.logger.info("Target generation completed:")
        self.logger.info(f"  Original records: {original_count}")
        self.logger.info(f"  Final records: {final_count}")
        self.logger.info(f"  Removed records: {removed_count}")

        # Return statistics
        if "next_ret" in df_with_targets.columns:
            returns = df_with_targets["next_ret"]
            self.logger.info("  Next-day return statistics:")
            self.logger.info(
                f"    Mean: {returns.mean():.6f} ({returns.mean() * 100:.4f}%)"
            )
            self.logger.info(
                f"    Std:  {returns.std():.6f} ({returns.std() * 100:.4f}%)"
            )
            self.logger.info(
                f"    Min:  {returns.min():.6f} ({returns.min() * 100:.4f}%)"
            )
            self.logger.info(
                f"    Max:  {returns.max():.6f} ({returns.max() * 100:.4f}%)"
            )

        # Direction statistics
        if "y_up" in df_with_targets.columns:
            up_count = df_with_targets["y_up"].sum()
            total_count = len(df_with_targets)
            up_rate = up_count / total_count if total_count > 0 else 0

            self.logger.info("  Direction label statistics:")
            self.logger.info(f"    Up days (y_up=1): {up_count} ({up_rate:.3f})")
            self.logger.info(
                f"    Down/Flat days (y_up=0): {total_count - up_count} ({1 - up_rate:.3f})"
            )

        # Symbol-wise statistics
        self.logger.info("  By symbol:")
        for symbol in df_with_targets["symbol"].unique():
            symbol_data = df_with_targets[df_with_targets["symbol"] == symbol]
            symbol_up_rate = symbol_data["y_up"].mean()
            symbol_return_mean = symbol_data["next_ret"].mean()

            self.logger.info(
                f"    {symbol}: {len(symbol_data)} days, "
                f"up_rate={symbol_up_rate:.3f}, "
                f"mean_return={symbol_return_mean:.6f}"
            )

    def get_target_summary(self, df: pd.DataFrame) -> dict:
        """
        Get summary statistics of generated targets.

        Args:
            df: DataFrame with targets

        Returns:
            Dictionary with target statistics
        """
        if "next_ret" not in df.columns or "y_up" not in df.columns:
            return {"error": "Targets not found in DataFrame"}

        summary = {
            "total_records": len(df),
            "symbols": df["symbol"].nunique(),
            "return_stats": {
                "mean": df["next_ret"].mean(),
                "std": df["next_ret"].std(),
                "min": df["next_ret"].min(),
                "max": df["next_ret"].max(),
                "skewness": df["next_ret"].skew(),
                "kurtosis": df["next_ret"].kurtosis(),
            },
            "direction_stats": {
                "up_days": df["y_up"].sum(),
                "down_days": (df["y_up"] == 0).sum(),
                "up_rate": df["y_up"].mean(),
                "class_balance": abs(
                    df["y_up"].mean() - 0.5
                ),  # Deviation from 50-50 balance
            },
            "symbol_stats": {},
        }

        # Per-symbol statistics
        for symbol in df["symbol"].unique():
            symbol_data = df[df["symbol"] == symbol]
            summary["symbol_stats"][symbol] = {
                "records": len(symbol_data),
                "up_rate": symbol_data["y_up"].mean(),
                "mean_return": symbol_data["next_ret"].mean(),
                "return_volatility": symbol_data["next_ret"].std(),
            }

        return summary

    def validate_targets(self, df: pd.DataFrame) -> bool:
        """
        Validate that targets are properly generated.

        Args:
            df: DataFrame with targets

        Returns:
            True if targets are valid, False otherwise
        """
        if "next_ret" not in df.columns:
            self.logger.error("next_ret column not found")
            return False

        if "y_up" not in df.columns:
            self.logger.error("y_up column not found")
            return False

        # Check for any NaN values in targets
        if df["next_ret"].isna().any():
            self.logger.error("Found NaN values in next_ret")
            return False

        if df["y_up"].isna().any():
            self.logger.error("Found NaN values in y_up")
            return False

        # Check y_up is binary
        unique_values = df["y_up"].unique()
        if not set(unique_values).issubset({0, 1}):
            self.logger.error(f"y_up contains non-binary values: {unique_values}")
            return False

        # Check for reasonable return range
        if (df["next_ret"] < -1.0).any() or (df["next_ret"] > 1.0).any():
            extreme_returns = df[(df["next_ret"] < -1.0) | (df["next_ret"] > 1.0)]
            self.logger.warning(
                f"Found {len(extreme_returns)} extreme returns (>100% or <-100%)"
            )

        self.logger.info("Target validation passed")
        return True
