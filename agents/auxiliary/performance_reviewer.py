"""
PerformanceReviewer – post-trade analysis + attribution per agent.

Zadania:
- Analizuje zamknięte transakcje per agent
- Oblicza win rate, profit factor, Sharpe ratio, max drawdown per agent
- Wykrywa systematyczne błędy (zbyt wczesne zamykanie, zbyt duże SL)
- Generuje sugestie optymalizacji parametrów
- Publikuje raporty w shared state (widoczne w dashboardzie)
- Może rekomendować wyłączenie agenta jeśli performance jest zły
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import select, and_

from agents.base_agent import BaseAgent
from core.logger import get_logger
from core.models import AgentName, AgentStatus, SignalDirection, TradeSignal
from core.shared_state import shared_state
from database.database import get_session
from database.models import DBOrder, DBSignal

log = get_logger(__name__)


class PerformanceReviewer(BaseAgent):
    """Przegląd wydajności agentów i sugestie optymalizacji."""

    DEFAULT_PARAMS = {
        "lookback_days":      7,
        "min_trades":         5,      # minimum transakcji do oceny
        "bad_win_rate":       0.35,   # poniżej → alert
        "bad_profit_factor":  0.8,    # poniżej → rekomendacja wyłączenia
        "check_interval_sec": 3600,   # co godzinę
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=3600):
        super().__init__(
            name=AgentName.PERFORMANCE_REV,
            connector=connector,
            market_data=market_data,
            bus=bus,
            symbols=symbols,
            interval_sec=interval_sec,
        )
        self.reports: dict[str, dict] = {}

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        # Uruchamiamy analizę raz na cykl, nie per symbol
        if symbol != self.symbols[0]:
            return None

        params = {**self.DEFAULT_PARAMS, **self._get_config().params}
        await self._run_full_review(params)
        return None  # PerformanceReviewer nie generuje sygnałów tradingowych

    async def _run_full_review(self, params: dict) -> None:
        """Pełna analiza wydajności wszystkich agentów tradingowych."""
        trading_agents = [
            AgentName.TREND_FOLLOWER,
            AgentName.MEAN_REVERSION,
            AgentName.SCALPER,
            AgentName.BREAKOUT_HUNTER,
            AgentName.SENTIMENT_TRADER,
            AgentName.OPTIONS_FLOW,
            AgentName.GAP_TRADER,
            AgentName.MOMENTUM_SURFER,
            AgentName.VIX_TRADER,
            AgentName.DIVERGENCE_HUNTER,
            AgentName.SCALP_KING,
        ]

        cutoff = datetime.utcnow() - timedelta(days=params["lookback_days"])

        for agent in trading_agents:
            report = await self._analyze_agent(agent, cutoff, params)
            if report:
                self.reports[agent.value] = report
                await self._publish_report(agent, report, params)

        # Zapisz do shared state
        if not hasattr(shared_state, "performance_reports"):
            shared_state.performance_reports = {}
        shared_state.performance_reports = dict(self.reports)

        # ── Uruchom learning engine na podstawie raportów ─────────────────────
        try:
            from agents.learning import get_learning_engine
            engine = get_learning_engine()
            agent_stats = {}
            trades_all  = []
            for agent_name, report in self.reports.items():
                if report.get("status") in ("ok", "warning") and report.get("trade_count", 0) > 0:
                    agent_stats[agent_name] = {
                        "win_rate":    report.get("win_rate", 0) * 100,
                        "total_pnl":   report.get("total_pnl", 0),
                        "trades":      report.get("trade_count", 0),
                        "wins":        int(report.get("win_rate", 0) * report.get("trade_count", 0)),
                    }
            if agent_stats:
                session_report = {
                    "session_id": datetime.utcnow().strftime("%Y%m%d_%H%M"),
                    "agent_stats": agent_stats,
                    "trades": trades_all,
                }
                lessons = engine.learn_from_session(session_report)
                # Zastosuj nowe parametry do shared_state
                for lesson in lessons:
                    cfg = shared_state.get_agent_config(
                        next((n for n in AgentName if n.value == lesson.agent_name), None)
                    )
                    if cfg and lesson.new_params:
                        cfg.params.update({
                            "confidence_threshold": lesson.new_params.get("confidence_threshold"),
                            "position_size_mult":   lesson.new_params.get("position_size_mult"),
                        })
                log.info("🎓 Learning engine zastosował {} lekcji", len(lessons))
        except Exception as exc:
            log.error("Błąd learning engine: {}", exc)

        log.info("PerformanceReviewer: zaktualizowano {} raportów", len(self.reports))

    async def _analyze_agent(
        self, agent: AgentName, cutoff: datetime, params: dict
    ) -> Optional[dict]:
        """Analizuje historię zleceń danego agenta."""
        try:
            async with get_session() as session:
                result = await session.execute(
                    select(DBSignal)
                    .where(
                        and_(
                            DBSignal.agent_name == agent.value,
                            DBSignal.timestamp >= cutoff,
                            DBSignal.approved == True,
                        )
                    )
                    .order_by(DBSignal.timestamp.desc())
                )
                signals = result.scalars().all()

                result2 = await session.execute(
                    select(DBOrder)
                    .where(
                        and_(
                            DBOrder.created_at >= cutoff,
                            DBOrder.status == "filled",
                        )
                    )
                )
                orders = result2.scalars().all()

        except Exception as exc:
            log.error("Błąd pobierania danych dla {}: {}", agent.value, exc)
            return None

        if len(signals) < params["min_trades"]:
            return {
                "agent":       agent.value,
                "status":      "insufficient_data",
                "trade_count": len(signals),
                "message":     f"Za mało transakcji ({len(signals)} < {params['min_trades']})",
            }

        # Symuluj PnL na podstawie sygnałów (entry_price, sl, tp)
        pnl_list  = []
        win_count = 0
        for sig in signals:
            if sig.entry_price and sig.stop_loss and sig.take_profit:
                # Zakładamy 50/50 czy TP czy SL zostało trafione (bez danych o zamknięciu)
                # W produkcji należy matchować z rzeczywistymi zleceniami
                tp_dist = abs(sig.take_profit - sig.entry_price)
                sl_dist = abs(sig.stop_loss   - sig.entry_price)
                rr = tp_dist / (sl_dist + 1e-9)
                # Użyj historycznych wyników z Orders jeśli dostępne
                matched_order = next(
                    (o for o in orders if o.signal_id == sig.signal_id), None
                )
                if matched_order and matched_order.avg_price > 0:
                    if sig.direction == "LONG":
                        pnl = (matched_order.avg_price - sig.entry_price) * matched_order.filled_qty
                    else:
                        pnl = (sig.entry_price - matched_order.avg_price) * matched_order.filled_qty
                    pnl_list.append(pnl)
                    if pnl > 0:
                        win_count += 1

        if not pnl_list:
            return {
                "agent":       agent.value,
                "status":      "no_completed_trades",
                "trade_count": len(signals),
                "signal_count": len(signals),
            }

        wins   = [p for p in pnl_list if p > 0]
        losses = [p for p in pnl_list if p <= 0]

        win_rate      = len(wins) / len(pnl_list)
        avg_win       = np.mean(wins)  if wins   else 0.0
        avg_loss      = abs(np.mean(losses)) if losses else 1.0
        profit_factor = (sum(wins) / (abs(sum(losses)) + 1e-9))
        total_pnl     = sum(pnl_list)
        sharpe        = self._sharpe(pnl_list)

        # Identyfikacja problemów
        issues: list[str] = []
        suggestions: list[str] = []

        if win_rate < params["bad_win_rate"]:
            issues.append(f"Niski win rate: {win_rate:.1%}")
            suggestions.append("Zwiększ minimalny próg confidence lub zawęź warunki wejścia")

        if profit_factor < params["bad_profit_factor"]:
            issues.append(f"Słaby profit factor: {profit_factor:.2f}")
            suggestions.append("Sprawdź stosunek SL/TP – możliwe zbyt ciasne TP lub zbyt szerokie SL")

        if avg_win < avg_loss * 0.8:
            issues.append(f"Avg win ({avg_win:.2f}) < avg loss ({avg_loss:.2f})")
            suggestions.append("Rozważ przesunięcie TP lub trailing stop")

        return {
            "agent":          agent.value,
            "status":         "ok" if not issues else "warning",
            "trade_count":    len(pnl_list),
            "win_rate":       round(win_rate, 3),
            "profit_factor":  round(profit_factor, 3),
            "total_pnl":      round(total_pnl, 2),
            "avg_win":        round(avg_win, 2),
            "avg_loss":       round(avg_loss, 2),
            "sharpe":         round(sharpe, 3),
            "issues":         issues,
            "suggestions":    suggestions,
            "updated_at":     datetime.utcnow().isoformat(),
        }

    async def _publish_report(
        self, agent: AgentName, report: dict, params: dict
    ) -> None:
        if report.get("status") == "ok":
            return

        issues      = report.get("issues", [])
        suggestions = report.get("suggestions", [])
        win_rate    = report.get("win_rate", 0)
        pf          = report.get("profit_factor", 1.0)

        # ── Wyślij alert na bus ───────────────────────────────────────────────
        if pf < params["bad_profit_factor"]:
            await self._bus.publish("alerts", {
                "level":   "WARNING",
                "title":   f"Słaba wydajność: {agent.value}",
                "message": f"Profit factor={pf} | Win rate={win_rate} | "
                           f"Sugestie: {'; '.join(suggestions)}",
                "source":  "PerformanceReviewer",
                "timestamp": datetime.utcnow().isoformat(),
            })

        # ── Przekaż sugestie do Szefa ─────────────────────────────────────────
        if issues or suggestions:
            try:
                from agents.auxiliary.coach import get_coach
                coach = get_coach()
                # Kara za każdy problem wykryty przez PerformanceReviewera
                penalty_per_issue = -3
                for issue in issues:
                    pnl_pct = -1.0  # symboliczna kara
                    if "win rate" in issue.lower():
                        pnl_pct = -2.0
                    elif "profit factor" in issue.lower():
                        pnl_pct = -1.5
                    elif "avg win" in issue.lower():
                        pnl_pct = -1.0

                    coach.review_trade(
                        agent_name = agent.value,
                        symbol     = "REVIEW",
                        direction  = "LONG",
                        pnl_usd    = penalty_per_issue * abs(pnl_pct),
                        pnl_pct    = pnl_pct,
                        trade_id   = f"review_{agent.value}_{datetime.utcnow().strftime('%H%M%S')}",
                    )
                    log.info("🎓 Coach otrzymał sugestię dla {}: {} → kara {}pkt",
                             agent.value, issue, penalty_per_issue)
            except Exception as exc:
                log.debug("Błąd przekazania sugestii do Szefa: {}", exc)

    @staticmethod
    def _sharpe(pnl_list: list[float], rf: float = 0.0) -> float:
        if len(pnl_list) < 2:
            return 0.0
        arr  = np.array(pnl_list)
        mean = arr.mean() - rf
        std  = arr.std()
        return float(mean / (std + 1e-9)) * np.sqrt(252)
