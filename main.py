"""
Punkt startowy systemu tradingowego.

Uruchomienie:
    python main.py                   # system + API
    python main.py --no-agents       # tylko API (bez agentów)
    python main.py --paper           # wymusza paper mode
"""
from __future__ import annotations

import asyncio
import argparse
import sys
from pathlib import Path

# Dodaj katalog projektu do sys.path
sys.path.insert(0, str(Path(__file__).parent))

from core.logger import setup_logging, get_logger
from core.message_bus import RedisMessageBus
from core.ibkr_connector import IBKRConnector
from core.shared_state import shared_state
from config.settings import get_settings
from database.database import init_db
from services.market_data import MarketDataService

# Agenci tradingowi
from agents.trading.trend_follower  import TrendFollower
from agents.trading.mean_reversion  import MeanReversion
from agents.trading.scalper         import Scalper
from agents.trading.breakout_hunter import BreakoutHunter
from agents.trading.sentiment_trader import SentimentTrader
from agents.trading.options_flow    import OptionsFlow
from agents.trading.gap_trader      import GapTrader
from agents.trading.momentum_surfer import MomentumSurfer
from agents.trading.vix_trader      import VIXTrader
from agents.trading.divergence_hunter import DivergenceHunter
from agents.trading.scalp_king      import ScalpKing

# Agenci pomocniczy
from agents.auxiliary.market_analyst     import MarketAnalyst
from agents.auxiliary.news_analyst       import NewsAnalyst
from agents.auxiliary.research_agent     import ResearchAgent
from agents.auxiliary.smart_money_tracker import SmartMoneyTracker
from agents.auxiliary.performance_reviewer import PerformanceReviewer
from agents.auxiliary.portfolio_allocator  import PortfolioAllocator
from agents.auxiliary.fundamentals_agent  import FundamentalsAgent
from agents.auxiliary.earnings_watcher    import EarningsWatcher
from agents.auxiliary.macro_analyst       import MacroAnalyst
from agents.auxiliary.correlation_guard   import CorrelationGuard
from agents.auxiliary.heatmap_analyst     import HeatmapAnalyst
from agents.auxiliary.whale_tracker       import WhaleTracker
from agents.auxiliary.economic_calendar   import EconomicCalendar

# Core
from agents.risk_manager  import RiskManager
from agents.orchestrator  import Orchestrator
from alerting.alerting    import AlertingService

setup_logging()
log = get_logger(__name__)

# Wycisz hałaśliwe zewnętrzne biblioteki
import logging as _logging
_logging.getLogger("yfinance").setLevel(_logging.CRITICAL)
_logging.getLogger("peewee").setLevel(_logging.CRITICAL)
_logging.getLogger("urllib3").setLevel(_logging.CRITICAL)
_logging.getLogger("requests").setLevel(_logging.CRITICAL)


def _calculate_risk_limits(capital: float, is_paper: bool) -> dict:
    """
    Auto-konfiguruje limity ryzyka na podstawie kapitału.

    Zasady:
    - Im mniejszy kapitał → większy % ryzyka per trade (proporcjonalnie)
    - Paper trading → bardziej agresywne limity (można tracić)
    - Real trading → konserwatywniejsze limity
    """
    if capital <= 0:
        capital = 10_000.0

    # Skalowanie agresywności
    if is_paper:
        daily_loss_pct     = 0.10   # 10% dziennie (paper - można ryzykować)
        drawdown_pct       = 20.0
        position_size_pct  = 8.0
    elif capital < 500:
        daily_loss_pct     = 0.08   # $100 → max $8 straty dziennie
        drawdown_pct       = 15.0
        position_size_pct  = 5.0
    elif capital < 2000:
        daily_loss_pct     = 0.06
        drawdown_pct       = 12.0
        position_size_pct  = 4.0
    elif capital < 10_000:
        daily_loss_pct     = 0.05
        drawdown_pct       = 10.0
        position_size_pct  = 3.0
    else:
        daily_loss_pct     = 0.03
        drawdown_pct       = 8.0
        position_size_pct  = 2.0

    max_daily_loss = round(capital * daily_loss_pct, 2)

    return {
        "max_daily_loss_usd":    max_daily_loss,
        "max_drawdown_pct":      drawdown_pct,
        "total_capital_usd":     capital,
        "max_position_size_pct": position_size_pct,
    }

# ── Instrumenty do obserwacji ────────────────────────────────────────────────
WATCHLIST = [
    # 🇺🇸 Mega-cap US
    "AAPL", "MSFT", "NVDA", "GOOGL", "AMZN", "META", "TSLA",
    # 💾 Chips & Tech
    "AMD", "INTC", "AVGO", "QCOM", "ARM", "TSM",
    # 🏦 Finanse US
    "JPM", "BAC", "GS", "V", "MA",
    # 📊 ETF szerokie
    "SPY", "QQQ", "IWM", "VTI",
    # ₿ Krypto ETF
    "IBIT", "COIN", "MSTR",
    # 🚀 Growth
    "PLTR", "SNOW", "UBER", "HOOD",
    # 🇵🇱 Polska GPW
    "PKN", "PKO", "PZU", "CDR", "ALE", "LPP", "KGH", "MBK", "DNP", "PEO",
    # 🇬🇧 Wielka Brytania LSE
    "HSBA", "BP", "SHEL", "AZN", "GSK", "BARC", "LLOY", "VOD", "RR", "BAE",
]


async def run_system(no_agents: bool = False) -> None:
    settings = get_settings()

    # ══════════════════════════════════════════════════════════════════════
    print("\033[2J\033[H", end="")  # wyczyść ekran
    print("\033[96m" + "═" * 60 + "\033[0m")
    print("\033[96m  ⚡ IBKR Multi-Agent Trading System\033[0m")
    print("\033[96m" + "═" * 60 + "\033[0m")
    mode_str = "\033[93m📄 PAPER TRADING\033[0m" if not settings.real_mode else "\033[91m🔴 REAL TRADING\033[0m"
    print(f"  Tryb: {mode_str}")
    print()

    # ── Baza danych ───────────────────────────────────────────────────────
    print("  \033[90m[1/5]\033[0m Inicjalizacja bazy danych...", end=" ", flush=True)
    await init_db()
    print("\033[92m✓\033[0m")

    # ── Message bus ───────────────────────────────────────────────────────
    bus = RedisMessageBus(settings.redis_url)

    # ── IBKR connector ────────────────────────────────────────────────────
    print("  \033[90m[2/5]\033[0m Łączenie z Alpaca...", end=" ", flush=True)
    connector = IBKRConnector()
    await connector.connect()
    shared_state.ibkr_connected = connector.connected
    shared_state._connector     = connector  # dostęp z API routes
    account = await connector.get_account()
    shared_state.account = account
    print(f"\033[92m✓\033[0m  kapitał: \033[93m${account.net_liquidation:,.2f}\033[0m  buying power: \033[93m${account.buying_power:,.2f}\033[0m")

    # ── Auto-konfiguracja ryzyka na podstawie kapitału ───────────────────
    capital = account.net_liquidation
    auto_risk = _calculate_risk_limits(capital, settings.alpaca_paper)
    shared_state.risk_limits.max_daily_loss_usd    = auto_risk["max_daily_loss_usd"]
    shared_state.risk_limits.max_drawdown_pct      = auto_risk["max_drawdown_pct"]
    shared_state.risk_limits.total_capital_usd     = capital
    shared_state.risk_limits.max_position_size_pct = auto_risk["max_position_size_pct"]
    print(f"  \033[90m⚙️  Ryzyko:\033[0m   max strata/dzień=${auto_risk['max_daily_loss_usd']:.0f} | "
          f"max pozycja={auto_risk['max_position_size_pct']:.0f}% | "
          f"max drawdown={auto_risk['max_drawdown_pct']:.0f}%")
    print(f"  \033[90m[3/5]\033[0m Pobieranie danych rynkowych ({len(WATCHLIST)} symboli)...", end=" ", flush=True)
    market_data = MarketDataService(connector)
    await market_data.start(WATCHLIST)
    print(f"\033[92m✓\033[0m  {', '.join(WATCHLIST)}")

    # ── Risk manager + Orchestrator ───────────────────────────────────────
    print("  \033[90m[4/5]\033[0m Uruchamianie Risk Managera i Orchestratora...", end=" ", flush=True)
    alerting = AlertingService()
    bus.subscribe("alerts", alerting.handle_bus_alert)
    risk_mgr = RiskManager(alerting=alerting)
    orchestrator = Orchestrator(connector, bus, risk_mgr)
    await orchestrator.start()
    await bus.start()
    shared_state._bus = bus
    print("\033[92m✓\033[0m")

    # ── Agenci ────────────────────────────────────────────────────────────
    print("  \033[90m[5/5]\033[0m Uruchamianie agentów...", end=" ", flush=True)
    all_agents = []
    if no_agents:
        print("\033[93mpominięto (--no-agents)\033[0m")
    else:
        trading_agents = [
            TrendFollower  (connector, market_data, bus, WATCHLIST, interval_sec=300),
            MeanReversion  (connector, market_data, bus, WATCHLIST, interval_sec=120),
            Scalper        (connector, market_data, bus, WATCHLIST, interval_sec=30),
            BreakoutHunter (connector, market_data, bus, WATCHLIST, interval_sec=180),
            SentimentTrader(connector, market_data, bus, WATCHLIST, interval_sec=240),
            OptionsFlow    (connector, market_data, bus, WATCHLIST, interval_sec=300),
            GapTrader      (connector, market_data, bus, WATCHLIST, interval_sec=600),
            MomentumSurfer (connector, market_data, bus, WATCHLIST, interval_sec=180),
            VIXTrader      (connector, market_data, bus, WATCHLIST, interval_sec=300),
            DivergenceHunter(connector, market_data, bus, WATCHLIST, interval_sec=240),
            ScalpKing      (connector, market_data, bus, WATCHLIST, interval_sec=15),
        ]
        aux_agents = [
            MarketAnalyst    (connector, market_data, bus, WATCHLIST, interval_sec=600),
            NewsAnalyst      (connector, market_data, bus, WATCHLIST, interval_sec=180),
            ResearchAgent    (connector, market_data, bus, WATCHLIST, interval_sec=1800),
            SmartMoneyTracker(connector, market_data, bus, WATCHLIST, interval_sec=300),
            PerformanceReviewer(connector, market_data, bus, WATCHLIST, interval_sec=3600),
            PortfolioAllocator (connector, market_data, bus, WATCHLIST, interval_sec=14400),
            FundamentalsAgent  (connector, market_data, bus, WATCHLIST, interval_sec=3600),
            EarningsWatcher    (connector, market_data, bus, WATCHLIST, interval_sec=3600),
            MacroAnalyst       (connector, market_data, bus, WATCHLIST, interval_sec=1800),
            CorrelationGuard   (connector, market_data, bus, WATCHLIST, interval_sec=300),
            HeatmapAnalyst     (connector, market_data, bus, WATCHLIST, interval_sec=1800),
            WhaleTracker       (connector, market_data, bus, WATCHLIST, interval_sec=120),
            EconomicCalendar   (connector, market_data, bus, WATCHLIST, interval_sec=3600),
        ]
        all_agents = trading_agents + aux_agents
        started = 0
        for agent in all_agents:
            cfg = shared_state.agent_configs.get(agent.name)
            if cfg and cfg.enabled:
                await agent.start()
                started += 1
        print(f"\033[92m✓\033[0m  {started} agentów aktywnych")

    # ── Gotowe — wyświetl banner ──────────────────────────────────────────
    print()
    print("\033[92m" + "═" * 60 + "\033[0m")
    print("\033[92m  ✅ SYSTEM GOTOWY — możesz otworzyć panel\033[0m")
    print("\033[92m" + "═" * 60 + "\033[0m")
    print()
    print("  \033[96m🖥  Panel:\033[0m   http://localhost:8501  (uruchom IBKR Panel - Start)")
    print("  \033[96m📡 API:\033[0m     http://localhost:8000/docs")
    print(f"  \033[96m💰 Konto:\033[0m   ${account.net_liquidation:,.2f}  ({('PAPER' if settings.alpaca_paper else 'REAL')})")
    print()
    print("  \033[90mCtrl+C aby zatrzymać system\033[0m")
    print()

    # ── FastAPI server ────────────────────────────────────────────────────
    import uvicorn
    from panel.api.app import app

    async def _account_refresh_loop():
        while True:
            await asyncio.sleep(30)
            try:
                acc = await connector.get_account()
                await shared_state.update_account(acc)
            except Exception:
                pass

    asyncio.create_task(_account_refresh_loop())

    # ── Pętla synchronizująca pozycje i wypełnienia co 10s ──────────────
    async def _orders_sync_loop():
        while True:
            await asyncio.sleep(10)
            try:
                # Zsynchronizuj pozycje
                positions = await connector.get_positions()
                for sym, pos in positions.items():
                    await shared_state.update_position(pos)
                for sym in list(shared_state.positions.keys()):
                    if sym not in positions:
                        # Pozycja zamknięta — ocen przez Szefa
                        old_pos = shared_state.positions.get(sym)
                        if old_pos and old_pos.avg_cost > 0:
                            try:
                                from agents.auxiliary.coach import get_coach
                                import time as _t
                                pnl_usd = old_pos.unrealized_pnl
                                pnl_pct = old_pos.pnl_pct
                                agent   = old_pos.agent_name.value if old_pos.agent_name else "Unknown"
                                get_coach().review_trade(
                                    agent_name = agent,
                                    symbol     = sym,
                                    direction  = "LONG" if old_pos.quantity > 0 else "SHORT",
                                    pnl_usd    = pnl_usd,
                                    pnl_pct    = pnl_pct,
                                    trade_id   = f"live_{sym}_{int(_t.time())}",
                                )
                            except Exception:
                                pass
                        await shared_state.remove_position(sym)
                # Zsynchronizuj konto
                acc = await connector.get_account()
                await shared_state.update_account(acc)

                # Aktualizuj statusy SUBMITTED → FILLED w bazie
                if connector._trading_client and not connector._demo_mode:
                    from database.database import get_session
                    from database.models import DBOrder
                    from sqlalchemy import select
                    from alpaca.trading.requests import GetOrdersRequest
                    from alpaca.trading.enums import QueryOrderStatus

                    closed = await asyncio.get_event_loop().run_in_executor(
                        None, lambda: connector._trading_client.get_orders(
                            GetOrdersRequest(status=QueryOrderStatus.CLOSED, limit=50)
                        )
                    )
                    closed_by_symbol = {}
                    for o in closed:
                        closed_by_symbol.setdefault(o.symbol, []).append(o)

                    async with get_session() as session:
                        result = await session.execute(
                            select(DBOrder).where(DBOrder.status == "submitted")
                        )
                        for db_order in result.scalars().all():
                            matches = closed_by_symbol.get(db_order.symbol, [])
                            for ao in matches:
                                if ao.status.value in ("filled", "partially_filled"):
                                    db_order.status     = ao.status.value
                                    db_order.filled_qty = float(ao.filled_qty or 0)
                                    db_order.avg_price  = float(ao.filled_avg_price or 0)
                                    break
            except Exception:
                pass

    asyncio.create_task(_orders_sync_loop())

    config = uvicorn.Config(
        app,
        host="0.0.0.0",
        port=8000,
        log_level="warning",
        loop="asyncio",
    )
    server = uvicorn.Server(config)

    # ── Live status ticker w konsoli ─────────────────────────────────────────
    async def _status_ticker():
        import datetime
        while True:
            await asyncio.sleep(30)
            acc    = shared_state.account
            pos    = len(shared_state.positions)
            sigs   = len(shared_state.recent_signals)
            pnl    = shared_state.daily_pnl
            pnl_c  = "\033[92m" if pnl >= 0 else "\033[91m"
            now    = datetime.datetime.now().strftime("%H:%M:%S")
            errors = sum(1 for s in shared_state.agent_states.values() if s.status.value == "error")
            err_str = f"  \033[91m⚠ {errors} błędów\033[0m" if errors else ""
            print(
                f"\r  \033[90m{now}\033[0m  "
                f"💰 \033[93m${acc.net_liquidation:,.0f}\033[0m  "
                f"📊 pozycji: \033[96m{pos}\033[0m  "
                f"📡 sygnałów: \033[96m{sigs}\033[0m  "
                f"PnL: {pnl_c}{pnl:+.2f}\033[0m"
                f"{err_str}",
                end="", flush=True
            )

    asyncio.create_task(_status_ticker())

    try:
        await server.serve()
    except asyncio.CancelledError:
        pass
        print("\n  \033[93m⏹  Zatrzymuję system…\033[0m")
        if not no_agents:
            for agent in all_agents:
                await agent.stop()
        await orchestrator.stop()
        await bus.stop()
        await connector.disconnect()
        print("  \033[92m✓ System zatrzymany\033[0m\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="IBKR Trading System")
    parser.add_argument("--no-agents", action="store_true", help="Uruchom tylko API bez agentów")
    parser.add_argument("--paper",     action="store_true", help="Wymusz paper trading mode")
    args = parser.parse_args()

    if args.paper:
        import os
        os.environ["REAL_MODE"] = "false"

    try:
        asyncio.run(run_system(no_agents=args.no_agents))
    except KeyboardInterrupt:
        log.info("Przerwano przez użytkownika (Ctrl+C)")


if __name__ == "__main__":
    main()
