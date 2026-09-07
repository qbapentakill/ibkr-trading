"""
ScalpKing – „Król Skalperów"

Ultra-szybki scalper aktywny tylko w pierwszej godzinie handlu (9:30-10:30 EST).
Najwyższy wolumen i zmienność dnia = najlepsze warunki do scalpingu.
"""
from __future__ import annotations
import datetime as _dt
from typing import Optional
import pandas as pd
from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal


class ScalpKing(BaseAgent):

    PERSONALITY = "Król Skalperów — dominuję w pierwszej godzinie handlu"

    DEFAULT_PARAMS = {
        "active_start_est":  "09:30",
        "active_end_est":    "10:45",
        "vol_mult":          2.5,
        "consec_bars":       2,
        "atr_sl_mult":       0.4,
        "atr_tp_mult":       0.8,
        "bb_width_min":      0.003,
        "min_confidence":    0.50,
        "max_spread_pct":    0.002,
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=15):
        super().__init__(
            name=AgentName.SCALP_KING,
            connector=connector, market_data=market_data,
            bus=bus, symbols=symbols, interval_sec=interval_sec,
        )

    def _is_active_hours(self) -> bool:
        """Sprawdza czy jesteśmy w aktywnych godzinach (EST)."""
        now_est = _dt.datetime.utcnow() - _dt.timedelta(hours=4)
        start   = now_est.replace(hour=9,  minute=30, second=0)
        end     = now_est.replace(hour=10, minute=45, second=0)
        return start <= now_est <= end and now_est.weekday() < 5

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        if not self._is_active_hours():
            return None

        cfg    = self._get_config()
        params = {**self.DEFAULT_PARAMS, **cfg.params}

        # Spread check
        try:
            quote = await self._market_data.get_quote(symbol)
            if quote and quote.last > 0:
                spread_pct = quote.spread / (quote.last + 1e-9)
                if spread_pct > params["max_spread_pct"]:
                    return None
        except Exception:
            pass

        df5 = await self._market_data.get_bars(symbol, "5m", 20)
        df1 = await self._market_data.get_bars(symbol, "1m", 10)

        if df5 is None or len(df5) < 10:
            return None

        df5 = self._market_data._add_indicators(df5)
        row = df5.iloc[-1]

        required = ["ema_3", "ema_8", "vol_ratio", "close", "atr_14", "bb_width"]
        if any(c not in df5.columns or pd.isna(row.get(c)) for c in required):
            return None

        bb_w  = float(row["bb_width"])
        if bb_w < params["bb_width_min"]:
            return None

        e3    = float(row["ema_3"])
        e8    = float(row["ema_8"])
        vol   = float(row["vol_ratio"])
        close = float(row["close"])
        atr   = float(row["atr_14"])

        n = params["consec_bars"]
        closes_n = df5["close"].iloc[-n:].values
        bull_mom = all(closes_n[i] > closes_n[i-1] for i in range(1, n))
        bear_mom = all(closes_n[i] < closes_n[i-1] for i in range(1, n))

        if vol < params["vol_mult"]:
            return None

        direction: Optional[SignalDirection] = None
        confidence = 0.0

        if e3 > e8 and bull_mom:
            direction  = SignalDirection.LONG
            confidence = min(0.92, 0.50 + (vol - params["vol_mult"]) * 0.08 + bb_w * 20)
        elif e3 < e8 and bear_mom:
            direction  = SignalDirection.SHORT
            confidence = min(0.92, 0.50 + (vol - params["vol_mult"]) * 0.08 + bb_w * 20)

        # Potwierdź na 1m
        if df1 is not None and len(df1) >= 5:
            try:
                df1 = self._market_data._add_indicators(df1)
                e3_1 = float(df1.iloc[-1].get("ema_3", e3))
                e8_1 = float(df1.iloc[-1].get("ema_8", e8))
                if direction == SignalDirection.LONG  and e3_1 > e8_1: confidence = min(0.94, confidence + 0.05)
                if direction == SignalDirection.SHORT and e3_1 < e8_1: confidence = min(0.94, confidence + 0.05)
            except Exception:
                pass

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
            size_pct=min(confidence * 50, cfg.max_allocation_pct * 0.5),
            reasoning=(f"[{self.PERSONALITY}] {direction.value} {symbol} | "
                       f"Opening hour scalp | Vol={vol:.2f}x | BB={bb_w:.4f} | conf={confidence:.3f}"),
            raw_indicators={"vol_ratio": vol, "bb_width": bb_w, "ema_3": e3, "ema_8": e8},
            timeframe="5m",
        )
