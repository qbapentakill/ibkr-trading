"""
GapTrader – „Łowca Luk"

Handluje lukami cenowymi przy otwarciu rynku.
Gap up > 0.5% + wolumen → LONG
Gap down > 0.5% + wolumen → SHORT lub gap fill
"""
from __future__ import annotations
from typing import Optional
import pandas as pd
from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal


class GapTrader(BaseAgent):

    PERSONALITY = "Łowca Luk — handluję lukami przy otwarciu rynku"

    DEFAULT_PARAMS = {
        "gap_min_pct":    0.005,   # min 0.5% luka
        "gap_max_pct":    0.05,    # max 5% luka (za duże = zbyt ryzykowne)
        "vol_min_mult":   1.5,
        "atr_sl_mult":    1.0,
        "atr_tp_mult":    2.0,
        "min_confidence": 0.48,
        "fill_strategy":  True,    # True = handluj wypełnienie luki
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=600):
        super().__init__(
            name=AgentName.GAP_TRADER,
            connector=connector, market_data=market_data,
            bus=bus, symbols=symbols, interval_sec=interval_sec,
        )

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        cfg    = self._get_config()
        params = {**self.DEFAULT_PARAMS, **cfg.params}

        df = await self._market_data.get_bars(symbol, "1d", 10)
        if df is None or len(df) < 3:
            return None
        df = self._market_data._add_indicators(df)

        prev_close = float(df.iloc[-2]["close"])
        curr_open  = float(df.iloc[-1]["open"])
        curr_close = float(df.iloc[-1]["close"])
        atr        = float(df.iloc[-1].get("atr_14", curr_close * 0.01))
        vol_r      = float(df.iloc[-1].get("vol_ratio", 1.0))

        if prev_close <= 0:
            return None

        gap_pct = (curr_open - prev_close) / prev_close
        abs_gap = abs(gap_pct)

        if abs_gap < params["gap_min_pct"] or abs_gap > params["gap_max_pct"]:
            return None
        if vol_r < params["vol_min_mult"]:
            return None

        # Gap fill strategy: cena wraca do poprzedniego zamknięcia
        if params["fill_strategy"]:
            direction = SignalDirection.SHORT if gap_pct > 0 else SignalDirection.LONG
        else:
            direction = SignalDirection.LONG  if gap_pct > 0 else SignalDirection.SHORT

        conf = min(0.88, 0.48 + abs_gap * 8 + (vol_r - 1.5) * 0.04)
        if conf < params["min_confidence"]:
            return None

        close = curr_close
        sl = close + params["atr_sl_mult"] * atr if direction == SignalDirection.SHORT \
             else close - params["atr_sl_mult"] * atr
        tp = prev_close if params["fill_strategy"] else (
            close + params["atr_tp_mult"] * atr if direction == SignalDirection.LONG
            else close - params["atr_tp_mult"] * atr
        )

        return TradeSignal(
            agent_name=self.name, symbol=symbol, direction=direction,
            confidence=conf, entry_price=round(close, 4),
            stop_loss=round(sl, 4), take_profit=round(float(tp), 4),
            size_pct=min(conf * 70, cfg.max_allocation_pct),
            reasoning=(f"[{self.PERSONALITY}] {direction.value} {symbol} | "
                       f"Gap={gap_pct:+.2%} | Vol={vol_r:.2f}x | "
                       f"Fill target={prev_close:.4f} | conf={conf:.3f}"),
            raw_indicators={"gap_pct": gap_pct, "vol_ratio": vol_r},
            timeframe="1d",
        )
