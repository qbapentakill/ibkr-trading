"""
MomentumSurfer – „Surfer Momentum"

Szuka akcji z najsilniejszym momentum w danym dniu.
ROC (Rate of Change) + RSI + wolumen = momentum score.
"""
from __future__ import annotations
from typing import Optional
import pandas as pd
from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal


class MomentumSurfer(BaseAgent):

    PERSONALITY = "Surfer Momentum — jadę na fali najsilniejszego ruchu dnia"

    DEFAULT_PARAMS = {
        "roc_period":       10,
        "roc_long_thresh":  1.5,    # ROC > 1.5% → bullish momentum
        "roc_short_thresh": -1.5,
        "rsi_min":          52,     # RSI musi potwierdzać
        "rsi_max":          48,
        "vol_min_mult":     1.4,
        "atr_sl_mult":      1.3,
        "atr_tp_mult":      2.8,
        "min_confidence":   0.50,
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=180):
        super().__init__(
            name=AgentName.MOMENTUM_SURFER,
            connector=connector, market_data=market_data,
            bus=bus, symbols=symbols, interval_sec=interval_sec,
        )

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        cfg    = self._get_config()
        params = {**self.DEFAULT_PARAMS, **cfg.params}

        df = await self._market_data.get_bars(symbol, "1h", 50)
        if df is None or len(df) < 15:
            return None
        df = self._market_data._add_indicators(df)
        row = df.iloc[-1]

        required = ["close", "rsi_14", "atr_14", "vol_ratio"]
        if any(c not in df.columns or pd.isna(row.get(c)) for c in required):
            return None

        close   = float(row["close"])
        rsi     = float(row["rsi_14"])
        atr     = float(row["atr_14"])
        vol_r   = float(row["vol_ratio"])

        # Rate of Change
        period = min(params["roc_period"], len(df) - 1)
        past   = float(df.iloc[-period - 1]["close"])
        roc    = (close - past) / (past + 1e-9) * 100

        direction: Optional[SignalDirection] = None
        confidence = 0.0

        if roc > params["roc_long_thresh"] and rsi > params["rsi_min"] and vol_r >= params["vol_min_mult"]:
            direction  = SignalDirection.LONG
            confidence = min(0.90, 0.50 + min(roc - params["roc_long_thresh"], 3) * 0.06
                            + (rsi - params["rsi_min"]) * 0.003
                            + (vol_r - params["vol_min_mult"]) * 0.04)

        elif roc < params["roc_short_thresh"] and rsi < (100 - params["rsi_min"]) and vol_r >= params["vol_min_mult"]:
            direction  = SignalDirection.SHORT
            confidence = min(0.90, 0.50 + min(abs(roc) - abs(params["roc_short_thresh"]), 3) * 0.06
                            + ((100 - params["rsi_min"]) - rsi) * 0.003
                            + (vol_r - params["vol_min_mult"]) * 0.04)

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
            size_pct=min(confidence * 80, cfg.max_allocation_pct),
            reasoning=(f"[{self.PERSONALITY}] {direction.value} {symbol} | "
                       f"ROC={roc:+.2f}% | RSI={rsi:.1f} | Vol={vol_r:.2f}x | conf={confidence:.3f}"),
            raw_indicators={"roc": roc, "rsi_14": rsi, "vol_ratio": vol_r},
            timeframe="1h",
        )
