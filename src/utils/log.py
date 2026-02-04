"""
Logging configuration with timestamped files
"""

import logging
from datetime import datetime
from logging import FileHandler, StreamHandler
from pathlib import Path

from config import Settings

settings = Settings()


def setup_logging(
    console_output: bool = True,
) -> str:
    """
    Setup logging with timestamped log files

    Args:
        console_output: Whether to also log to console

    Returns:
        Path to the created log file
    """
    # Create logs directory
    log_path = Path(settings.LOG_DIR)
    log_path.mkdir(exist_ok=True)

    # Generate timestamped filename
    timestamp = datetime.now().strftime("%Y%m%d_%H")
    log_filename = log_path / f"{settings.APP_NAME}_{timestamp}.log"

    # Create formatters
    detailed_formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_formatter = logging.Formatter("%(levelname)s - %(message)s")

    # Setup root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(settings.LOG_LEVEL)

    # Clear existing handlers
    root_logger.handlers.clear()

    file_handler = FileHandler(
        log_filename,
        encoding="utf-8",
    )
    file_handler.setLevel(settings.LOG_LEVEL)
    file_handler.setFormatter(detailed_formatter)
    root_logger.addHandler(file_handler)

    # Console handler
    if console_output:
        console_handler = StreamHandler()
        console_handler.setLevel(settings.LOG_LEVEL)
        console_handler.setFormatter(console_formatter)
        root_logger.addHandler(console_handler)

    # Log the setup
    logger = logging.getLogger(__name__)
    logger.info(f"Logging initialized: {log_filename}")

    return str(log_filename)


def cleanup_old_logs(keep_days: int = 7):
    """
    Remove log files older than specified days

    Args:
        keep_days: Number of days to keep logs
    """
    from datetime import timedelta

    log_path = Path(settings.LOG_DIR)
    if not log_path.exists():
        return

    cutoff_time = datetime.now() - timedelta(days=keep_days)

    for log_file in log_path.glob("*.log"):
        if log_file.stat().st_mtime < cutoff_time.timestamp():
            try:
                log_file.unlink()
                logging.info(f"Deleted old log file: {log_file}")
            except Exception as e:
                logging.error(f"Failed to delete log file {log_file}: {e}")
