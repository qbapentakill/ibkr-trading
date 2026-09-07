"""
MarketDataService – zarządza danymi rynkowymi.

Źródło danych: yfinance (darmowe, 15-min opóźnienie)
Zlecenia: Alpaca Paper Trading (przez connector)
"""
from __future__ import annotations

import asyncio
from datetime import datetime, timedelta
from typing import Optional

import pandas as pd
import ta as ta_lib
import numpy as np

from config.settings import get_settings
from core.ibkr_connector import IBKRConnector
from core.logger import get_logger
from core.models import Bar, Quote
from core.shared_state import shared_state

log = get_logger(__name__)

# Mapowanie timeframe → yfinance interval + period
TIMEFRAME_YFINANCE = {
    "1m":  ("1m",  "7d"),
    "5m":  ("5m",  "60d"),
    "15m": ("15m", "60d"),
    "1h":  ("1h",  "730d"),
    "4h":  ("1h",  "730d"),   # yfinance nie ma 4h, używamy 1h
    "1d":  ("1d",  "2y"),
}

# Co ile minut odświeżać dane (yfinance)
REFRESH_INTERVAL_MIN = 5


class MarketDataService:
    def __init__(self, connector: IBKRConnector) -> None:
        self._connector  = connector
        self._settings   = get_settings()
        self._bar_cache: dict[str, dict[str, pd.DataFrame]] = {}
        self._quotes:    dict[str, Quote] = {}
        self._quote_lock = asyncio.Lock()
        self._last_refresh: dict[str, datetime] = {}

    # ──────────────────────────────────────────────────────────────────────────
    # Publiczne API
    # ──────────────────────────────────────────────────────────────────────────

    async def start(self, symbols: list[str]) -> None:
        """Startuje serwis — ładuje dane z Polygon/Alpaca dla wszystkich symboli."""
        log.info("📡 MarketDataService: ładuję dane dla {} symboli…", len(symbols))
        for symbol in symbols:
            self._connector.subscribe_quotes(symbol, self._on_quote)
            if self._connector._is_crypto(symbol) and not self._connector._demo_mode:
                # Krypto — ładuj z Alpaca
                for tf in ("1h", "4h", "1d"):
                    try:
                        await self._get_crypto_bars_df(symbol, tf, 200)
                    except Exception:
                        if symbol not in self._bar_cache:
                            self._bar_cache[symbol] = {}
                        self._bar_cache[symbol][tf] = self._make_demo_df(symbol, 200)
            else:
                # Akcje/ETF — ładuj z Polygon tylko kluczowe TF
                for tf in ("15m", "1h", "1d"):
                    await self._load_bars_yfinance(symbol, tf)
        log.info("✅ MarketDataService uruchomiony dla {} symboli", len(symbols))
        asyncio.create_task(self._refresh_loop(symbols))

    async def get_bars(
        self, symbol: str, timeframe: str = "1h", limit: int = 200
    ) -> pd.DataFrame:
        # Dla krypto używaj Alpaca Crypto API
        if self._connector._is_crypto(symbol) and not self._connector._demo_mode:
            return await self._get_crypto_bars_df(symbol, timeframe, limit)

        # Dla GPW/LSE używaj Polygon z odpowiednim formatem tickera
        if self._connector._is_gpw(symbol) or self._connector._is_lse(symbol):
            return await self._get_foreign_bars_df(symbol, timeframe, limit)

        df = self._bar_cache.get(symbol, {}).get(timeframe)
        if df is None or df.empty:
            await self._load_bars_yfinance(symbol, timeframe)
            df = self._bar_cache.get(symbol, {}).get(timeframe, pd.DataFrame())
        if df.empty:
            return df
        df = df.tail(limit).copy()
        df = self._add_indicators(df)
        return df

    async def _get_foreign_bars_df(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Pobiera świece GPW/LSE z Polygon.io."""
        cached = self._bar_cache.get(symbol, {}).get(timeframe)
        if cached is not None and not cached.empty:
            return cached.tail(limit).copy()

        try:
            df = await asyncio.get_event_loop().run_in_executor(
                None, self._fetch_yfinance, symbol, timeframe
            )
            if df is None or df.empty:
                df = self._make_demo_df(symbol, limit)
            if symbol not in self._bar_cache:
                self._bar_cache[symbol] = {}
            self._bar_cache[symbol][timeframe] = df
            return df.tail(limit).copy()
        except Exception as exc:
            log.debug("Foreign bars error {}: {}", symbol, exc)
            return self._make_demo_df(symbol, limit)

    async def _get_crypto_bars_df(self, symbol: str, timeframe: str, limit: int) -> pd.DataFrame:
        """Pobiera świece krypto z Alpaca i konwertuje na DataFrame."""
        # Mapuj timeframe → duration
        duration_map = {"1m":"2 D","5m":"7 D","15m":"14 D","1h":"30 D","4h":"60 D","1d":"365 D"}
        tf_size_map  = {"1m":"1 min","5m":"5 mins","15m":"15 mins","1h":"1 hour","4h":"4 hours","1d":"1 day"}
        duration = duration_map.get(timeframe, "30 D")
        bar_size = tf_size_map.get(timeframe, "1 hour")

        # Cache
        cache_key = f"{symbol}/{timeframe}"
        cached = self._bar_cache.get(symbol, {}).get(timeframe)
        if cached is not None and not cached.empty:
            return cached.tail(limit).copy()

        try:
            bars = await self._connector.get_crypto_bars(symbol, bar_size, duration)
            if not bars:
                return self._make_demo_df(symbol, limit)
            import pandas as pd
            rows = [{"open":b.open,"high":b.high,"low":b.low,
                     "close":b.close,"volume":b.volume} for b in bars]
            idx = [b.timestamp for b in bars]
            df  = pd.DataFrame(rows, index=idx)
            df  = self._add_indicators(df)
            if symbol not in self._bar_cache:
                self._bar_cache[symbol] = {}
            self._bar_cache[symbol][timeframe] = df
            return df.tail(limit).copy()
        except Exception as exc:
            log.debug("Krypto bars error {}: {}", symbol, exc)
            return self._make_demo_df(symbol, limit)

    async def get_quote(self, symbol: str) -> Optional[Quote]:
        # Dla krypto używaj Alpaca Crypto API
        if self._connector._is_crypto(symbol) and not self._connector._demo_mode:
            try:
                q = await self._connector.get_crypto_quote(symbol)
                if q and q.last > 0:
                    async with self._quote_lock:
                        self._quotes[symbol] = q
                    return q
            except Exception:
                pass

        async with self._quote_lock:
            q = self._quotes.get(symbol)
        if q is None:
            q = await self._fetch_quote_yfinance(symbol)
            async with self._quote_lock:
                self._quotes[symbol] = q
        return q

    async def get_latest_price(self, symbol: str) -> float:
        q = await self.get_quote(symbol)
        return q.last if q else 0.0

    # ──────────────────────────────────────────────────────────────────────────
    # yfinance loader
    # ──────────────────────────────────────────────────────────────────────────

    async def _load_bars_yfinance(self, symbol: str, timeframe: str) -> None:
        """Pobiera świece z yfinance w tle (nie blokuje event loop)."""
        try:
            df = await asyncio.get_event_loop().run_in_executor(
                None, self._fetch_yfinance, symbol, timeframe
            )
            if df is None or df.empty:
                log.debug("yfinance: brak danych {}/{} — używam demo", symbol, timeframe)
                df = self._make_demo_df(symbol, 200)

            if symbol not in self._bar_cache:
                self._bar_cache[symbol] = {}
            self._bar_cache[symbol][timeframe] = df
            self._last_refresh[f"{symbol}/{timeframe}"] = datetime.utcnow()
            log.debug("Załadowano {} świec {}/{}", len(df), symbol, timeframe)

        except Exception as exc:
            log.debug("Błąd yfinance {}/{}: {} — demo", symbol, timeframe, exc)
            if symbol not in self._bar_cache:
                self._bar_cache[symbol] = {}
            if timeframe not in self._bar_cache[symbol]:
                self._bar_cache[symbol][timeframe] = self._make_demo_df(symbol, 200)

    def _fetch_yfinance(self, symbol: str, timeframe: str) -> pd.DataFrame:
        """Pobiera dane historyczne z Polygon.io REST API."""
        import requests
        import datetime as dt

        tf_map = {
            "1m":  (1,  "minute", 7),
            "5m":  (5,  "minute", 30),
            "15m": (15, "minute", 30),
            "1h":  (1,  "hour",   730),
            "4h":  (4,  "hour",   730),
            "1d":  (1,  "day",    730),
        }
        mult, span, days = tf_map.get(timeframe, (1, "hour", 180))
        end   = dt.date.today().isoformat()
        start = (dt.date.today() - dt.timedelta(days=days)).isoformat()

        try:
            from config.settings import get_settings
            key = get_settings().polygon_api_key
            url = (
                f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/"
                f"{mult}/{span}/{start}/{end}"
                f"?adjusted=true&sort=asc&limit=1000&apiKey={key}"
            )
            r       = requests.get(url, timeout=20)
            results = r.json().get("results", []) if r.status_code == 200 else []
            if not results:
                return pd.DataFrame()

            df = pd.DataFrame(results)
            df = df.rename(columns={"o":"open","h":"high","l":"low",
                                    "c":"close","v":"volume","t":"timestamp"})
            df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms", utc=True).dt.tz_localize(None)
            df = df.set_index("timestamp")[["open","high","low","close","volume"]].sort_index()
            log.debug("Polygon: {} świec {}/{}", len(df), symbol, timeframe)
            return df

        except Exception as exc:
            log.debug("Polygon {}/{}: {}", symbol, timeframe, exc)
            return pd.DataFrame()

    async def _fetch_quote_yfinance(self, symbol: str) -> Quote:
        """Pobiera aktualną cenę z Polygon.io."""
        try:
            import requests
            from config.settings import get_settings
            key = get_settings().polygon_api_key
            r   = requests.get(
                f"https://api.polygon.io/v2/last/trade/{symbol}?apiKey={key}",
                timeout=10,
            )
            if r.status_code == 200:
                price = float(r.json().get("results", {}).get("p", 0))
                if price > 0:
                    return Quote(symbol=symbol, bid=price-0.01, ask=price+0.01,
                                 last=price, volume=1_000_000)
        except Exception:
            pass

        # Fallback — ostatnia zamknięta cena z cache
        df = self._bar_cache.get(symbol, {}).get("1h")
        if df is not None and not df.empty:
            price = float(df["close"].iloc[-1])
            return Quote(symbol=symbol, bid=price-0.01, ask=price+0.01,
                         last=price, volume=1_000_000)

        return self._connector._demo_quote(symbol)

    async def _refresh_loop(self, symbols: list[str]) -> None:
        """Odświeża dane co REFRESH_INTERVAL_MIN minut."""
        while True:
            await asyncio.sleep(REFRESH_INTERVAL_MIN * 60)
            log.debug("🔄 Odświeżam dane rynkowe z yfinance…")
            for symbol in symbols:
                # Odświeżaj tylko najważniejsze timeframe'y
                for tf in ("5m", "15m", "1h"):
                    await self._load_bars_yfinance(symbol, tf)
                # Zaktualizuj quote
                q = await self._fetch_quote_yfinance(symbol)
                async with self._quote_lock:
                    self._quotes[symbol] = q

    # ──────────────────────────────────────────────────────────────────────────
    # Demo fallback
    # ──────────────────────────────────────────────────────────────────────────

    def _make_demo_df(self, symbol: str, n: int = 200) -> pd.DataFrame:
        """Generuje syntetyczne dane gdy yfinance niedostępny."""
        import random
        base = {"AAPL": 175, "TSLA": 245, "NVDA": 480, "SPY": 445,
                "QQQ": 375, "MSFT": 420, "AMZN": 185, "META": 510,
                "AMD": 165, "COIN": 225}.get(symbol, 100)
        price = float(base)
        rows, ts = [], datetime.utcnow() - timedelta(hours=n)
        for _ in range(n):
            o = round(price, 2)
            c = round(price + random.uniform(-2, 2), 2)
            h = round(max(o, c) + random.uniform(0, 1), 2)
            l = round(min(o, c) - random.uniform(0, 1), 2)
            rows.append({"open": o, "high": h, "low": l, "close": c,
                         "volume": random.randint(1000, 50000)})
            price = c
            ts += timedelta(hours=1)
        idx = pd.date_range(end=datetime.utcnow(), periods=n, freq="1h")
        return pd.DataFrame(rows, index=idx)

    async def _on_quote(self, quote: Quote) -> None:
        async with self._quote_lock:
            self._quotes[quote.symbol] = quote

    def _add_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        """Dodaje kompletny zestaw wskaźników technicznych."""
        if len(df) < 5:
            return df

        close = df["close"]
        high  = df["high"]
        low   = df["low"]
        vol   = df["volume"]
        n     = len(df)

        # ── EMA ───────────────────────────────────────────────────────────────
        df["ema_3"]   = ta_lib.trend.ema_indicator(close, window=min(3,   n))
        df["ema_8"]   = ta_lib.trend.ema_indicator(close, window=min(8,   n))
        df["ema_9"]   = ta_lib.trend.ema_indicator(close, window=min(9,   n))
        df["ema_21"]  = ta_lib.trend.ema_indicator(close, window=min(21,  n))
        df["ema_50"]  = ta_lib.trend.ema_indicator(close, window=min(50,  n))
        df["ema_200"] = ta_lib.trend.ema_indicator(close, window=min(200, n))
        df["sma_20"]  = ta_lib.trend.sma_indicator(close, window=min(20,  n))

        # ── RSI ───────────────────────────────────────────────────────────────
        rsi_window = min(14, max(2, n - 1))
        if n >= rsi_window + 1:
            try:
                df["rsi_14"] = ta_lib.momentum.rsi(close, window=rsi_window)
            except Exception:
                df["rsi_14"] = 50.0
        else:
            df["rsi_14"] = 50.0

        # ── MACD ──────────────────────────────────────────────────────────────
        if n >= 26:
            macd_obj = ta_lib.trend.MACD(close)
            df["macd"]        = macd_obj.macd()
            df["macd_signal"] = macd_obj.macd_signal()
            df["macd_hist"]   = macd_obj.macd_diff()
        else:
            df["macd"] = df["macd_signal"] = df["macd_hist"] = 0.0

        # ── Bollinger Bands ───────────────────────────────────────────────────
        bb_w = min(20, n)
        bb_obj = ta_lib.volatility.BollingerBands(close, window=bb_w, window_dev=2)
        df["bb_lower"] = bb_obj.bollinger_lband()
        df["bb_mid"]   = bb_obj.bollinger_mavg()
        df["bb_upper"] = bb_obj.bollinger_hband()
        df["bb_width"] = (df["bb_upper"] - df["bb_lower"]) / (df["bb_mid"] + 1e-9)
        df["bb_pct"]   = bb_obj.bollinger_pband()

        # ── ATR ───────────────────────────────────────────────────────────────
        atr_window = min(14, max(2, n - 1))
        try:
            df["atr_14"] = ta_lib.volatility.average_true_range(high, low, close, window=atr_window)
        except Exception:
            df["atr_14"] = (high - low).mean()

        # ── ADX ───────────────────────────────────────────────────────────────
        adx_window = min(14, max(2, n // 3))
        if n >= adx_window * 3:
            try:
                df["adx"]    = ta_lib.trend.adx(high, low, close, window=adx_window)
                df["di_pos"] = ta_lib.trend.adx_pos(high, low, close, window=adx_window)
                df["di_neg"] = ta_lib.trend.adx_neg(high, low, close, window=adx_window)
            except Exception:
                df["adx"] = df["di_pos"] = df["di_neg"] = 0.0
        else:
            df["adx"] = df["di_pos"] = df["di_neg"] = 0.0

        # ── Z-score ───────────────────────────────────────────────────────────
        roll_w = min(20, n)
        rolling_mean = close.rolling(roll_w).mean()
        rolling_std  = close.rolling(roll_w).std()
        df["zscore"] = (close - rolling_mean) / (rolling_std + 1e-9)

        # ── Volume ────────────────────────────────────────────────────────────
        df["vol_sma_20"] = vol.rolling(min(20, n)).mean()
        df["vol_ratio"]  = vol / (df["vol_sma_20"] + 1e-9)

        # ── Support / Resistance ──────────────────────────────────────────────
        df["resistance_20"] = high.rolling(min(20, n)).max()
        df["support_20"]    = low.rolling(min(20, n)).min()

        return df

    def get_zscore(self, symbol: str, timeframe: str = "1h") -> Optional[float]:
        df = self._bar_cache.get(symbol, {}).get(timeframe)
        if df is None or df.empty:
            return None
        zscore_col = "zscore"
        rolling_mean = df["close"].rolling(20).mean()
        rolling_std  = df["close"].rolling(20).std()
        zscore = (df["close"] - rolling_mean) / (rolling_std + 1e-9)
        return float(zscore.iloc[-1])
