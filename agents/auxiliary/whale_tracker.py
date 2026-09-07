"""
WhaleTracker – „Tropicel Wielorybów"

Śledzi duże transakcje (dla krypto przez wolumen i ruchy cen).
Nagły skok wolumenu bez newsów = wieloryb wchodzi/wychodzi.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
import pandas as pd
from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal
from core.shared_state import shared_state
from core.logger import get_logger

log = get_logger(__name__)


class WhaleTracker(BaseAgent):

    PERSONALITY = "Tropiciel Wielorybów — podążam za dużymi graczami"

    DEFAULT_PARAMS = {
        "whale_vol_mult":   3.5,    # wolumen > 3.5x średnia = wieloryb
        "price_move_min":   0.008,  # min 0.8% ruch cenowy
        "lookback_candles": 20,
        "atr_sl_mult":      1.2,
        "atr_tp_mult":      2.2,
        "min_confidence":   0.52,
        "cooldown_min":     30,     # nie handluj ponownie przez 30 min
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=120):
        super().__init__(
            name=AgentName.WHALE_TRACKER,
            connector=connector, market_data=market_data,
            bus=bus, symbols=symbols, interval_sec=interval_sec,
        )
        self._last_signal: dict[str, datetime] = {}

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        cfg    = self._get_config()
        params = {**self.DEFAULT_PARAMS, **cfg.params}

        # Cooldown
        import datetime as _dt
        last = self._last_signal.get(symbol)
        if last and (_dt.datetime.utcnow() - last).total_seconds() < params["cooldown_min"] * 60:
            return None

        df = await self._market_data.get_bars(symbol, "15m", params["lookback_candles"] + 5)
        if df is None or len(df) < params["lookback_candles"]:
            return None
        df = self._market_data._add_indicators(df)

        required = ["close", "volume", "vol_sma_20", "atr_14"]
        if any(c not in df.columns or pd.isna(df.iloc[-1].get(c)) for c in required):
            return None

        row      = df.iloc[-1]
        prev_row = df.iloc[-2]
        close    = float(row["close"])
        prev_c   = float(prev_row["close"])
        vol      = float(row["volume"])
        vol_avg  = float(row["vol_sma_20"])
        atr      = float(row["atr_14"])
        vol_r    = vol / (vol_avg + 1e-9)

        if vol_r < params["whale_vol_mult"]:
            return None

        price_move = (close - prev_c) / (prev_c + 1e-9)
        if abs(price_move) < params["price_move_min"]:
            return None

        # Kierunek zgodny z ruchem wieloryba
        direction = SignalDirection.LONG if price_move > 0 else SignalDirection.SHORT
        confidence = min(0.90, 0.52 + min(vol_r - params["whale_vol_mult"], 5) * 0.04
                         + abs(price_move) * 5)

        if confidence < params["min_confidence"]:
            return None

        sl = close - params["atr_sl_mult"] * atr if direction == SignalDirection.LONG \
             else close + params["atr_sl_mult"] * atr
        tp = close + params["atr_tp_mult"] * atr if direction == SignalDirection.LONG \
             else close - params["atr_tp_mult"] * atr

        self._last_signal[symbol] = _dt.datetime.utcnow()

        log.info("🐋 WhaleTracker: {} {} | Vol={}x | Move={:+.2%}",
                 direction.value, symbol, vol_r, price_move)

        return TradeSignal(
            agent_name=self.name, symbol=symbol, direction=direction,
            confidence=confidence, entry_price=round(close, 4),
            stop_loss=round(sl, 4), take_profit=round(tp, 4),
            size_pct=min(confidence * 75, cfg.max_allocation_pct),
            reasoning=(f"[{self.PERSONALITY}] {direction.value} {symbol} | "
                       f"Whale vol={vol_r:.1f}x | Move={price_move:+.2%} | conf={confidence:.3f}"),
            raw_indicators={"vol_ratio": vol_r, "price_move": price_move},
            timeframe="15m",
        )
