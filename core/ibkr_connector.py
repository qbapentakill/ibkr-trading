"""
AlpacaConnector – zastępuje IBKRConnector.

Obsługuje:
- Paper Trading przez Alpaca API (domyślnie)
- Real Trading (wymaga alpaca_paper=False w .env)
- Dane historyczne i real-time przez Alpaca Data API
- Składanie zleceń Market/Limit/Stop
- Synchronizację pozycji i rachunku
- Tryb DEMO gdy brak kluczy API
"""
from __future__ import annotations

import asyncio
import random
from datetime import datetime, timedelta
from typing import Callable, Optional

from config.settings import get_settings
from core.logger import get_logger, get_trading_logger
from core.models import (
    AccountSummary,
    Bar,
    OrderRequest,
    OrderResult,
    OrderStatus,
    Position,
    Quote,
)

log  = get_logger(__name__)
tlog = get_trading_logger(__name__)

# Lazy import – alpaca-py opcjonalne
try:
    from alpaca.trading.client import TradingClient
    from alpaca.trading.requests import (
        MarketOrderRequest,
        LimitOrderRequest,
        StopOrderRequest,
        StopLimitOrderRequest,
        GetOrdersRequest,
    )
    from alpaca.trading.enums import OrderSide, TimeInForce, QueryOrderStatus
    from alpaca.data.historical import StockHistoricalDataClient, CryptoHistoricalDataClient
    from alpaca.data.requests import (
        StockBarsRequest, StockLatestQuoteRequest,
        CryptoBarsRequest, CryptoLatestQuoteRequest,
    )
    from alpaca.data.timeframe import TimeFrame, TimeFrameUnit
    ALPACA_AVAILABLE = True
except ImportError:
    ALPACA_AVAILABLE = False
    log.warning("alpaca-py niedostępny – tryb DEMO/offline")


# Mapowanie timeframe string → Alpaca TimeFrame
_TIMEFRAME_MAP = {
    "1 min":   (1,  TimeFrameUnit.Minute)  if ALPACA_AVAILABLE else None,
    "5 mins":  (5,  TimeFrameUnit.Minute)  if ALPACA_AVAILABLE else None,
    "15 mins": (15, TimeFrameUnit.Minute)  if ALPACA_AVAILABLE else None,
    "1 hour":  (1,  TimeFrameUnit.Hour)    if ALPACA_AVAILABLE else None,
    "4 hours": (4,  TimeFrameUnit.Hour)    if ALPACA_AVAILABLE else None,
    "1 day":   (1,  TimeFrameUnit.Day)     if ALPACA_AVAILABLE else None,
}


class IBKRConnectionError(Exception):
    """Brak połączenia z brokerem."""


class IBKRConnector:
    """
    Connector do Alpaca API (zastępuje IBKR).
    Nazwa zachowana dla kompatybilności z resztą systemu.

    Użycie:
        connector = IBKRConnector()
        await connector.connect()
        quote = await connector.get_quote("AAPL")
        await connector.disconnect()
    """

    def __init__(self) -> None:
        self._settings  = get_settings()
        self._connected = False
        self._demo_mode = not ALPACA_AVAILABLE

        self._trading_client: Optional["TradingClient"] = None
        self._data_client:    Optional["StockHistoricalDataClient"] = None
        self._crypto_client:  Optional["CryptoHistoricalDataClient"] = None

        self._positions_cache: dict[str, Position]  = {}
        self._account_cache   = AccountSummary()
        self._quote_callbacks: dict[str, list[Callable[[Quote], None]]] = {}
        self._lock = asyncio.Lock()

    # ──────────────────────────────────────────────────────────────────────────
    # Połączenie
    # ──────────────────────────────────────────────────────────────────────────

    async def connect(self) -> None:
        """Inicjalizuje połączenie z Alpaca API."""
        if self._demo_mode:
            log.warning("alpaca-py niedostępny – tryb DEMO")
            self._connected = True
            self._account_cache = AccountSummary(
                net_liquidation=self._settings.total_capital_usd,
                buying_power=self._settings.total_capital_usd,
                total_cash=self._settings.total_capital_usd,
            )
            return

        api_key    = self._settings.alpaca_api_key
        secret_key = self._settings.alpaca_secret_key

        if not api_key or not secret_key:
            log.warning("⚠️  Brak kluczy Alpaca API – tryb DEMO")
            self._demo_mode = True
            self._connected = True
            return

        try:
            paper = self._settings.alpaca_paper
            self._trading_client = TradingClient(
                api_key    = api_key,
                secret_key = secret_key,
                paper      = paper,
            )
            self._data_client = StockHistoricalDataClient(
                api_key    = api_key,
                secret_key = secret_key,
            )
            # Krypto client — te same klucze
            self._crypto_client = CryptoHistoricalDataClient(
                api_key    = api_key,
                secret_key = secret_key,
            )

            # Weryfikacja połączenia
            account = self._trading_client.get_account()
            self._connected = True

            mode   = "PAPER 📄" if paper else "🔴 REAL"
            equity = float(account.equity) if account.equity else 0.0
            log.info("✅ Połączono z Alpaca {} | Konto: {} | Kapitał: ${:.2f}",
                     mode, str(account.id)[:8] + "…", equity)

            await self._sync_account()
            await self._sync_positions()

        except Exception as exc:
            log.warning("⚠️  Błąd połączenia z Alpaca: {} – tryb DEMO", exc)
            self._demo_mode = True
            self._connected = True
            self._account_cache = AccountSummary(
                net_liquidation=self._settings.total_capital_usd,
                buying_power=self._settings.total_capital_usd,
                total_cash=self._settings.total_capital_usd,
            )

    async def disconnect(self) -> None:
        self._connected = False
        log.info("Rozłączono z Alpaca")

    @property
    def connected(self) -> bool:
        return self._connected

    # ──────────────────────────────────────────────────────────────────────────
    # Market Data
    # ──────────────────────────────────────────────────────────────────────────

    async def get_quote(self, symbol: str) -> Quote:
        """Pobiera aktualną ofertę bid/ask."""
        if self._demo_mode or not self._data_client:
            return self._demo_quote(symbol)

        try:
            req    = StockLatestQuoteRequest(symbol_or_symbols=symbol)
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._data_client.get_stock_latest_quote(req)
            )
            q = result[symbol]
            return Quote(
                symbol=symbol,
                bid=float(q.bid_price or 0),
                ask=float(q.ask_price or 0),
                last=float((q.bid_price + q.ask_price) / 2 if q.bid_price and q.ask_price else 0),
                volume=float(q.bid_size or 0),
            )
        except Exception as exc:
            log.debug("Błąd pobierania quote {}: {}", symbol, exc)
            return self._demo_quote(symbol)

    async def get_historical_bars(
        self,
        symbol:       str,
        bar_size:     str = "1 hour",
        duration:     str = "30 D",
        what_to_show: str = "TRADES",
    ) -> list[Bar]:
        """
        Pobiera historyczne świece z Alpaca.
        bar_size: '1 min', '5 mins', '15 mins', '1 hour', '4 hours', '1 day'
        duration: '1 D', '7 D', '30 D', '1 M', '1 Y'
        """
        if self._demo_mode or not self._data_client:
            return self._demo_bars(symbol, 100)

        try:
            # Przelicz duration na datetime
            end   = datetime.utcnow()
            start = self._duration_to_start(duration, end)

            # Mapuj bar_size → Alpaca TimeFrame
            tf_params = _TIMEFRAME_MAP.get(bar_size)
            if tf_params is None:
                tf_params = (1, TimeFrameUnit.Hour)
            amount, unit = tf_params
            timeframe = TimeFrame(amount, unit)

            req = StockBarsRequest(
                symbol_or_symbols = symbol,
                timeframe         = timeframe,
                start             = start,
                end               = end,
                limit             = 1000,
            )

            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._data_client.get_stock_bars(req)
            )

            bars_df = result.df
            if bars_df.empty:
                log.debug("Brak danych Alpaca dla {} – używam demo", symbol)
                return self._demo_bars(symbol, 100)

            # Resetuj multi-index jeśli potrzeba
            if hasattr(bars_df.index, 'levels'):
                bars_df = bars_df.reset_index(level=0, drop=True)

            bars = []
            for ts, row in bars_df.iterrows():
                bars.append(Bar(
                    timestamp = ts.to_pydatetime() if hasattr(ts, 'to_pydatetime') else ts,
                    open      = float(row.get("open",  0)),
                    high      = float(row.get("high",  0)),
                    low       = float(row.get("low",   0)),
                    close     = float(row.get("close", 0)),
                    volume    = float(row.get("volume", 0)),
                    symbol    = symbol,
                ))
            return bars

        except Exception as exc:
            log.debug("Błąd pobierania świec Alpaca {}: {} – demo", symbol, exc)
            return self._demo_bars(symbol, 100)

    def subscribe_quotes(self, symbol: str, callback: Callable[[Quote], None]) -> None:
        """Rejestruje callback na nowe kwotowania."""
        if symbol not in self._quote_callbacks:
            self._quote_callbacks[symbol] = []
        self._quote_callbacks[symbol].append(callback)

    # ── Krypto ────────────────────────────────────────────────────────────────

    # Symbole GPW (format Polygon: ticker.WAR) i LSE (ticker.XLON)
    GPW_SYMBOLS = {"PKN","PKO","PZU","CDR","ALE","DNP","KGH","JSW","LPP","CCC",
                   "MBK","PEO","ING","SPL","OPL","PGN","TPE","ENA","PGE","ACP","ARLN"}
    LSE_SYMBOLS = {"HSBA","BP","SHEL","GSK","AZN","ULVR","RIO","AAL","BARC","LLOY",
                   "NWG","VOD","BT","IAG","RR","BAE","REL","DGE","CPG","EXPN","LGEN","PRU","STAN"}

    def _is_gpw(self, symbol: str) -> bool:
        return symbol.upper() in self.GPW_SYMBOLS

    def _is_lse(self, symbol: str) -> bool:
        return symbol.upper() in self.LSE_SYMBOLS

    def _polygon_symbol(self, symbol: str) -> str:
        """Konwertuje ticker na format Polygon dla GPW/LSE."""
        s = symbol.upper()
        if self._is_gpw(s):
            return f"{s}:PLN"   # GPW notuje w PLN
        if self._is_lse(s):
            return f"{s}:GBX"   # LSE notuje w groszach brytyjskich (GBX)
        return s
    # Symbole krypto które Alpaca obsługuje (format BTC/USD)
    CRYPTO_SYMBOLS = {
        "BTC","ETH","SOL","BNB","XRP","ADA","AVAX","DOT","LINK","UNI",
        "MATIC","DOGE","LTC","BCH","ATOM","NEAR","APT","SHIB","PEPE",
    }

    def _is_crypto(self, symbol: str) -> bool:
        return symbol.upper() in self.CRYPTO_SYMBOLS
        """Konwertuje BTC → BTC/USD dla Alpaca Crypto API."""
        s = symbol.upper()
        if "/" not in s:
            return f"{s}/USD"
        return s

    async def get_crypto_bars(
        self,
        symbol:   str,
        bar_size: str = "1 hour",
        duration: str = "30 D",
    ) -> list[Bar]:
        """Pobiera historyczne świece krypto z Alpaca."""
        if not self._crypto_client:
            return self._demo_bars(symbol, 100)
        try:
            end   = datetime.utcnow()
            start = self._duration_to_start(duration, end)
            tf_params = _TIMEFRAME_MAP.get(bar_size, (1, TimeFrameUnit.Hour))
            if tf_params is None:
                tf_params = (1, TimeFrameUnit.Hour)
            amount, unit = tf_params
            timeframe = TimeFrame(amount, unit)

            req = CryptoBarsRequest(
                symbol_or_symbols = self._crypto_symbol(symbol),
                timeframe         = timeframe,
                start             = start,
                end               = end,
                limit             = 1000,
            )
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._crypto_client.get_crypto_bars(req)
            )
            bars_df = result.df
            if bars_df.empty:
                return self._demo_bars(symbol, 100)
            if hasattr(bars_df.index, "levels"):
                bars_df = bars_df.reset_index(level=0, drop=True)
            bars = []
            for ts, row in bars_df.iterrows():
                bars.append(Bar(
                    timestamp = ts.to_pydatetime() if hasattr(ts, "to_pydatetime") else ts,
                    open      = float(row.get("open",  0)),
                    high      = float(row.get("high",  0)),
                    low       = float(row.get("low",   0)),
                    close     = float(row.get("close", 0)),
                    volume    = float(row.get("volume", 0)),
                    symbol    = symbol,
                ))
            return bars
        except Exception as exc:
            log.debug("Błąd krypto bars {}: {} — demo", symbol, exc)
            return self._demo_bars(symbol, 100)

    async def get_crypto_quote(self, symbol: str) -> Quote:
        """Pobiera aktualną cenę krypto z Alpaca."""
        if not self._crypto_client:
            return self._demo_quote(symbol)
        try:
            req    = CryptoLatestQuoteRequest(symbol_or_symbols=self._crypto_symbol(symbol))
            result = await asyncio.get_event_loop().run_in_executor(
                None, lambda: self._crypto_client.get_crypto_latest_quote(req)
            )
            sym_key = self._crypto_symbol(symbol)
            q = result.get(sym_key)
            if q:
                mid = (float(q.bid_price or 0) + float(q.ask_price or 0)) / 2
                return Quote(
                    symbol=symbol, bid=float(q.bid_price or 0),
                    ask=float(q.ask_price or 0), last=mid, volume=1_000_000,
                )
        except Exception as exc:
            log.debug("Błąd krypto quote {}: {}", symbol, exc)
        return self._demo_quote(symbol)

    # ──────────────────────────────────────────────────────────────────────────
    # Zlecenia
    # ──────────────────────────────────────────────────────────────────────────

    async def place_order(self, request: OrderRequest) -> OrderResult:
        """Składa zlecenie przez Alpaca API."""
        async with self._lock:
            if self._demo_mode or not self._trading_client:
                return self._demo_order_result(request)

            try:
                from core.models import OrderType, OrderSide as AppOrderSide
                side = OrderSide.BUY if request.side.value == "BUY" else OrderSide.SELL
                tif  = TimeInForce.DAY

                # Fractional shares wymagają DAY, całkowite mogą być GTC
                import datetime as _dt
                now_est = _dt.datetime.utcnow() - _dt.timedelta(hours=4)
                market_open  = now_est.replace(hour=9,  minute=30, second=0)
                market_close = now_est.replace(hour=16, minute=0,  second=0)
                is_market_hours = (market_open <= now_est <= market_close
                                   and now_est.weekday() < 5)

                # Zawsze używaj DAY — fractional shares nie obsługują GTC
                tif = TimeInForce.DAY

                if request.order_type == OrderType.MARKET or not hasattr(request, 'order_type'):
                    order_req = MarketOrderRequest(
                        symbol       = request.symbol,
                        qty          = request.quantity,
                        side         = side,
                        time_in_force= tif,
                    )
                elif request.order_type == OrderType.LIMIT:
                    order_req = LimitOrderRequest(
                        symbol        = request.symbol,
                        qty           = request.quantity,
                        side          = side,
                        time_in_force = tif,
                        limit_price   = request.limit_price,
                    )
                elif request.order_type == OrderType.STOP:
                    order_req = StopOrderRequest(
                        symbol        = request.symbol,
                        qty           = request.quantity,
                        side          = side,
                        time_in_force = tif,
                        stop_price    = request.stop_price,
                    )
                else:
                    order_req = MarketOrderRequest(
                        symbol        = request.symbol,
                        qty           = request.quantity,
                        side          = side,
                        time_in_force = tif,
                    )

                order = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: self._trading_client.submit_order(order_req)
                )

                tlog.info("📤 Alpaca zlecenie | {} {} {} qty={}",
                          request.symbol, request.side.value,
                          getattr(request, 'order_type', 'MARKET'), request.quantity)

                # Mapuj rzeczywisty status Alpaca
                alpaca_status = str(order.status.value) if hasattr(order.status, 'value') else str(order.status)
                status_map = {
                    "filled":            OrderStatus.FILLED,
                    "partially_filled":  OrderStatus.PARTIAL,
                    "new":               OrderStatus.SUBMITTED,
                    "accepted":          OrderStatus.SUBMITTED,
                    "pending_new":       OrderStatus.SUBMITTED,
                    "cancelled":         OrderStatus.CANCELLED,
                    "rejected":          OrderStatus.REJECTED,
                    "expired":           OrderStatus.CANCELLED,
                }
                mapped_status = status_map.get(alpaca_status, OrderStatus.SUBMITTED)

                # Dla paper trading poczekaj chwilę i sprawdź czy wypełnione
                if alpaca_status in ("new", "accepted", "pending_new"):
                    await asyncio.sleep(1.5)
                    try:
                        refreshed = await asyncio.get_event_loop().run_in_executor(
                            None, lambda: self._trading_client.get_order_by_id(order.id)
                        )
                        alpaca_status2 = str(refreshed.status.value) if hasattr(refreshed.status, 'value') else str(refreshed.status)
                        mapped_status  = status_map.get(alpaca_status2, OrderStatus.SUBMITTED)
                        filled_price   = float(refreshed.filled_avg_price or 0)
                        filled_qty     = float(refreshed.filled_qty or 0)
                    except Exception:
                        filled_price = float(order.filled_avg_price or 0)
                        filled_qty   = float(order.filled_qty or 0)
                else:
                    filled_price = float(order.filled_avg_price or 0)
                    filled_qty   = float(order.filled_qty or 0)

                return OrderResult(
                    order_id   = request.id,
                    ibkr_id    = hash(str(order.id)) % 99999,
                    status     = mapped_status,
                    filled_qty = filled_qty,
                    avg_price  = filled_price,
                )

            except Exception as exc:
                log.error("Błąd składania zlecenia Alpaca: {}", exc)
                return OrderResult(
                    order_id  = request.id,
                    status    = OrderStatus.REJECTED,
                    error_msg = str(exc),
                )

    async def cancel_all_orders(self) -> None:
        """Anuluje wszystkie otwarte zlecenia."""
        if self._demo_mode or not self._trading_client:
            log.warning("cancel_all_orders: tryb DEMO")
            return
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._trading_client.cancel_orders
            )
            log.warning("🚨 Anulowano WSZYSTKIE zlecenia Alpaca")
        except Exception as exc:
            log.error("Błąd anulowania zleceń: {}", exc)

    async def close_all_positions(self) -> None:
        """Zamyka wszystkie otwarte pozycje."""
        if self._demo_mode or not self._trading_client:
            self._positions_cache.clear()
            return
        try:
            await asyncio.get_event_loop().run_in_executor(
                None, self._trading_client.close_all_positions
            )
            log.warning("🚨 Zamknięto WSZYSTKIE pozycje Alpaca")
        except Exception as exc:
            log.error("Błąd zamykania pozycji: {}", exc)

    # ──────────────────────────────────────────────────────────────────────────
    # Pozycje i rachunek
    # ──────────────────────────────────────────────────────────────────────────

    async def _sync_positions(self) -> None:
        if self._demo_mode or not self._trading_client:
            return
        try:
            positions = await asyncio.get_event_loop().run_in_executor(
                None, self._trading_client.get_all_positions
            )
            self._positions_cache.clear()
            for p in positions:
                self._positions_cache[p.symbol] = Position(
                    symbol   = p.symbol,
                    quantity = float(p.qty),
                    avg_cost = float(p.avg_entry_price),
                )
            log.info("Zsynchronizowano {} pozycji z Alpaca", len(self._positions_cache))
        except Exception as exc:
            log.error("Błąd synchronizacji pozycji: {}", exc)

    async def _sync_account(self) -> None:
        if self._demo_mode or not self._trading_client:
            # W trybie demo ustaw kapitał z settings
            from config.settings import get_settings
            from core.shared_state import shared_state
            cap = get_settings().total_capital_usd
            self._account_cache = AccountSummary(
                net_liquidation = cap,
                total_cash      = cap,
                buying_power    = cap,
            )
            shared_state.account = self._account_cache
            return
        try:
            acc = await asyncio.get_event_loop().run_in_executor(
                None, self._trading_client.get_account
            )
            self._account_cache = AccountSummary(
                net_liquidation = float(acc.equity or 0),
                total_cash      = float(acc.cash or 0),
                buying_power    = float(acc.buying_power or 0),
                unrealized_pnl  = float(acc.long_market_value or 0) - float(acc.short_market_value or 0),
                realized_pnl    = float(acc.equity or 0) - float(acc.last_equity or 0),
                daily_pnl       = float(acc.equity or 0) - float(acc.last_equity or 0),
            )
            # Zaktualizuj shared_state od razu
            from core.shared_state import shared_state
            shared_state.account = self._account_cache
            log.info("💰 Konto zsynchronizowane: equity=${:.2f} buying_power=${:.2f}",
                     self._account_cache.net_liquidation,
                     self._account_cache.buying_power)
        except Exception as exc:
            log.error("Błąd synchronizacji rachunku: {}", exc)

    async def get_positions(self) -> dict[str, Position]:
        if not self._demo_mode:
            await self._sync_positions()
        return dict(self._positions_cache)

    async def get_account(self) -> AccountSummary:
        if not self._demo_mode:
            await self._sync_account()
        return self._account_cache

    def get_account_values(self) -> dict:
        """Kompatybilność wsteczna."""
        return {
            "NetLiquidation": self._account_cache.net_liquidation,
            "BuyingPower":    self._account_cache.buying_power,
            "TotalCash":      self._account_cache.total_cash,
            "paper":          self._settings.alpaca_paper,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _duration_to_start(self, duration: str, end: datetime) -> datetime:
        """Przelicza duration string ('30 D', '1 Y' itp.) na datetime."""
        parts = duration.strip().split()
        if len(parts) != 2:
            return end - timedelta(days=30)
        amount = int(parts[0])
        unit   = parts[1].upper()
        if unit in ("D",):
            return end - timedelta(days=amount)
        elif unit in ("W",):
            return end - timedelta(weeks=amount)
        elif unit in ("M",):
            return end - timedelta(days=amount * 30)
        elif unit in ("Y",):
            return end - timedelta(days=amount * 365)
        return end - timedelta(days=30)

    def _demo_quote(self, symbol: str) -> Quote:
        base  = {"AAPL": 175, "TSLA": 245, "NVDA": 480, "SPY": 445, "QQQ": 375}.get(symbol, 100)
        price = base + random.uniform(-5, 5)
        return Quote(
            symbol=symbol,
            bid=round(price - 0.01, 2),
            ask=round(price + 0.01, 2),
            last=round(price, 2),
            volume=random.randint(1_000, 100_000),
        )

    def _demo_bars(self, symbol: str, n: int = 100) -> list[Bar]:
        bars  = []
        base  = {"AAPL": 175, "TSLA": 245, "NVDA": 480, "SPY": 445, "QQQ": 375}.get(symbol, 100)
        price = float(base)
        ts    = datetime.utcnow() - timedelta(hours=n)
        for _ in range(n):
            o = round(price, 2)
            c = round(price + random.uniform(-2, 2), 2)
            h = round(max(o, c) + random.uniform(0, 1), 2)
            l = round(min(o, c) - random.uniform(0, 1), 2)
            bars.append(Bar(
                timestamp=ts, open=o, high=h, low=l, close=c,
                volume=random.randint(1000, 50000), symbol=symbol,
            ))
            price = c
            ts   += timedelta(hours=1)
        return bars

    def _demo_order_result(self, request: OrderRequest) -> OrderResult:
        price = getattr(request, 'limit_price', None) or 100.0 + random.uniform(-1, 1)
        tlog.info("[DEMO] Symulowane wypełnienie: {} {} {}",
                  request.symbol, request.side.value, request.quantity)
        return OrderResult(
            order_id   = request.id,
            ibkr_id    = random.randint(10000, 99999),
            status     = OrderStatus.FILLED,
            filled_qty = request.quantity,
            avg_price  = round(price, 2),
            commission = 0.0,
            filled_at  = datetime.utcnow(),
        )
