"""Logger utility for daily_trade system.

Provides unified logging functionality across all components.
Follows the specification in FORECAST_MODEL_DESIGN_DOC.md.
"""

import logging
from datetime import datetime
from pathlib import Path
from typing import Optional


class AppLogger:
    """
    Unified logger for daily_trade system.

    Features:
    - Standardized format: [YYYY-MM-DD HH:MM:SS] LEVEL: message
    - File output to ./logs/run_YYYYMMDD.log
    - Console output with color coding
    - Automatic log directory creation
    """

    def __init__(
        self,
        name: str = "daily_trade",
        log_dir: Optional[str] = None,
        level: int = logging.INFO,
        console_output: bool = True,
    ):
        """
        Initialize the logger.

        Args:
            name: Logger name
            log_dir: Log directory path. If None, uses './logs'
            level: Logging level (default: INFO)
            console_output: Whether to output to console
        """
        self.name = name
        self.log_dir = Path(log_dir) if log_dir else Path("./logs")
        self.level = level
        self.console_output = console_output

        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # Setup logger
        self.logger = self._setup_logger()

    def _setup_logger(self) -> logging.Logger:
        """Setup logger with file and console handlers."""
        logger = logging.getLogger(self.name)
        logger.setLevel(self.level)

        # Clear existing handlers to avoid duplication
        logger.handlers.clear()

        # Create formatter
        formatter = logging.Formatter(
            "[%(asctime)s] %(levelname)s: %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

        # File handler
        log_filename = f"run_{datetime.now().strftime('%Y%m%d')}.log"
        log_filepath = self.log_dir / log_filename
        file_handler = logging.FileHandler(log_filepath, encoding="utf-8")
        file_handler.setLevel(self.level)
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

        # Console handler
        if self.console_output:
            console_handler = logging.StreamHandler()
            console_handler.setLevel(self.level)
            console_handler.setFormatter(formatter)
            logger.addHandler(console_handler)

        return logger

    def debug(self, message: str) -> None:
        """Log debug message."""
        self.logger.debug(message)

    def info(self, message: str) -> None:
        """Log info message."""
        self.logger.info(message)

    def warning(self, message: str) -> None:
        """Log warning message."""
        self.logger.warning(message)

    def warn(self, message: str) -> None:
        """Alias for warning."""
        self.warning(message)

    def error(self, message: str) -> None:
        """Log error message."""
        self.logger.error(message)

    def critical(self, message: str) -> None:
        """Log critical message."""
        self.logger.critical(message)

    def exception(self, message: str) -> None:
        """Log exception with traceback."""
        self.logger.exception(message)


def get_logger(
    name: str = "daily_trade",
    log_dir: Optional[str] = None,
    level: int = logging.INFO,
    console_output: bool = True,
) -> AppLogger:
    """
    Get a logger instance.

    Args:
        name: Logger name
        log_dir: Log directory path
        level: Logging level
        console_output: Whether to output to console

    Returns:
        AppLogger instance

    Example:
        >>> from daily_trade.utils.logger import get_logger
        >>> logger = get_logger()
        >>> logger.info("Features built for 5 symbols (records=6200)")
    """
    return AppLogger(name, log_dir, level, console_output)
