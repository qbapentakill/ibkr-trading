"""
SmartMoneyTracker – śledzi aktywność „dużych graczy".

Metodologia:
- Wykrywa duże transakcje blokowe (block trades) przez anomalie wolumenu
- Analizuje delta wolumenu (buy volume vs sell volume)
- Śledzi open interest zmiany (jeśli dostępne)
- Wykrywa akumulację / dystrybucję przez wskaźniki OBV i CMF
- Generuje sygnały gdy „smart money" wydaje się kupować/sprzedawać
"""
from __future__ import annotations

from typing import Optional

import pandas as pd
import numpy as np

from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal


class SmartMoneyTracker(BaseAgent):
    """Śledzenie aktywności instytucjonalnej przez analizę wolumenu."""

    DEFAULT_PARAMS = {
        "obv_lookback":       20,
        "cmf_period":         20,
        "block_vol_mult":     3.0,   # blok trade = wolumen > N*średnia
        "accumulation_bars":  5,     # ile kolejnych świec z wyż. wolumenem
        "timeframe":         "1h",
        "min_confidence":     0.48,
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=300):
        super().__init__(
            name=AgentName.SMART_MONEY,
            connector=connector,
            market_data=market_data,
            bus=bus,
            symbols=symbols,
            interval_sec=interval_sec,
        )

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        params = {**self.DEFAULT_PARAMS, **self._get_config().params}
        df = await self._market_data.get_bars(symbol, timeframe=params["timeframe"], limit=100)
        if df is None or len(df) < 30:
            return None

        df = self._compute_smart_money_indicators(df, params)
        row = df.iloc[-1]

        obv_trend   = self._obv_trend(df, params["obv_lookback"])
        cmf_value   = float(row.get("cmf", 0))
        vol_ratio   = float(row.get("vol_ratio", 1.0))
        close       = float(row.get("close", 0))
        atr         = float(row.get("atr_14", close * 0.01))

        # Wykryj block trade
        block_trade = vol_ratio >= params["block_vol_mult"]

        # Wykryj akumulację / dystrybucję
        accumulation = self._detect_accumulation(df, params["accumulation_bars"])

        direction: Optional[SignalDirection] = None
        confidence = 0.0
        signals: list[str] = []

        # ── Sygnał LONG (akumulacja smart money) ─────────────────────────────
        if (obv_trend == "rising" and cmf_value > 0.05
                and (accumulation == "accumulation" or block_trade)):
            direction  = SignalDirection.LONG
            confidence = min(0.80, 0.48 + cmf_value * 0.5)
            if block_trade:
                confidence = min(0.85, confidence + 0.08)
            signals = [
                f"OBV trend={obv_trend}",
                f"CMF={cmf_value:.3f}",
                f"Vol_ratio={vol_ratio:.1f}x",
                f"Akumulacja={accumulation}",
            ]

        # ── Sygnał SHORT (dystrybucja) ────────────────────────────────────────
        elif (obv_trend == "falling" and cmf_value < -0.05
                  and (accumulation == "distribution" or block_trade)):
            direction  = SignalDirection.SHORT
            confidence = min(0.80, 0.48 + abs(cmf_value) * 0.5)
            if block_trade:
                confidence = min(0.85, confidence + 0.08)
            signals = [
                f"OBV trend={obv_trend}",
                f"CMF={cmf_value:.3f}",
                f"Vol_ratio={vol_ratio:.1f}x",
                f"Dystrybucja={accumulation}",
            ]

        if direction is None or confidence < params["min_confidence"]:
            return None

        sl = close - 1.5 * atr if direction == SignalDirection.LONG else close + 1.5 * atr
        tp = close + 2.0 * atr if direction == SignalDirection.LONG else close - 2.0 * atr

        reasoning = (
            f"SmartMoneyTracker {direction.value} | "
            + " | ".join(signals)
            + f" | conf={confidence:.2f}"
        )

        return TradeSignal(
            agent_name=self.name,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=close,
            stop_loss=round(sl, 4),
            take_profit=round(tp, 4),
            size_pct=confidence * 70,
            reasoning=reasoning,
            raw_indicators={
                "obv_trend":   obv_trend,
                "cmf":         cmf_value,
                "vol_ratio":   vol_ratio,
                "accumulation": accumulation,
                "block_trade": block_trade,
            },
            timeframe=params["timeframe"],
        )

    # ──────────────────────────────────────────────────────────────────────────

    def _compute_smart_money_indicators(self, df: pd.DataFrame, params: dict) -> pd.DataFrame:
        # OBV (On Balance Volume)
        obv = [0.0]
        for i in range(1, len(df)):
            if df["close"].iloc[i] > df["close"].iloc[i-1]:
                obv.append(obv[-1] + df["volume"].iloc[i])
            elif df["close"].iloc[i] < df["close"].iloc[i-1]:
                obv.append(obv[-1] - df["volume"].iloc[i])
            else:
                obv.append(obv[-1])
        df = df.copy()
        df["obv"] = obv

        # CMF (Chaikin Money Flow)
        period = params["cmf_period"]
        mfm = ((df["close"] - df["low"]) - (df["high"] - df["close"])) / \
              (df["high"] - df["low"] + 1e-9)
        mfv = mfm * df["volume"]
        df["cmf"] = mfv.rolling(period).sum() / (df["volume"].rolling(period).sum() + 1e-9)

        return df

    def _obv_trend(self, df: pd.DataFrame, lookback: int) -> str:
        if "obv" not in df.columns or len(df) < lookback:
            return "neutral"
        obv_recent = df["obv"].iloc[-lookback:]
        slope = np.polyfit(range(lookback), obv_recent, 1)[0]
        if slope > 0:
            return "rising"
        if slope < 0:
            return "falling"
        return "neutral"

    def _detect_accumulation(self, df: pd.DataFrame, n: int) -> str:
        if len(df) < n + 1:
            return "neutral"
        recent = df.iloc[-n:]
        # Akumulacja: rosnący wolumen przy rosnącej cenie
        price_rising = recent["close"].iloc[-1] > recent["close"].iloc[0]
        vol_rising   = recent["volume"].mean() > df["volume"].iloc[-(n*3):-n].mean()

        if price_rising and vol_rising:
            return "accumulation"
        if not price_rising and vol_rising:
            return "distribution"
        return "neutral"
