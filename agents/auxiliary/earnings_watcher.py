"""
EarningsWatcher – „Strażnik Wyników"

Śledzi kalendarz wyników spółek. Przed earnings:
- Zmniejsza alokację agentów tradingowych dla danej spółki
- Publikuje ostrzeżenie na bus
- Po earnings: analizuje reakcję rynku i generuje sygnał
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import feedparser
from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal
from core.logger import get_logger

log = get_logger(__name__)

# Spółki z kalendarzem earnings (uproszczony — w produkcji API finansowe)
EARNINGS_KEYWORDS = [
    "earnings", "quarterly results", "revenue", "EPS", "beat", "miss",
    "guidance", "outlook", "quarterly", "fiscal"
]


class EarningsWatcher(BaseAgent):

    PERSONALITY = "Strażnik Wyników — ostrzegam przed ryzykiem earnings"

    DEFAULT_PARAMS = {
        "warning_days_before": 3,    # ostrzegaj X dni przed earnings
        "vol_spike_threshold": 1.8,  # wolumen powyżej = coś się dzieje
        "post_earnings_entry": True, # wchodź po wynikach na dużym ruchu
        "min_move_pct":        0.03, # min 3% ruch po wynikach
        "min_confidence":      0.50,
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=3600):
        super().__init__(
            name=AgentName.EARNINGS_WATCHER,
            connector=connector, market_data=market_data,
            bus=bus, symbols=symbols, interval_sec=interval_sec,
        )
        self._earnings_cache: dict[str, list] = {}

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        if symbol != self.symbols[0]:
            return None  # analizuj tylko raz na cykl

        params = {**self.DEFAULT_PARAMS, **self._get_config().params}

        # Szukaj newsów earnings w RSS
        await self._fetch_earnings_news(symbol)

        # Sprawdź czy duży ruch po wynikach
        return await self._check_post_earnings(symbol, params)

    async def _fetch_earnings_news(self, symbol: str) -> None:
        """Pobiera newsy o wynikach z Yahoo RSS."""
        try:
            url  = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
            feed = await asyncio.get_event_loop().run_in_executor(
                None, lambda: feedparser.parse(url)
            )
            earnings_news = []
            for entry in feed.entries[:20]:
                title = getattr(entry, "title", "").lower()
                if any(kw in title for kw in EARNINGS_KEYWORDS):
                    earnings_news.append({
                        "title": getattr(entry, "title", ""),
                        "published": datetime.utcnow(),
                    })
            if earnings_news:
                self._earnings_cache[symbol] = earnings_news
                log.info("📅 EarningsWatcher: {} earnings news dla {}", len(earnings_news), symbol)
        except Exception as exc:
            log.debug("EarningsWatcher RSS error {}: {}", symbol, exc)

    async def _check_post_earnings(self, symbol: str, params: dict) -> Optional[TradeSignal]:
        """Sprawdza czy jest okazja po wynikach (duży ruch z wolumenem)."""
        df = await self._market_data.get_bars(symbol, "1d", 5)
        if df is None or len(df) < 2:
            return None
        df = self._market_data._add_indicators(df)

        prev_close = float(df.iloc[-2]["close"])
        curr_close = float(df.iloc[-1]["close"])
        vol_r      = float(df.iloc[-1].get("vol_ratio", 1.0))
        atr        = float(df.iloc[-1].get("atr_14", curr_close * 0.015))

        move_pct = (curr_close - prev_close) / (prev_close + 1e-9)

        # Duży ruch z wolumenem po newsach earnings
        has_earnings = bool(self._earnings_cache.get(symbol))
        if not has_earnings:
            return None
        if abs(move_pct) < params["min_move_pct"]:
            return None
        if vol_r < params["vol_spike_threshold"]:
            return None

        direction = SignalDirection.LONG if move_pct > 0 else SignalDirection.SHORT
        conf      = min(0.85, 0.50 + abs(move_pct) * 3 + (vol_r - 1.8) * 0.05)

        if conf < params["min_confidence"]:
            return None

        sl = curr_close - 1.5 * atr if direction == SignalDirection.LONG \
             else curr_close + 1.5 * atr
        tp = curr_close + 2.5 * atr if direction == SignalDirection.LONG \
             else curr_close - 2.5 * atr

        cfg = self._get_config()
        return TradeSignal(
            agent_name=self.name, symbol=symbol, direction=direction,
            confidence=conf, entry_price=round(curr_close, 4),
            stop_loss=round(sl, 4), take_profit=round(tp, 4),
            size_pct=min(conf * 65, cfg.max_allocation_pct * 0.7),
            reasoning=(f"[{self.PERSONALITY}] {direction.value} {symbol} | "
                       f"Post-earnings ruch={move_pct:+.2%} | Vol={vol_r:.2f}x | conf={conf:.3f}"),
            raw_indicators={"move_pct": move_pct, "vol_ratio": vol_r},
            timeframe="1d",
        )
