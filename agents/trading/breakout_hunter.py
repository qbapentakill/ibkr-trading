"""
BreakoutHunter – „Oportunista"

CHARAKTER:
  Czujny, cierpliwy w oczekiwaniu, wybuchowy w działaniu.
  Czeka na wybicie z konsolidacji z rozszerzającą się zmiennością.
  Wchodzi tylko po potwierdzeniu breakoutu (close poza poziomem, nie wick).

METODYKA:
  - Support/Resistance: rolling 20-świecowy high/low
  - ATR breakout: cena musi zamknąć się > resistance + 0.3*ATR (nie wick)
  - Volume profile: wolumen w momencie breakoutu > 1.5x średnia
  - Volatility expansion: ATR rośnie (potwierdzenie ekspansji)
  - False breakout filter: poprzednia świeca musiała być WEWNĄTRZ zakresu

ZARZĄDZANIE RYZYKIEM:
  - SL: poziom resistance/support (powrót = false breakout)
  - TP: 1.5 * ATR od poziomu breakout
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal


class BreakoutHunter(BaseAgent):

    PERSONALITY = "Oportunista – czekam na wybicie z konsolidacji z wolumenem"

    DEFAULT_PARAMS = {
        "breakout_atr_mult":      0.1,    # obniżone z 0.3
        "vol_min_mult":           1.2,    # obniżone z 1.5
        "sl_buffer_pct":          0.002,
        "tp_atr_mult":            1.5,
        "lookback":               20,
        "atr_expansion_min":      1.0,    # obniżone z 1.1 — nie wymagamy ekspansji
        "require_close_outside":  True,
        "timeframes":            ["15m", "1h"],
        "min_confidence":         0.42,   # obniżone z 0.52
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=180):
        super().__init__(
            name=AgentName.BREAKOUT_HUNTER,
            connector=connector,
            market_data=market_data,
            bus=bus,
            symbols=symbols,
            interval_sec=interval_sec,
        )

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        cfg    = self._get_config()
        params = {**self.DEFAULT_PARAMS, **cfg.params}

        df = await self._market_data.get_bars(symbol, "1h", 80)
        if df is None or len(df) < 30:
            return None

        df = self._market_data._add_indicators(df)

        required = ["close", "high", "low", "volume", "atr_14",
                    "resistance_20", "support_20", "vol_sma_20"]
        row  = df.iloc[-1]
        prev = df.iloc[-2]
        if any(c not in df.columns or pd.isna(row.get(c)) for c in required):
            return None

        close      = float(row["close"])
        high       = float(row["high"])
        low        = float(row["low"])
        resistance = float(row["resistance_20"])
        support    = float(row["support_20"])
        atr        = float(row["atr_14"])
        vol        = float(row["volume"])
        vol_avg    = float(row["vol_sma_20"])
        vol_ratio  = vol / (vol_avg + 1e-9)

        prev_close = float(prev["close"])
        prev_high  = float(prev["high"])
        prev_low   = float(prev["low"])

        # ATR expansion check
        atr_history = df["atr_14"].iloc[-10:-1]
        atr_avg_prev = float(atr_history.mean()) if len(atr_history) > 3 else atr
        atr_expanding = atr >= params["atr_expansion_min"] * atr_avg_prev

        direction: Optional[SignalDirection] = None
        confidence = 0.0
        sl = tp = 0.0
        breakout_details = ""

        min_move = params["breakout_atr_mult"] * atr

        # ── LONG breakout ─────────────────────────────────────────────────────
        if (close > resistance + min_move
                and vol_ratio >= params["vol_min_mult"]
                and prev_close <= resistance       # poprzednia świeca WEWNĄTRZ
                and (not params["require_close_outside"] or close > resistance)):

            sl = round(resistance * (1 - params["sl_buffer_pct"]), 4)
            tp = round(resistance + params["tp_atr_mult"] * atr, 4)

            vol_b  = min(0.15, (vol_ratio - params["vol_min_mult"]) * 0.06)
            atr_b  = 0.05 if atr_expanding else 0.0
            bo_str = min(0.10, (close - resistance) / atr * 0.04)
            confidence = min(0.90, 0.52 + vol_b + atr_b + bo_str)
            direction  = SignalDirection.LONG
            breakout_details = (
                f"Breakout LONG powyżej resistance={resistance:.4f} | "
                f"close={close:.4f} (+{close - resistance:.4f}) | "
                f"ATR_expanding={atr_expanding}"
            )

        # ── SHORT breakout ────────────────────────────────────────────────────
        elif (close < support - min_move
                  and vol_ratio >= params["vol_min_mult"]
                  and prev_close >= support
                  and (not params["require_close_outside"] or close < support)):

            sl = round(support * (1 + params["sl_buffer_pct"]), 4)
            tp = round(support - params["tp_atr_mult"] * atr, 4)

            vol_b  = min(0.15, (vol_ratio - params["vol_min_mult"]) * 0.06)
            atr_b  = 0.05 if atr_expanding else 0.0
            bo_str = min(0.10, (support - close) / atr * 0.04)
            confidence = min(0.90, 0.52 + vol_b + atr_b + bo_str)
            direction  = SignalDirection.SHORT
            breakout_details = (
                f"Breakout SHORT poniżej support={support:.4f} | "
                f"close={close:.4f} (-{support - close:.4f}) | "
                f"ATR_expanding={atr_expanding}"
            )

        if direction is None or confidence < params["min_confidence"]:
            return None

        # ── Potwierdzenie 15m ─────────────────────────────────────────────────
        df15 = await self._market_data.get_bars(symbol, "15m", 20)
        if df15 is not None and len(df15) >= 5:
            df15 = self._market_data._add_indicators(df15)
            close_15 = float(df15.iloc[-1]["close"])
            if direction == SignalDirection.LONG  and close_15 > resistance:
                confidence = min(0.93, confidence + 0.05)
            elif direction == SignalDirection.SHORT and close_15 < support:
                confidence = min(0.93, confidence + 0.05)
            else:
                confidence -= 0.08  # słabe potwierdzenie 15m

        if confidence < params["min_confidence"]:
            return None

        reasoning = (
            f"[{self.PERSONALITY}] {direction.value} na {symbol} | "
            f"{breakout_details} | "
            f"Vol={vol_ratio:.2f}x (min {params['vol_min_mult']}x) | "
            f"ATR={atr:.4f} (avg_prev={atr_avg_prev:.4f}) | "
            f"SL={sl} TP={tp} | conf={confidence:.3f}"
        )

        return TradeSignal(
            agent_name=self.name,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=round(close, 4),
            stop_loss=sl,
            take_profit=tp,
            size_pct=min(confidence * 90, cfg.max_allocation_pct),
            reasoning=reasoning,
            raw_indicators={
                "resistance_20": resistance, "support_20": support,
                "atr_14":        atr,        "vol_ratio":  vol_ratio,
                "atr_expanding": atr_expanding,
            },
            timeframe="1h",
        )
