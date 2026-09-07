"""
Centralny logger systemu oparty o loguru.
Każdy komponent pobiera logger przez get_logger(__name__).
"""
from __future__ import annotations

import sys
from pathlib import Path

from loguru import logger

_initialized = False

LOG_DIR = Path("logs")


def setup_logging(level: str = "DEBUG") -> None:
    global _initialized
    if _initialized:
        return

    LOG_DIR.mkdir(exist_ok=True)

    logger.remove()

    # ── konsola — tylko WARNING+ (czyste UI) ─────────────────────────────────
    logger.add(
        sys.stdout,
        level="WARNING",
        format=(
            "  <level>{level: <8}</level> │ "
            "<cyan>{name}</cyan> — "
            "<level>{message}</level>"
        ),
        colorize=True,
    )

    # ── plik główny — wszystko (DEBUG+) ──────────────────────────────────────
    logger.add(
        LOG_DIR / "system.log",
        level="DEBUG",
        rotation="50 MB",
        retention="30 days",
        compression="gz",
        enqueue=True,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    )
    # ── plik tylko dla błędów ─────────────────────────────────────────────────
    logger.add(
        LOG_DIR / "errors.log",
        level="ERROR",
        rotation="20 MB",
        retention="90 days",
        compression="gz",
        enqueue=True,
    )

    # ── plik tradingowy ───────────────────────────────────────────────────────
    logger.add(
        LOG_DIR / "trading.log",
        level="INFO",
        rotation="20 MB",
        retention="90 days",
        compression="gz",
        enqueue=True,
        filter=lambda r: r["extra"].get("trading", False),
    )

    _initialized = True


def get_logger(name: str):
    """Zwraca logger z prefiksem nazwy modułu."""
    return logger.bind(module=name)


def get_trading_logger(name: str):
    """Logger wyspecjalizowany pod wpisy tradingowe."""
    return logger.bind(module=name, trading=True)
