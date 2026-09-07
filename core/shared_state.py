"""
SharedState – singleton przechowujący globalny stan systemu w pamięci.

Jest jednym źródłem prawdy dla:
- statusów agentów
- konfiguracji agentów
- otwartych pozycji
- limitów ryzyka
- flagi emergency stop

Persystencja do bazy danych odbywa się oddzielnie (w tle).
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from core.logger import get_logger
from core.models import (
    AccountSummary,
    AgentConfig,
    AgentName,
    AgentState,
    AgentStatus,
    Position,
    RiskLimits,
    TradeSignal,
)

log = get_logger(__name__)


class SharedState:
    """Thread-safe (asyncio) singleton stanu systemu."""

    _instance: Optional["SharedState"] = None

    def __new__(cls) -> "SharedState":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        if self._initialized:
            return
        self._initialized = True

        self._lock = asyncio.Lock()

        # Limity ryzyka
        self.risk_limits = RiskLimits()

        # Konfiguracje agentów (domyślne)
        self.agent_configs: dict[AgentName, AgentConfig] = {
            name: AgentConfig(agent_name=name) for name in AgentName
        }

        # Stany agentów
        self.agent_states: dict[AgentName, AgentState] = {
            name: AgentState(agent_name=name) for name in AgentName
        }

        # Pozycje
        self.positions: dict[str, Position] = {}

        # Podsumowanie rachunku
        self.account: AccountSummary = AccountSummary()

        # PnL per agent (dzisiaj)
        self.agent_pnl: dict[AgentName, float] = {name: 0.0 for name in AgentName}

        # Ostatnie sygnały (dla panelu)
        self.recent_signals: list[TradeSignal] = []

        # Flaga ON/OFF agentów
        self.agents_running: bool = True
        self._max_recent = 50

        # Dzienny PnL systemu
        self.daily_pnl: float = 0.0
        self.peak_equity: float = 0.0
        self.current_drawdown_pct: float = 0.0

        log.info("SharedState zainicjalizowany")

    # ──────────────────────────────────────────────────────────────────────────
    # Emergency Stop
    # ──────────────────────────────────────────────────────────────────────────

    async def trigger_emergency_stop(self, reason: str = "manual") -> None:
        async with self._lock:
            self.risk_limits.emergency_stop = True
            self.risk_limits.emergency_stop_ts = datetime.utcnow()
            log.critical("🚨 EMERGENCY STOP AKTYWOWANY | Powód: {}", reason)

    async def clear_emergency_stop(self) -> None:
        async with self._lock:
            self.risk_limits.emergency_stop = False
            self.risk_limits.emergency_stop_ts = None
            log.warning("✅ Emergency Stop odblokowany")

    @property
    def emergency_stop(self) -> bool:
        return self.risk_limits.emergency_stop

    # ──────────────────────────────────────────────────────────────────────────
    # Agent management
    # ──────────────────────────────────────────────────────────────────────────

    async def set_agent_status(self, name: AgentName, status: AgentStatus) -> None:
        async with self._lock:
            self.agent_states[name].status = status
            self.agent_states[name].updated_at = datetime.utcnow()

    async def set_agent_config(self, config: AgentConfig) -> None:
        async with self._lock:
            self.agent_configs[config.agent_name] = config

    def get_agent_config(self, name: AgentName) -> AgentConfig:
        return self.agent_configs.get(name, AgentConfig(agent_name=name))

    def is_agent_enabled(self, name: AgentName) -> bool:
        cfg = self.agent_configs.get(name)
        return cfg.enabled if cfg else False

    # ──────────────────────────────────────────────────────────────────────────
    # Pozycje
    # ──────────────────────────────────────────────────────────────────────────

    async def update_position(self, position: Position) -> None:
        async with self._lock:
            self.positions[position.symbol] = position

    async def remove_position(self, symbol: str) -> None:
        async with self._lock:
            self.positions.pop(symbol, None)

    def get_total_exposure_usd(self) -> float:
        return sum(abs(p.market_value) for p in self.positions.values())

    # ──────────────────────────────────────────────────────────────────────────
    # Sygnały
    # ──────────────────────────────────────────────────────────────────────────

    async def add_signal(self, signal: TradeSignal) -> None:
        async with self._lock:
            self.recent_signals.insert(0, signal)
            if len(self.recent_signals) > self._max_recent:
                self.recent_signals = self.recent_signals[: self._max_recent]
            self.agent_states[signal.agent_name].last_signal = signal
            self.agent_states[signal.agent_name].signals_today += 1

    # ──────────────────────────────────────────────────────────────────────────
    # PnL / drawdown
    # ──────────────────────────────────────────────────────────────────────────

    async def update_account(self, account: AccountSummary) -> None:
        async with self._lock:
            self.account = account
            self.daily_pnl = account.daily_pnl
            equity = account.net_liquidation
            if equity > self.peak_equity:
                self.peak_equity = equity
            if self.peak_equity > 0:
                self.current_drawdown_pct = (
                    (self.peak_equity - equity) / self.peak_equity * 100.0
                )

    # ──────────────────────────────────────────────────────────────────────────
    # Snapshot (dla API panelu)
    # ──────────────────────────────────────────────────────────────────────────

    def snapshot(self) -> dict:
        """Zwraca pełny snapshot stanu (dla REST / WebSocket)."""
        from config.settings import get_settings
        import datetime as _dt
        settings = get_settings()
        # Czas polski UTC+2
        now_pl = (_dt.datetime.utcnow() + _dt.timedelta(hours=2)).isoformat()
        return {
            "emergency_stop":  self.emergency_stop,
            "agents_running":  self.agents_running,
            "real_mode":       settings.real_mode,
            "paper_mode":      settings.alpaca_paper,
            "ibkr_connected":  getattr(self, "ibkr_connected", False),
            "daily_pnl":       self.daily_pnl,
            "drawdown_pct":    self.current_drawdown_pct,
            "account":         self.account.model_dump(),
            "positions":       {s: p.model_dump() for s, p in self.positions.items()},
            "agents": {
                n.value: {
                    "config": self.agent_configs[n].model_dump(),
                    "state":  self.agent_states[n].model_dump(),
                }
                for n in AgentName
            },
            "recent_signals": [s.model_dump() for s in self.recent_signals[:10]],
            "risk_limits":    self.risk_limits.model_dump(),
            "timestamp":      now_pl,
        }


# Globalny singleton
shared_state = SharedState()
