"""
VIXTrader – „Handlarz Strachu"

Reaguje na indeks VIX (strach rynku).
VIX spike > 30 = panika = kupuj dip.
VIX < 15 = euforia = sprzedaj rally.
"""
from __future__ import annotations
from typing import Optional
import pandas as pd
from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal


class VIXTrader(BaseAgent):

    PERSONALITY = "Handlarz Strachu — kupuję panikę, sprzedaję euforię"

    DEFAULT_PARAMS = {
        "vix_panic":      30.0,   # VIX > 30 → kup dip na SPY/QQQ
        "vix_euphoria":   15.0,   # VIX < 15 → ostrożność
        "vix_extreme":    40.0,   # VIX > 40 → bardzo silny sygnał
        "atr_sl_mult":    1.5,
        "atr_tp_mult":    3.0,
        "min_confidence": 0.50,
        "vix_symbols":    ["SPY", "QQQ", "IWM"],  # handluj tylko na szerokim rynku
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=300):
        super().__init__(
            name=AgentName.VIX_TRADER,
            connector=connector, market_data=market_data,
            bus=bus, symbols=symbols, interval_sec=interval_sec,
        )

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        cfg    = self._get_config()
        params = {**self.DEFAULT_PARAMS, **cfg.params}

        # Handluj tylko na wybranych symbolach
        if symbol not in params["vix_symbols"]:
            return None

        # Pobierz proxy VIX — używamy SPY jako proxy strachu
        df_spy = await self._market_data.get_bars("SPY", "1d", 30)
        if df_spy is None or len(df_spy) < 10:
            return None
        df_spy = self._market_data._add_indicators(df_spy)

        # Oblicz volatility proxy jako ATR/Close * 100
        atr_spy   = float(df_spy.iloc[-1].get("atr_14", 1))
        close_spy = float(df_spy.iloc[-1].get("close", 100))
        vix_proxy = (atr_spy / close_spy) * 100 * 15  # skaluj do zakresu VIX

        df = await self._market_data.get_bars(symbol, "1h", 30)
        if df is None or len(df) < 10:
            return None
        df = self._market_data._add_indicators(df)
        row   = df.iloc[-1]
        close = float(row.get("close", 0))
        atr   = float(row.get("atr_14", close * 0.01))
        rsi   = float(row.get("rsi_14", 50))

        direction: Optional[SignalDirection] = None
        confidence = 0.0

        if vix_proxy >= params["vix_panic"] and rsi < 45:
            # Panika → kupuj dip
            direction  = SignalDirection.LONG
            fear_bonus = min(0.2, (vix_proxy - params["vix_panic"]) * 0.005)
            confidence = min(0.90, 0.50 + fear_bonus)
            if vix_proxy >= params["vix_extreme"]:
                confidence = min(0.93, confidence + 0.08)

        elif vix_proxy <= params["vix_euphoria"] and rsi > 65:
            # Euforia → sprzedaj
            direction  = SignalDirection.SHORT
            greed_bonus = min(0.15, (params["vix_euphoria"] - vix_proxy) * 0.01)
            confidence  = min(0.85, 0.50 + greed_bonus)

        if direction is None or confidence < params["min_confidence"]:
            return None

        sl = close - params["atr_sl_mult"] * atr if direction == SignalDirection.LONG \
             else close + params["atr_sl_mult"] * atr
        tp = close + params["atr_tp_mult"] * atr if direction == SignalDirection.LONG \
             else close - params["atr_tp_mult"] * atr

        return TradeSignal(
            agent_name=self.name, symbol=symbol, direction=direction,
            confidence=confidence, entry_price=round(close, 4),
            stop_loss=round(sl, 4), take_profit=round(tp, 4),
            size_pct=min(confidence * 85, cfg.max_allocation_pct),
            reasoning=(f"[{self.PERSONALITY}] {direction.value} {symbol} | "
                       f"VIX_proxy={vix_proxy:.1f} | RSI={rsi:.1f} | conf={confidence:.3f}"),
            raw_indicators={"vix_proxy": vix_proxy, "rsi_14": rsi},
            timeframe="1h",
        )
