"""
NewsAnalyst – centralny agregator i klasyfikator newsów.

Zadania:
- Pobiera newsy z wielu źródeł (RSS, Yahoo Finance)
- Klasyfikuje newsy według wpływu: HIGH / MEDIUM / LOW
- Wykrywa nadchodzące eventy makro (NFP, CPI, FOMC daty)
- Udostępnia przetworzone newsy innym agentom przez shared state
- Generuje alerty przy newsach HIGH impact
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional

import feedparser

from agents.base_agent import BaseAgent
from core.logger import get_logger
from core.models import AgentName, Alert, AlertLevel, SignalDirection, TradeSignal
from core.shared_state import shared_state

log = get_logger(__name__)

HIGH_IMPACT_PATTERNS = [
    r"\bfed\b|\bfederal reserve\b|\bfomc\b|\brate (hike|cut|decision)\b",
    r"\becb\b|\beuropean central bank\b",
    r"\bnfp\b|\bnon.?farm payroll\b",
    r"\bcpi\b|\bpce\b|\binflation (data|report|surprise)\b",
    r"\bgdp (growth|contraction|recession)\b",
    r"\btrump\b.{0,30}(tariff|sanction|war|deal|executive order)",
    r"\bmusk\b.{0,30}(twitter|tesla|spacex|doge|bitcoin)",
    r"\bbankrupt\b|\bdefault\b|\bcredit rating\b",
    r"\bearning(s)? (beat|miss|surprise)\b",
    r"\bblackout\b|\bgeopolit\b|\bwar\b|\battack\b",
]

ECONOMIC_CALENDAR = [
    # (name, day_of_month_approx, hour_utc) – uproszczone
    ("NFP",  "first_friday",    13, 30),
    ("CPI",  "second_tuesday",  13, 30),
    ("FOMC", "every_6_weeks",   19,  0),
]

NEWS_SOURCES = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US",
    "https://www.marketwatch.com/rss/topstories",
    "https://feeds.reuters.com/reuters/businessNews",
]


class NewsAnalyst(BaseAgent):
    """Przetwarza i klasyfikuje newsy finansowe dla innych agentów."""

    def __init__(self, connector, market_data, bus, symbols, interval_sec=180):
        super().__init__(
            name=AgentName.NEWS_ANALYST,
            connector=connector,
            market_data=market_data,
            bus=bus,
            symbols=symbols,
            interval_sec=interval_sec,
        )
        self._processed_links: set[str] = set()
        self._all_news: list[dict] = []

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        # NewsAnalyst analizuje raz na cykl (nie per symbol)
        if symbol != self.symbols[0]:
            return None

        await self._fetch_and_classify()
        return None   # sam nie generuje sygnałów – dostarcza dane

    async def _fetch_and_classify(self) -> None:
        """Pobiera i klasyfikuje newsy, zapisuje w shared state."""
        new_items: list[dict] = []

        for url in NEWS_SOURCES:
            try:
                items = await asyncio.get_event_loop().run_in_executor(
                    None, self._parse_feed, url
                )
                new_items.extend(items)
            except Exception as exc:
                log.debug("Błąd RSS {}: {}", url, exc)

        high_impact_found = []
        for item in new_items:
            link = item.get("link", "")
            if link in self._processed_links:
                continue
            self._processed_links.add(link)

            impact = self._classify_impact(item)
            item["impact"] = impact
            self._all_news.insert(0, item)

            if impact == "HIGH":
                high_impact_found.append(item)

        # Ogranicz historię do 500 newsów
        self._all_news = self._all_news[:500]

        # Aktualizuj shared state
        if not hasattr(shared_state, "latest_news"):
            shared_state.latest_news = []
        shared_state.latest_news = self._all_news[:50]

        # Alerty dla HIGH impact
        for item in high_impact_found:
            await self._bus.publish("alerts", {
                "level":   AlertLevel.WARNING.value,
                "title":   f"HIGH IMPACT NEWS",
                "message": item.get("title", "")[:200],
                "source":  "NewsAnalyst",
                "timestamp": datetime.utcnow().isoformat(),
            })
            log.warning("📰 HIGH IMPACT: {}", item.get("title", "")[:100])

    def _parse_feed(self, url: str) -> list[dict]:
        items = []
        try:
            feed = feedparser.parse(url)
            for entry in feed.entries[:30]:
                published = datetime.utcnow()
                if hasattr(entry, "published_parsed") and entry.published_parsed:
                    try:
                        published = datetime(*entry.published_parsed[:6])
                    except Exception:
                        pass
                items.append({
                    "title":     getattr(entry, "title", ""),
                    "summary":   getattr(entry, "summary", "")[:500],
                    "link":      getattr(entry, "link", ""),
                    "published": published,
                    "source":    url,
                })
        except Exception as exc:
            log.debug("Parse error {}: {}", url, exc)
        return items

    def _classify_impact(self, item: dict) -> str:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        for pattern in HIGH_IMPACT_PATTERNS:
            if re.search(pattern, text, re.IGNORECASE):
                return "HIGH"
        # MEDIUM: wspomniane firmy z watchlisty
        medium_keywords = ["earnings", "revenue", "profit", "loss", "merger",
                           "acquisition", "ipo", "dividend", "guidance"]
        if any(kw in text for kw in medium_keywords):
            return "MEDIUM"
        return "LOW"

    def get_recent_news(self, hours: int = 4, min_impact: str = "LOW") -> list[dict]:
        """Zwraca newsy z ostatnich N godzin o minimalnym impakcie."""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        impact_order = {"HIGH": 3, "MEDIUM": 2, "LOW": 1}
        min_level = impact_order.get(min_impact, 1)
        return [
            n for n in self._all_news
            if n.get("published", datetime.utcnow()) > cutoff
            and impact_order.get(n.get("impact", "LOW"), 1) >= min_level
        ]
