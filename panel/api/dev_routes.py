"""
Dev API Routes - endpointy dla panelu developerskiego.

Wszystkie pod prefixem /dev (czyli /api/dev/...)
Bez auth w fazie developerskiej - dodaj auth middleware przed launchem.
"""
from __future__ import annotations

import time
from datetime import datetime, timedelta, timezone
from typing import Optional

import psutil
from fastapi import APIRouter, Query
from sqlalchemy import select, func, and_, desc

from core.shared_state import shared_state
from database.database import get_session
from database.models import (
    DBAuditLog, DBAgentEvent, DBEquitySnapshot,
    DBSystemMetric, DBOrder, DBSignal, DBAlert,
)

router = APIRouter(prefix="/dev", tags=["developer"])

_start_time = time.time()


# ─────────────────────────────────────────────────────────────────────────────
# Health
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/health")
async def dev_health():
    """Aktualne metryki systemowe."""
    snap = shared_state.snapshot()
    cpu  = psutil.cpu_percent(interval=None)
    ram  = psutil.virtual_memory()

    active_agents = sum(
        1 for a in snap.get("agents", {}).values()
        if a.get("enabled") and a.get("running")
    )

    # Błędy z ostatnich 24h
    async with get_session() as session:
        since = datetime.now(timezone.utc) - timedelta(hours=24)
        errors_q = await session.execute(
            select(func.count()).select_from(DBAgentEvent)
            .where(and_(
                DBAgentEvent.event_type == "agent_error",
                DBAgentEvent.timestamp >= since,
            ))
        )
        errors_today = errors_q.scalar() or 0

        signals_q = await session.execute(
            select(func.count()).select_from(DBAgentEvent)
            .where(and_(
                DBAgentEvent.event_type == "signal_generated",
                DBAgentEvent.timestamp >= since,
            ))
        )
        signals_today = signals_q.scalar() or 0

    return {
        "cpu_pct":        cpu,
        "ram_pct":        ram.percent,
        "ram_mb":         ram.used / 1024 / 1024,
        "ibkr_connected": snap.get("ibkr_connected", False),
        "paper_mode":     snap.get("paper_mode", True),
        "active_agents":  active_agents,
        "signals_today":  signals_today,
        "errors_today":   errors_today,
        "uptime_sec":     int(time.time() - _start_time),
    }


# ─────────────────────────────────────────────────────────────────────────────
# Audit Log
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/audit-log")
async def get_audit_log(
    limit:  int = Query(100, le=1000),
    action: Optional[str] = None,
    user:   Optional[str] = None,
):
    async with get_session() as session:
        q = select(DBAuditLog).order_by(desc(DBAuditLog.timestamp)).limit(limit)
        if action:
            q = q.where(DBAuditLog.action == action)
        if user:
            q = q.where(DBAuditLog.user == user)
        result = await session.execute(q)
        rows = result.scalars().all()

    return [
        {
            "id":         r.id,
            "timestamp":  r.timestamp.isoformat(),
            "user":       r.user,
            "action":     r.action,
            "details":    r.details or {},
            "ip_address": r.ip_address,
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Agent Events (Activity Feed)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/agent-events")
async def get_agent_events(
    limit:      int = Query(200, le=1000),
    agent:      Optional[str] = None,
    event_type: Optional[str] = None,
    symbol:     Optional[str] = None,
    hours:      int = Query(24, le=720),
):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    async with get_session() as session:
        q = (
            select(DBAgentEvent)
            .where(DBAgentEvent.timestamp >= since)
            .order_by(desc(DBAgentEvent.timestamp))
            .limit(limit)
        )
        if agent:
            q = q.where(DBAgentEvent.agent_name == agent)
        if event_type:
            q = q.where(DBAgentEvent.event_type == event_type)
        if symbol:
            q = q.where(DBAgentEvent.symbol == symbol)

        result = await session.execute(q)
        rows = result.scalars().all()

    return [
        {
            "id":         r.id,
            "timestamp":  r.timestamp.isoformat(),
            "agent_name": r.agent_name,
            "event_type": r.event_type,
            "symbol":     r.symbol,
            "direction":  r.direction,
            "price":      r.price,
            "quantity":   r.quantity,
            "pnl":        r.pnl,
            "confidence": r.confidence,
            "reasoning":  r.reasoning,
            "details":    r.details or {},
            "paper_mode": r.paper_mode,
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Statystyki 24h
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stats/24h")
async def get_stats_24h():
    since = datetime.now(timezone.utc) - timedelta(hours=24)

    async with get_session() as session:
        # Łączne liczby
        def count_q(model, *filters):
            return select(func.count()).select_from(model).where(
                model.timestamp >= since, *filters
            )

        results = {}
        for key, q in [
            ("signals_24h",  count_q(DBAgentEvent, DBAgentEvent.event_type == "signal_generated")),
            ("orders_24h",   count_q(DBAgentEvent, DBAgentEvent.event_type == "order_placed")),
            ("approved_24h", count_q(DBAgentEvent, DBAgentEvent.event_type == "signal_approved")),
            ("rejected_24h", count_q(DBAgentEvent, DBAgentEvent.event_type == "signal_rejected")),
            ("errors_24h",   count_q(DBAgentEvent, DBAgentEvent.event_type == "agent_error")),
        ]:
            r = await session.execute(q)
            results[key] = r.scalar() or 0

        # Per agent
        per_agent_q = await session.execute(
            select(
                DBAgentEvent.agent_name,
                DBAgentEvent.event_type,
                func.count().label("cnt"),
            )
            .where(DBAgentEvent.timestamp >= since)
            .group_by(DBAgentEvent.agent_name, DBAgentEvent.event_type)
        )
        rows = per_agent_q.all()

    per_agent: dict = {}
    for agent_name, event_type, cnt in rows:
        if agent_name not in per_agent:
            per_agent[agent_name] = {"signals": 0, "errors": 0, "orders": 0}
        if event_type == "signal_generated":
            per_agent[agent_name]["signals"] += cnt
        elif event_type == "agent_error":
            per_agent[agent_name]["errors"] += cnt
        elif event_type == "order_placed":
            per_agent[agent_name]["orders"] += cnt

    return {**results, "per_agent": per_agent}


# ─────────────────────────────────────────────────────────────────────────────
# Equity History (PnL Timeline)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/equity-history")
async def get_equity_history(hours: int = Query(24, le=8760)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    async with get_session() as session:
        q = (
            select(DBEquitySnapshot)
            .where(DBEquitySnapshot.timestamp >= since)
            .order_by(DBEquitySnapshot.timestamp)
        )
        result = await session.execute(q)
        rows = result.scalars().all()

    return [
        {
            "timestamp":       r.timestamp.isoformat(),
            "net_liquidation": r.net_liquidation,
            "daily_pnl":       r.daily_pnl,
            "unrealized_pnl":  r.unrealized_pnl,
            "realized_pnl":    r.realized_pnl,
            "drawdown_pct":    r.drawdown_pct,
            "open_positions":  r.open_positions,
            "agent_pnl":       r.agent_pnl or {},
            "paper_mode":      r.paper_mode,
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# System Metrics History
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/system-metrics")
async def get_system_metrics(hours: int = Query(1, le=168)):
    since = datetime.now(timezone.utc) - timedelta(hours=hours)

    async with get_session() as session:
        q = (
            select(DBSystemMetric)
            .where(DBSystemMetric.timestamp >= since)
            .order_by(DBSystemMetric.timestamp)
        )
        result = await session.execute(q)
        rows = result.scalars().all()

    return [
        {
            "timestamp":      r.timestamp.isoformat(),
            "cpu_pct":        r.cpu_pct,
            "ram_pct":        r.ram_pct,
            "ram_mb":         r.ram_mb,
            "ibkr_connected": r.ibkr_connected,
            "active_agents":  r.active_agents,
            "signals_today":  r.signals_today,
            "errors_today":   r.errors_today,
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Signals PRO
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/signals-pro")
async def get_signals_pro(
    limit:    int = Query(50, le=500),
    agent:    Optional[str] = None,
    symbol:   Optional[str] = None,
    approved: Optional[bool] = None,
):
    async with get_session() as session:
        q = select(DBSignal).order_by(desc(DBSignal.timestamp)).limit(limit)
        if agent:
            q = q.where(DBSignal.agent_name == agent)
        if symbol:
            q = q.where(DBSignal.symbol == symbol)
        if approved is not None:
            q = q.where(DBSignal.approved == approved)

        result = await session.execute(q)
        rows = result.scalars().all()

    return [
        {
            "signal_id":      r.signal_id,
            "timestamp":      r.timestamp.isoformat(),
            "agent_name":     r.agent_name,
            "symbol":         r.symbol,
            "direction":      r.direction,
            "confidence":     r.confidence,
            "entry_price":    r.entry_price,
            "stop_loss":      r.stop_loss,
            "take_profit":    r.take_profit,
            "size_pct":       r.size_pct,
            "reasoning":      r.reasoning,
            "raw_indicators": r.raw_indicators or {},
            "timeframe":      r.timeframe,
            "approved":       r.approved,
            "reject_reason":  r.reject_reason,
        }
        for r in rows
    ]


# ─────────────────────────────────────────────────────────────────────────────
# Export endpoints
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/export-stats")
async def get_export_stats():
    """Statystyki dla strony export - ile rekordów w każdej tabeli."""
    import os
    from pathlib import Path

    async with get_session() as session:
        counts = {}
        for key, model in [
            ("total_orders",       DBOrder),
            ("total_signals",      DBSignal),
            ("total_audit",        DBAuditLog),
            ("total_equity_snaps", DBEquitySnapshot),
            ("total_agent_events", DBAgentEvent),
        ]:
            q = await session.execute(select(func.count()).select_from(model))
            counts[key] = q.scalar() or 0

    db_path = Path("data/trading.db")
    counts["db_size_mb"] = f"{db_path.stat().st_size / 1024 / 1024:.2f} MB" if db_path.exists() else "—"
    return counts


@router.get("/export/{resource}")
async def export_resource(
    resource: str,
    from_date: str = Query("2020-01-01", alias="from"),
    to_date:   str = Query("2099-12-31", alias="to"),
):
    """Export danych do CSV/JSON."""
    try:
        dt_from = datetime.fromisoformat(from_date).replace(tzinfo=timezone.utc)
        dt_to   = datetime.fromisoformat(to_date).replace(tzinfo=timezone.utc) + timedelta(days=1)
    except ValueError:
        return {"error": "Invalid date format"}

    async with get_session() as session:
        if resource == "orders":
            q = (select(DBOrder)
                 .where(DBOrder.created_at.between(dt_from, dt_to))
                 .order_by(desc(DBOrder.created_at)))
            result = await session.execute(q)
            rows = result.scalars().all()
            return [
                {
                    "timestamp":  r.created_at.isoformat(),
                    "symbol":     r.symbol,
                    "side":       r.side,
                    "order_type": r.order_type,
                    "quantity":   r.quantity,
                    "avg_price":  r.avg_price,
                    "status":     r.status,
                    "commission": r.commission,
                    "paper_mode": r.paper_mode,
                    "filled_at":  r.filled_at.isoformat() if r.filled_at else None,
                }
                for r in rows
            ]

        elif resource == "signals":
            q = (select(DBSignal)
                 .where(DBSignal.timestamp.between(dt_from, dt_to))
                 .order_by(desc(DBSignal.timestamp)))
            result = await session.execute(q)
            rows = result.scalars().all()
            return [
                {
                    "timestamp":     r.timestamp.isoformat(),
                    "agent_name":    r.agent_name,
                    "symbol":        r.symbol,
                    "direction":     r.direction,
                    "confidence":    r.confidence,
                    "entry_price":   r.entry_price,
                    "stop_loss":     r.stop_loss,
                    "take_profit":   r.take_profit,
                    "reasoning":     r.reasoning,
                    "approved":      r.approved,
                    "reject_reason": r.reject_reason,
                }
                for r in rows
            ]

        elif resource == "audit-log":
            q = (select(DBAuditLog)
                 .where(DBAuditLog.timestamp.between(dt_from, dt_to))
                 .order_by(desc(DBAuditLog.timestamp)))
            result = await session.execute(q)
            rows = result.scalars().all()
            return [
                {
                    "timestamp": r.timestamp.isoformat(),
                    "user":      r.user,
                    "action":    r.action,
                    "details":   r.details,
                    "ip":        r.ip_address,
                }
                for r in rows
            ]

        elif resource == "equity":
            q = (select(DBEquitySnapshot)
                 .where(DBEquitySnapshot.timestamp.between(dt_from, dt_to))
                 .order_by(DBEquitySnapshot.timestamp))
            result = await session.execute(q)
            rows = result.scalars().all()
            return [
                {
                    "timestamp":       r.timestamp.isoformat(),
                    "net_liquidation": r.net_liquidation,
                    "daily_pnl":       r.daily_pnl,
                    "drawdown_pct":    r.drawdown_pct,
                    "open_positions":  r.open_positions,
                    "agent_pnl":       r.agent_pnl,
                }
                for r in rows
            ]

        elif resource == "agent-events":
            q = (select(DBAgentEvent)
                 .where(DBAgentEvent.timestamp.between(dt_from, dt_to))
                 .order_by(desc(DBAgentEvent.timestamp)))
            result = await session.execute(q)
            rows = result.scalars().all()
            return [
                {
                    "timestamp":  r.timestamp.isoformat(),
                    "agent_name": r.agent_name,
                    "event_type": r.event_type,
                    "symbol":     r.symbol,
                    "direction":  r.direction,
                    "price":      r.price,
                    "pnl":        r.pnl,
                    "confidence": r.confidence,
                    "reasoning":  r.reasoning,
                }
                for r in rows
            ]

        elif resource == "system-metrics":
            q = (select(DBSystemMetric)
                 .where(DBSystemMetric.timestamp.between(dt_from, dt_to))
                 .order_by(DBSystemMetric.timestamp))
            result = await session.execute(q)
            rows = result.scalars().all()
            return [
                {
                    "timestamp":     r.timestamp.isoformat(),
                    "cpu_pct":       r.cpu_pct,
                    "ram_pct":       r.ram_pct,
                    "ibkr_connected": r.ibkr_connected,
                    "active_agents": r.active_agents,
                    "signals_today": r.signals_today,
                    "errors_today":  r.errors_today,
                }
                for r in rows
            ]

    return {"error": f"Unknown resource: {resource}"}
