"""
SentimentTrader – „Narracyjny"

CHARAKTER:
  Reaguje na narrację rynkową. Rozumie, że jeden tweet Muska lub wypowiedź
  Trumpa może chwilowo zdominować ruchy techniczne. Szybko wchodzi po newsie
  i szybko wychodzi gdy narracja się wyczerpuje.

METODYKA:
  - RSS/Atom feeds finansowe (Yahoo Finance, Reuters, MarketWatch)
  - VADER sentiment scoring z kontekstowymi wagami per typ źródła
  - Impact scoring: KLUCZOWI AKTORZY z specjalnymi wagami:
      * Trump (tariffs, war, deal, executive order): ×2.5
      * Musk (Tesla, SpaceX, DOGE, X/Twitter):       ×2.2
      * Fed/FOMC/Powell (rate decision):              ×3.0  ← najważniejszy
      * ECB/Lagarde:                                  ×2.8
      * NFP / Non-farm payrolls:                      ×2.5
      * CPI / PCE / Inflation:                        ×2.3
  - Decay: sygnał traci wagę po 2h od momentu newsa
  - Economic calendar: przed ważnym eventem → zmniejsza alokację

ZARZĄDZANIE RYZYKIEM:
  - Małe pozycje (event-driven = wysoka niepewność)
  - Natychmiastowe zamknięcie przy odwróceniu sentymentu
"""
from __future__ import annotations

import asyncio
import re
from datetime import datetime, timedelta
from typing import Optional

import feedparser

from agents.base_agent import BaseAgent
from core.logger import get_logger
from core.models import AgentName, SignalDirection, TradeSignal

log = get_logger(__name__)

# ── Reguły wagowania aktorów i kategorii ──────────────────────────────────────
ACTOR_RULES: list[tuple[str, float]] = [
    # (regex, weight)
    (r"\bfed\b|\bfederal reserve\b|\bfomc\b|\bpowell\b",          3.0),
    (r"\becb\b|\beuropean central bank\b|\blagarde\b",             2.8),
    (r"\bnfp\b|\bnon.?farm payroll\b",                            2.5),
    (r"\bcpi\b|\bpce\b|\bcore inflation\b",                       2.3),
    (r"\btrump\b.{0,40}(tariff|sanction|deal|order|ban|war)",     2.5),
    (r"\btrump\b",                                                 1.8),
    (r"\belon musk\b|\bmusk\b.{0,20}(tesla|spacex|doge|twitter|x\.com)", 2.2),
    (r"\bmusk\b",                                                  1.6),
    (r"\bgdp\b|\brecession\b|\bgrowth\b",                         1.8),
    (r"\bearning(s)? (beat|miss|surprise)\b",                     1.7),
    (r"\brate (hike|cut|pause|hold)\b",                           2.0),
    (r"\bbanking crisis\b|\bbank run\b|\bsvb\b|\bcredit suisse\b", 2.5),
    (r"\bgeopolit\b|\bwar\b|\bsanction\b|\battack\b",             1.9),
    (r"\bcrash\b|\bpanic\b|\bsell.off\b",                         1.8),
    (r"\brally\b|\bsurge\b|\bbull\b",                             1.3),
    (r"\bbear\b|\bdrop\b|\bfall\b",                               1.3),
]

# Pozytywne i negatywne słowa (VADER fallback)
POS_WORDS = {"bullish", "buy", "rally", "surge", "gain", "beat", "rise",
             "positive", "growth", "strong", "record", "boom", "optimism",
             "upgrade", "outperform", "recovery", "expand"}
NEG_WORDS = {"bearish", "sell", "crash", "drop", "loss", "miss", "fall",
             "negative", "weak", "recession", "crisis", "fear", "downgrade",
             "underperform", "contraction", "default", "bankrupt"}

NEWS_FEEDS = [
    "https://feeds.finance.yahoo.com/rss/2.0/headline?region=US&lang=en-US",
    "https://www.marketwatch.com/rss/topstories",
]

SYMBOL_KEYWORDS: dict[str, list[str]] = {
    "AAPL":    ["apple", "aapl", "iphone", "tim cook", "app store"],
    "TSLA":    ["tesla", "tsla", "musk", "elon", "ev", "electric vehicle", "cybertruck"],
    "NVDA":    ["nvidia", "nvda", "jensen huang", "gpu", "ai chip", "cuda"],
    "SPY":     ["s&p 500", "spy", "market", "stocks", "wall street", "economy"],
    "QQQ":     ["nasdaq", "qqq", "tech", "technology", "big tech"],
    "GLD":     ["gold", "gld", "precious metals", "inflation hedge", "safe haven"],
    "EUR/USD": ["euro", "eur", "ecb", "lagarde", "dollar", "fed", "interest rate"],
    "BTC":     ["bitcoin", "btc", "crypto", "cryptocurrency", "musk", "doge"],
}


class SentimentTrader(BaseAgent):

    PERSONALITY = "Narracyjny – reaguję na głos rynku, szczególnie Fed, Trump i Muska"

    DEFAULT_PARAMS = {
        "sentiment_threshold_long":  0.05,   # obniżone z 0.12
        "sentiment_threshold_short": -0.05,  # podniesione z -0.12
        "news_max_age_hours":         6,     # zwiększone z 3
        "min_confidence":             0.35,  # obniżone z 0.40
        "fetch_interval_min":         4,
        "decay_halflife_hours":       2.0,   # zwiększone z 1.5
        "min_news_count":             1,
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=240):
        super().__init__(
            name=AgentName.SENTIMENT_TRADER,
            connector=connector,
            market_data=market_data,
            bus=bus,
            symbols=symbols,
            interval_sec=interval_sec,
        )
        self._news_cache:  dict[str, list[dict]] = {}
        self._last_fetch:  Optional[datetime]    = None
        self._vader = None
        self._init_vader()

    def _init_vader(self) -> None:
        try:
            from vaderSentiment.vaderSentiment import SentimentIntensityAnalyzer
            self._vader = SentimentIntensityAnalyzer()
        except ImportError:
            log.warning("VADER niedostępny – używam fallback keyword analizy")

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        cfg    = self._get_config()
        params = {**self.DEFAULT_PARAMS, **cfg.params}

        await self._maybe_refresh_news(symbol, params)

        news = self._news_cache.get(symbol, [])
        if not news:
            return None

        cutoff = datetime.utcnow() - timedelta(hours=params["news_max_age_hours"])
        fresh  = [n for n in news if n.get("published", datetime.min) > cutoff]

        if len(fresh) < params["min_news_count"]:
            return None

        # Oblicz sentyment z wagami i decay
        sentiment, max_weight, top_news = self._weighted_sentiment(fresh, symbol, params)

        direction: Optional[SignalDirection] = None
        confidence = 0.0

        if sentiment > params["sentiment_threshold_long"]:
            direction  = SignalDirection.LONG
            confidence = min(0.85, 0.40 + abs(sentiment) * max_weight * 0.15)
        elif sentiment < params["sentiment_threshold_short"]:
            direction  = SignalDirection.SHORT
            confidence = min(0.85, 0.40 + abs(sentiment) * max_weight * 0.15)

        if direction is None or confidence < params["min_confidence"]:
            return None

        # Dane techniczne (SL/TP)
        df = await self._market_data.get_bars(symbol, "1h", 20)
        if df is None or df.empty or len(df) < 2:
            return None
        df = self._market_data._add_indicators(df)
        if df.empty or "close" not in df.columns:
            return None
        row   = df.iloc[-1]
        close = float(row.get("close", 0))
        if close <= 0:
            return None
        atr   = float(row.get("atr_14", close * 0.015) or close * 0.015)

        sl = close - 2.0 * atr if direction == SignalDirection.LONG else close + 2.0 * atr
        tp = close + 2.5 * atr if direction == SignalDirection.LONG else close - 2.5 * atr

        reasoning = (
            f"[{self.PERSONALITY}] {direction.value} na {symbol} | "
            f"Sentiment={sentiment:+.4f} (max_weight={max_weight:.1f}×) | "
            f"Newsów={len(fresh)} (świeżych={params['news_max_age_hours']}h) | "
            f"Top: \"{top_news[:90]}\" | "
            f"SL={sl:.4f} TP={tp:.4f} | conf={confidence:.3f}"
        )

        return TradeSignal(
            agent_name=self.name,
            symbol=symbol,
            direction=direction,
            confidence=confidence,
            entry_price=round(close, 4),
            stop_loss=round(sl, 4),
            take_profit=round(tp, 4),
            size_pct=min(confidence * 65, cfg.max_allocation_pct * 0.6),
            reasoning=reasoning,
            raw_indicators={
                "sentiment":    sentiment,
                "max_weight":   max_weight,
                "news_count":   len(fresh),
                "top_headline": top_news[:200],
            },
            timeframe="event",
        )

    # ──────────────────────────────────────────────────────────────────────────

    async def _maybe_refresh_news(self, symbol: str, params: dict) -> None:
        interval = timedelta(minutes=params["fetch_interval_min"])
        if self._last_fetch and (datetime.utcnow() - self._last_fetch) < interval:
            return
        try:
            items = await asyncio.get_event_loop().run_in_executor(
                None, self._fetch_sync, symbol
            )
            self._news_cache[symbol] = items
            self._last_fetch = datetime.utcnow()
        except Exception as exc:
            log.debug("Błąd RSS dla {}: {}", symbol, exc)

    def _fetch_sync(self, symbol: str) -> list[dict]:
        items = []
        url = f"https://feeds.finance.yahoo.com/rss/2.0/headline?s={symbol}&region=US&lang=en-US"
        for u in [url] + NEWS_FEEDS[:1]:
            try:
                feed = feedparser.parse(u)
                for e in feed.entries[:25]:
                    pub = datetime.utcnow()
                    if getattr(e, "published_parsed", None):
                        try:
                            pub = datetime(*e.published_parsed[:6])
                        except Exception:
                            pass
                    items.append({
                        "title":     getattr(e, "title", ""),
                        "summary":   getattr(e, "summary", "")[:400],
                        "link":      getattr(e, "link", ""),
                        "published": pub,
                    })
            except Exception:
                pass
        return items

    def _weighted_sentiment(
        self, items: list[dict], symbol: str, params: dict
    ) -> tuple[float, float, str]:
        kws = SYMBOL_KEYWORDS.get(symbol, [symbol.lower()])
        scores: list[tuple[float, float, str, datetime]] = []

        for item in items:
            text = f"{item.get('title', '')} {item.get('summary', '')}".lower()

            relevant = any(k in text for k in kws) or symbol.lower() in text
            if not relevant and symbol not in ("SPY", "QQQ"):
                continue

            # Базовый сентимент
            if self._vader:
                raw = self._vader.polarity_scores(text)["compound"]
            else:
                raw = self._fallback_sentiment(text)

            # Вес актора
            weight = 1.0
            for pattern, w in ACTOR_RULES:
                if re.search(pattern, text, re.IGNORECASE):
                    weight = max(weight, w)

            # Time decay
            age_h = (datetime.utcnow() - item.get("published", datetime.utcnow())).total_seconds() / 3600
            decay = 0.5 ** (age_h / params["decay_halflife_hours"])

            scores.append((raw * weight * decay, weight, item.get("title", ""), item.get("published", datetime.utcnow())))

        if not scores:
            return 0.0, 1.0, ""

        agg_score  = sum(s[0] for s in scores) / len(scores)
        max_weight = max(s[1] for s in scores)
        # Najważniejszy news (po weight × decay)
        top        = max(scores, key=lambda x: abs(x[0]))
        return agg_score, max_weight, top[2]

    def _fallback_sentiment(self, text: str) -> float:
        pos = sum(1 for w in POS_WORDS if w in text)
        neg = sum(1 for w in NEG_WORDS if w in text)
        total = pos + neg
        return (pos - neg) / total if total > 0 else 0.0
