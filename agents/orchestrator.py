"""
Orchestrator – centralny agregator sygnałów.

Algorytm decyzji:
1. Zbiera sygnały z message busa (kanał 'signals')
2. Grupuje sygnały per symbol (okno agregacji ~5s)
3. Oblicza ważony wynik na podstawie pewności i wag agentów
4. Przekazuje do RiskManagera
5. Jeśli zatwierdzone → buduje OrderRequest → IBKR
6. Zapisuje wszystko do bazy danych
7. Publikuje wyniki na kanał 'orders' i 'audit'

Wagi agentów (konfigurowane, domyślnie):
  TrendFollower   0.25
  MeanReversion   0.20
  BreakoutHunter  0.20
  SentimentTrader 0.15
  Scalper         0.10
  (pozostałe)     0.10
"""
from __future__ import annotations

import asyncio
from collections import defaultdict
from datetime import datetime
from typing import Any, Optional

from config.settings import get_settings
from core.ibkr_connector import IBKRConnector
from core.logger import get_logger, get_trading_logger
from core.message_bus import MessageBus
from core.models import (
    AgentName,
    AlertLevel,
    OrderRequest,
    OrderResult,
    SignalDirection,
    TradeSignal,
)
from core.shared_state import shared_state
from agents.risk_manager import RiskManager
from database.database import get_session
from database.models import DBOrder, DBSignal

log  = get_logger(__name__)
tlog = get_trading_logger(__name__)

# Wagi agentów w agregacji sygnałów
AGENT_WEIGHTS: dict[AgentName, float] = {
    AgentName.TREND_FOLLOWER:    0.18,
    AgentName.MEAN_REVERSION:    0.15,
    AgentName.BREAKOUT_HUNTER:   0.15,
    AgentName.SENTIMENT_TRADER:  0.10,
    AgentName.SCALPER:           0.07,
    AgentName.OPTIONS_FLOW:      0.10,
    AgentName.GAP_TRADER:        0.06,
    AgentName.MOMENTUM_SURFER:   0.08,
    AgentName.VIX_TRADER:        0.05,
    AgentName.DIVERGENCE_HUNTER: 0.08,
    AgentName.SCALP_KING:        0.05,
    AgentName.MARKET_ANALYST:    0.03,
    AgentName.NEWS_ANALYST:      0.03,
    AgentName.WHALE_TRACKER:     0.03,
}

# Minimalny ważony wynik do otwarcia pozycji
MIN_CONSENSUS_SCORE = 0.15

# Okno agregacji sygnałów (sekundy)
AGGREGATION_WINDOW_SEC = 5.0


class Orchestrator:
    """
    Łączy wszystkie komponenty systemu i zarządza procesem
    od sygnału do zlecenia.
    """

    def __init__(
        self,
        connector: IBKRConnector,
        bus: MessageBus,
        risk_manager: RiskManager,
    ) -> None:
        self._connector    = connector
        self._bus          = bus
        self._risk_manager = risk_manager
        self._settings     = get_settings()

        # Bufor sygnałów czekający na agregację {symbol: [signals]}
        self._signal_buffer: dict[str, list[TradeSignal]] = defaultdict(list)
        self._buffer_lock   = asyncio.Lock()
        self._flush_task:  Optional[asyncio.Task] = None
        self._running = False

    # ──────────────────────────────────────────────────────────────────────────
    # Lifecycle
    # ──────────────────────────────────────────────────────────────────────────

    async def start(self) -> None:
        if self._running:
            return
        self._running = True
        # Subskrybuj sygnały z bus
        self._bus.subscribe("signals", self._on_signal)
        # Uruchom pętlę flushującą agregator
        self._flush_task = asyncio.create_task(
            self._flush_loop(), name="orchestrator_flush"
        )
        log.info("✅ Orchestrator uruchomiony")

    async def stop(self) -> None:
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError:
                pass
        log.info("Orchestrator zatrzymany")

    # ──────────────────────────────────────────────────────────────────────────
    # Odbiór sygnałów
    # ──────────────────────────────────────────────────────────────────────────

    async def _on_signal(self, message: dict) -> None:
        """Handler wywoływany przez MessageBus przy nowym sygnale."""
        try:
            # model_dump() serializuje enums jako stringi — używamy model_validate
            signal = TradeSignal.model_validate(message)
        except Exception as exc:
            log.error("Błąd parsowania sygnału: {}", exc)
            return

        async with self._buffer_lock:
            self._signal_buffer[signal.symbol].append(signal)

        # Zapis do DB w tle z obsługą błędów
        task = asyncio.create_task(self._persist_signal(signal))
        task.add_done_callback(
            lambda t: log.error("Błąd zapisu sygnału: {}", t.exception())
            if t.exception() else None
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Agregacja i decyzja
    # ──────────────────────────────────────────────────────────────────────────

    async def _flush_loop(self) -> None:
        """Co AGGREGATION_WINDOW_SEC przetwarza bufor sygnałów."""
        while self._running:
            await asyncio.sleep(AGGREGATION_WINDOW_SEC)
            if shared_state.emergency_stop:
                continue
            async with self._buffer_lock:
                symbols = list(self._signal_buffer.keys())
                buffer_snapshot = {s: list(self._signal_buffer[s]) for s in symbols}
                self._signal_buffer.clear()

            for symbol, signals in buffer_snapshot.items():
                if signals:
                    await self._process_signals(symbol, signals)

    async def _process_signals(self, symbol: str, signals: list[TradeSignal]) -> None:
        """Agreguje sygnały dla jednego symbolu i podejmuje decyzję."""

        # Filtruj tylko LONG/SHORT (nie CLOSE/NEUTRAL)
        actionable = [s for s in signals if s.direction in (SignalDirection.LONG, SignalDirection.SHORT)]
        close_signals = [s for s in signals if s.direction == SignalDirection.CLOSE]

        # CLOSE – natychmiast zamknij pozycję jeśli >50% agentów chce zamknąć
        if close_signals and len(close_signals) / max(len(signals), 1) >= 0.5:
            await self._handle_close(symbol, close_signals)
            return

        if not actionable:
            return

        # Oblicz wynik ważony
        long_score  = 0.0
        short_score = 0.0
        total_weight = 0.0
        reasoning_parts: list[str] = []

        for s in actionable:
            w = AGENT_WEIGHTS.get(s.agent_name, 0.05)
            weighted_conf = w * s.confidence
            if s.direction == SignalDirection.LONG:
                long_score += weighted_conf
            else:
                short_score += weighted_conf
            total_weight += w
            reasoning_parts.append(
                f"{s.agent_name.value}({s.direction.value},{s.confidence:.2f})"
            )

        # Normalizuj
        if total_weight > 0:
            long_score  /= total_weight
            short_score /= total_weight

        best_direction = SignalDirection.LONG if long_score >= short_score else SignalDirection.SHORT
        best_score     = max(long_score, short_score)

        reasoning = (
            f"Agregacja {len(actionable)} sygnałów: {', '.join(reasoning_parts)}. "
            f"Wynik: LONG={long_score:.3f} SHORT={short_score:.3f} → {best_direction.value}"
        )

        log.info("📊 Aggregacja {} | score={:.3f} ({}) | {}", 
                 symbol, best_score, best_direction.value, reasoning[:100])

        if best_score < MIN_CONSENSUS_SCORE:
            log.debug("Brak konsensusu dla {} (score={:.3f} < {})", 
                     symbol, best_score, MIN_CONSENSUS_SCORE)
            return

        # Wybierz reprezentatywny sygnał (najwyższa pewność w zwycięskim kierunku)
        best_signal = max(
            [s for s in actionable if s.direction == best_direction],
            key=lambda s: s.confidence,
        )
        # Aktualizuj reasoning
        best_signal = best_signal.model_copy(update={"reasoning": reasoning})

        # Pobierz aktualną cenę
        try:
            quote = await self._connector.get_quote(symbol)
            current_price = quote.last
        except Exception:
            current_price = best_signal.entry_price or 0.0

        # Pobierz kapitał
        account  = await self._connector.get_account()
        capital  = account.net_liquidation or self._settings.total_capital_usd

        # RiskManager VETO
        decision = await self._risk_manager.evaluate(best_signal, capital, current_price)

        if not decision.approved:
            log.warning("VETO RiskManager: {} | {}", symbol, decision.reason)
            await self._persist_signal_decision(best_signal.id, False, decision.reason)
            return

        await self._persist_signal_decision(best_signal.id, True, decision.reason)

        # Buduj i złóż zlecenie
        order = self._risk_manager.build_order(
            best_signal,
            decision,
            current_price,
            capital,
            paper_mode=self._settings.alpaca_paper,
        )
        if not order:
            return

        result = await self._connector.place_order(order)

        # Nie zapisuj odrzuconych zleceń do bazy (rynek zamknięty itp.)
        if result.status.value == "rejected":
            log.debug("Zlecenie odrzucone przez Alpaca: {}", result.error_msg)
            return

        # ── Poczekaj 2s i zsynchronizuj pozycje z Alpaca ─────────────────────
        await asyncio.sleep(2)
        filled_price = current_price  # fallback
        try:
            positions = await self._connector.get_positions()
            for sym, pos in positions.items():
                await shared_state.update_position(pos)
            for sym in list(shared_state.positions.keys()):
                if sym not in positions:
                    await shared_state.remove_position(sym)
            # Pobierz rzeczywistą cenę wypełnienia z Alpaca
            if self._connector._trading_client:
                alpaca_orders = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self._connector._trading_client.get_orders()
                )
                for ao in alpaca_orders:
                    if str(ao.id) and ao.symbol == symbol:
                        if ao.filled_avg_price:
                            filled_price = float(ao.filled_avg_price)
                            break
        except Exception as exc:
            log.debug("Błąd sync pozycji po zleceniu: {}", exc)

        await self._persist_order(order, result, entry_price=current_price)
        await self._bus.publish("audit", {
            "event":     "order_placed",
            "symbol":    symbol,
            "side":      order.side.value,
            "quantity":  order.quantity,
            "status":    result.status.value,
            "reasoning": reasoning,
            "timestamp": datetime.utcnow().isoformat(),
        })

        # ── Coach ocenia zamknięcie pozycji ───────────────────────────────────
        try:
            from agents.auxiliary.coach import get_coach
            if order.side.value == "SELL":
                # Znajdź cenę wejścia z poprzedniej pozycji
                entry_price = current_price  # fallback
                pos_before  = shared_state.positions.get(symbol)
                if pos_before and pos_before.avg_cost > 0:
                    entry_price = pos_before.avg_cost
                exit_price = filled_price if filled_price > 0 else current_price
                if entry_price > 0 and exit_price > 0:
                    pnl_usd = (exit_price - entry_price) * order.quantity
                    pnl_pct = (pnl_usd / (entry_price * order.quantity)) * 100
                    get_coach().review_trade(
                        agent_name = best_signal.agent_name.value,
                        symbol     = symbol,
                        direction  = "LONG",
                        pnl_usd    = pnl_usd,
                        pnl_pct    = pnl_pct,
                        trade_id   = order.id,
                    )
            # BUY — nie oceniamy bez znajomości PnL
        except Exception as exc:
            log.debug("Błąd oceny Szefa: {}", exc)

    async def _handle_close(self, symbol: str, signals: list[TradeSignal]) -> None:
        """Zamknięcie pozycji na żądanie agentów."""
        pos = shared_state.positions.get(symbol)
        if not pos or pos.quantity == 0:
            return

        from core.models import OrderSide, OrderType
        side = OrderSide.SELL if pos.quantity > 0 else OrderSide.BUY
        order = OrderRequest(
            signal_id=signals[0].id,
            symbol=symbol,
            side=side,
            quantity=abs(pos.quantity),
            paper_mode=self._settings.alpaca_paper,
        )
        result = await self._connector.place_order(order)
        tlog.info("🔒 Zamknięto pozycję {} | qty={} | status={}", 
                  symbol, pos.quantity, result.status.value)

    # ──────────────────────────────────────────────────────────────────────────
    # Persystencja
    # ──────────────────────────────────────────────────────────────────────────

    async def _persist_signal(self, signal: TradeSignal) -> None:
        try:
            async with get_session() as session:
                row = DBSignal(
                    signal_id=signal.id,
                    agent_name=signal.agent_name.value,
                    symbol=signal.symbol,
                    direction=signal.direction.value,
                    confidence=signal.confidence,
                    entry_price=signal.entry_price,
                    stop_loss=signal.stop_loss,
                    take_profit=signal.take_profit,
                    size_pct=signal.size_pct,
                    reasoning=signal.reasoning,
                    raw_indicators=signal.raw_indicators,
                    timeframe=signal.timeframe,
                    timestamp=signal.timestamp,
                )
                session.add(row)
        except Exception as exc:
            log.error("Błąd zapisu sygnału do DB: {}", exc)

    async def _persist_signal_decision(
        self, signal_id: str, approved: bool, reason: str
    ) -> None:
        try:
            from sqlalchemy import update
            async with get_session() as session:
                await session.execute(
                    update(DBSignal)
                    .where(DBSignal.signal_id == signal_id)
                    .values(approved=approved, reject_reason=reason if not approved else None)
                )
        except Exception as exc:
            log.error("Błąd aktualizacji decyzji sygnału: {}", exc)

    async def _persist_order(self, order: OrderRequest, result: OrderResult, entry_price: float = 0.0) -> None:
        try:
            async with get_session() as session:
                # Użyj entry_price z sygnału jeśli Alpaca nie zwróciła ceny
                display_price = result.avg_price if result.avg_price and result.avg_price > 0 else entry_price
                row = DBOrder(
                    order_id=order.id,
                    ibkr_id=result.ibkr_id,
                    signal_id=order.signal_id,
                    symbol=order.symbol,
                    side=order.side.value,
                    order_type=order.order_type.value,
                    quantity=order.quantity,
                    limit_price=order.limit_price or entry_price,
                    stop_price=order.stop_price,
                    status=result.status.value,
                    filled_qty=result.filled_qty or order.quantity,
                    avg_price=display_price,
                    commission=result.commission,
                    error_msg=result.error_msg,
                    paper_mode=order.paper_mode,
                    created_at=order.created_at,
                    filled_at=result.filled_at,
                )
                session.add(row)
        except Exception as exc:
            log.error("Błąd zapisu zlecenia do DB: {}", exc)
