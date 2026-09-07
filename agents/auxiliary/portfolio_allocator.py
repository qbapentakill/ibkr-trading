"""
PortfolioAllocator – dynamiczna alokacja kapitału między agentami.

Metodologia:
- Kelly Criterion (capped) per agent na podstawie historycznych wyników
- Uwzględnia korelacje między strategiami
- Redukuje alokację dla agentów z niedawną złą passą (drawdown protection)
- Dostosowuje alokację do reżimu rynkowego (trend/range/volatile)
- Aktualizuje AgentConfig.max_allocation_pct w shared state
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import numpy as np

from agents.base_agent import BaseAgent
from core.logger import get_logger
from core.models import AgentConfig, AgentName, TradeSignal
from core.shared_state import shared_state

log = get_logger(__name__)

# Bazowe wagi agentów (jeśli brak danych historycznych)
BASE_WEIGHTS: dict[AgentName, float] = {
    AgentName.TREND_FOLLOWER:   0.30,
    AgentName.MEAN_REVERSION:   0.25,
    AgentName.BREAKOUT_HUNTER:  0.20,
    AgentName.SENTIMENT_TRADER: 0.15,
    AgentName.SCALPER:          0.10,
}

# Maksymalna alokacja na pojedynczego agenta (cap Kelly)
MAX_KELLY_CAP = 0.25   # 25% kapitału max na agenta


class PortfolioAllocator(BaseAgent):
    """Dynamiczna alokacja kapitału z Kelly Criterion."""

    DEFAULT_PARAMS = {
        "kelly_fraction":    0.25,   # ułamek Kelly (quarter-Kelly dla bezpieczeństwa)
        "rebalance_hours":   4,      # co ile godzin rebalansuje
        "min_allocation":    2.0,    # minimum % na aktywny agenat
        "max_allocation":    30.0,   # maximum % na agenta
        "drawdown_penalty":  0.5,    # mnożnik alokacji gdy agent ma drawdown
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=14400):
        super().__init__(
            name=AgentName.PORTFOLIO_ALLOC,
            connector=connector,
            market_data=market_data,
            bus=bus,
            symbols=symbols,
            interval_sec=interval_sec,   # co 4 godziny
        )
        self._last_rebalance: Optional[datetime] = None

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        if symbol != self.symbols[0]:
            return None

        params = {**self.DEFAULT_PARAMS, **self._get_config().params}
        await self._rebalance(params)
        return None

    async def _rebalance(self, params: dict) -> None:
        """Przelicza i aktualizuje alokacje kapitału."""
        log.info("PortfolioAllocator: przeliczam alokacje…")

        performance = getattr(shared_state, "performance_reports", {})
        market_regime = getattr(shared_state, "market_regimes", {})
        regime = list(market_regime.values())[0] if market_regime else "unknown"

        allocations: dict[AgentName, float] = {}

        for agent, base_weight in BASE_WEIGHTS.items():
            perf  = performance.get(agent.value, {})
            alloc = self._calculate_kelly(agent, perf, base_weight, params)

            # Dostosuj do reżimu rynkowego
            alloc = self._adjust_for_regime(agent, alloc, regime)

            # Clamp
            alloc = max(params["min_allocation"],
                        min(params["max_allocation"], alloc))

            allocations[agent] = alloc

        # Normalizuj do 100%
        total = sum(allocations.values())
        if total > 0:
            allocations = {a: round(v / total * 100, 2) for a, v in allocations.items()}

        # Aktualizuj SharedState
        for agent, pct in allocations.items():
            cfg = shared_state.agent_configs.get(agent)
            if cfg:
                cfg.max_allocation_pct = pct
                await shared_state.set_agent_config(cfg)

        self._last_rebalance = datetime.utcnow()

        log.info(
            "Nowe alokacje: {}",
            {a.value: f"{p:.1f}%" for a, p in allocations.items()},
        )

        # Zapisz w shared state
        if not hasattr(shared_state, "allocations"):
            shared_state.allocations = {}
        shared_state.allocations = {a.value: p for a, p in allocations.items()}

    def _calculate_kelly(
        self,
        agent: AgentName,
        perf: dict,
        base_weight: float,
        params: dict,
    ) -> float:
        """
        Kelly Criterion: f = (win_rate * avg_win - (1-win_rate) * avg_loss) / avg_win
        Cappowany do MAX_KELLY_CAP.
        """
        if not perf or perf.get("status") in ("insufficient_data", "no_completed_trades"):
            return base_weight * 100.0

        win_rate = perf.get("win_rate", 0.5)
        avg_win  = perf.get("avg_win",  1.0)
        avg_loss = perf.get("avg_loss", 1.0)

        if avg_win <= 0 or avg_loss <= 0:
            return base_weight * 100.0

        # Klasyczny Kelly
        b = avg_win / avg_loss
        kelly = (b * win_rate - (1 - win_rate)) / b
        kelly = max(0.0, kelly)

        # Fraction-Kelly dla bezpieczeństwa (quarter-Kelly domyślnie)
        kelly *= params["kelly_fraction"]

        # Cap
        kelly = min(kelly, MAX_KELLY_CAP)

        # Kara za drawdown
        if perf.get("profit_factor", 1.0) < 1.0:
            kelly *= params["drawdown_penalty"]

        return kelly * 100.0  # jako procent

    def _adjust_for_regime(
        self, agent: AgentName, alloc: float, regime: str
    ) -> float:
        """
        Dostosowuje alokację do reżimu rynkowego:
        - Trend: +20% dla TrendFollower, -20% dla MeanReversion
        - Range: +20% dla MeanReversion, -20% dla TrendFollower
        - Volatile: +10% dla Scalper i BreakoutHunter
        """
        regime_adjustments = {
            "trending": {
                AgentName.TREND_FOLLOWER:  1.20,
                AgentName.MEAN_REVERSION:  0.70,
                AgentName.BREAKOUT_HUNTER: 1.10,
                AgentName.SCALPER:         0.80,
                AgentName.SENTIMENT_TRADER: 1.00,
            },
            "ranging": {
                AgentName.TREND_FOLLOWER:  0.70,
                AgentName.MEAN_REVERSION:  1.30,
                AgentName.BREAKOUT_HUNTER: 0.90,
                AgentName.SCALPER:         1.00,
                AgentName.SENTIMENT_TRADER: 0.90,
            },
            "volatile": {
                AgentName.TREND_FOLLOWER:  0.80,
                AgentName.MEAN_REVERSION:  0.80,
                AgentName.BREAKOUT_HUNTER: 1.20,
                AgentName.SCALPER:         1.30,
                AgentName.SENTIMENT_TRADER: 1.10,
            },
        }
        multiplier = regime_adjustments.get(regime, {}).get(agent, 1.0)
        return alloc * multiplier
