"""
MeanReversion – „Matematyczny Kontrarian"

CHARAKTER:
  Chłodny, analityczny. Nie interesuje go kierunek trendu – interesuje go
  odchylenie od średniej. Im większe ekstremum, tym silniejszy sygnał.
  Działa wyłącznie gdy rynek jest w fazie konsolidacji (bez silnego trendu).

METODYKA:
  - Bollinger Bands (20, 2.0 std) – oversold/overbought
  - RSI(14) < 28 lub > 72 – potwierdzenie ekstremum
  - Z-score < -2.5 lub > +2.5 – statystyczne potwierdzenie odchylenia
  - Volume confirmation: wolumen spada przy ekstremalnej cenie (wyczerpanie)
  - ADX < 25 – filtr: brak silnego trendu

ZARZĄDZANIE RYZYKIEM:
  - SL: poza 2.5 std Bollinger (za BB outer)
  - TP: powrót do BB mid (średniej)
  - Pozycja mniejsza niż Trend – wyższe ryzyko false reversal
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal


class MeanReversion(BaseAgent):

    PERSONALITY = "Matematyczny Kontrarian – szukam statystycznych ekstremów"

    DEFAULT_PARAMS = {
        "rsi_oversold":      32.0,   # podniesione z 28
        "rsi_overbought":    68.0,   # obniżone z 72
        "zscore_long":      -2.0,    # podniesione z -2.5
        "zscore_short":      2.0,    # obniżone z 2.5
        "adx_max":           30.0,   # podniesione z 25
        "vol_exhaustion":    True,
        "bb_outer_mult":     2.5,
        "timeframes":       ["15m", "1h"],
        "min_confidence":    0.45,   # obniżone z 0.52
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=120):
        super().__init__(
            name=AgentName.MEAN_REVERSION,
            connector=connector,
            market_data=market_data,
            bus=bus,
            symbols=symbols,
            interval_sec=interval_sec,
        )

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        cfg    = self._get_config()
        params = {**self.DEFAULT_PARAMS, **cfg.params}

        # Analiza 1H jako główny TF
        df1h = await self._market_data.get_bars(symbol, "1h", 80)
        if df1h is None or len(df1h) < 40:
            return None

        df1h = self._market_data._add_indicators(df1h)
        row  = df1h.iloc[-1]

        # Wymagane wskaźniki
        required = ["rsi_14", "zscore", "close", "bb_lower", "bb_upper",
                    "bb_mid", "bb_width", "atr_14", "adx", "vol_ratio"]
        if any(col not in df1h.columns or pd.isna(row.get(col)) for col in required):
            return None

        rsi     = float(row["rsi_14"])
        zscore  = float(row["zscore"])
        close   = float(row["close"])
        bb_l    = float(row["bb_lower"])
        bb_u    = float(row["bb_upper"])
        bb_m    = float(row["bb_mid"])
        bb_w    = float(row["bb_width"])
        adx     = float(row["adx"])
        atr     = float(row["atr_14"])
        vol_r   = float(row["vol_ratio"])

        # ── Filtr ADX ─────────────────────────────────────────────────────────
        if adx > params["adx_max"]:
            return None

        # ── Volume exhaustion (wolumen spada przy ekstremalnej cenie) ─────────
        vol_exhausting = vol_r < 0.8 if params["vol_exhaustion"] else True

        direction: Optional[SignalDirection] = None
        confidence = 0.0

        # ── LONG: oversold ────────────────────────────────────────────────────
        if (close < bb_l
                and rsi < params["rsi_oversold"]
                and zscore < params["zscore_long"]):
            rsi_depth   = (params["rsi_oversold"] - rsi) / params["rsi_oversold"]
            zsc_depth   = abs(zscore) / 4.0
            vol_bonus   = 0.05 if vol_exhausting else 0.0
            confidence  = min(0.92, 0.52 + rsi_depth * 0.25 + zsc_depth * 0.15 + vol_bonus)
            direction   = SignalDirection.LONG

        # ── SHORT: overbought ─────────────────────────────────────────────────
        elif (close > bb_u
                  and rsi > params["rsi_overbought"]
                  and zscore > params["zscore_short"]):
            rsi_depth   = (rsi - params["rsi_overbought"]) / (100 - params["rsi_overbought"])
            zsc_depth   = abs(zscore) / 4.0
            vol_bonus   = 0.05 if vol_exhausting else 0.0
            confidence  = min(0.92, 0.52 + rsi_depth * 0.25 + zsc_depth * 0.15 + vol_bonus)
            direction   = SignalDirection.SHORT

        if direction is None or confidence < params["min_confidence"]:
            return None

        # ── Potwierdzenie na 15m ──────────────────────────────────────────────
        df15 = await self._market_data.get_bars(symbol, "15m", 30)
        if df15 is not None and len(df15) >= 15:
            df15 = self._market_data._add_indicators(df15)
            rsi15 = float(df15.iloc[-1].get("rsi_14", 50))
            if direction == SignalDirection.LONG  and rsi15 < 35: confidence = min(0.95, confidence + 0.05)
            if direction == SignalDirection.SHORT and rsi15 > 65: confidence = min(0.95, confidence + 0.05)

        # SL/TP
        outer_bb_l = bb_m - params["bb_outer_mult"] * (bb_m - bb_l) / 2
        outer_bb_u = bb_m + params["bb_outer_mult"] * (bb_u - bb_m) / 2

        if direction == SignalDirection.LONG:
            sl = round(outer_bb_l - atr * 0.5, 4)
            tp = round(bb_m, 4)
        else:
            sl = round(outer_bb_u + atr * 0.5, 4)
            tp = round(bb_m, 4)

        reasoning = (
            f"[{self.PERSONALITY}] {direction.value} na {symbol} | "
            f"RSI={rsi:.1f} | z-score={zscore:.3f} | "
            f"BB[{bb_l:.4f}–{bb_m:.4f}–{bb_u:.4f}] width={bb_w:.4f} | "
            f"ADX={adx:.1f} (< {params['adx_max']}) | "
            f"Vol_ratio={vol_r:.2f} (exhaustion={vol_exhausting}) | "
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
            size_pct=min(confidence * 75, cfg.max_allocation_pct),
            reasoning=reasoning,
            raw_indicators={
                "rsi_14":   rsi,    "zscore":    zscore,
                "bb_lower": bb_l,   "bb_upper":  bb_u,
                "bb_mid":   bb_m,   "bb_width":  bb_w,
                "adx":      adx,    "vol_ratio": vol_r,
            },
            timeframe="1h",
        )
