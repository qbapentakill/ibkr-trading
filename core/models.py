"""
Modele Pydantic używane w całym systemie.
Stanowią jedyne źródło prawdy o strukturach danych przesyłanych między komponentami.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field


# ══════════════════════════════════════════════════════════════════════════════
# Enumeracje
# ══════════════════════════════════════════════════════════════════════════════

class AgentName(str, Enum):
    TREND_FOLLOWER   = "TrendFollower"
    MEAN_REVERSION   = "MeanReversion"
    SCALPER          = "Scalper"
    BREAKOUT_HUNTER  = "BreakoutHunter"
    SENTIMENT_TRADER = "SentimentTrader"
    # Nowe trading boty
    OPTIONS_FLOW     = "OptionsFlow"
    GAP_TRADER       = "GapTrader"
    MOMENTUM_SURFER  = "MomentumSurfer"
    VIX_TRADER       = "VIXTrader"
    DIVERGENCE_HUNTER= "DivergenceHunter"
    SCALP_KING       = "ScalpKing"
    # Pomocnicze oryginalne
    MARKET_ANALYST   = "MarketAnalyst"
    NEWS_ANALYST     = "NewsAnalyst"
    RESEARCH_AGENT   = "ResearchAgent"
    SMART_MONEY      = "SmartMoneyTracker"
    RISK_MANAGER     = "RiskManager"
    PERFORMANCE_REV  = "PerformanceReviewer"
    PORTFOLIO_ALLOC  = "PortfolioAllocator"
    ORCHESTRATOR     = "Orchestrator"
    # Nowe pomocnicze
    EARNINGS_WATCHER = "EarningsWatcher"
    MACRO_ANALYST    = "MacroAnalyst"
    CORRELATION_GUARD= "CorrelationGuard"
    HEATMAP_ANALYST  = "HeatmapAnalyst"
    WHALE_TRACKER    = "WhaleTracker"
    ECONOMIC_CALENDAR= "EconomicCalendar"


class AgentStatus(str, Enum):
    ACTIVE   = "active"
    DISABLED = "disabled"
    ERROR    = "error"
    STARTING = "starting"
    STOPPING = "stopping"


class OrderSide(str, Enum):
    BUY  = "BUY"
    SELL = "SELL"


class OrderType(str, Enum):
    MARKET = "MKT"
    LIMIT  = "LMT"
    STOP   = "STP"
    STOP_LIMIT = "STP LMT"


class OrderStatus(str, Enum):
    PENDING    = "pending"
    SUBMITTED  = "submitted"
    FILLED     = "filled"
    CANCELLED  = "cancelled"
    REJECTED   = "rejected"
    PARTIAL    = "partial"


class SignalDirection(str, Enum):
    LONG    = "LONG"
    SHORT   = "SHORT"
    CLOSE   = "CLOSE"
    NEUTRAL = "NEUTRAL"


class AlertLevel(str, Enum):
    INFO     = "INFO"
    WARNING  = "WARNING"
    CRITICAL = "CRITICAL"
    EMERGENCY = "EMERGENCY"


# ══════════════════════════════════════════════════════════════════════════════
# Market Data
# ══════════════════════════════════════════════════════════════════════════════

class Bar(BaseModel):
    """Pojedyncza świeca OHLCV."""
    timestamp: datetime
    open:      float
    high:      float
    low:       float
    close:     float
    volume:    float
    symbol:    str


class Quote(BaseModel):
    """Aktualna oferta bid/ask."""
    symbol:    str
    bid:       float
    ask:       float
    last:      float
    volume:    float
    timestamp: datetime = Field(default_factory=datetime.utcnow)

    @property
    def mid(self) -> float:
        return (self.bid + self.ask) / 2.0

    @property
    def spread(self) -> float:
        return self.ask - self.bid


# ══════════════════════════════════════════════════════════════════════════════
# Sygnały i zlecenia
# ══════════════════════════════════════════════════════════════════════════════

class TradeSignal(BaseModel):
    """Sygnał wygenerowany przez agenta tradingowego."""
    id:             str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    agent_name:     AgentName
    symbol:         str
    direction:      SignalDirection
    confidence:     float = Field(ge=0.0, le=1.0, description="Pewność sygnału 0–1")
    entry_price:    Optional[float] = None
    stop_loss:      Optional[float] = None
    take_profit:    Optional[float] = None
    size_pct:       float = Field(default=1.0, ge=0.0, le=100.0, description="% alokacji agenta")
    reasoning:      str   = ""
    raw_indicators: dict[str, Any] = Field(default_factory=dict)
    timestamp:      datetime = Field(default_factory=datetime.utcnow)
    timeframe:      str = "1H"


class OrderRequest(BaseModel):
    """Zlecenie przekazywane do connectora IBKR."""
    id:          str = Field(default_factory=lambda: __import__('uuid').uuid4().hex)
    signal_id:   str
    symbol:      str
    side:        OrderSide
    order_type:  OrderType = OrderType.MARKET
    quantity:    float
    limit_price: Optional[float] = None
    stop_price:  Optional[float] = None
    tif:         str = "DAY"   # Time In Force
    paper_mode:  bool = True
    created_at:  datetime = Field(default_factory=datetime.utcnow)


class OrderResult(BaseModel):
    """Wynik złożonego zlecenia."""
    order_id:    str
    ibkr_id:     Optional[int] = None
    status:      OrderStatus
    filled_qty:  float = 0.0
    avg_price:   float = 0.0
    commission:  float = 0.0
    error_msg:   Optional[str] = None
    filled_at:   Optional[datetime] = None


# ══════════════════════════════════════════════════════════════════════════════
# Pozycje i PnL
# ══════════════════════════════════════════════════════════════════════════════

class Position(BaseModel):
    """Otwarta pozycja."""
    symbol:       str
    quantity:     float          # + = long, - = short
    avg_cost:     float
    current_price: float = 0.0
    unrealized_pnl: float = 0.0
    realized_pnl:   float = 0.0
    agent_name:   Optional[AgentName] = None
    opened_at:    datetime = Field(default_factory=datetime.utcnow)

    @property
    def market_value(self) -> float:
        return self.quantity * self.current_price

    @property
    def pnl_pct(self) -> float:
        if self.avg_cost == 0:
            return 0.0
        return (self.current_price - self.avg_cost) / self.avg_cost * 100.0


class AccountSummary(BaseModel):
    """Podsumowanie rachunku IBKR."""
    net_liquidation:   float = 0.0
    total_cash:        float = 0.0
    buying_power:      float = 0.0
    unrealized_pnl:    float = 0.0
    realized_pnl:      float = 0.0
    daily_pnl:         float = 0.0
    currency:          str = "USD"
    timestamp:         datetime = Field(default_factory=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# Agent state
# ══════════════════════════════════════════════════════════════════════════════

class AgentConfig(BaseModel):
    """Konfiguracja konkretnego agenta (persystowana w DB)."""
    agent_name:          AgentName
    enabled:             bool  = True
    max_allocation_pct:  float = Field(default=10.0, ge=0.0, le=100.0)
    max_risk_per_trade_pct: float = Field(default=1.0, ge=0.0, le=10.0)
    max_position_size_usd: float = 1000.0
    params:              dict[str, Any] = Field(default_factory=dict)


class AgentState(BaseModel):
    """Bieżący stan agenta widoczny w panelu."""
    agent_name:   AgentName
    status:       AgentStatus = AgentStatus.DISABLED
    last_signal:  Optional[TradeSignal] = None
    last_error:   Optional[str] = None
    signals_today: int = 0
    updated_at:   datetime = Field(default_factory=datetime.utcnow)


# ══════════════════════════════════════════════════════════════════════════════
# Risk
# ══════════════════════════════════════════════════════════════════════════════

class RiskDecision(BaseModel):
    """Decyzja RiskManagera dla danego sygnału."""
    signal_id:    str
    approved:     bool
    reason:       str
    adjusted_size_pct: Optional[float] = None   # jeśli rozmiar zmniejszony
    timestamp:    datetime = Field(default_factory=datetime.utcnow)


class RiskLimits(BaseModel):
    """Globalne limity ryzyka."""
    max_daily_loss_usd:    float = 500.0
    max_drawdown_pct:      float = 10.0
    total_capital_usd:     float = 10000.0
    max_position_size_pct: float = 5.0
    emergency_stop:        bool  = False
    emergency_stop_ts:     Optional[datetime] = None


# ══════════════════════════════════════════════════════════════════════════════
# Alerty
# ══════════════════════════════════════════════════════════════════════════════

class Alert(BaseModel):
    """Alert do wysłania przez Telegram / e-mail."""
    level:    AlertLevel
    title:    str
    message:  str
    source:   str = "system"
    timestamp: datetime = Field(default_factory=datetime.utcnow)
