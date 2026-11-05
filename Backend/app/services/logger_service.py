"""
Structured Application Logging Service for Agentic AI Data Analyst.
Provides unified console and rotating file logging for requests, queries, cache events, and errors.
"""

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
import sys

# Ensure logs directory exists
LOG_DIR = Path(__file__).resolve().parents[2] / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_FILE = LOG_DIR / "analyst.log"

# Create custom logger
logger = logging.getLogger("ai_data_analyst")
logger.setLevel(logging.INFO)

# Avoid duplicate handlers if re-imported
if not logger.handlers:
    formatter = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # 1. Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # 2. Rotating File Handler (5 MB per file, max 3 backups)
    try:
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8"
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)
    except Exception as e:
        logger.warning(f"Failed to initialize file logger: {e}")


def get_recent_logs(max_lines: int = 50) -> list[str]:
    """Retrieves the most recent log lines from analyst.log."""
    if not LOG_FILE.exists():
        return ["Log file has not been created yet."]
    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
            return [line.strip() for line in lines[-max_lines:]]
    except Exception as e:
        return [f"Error reading log file: {str(e)}"]
