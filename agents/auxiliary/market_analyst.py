"""
MarketAnalyst – analizuje ogólny stan rynku i publikuje kontekst.

Zadania:
- Ocenia reżim rynkowy: trend / range / volatile
- Oblicza korelacje między symbolami
- Wykrywa anomalie (niezwykły wolumen, breadth divergence)
- Publikuje kondycję rynku na shared state (używane przez inne agenty)
- Generuje słabe sygnały kierunkowe (niski weight w Orchestratorze)
"""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd

from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal


class MarketRegime:
    TRENDING  = "trending"
    RANGING   = "ranging"
    VOLATILE  = "volatile"
    UNKNOWN   = "unknown"


class MarketAnalyst(BaseAgent):
    """Analiza makro stanu rynku i reżimu."""

    DEFAULT_PARAMS = {
        "adx_trend_min":    25,
        "bb_width_volatile": 0.04,
        "vol_anomaly_mult":  3.0,
        "timeframe":        "1h",
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=600):
        super().__init__(
            name=AgentName.MARKET_ANALYST,
            connector=connector,
            market_data=market_data,
            bus=bus,
            symbols=symbols,
            interval_sec=interval_sec,   # co 10 minut
        )
        self.market_regimes: dict[str, str] = {}

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        params = {**self.DEFAULT_PARAMS, **self._get_config().params}
        df = await self._market_data.get_bars(symbol, timeframe=params["timeframe"], limit=100)
        if df is None or len(df) < 30:
            return None

        row  = df.iloc[-1]
        regime = self._detect_regime(df, row, params)
        self.market_regimes[symbol] = regime

        # Aktualizuj shared state z kontekstem rynku
        from core.shared_state import shared_state
        if not hasattr(shared_state, "market_regimes"):
            shared_state.market_regimes = {}
        shared_state.market_regimes[symbol] = regime

        # Wykryj anomalie
        anomaly = self._detect_anomaly(df, row, params)
        if anomaly:
            self._log.warning("⚠️ Anomalia rynkowa {} | {} | {}", symbol, regime, anomaly)

        # Generuj słaby sygnał tylko przy silnym trendzie
        if regime == MarketRegime.TRENDING:
            return self._trend_signal(symbol, df, row)

        return None

    def _detect_regime(self, df: pd.DataFrame, row, params: dict) -> str:
        adx = float(row.get("adx", 0)) if "adx" in df.columns else 0
        bb_width = float(row.get("bb_width", 0)) if "bb_width" in df.columns else 0

        if adx > params["adx_trend_min"]:
            return MarketRegime.TRENDING
        if bb_width > params["bb_width_volatile"]:
            return MarketRegime.VOLATILE
        return MarketRegime.RANGING

    def _detect_anomaly(self, df: pd.DataFrame, row, params: dict) -> Optional[str]:
        if "vol_ratio" not in df.columns:
            return None
        vol_ratio = float(row.get("vol_ratio", 1.0))
        if vol_ratio > params["vol_anomaly_mult"]:
            return f"Wolumen {vol_ratio:.1f}x powyżej średniej"

        # Spread ceny
        high = float(row.get("high", 0))
        low  = float(row.get("low", 0))
        close= float(row.get("close", 1))
        candle_range_pct = (high - low) / (close + 1e-9) * 100
        if candle_range_pct > 3.0:
            return f"Duży zasięg świecy: {candle_range_pct:.1f}%"
        return None

    def _trend_signal(self, symbol: str, df: pd.DataFrame, row) -> Optional[TradeSignal]:
        if "ema_21" not in df.columns or "ema_50" not in df.columns:
            return None
        e21   = float(row.get("ema_21", 0))
        e50   = float(row.get("ema_50", 0))
        close = float(row.get("close", 0))
        adx   = float(row.get("adx", 0))

        if e21 <= 0 or e50 <= 0:
            return None

        direction = SignalDirection.LONG if e21 > e50 else SignalDirection.SHORT
        confidence = min(0.60, 0.35 + adx * 0.005)

        return TradeSignal(
            agent_name=self.name,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=close,
            size_pct=30.0,
            reasoning=(
                f"MarketAnalyst: reżim={MarketRegime.TRENDING} | "
                f"EMA21={e21:.2f} vs EMA50={e50:.2f} | ADX={adx:.1f}"
            ),
            raw_indicators={"regime": MarketRegime.TRENDING, "adx": adx},
            timeframe="1h",
        )
