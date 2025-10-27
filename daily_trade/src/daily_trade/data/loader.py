"""DataLoader for fetching OHLCV data using yfinance API.

This module provides the DataLoader class for fetching stock data
with retry mechanisms and data validation.
"""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Union

import pandas as pd
import yfinance as yf
from tenacity import (
    before_sleep_log,
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from ..utils.logger import get_logger


@dataclass
class LoadConfig:
    """Configuration class for DataLoader."""

    start: Optional[str] = None  # "2019-01-01"
    end: Optional[str] = None  # "2025-10-24"
    interval: str = "1d"  # 1d, 1wk, 1mo
    timezone: str = "Asia/Tokyo"
    retry_count: int = 3
    retry_delay: float = 1.0  # seconds
    save_dir: Optional[str] = None  # "./data/ohlcv/"


class DataLoader:
    """
    DataLoader for fetching OHLCV data using yfinance API.

    Features:
    - Fetch daily OHLC data for specified symbols
    - Timezone standardization to Asia/Tokyo
    - Retry mechanism (3 attempts by default)
    - Automatic data cleaning and validation
    - Parquet file saving capability
    """

    def __init__(self, config: LoadConfig):
        """
        Initialize DataLoader.

        Args:
            config: LoadConfig instance with data loading parameters
        """
        self.config = config
        self.logger = get_logger()

        # Setup save directory
        if config.save_dir:
            self.save_dir = Path(config.save_dir)
        else:
            self.save_dir = Path("./data/ohlcv/")
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def load_ohlcv(self, symbols: List[str]) -> pd.DataFrame:
        """
        Load OHLCV data for specified symbols.

        Args:
            symbols: List of stock symbols (e.g., ["7203.T", "6758.T"])

        Returns:
            DataFrame with columns: timestamp, symbol, open, high, low, close, adj_close, volume

        Raises:
            ValueError: If no data could be loaded for any symbols
        """
        self.logger.info(f"Start DataLoader (symbols={len(symbols)})")

        all_frames = []
        failed_symbols = []

        for symbol in symbols:
            try:
                df = self._fetch_symbol_data(symbol)
                if df is not None and not df.empty:
                    all_frames.append(df)
                    self.logger.info(f"Loaded {len(df)} records for {symbol}")
                else:
                    failed_symbols.append(symbol)
                    self.logger.warning(f"No data retrieved for {symbol}")
            except Exception as e:
                failed_symbols.append(symbol)
                self.logger.error(f"Failed to load data for {symbol}: {str(e)}")

        if not all_frames:
            raise ValueError(f"No data could be loaded for any symbols: {symbols}")

        # Combine all dataframes
        combined_df = pd.concat(all_frames, ignore_index=True)

        # Sort by timestamp and symbol
        combined_df = combined_df.sort_values(["timestamp", "symbol"]).reset_index(drop=True)

        self.logger.info(f"Combined data: {len(combined_df)} total records from {len(all_frames)} symbols")

        if failed_symbols:
            self.logger.warning(f"Failed symbols: {failed_symbols}")

        return combined_df

    def _fetch_symbol_data(self, symbol: str) -> Optional[pd.DataFrame]:
        """
        Fetch data for a single symbol with retry mechanism using tenacity.

        Args:
            symbol: Stock symbol

        Returns:
            DataFrame or None if failed
        """

        @retry(
            stop=stop_after_attempt(self.config.retry_count),
            wait=wait_exponential(multiplier=self.config.retry_delay, min=1, max=10),
            retry=retry_if_exception_type((ConnectionError, TimeoutError, Exception)),
            before_sleep=before_sleep_log(self.logger.logger, log_level="WARNING"),
            reraise=True,
        )
        def _fetch_with_retry():
            """Inner function with retry decorator."""
            # Download data using yfinance
            ticker = yf.Ticker(symbol)
            df = ticker.history(
                start=self.config.start,
                end=self.config.end,
                interval=self.config.interval,
                auto_adjust=False,  # Keep both Close and Adj Close
                prepost=False,
                repair=True,
            )

            if df.empty:
                self.logger.warning(f"Empty data returned for {symbol}")
                return None

            # Clean and standardize the data
            return self._clean_data(df, symbol)

        try:
            return _fetch_with_retry()
        except Exception as e:
            self.logger.error(f"All retry attempts failed for {symbol}: {str(e)}")
            return None

    def _clean_data(self, df: pd.DataFrame, symbol: str) -> pd.DataFrame:
        """
        Clean and standardize the raw yfinance data.

        Args:
            df: Raw yfinance DataFrame
            symbol: Stock symbol

        Returns:
            Cleaned DataFrame
        """
        # Reset index to get timestamp as column
        df = df.reset_index()

        # Standardize column names
        df.columns = df.columns.str.lower().str.replace(" ", "_")

        # Rename columns to match our schema
        column_mapping = {"date": "timestamp", "adj_close": "adj_close"}
        df = df.rename(columns=column_mapping)

        # Add symbol column
        df["symbol"] = symbol

        # Convert timezone to Asia/Tokyo
        if "timestamp" in df.columns:
            if df["timestamp"].dt.tz is None:
                # If timezone-naive, assume UTC and convert
                df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
            df["timestamp"] = df["timestamp"].dt.tz_convert(self.config.timezone)

        # Select and reorder columns
        required_columns = [
            "timestamp",
            "symbol",
            "open",
            "high",
            "low",
            "close",
            "adj_close",
            "volume",
        ]
        available_columns = [col for col in required_columns if col in df.columns]
        df = df[available_columns]

        # Basic data validation
        self._validate_data(df, symbol)

        return df

    def _validate_data(self, df: pd.DataFrame, symbol: str) -> None:
        """
        Validate the cleaned data and log warnings for issues.

        Args:
            df: Cleaned DataFrame
            symbol: Stock symbol
        """
        if df.empty:
            return

        # Check for negative prices
        price_columns = ["open", "high", "low", "close", "adj_close"]
        for col in price_columns:
            if col in df.columns:
                negative_count = (df[col] < 0).sum()
                if negative_count > 0:
                    self.logger.warning(f"Found {negative_count} negative {col} values for {symbol}")

        # Check for zero volume
        if "volume" in df.columns:
            zero_volume_count = (df["volume"] == 0).sum()
            if zero_volume_count > 0:
                self.logger.warning(f"Found {zero_volume_count} zero volume days for {symbol}")

        # Check for invalid OHLC relationships
        if all(col in df.columns for col in ["open", "high", "low", "close"]):
            invalid_high = ((df["high"] < df[["open", "close"]].max(axis=1)) | (df["high"] < df["low"])).sum()
            invalid_low = ((df["low"] > df[["open", "close"]].min(axis=1)) | (df["low"] > df["high"])).sum()

            if invalid_high > 0:
                self.logger.warning(f"Found {invalid_high} invalid high prices for {symbol}")
            if invalid_low > 0:
                self.logger.warning(f"Found {invalid_low} invalid low prices for {symbol}")

        # Check for duplicate timestamps
        duplicate_count = df["timestamp"].duplicated().sum()
        if duplicate_count > 0:
            self.logger.warning(f"Found {duplicate_count} duplicate timestamps for {symbol}")

    def save_to_parquet(self, df: pd.DataFrame, filename: Optional[str] = None) -> str:
        """
        Save DataFrame to Parquet file.

        Args:
            df: DataFrame to save
            filename: Optional filename. If None, auto-generate

        Returns:
            Path to saved file
        """
        if filename is None:
            timestamp_str = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"ohlcv_data_{timestamp_str}.parquet"

        filepath = self.save_dir / filename

        try:
            df.to_parquet(filepath, engine="pyarrow", compression="snappy")
            self.logger.info(f"Data saved to {filepath} ({len(df)} records)")
            return str(filepath)
        except Exception as e:
            self.logger.error(f"Failed to save data to {filepath}: {str(e)}")
            raise

    def load_from_parquet(self, filepath: Union[str, Path]) -> pd.DataFrame:
        """
        Load DataFrame from Parquet file.

        Args:
            filepath: Path to Parquet file

        Returns:
            Loaded DataFrame
        """
        try:
            df = pd.read_parquet(filepath)
            self.logger.info(f"Loaded data from {filepath} ({len(df)} records)")
            return df
        except Exception as e:
            self.logger.error(f"Failed to load data from {filepath}: {str(e)}")
            raise
