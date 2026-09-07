"""
CryptoDataService — darmowe publiczne API dla danych krypto.

Źródła (bez klucza API):
1. CoinGecko Keyless API — ceny, market cap, volume, zmiana 24h
2. CoinCap API — ceny live
3. Binance Public API — ceny i wolumeny (najszybsze)

Użycie:
    svc = CryptoDataService()
    price = await svc.get_price("BTC")
    data  = await svc.get_market_data(["BTC","ETH","SOL"])
"""
from __future__ import annotations

import asyncio
from typing import Optional
from core.logger import get_logger

log = get_logger(__name__)

# Mapowanie ticker → CoinGecko ID
COINGECKO_IDS = {
    "BTC":   "bitcoin",
    "ETH":   "ethereum",
    "SOL":   "solana",
    "BNB":   "binancecoin",
    "XRP":   "ripple",
    "ADA":   "cardano",
    "AVAX":  "avalanche-2",
    "DOT":   "polkadot",
    "LINK":  "chainlink",
    "UNI":   "uniswap",
    "MATIC": "matic-network",
    "DOGE":  "dogecoin",
    "SHIB":  "shiba-inu",
    "LTC":   "litecoin",
    "BCH":   "bitcoin-cash",
    "ATOM":  "cosmos",
    "NEAR":  "near",
    "APT":   "aptos",
    "ARB":   "arbitrum",
    "OP":    "optimism",
    "INJ":   "injective-protocol",
    "PEPE":  "pepe",
    "WIF":   "dogwifcoin",
    "BONK":  "bonk",
    "TIA":   "celestia",
    "SUI":   "sui",
    "TON":   "the-open-network",
    "RNDR":  "render-token",
    "FIL":   "filecoin",
    "ICP":   "internet-computer",
}

# Mapowanie ticker → Binance symbol
BINANCE_SYMBOLS = {k: f"{k}USDT" for k in COINGECKO_IDS.keys()}


class CryptoDataService:
    """Agreguje dane krypto z wielu darmowych źródeł."""

    def __init__(self) -> None:
        self._cache: dict[str, dict] = {}

    async def get_price(self, ticker: str) -> float:
        """Pobiera aktualną cenę — próbuje Binance, potem CoinGecko."""
        data = await self.get_market_data([ticker])
        return data.get(ticker, {}).get("price", 0.0)

    async def get_market_data(self, tickers: list[str]) -> dict[str, dict]:
        """
        Pobiera pełne dane rynkowe dla listy tickerów.
        Zwraca: {ticker: {price, change_24h, volume_24h, market_cap, high_24h, low_24h}}
        """
        results = {}

        # Próba 1 — Binance (najszybsze, brak limitu dla publicznych)
        binance_data = await self._fetch_binance(tickers)
        results.update(binance_data)

        # Dla brakujących — CoinGecko
        missing = [t for t in tickers if t not in results or not results[t].get("price")]
        if missing:
            cg_data = await self._fetch_coingecko(missing)
            results.update(cg_data)

        # Dla nadal brakujących — CoinCap
        still_missing = [t for t in tickers if t not in results or not results[t].get("price")]
        if still_missing:
            cc_data = await self._fetch_coincap(still_missing)
            results.update(cc_data)

        return results

    # ── Binance Public API ────────────────────────────────────────────────────

    async def _fetch_binance(self, tickers: list[str]) -> dict[str, dict]:
        """Binance 24hr ticker — bez klucza API."""
        import aiohttp
        results = {}
        try:
            async with aiohttp.ClientSession() as session:
                # Pobierz wszystkie 24h tickery naraz
                async with session.get(
                    "https://api.binance.com/api/v3/ticker/24hr",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as r:
                    if r.status == 200:
                        all_tickers = await r.json()
                        ticker_map  = {t["symbol"]: t for t in all_tickers}

                        for tick in tickers:
                            bin_sym = BINANCE_SYMBOLS.get(tick.upper())
                            if bin_sym and bin_sym in ticker_map:
                                t = ticker_map[bin_sym]
                                results[tick] = {
                                    "price":      float(t.get("lastPrice", 0)),
                                    "change_24h": float(t.get("priceChangePercent", 0)),
                                    "volume_24h": float(t.get("quoteVolume", 0)),
                                    "high_24h":   float(t.get("highPrice", 0)),
                                    "low_24h":    float(t.get("lowPrice", 0)),
                                    "market_cap": 0,
                                    "source":     "Binance",
                                }
        except Exception as exc:
            log.debug("Binance fetch error: {}", exc)
        return results

    # ── CoinGecko Keyless API ─────────────────────────────────────────────────

    async def _fetch_coingecko(self, tickers: list[str]) -> dict[str, dict]:
        """CoinGecko Keyless Public API — bez klucza."""
        import aiohttp
        results = {}
        ids = [COINGECKO_IDS[t] for t in tickers if t in COINGECKO_IDS]
        if not ids:
            return results
        try:
            ids_str = ",".join(ids)
            url = (
                f"https://api.coingecko.com/api/v3/simple/price"
                f"?ids={ids_str}&vs_currencies=usd"
                f"&include_24hr_change=true&include_24hr_vol=true"
                f"&include_market_cap=true"
            )
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    url,
                    headers={"accept": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=8)
                ) as r:
                    if r.status == 200:
                        data = await r.json()
                        # Odwróć mapowanie ID → ticker
                        id_to_ticker = {v: k for k, v in COINGECKO_IDS.items()}
                        for cg_id, vals in data.items():
                            ticker = id_to_ticker.get(cg_id)
                            if ticker and ticker in tickers:
                                results[ticker] = {
                                    "price":      float(vals.get("usd", 0)),
                                    "change_24h": float(vals.get("usd_24h_change", 0)),
                                    "volume_24h": float(vals.get("usd_24h_vol", 0)),
                                    "market_cap": float(vals.get("usd_market_cap", 0)),
                                    "high_24h":   0,
                                    "low_24h":    0,
                                    "source":     "CoinGecko",
                                }
        except Exception as exc:
            log.debug("CoinGecko fetch error: {}", exc)
        return results

    # ── CoinCap API ───────────────────────────────────────────────────────────

    async def _fetch_coincap(self, tickers: list[str]) -> dict[str, dict]:
        """CoinCap Public API — bez klucza."""
        import aiohttp
        results = {}
        try:
            async with aiohttp.ClientSession() as session:
                for ticker in tickers:
                    coin_id = ticker.lower()
                    async with session.get(
                        f"https://api.coincap.io/v2/assets/{coin_id}",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as r:
                        if r.status == 200:
                            data = (await r.json()).get("data", {})
                            price = float(data.get("priceUsd", 0) or 0)
                            if price > 0:
                                results[ticker] = {
                                    "price":      price,
                                    "change_24h": float(data.get("changePercent24Hr", 0) or 0),
                                    "volume_24h": float(data.get("volumeUsd24Hr", 0) or 0),
                                    "market_cap": float(data.get("marketCapUsd", 0) or 0),
                                    "high_24h":   0,
                                    "low_24h":    0,
                                    "source":     "CoinCap",
                                }
        except Exception as exc:
            log.debug("CoinCap fetch error: {}", exc)
        return results

    async def get_trending(self) -> list[dict]:
        """Pobiera trending coins z CoinGecko."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/search/trending",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as r:
                    if r.status == 200:
                        data  = await r.json()
                        coins = data.get("coins", [])
                        return [
                            {
                                "name":   c["item"]["name"],
                                "symbol": c["item"]["symbol"].upper(),
                                "rank":   c["item"]["market_cap_rank"],
                                "thumb":  c["item"]["thumb"],
                            }
                            for c in coins[:7]
                        ]
        except Exception as exc:
            log.debug("CoinGecko trending error: {}", exc)
        return []

    async def get_global_stats(self) -> dict:
        """Globalne statystyki rynku krypto."""
        import aiohttp
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    "https://api.coingecko.com/api/v3/global",
                    timeout=aiohttp.ClientTimeout(total=5)
                ) as r:
                    if r.status == 200:
                        data = (await r.json()).get("data", {})
                        return {
                            "total_market_cap_usd":  data.get("total_market_cap", {}).get("usd", 0),
                            "total_volume_24h_usd":  data.get("total_volume", {}).get("usd", 0),
                            "btc_dominance":         data.get("market_cap_percentage", {}).get("btc", 0),
                            "eth_dominance":         data.get("market_cap_percentage", {}).get("eth", 0),
                            "active_coins":          data.get("active_cryptocurrencies", 0),
                            "market_cap_change_24h": data.get("market_cap_change_percentage_24h_usd", 0),
                        }
        except Exception as exc:
            log.debug("CoinGecko global stats error: {}", exc)
        return {}


# Singleton
_crypto_svc: Optional[CryptoDataService] = None

def get_crypto_service() -> CryptoDataService:
    global _crypto_svc
    if _crypto_svc is None:
        _crypto_svc = CryptoDataService()
    return _crypto_svc
