"""
EconomicCalendar – „Kalendarz Makro"

Blokuje nowe pozycje przed ważnymi wydarzeniami ekonomicznymi.
Monitoruje: Fed, NFP, CPI, GDP, PMI przez RSS newsy.
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

HIGH_IMPACT_EVENTS = [
    "federal reserve", "fomc", "fed decision", "interest rate decision",
    "nonfarm payroll", "non-farm", "cpi", "consumer price index",
    "gdp", "gross domestic product", "pce", "personal consumption",
    "unemployment rate", "jobs report", "pmi", "ism manufacturing",
    "retail sales", "housing starts", "durable goods",
]

BLOCK_MINUTES_BEFORE = 30   # blokuj 30 min przed wydarzeniem
BLOCK_MINUTES_AFTER  = 15   # blokuj 15 min po wydarzeniu


class EconomicCalendar(BaseAgent):

    PERSONALITY = "Kalendarz Makro — ostrzegam przed ryzykownymi momentami"

    DEFAULT_PARAMS = {
        "fetch_interval_min": 60,
        "block_trading":      True,
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=3600):
        super().__init__(
            name=AgentName.ECONOMIC_CALENDAR,
            connector=connector, market_data=market_data,
            bus=bus, symbols=symbols, interval_sec=interval_sec,
        )
        self._upcoming_events: list[dict] = []
        self._last_fetch: Optional[datetime] = None
        self._trading_blocked: bool = False

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        if symbol != self.symbols[0]:
            return None

        params = {**self.DEFAULT_PARAMS, **self._get_config().params}
        await self._fetch_events(params)
        await self._check_block_status(params)
        return None

    async def _fetch_events(self, params: dict) -> None:
        interval = timedelta(minutes=params["fetch_interval_min"])
        if self._last_fetch and (datetime.utcnow() - self._last_fetch) < interval:
            return

        events = []
        try:
            feeds = [
                "https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US",
            ]
            for url in feeds:
                feed = await asyncio.get_event_loop().run_in_executor(
                    None, lambda u=url: feedparser.parse(u)
                )
                for entry in feed.entries[:30]:
                    title = getattr(entry, "title", "").lower()
                    if any(ev in title for ev in HIGH_IMPACT_EVENTS):
                        events.append({
                            "title":    getattr(entry, "title", ""),
                            "time":     datetime.utcnow(),
                            "impact":   "HIGH",
                        })
        except Exception:
            pass

        self._upcoming_events = events
        self._last_fetch      = datetime.utcnow()

        if events:
            log.info("📅 EconomicCalendar: {} HIGH IMPACT events wykrytych", len(events))

        # Zapisz do shared_state
        if not hasattr(shared_state, "economic_events"):
            shared_state.economic_events = []
        shared_state.economic_events = events[:10]

    async def _check_block_status(self, params: dict) -> None:
        """Blokuje trading gdy są ważne wydarzenia."""
        if not params["block_trading"]:
            return

        now = datetime.utcnow()
        should_block = False

        for event in self._upcoming_events:
            event_time = event.get("time", now)
            diff = abs((now - event_time).total_seconds() / 60)
            if diff <= max(BLOCK_MINUTES_BEFORE, BLOCK_MINUTES_AFTER):
                should_block = True
                break

        if should_block and not self._trading_blocked:
            self._trading_blocked = True
            log.warning("⛔ EconomicCalendar: Blokuję nowe pozycje — zbliża się HIGH IMPACT event")
            await self._bus.publish("alerts", {
                "level":     "WARNING",
                "title":     "EconomicCalendar: Blokada tradingu",
                "message":   "Zbliża się ważne wydarzenie makro — nowe pozycje zablokowane",
                "source":    "EconomicCalendar",
                "timestamp": now.isoformat(),
            })
        elif not should_block and self._trading_blocked:
            self._trading_blocked = False
            log.info("✅ EconomicCalendar: Odblokuję trading")
