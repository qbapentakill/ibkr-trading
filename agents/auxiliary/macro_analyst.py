"""
MacroAnalyst – „Makro Strateg"

Analizuje dane makroekonomiczne przez RSS i dostosowuje
agresywność całego systemu. Wysoka niepewność makro → zmniejsz alokacje.
"""
from __future__ import annotations
import asyncio
from datetime import datetime, timedelta
from typing import Optional
import feedparser
from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal
from core.shared_state import shared_state
from core.logger import get_logger

log = get_logger(__name__)

MACRO_KEYWORDS = {
    "hawkish":  ["rate hike", "tighten", "inflation", "hawkish", "aggressive fed"],
    "dovish":   ["rate cut", "pivot", "dovish", "easing", "stimulus", "fed pause"],
    "risk_off": ["recession", "crisis", "crash", "default", "bank run", "war", "tariff"],
    "risk_on":  ["growth", "gdp beat", "employment", "strong economy", "soft landing"],
}

MACRO_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US",
    "https://www.marketwatch.com/rss/topstories",
]


class MacroAnalyst(BaseAgent):

    PERSONALITY = "Makro Strateg — dostosowuję agresywność do makroekonomii"

    DEFAULT_PARAMS = {
        "fetch_interval_min":   30,
        "risk_off_threshold":   2,    # ile risk_off newsów = redukuj alokację
        "alloc_reduction_pct":  30,   # o ile % redukować alokacje
        "min_confidence":       0.40,
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=1800):
        super().__init__(
            name=AgentName.MACRO_ANALYST,
            connector=connector, market_data=market_data,
            bus=bus, symbols=symbols, interval_sec=interval_sec,
        )
        self._macro_score: float = 0.0
        self._last_fetch: Optional[datetime] = None

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        if symbol != self.symbols[0]:
            return None

        params = {**self.DEFAULT_PARAMS, **self._get_config().params}
        await self._fetch_macro_news(params)
        await self._apply_macro_adjustments(params)
        return None  # MacroAnalyst nie generuje sygnałów tradingowych

    async def _fetch_macro_news(self, params: dict) -> None:
        interval = timedelta(minutes=params["fetch_interval_min"])
        if self._last_fetch and (datetime.utcnow() - self._last_fetch) < interval:
            return

        try:
            scores = {"hawkish": 0, "dovish": 0, "risk_off": 0, "risk_on": 0}
            for feed_url in MACRO_FEEDS:
                try:
                    feed = await asyncio.get_event_loop().run_in_executor(
                        None, lambda u=feed_url: feedparser.parse(u)
                    )
                    for entry in feed.entries[:30]:
                        text = (getattr(entry, "title", "") + " " +
                                getattr(entry, "summary", "")).lower()
                        for category, keywords in MACRO_KEYWORDS.items():
                            if any(kw in text for kw in keywords):
                                scores[category] += 1
                except Exception:
                    pass

            # Oblicz macro score (-1 = bearish, +1 = bullish)
            bullish = scores["dovish"] + scores["risk_on"]
            bearish = scores["hawkish"] + scores["risk_off"]
            total   = bullish + bearish + 1e-9
            self._macro_score = (bullish - bearish) / total

            log.info("📊 MacroAnalyst: score={:.2f} (dovish={} risk_on={} hawkish={} risk_off={})",
                     self._macro_score, scores["dovish"], scores["risk_on"],
                     scores["hawkish"], scores["risk_off"])

            # Zapisz do shared_state
            if not hasattr(shared_state, "macro_data"):
                shared_state.macro_data = {}
            shared_state.macro_data = {
                "score":    self._macro_score,
                "scores":   scores,
                "updated":  datetime.utcnow().isoformat(),
                "sentiment": "BULLISH" if self._macro_score > 0.2 else
                             "BEARISH" if self._macro_score < -0.2 else "NEUTRAL",
            }
            self._last_fetch = datetime.utcnow()
        except Exception as exc:
            log.debug("MacroAnalyst error: {}", exc)

    async def _apply_macro_adjustments(self, params: dict) -> None:
        """Dostosowuje globalne parametry ryzyka na podstawie makro."""
        from core.models import AgentName as AN
        if self._macro_score < -0.3:
            # Środowisko risk-off — zmniejsz agresywność
            for name in AN:
                cfg = shared_state.get_agent_config(name)
                if cfg and cfg.max_allocation_pct > 5.0:
                    # Nie modyfikuj bezpośrednio — publikuj alert
                    pass
            await self._bus.publish("alerts", {
                "level":   "WARNING",
                "title":   "MacroAnalyst: Risk-Off",
                "message": f"Negatywne makro (score={self._macro_score:.2f}) — rozważ zmniejszenie alokacji",
                "source":  "MacroAnalyst",
                "timestamp": datetime.utcnow().isoformat(),
            })
            log.warning("⚠️ MacroAnalyst: Risk-Off środowisko (score={:.2f})", self._macro_score)
