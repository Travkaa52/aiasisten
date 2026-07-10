"""
logger.py
Единая точка настройки loguru: пишем в консоль (для GitHub Actions логов)
и в ротируемый файл (полезно при Docker-деплое с volume под logs/).
"""

from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

from assistant.config import config


def setup_logging() -> "logger":
    logger.remove()  # убираем дефолтный handler

    logger.add(
        sys.stdout,
        level=config.log_level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>"
        ),
        backtrace=False,
        diagnose=False,
    )

    log_dir = Path(config.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    logger.add(
        log_dir / "assistant.log",
        level=config.log_level,
        rotation="5 MB",
        retention="14 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=False,
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | "
            "{name}:{function}:{line} - {message}"
        ),
    )

    logger.add(
        log_dir / "errors.log",
        level="ERROR",
        rotation="5 MB",
        retention="30 days",
        compression="zip",
        enqueue=True,
        backtrace=True,
        diagnose=False,
    )

    return logger


log = setup_logging()
