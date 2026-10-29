"""
Modele SQLAlchemy (ORM) – tabele bazy danych.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


class DBPosition(Base):
    __tablename__ = "positions"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    symbol        = Column(String(20), nullable=False, index=True)
    quantity      = Column(Float, nullable=False, default=0.0)
    avg_cost      = Column(Float, nullable=False, default=0.0)
    current_price = Column(Float, default=0.0)
    unrealized_pnl= Column(Float, default=0.0)
    realized_pnl  = Column(Float, default=0.0)
    agent_name    = Column(String(50), nullable=True)
    opened_at     = Column(DateTime, default=datetime.utcnow)
    updated_at    = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DBOrder(Base):
    __tablename__ = "orders"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    order_id      = Column(String(64), unique=True, nullable=False, index=True)
    ibkr_id       = Column(Integer, nullable=True)
    signal_id     = Column(String(64), nullable=True)
    symbol        = Column(String(20), nullable=False)
    side          = Column(String(10), nullable=False)
    order_type    = Column(String(20), nullable=False)
    quantity      = Column(Float, nullable=False)
    limit_price   = Column(Float, nullable=True)
    stop_price    = Column(Float, nullable=True)
    status        = Column(String(20), nullable=False)
    filled_qty    = Column(Float, default=0.0)
    avg_price     = Column(Float, default=0.0)
    commission    = Column(Float, default=0.0)
    error_msg     = Column(Text, nullable=True)
    paper_mode    = Column(Boolean, default=True)
    created_at    = Column(DateTime, default=datetime.utcnow)
    filled_at     = Column(DateTime, nullable=True)


class DBSignal(Base):
    __tablename__ = "signals"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    signal_id       = Column(String(64), unique=True, nullable=False, index=True)
    agent_name      = Column(String(50), nullable=False)
    symbol          = Column(String(20), nullable=False)
    direction       = Column(String(10), nullable=False)
    confidence      = Column(Float, nullable=False)
    entry_price     = Column(Float, nullable=True)
    stop_loss       = Column(Float, nullable=True)
    take_profit     = Column(Float, nullable=True)
    size_pct        = Column(Float, default=1.0)
    reasoning       = Column(Text, default="")
    raw_indicators  = Column(JSON, default=dict)
    timeframe       = Column(String(10), default="1H")
    approved        = Column(Boolean, nullable=True)    # None = oczekuje
    reject_reason   = Column(Text, nullable=True)
    timestamp       = Column(DateTime, default=datetime.utcnow, index=True)


class DBAgentConfig(Base):
    __tablename__ = "agent_configs"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    agent_name            = Column(String(50), unique=True, nullable=False)
    enabled               = Column(Boolean, default=True)
    max_allocation_pct    = Column(Float, default=10.0)
    max_risk_per_trade_pct= Column(Float, default=1.0)
    max_position_size_usd = Column(Float, default=1000.0)
    params                = Column(JSON, default=dict)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DBRiskLimits(Base):
    __tablename__ = "risk_limits"

    id                    = Column(Integer, primary_key=True, autoincrement=True)
    max_daily_loss_usd    = Column(Float, default=500.0)
    max_drawdown_pct      = Column(Float, default=10.0)
    total_capital_usd     = Column(Float, default=10000.0)
    max_position_size_pct = Column(Float, default=5.0)
    emergency_stop        = Column(Boolean, default=False)
    emergency_stop_ts     = Column(DateTime, nullable=True)
    updated_at            = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class DBAuditLog(Base):
    """Log wszystkich działań użytkownika w panelu."""
    __tablename__ = "audit_log"

    id         = Column(Integer, primary_key=True, autoincrement=True)
    user       = Column(String(100), default="admin")
    action     = Column(String(200), nullable=False)
    details    = Column(JSON, default=dict)
    ip_address = Column(String(50), nullable=True)
    timestamp  = Column(DateTime, default=datetime.utcnow, index=True)


class DBBar(Base):
    """Cache świec historycznych."""
    __tablename__ = "bars"
    __table_args__ = (
        UniqueConstraint("symbol", "timeframe", "timestamp", name="uq_bar"),
    )

    id        = Column(Integer, primary_key=True, autoincrement=True)
    symbol    = Column(String(20), nullable=False, index=True)
    timeframe = Column(String(10), nullable=False)
    timestamp = Column(DateTime, nullable=False, index=True)
    open      = Column(Float, nullable=False)
    high      = Column(Float, nullable=False)
    low       = Column(Float, nullable=False)
    close     = Column(Float, nullable=False)
    volume    = Column(Float, nullable=False)


class DBAlert(Base):
    """Historia alertów."""
    __tablename__ = "alerts"

    id        = Column(Integer, primary_key=True, autoincrement=True)
    level     = Column(String(20), nullable=False)
    title     = Column(String(200), nullable=False)
    message   = Column(Text, nullable=False)
    source    = Column(String(100), default="system")
    sent      = Column(Boolean, default=False)
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)


class DBEquitySnapshot(Base):
    """
    Snapshot equity co 1 minutę - fundament historycznych wykresów PnL.
    Zapisuje: kapitał całkowity, dzienny PnL, PnL per agent.
    """
    __tablename__ = "equity_snapshots"

    id                = Column(Integer, primary_key=True, autoincrement=True)
    timestamp         = Column(DateTime, default=datetime.utcnow, index=True)
    net_liquidation   = Column(Float, default=0.0)   # całkowity kapitał
    daily_pnl         = Column(Float, default=0.0)   # dzienny PnL
    unrealized_pnl    = Column(Float, default=0.0)   # niezrealizowany PnL
    realized_pnl      = Column(Float, default=0.0)   # zrealizowany PnL
    drawdown_pct      = Column(Float, default=0.0)   # drawdown %
    open_positions    = Column(Integer, default=0)   # liczba otwartych pozycji
    agent_pnl         = Column(JSON, default=dict)   # {agent_name: pnl_float}
    paper_mode        = Column(Boolean, default=True)


class DBSystemMetric(Base):
    """
    Metryki systemowe co 1 minutę.
    CPU, RAM, latency API, status połączeń.
    """
    __tablename__ = "system_metrics"

    id              = Column(Integer, primary_key=True, autoincrement=True)
    timestamp       = Column(DateTime, default=datetime.utcnow, index=True)
    cpu_pct         = Column(Float, default=0.0)
    ram_pct         = Column(Float, default=0.0)
    ram_mb          = Column(Float, default=0.0)
    ibkr_connected  = Column(Boolean, default=False)
    ibkr_latency_ms = Column(Float, nullable=True)   # czas odpowiedzi IBKR
    api_latency_ms  = Column(Float, nullable=True)   # czas odpowiedzi backendu
    active_agents   = Column(Integer, default=0)
    signals_today   = Column(Integer, default=0)
    orders_today    = Column(Integer, default=0)
    errors_today    = Column(Integer, default=0)


class DBAgentEvent(Base):
    """
    Rejestr wszystkich zdarzeń agentów - kompletna historia decyzji systemu.
    To jest główny 'rejestrator posunięć' o który prosiłeś.
    """
    __tablename__ = "agent_events"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    timestamp   = Column(DateTime, default=datetime.utcnow, index=True)
    agent_name  = Column(String(50), nullable=False, index=True)
    event_type  = Column(String(50), nullable=False, index=True)
    # Typy: signal_generated, signal_approved, signal_rejected,
    #       order_placed, order_filled, order_cancelled,
    #       position_opened, position_closed,
    #       agent_started, agent_stopped, agent_error,
    #       risk_triggered, emergency_stop
    symbol      = Column(String(20), nullable=True, index=True)
    direction   = Column(String(10), nullable=True)   # BUY/SELL
    price       = Column(Float, nullable=True)
    quantity    = Column(Float, nullable=True)
    pnl         = Column(Float, nullable=True)         # PnL przy zamknięciu
    confidence  = Column(Float, nullable=True)         # confidence sygnału
    reasoning   = Column(Text, nullable=True)          # reasoning agenta
    details     = Column(JSON, default=dict)           # wszystkie dodatkowe dane
    paper_mode  = Column(Boolean, default=True)
