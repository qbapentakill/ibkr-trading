"""
Bazowa klasa wszystkich agentów tradingowych i pomocniczych.

Każdy agent:
- Dziedziczy z BaseAgent
- Implementuje metodę analyze() → TradeSignal | None
- Ma własną pętlę asyncio z konfigurowalnym interwałem
- Zgłasza sygnały przez message bus
- Może być włączony/wyłączony w locie przez SharedState
"""
from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from core.logger import get_logger, get_trading_logger
from core.models import (
    AgentName,
    AgentState,
    AgentStatus,
    TradeSignal,
)
from core.shared_state import shared_state

if TYPE_CHECKING:
    from core.ibkr_connector import IBKRConnector
    from services.market_data import MarketDataService
    from core.message_bus import MessageBus

log = get_logger(__name__)
tlog = get_trading_logger(__name__)


class BaseAgent(ABC):
    """
    Abstrakcyjna klasa bazowa dla wszystkich agentów.

    Parametry konstruktora:
        name        – unikalna nazwa agenta (AgentName enum)
        connector   – IBKR connector
        market_data – serwis danych rynkowych
        bus         – message bus (Redis/asyncio)
        symbols     – lista tickerów do obserwacji
        interval_sec – jak często wywoływać analyze()
    """

    def __init__(
        self,
        name: AgentName,
        connector: "IBKRConnector",
        market_data: "MarketDataService",
        bus: "MessageBus",
        symbols: list[str],
        interval_sec: int = 60,
    ) -> None:
        self.name          = name
        self._connector    = connector
        self._market_data  = market_data
        self._bus          = bus
        self.symbols       = symbols
        self.interval_sec  = interval_sec

        self._running      = False
        self._task: Optional[asyncio.Task] = None
        self._log          = get_logger(f"agent.{name.value}")
        self._tlog         = get_trading_logger(f"agent.{name.value}")

    # ──────────────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Uruchamia pętlę agenta."""
        if self._running:
            return
        self._running = True
        await shared_state.set_agent_status(self.name, AgentStatus.ACTIVE)
        self._task = asyncio.create_task(self._run_loop(), name=f"agent_{self.name.value}")
        self._log.info("▶ Agent {} uruchomiony (interwał {}s)", self.name.value, self.interval_sec)

    async def stop(self) -> None:
        """Zatrzymuje pętlę agenta."""
        self._running = False
        await shared_state.set_agent_status(self.name, AgentStatus.DISABLED)
        if self._task and not self._task.done():
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        self._log.info("⏹ Agent {} zatrzymany", self.name.value)

    async def restart(self) -> None:
        await self.stop()
        await asyncio.sleep(1)
        await self.start()

    # ──────────────────────────────────────────────────────────────────────────
    # Pętla główna
    # ──────────────────────────────────────────────────────────────────────────

    async def _run_loop(self) -> None:
        while self._running:
            # Sprawdź czy agent jest włączony w SharedState
            if not shared_state.is_agent_enabled(self.name):
                self._log.debug("Agent {} wyłączony – czekam…", self.name.value)
                await asyncio.sleep(self.interval_sec)
                continue

            # Sprawdź Emergency Stop
            if shared_state.emergency_stop:
                self._log.warning("EMERGENCY STOP aktywny – agent {} wstrzymany", self.name.value)
                await asyncio.sleep(5)
                continue

            try:
                for symbol in self.symbols:
                    signal = await self.analyze(symbol)
                    if signal is not None:
                        await self._emit_signal(signal)
            except asyncio.CancelledError:
                break
            except Exception as exc:
                self._log.error("Błąd w pętli agenta {}: {}", self.name.value, exc)
                await shared_state.set_agent_status(self.name, AgentStatus.ERROR)
                state = shared_state.agent_states[self.name]
                state.last_error = str(exc)
                await asyncio.sleep(min(self.interval_sec, 30))
                await shared_state.set_agent_status(self.name, AgentStatus.ACTIVE)

            await asyncio.sleep(self.interval_sec)

    # ──────────────────────────────────────────────────────────────────────────
    # Abstrakcja do implementacji przez podklasy
    # ──────────────────────────────────────────────────────────────────────────

    @abstractmethod
    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        """
        Główna logika analizy. Zwraca TradeSignal lub None.
        Każdy sygnał MUSI zawierać reasoning – uzasadnienie decyzji.
        """
        ...

    # ──────────────────────────────────────────────────────────────────────────
    # Emisja sygnału
    # ──────────────────────────────────────────────────────────────────────────

    async def _emit_signal(self, signal: TradeSignal) -> None:
        """Publikuje sygnał na message bus i zapisuje w SharedState."""
        await shared_state.add_signal(signal)
        await self._bus.publish("signals", signal.model_dump())
        self._tlog.info(
            "📡 Sygnał | agent={} symbol={} dir={} conf={:.2f} | {}",
            signal.agent_name.value,
            signal.symbol,
            signal.direction.value,
            signal.confidence,
            signal.reasoning[:120],
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers dla podklas
    # ──────────────────────────────────────────────────────────────────────────

    def _get_config(self):
        return shared_state.get_agent_config(self.name)
