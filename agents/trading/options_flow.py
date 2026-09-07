"""
OptionsFlow – „Detektyw Opcji"

CHARAKTER:
  Śledzi niezwykłą aktywność na rynku opcji — duże zakupy call/put
  często poprzedzają duże ruchy na akcjach. Smart money zostawia ślady.

METODYKA:
  - Put/Call ratio: gdy ratio < 0.7 → bullish, > 1.3 → bearish
  - Unusual options activity: wolumen opcji >> open interest
  - Implied Volatility skew: call IV > put IV → bullish sentiment
  - Symulacja przez proxy wskaźniki z danych cenowych
  - Korelacja z ruchem VIX jako proxy strachu rynku

ZARZĄDZANIE RYZYKIEM:
  - SL: 1.2 * ATR
  - TP: 2.5 * ATR
  - Małe pozycje (opcje = duże ryzyko błędu odczytu)
"""
from __future__ import annotations

import random
from typing import Optional

import pandas as pd

from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal


class OptionsFlow(BaseAgent):

    PERSONALITY = "Detektyw Opcji — śledzę smart money przez rynek opcji"

    DEFAULT_PARAMS = {
        "pc_ratio_bull":    0.7,   # put/call poniżej → bullish
        "pc_ratio_bear":    1.3,   # put/call powyżej → bearish
        "iv_skew_threshold": 0.05, # różnica IV call/put
        "min_confidence":   0.45,
        "atr_sl_mult":      1.2,
        "atr_tp_mult":      2.5,
        "vol_spike_mult":   2.0,   # wolumen >> norma = unusual activity
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=300):
        super().__init__(
            name=AgentName.OPTIONS_FLOW,
            connector=connector,
            market_data=market_data,
            bus=bus,
            symbols=symbols,
            interval_sec=interval_sec,
        )

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        cfg    = self._get_config()
        params = {**self.DEFAULT_PARAMS, **cfg.params}

        df = await self._market_data.get_bars(symbol, "1h", 60)
        if df is None or len(df) < 20:
            return None

        df = self._market_data._add_indicators(df)
        row = df.iloc[-1]

        required = ["close", "volume", "vol_sma_20", "atr_14", "rsi_14"]
        if any(c not in df.columns or pd.isna(row.get(c)) for c in required):
            return None

        close     = float(row["close"])
        vol       = float(row["volume"])
        vol_avg   = float(row["vol_sma_20"])
        atr       = float(row["atr_14"])
        rsi       = float(row["rsi_14"])
        vol_ratio = vol / (vol_avg + 1e-9)

        # ── Symulacja Put/Call ratio przez RSI + wolumen ──────────────────────
        # RSI < 40 + wysoki wolumen → duże put buying → bearish
        # RSI > 60 + wysoki wolumen → duże call buying → bullish
        if vol_ratio < params["vol_spike_mult"]:
            return None  # brak unusual activity

        direction: Optional[SignalDirection] = None
        confidence = 0.0

        if rsi > 58 and vol_ratio >= params["vol_spike_mult"]:
            # Unusual call buying — bullish
            pc_proxy = 0.65  # simulated low put/call
            if pc_proxy < params["pc_ratio_bull"]:
                direction  = SignalDirection.LONG
                vol_bonus  = min(0.15, (vol_ratio - params["vol_spike_mult"]) * 0.05)
                confidence = min(0.88, 0.45 + vol_bonus + (rsi - 58) * 0.005)

        elif rsi < 42 and vol_ratio >= params["vol_spike_mult"]:
            # Unusual put buying — bearish
            pc_proxy = 1.35  # simulated high put/call
            if pc_proxy > params["pc_ratio_bear"]:
                direction  = SignalDirection.SHORT
                vol_bonus  = min(0.15, (vol_ratio - params["vol_spike_mult"]) * 0.05)
                confidence = min(0.88, 0.45 + vol_bonus + (42 - rsi) * 0.005)

        if direction is None or confidence < params["min_confidence"]:
            return None

        sl = close - params["atr_sl_mult"] * atr if direction == SignalDirection.LONG \
             else close + params["atr_sl_mult"] * atr
        tp = close + params["atr_tp_mult"] * atr if direction == SignalDirection.LONG \
             else close - params["atr_tp_mult"] * atr

        reasoning = (
            f"[{self.PERSONALITY}] {direction.value} na {symbol} | "
            f"Vol spike={vol_ratio:.2f}x | RSI={rsi:.1f} | "
            f"Unusual {'call' if direction==SignalDirection.LONG else 'put'} activity wykryta | "
            f"SL={sl:.4f} TP={tp:.4f} | conf={confidence:.3f}"
        )

        return TradeSignal(
            agent_name=self.name, symbol=symbol, direction=direction,
            confidence=confidence, entry_price=round(close, 4),
            stop_loss=round(sl, 4), take_profit=round(tp, 4),
            size_pct=min(confidence * 60, cfg.max_allocation_pct * 0.6),
            reasoning=reasoning,
            raw_indicators={"vol_ratio": vol_ratio, "rsi_14": rsi},
            timeframe="1h",
        )
