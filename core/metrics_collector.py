"""
MetricsCollector - zbiera i zapisuje metryki systemu co 1 minutę.

Uruchamiany jako background task przez orchestrator.
Zapełnia tabele: equity_snapshots, system_metrics, agent_events.
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Optional

import psutil

from core.logger import get_logger
from core.shared_state import shared_state
from database.database import get_session
from database.models import DBEquitySnapshot, DBSystemMetric, DBAgentEvent

log = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# Singleton kolektor
# ─────────────────────────────────────────────────────────────────────────────

class MetricsCollector:
    """
    Background worker zbierający metryki systemowe i equity snapshots.

    Uruchomienie:
        collector = MetricsCollector()
        asyncio.create_task(collector.run())
    """

    def __init__(self, interval_sec: int = 60):
        self.interval_sec  = interval_sec
        self._running      = False
        self._start_time   = time.time()
        self._errors_today = 0
        self._last_day     = datetime.now(timezone.utc).date()

    # ── Główna pętla ─────────────────────────────────────────────────────────

    async def run(self) -> None:
        self._running = True
        log.info("MetricsCollector uruchomiony (interval={}s)", self.interval_sec)

        while self._running:
            try:
                await self._collect()
            except Exception as e:
                log.error("MetricsCollector błąd: {}", e)
            await asyncio.sleep(self.interval_sec)

    def stop(self) -> None:
        self._running = False

    # ── Zbieranie danych ─────────────────────────────────────────────────────

    async def _collect(self) -> None:
        now = datetime.now(timezone.utc)

        # Reset błędów o północy
        if now.date() != self._last_day:
            self._errors_today = 0
            self._last_day = now.date()

        snap = shared_state.snapshot()

        async with get_session() as session:
            # ── 1. Equity snapshot ────────────────────────────────────────
            equity = DBEquitySnapshot(
                timestamp       = now,
                net_liquidation = snap.get("net_liquidation", 0.0),
                daily_pnl       = snap.get("daily_pnl", 0.0),
                unrealized_pnl  = snap.get("unrealized_pnl", 0.0),
                realized_pnl    = snap.get("realized_pnl", 0.0),
                drawdown_pct    = snap.get("drawdown_pct", 0.0),
                open_positions  = len(snap.get("positions", {})),
                agent_pnl       = snap.get("agent_pnl", {}),
                paper_mode      = snap.get("paper_mode", True),
            )
            session.add(equity)

            # ── 2. Metryki systemowe ──────────────────────────────────────
            cpu = psutil.cpu_percent(interval=None)
            ram = psutil.virtual_memory()

            # Policz sygnały i zlecenia z dziś
            signals_today = len([
                s for s in snap.get("recent_signals", [])
            ])
            active_agents = sum(
                1 for a in snap.get("agents", {}).values()
                if a.get("enabled") and a.get("running")
            )

            metric = DBSystemMetric(
                timestamp      = now,
                cpu_pct        = cpu,
                ram_pct        = ram.percent,
                ram_mb         = ram.used / 1024 / 1024,
                ibkr_connected = snap.get("ibkr_connected", False),
                active_agents  = active_agents,
                signals_today  = signals_today,
                errors_today   = self._errors_today,
            )
            session.add(metric)

            await session.commit()

    # ── Rejestracja zdarzeń agentów (wołane z zewnątrz) ──────────────────────

    @staticmethod
    async def record_event(
        agent_name: str,
        event_type: str,
        symbol:     Optional[str]  = None,
        direction:  Optional[str]  = None,
        price:      Optional[float] = None,
        quantity:   Optional[float] = None,
        pnl:        Optional[float] = None,
        confidence: Optional[float] = None,
        reasoning:  Optional[str]  = None,
        details:    Optional[dict] = None,
        paper_mode: bool = True,
    ) -> None:
        """
        Zapisuje zdarzenie agenta do tabeli agent_events.
        Wołaj z orchestratora, agentów, risk managera.

        Przykład:
            await MetricsCollector.record_event(
                agent_name="momentum_surfer",
                event_type="signal_generated",
                symbol="AAPL",
                direction="BUY",
                confidence=0.82,
                reasoning="RSI oversold + volume spike",
            )
        """
        try:
            async with get_session() as session:
                event = DBAgentEvent(
                    timestamp  = datetime.now(timezone.utc),
                    agent_name = agent_name,
                    event_type = event_type,
                    symbol     = symbol,
                    direction  = direction,
                    price      = price,
                    quantity   = quantity,
                    pnl        = pnl,
                    confidence = confidence,
                    reasoning  = reasoning,
                    details    = details or {},
                    paper_mode = paper_mode,
                )
                session.add(event)
                await session.commit()
        except Exception as e:
            log.error("Błąd zapisu agent_event: {}", e)

    def increment_errors(self) -> None:
        """Wywołaj gdy wykryjesz błąd systemowy."""
        self._errors_today += 1


# ── Globalny singleton ────────────────────────────────────────────────────────
metrics_collector = MetricsCollector(interval_sec=60)
