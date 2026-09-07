"""
Backtester – silnik testowania strategii na danych historycznych.

Obsługuje:
- Pojedyncze strategie i multi-agent portfolio
- Walk-Forward Analysis (WFA)
- Monte Carlo simulation
- Pełne metryki: Sharpe, Sortino, Max Drawdown, Profit Factor, Win Rate
- Koszty transakcyjne (prowizja + spread)
- Eksport wyników do CSV / JSON

Użycie:
    from backtester.engine import Backtester, BacktestConfig
    
    config = BacktestConfig(
        symbol="AAPL",
        start="2023-01-01",
        end="2024-01-01",
        initial_capital=10000,
        commission=1.0,
    )
    bt = Backtester(config)
    results = await bt.run(agent_class=TrendFollower, agent_params={})
    print(results.summary())
"""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any, Optional, Type

import numpy as np
import pandas as pd

from agents.base_agent import BaseAgent
from core.logger import get_logger
from core.models import AgentName, SignalDirection, TradeSignal
from services.market_data import MarketDataService

log = get_logger(__name__)


# ══════════════════════════════════════════════════════════════════════════════
# Konfiguracja
# ══════════════════════════════════════════════════════════════════════════════

@dataclass
class BacktestConfig:
    symbol:          str
    start:           str        # "YYYY-MM-DD"
    end:             str        # "YYYY-MM-DD"
    timeframe:       str = "1h"
    initial_capital: float = 10_000.0
    commission:      float = 1.0        # USD per strona
    spread_pct:      float = 0.0005     # 0.05% spread
    position_size_pct: float = 5.0      # % kapitału na transakcję
    slippage_pct:    float = 0.0002     # 0.02% poślizg


@dataclass
class Trade:
    entry_time:  datetime
    exit_time:   Optional[datetime]
    direction:   SignalDirection
    entry_price: float
    exit_price:  float = 0.0
    quantity:    float = 0.0
    pnl:         float = 0.0
    commission:  float = 0.0
    exit_reason: str   = ""    # sl / tp / signal / end_of_data


@dataclass
class BacktestResults:
    config:          BacktestConfig
    trades:          list[Trade]  = field(default_factory=list)
    equity_curve:    list[float]  = field(default_factory=list)
    timestamps:      list[datetime] = field(default_factory=list)
    agent_name:      str = ""

    # ── Metryki ───────────────────────────────────────────────────────────────
    total_return_pct:   float = 0.0
    annual_return_pct:  float = 0.0
    sharpe_ratio:       float = 0.0
    sortino_ratio:      float = 0.0
    max_drawdown_pct:   float = 0.0
    profit_factor:      float = 0.0
    win_rate:           float = 0.0
    avg_win:            float = 0.0
    avg_loss:           float = 0.0
    total_trades:       int   = 0
    winning_trades:     int   = 0
    losing_trades:      int   = 0
    avg_trade_duration: str   = ""

    def summary(self) -> str:
        return (
            f"\n{'='*60}\n"
            f"BACKTEST: {self.agent_name} | {self.config.symbol} "
            f"[{self.config.start} → {self.config.end}]\n"
            f"{'='*60}\n"
            f"Kapitał startowy:  ${self.config.initial_capital:,.2f}\n"
            f"Zwrot całkowity:   {self.total_return_pct:+.2f}%\n"
            f"Zwrot roczny:      {self.annual_return_pct:+.2f}%\n"
            f"Sharpe Ratio:      {self.sharpe_ratio:.3f}\n"
            f"Sortino Ratio:     {self.sortino_ratio:.3f}\n"
            f"Max Drawdown:      {self.max_drawdown_pct:.2f}%\n"
            f"Profit Factor:     {self.profit_factor:.3f}\n"
            f"Win Rate:          {self.win_rate:.1%}\n"
            f"Transakcji:        {self.total_trades} "
            f"(W:{self.winning_trades} L:{self.losing_trades})\n"
            f"Avg Win:           ${self.avg_win:.2f}\n"
            f"Avg Loss:          ${self.avg_loss:.2f}\n"
            f"Avg Hold:          {self.avg_trade_duration}\n"
            f"{'='*60}\n"
        )

    def to_dict(self) -> dict:
        return {
            "agent":             self.agent_name,
            "symbol":            self.config.symbol,
            "start":             self.config.start,
            "end":               self.config.end,
            "total_return_pct":  round(self.total_return_pct, 3),
            "annual_return_pct": round(self.annual_return_pct, 3),
            "sharpe_ratio":      round(self.sharpe_ratio, 3),
            "sortino_ratio":     round(self.sortino_ratio, 3),
            "max_drawdown_pct":  round(self.max_drawdown_pct, 3),
            "profit_factor":     round(self.profit_factor, 3),
            "win_rate":          round(self.win_rate, 4),
            "total_trades":      self.total_trades,
        }


# ══════════════════════════════════════════════════════════════════════════════
# Backtester
# ══════════════════════════════════════════════════════════════════════════════

class MockMessageBus:
    """Minimalny mock bus do backtestu – zbiera sygnały bez wysyłania."""
    def __init__(self): self.signals: list[dict] = []
    async def publish(self, channel: str, message: dict): self.signals.append(message)
    def subscribe(self, *a): pass


class MockConnector:
    """Mock connector – zwraca dane z DataFrame."""
    def __init__(self, df: pd.DataFrame, symbol: str):
        self._df     = df
        self._symbol = symbol
        self._cursor = 0

    async def get_quote(self, symbol):
        from core.models import Quote
        close = float(self._df.iloc[self._cursor]["close"])
        return Quote(symbol=symbol, bid=close*0.9999, ask=close*1.0001, last=close, volume=1000)

    async def get_historical_bars(self, symbol, **kwargs):
        from core.models import Bar
        rows = self._df.iloc[:self._cursor + 1]
        return [
            Bar(
                timestamp=idx if isinstance(idx, datetime) else datetime.utcnow(),
                open=float(r["open"]), high=float(r["high"]),
                low=float(r["low"]),  close=float(r["close"]),
                volume=float(r["volume"]), symbol=symbol,
            )
            for idx, r in rows.iterrows()
        ]

    @property
    def connected(self): return True


class MockMarketData:
    """MarketData mock – serwuje dane z cache okna rolling."""
    def __init__(self, df: pd.DataFrame):
        self._df = df
        self.cursor = 0

    async def get_bars(self, symbol, timeframe="1h", limit=200):
        end   = self.cursor + 1
        start = max(0, end - limit)
        df_slice = self._df.iloc[start:end].copy()
        return self._add_indicators(df_slice)

    async def get_quote(self, symbol):
        from core.models import Quote
        row = self._df.iloc[self.cursor]
        c   = float(row["close"])
        return Quote(symbol=symbol, bid=c*0.9999, ask=c*1.0001, last=c, volume=float(row.get("volume", 1000)))

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        if len(df) < 5:
            return df
        try:
            import ta as ta_lib
            df = df.copy()
            close = df["close"]
            high  = df["high"]
            low   = df["low"]

            df["ema_3"]   = ta_lib.trend.ema_indicator(close, window=3)
            df["ema_8"]   = ta_lib.trend.ema_indicator(close, window=8)
            df["ema_9"]   = ta_lib.trend.ema_indicator(close, window=9)
            df["ema_21"]  = ta_lib.trend.ema_indicator(close, window=21)
            df["ema_50"]  = ta_lib.trend.ema_indicator(close, window=50)
            df["ema_200"] = ta_lib.trend.ema_indicator(close, window=200)
            df["sma_20"]  = ta_lib.trend.sma_indicator(close, window=20)
            if len(df) >= 14:
                df["rsi_14"] = ta_lib.momentum.rsi(close, window=14)
                df["atr_14"] = ta_lib.volatility.average_true_range(high, low, close, window=14)
                df["adx"]    = ta_lib.trend.adx(high, low, close, window=14)
                df["di_pos"] = ta_lib.trend.adx_pos(high, low, close, window=14)
                df["di_neg"] = ta_lib.trend.adx_neg(high, low, close, window=14)
            if len(df) >= 20:
                bb = ta_lib.volatility.BollingerBands(close, window=20, window_dev=2)
                df["bb_lower"] = bb.bollinger_lband()
                df["bb_mid"]   = bb.bollinger_mavg()
                df["bb_upper"] = bb.bollinger_hband()
                df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / (df["bb_mid"] + 1e-9)
                rm = close.rolling(20).mean()
                rs = close.rolling(20).std()
                df["zscore"] = (close - rm) / (rs + 1e-9)
                df["vol_sma_20"] = df["volume"].rolling(20).mean()
                df["vol_ratio"]  = df["volume"] / (df["vol_sma_20"] + 1e-9)
                df["resistance_20"] = high.rolling(20).max()
                df["support_20"]    = low.rolling(20).min()
        except Exception as exc:
            log.debug("Indicator error w backtest: {}", exc)
        return df

    # Potrzebne przez agentów (uproszczone)
    _bar_cache: dict = {}
    def _add_indicators_direct(self, df): return self._add_indicators(df)


class Backtester:
    """Główny silnik backtestingu."""

    def __init__(self, config: BacktestConfig) -> None:
        self.config = config

    async def run_with_data(
        self,
        df: pd.DataFrame,
        agent_class: Type[BaseAgent],
        agent_params: dict | None = None,
        agent_name_override: str | None = None,
    ) -> BacktestResults:
        """
        Uruchamia backtest na gotowym DataFrame.
        df musi mieć kolumny: open, high, low, close, volume
        """
        agent_params = agent_params or {}
        cfg = self.config

        bus         = MockMessageBus()
        mock_md     = MockMarketData(df)
        mock_conn   = MockConnector(df, cfg.symbol)

        # Stwórz agenta
        agent = agent_class(
            connector=mock_conn,
            market_data=mock_md,
            bus=bus,
            symbols=[cfg.symbol],
            **agent_params,
        )
        agent_name = agent_name_override or agent.name.value

        capital  = cfg.initial_capital
        equity   = [capital]
        timestamps = [df.index[0] if hasattr(df.index[0], 'strftime') else datetime.utcnow()]
        trades:  list[Trade] = []
        open_trade: Optional[Trade] = None

        log.info("Backtest {} | {} | {} → {} | {} świec",
                 agent_name, cfg.symbol, cfg.start, cfg.end, len(df))

        # Iteracja po świecach
        for i in range(50, len(df)):   # pierwsze 50 na rozgrzanie wskaźników
            mock_md.cursor  = i
            mock_conn._cursor = i
            row = df.iloc[i]
            close_price = float(row["close"])
            ts = df.index[i] if hasattr(df.index[i], 'strftime') else datetime(2020, 1, 1) + timedelta(hours=i)

            # Sprawdź czy zamknąć otwartą pozycję
            if open_trade:
                close_reason = None
                # Stop Loss
                if open_trade.direction == SignalDirection.LONG:
                    if hasattr(open_trade, "_sl") and close_price <= open_trade._sl:
                        close_reason = "sl"
                    elif hasattr(open_trade, "_tp") and close_price >= open_trade._tp:
                        close_reason = "tp"
                else:
                    if hasattr(open_trade, "_sl") and close_price >= open_trade._sl:
                        close_reason = "sl"
                    elif hasattr(open_trade, "_tp") and close_price <= open_trade._tp:
                        close_reason = "tp"

                if close_reason:
                    exit_price = close_price * (1 + (cfg.slippage_pct if open_trade.direction == SignalDirection.LONG else -cfg.slippage_pct))
                    if open_trade.direction == SignalDirection.LONG:
                        pnl = (exit_price - open_trade.entry_price) * open_trade.quantity
                    else:
                        pnl = (open_trade.entry_price - exit_price) * open_trade.quantity
                    pnl -= cfg.commission  # prowizja wyjścia
                    open_trade.exit_price  = exit_price
                    open_trade.exit_time   = ts
                    open_trade.pnl         = pnl
                    open_trade.exit_reason = close_reason
                    trades.append(open_trade)
                    capital    += pnl
                    open_trade  = None

            # Pobierz sygnał od agenta
            if not open_trade:
                try:
                    signal = await agent.analyze(cfg.symbol)
                except Exception:
                    signal = None

                if signal and signal.direction in (SignalDirection.LONG, SignalDirection.SHORT):
                    entry = close_price * (1 + (cfg.spread_pct / 2) + cfg.slippage_pct)
                    qty   = (capital * cfg.position_size_pct / 100.0) / entry
                    if qty > 0:
                        t = Trade(
                            entry_time=ts,
                            exit_time=None,
                            direction=signal.direction,
                            entry_price=entry,
                            quantity=qty,
                            commission=cfg.commission,
                        )
                        t._sl = signal.stop_loss   or entry * (0.98 if signal.direction == SignalDirection.LONG else 1.02)
                        t._tp = signal.take_profit or entry * (1.03 if signal.direction == SignalDirection.LONG else 0.97)
                        capital -= cfg.commission  # prowizja wejścia
                        open_trade = t

            equity.append(capital)
            timestamps.append(ts)

        # Zamknij otwartą pozycję na końcu danych
        if open_trade:
            last_close = float(df.iloc[-1]["close"])
            pnl = (last_close - open_trade.entry_price) * open_trade.quantity \
                  if open_trade.direction == SignalDirection.LONG \
                  else (open_trade.entry_price - last_close) * open_trade.quantity
            pnl -= cfg.commission
            open_trade.exit_price  = last_close
            open_trade.exit_time   = timestamps[-1]
            open_trade.pnl         = pnl
            open_trade.exit_reason = "end_of_data"
            trades.append(open_trade)
            capital += pnl

        results = BacktestResults(
            config=cfg, trades=trades,
            equity_curve=equity, timestamps=timestamps,
            agent_name=agent_name,
        )
        self._compute_metrics(results)
        return results

    # ──────────────────────────────────────────────────────────────────────────
    # Metryki
    # ──────────────────────────────────────────────────────────────────────────

    def _compute_metrics(self, r: BacktestResults) -> None:
        equity = np.array(r.equity_curve)
        init   = r.config.initial_capital

        r.total_return_pct = (equity[-1] / init - 1) * 100

        # Roczny zwrot
        days = max(1, (r.timestamps[-1] - r.timestamps[0]).days if len(r.timestamps) > 1 else 252)
        r.annual_return_pct = ((equity[-1] / init) ** (365.0 / days) - 1) * 100

        # Drawdown
        peak = np.maximum.accumulate(equity)
        dd   = (peak - equity) / (peak + 1e-9) * 100
        r.max_drawdown_pct = float(dd.max())

        # Sharpe / Sortino
        rets = np.diff(equity) / (equity[:-1] + 1e-9)
        if len(rets) > 1:
            r.sharpe_ratio  = float(rets.mean() / (rets.std() + 1e-9) * np.sqrt(252))
            neg_rets = rets[rets < 0]
            down_std = neg_rets.std() if len(neg_rets) > 1 else 1e-9
            r.sortino_ratio = float(rets.mean() / (down_std + 1e-9) * np.sqrt(252))

        # Trade metryki
        r.total_trades  = len(r.trades)
        wins  = [t.pnl for t in r.trades if t.pnl > 0]
        losses= [t.pnl for t in r.trades if t.pnl <= 0]

        r.winning_trades = len(wins)
        r.losing_trades  = len(losses)
        r.win_rate   = len(wins) / max(r.total_trades, 1)
        r.avg_win    = float(np.mean(wins))  if wins   else 0.0
        r.avg_loss   = float(np.mean(losses)) if losses else 0.0

        gross_profit = sum(wins)
        gross_loss   = abs(sum(losses))
        r.profit_factor = gross_profit / (gross_loss + 1e-9)

        # Avg hold duration
        durations = []
        for t in r.trades:
            if t.exit_time and t.entry_time:
                durations.append((t.exit_time - t.entry_time).total_seconds() / 3600)
        if durations:
            avg_h = np.mean(durations)
            r.avg_trade_duration = f"{avg_h:.1f}h"


# ══════════════════════════════════════════════════════════════════════════════
# Walk-Forward Analysis
# ══════════════════════════════════════════════════════════════════════════════

class WalkForwardAnalysis:
    """
    Walk-Forward Analysis – optymalizacja na oknie In-Sample,
    walidacja na Out-of-Sample.

    Parametry:
        n_splits        – liczba okien (domyślnie 5)
        is_ratio        – proporcja In-Sample do Out-of-Sample (domyślnie 0.7)
    """

    def __init__(
        self,
        config: BacktestConfig,
        n_splits: int = 5,
        is_ratio:  float = 0.7,
    ) -> None:
        self.config    = config
        self.n_splits  = n_splits
        self.is_ratio  = is_ratio

    async def run(
        self,
        df: pd.DataFrame,
        agent_class: Type[BaseAgent],
        param_grid: dict[str, list] | None = None,
    ) -> dict:
        """
        Zwraca wyniki WFA: lista wyników per okno + podsumowanie.
        """
        n = len(df)
        window_size = n // self.n_splits
        results_wfa = []

        log.info("Walk-Forward: {} okien, window_size={}", self.n_splits, window_size)

        for i in range(self.n_splits):
            start = i * window_size
            end   = start + window_size if i < self.n_splits - 1 else n
            split = int((end - start) * self.is_ratio)

            df_is  = df.iloc[start : start + split]       # In-Sample
            df_oos = df.iloc[start + split : end]          # Out-of-Sample

            if len(df_is) < 100 or len(df_oos) < 20:
                continue

            bt_is  = Backtester(self.config)
            bt_oos = Backtester(self.config)

            res_is  = await bt_is.run_with_data(df_is,  agent_class, agent_name_override=f"IS_{i+1}")
            res_oos = await bt_oos.run_with_data(df_oos, agent_class, agent_name_override=f"OOS_{i+1}")

            results_wfa.append({
                "window":     i + 1,
                "is_return":  res_is.total_return_pct,
                "oos_return": res_oos.total_return_pct,
                "is_sharpe":  res_is.sharpe_ratio,
                "oos_sharpe": res_oos.sharpe_ratio,
                "is_result":  res_is.to_dict(),
                "oos_result": res_oos.to_dict(),
            })
            log.info("WFA okno {} | IS={:+.2f}% OOS={:+.2f}%",
                     i+1, res_is.total_return_pct, res_oos.total_return_pct)

        oos_returns = [w["oos_return"] for w in results_wfa]
        return {
            "windows":          results_wfa,
            "avg_oos_return":   float(np.mean(oos_returns)) if oos_returns else 0.0,
            "std_oos_return":   float(np.std(oos_returns))  if oos_returns else 0.0,
            "positive_windows": sum(1 for r in oos_returns if r > 0),
            "total_windows":    len(results_wfa),
        }


# ══════════════════════════════════════════════════════════════════════════════
# Monte Carlo
# ══════════════════════════════════════════════════════════════════════════════

class MonteCarloSimulation:
    """
    Symulacja Monte Carlo na podstawie rozkładu zwrotów z backtestu.
    Generuje N=1000 ścieżek equity curve i oblicza przedziały ufności.
    """

    def __init__(self, n_simulations: int = 1000) -> None:
        self.n_simulations = n_simulations

    def run(self, results: BacktestResults) -> dict:
        if not results.trades:
            return {"error": "Brak transakcji do symulacji"}

        pnl_list = [t.pnl for t in results.trades]
        n_trades = len(pnl_list)
        init_cap = results.config.initial_capital

        paths = []
        final_equities = []

        for _ in range(self.n_simulations):
            sampled  = np.random.choice(pnl_list, size=n_trades, replace=True)
            equity_path = [init_cap]
            for pnl in sampled:
                equity_path.append(equity_path[-1] + pnl)
            paths.append(equity_path)
            final_equities.append(equity_path[-1])

        final = np.array(final_equities)
        p5, p25, p50, p75, p95 = np.percentile(final, [5, 25, 50, 75, 95])

        # Max Drawdown distribution
        mdd_list = []
        for path in paths:
            arr  = np.array(path)
            peak = np.maximum.accumulate(arr)
            dd   = (peak - arr) / (peak + 1e-9) * 100
            mdd_list.append(float(dd.max()))

        mdd = np.array(mdd_list)
        prob_profitable = float((final > init_cap).mean()) * 100

        log.info(
            "Monte Carlo ({} symulacji) | P50={:+.1f}% | P5={:+.1f}% | "
            "P(profit)={:.1f}% | Avg_MaxDD={:.1f}%",
            self.n_simulations,
            (p50 / init_cap - 1) * 100,
            (p5  / init_cap - 1) * 100,
            prob_profitable,
            float(mdd.mean()),
        )

        return {
            "n_simulations":       self.n_simulations,
            "initial_capital":     init_cap,
            "percentiles": {
                "p5":   round(p5,  2),
                "p25":  round(p25, 2),
                "p50":  round(p50, 2),
                "p75":  round(p75, 2),
                "p95":  round(p95, 2),
            },
            "returns_pct": {
                "p5":   round((p5  / init_cap - 1) * 100, 2),
                "p25":  round((p25 / init_cap - 1) * 100, 2),
                "p50":  round((p50 / init_cap - 1) * 100, 2),
                "p75":  round((p75 / init_cap - 1) * 100, 2),
                "p95":  round((p95 / init_cap - 1) * 100, 2),
            },
            "prob_profitable_pct": round(prob_profitable, 2),
            "avg_max_drawdown_pct": round(float(mdd.mean()), 2),
            "worst_max_drawdown_pct": round(float(mdd.max()), 2),
            "paths_sample": [p[::max(1, len(p)//50)] for p in paths[:10]],  # 10 próbek dla wykresu
        }
