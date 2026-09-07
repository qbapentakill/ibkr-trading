"""
TrendFollower – „Cierpliwy Strateg"

CHARAKTER:
  Spokojny, długoterminowy. Ignoruje szum rynkowy i krótkoterminowe korekty.
  Wchodzi tylko gdy trend jest wyraźny i potwierdzony na KILKU timeframe'ach.
  Nigdy nie goni ceny – czeka na pullback do EMA lub ustanowienie nowego HH/HL.

METODYKA:
  - EMA crossover (9/21/50/200) – potwierdzenie struktury trendu
  - ADX > 25 – siła trendu, DI+/DI- – kierunek
  - Price action: Higher Highs / Higher Lows (uptrend), LH/LL (downtrend)
  - Multi-timeframe: sygnał tylko gdy 1H I 4H zgodne
  - Wejście na pullback do EMA21 (nie na szczycie)

ZARZĄDZANIE RYZYKIEM:
  - SL: 1.5 * ATR14 od entry
  - TP: 3.0 * ATR14 (R:R = 1:2)
  - Trailing stop po osiągnięciu 1.5R
"""
from __future__ import annotations

from typing import Optional

import pandas as pd

from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal


class TrendFollower(BaseAgent):

    PERSONALITY = "Cierpliwy Strateg – czekam na wyraźny trend potwierdzony multi-TF"

    DEFAULT_PARAMS = {
        "adx_min":            20.0,   # obniżone z 25
        "adx_weak":           15.0,   # obniżone z 20
        "atr_sl_mult":        1.5,
        "atr_tp_mult":        3.0,
        "pullback_ema":       "ema_21",
        "pullback_tolerance": 0.015,  # zwiększone z 0.005 — luźniejszy pullback
        "hh_hl_bars":         5,      # obniżone z 10
        "timeframes":         ["1h", "4h"],
        "min_confidence":     0.45,   # obniżone z 0.58
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=300):
        super().__init__(
            name=AgentName.TREND_FOLLOWER,
            connector=connector,
            market_data=market_data,
            bus=bus,
            symbols=symbols,
            interval_sec=interval_sec,
        )

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        cfg    = self._get_config()
        params = {**self.DEFAULT_PARAMS, **cfg.params}

        results = []
        for tf in params["timeframes"]:
            df = await self._market_data.get_bars(symbol, timeframe=tf, limit=150)
            if df is None or len(df) < 60:
                continue
            r = self._analyze_tf(df, params, tf)
            if r:
                results.append(r)

        # Wymagaj zgodności obu TF
        if len(results) < 2:
            return None

        directions = [r[0] for r in results]
        if len(set(directions)) > 1:
            return None  # sprzeczność – TrendFollower czeka

        direction  = directions[0]
        confidence = sum(r[1] for r in results) / len(results)
        indicators = results[-1][2]  # z wyższego TF

        if confidence < params["min_confidence"]:
            return None

        # Sprawdź pullback (wchodzimy przy EMA, nie na szczycie)
        df_entry = await self._market_data.get_bars(symbol, timeframe="1h", limit=30)
        if df_entry is None or df_entry.empty:
            return None

        df_entry = self._market_data._add_indicators(df_entry)
        row = df_entry.iloc[-1]
        close = float(row["close"])
        ema_val = float(row.get(params["pullback_ema"], close))
        atr     = float(row.get("atr_14", close * 0.01))

        near_ema = abs(close - ema_val) / (ema_val + 1e-9) < params["pullback_tolerance"]
        if not near_ema:
            confidence *= 0.85  # redukuj jeśli nie przy EMA (ale nie odrzucaj)

        # Price action: HH/HL / LH/LL
        pa_confirmed = self._check_price_action(df_entry, direction, params["hh_hl_bars"])
        if pa_confirmed:
            confidence = min(0.95, confidence + 0.05)

        sl = close - params["atr_sl_mult"] * atr if direction == SignalDirection.LONG \
             else close + params["atr_sl_mult"] * atr
        tp = close + params["atr_tp_mult"] * atr if direction == SignalDirection.LONG \
             else close - params["atr_tp_mult"] * atr

        reasoning = (
            f"[{self.PERSONALITY}] {direction.value} na {symbol} | "
            f"EMA9={indicators.get('ema_9', 0):.3f} "
            f"EMA21={indicators.get('ema_21', 0):.3f} "
            f"EMA50={indicators.get('ema_50', 0):.3f} "
            f"EMA200={indicators.get('ema_200', 0):.3f} | "
            f"ADX={indicators.get('adx', 0):.1f} "
            f"DI+={indicators.get('di_pos', 0):.1f} "
            f"DI-={indicators.get('di_neg', 0):.1f} | "
            f"Przy EMA={near_ema} | PA={pa_confirmed} | "
            f"ATR={atr:.4f} SL={sl:.4f} TP={tp:.4f} | conf={confidence:.3f}"
        )

        return TradeSignal(
            agent_name=self.name,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=round(close, 4),
            stop_loss=round(sl, 4),
            take_profit=round(tp, 4),
            size_pct=min(confidence * 100, cfg.max_allocation_pct),
            reasoning=reasoning,
            raw_indicators=indicators,
            timeframe="1h+4h",
        )

    # ──────────────────────────────────────────────────────────────────────────

    def _analyze_tf(
        self, df: pd.DataFrame, params: dict, tf: str
    ) -> Optional[tuple[SignalDirection, float, dict]]:
        df = self._market_data._add_indicators(df)
        row = df.iloc[-1]
        ind = {
            col: float(row[col])
            for col in ["ema_9", "ema_21", "ema_50", "ema_200",
                        "adx", "di_pos", "di_neg", "atr_14", "close"]
            if col in df.columns and not pd.isna(row.get(col, float("nan")))
        }

        adx   = ind.get("adx",    0)
        di_p  = ind.get("di_pos", 0)
        di_n  = ind.get("di_neg", 0)
        e9    = ind.get("ema_9",   0)
        e21   = ind.get("ema_21",  0)
        e50   = ind.get("ema_50",  0)
        e200  = ind.get("ema_200", 0)
        close = ind.get("close",   0)

        if adx < params["adx_weak"]:
            return None

        if e9 > e21 > e50 and close > e200 and adx > params["adx_min"] and di_p > di_n:
            spread = (e9 - e50) / (e50 + 1e-9)
            conf   = min(0.92, 0.58 + (adx - 25) * 0.006 + spread * 8)
            return SignalDirection.LONG, conf, ind

        if e9 < e21 < e50 and close < e200 and adx > params["adx_min"] and di_n > di_p:
            spread = (e50 - e9) / (e50 + 1e-9)
            conf   = min(0.92, 0.58 + (adx - 25) * 0.006 + spread * 8)
            return SignalDirection.SHORT, conf, ind

        return None

    def _check_price_action(
        self, df: pd.DataFrame, direction: SignalDirection, n: int
    ) -> bool:
        """Sprawdza HH/HL dla uptrend lub LH/LL dla downtrend."""
        if len(df) < n + 2:
            return False
        highs = df["high"].iloc[-n:].values
        lows  = df["low"].iloc[-n:].values

        if direction == SignalDirection.LONG:
            # HH: każdy szczyt wyższy od poprzedniego
            hh = all(highs[i] >= highs[i-1] for i in range(1, len(highs)))
            # HL: każde dno wyższe od poprzedniego
            hl = all(lows[i]  >= lows[i-1]  for i in range(1, len(lows)))
            return hh or hl
        else:
            lh = all(highs[i] <= highs[i-1] for i in range(1, len(highs)))
            ll = all(lows[i]  <= lows[i-1]  for i in range(1, len(lows)))
            return lh or ll
