"""ロギング設定."""

import logging
import sys
from pathlib import Path


def setup_logging(level: str = "INFO", log_file: Path | None = None) -> None:
    """アプリケーション全体のロギングを設定する.

    Args:
        level: ログレベル（DEBUG, INFO, WARNING, ERROR, CRITICAL）
        log_file: ログファイルパス。Noneの場合はコンソール出力のみ
    """
    root_logger = logging.getLogger("daily_routine")
    root_logger.setLevel(getattr(logging, level.upper(), logging.INFO))

    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # コンソールハンドラ
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)

    # ファイルハンドラ
    if log_file is not None:
        log_file.parent.mkdir(parents=True, exist_ok=True)
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
