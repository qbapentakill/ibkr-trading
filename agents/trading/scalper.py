"""
Scalper – „Agresywny Spekulant"

CHARAKTER:
  Szybki, impulsywny, nie toleruje wahania. Działa na granicy latencji.
  Małe pozycje, szybkie wejście i wyjście. Generuje wiele sygnałów ale
  z niższą pewnością – RiskManager utrzymuje małe rozmiary pozycji.

METODYKA:
  - Order flow surrogates: nagłe skoki wolumenu (vol > 2x średnia)
  - Momentum: 3 kolejne świece w tym samym kierunku
  - EMA3 / EMA8 crossover (krótkie MA) 
  - MACD zero-line cross na 5m (opcjonalny filtr)
  - Brak pozycji w strefie konsolidacji (BB bardzo wąskie)

ZARZĄDZANIE RYZYKIEM:
  - SL: 0.5 * ATR (bardzo ciasny)
  - TP: 1.0 * ATR
  - Max czas w pozycji: 15 minut → sygnał CLOSE
  - Bardzo mały size_pct
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

import pandas as pd

from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal


class Scalper(BaseAgent):

    PERSONALITY = "Agresywny Spekulant – reaguję na impulsy wolumenowe w sekundach"

    DEFAULT_PARAMS = {
        "vol_mult":         1.3,     # obniżone z 2.0
        "consec_bars":      2,       # obniżone z 3
        "atr_sl_mult":      0.5,
        "atr_tp_mult":      1.0,
        "bb_width_min":     0.001,   # obniżone z 0.002
        "use_macd_filter":  True,
        "min_confidence":   0.38,    # obniżone z 0.44
        "max_spread_pct":   0.005,   # zwiększone z 0.001
        "max_hold_minutes": 15,
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=30):
        super().__init__(
            name=AgentName.SCALPER,
            connector=connector,
            market_data=market_data,
            bus=bus,
            symbols=symbols,
            interval_sec=interval_sec,
        )
        self._position_open_time: dict[str, datetime] = {}

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        cfg    = self._get_config()
        params = {**self.DEFAULT_PARAMS, **cfg.params}

        # ── Sprawdź czy pozycja przekroczyła max czas trzymania ──────────────
        from core.shared_state import shared_state
        pos = shared_state.positions.get(symbol)
        if pos and pos.quantity != 0:
            open_time = self._position_open_time.get(symbol)
            if open_time is None:
                self._position_open_time[symbol] = datetime.utcnow()
            elif (datetime.utcnow() - open_time).total_seconds() > params["max_hold_minutes"] * 60:
                self._position_open_time.pop(symbol, None)
                return TradeSignal(
                    agent_name=self.name,
                    symbol=symbol,
                    direction=SignalDirection.CLOSE,
                    confidence=1.0,
                    reasoning=f"[Scalper] CLOSE {symbol} — przekroczono max czas trzymania {params['max_hold_minutes']}min",
                    timeframe="5m",
                )
        else:
            self._position_open_time.pop(symbol, None)

        # Sprawdź spread
        try:
            quote = await self._market_data.get_quote(symbol)
            if quote and quote.last > 0:
                spread_pct = quote.spread / (quote.last + 1e-9)
                if spread_pct > params["max_spread_pct"]:
                    return None  # za szeroki spread – scalping nieopłacalny
        except Exception:
            pass

        df5 = await self._market_data.get_bars(symbol, "5m", 40)
        df1 = await self._market_data.get_bars(symbol, "1m", 15)

        if df5 is None or len(df5) < 10:
            return None

        df5 = self._market_data._add_indicators(df5)

        # ── Filtr BB (brak konsolidacji) ──────────────────────────────────────
        bb_w = float(df5.iloc[-1].get("bb_width", 0))
        if bb_w < params["bb_width_min"]:
            return None  # rynek zbyt skonsolidowany

        result5 = self._check_momentum(df5, params)
        if not result5:
            return None

        direction, conf, ind = result5

        # ── MACD filtr ────────────────────────────────────────────────────────
        if params["use_macd_filter"] and "macd_hist" in df5.columns:
            macd_hist = float(df5.iloc[-1].get("macd_hist", 0))
            if direction == SignalDirection.LONG  and macd_hist < 0: conf *= 0.80
            if direction == SignalDirection.SHORT and macd_hist > 0: conf *= 0.80

        # ── Potwierdzenie 1m ──────────────────────────────────────────────────
        if df1 is not None and len(df1) >= 10:
            try:
                df1 = self._market_data._add_indicators(df1)
                r1  = self._check_momentum(df1, {**params, "consec_bars": 2})
                if r1 and r1[0] == direction:
                    conf = min(0.90, conf + 0.08)
                elif r1 and r1[0] != direction:
                    return None  # sprzeczność 1m/5m
            except Exception:
                pass  # df1 zbyt mały — ignoruj

        if conf < params["min_confidence"]:
            return None

        close = float(df5.iloc[-1]["close"])
        atr   = float(ind.get("atr_14", close * 0.003))

        sl = close - params["atr_sl_mult"] * atr if direction == SignalDirection.LONG \
             else close + params["atr_sl_mult"] * atr
        tp = close + params["atr_tp_mult"] * atr if direction == SignalDirection.LONG \
             else close - params["atr_tp_mult"] * atr

        reasoning = (
            f"[{self.PERSONALITY}] {direction.value} na {symbol} | "
            f"EMA3={ind.get('ema_3', 0):.4f} EMA8={ind.get('ema_8', 0):.4f} | "
            f"Vol={ind.get('vol_ratio', 0):.2f}x (>{params['vol_mult']}x) | "
            f"Momentum {params['consec_bars']} świece | "
            f"BB_width={bb_w:.4f} | "
            f"ATR={atr:.4f} SL={sl:.4f} TP={tp:.4f} | conf={conf:.3f}"
        )

        # Zapisz czas otwarcia pozycji
        self._position_open_time[symbol] = datetime.utcnow()

        return TradeSignal(
            agent_name=self.name,
            symbol=symbol,
            direction=direction,
            confidence=conf,
            entry_price=round(close, 4),
            stop_loss=round(sl, 4),
            take_profit=round(tp, 4),
            size_pct=min(conf * 55, cfg.max_allocation_pct * 0.5),  # połowa alokacji
            reasoning=reasoning,
            raw_indicators=ind,
            timeframe="5m",
        )

    def _check_momentum(
        self, df: pd.DataFrame, params: dict
    ) -> Optional[tuple[SignalDirection, float, dict]]:
        n = params["consec_bars"]
        if len(df) < n + 8:
            return None

        row = df.iloc[-1]
        required = ["ema_3", "ema_8", "vol_ratio", "close", "atr_14"]
        for c in required:
            if c not in df.columns or pd.isna(row.get(c)):
                return None

        e3    = float(row["ema_3"])
        e8    = float(row["ema_8"])
        vol   = float(row["vol_ratio"])
        close = float(row["close"])
        atr   = float(row["atr_14"])

        closes_n = df["close"].iloc[-n:].values
        bull_mom = all(closes_n[i] > closes_n[i-1] for i in range(1, n))
        bear_mom = all(closes_n[i] < closes_n[i-1] for i in range(1, n))
        vol_ok   = vol >= params["vol_mult"]

        ind = {"ema_3": e3, "ema_8": e8, "vol_ratio": vol,
               "close": close, "atr_14": atr}

        if e3 > e8 and bull_mom and vol_ok:
            conf = min(0.88, 0.44 + min((vol - params["vol_mult"]) * 0.06, 0.20))
            return SignalDirection.LONG, conf, ind

        if e3 < e8 and bear_mom and vol_ok:
            conf = min(0.88, 0.44 + min((vol - params["vol_mult"]) * 0.06, 0.20))
            return SignalDirection.SHORT, conf, ind

        return None
