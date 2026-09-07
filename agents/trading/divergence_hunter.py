"""
DivergenceHunter – „Łowca Dywergencji"

Szuka dywergencji RSI/MACD vs cena — klasyczny sygnał odwrócenia.
Bullish divergence: cena robi nowe dno, RSI robi wyższe dno → LONG
Bearish divergence: cena robi nowy szczyt, RSI robi niższy szczyt → SHORT
"""
from __future__ import annotations
from typing import Optional
import pandas as pd
from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal


class DivergenceHunter(BaseAgent):

    PERSONALITY = "Łowca Dywergencji — widzę co inni przeoczają"

    DEFAULT_PARAMS = {
        "lookback":        10,
        "rsi_div_min":     3.0,    # min różnica RSI między dołkami/szczytami
        "price_div_min":   0.005,  # min 0.5% różnica cenowa
        "adx_min":         15.0,   # trochę trendu potrzeba
        "atr_sl_mult":     1.4,
        "atr_tp_mult":     2.8,
        "min_confidence":  0.52,
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=240):
        super().__init__(
            name=AgentName.DIVERGENCE_HUNTER,
            connector=connector, market_data=market_data,
            bus=bus, symbols=symbols, interval_sec=interval_sec,
        )

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        cfg    = self._get_config()
        params = {**self.DEFAULT_PARAMS, **cfg.params}

        df = await self._market_data.get_bars(symbol, "1h", 60)
        if df is None or len(df) < params["lookback"] + 5:
            return None
        df = self._market_data._add_indicators(df)

        required = ["close", "rsi_14", "atr_14", "adx", "macd_hist"]
        if any(c not in df.columns for c in required):
            return None

        n      = params["lookback"]
        closes = df["close"].iloc[-n:].values
        rsis   = df["rsi_14"].iloc[-n:].values
        macds  = df["macd_hist"].iloc[-n:].values

        close = float(df.iloc[-1]["close"])
        atr   = float(df.iloc[-1]["atr_14"])
        adx   = float(df.iloc[-1]["adx"])

        if adx < params["adx_min"]:
            return None

        direction: Optional[SignalDirection] = None
        confidence = 0.0

        # ── Bullish divergence: niższe dno ceny, wyższe dno RSI ──────────────
        price_low_1 = min(closes[:n//2])
        price_low_2 = min(closes[n//2:])
        rsi_low_1   = min(rsis[:n//2])
        rsi_low_2   = min(rsis[n//2:])

        if (price_low_2 < price_low_1 * (1 - params["price_div_min"]) and
                rsi_low_2 > rsi_low_1 + params["rsi_div_min"] and
                float(df.iloc[-1]["rsi_14"]) < 45):
            direction  = SignalDirection.LONG
            div_strength = rsi_low_2 - rsi_low_1
            confidence = min(0.88, 0.52 + div_strength * 0.008)

        # ── Bearish divergence: wyższy szczyt ceny, niższy szczyt RSI ─────────
        price_high_1 = max(closes[:n//2])
        price_high_2 = max(closes[n//2:])
        rsi_high_1   = max(rsis[:n//2])
        rsi_high_2   = max(rsis[n//2:])

        if (price_high_2 > price_high_1 * (1 + params["price_div_min"]) and
                rsi_high_2 < rsi_high_1 - params["rsi_div_min"] and
                float(df.iloc[-1]["rsi_14"]) > 55):
            direction  = SignalDirection.SHORT
            div_strength = rsi_high_1 - rsi_high_2
            confidence = min(0.88, 0.52 + div_strength * 0.008)

        if direction is None or confidence < params["min_confidence"]:
            return None

        # Potwierdź MACD
        macd_now = float(df.iloc[-1]["macd_hist"])
        if direction == SignalDirection.LONG  and macd_now < -0.01: confidence = min(0.92, confidence + 0.04)
        if direction == SignalDirection.SHORT and macd_now > 0.01:  confidence = min(0.92, confidence + 0.04)

        sl = close - params["atr_sl_mult"] * atr if direction == SignalDirection.LONG \
             else close + params["atr_sl_mult"] * atr
        tp = close + params["atr_tp_mult"] * atr if direction == SignalDirection.LONG \
             else close - params["atr_tp_mult"] * atr

        div_type = "BULLISH" if direction == SignalDirection.LONG else "BEARISH"
        return TradeSignal(
            agent_name=self.name, symbol=symbol, direction=direction,
            confidence=confidence, entry_price=round(close, 4),
            stop_loss=round(sl, 4), take_profit=round(tp, 4),
            size_pct=min(confidence * 80, cfg.max_allocation_pct),
            reasoning=(f"[{self.PERSONALITY}] {div_type} divergence na {symbol} | "
                       f"RSI dywerguje vs cena | ADX={adx:.1f} | conf={confidence:.3f}"),
            raw_indicators={"adx": adx, "macd_hist": macd_now},
            timeframe="1h",
        )
