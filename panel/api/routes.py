"""
FastAPI – wszystkie endpointy REST + WebSocket dla panelu sterowania.

Endpointy:
  POST /api/auth/token            – logowanie
  GET  /api/status                – pełny snapshot systemu
  GET  /api/agents                – lista agentów + stany
  POST /api/agents/{name}/enable  – włącz agenta
  POST /api/agents/{name}/disable – wyłącz agenta
  PUT  /api/agents/{name}/config  – zmień konfigurację agenta
  GET  /api/positions             – otwarte pozycje
  GET  /api/orders                – historia zleceń
  GET  /api/signals               – ostatnie sygnały
  GET  /api/risk                  – limity ryzyka
  PUT  /api/risk                  – zmień limity ryzyka
  POST /api/emergency/stop        – EMERGENCY STOP (wymaga hasła)
  POST /api/emergency/clear       – odblokuj Emergency Stop
  GET  /api/performance           – raporty wydajności agentów
  GET  /api/news                  – ostatnie newsy
  GET  /api/logs                  – ostatnie logi
  WS   /api/ws                    – WebSocket live feed
  POST /api/chat                  – AI Chat query
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timedelta
from typing import Any

from fastapi import (
    APIRouter, Depends, HTTPException, WebSocket,
    WebSocketDisconnect, status,
)
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import BaseModel

from config.settings import get_settings
from core.models import AgentConfig, AgentName, AgentStatus, RiskLimits
from core.shared_state import shared_state
from database.database import get_session
from database.models import DBAuditLog, DBOrder, DBSignal
from panel.api.auth import Token, authenticate_user, create_access_token, get_current_user
from sqlalchemy import select, desc

settings = get_settings()
router   = APIRouter()

# ── Globalny rejestr WebSocket połączeń ──────────────────────────────────────
_ws_clients: list[WebSocket] = []


async def broadcast_ws(data: dict) -> None:
    """Rozgłasza wiadomość do wszystkich podłączonych klientów WS."""
    dead = []
    for ws in _ws_clients:
        try:
            await ws.send_json(data)
        except Exception:
            dead.append(ws)
    for ws in dead:
        _ws_clients.remove(ws)


# ══════════════════════════════════════════════════════════════════════════════
# Auth
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/auth/token", response_model=Token, tags=["auth"])
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    from panel.api.auth import authenticate_user, get_user_role
    if not authenticate_user(form_data.username, form_data.password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Nieprawidłowy login lub hasło",
        )
    role  = get_user_role(form_data.username)
    token = create_access_token({"sub": form_data.username, "role": role})
    await _audit("login", form_data.username, {"action": "login", "role": role})
    return Token(access_token=token)


# ══════════════════════════════════════════════════════════════════════════════
# System status
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/status", tags=["system"])
async def get_status(user: str = Depends(get_current_user)):
    return shared_state.snapshot()


@router.get("/connection", tags=["system"])
async def get_connection(user: str = Depends(get_current_user)):
    from core.ibkr_connector import IBKRConnector
    # Connector dostępny przez dependency injection w produkcji
    # Tu zwracamy stan z shared_state
    return {
        "ibkr_connected": getattr(shared_state, "ibkr_connected", False),
        "paper_mode":     not settings.real_mode,
        "real_mode":      settings.real_mode,
        "timestamp":      datetime.utcnow().isoformat(),
    }


# ══════════════════════════════════════════════════════════════════════════════
# Agenci
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/agents", tags=["agents"])
async def list_agents(user: str = Depends(get_current_user)):
    return {
        name.value: {
            "config": shared_state.agent_configs[name].model_dump(),
            "state":  shared_state.agent_states[name].model_dump(),
        }
        for name in AgentName
    }


@router.post("/agents/{agent_name}/enable", tags=["agents"])
async def enable_agent(agent_name: str, user: str = Depends(get_current_user)):
    name = _resolve_agent(agent_name)
    cfg  = shared_state.agent_configs[name]
    cfg.enabled = True
    await shared_state.set_agent_config(cfg)
    await shared_state.set_agent_status(name, AgentStatus.ACTIVE)
    await _audit(user, "enable_agent", {"agent": agent_name})
    return {"ok": True, "agent": agent_name, "enabled": True}


@router.post("/agents/{agent_name}/disable", tags=["agents"])
async def disable_agent(agent_name: str, user: str = Depends(get_current_user)):
    name = _resolve_agent(agent_name)
    cfg  = shared_state.agent_configs[name]
    cfg.enabled = False
    await shared_state.set_agent_config(cfg)
    await shared_state.set_agent_status(name, AgentStatus.DISABLED)
    await _audit(user, "disable_agent", {"agent": agent_name})
    return {"ok": True, "agent": agent_name, "enabled": False}


@router.post("/agents/stop-all", tags=["agents"])
async def stop_all_agents(user: str = Depends(get_current_user)):
    """Zatrzymuje wszystkich agentów jednym kliknięciem."""
    for name in AgentName:
        cfg = shared_state.agent_configs[name]
        cfg.enabled = False
        await shared_state.set_agent_config(cfg)
        await shared_state.set_agent_status(name, AgentStatus.DISABLED)
    shared_state.agents_running = False
    await _audit(user, "stop_all_agents", {})
    return {"ok": True, "agents_running": False}


@router.post("/agents/start-all", tags=["agents"])
async def start_all_agents(user: str = Depends(get_current_user)):
    """Uruchamia wszystkich agentów jednym kliknięciem."""
    for name in AgentName:
        cfg = shared_state.agent_configs[name]
        cfg.enabled = True
        await shared_state.set_agent_config(cfg)
        await shared_state.set_agent_status(name, AgentStatus.ACTIVE)
    shared_state.agents_running = True
    await _audit(user, "start_all_agents", {})
    return {"ok": True, "agents_running": True}


class AgentConfigUpdate(BaseModel):
    max_allocation_pct:     float | None = None
    max_risk_per_trade_pct: float | None = None
    max_position_size_usd:  float | None = None
    params:                 dict | None  = None


@router.put("/agents/{agent_name}/config", tags=["agents"])
async def update_agent_config(
    agent_name: str,
    update: AgentConfigUpdate,
    user: str = Depends(get_current_user),
):
    name = _resolve_agent(agent_name)
    cfg  = shared_state.agent_configs[name]
    if update.max_allocation_pct     is not None: cfg.max_allocation_pct     = update.max_allocation_pct
    if update.max_risk_per_trade_pct is not None: cfg.max_risk_per_trade_pct = update.max_risk_per_trade_pct
    if update.max_position_size_usd  is not None: cfg.max_position_size_usd  = update.max_position_size_usd
    if update.params                 is not None: cfg.params.update(update.params)
    await shared_state.set_agent_config(cfg)
    await _audit(user, "update_agent_config", {"agent": agent_name, "update": update.model_dump()})
    return {"ok": True, "config": cfg.model_dump()}


# ══════════════════════════════════════════════════════════════════════════════
# Pozycje i zlecenia
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/positions", tags=["trading"])
async def get_positions(user: str = Depends(get_current_user)):
    return {s: p.model_dump() for s, p in shared_state.positions.items()}


@router.get("/orders", tags=["trading"])
async def get_orders(limit: int = 50, user: str = Depends(get_current_user)):
    async with get_session() as session:
        result = await session.execute(
            select(DBOrder).order_by(desc(DBOrder.created_at)).limit(limit)
        )
        orders = result.scalars().all()
    return [
        {
            "order_id":   o.order_id,
            "symbol":     o.symbol,
            "side":       o.side,
            "quantity":   o.quantity,
            "status":     o.status,
            "avg_price":  o.avg_price,
            "commission": o.commission,
            "paper_mode": o.paper_mode,
            "created_at": o.created_at.isoformat() if o.created_at else None,
        }
        for o in orders
    ]


@router.get("/signals", tags=["trading"])
async def get_signals(limit: int = 30, user: str = Depends(get_current_user)):
    async with get_session() as session:
        result = await session.execute(
            select(DBSignal).order_by(desc(DBSignal.timestamp)).limit(limit)
        )
        signals = result.scalars().all()
    return [
        {
            "signal_id":  s.signal_id,
            "agent_name": s.agent_name,
            "symbol":     s.symbol,
            "direction":  s.direction,
            "confidence": s.confidence,
            "reasoning":  s.reasoning,
            "approved":   s.approved,
            "timestamp":  s.timestamp.isoformat() if s.timestamp else None,
        }
        for s in signals
    ]


# ══════════════════════════════════════════════════════════════════════════════
# Risk management
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/risk", tags=["risk"])
async def get_risk(user: str = Depends(get_current_user)):
    return shared_state.risk_limits.model_dump()


class RiskUpdate(BaseModel):
    max_daily_loss_usd:    float | None = None
    max_drawdown_pct:      float | None = None
    total_capital_usd:     float | None = None
    max_position_size_pct: float | None = None


@router.put("/risk", tags=["risk"])
async def update_risk(update: RiskUpdate, user: str = Depends(get_current_user)):
    lim = shared_state.risk_limits
    if update.max_daily_loss_usd    is not None: lim.max_daily_loss_usd    = update.max_daily_loss_usd
    if update.max_drawdown_pct      is not None: lim.max_drawdown_pct      = update.max_drawdown_pct
    if update.total_capital_usd     is not None: lim.total_capital_usd     = update.total_capital_usd
    if update.max_position_size_pct is not None: lim.max_position_size_pct = update.max_position_size_pct
    await _audit(user, "update_risk_limits", update.model_dump())
    return {"ok": True, "limits": lim.model_dump()}


# ══════════════════════════════════════════════════════════════════════════════
# Emergency Stop
# ══════════════════════════════════════════════════════════════════════════════

class EmergencyRequest(BaseModel):
    password:     str
    close_positions: bool = True


@router.post("/emergency/stop", tags=["emergency"])
async def emergency_stop(req: EmergencyRequest, user: str = Depends(get_current_user)):
    if req.password != settings.emergency_stop_password:
        raise HTTPException(status_code=403, detail="Nieprawidłowe hasło Emergency Stop")

    await shared_state.trigger_emergency_stop(reason=f"Panel: {user}")
    await _audit(user, "EMERGENCY_STOP", {"close_positions": req.close_positions})

    if req.close_positions:
        # Connector jest dostępny przez aplikację – publikujemy event
        from core.message_bus import MessageBus
        bus = getattr(shared_state, "_bus", None)
        if bus:
            await bus.publish("audit", {
                "event":     "emergency_close_all",
                "timestamp": datetime.utcnow().isoformat(),
            })

    await broadcast_ws({"event": "emergency_stop", "timestamp": datetime.utcnow().isoformat()})
    return {"ok": True, "emergency_stop": True, "message": "🚨 EMERGENCY STOP AKTYWOWANY"}


class ClearEmergencyRequest(BaseModel):
    password: str


@router.post("/emergency/clear", tags=["emergency"])
async def clear_emergency(req: ClearEmergencyRequest, user: str = Depends(get_current_user)):
    if req.password != settings.emergency_stop_password:
        raise HTTPException(status_code=403, detail="Nieprawidłowe hasło")
    await shared_state.clear_emergency_stop()
    await _audit(user, "EMERGENCY_CLEAR", {})
    await broadcast_ws({"event": "emergency_cleared", "timestamp": datetime.utcnow().isoformat()})
    return {"ok": True, "emergency_stop": False}


# ══════════════════════════════════════════════════════════════════════════════
# Performance / News / Logs
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/performance", tags=["analytics"])
async def get_performance(user: str = Depends(get_current_user)):
    return getattr(shared_state, "performance_reports", {})


@router.get("/allocations", tags=["analytics"])
async def get_allocations(user: str = Depends(get_current_user)):
    return getattr(shared_state, "allocations", {})


@router.get("/news", tags=["analytics"])
async def get_news(limit: int = 20, user: str = Depends(get_current_user)):
    news = getattr(shared_state, "latest_news", [])
    return news[:limit]


@router.get("/logs", tags=["system"])
async def get_logs(lines: int = 100, user: str = Depends(get_current_user)):
    """Zwraca ostatnie N linii z pliku logów."""
    try:
        from pathlib import Path
        log_file = Path("logs/system.log")
        if not log_file.exists():
            return []
        with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
            all_lines = f.readlines()
        return [l.rstrip() for l in all_lines[-lines:]]
    except Exception as exc:
        return [f"Błąd odczytu logów: {exc}"]


# ══════════════════════════════════════════════════════════════════════════════
# WebSocket live feed
# ══════════════════════════════════════════════════════════════════════════════

@router.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    _ws_clients.append(ws)
    try:
        # Wyślij snapshot startowy
        await ws.send_json({"event": "connected", "data": shared_state.snapshot()})
        while True:
            # Ping co 5 sekund + push aktualizacji
            await asyncio.sleep(5)
            snap = shared_state.snapshot()
            await ws.send_json({"event": "update", "data": snap})
    except WebSocketDisconnect:
        pass
    finally:
        if ws in _ws_clients:
            _ws_clients.remove(ws)


# ══════════════════════════════════════════════════════════════════════════════
# AI Chat endpoint
# ══════════════════════════════════════════════════════════════════════════════

class ChatRequest(BaseModel):
    message: str
    history: list[dict] = []   # [{"role": "user"|"assistant", "content": "..."}]


@router.post("/chat", tags=["ai"])
async def ai_chat(req: ChatRequest, user: str = Depends(get_current_user)):
    from panel.ai_chat import AIChatEngine
    engine = AIChatEngine.get_instance()
    response = await engine.chat(req.message, req.history, user=user)
    await _audit(user, "ai_chat", {"message": req.message[:200]})
    return response


# ══════════════════════════════════════════════════════════════════════════════
# Helpers
# ══════════════════════════════════════════════════════════════════════════════

def _resolve_agent(name: str) -> AgentName:
    try:
        return AgentName(name)
    except ValueError:
        # Spróbuj case-insensitive
        for a in AgentName:
            if a.value.lower() == name.lower():
                return a
        raise HTTPException(status_code=404, detail=f"Agent '{name}' nie istnieje")


async def _audit(user: str, action: str, details: dict) -> None:
    try:
        async with get_session() as session:
            session.add(DBAuditLog(user=user, action=action, details=details))
    except Exception:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# Backtester endpoint
# ══════════════════════════════════════════════════════════════════════════════

class BacktestRequest(BaseModel):
    symbol:    str
    start:     str
    end:       str
    timeframe: str = "1h"
    agent:     str = "TrendFollower"
    capital:   float = 10000.0
    run_wfa:   bool = False
    run_mc:    bool = False


@router.post("/backtest/run", tags=["backtester"])
async def run_backtest(req: BacktestRequest, user: str = Depends(get_current_user)):
    from backtester.engine import Backtester, BacktestConfig, WalkForwardAnalysis, MonteCarloSimulation
    from backtester.data_loader import load_data

    AGENT_MAP = {
        "TrendFollower":  "agents.trading.trend_follower.TrendFollower",
        "MeanReversion":  "agents.trading.mean_reversion.MeanReversion",
        "Scalper":        "agents.trading.scalper.Scalper",
        "BreakoutHunter": "agents.trading.breakout_hunter.BreakoutHunter",
        "SentimentTrader":"agents.trading.sentiment_trader.SentimentTrader",
    }

    module_path = AGENT_MAP.get(req.agent)
    if not module_path:
        raise HTTPException(status_code=400, detail=f"Nieznany agent: {req.agent}")

    # Dynamiczny import klasy agenta
    import importlib
    mod_name, cls_name = module_path.rsplit(".", 1)
    module = importlib.import_module(mod_name)
    agent_class = getattr(module, cls_name)

    # Załaduj dane
    df = await load_data(req.symbol, req.start, req.end, req.timeframe)
    if df is None or df.empty:
        return {"error": f"Brak danych dla {req.symbol} [{req.start}→{req.end}]. Zainstaluj yfinance."}

    config = BacktestConfig(
        symbol=req.symbol, start=req.start, end=req.end,
        timeframe=req.timeframe, initial_capital=req.capital,
    )

    bt      = Backtester(config)
    results = await bt.run_with_data(df, agent_class)

    response = {
        "backtest":    results.to_dict(),
        "equity_curve": results.equity_curve[::max(1, len(results.equity_curve)//200)],  # max 200 punktów
        "summary":     results.summary(),
        "wfa":  None,
        "mc":   None,
    }

    if req.run_wfa:
        wfa = WalkForwardAnalysis(config, n_splits=5)
        response["wfa"] = await wfa.run(df, agent_class)

    if req.run_mc:
        mc = MonteCarloSimulation(n_simulations=1000)
        response["mc"] = mc.run(results)

    await _audit(user, "backtest_run", {"symbol": req.symbol, "agent": req.agent})
    return response


# ══════════════════════════════════════════════════════════════════════════════
# Paper Trading Session
# ══════════════════════════════════════════════════════════════════════════════

# Globalny rejestr aktywnych sesji
_active_sessions: dict[str, dict] = {}


class PaperSessionRequest(BaseModel):
    duration_min:     float = 5.0
    capital:          float = 10_000.0
    selected_agents:  list[str] = ["TrendFollower", "MeanReversion", "Scalper", "BreakoutHunter", "SentimentTrader"]
    selected_symbols: list[str] = ["AAPL", "TSLA", "NVDA", "SPY", "QQQ"]


@router.post("/paper-session/start", tags=["paper-session"])
async def start_paper_session(
    req: PaperSessionRequest,
    user: str = Depends(get_current_user),
):
    """Uruchamia sesję testową w tle i zwraca session_id."""
    from backtester.paper_session import PaperTradingSession

    session = PaperTradingSession(
        duration_min     = req.duration_min,
        capital          = req.capital,
        selected_agents  = req.selected_agents,
        selected_symbols = req.selected_symbols,
    )
    session_id = session.session_id
    _active_sessions[session_id] = {
        "status":  "running",
        "session": session,
        "report":  None,
    }

    async def _run():
        report = await session.run()
        _active_sessions[session_id]["report"]  = report.summary()
        _active_sessions[session_id]["status"]  = "done"

    asyncio.create_task(_run())
    await _audit(user, "paper_session_start", {"session_id": session_id, "duration_min": req.duration_min})
    return {"session_id": session_id, "status": "running", "duration_min": req.duration_min}


@router.get("/paper-session/{session_id}/status", tags=["paper-session"])
async def get_paper_session_status(
    session_id: str,
    user: str = Depends(get_current_user),
):
    """Zwraca aktualny status sesji i live tradesów."""
    entry = _active_sessions.get(session_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Sesja nie znaleziona")

    session = entry["session"]
    return {
        "session_id":  session_id,
        "status":      entry["status"],
        "live_trades": session.get_live_trades(),
        "report":      entry["report"],
        "lessons":     session.get_lessons(),
    }


@router.get("/paper-session/{session_id}/report", tags=["paper-session"])
async def get_paper_session_report(
    session_id: str,
    user: str = Depends(get_current_user),
):
    """Zwraca pełny raport po zakończeniu sesji."""
    entry = _active_sessions.get(session_id)
    if not entry:
        raise HTTPException(status_code=404, detail="Sesja nie znaleziona")
    if entry["status"] != "done":
        return {"status": "running", "message": "Sesja jeszcze trwa..."}
    return entry["report"]


@router.get("/paper-sessions", tags=["paper-session"])
async def list_paper_sessions(user: str = Depends(get_current_user)):
    """Lista wszystkich sesji (aktywnych i zakończonych)."""
    return [
        {
            "session_id": sid,
            "status":     e["status"],
            "trades":     len(e["session"].get_live_trades()),
        }
        for sid, e in _active_sessions.items()
    ]


@router.get("/paper-session/memories", tags=["paper-session"])
async def get_agent_memories(user: str = Depends(get_current_user)):
    """Zwraca historię uczenia wszystkich agentów."""
    from agents.learning import get_learning_engine
    return get_learning_engine().get_all_memories()


# ══════════════════════════════════════════════════════════════════════════════
# Przełącznik trybu Paper / Real
# ══════════════════════════════════════════════════════════════════════════════
# Users management
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/auth/register", tags=["auth"])
async def register(data: dict):
    """Rejestruje nowe konto (wymaga zatwierdzenia admina)."""
    from panel.api.auth import register_user
    ok, msg = register_user(data.get("username", ""), data.get("password", ""))
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return {"ok": True, "message": msg}


@router.get("/users", tags=["users"])
async def get_users(user: str = Depends(get_current_user)):
    from panel.api.auth import list_users, get_user_role
    if get_user_role(user) != "admin":
        raise HTTPException(status_code=403, detail="Tylko admin")
    return list_users()


@router.post("/users/{username}/approve", tags=["users"])
async def approve_user(username: str, user: str = Depends(get_current_user)):
    from panel.api.auth import approve_user as _approve, get_user_role
    if get_user_role(user) != "admin":
        raise HTTPException(status_code=403, detail="Tylko admin")
    ok, msg = _approve(username)
    return {"ok": ok, "message": msg}


@router.post("/users/{username}/reject", tags=["users"])
async def reject_user(username: str, user: str = Depends(get_current_user)):
    from panel.api.auth import reject_user as _reject, get_user_role
    if get_user_role(user) != "admin":
        raise HTTPException(status_code=403, detail="Tylko admin")
    ok, msg = _reject(username)
    return {"ok": ok, "message": msg}


@router.delete("/users/{username}", tags=["users"])
async def delete_user(username: str, user: str = Depends(get_current_user)):
    from panel.api.auth import delete_user as _delete, get_user_role
    if get_user_role(user) != "admin":
        raise HTTPException(status_code=403, detail="Tylko admin")
    ok, msg = _delete(username)
    return {"ok": ok, "message": msg}


# ══════════════════════════════════════════════════════════════════════════════

@router.post("/trading-mode/paper", tags=["system"])
async def switch_to_paper(user: str = Depends(get_current_user)):
    """Przełącza system na Paper Trading (bezpieczny tryb)."""
    import os
    os.environ["ALPACA_PAPER"] = "true"
    os.environ["REAL_MODE"]    = "false"
    # Przeładuj settings (wyczyść cache)
    from config.settings import get_settings
    get_settings.cache_clear()
    await _audit(user, "switch_to_paper", {})
    log.warning("🔄 Przełączono na PAPER TRADING przez użytkownika {}", user)
    return {"ok": True, "mode": "paper", "message": "Przełączono na Paper Trading"}


@router.post("/trading-mode/real", tags=["system"])
async def switch_to_real(user: str = Depends(get_current_user)):
    """Przełącza system na Real Trading. UWAGA: prawdziwe pieniądze!"""
    import os
    os.environ["ALPACA_PAPER"] = "false"
    os.environ["REAL_MODE"]    = "true"
    from config.settings import get_settings
    get_settings.cache_clear()
    await _audit(user, "switch_to_real", {})
    log.warning("🔴 Przełączono na REAL TRADING przez użytkownika {}", user)
    return {"ok": True, "mode": "real", "message": "⚠️ Przełączono na Real Trading!"}


@router.get("/trading-mode", tags=["system"])
async def get_trading_mode(user: str = Depends(get_current_user)):
    """Zwraca aktualny tryb handlu."""
    return {
        "paper_mode":  settings.alpaca_paper,
        "real_mode":   settings.real_mode,
        "base_url":    settings.alpaca_base_url,
    }


# ══════════════════════════════════════════════════════════════════════════════
# Coach — ranking i punkty agentów
# ══════════════════════════════════════════════════════════════════════════════

@router.post("/performance/send-to-coach/{agent_name}", tags=["performance"])
async def send_to_coach(agent_name: str, data: dict, user: str = Depends(get_current_user)):
    """Wysyła sugestie z Wydajności do CoachAgenta — kara za problemy."""
    from agents.auxiliary.coach import get_coach
    from datetime import datetime as _dt
    coach   = get_coach()
    issues  = data.get("issues", [])
    win_rate    = data.get("win_rate", 0)
    pf          = data.get("profit_factor", 0)
    total_penalty = 0

    for issue in issues:
        pnl_pct = -1.5
        if "win rate" in issue.lower():    pnl_pct = -2.5
        if "profit factor" in issue.lower(): pnl_pct = -2.0
        pnl_usd = round(pnl_pct * 3, 2)
        coach.review_trade(
            agent_name = agent_name,
            symbol     = "REVIEW",
            direction  = "LONG",
            pnl_usd    = pnl_usd,
            pnl_pct    = pnl_pct,
            trade_id   = f"rev_{agent_name}_{_dt.utcnow().strftime('%H%M%S')}",
        )
        total_penalty += abs(pnl_usd)

    await _audit(user, "send_to_coach", {
        "agent": agent_name, "issues": issues, "penalty": total_penalty
    })
    return {"ok": True, "agent": agent_name, "penalty_applied": total_penalty,
            "message": f"Szef ukarał {agent_name} za {len(issues)} problemów (łącznie -{total_penalty:.0f} pkt)"}



async def get_recent_activity(hours: int = 12, user: str = Depends(get_current_user)):
    """Zwraca aktywność punktową z ostatnich X godzin."""
    from agents.auxiliary.coach import get_coach
    coach = get_coach()
    return coach.get_recent_activity(hours)


@router.get("/coach/ranking", tags=["coach"])
async def get_coach_ranking(user: str = Depends(get_current_user)):
    """Zwraca ranking wszystkich agentów z punktami."""
    from agents.auxiliary.coach import get_coach
    return get_coach().get_ranking()


@router.get("/coach/agent/{agent_name}", tags=["coach"])
async def get_coach_agent(agent_name: str, user: str = Depends(get_current_user)):
    """Zwraca szczegółowy wynik konkretnego agenta."""
    from agents.auxiliary.coach import get_coach
    return get_coach().get_agent_score(agent_name)


@router.post("/coach/reset/{agent_name}", tags=["coach"])
async def reset_coach_agent(agent_name: str, user: str = Depends(get_current_user)):
    """Resetuje wynik agenta."""
    from agents.auxiliary.coach import get_coach
    get_coach().reset_agent(agent_name)
    await _audit(user, "coach_reset", {"agent": agent_name})
    return {"ok": True, "agent": agent_name}


# ══════════════════════════════════════════════════════════════════════════════
# ══════════════════════════════════════════════════════════════════════════════
# Crypto — public API (CoinGecko / Binance / CoinCap — bez klucza)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/crypto/market/global", tags=["crypto"])
async def get_crypto_global(user: str = Depends(get_current_user)):
    """Globalne statystyki rynku krypto z CoinGecko."""
    from services.crypto_data import get_crypto_service
    return await get_crypto_service().get_global_stats()


@router.get("/crypto/market/trending", tags=["crypto"])
async def get_crypto_trending(user: str = Depends(get_current_user)):
    """Trending coins z CoinGecko."""
    from services.crypto_data import get_crypto_service
    return await get_crypto_service().get_trending()


@router.get("/crypto/market/prices", tags=["crypto"])
async def get_crypto_prices(
    symbols: str = "BTC,ETH,SOL,BNB,DOGE,AVAX,XRP,ADA",
    user: str = Depends(get_current_user)
):
    """Ceny wielu kryptowalut — Binance → CoinGecko → CoinCap."""
    from services.crypto_data import get_crypto_service
    tickers = [s.strip().upper() for s in symbols.split(",")]
    return await get_crypto_service().get_market_data(tickers)


# ══════════════════════════════════════════════════════════════════════════════
# Crypto endpoints (Alpaca + Polygon)
# ══════════════════════════════════════════════════════════════════════════════

@router.get("/crypto/{symbol}/quote", tags=["crypto"])
async def get_crypto_quote(symbol: str, user: str = Depends(get_current_user)):
    """Live cena krypto z Alpaca."""
    from core.ibkr_connector import IBKRConnector
    connector = IBKRConnector()
    if connector._crypto_client or not connector._demo_mode:
        # Użyj globalnego connectora z shared_state
        from core.shared_state import shared_state
        conn = getattr(shared_state, "_connector", None)
        if conn and hasattr(conn, "get_crypto_quote"):
            try:
                q = await conn.get_crypto_quote(symbol.upper())
                return {"symbol": symbol, "price": q.last, "bid": q.bid, "ask": q.ask}
            except Exception:
                pass
    # Fallback — Polygon
    try:
        import requests as _req
        key = get_settings().polygon_api_key
        r = _req.get(f"https://api.polygon.io/v2/last/trade/{symbol}?apiKey={key}", timeout=5)
        if r.status_code == 200:
            price = float(r.json().get("results", {}).get("p", 0))
            return {"symbol": symbol, "price": price, "bid": price, "ask": price}
    except Exception:
        pass
    return {"symbol": symbol, "price": 0, "bid": 0, "ask": 0}


@router.get("/crypto/{symbol}/bars", tags=["crypto"])
async def get_crypto_bars(
    symbol: str,
    timeframe: str = "1h",
    user: str = Depends(get_current_user),
):
    """Świece krypto z Alpaca lub Polygon."""
    from core.shared_state import shared_state
    conn = getattr(shared_state, "_connector", None)

    tf_map = {"1m":"1 min","5m":"5 mins","15m":"15 mins","1h":"1 hour","4h":"4 hours","1d":"1 day"}
    dur_map = {"1m":"2 D","5m":"7 D","15m":"14 D","1h":"30 D","4h":"60 D","1d":"365 D"}
    bar_size = tf_map.get(timeframe, "1 hour")
    duration = dur_map.get(timeframe, "30 D")

    # Spróbuj przez Alpaca Crypto
    if conn and hasattr(conn, "get_crypto_bars"):
        try:
            bars = await conn.get_crypto_bars(symbol.upper(), bar_size, duration)
            if bars:
                return [{"t": b.timestamp.isoformat(), "o": b.open, "h": b.high,
                         "l": b.low, "c": b.close, "v": b.volume} for b in bars]
        except Exception:
            pass

    # Fallback — Polygon
    try:
        import requests as _req
        import datetime as _dt
        key  = get_settings().polygon_api_key
        mult_map = {"1m":(1,"minute",2),"5m":(5,"minute",10),"15m":(15,"minute",20),
                    "1h":(1,"hour",30),"4h":(4,"hour",60),"1d":(1,"day",365)}
        mult, span, days = mult_map.get(timeframe, (1,"hour",30))
        end   = _dt.date.today().isoformat()
        start = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
        r = _req.get(
            f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{mult}/{span}/{start}/{end}"
            f"?adjusted=true&sort=asc&limit=300&apiKey={key}",
            timeout=8
        )
        if r.status_code == 200:
            results = r.json().get("results", [])
            import datetime as _dt2
            return [{"t": _dt2.datetime.utcfromtimestamp(row["t"]/1000).isoformat(),
                     "o": row["o"], "h": row["h"], "l": row["l"],
                     "c": row["c"], "v": row.get("v", 0)} for row in results]
    except Exception:
        pass
    return []


# ══════════════════════════════════════════════════════════════════════════════

@router.get("/fundamentals/{symbol}", tags=["fundamentals"])
async def get_fundamentals(symbol: str, user: str = Depends(get_current_user)):
    """Zwraca wskaźniki fundamentalne dla symbolu (P/E, PEG, ROE itp.)"""
    # Sprawdź cache w shared_state
    cached = getattr(shared_state, "fundamentals", {}).get(symbol.upper())
    if cached:
        return cached
    # Pobierz świeże dane z limitem czasu 12s
    from agents.auxiliary.fundamentals_agent import FundamentalsAgent
    agent = FundamentalsAgent(None, None, None, [])
    try:
        data = await asyncio.wait_for(
            asyncio.get_event_loop().run_in_executor(
                None, agent._fetch_fundamentals, symbol.upper()
            ),
            timeout=12.0,
        )
    except asyncio.TimeoutError:
        return {"error": f"Timeout pobierania danych dla {symbol} — spróbuj ponownie"}
    return data


@router.get("/fundamentals", tags=["fundamentals"])
async def get_all_fundamentals(user: str = Depends(get_current_user)):
    """Zwraca wszystkie zapisane wskaźniki fundamentalne."""
    return getattr(shared_state, "fundamentals", {})
