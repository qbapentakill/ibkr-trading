"""
ResearchAgent – głęboka analiza fundamentalna i techniczna.

Zadania:
- Pobiera dane finansowe (P/E, EPS, market cap) z Yahoo Finance
- Analizuje wielotimeframe'owy trend (MTF analysis)
- Identyfikuje kluczowe poziomy S/R na wielu TF
- Produkuje raporty analityczne publikowane w shared state
- Uruchamiany rzadko (co 30 min) – jest kosztowny obliczeniowo
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import pandas as pd

from agents.base_agent import BaseAgent
from core.logger import get_logger
from core.models import AgentName, SignalDirection, TradeSignal
from core.shared_state import shared_state

log = get_logger(__name__)


class ResearchAgent(BaseAgent):
    """Analiza multi-timeframe + fundamenty."""

    DEFAULT_PARAMS = {
        "timeframes":     ["15m", "1h", "4h", "1d"],
        "min_aligned_tf": 3,    # ile TF musi być zgodnych
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=1800):
        super().__init__(
            name=AgentName.RESEARCH_AGENT,
            connector=connector,
            market_data=market_data,
            bus=bus,
            symbols=symbols,
            interval_sec=interval_sec,   # co 30 minut
        )
        self._reports: dict[str, dict] = {}

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        params = {**self.DEFAULT_PARAMS, **self._get_config().params}

        # Multi-timeframe analiza
        mtf_signals: list[SignalDirection] = []
        mtf_details: dict[str, str] = {}

        for tf in params["timeframes"]:
            try:
                df = await self._market_data.get_bars(symbol, timeframe=tf, limit=100)
                if df is None or len(df) < 30:
                    continue
                direction = self._analyze_tf_trend(df, tf)
                if direction:
                    mtf_signals.append(direction)
                    mtf_details[tf] = direction.value
            except Exception:
                continue

        # Fundamenty — wyłączone gdy yfinance blokuje
        fundamentals = {"summary": "N/A"}

        # Zapisz raport
        report = {
            "symbol":       symbol,
            "mtf_signals":  mtf_details,
            "fundamentals": fundamentals,
            "updated_at":   datetime.utcnow().isoformat(),
        }
        self._reports[symbol] = report
        if not hasattr(shared_state, "research_reports"):
            shared_state.research_reports = {}
        shared_state.research_reports[symbol] = report

        # Sygnał tylko gdy N TF jest zgodnych
        if len(mtf_signals) < params["min_aligned_tf"]:
            return None

        longs  = mtf_signals.count(SignalDirection.LONG)
        shorts = mtf_signals.count(SignalDirection.SHORT)
        total  = len(mtf_signals)

        if longs / total >= 0.75:
            direction = SignalDirection.LONG
            confidence = min(0.75, 0.45 + longs / total * 0.3)
        elif shorts / total >= 0.75:
            direction = SignalDirection.SHORT
            confidence = min(0.75, 0.45 + shorts / total * 0.3)
        else:
            return None

        try:
            df_1h = await self._market_data.get_bars(symbol, "1h", 20)
            if df_1h is None or df_1h.empty or "close" not in df_1h.columns:
                return None
            close = float(df_1h["close"].iloc[-1])
        except Exception:
            return None

        reasoning = (
            f"ResearchAgent {direction.value} | MTF: {mtf_details} | "
            f"Zgodność: {longs}L/{shorts}S z {total} TF"
        )

        return TradeSignal(
            agent_name=self.name,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=close,
            size_pct=confidence * 50,
            reasoning=reasoning,
            raw_indicators={"mtf": mtf_details},
            timeframe="multi",
        )

    def _analyze_tf_trend(self, df: pd.DataFrame, tf: str) -> Optional[SignalDirection]:
        """Ocenia kierunek trendu na danym TF."""
        if "ema_21" not in df.columns or "ema_50" not in df.columns:
            return None

        row = df.iloc[-1]
        e21  = float(row.get("ema_21", 0))
        e50  = float(row.get("ema_50", 0))
        close = float(row.get("close", 0))

        if e21 <= 0 or e50 <= 0:
            return None

        # Trend + cena powyżej/poniżej EMA
        if close > e21 > e50:
            return SignalDirection.LONG
        if close < e21 < e50:
            return SignalDirection.SHORT
        return None

    def _fetch_fundamentals(self, symbol: str) -> dict:
        """Pobiera podstawowe dane fundamentalne z yfinance (jeśli dostępny)."""
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info   = ticker.fast_info  # fast_info jest bezpieczniejsze niż .info
            return {
                "last_price":  getattr(info, "last_price", "N/A"),
                "market_cap":  getattr(info, "market_cap", "N/A"),
                "52w_high":    getattr(info, "fifty_two_week_high", "N/A"),
                "52w_low":     getattr(info, "fifty_two_week_low", "N/A"),
                "summary":     f"Cap={getattr(info, 'market_cap', 'N/A')}",
            }
        except Exception:
            return {"summary": "dane niedostępne"}
