"""
CorrelationGuard – „Strażnik Korelacji"

Wykrywa gdy zbyt wiele pozycji jest skorelowanych — ryzyko systemowe.
Jeśli >60% pozycji idzie w tym samym kierunku na skorelowanych aktywach → alert.
"""
from __future__ import annotations
from datetime import datetime
from typing import Optional
from agents.base_agent import BaseAgent
from core.models import AgentName, SignalDirection, TradeSignal
from core.shared_state import shared_state
from core.logger import get_logger

log = get_logger(__name__)

# Grupy aktywów silnie skorelowanych
CORRELATION_GROUPS = {
    "tech":    ["AAPL","MSFT","NVDA","GOOGL","META","AMZN","AMD"],
    "crypto":  ["BTC","ETH","SOL","BNB","AVAX","ADA"],
    "energy":  ["XOM","CVX","OXY","SLB","BP"],
    "finance": ["JPM","BAC","GS","V","MA"],
    "index":   ["SPY","QQQ","IWM","DIA"],
}

MAX_CORRELATED_PCT = 0.6  # max 60% pozycji z tej samej grupy


class CorrelationGuard(BaseAgent):

    PERSONALITY = "Strażnik Korelacji — chronię przed ryzykiem skupienia"

    DEFAULT_PARAMS = {
        "check_interval_sec": 300,
        "max_group_pct":      0.6,
        "alert_threshold":    3,   # min pozycji w grupie do alertu
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=300):
        super().__init__(
            name=AgentName.CORRELATION_GUARD,
            connector=connector, market_data=market_data,
            bus=bus, symbols=symbols, interval_sec=interval_sec,
        )

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        if symbol != self.symbols[0]:
            return None

        params   = {**self.DEFAULT_PARAMS, **self._get_config().params}
        positions = shared_state.positions

        if len(positions) < 2:
            return None

        # Sprawdź skupienie w grupach korelacji
        for group_name, group_symbols in CORRELATION_GROUPS.items():
            group_positions = [s for s in positions.keys() if s in group_symbols]
            if len(group_positions) < params["alert_threshold"]:
                continue

            group_pct = len(group_positions) / max(len(positions), 1)
            if group_pct >= params["max_group_pct"]:
                msg = (f"⚠️ Skupienie w grupie '{group_name}': "
                       f"{len(group_positions)}/{len(positions)} pozycji "
                       f"({group_pct:.0%}) — ryzyko systemowe!")
                log.warning("CorrelationGuard: {}", msg)
                await self._bus.publish("alerts", {
                    "level":     "WARNING",
                    "title":     f"Skupienie korelacji: {group_name}",
                    "message":   msg,
                    "source":    "CorrelationGuard",
                    "timestamp": datetime.utcnow().isoformat(),
                })

        # Zapisz raport do shared_state
        if not hasattr(shared_state, "correlation_report"):
            shared_state.correlation_report = {}

        report = {}
        for group_name, group_symbols in CORRELATION_GROUPS.items():
            in_group = [s for s in positions.keys() if s in group_symbols]
            if in_group:
                report[group_name] = {
                    "symbols": in_group,
                    "count":   len(in_group),
                    "pct":     round(len(in_group) / max(len(positions), 1) * 100, 1),
                }
        shared_state.correlation_report = report

        return None
