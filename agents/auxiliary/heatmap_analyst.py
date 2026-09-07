"""
HeatmapAnalyst – „Analityk Sektorów"

Analizuje które sektory rynku są mocne/słabe w danym dniu.
Dostarcza kontekst sektorowy dla innych agentów.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal
from core.shared_state import shared_state
from core.logger import get_logger

log = get_logger(__name__)

SECTOR_ETFS = {
    "Technology":   "XLK",
    "Financials":   "XLF",
    "Energy":       "XLE",
    "Healthcare":   "XLV",
    "Industrials":  "XLI",
    "Utilities":    "XLU",
    "Real Estate":  "XLRE",
    "Consumer Disc":"XLY",
    "Consumer Stap":"XLP",
    "Materials":    "XLB",
    "Comm Services":"XLC",
}


class HeatmapAnalyst(BaseAgent):

    PERSONALITY = "Analityk Sektorów — wiem który sektor dyktuje kierunek rynku"

    DEFAULT_PARAMS = {
        "strong_threshold":  0.005,   # >0.5% dzienny ruch = mocny sektor
        "weak_threshold":   -0.005,   # <-0.5% = słaby sektor
        "check_interval_sec": 1800,
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=1800):
        super().__init__(
            name=AgentName.HEATMAP_ANALYST,
            connector=connector, market_data=market_data,
            bus=bus, symbols=symbols, interval_sec=interval_sec,
        )

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        if symbol != self.symbols[0]:
            return None

        params   = {**self.DEFAULT_PARAMS, **self._get_config().params}
        heatmap  = {}
        strong   = []
        weak     = []

        for sector, etf in SECTOR_ETFS.items():
            try:
                df = await self._market_data.get_bars(etf, "1d", 3)
                if df is None or len(df) < 2:
                    continue
                prev  = float(df.iloc[-2]["close"])
                curr  = float(df.iloc[-1]["close"])
                chg   = (curr - prev) / (prev + 1e-9)
                heatmap[sector] = {"etf": etf, "change_pct": round(chg * 100, 2),
                                   "status": "strong" if chg > params["strong_threshold"]
                                             else "weak" if chg < params["weak_threshold"]
                                             else "neutral"}
                if chg > params["strong_threshold"]:
                    strong.append(sector)
                elif chg < params["weak_threshold"]:
                    weak.append(sector)
            except Exception:
                pass

        # Zapisz do shared_state
        if not hasattr(shared_state, "sector_heatmap"):
            shared_state.sector_heatmap = {}
        shared_state.sector_heatmap = {
            "heatmap":   heatmap,
            "strong":    strong,
            "weak":      weak,
            "updated":   datetime.utcnow().isoformat(),
            "market_mood": "BULLISH" if len(strong) > len(weak) * 1.5
                           else "BEARISH" if len(weak) > len(strong) * 1.5
                           else "MIXED",
        }

        if strong:
            log.info("📊 HeatmapAnalyst: Mocne sektory: {}", ", ".join(strong))
        if weak:
            log.info("📊 HeatmapAnalyst: Słabe sektory: {}", ", ".join(weak))

        return None
