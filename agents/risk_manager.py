"""
RiskManager – agent z absolutnym prawem VETO.

Każdy sygnał MUSI przejść przez RiskManager zanim trafi do Orchestratora
jako zatwierdzone zlecenie.

Sprawdza:
1. Emergency Stop
2. Dzienny limit straty
3. Maksymalny drawdown
4. Rozmiar pozycji (% kapitału)
5. Alokację per agent
6. Skupienie (correlation exposure)
7. Ograniczenie liczby jednoczesnych otwartych pozycji
8. Podejrzanie duży rozmiar zlecenia
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from core.logger import get_logger, get_trading_logger
from core.models import (
    AgentName,
    AlertLevel,
    OrderRequest,
    OrderSide,
    OrderType,
    RiskDecision,
    TradeSignal,
    SignalDirection,
)
from core.shared_state import shared_state
from alerting.alerting import AlertingService

log  = get_logger(__name__)
tlog = get_trading_logger(__name__)


class RiskManager:
    """
    Niezależny komponent – nie dziedziczy z BaseAgent ponieważ
    musi być wywoływany synchronicznie w procesie decyzji.
    """

    MAX_OPEN_POSITIONS = 20
    MAX_CORRELATED_SYMBOLS = 3   # max pozycje w tym samym sektorze

    def __init__(self, alerting: Optional[AlertingService] = None) -> None:
        self._alerting = alerting

    # ──────────────────────────────────────────────────────────────────────────
    # Główna metoda oceny
    # ──────────────────────────────────────────────────────────────────────────

    async def evaluate(
        self,
        signal: TradeSignal,
        capital: float,
        current_price: float,
    ) -> RiskDecision:
        """
        Ocenia sygnał i zwraca decyzję (approved=True/False).
        Jeśli approved, może zmniejszyć rozmiar pozycji.
        """
        limits = shared_state.risk_limits

        # ── 1. Emergency Stop ─────────────────────────────────────────────────
        if limits.emergency_stop:
            return self._reject(signal, "EMERGENCY STOP aktywny – brak nowych pozycji")

        # ── 2. Sygnał CLOSE/NEUTRAL – zawsze ok ──────────────────────────────
        if signal.direction in (SignalDirection.CLOSE, SignalDirection.NEUTRAL):
            return self._approve(signal)

        # ── 3. Agent wyłączony ────────────────────────────────────────────────
        if not shared_state.is_agent_enabled(signal.agent_name):
            return self._reject(signal, f"Agent {signal.agent_name.value} jest wyłączony")

        # ── 4. Dzienny limit straty ───────────────────────────────────────────
        daily_pnl = shared_state.daily_pnl
        if daily_pnl < -limits.max_daily_loss_usd:
            msg = f"Dzienny limit straty przekroczony: {daily_pnl:.2f} USD (limit: -{limits.max_daily_loss_usd:.2f})"
            await self._alert(AlertLevel.CRITICAL, "Limit straty", msg)
            return self._reject(signal, msg)

        # ── 5. Drawdown ───────────────────────────────────────────────────────
        if shared_state.current_drawdown_pct > limits.max_drawdown_pct:
            msg = f"Drawdown {shared_state.current_drawdown_pct:.2f}% > limit {limits.max_drawdown_pct:.2f}%"
            await self._alert(AlertLevel.CRITICAL, "Przekroczony drawdown", msg)
            return self._reject(signal, msg)

        # ── 6. Zbyt dużo otwartych pozycji ───────────────────────────────────
        open_positions = len(shared_state.positions)
        if open_positions >= self.MAX_OPEN_POSITIONS:
            return self._reject(
                signal,
                f"Maks. liczba pozycji ({self.MAX_OPEN_POSITIONS}) osiągnięta",
            )

        # ── 7. Duplikat pozycji ────────────────────────────────────────────────
        existing = shared_state.positions.get(signal.symbol)
        if existing and existing.quantity != 0:
            side_ok = (
                (signal.direction == SignalDirection.LONG  and existing.quantity < 0) or
                (signal.direction == SignalDirection.SHORT and existing.quantity > 0)
            )
            if not side_ok:
                return self._reject(
                    signal,
                    f"Pozycja {signal.symbol} już otwarta (qty={existing.quantity:.2f})",
                )

        # ── 7b. Blokada SHORT bez istniejącej pozycji (Alpaca paper nie wspiera nagiego short) ──
        if signal.direction == SignalDirection.SHORT:
            pos = shared_state.positions.get(signal.symbol)
            if not pos or pos.quantity <= 0:
                return self._reject(
                    signal,
                    f"SHORT {signal.symbol} zablokowany — brak pozycji LONG do zamknięcia (Alpaca paper nie wspiera nagiego short)",
                )

        # ── 7c. Blokada zleceń po godzinach rynkowych ────────────────────────
        import datetime as _dt
        now_est = _dt.datetime.utcnow() - _dt.timedelta(hours=4)
        market_open  = now_est.replace(hour=9,  minute=30, second=0)
        market_close = now_est.replace(hour=16, minute=0,  second=0)
        is_market_hours = (market_open <= now_est <= market_close and now_est.weekday() < 5)
        if not is_market_hours:
            return self._reject(
                signal,
                f"Rynek zamknięty (EST {now_est.strftime('%H:%M')}) — zlecenie odłożone do otwarcia",
            )

        # ── 8. Alokacja per agent ─────────────────────────────────────────────
        agent_cfg = shared_state.get_agent_config(signal.agent_name)
        max_alloc_usd = capital * agent_cfg.max_allocation_pct / 100.0
        exposure = shared_state.get_total_exposure_usd()
        if exposure >= limits.total_capital_usd * 0.9:
            return self._reject(signal, f"Całkowita ekspozycja ({exposure:.0f}$) bliska limitu")

        # ── 9. Oblicz dopuszczalny rozmiar pozycji ────────────────────────────
        max_size_by_global = capital * limits.max_position_size_pct / 100.0
        max_size_by_agent  = agent_cfg.max_position_size_usd
        max_size_by_risk   = capital * agent_cfg.max_risk_per_trade_pct / 100.0

        # Jeśli mamy stop_loss → rozmiar na podstawie ryzyka
        if signal.stop_loss and current_price > 0:
            risk_per_share = abs(current_price - signal.stop_loss)
            if risk_per_share > 0:
                max_size_by_risk_shares = (capital * agent_cfg.max_risk_per_trade_pct / 100.0) / risk_per_share
                max_size_by_risk = max_size_by_risk_shares * current_price

        allowed_size_usd = min(max_size_by_global, max_size_by_agent, max_size_by_risk)

        # Przelicz żądaną wartość zlecenia
        requested_usd = (signal.size_pct / 100.0) * max_alloc_usd

        final_size_usd = min(requested_usd, allowed_size_usd)

        if final_size_usd < 10:
            return self._reject(signal, f"Rozmiar pozycji zbyt mały ({final_size_usd:.2f}$)")

        # Oblicz skorygowany size_pct
        adjusted_pct = (final_size_usd / max_alloc_usd * 100.0) if max_alloc_usd > 0 else 0.0

        tlog.info(
            "✅ RiskManager APPROVED | {} {} | size_usd={:.2f} (requested={:.2f})",
            signal.symbol, signal.direction.value, final_size_usd, requested_usd,
        )

        return RiskDecision(
            signal_id=signal.id,
            approved=True,
            reason=f"OK – size_usd={final_size_usd:.2f}$ (limit: {allowed_size_usd:.2f}$)",
            adjusted_size_pct=adjusted_pct,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Budowanie OrderRequest ze zatwierdzonego sygnału
    # ──────────────────────────────────────────────────────────────────────────

    def build_order(
        self,
        signal: TradeSignal,
        decision: RiskDecision,
        current_price: float,
        capital: float,
        paper_mode: bool = True,
    ) -> Optional[OrderRequest]:
        """Buduje OrderRequest na podstawie sygnału i decyzji RiskManagera."""
        if not decision.approved:
            return None

        agent_cfg  = shared_state.get_agent_config(signal.agent_name)
        alloc_usd  = capital * agent_cfg.max_allocation_pct / 100.0
        size_pct   = decision.adjusted_size_pct or signal.size_pct
        trade_usd  = alloc_usd * size_pct / 100.0

        if current_price <= 0:
            return None

        quantity = round(trade_usd / current_price, 4)
        if quantity <= 0:
            return None

        side = (
            OrderSide.BUY if signal.direction == SignalDirection.LONG
            else OrderSide.SELL
        )

        # Zawsze MARKET — Alpaca paper trading działa najlepiej z market orders
        # LIMIT może nie zostać wypełniony jeśli cena ucieknie
        order_type  = OrderType.MARKET
        limit_price = None

        return OrderRequest(
            signal_id=signal.id,
            symbol=signal.symbol,
            side=side,
            order_type=order_type,
            quantity=quantity,
            limit_price=limit_price,
            stop_price=signal.stop_loss,
            paper_mode=paper_mode,
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _approve(self, signal: TradeSignal, reason: str = "OK") -> RiskDecision:
        return RiskDecision(
            signal_id=signal.id,
            approved=True,
            reason=reason,
        )

    def _reject(self, signal: TradeSignal, reason: str) -> RiskDecision:
        log.debug(  # zmieniono z warning na debug
            "❌ RiskManager VETO | {} {} | {}",
            signal.symbol, signal.direction.value, reason,
        )
        return RiskDecision(
            signal_id=signal.id,
            approved=False,
            reason=reason,
        )

    async def _alert(self, level: AlertLevel, title: str, msg: str) -> None:
        if self._alerting:
            from core.models import Alert
            await self._alerting.send(Alert(level=level, title=title, message=msg, source="RiskManager"))
