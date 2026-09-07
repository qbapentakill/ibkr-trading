"""
DataLoader – pobiera dane historyczne do backtestów.

Źródła (w kolejności fallback):
1. yfinance (bezpłatne, szybkie)
2. IBKR connector (jeśli połączony)
3. Lokalne pliki CSV z folderu data/
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Optional

import pandas as pd

from core.logger import get_logger

log = get_logger(__name__)


async def load_data(
    symbol: str,
    start:  str,
    end:    str,
    timeframe: str = "1h",
    source: str = "auto",
) -> Optional[pd.DataFrame]:
    """
    Ładuje dane OHLCV jako DataFrame z indeksem datetime.

    timeframe: '1m', '5m', '15m', '1h', '4h', '1d'
    Zwraca None jeśli brak danych.
    """
    if source in ("auto", "yfinance"):
        df = _load_yfinance(symbol, start, end, timeframe)
        if df is not None and not df.empty:
            log.info("Załadowano {} świec {} z yfinance", len(df), symbol)
            return df

    if source in ("auto", "csv"):
        df = _load_csv(symbol, timeframe)
        if df is not None and not df.empty:
            log.info("Załadowano {} świec {} z CSV", len(df), symbol)
            # Filtruj po datach
            df = df.loc[start:end]
            return df

    log.warning("Brak danych dla {} [{} → {}]", symbol, start, end)
    return None


def _load_yfinance(
    symbol: str, start: str, end: str, timeframe: str
) -> Optional[pd.DataFrame]:
    TF_MAP = {
        "1m": "1m", "5m": "5m", "15m": "15m",
        "1h": "1h", "4h": "4h",  "1d":  "1d",
    }
    yf_interval = TF_MAP.get(timeframe, "1h")

    try:
        import yfinance as yf
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end, interval=yf_interval)
        if df.empty:
            return None
        df = df.rename(columns={
            "Open": "open", "High": "high", "Low": "low",
            "Close": "close", "Volume": "volume",
        })
        df.index = pd.to_datetime(df.index, utc=True).tz_localize(None)
        return df[["open", "high", "low", "close", "volume"]].dropna()
    except Exception as exc:
        log.debug("yfinance error dla {}: {}", symbol, exc)
        return None


def _load_csv(symbol: str, timeframe: str) -> Optional[pd.DataFrame]:
    paths = [
        Path(f"data/{symbol}_{timeframe}.csv"),
        Path(f"data/{symbol}.csv"),
    ]
    for p in paths:
        if p.exists():
            try:
                df = pd.read_csv(p, index_col=0, parse_dates=True)
                df.columns = [c.lower() for c in df.columns]
                df = df[["open", "high", "low", "close", "volume"]].dropna()
                return df
            except Exception as exc:
                log.debug("CSV load error {}: {}", p, exc)
    return None
