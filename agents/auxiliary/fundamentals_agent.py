"""
FundamentalsAgent – bot wyliczający wskaźniki fundamentalne.

Wylicza dla każdego symbolu:
  - P/E Ratio        (cena / zysk na akcję)
  - Forward P/E      (cena / prognozowany przyszły zysk)
  - PEG Ratio        (P/E / stopa wzrostu EPS)
  - P/B Ratio        (cena / wartość księgowa)
  - EV/EBITDA        (wartość przedsiębiorstwa / EBITDA)
  - Debt/Equity      (zadłużenie / kapitał własny)
  - ROE              (zwrot z kapitału własnego)
  - Dividend Yield   (stopa dywidendy)
  - Market Cap       (kapitalizacja rynkowa)

Interpretacja wskaźników:
  P/E < 15   → niedowartościowany
  P/E 15-25  → uczciwa wycena
  P/E > 25   → przewartościowany (ale tech często wyżej)
  PEG < 1    → akcja tania względem wzrostu
  PEG 1-2    → uczciwa wycena
  PEG > 2    → droga względem wzrostu
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

from agents.base_agent import BaseAgent
from core.models import AgentName, TradeSignal, SignalDirection
from core.logger import get_logger
from core.shared_state import shared_state

log = get_logger(__name__)


class FundamentalsAgent(BaseAgent):
    """Bot analizujący wskaźniki fundamentalne."""

    DEFAULT_PARAMS = {
        "pe_buy_threshold":    20.0,   # P/E poniżej → sygnał LONG
        "pe_sell_threshold":   35.0,   # P/E powyżej → sygnał SHORT
        "peg_buy_threshold":   1.0,    # PEG poniżej → sygnał LONG
        "peg_sell_threshold":  2.5,    # PEG powyżej → sygnał SHORT
        "min_roe":             10.0,   # min ROE% żeby rozważyć LONG
    }

    def __init__(self, connector, market_data, bus, symbols, interval_sec=3600):
        super().__init__(
            name        = AgentName.RESEARCH_AGENT,
            connector   = connector,
            market_data = market_data,
            bus         = bus,
            symbols     = symbols,
            interval_sec= interval_sec,
        )
        self._fundamentals_cache: dict[str, dict] = {}
        self._last_fetch: dict[str, float] = {}   # symbol → timestamp

    async def analyze(self, symbol: str) -> Optional[TradeSignal]:
        import time
        params = {**self.DEFAULT_PARAMS, **self._get_config().params}

        # Ogranicz do jednego symbolu co 5 minut żeby nie bombardować Yahoo
        last = self._last_fetch.get(symbol, 0)
        if time.time() - last < 300:
            return None
        self._last_fetch[symbol] = time.time()

        # Pobierz dane fundamentalne
        data = await asyncio.get_event_loop().run_in_executor(
            None, self._fetch_fundamentals, symbol
        )

        if not data or data.get("error"):
            return None

        # Zapisz do cache i shared_state
        self._fundamentals_cache[symbol] = data
        if not hasattr(shared_state, "fundamentals"):
            shared_state.fundamentals = {}
        shared_state.fundamentals[symbol] = data

        # Generuj sygnał na podstawie wskaźników
        return self._evaluate(symbol, data, params)

    def _fetch_fundamentals(self, symbol: str) -> dict:
        """Pobiera dane z Polygon.io (główne) + yfinance (fallback)."""
        import requests as _req
        import time, warnings, logging

        logging.getLogger("yfinance").setLevel(logging.CRITICAL)
        warnings.filterwarnings("ignore")

        info = {}

        # ── Próba 1: Polygon.io Ticker Details ────────────────────────────────
        try:
            from config.settings import get_settings
            key = get_settings().polygon_api_key
            if key:
                r = _req.get(
                    f"https://api.polygon.io/v3/reference/tickers/{symbol}?apiKey={key}",
                    timeout=8
                )
                if r.status_code == 200:
                    results = r.json().get("results", {})
                    branding = results.get("branding", {})
                    info["shortName"]     = results.get("name", symbol)
                    info["sector"]        = results.get("sic_description", "N/A")
                    info["marketCap"]     = results.get("market_cap", 0)
                    info["totalEmployees"]= results.get("total_employees", 0)
                    info["description"]   = results.get("description", "")

                # Pobierz aktualną cenę
                rp = _req.get(
                    f"https://api.polygon.io/v2/last/trade/{symbol}?apiKey={key}",
                    timeout=5
                )
                if rp.status_code == 200:
                    info["currentPrice"] = float(rp.json().get("results", {}).get("p", 0))

                # Pobierz dane finansowe z Polygon Financials
                rf = _req.get(
                    f"https://api.polygon.io/vX/reference/financials?ticker={symbol}&limit=1&apiKey={key}",
                    timeout=8
                )
                if rf.status_code == 200:
                    fin_results = rf.json().get("results", [])
                    if fin_results:
                        fin = fin_results[0]
                        ic  = fin.get("financials", {}).get("income_statement", {})
                        bs  = fin.get("financials", {}).get("balance_sheet", {})
                        cf  = fin.get("financials", {}).get("cash_flow_statement", {})
                        info["totalRevenue"]           = ic.get("revenues", {}).get("value", 0)
                        info["netIncomeToCommon"]       = ic.get("net_income_loss", {}).get("value", 0)
                        info["totalDebt"]               = bs.get("long_term_debt", {}).get("value", 0)
                        info["totalStockholderEquity"]  = bs.get("equity", {}).get("value", 1)
        except Exception:
            pass

        # ── Próba 2: yfinance jako uzupełnienie ───────────────────────────────
        if not info.get("currentPrice") or not info.get("trailingEps"):
            try:
                import yfinance as yf
                time.sleep(0.5)
                t = yf.Ticker(symbol)
                try:
                    yf_info = t.info
                    # Uzupełnij brakujące dane
                    for key in ["trailingEps","forwardEps","bookValue","ebitda",
                                "enterpriseValue","earningsGrowth","revenueGrowth",
                                "dividendYield","sharesOutstanding","currentPrice",
                                "regularMarketPrice","shortName","sector"]:
                        if key not in info or not info.get(key):
                            info[key] = yf_info.get(key)
                except Exception:
                    pass
            except Exception:
                pass

        # ── Wylicz wskaźniki ──────────────────────────────────────────────────
        try:
            price         = info.get("currentPrice") or info.get("regularMarketPrice") or 0
            eps           = info.get("trailingEps", 0) or 0
            forward_eps   = info.get("forwardEps", 0) or 0
            book_value    = info.get("bookValue", 0) or 0
            ebitda        = info.get("ebitda", 0) or 0
            enterprise_val= info.get("enterpriseValue", 0) or 0
            total_debt    = info.get("totalDebt", 0) or 0
            equity        = info.get("totalStockholderEquity") or info.get("bookValue", 1) or 1
            net_income    = info.get("netIncomeToCommon", 0) or 0
            revenue       = info.get("totalRevenue", 0) or 0
            shares        = info.get("sharesOutstanding", 1) or 1
            dividend      = info.get("dividendYield", 0) or 0
            market_cap    = info.get("marketCap", 0) or 0
            eps_growth    = info.get("earningsGrowth") or info.get("revenueGrowth", 0) or 0
            sector        = info.get("sector", "N/A")
            company       = info.get("shortName", symbol)

            # ── Wylicz wskaźniki ──────────────────────────────────────────────

            # P/E Ratio
            pe = round(price / eps, 2) if eps and eps > 0 and price else None

            # Forward P/E
            forward_pe = round(price / forward_eps, 2) if forward_eps and forward_eps > 0 and price else None

            # PEG Ratio = P/E / roczny wzrost EPS (%)
            peg = None
            if pe and eps_growth and eps_growth > 0:
                growth_pct = eps_growth * 100
                peg = round(pe / growth_pct, 2) if growth_pct > 0 else None

            # P/B Ratio
            pb = round(price / book_value, 2) if book_value and book_value > 0 and price else None

            # EV/EBITDA
            ev_ebitda = round(enterprise_val / ebitda, 2) if ebitda and ebitda > 0 and enterprise_val else None

            # Debt/Equity
            de = round(total_debt / equity, 2) if equity and equity > 0 else None

            # ROE (Return on Equity) %
            roe = round((net_income / equity) * 100, 1) if equity and equity > 0 and net_income else None

            # Profit Margin %
            margin = round((net_income / revenue) * 100, 1) if revenue and revenue > 0 and net_income else None

            # Interpretacje
            pe_signal    = self._interpret_pe(pe)
            peg_signal   = self._interpret_peg(peg)
            overall      = self._overall_signal(pe, peg, roe)

            return {
                "symbol":       symbol,
                "company":      company,
                "sector":       sector,
                "price":        round(float(price), 2) if price else None,
                "market_cap":   market_cap,
                "market_cap_str": self._format_cap(market_cap),

                # Wskaźniki wyceny
                "pe":           pe,
                "forward_pe":   forward_pe,
                "peg":          peg,
                "pb":           pb,
                "ev_ebitda":    ev_ebitda,

                # Finanse
                "eps":          round(float(eps), 2) if eps else None,
                "forward_eps":  round(float(forward_eps), 2) if forward_eps else None,
                "eps_growth":   round(float(eps_growth) * 100, 1) if eps_growth else None,
                "roe":          roe,
                "de_ratio":     de,
                "profit_margin": margin,
                "dividend_yield": round(float(dividend) * 100, 2) if dividend else 0.0,

                # Interpretacje
                "pe_signal":    pe_signal,
                "peg_signal":   peg_signal,
                "overall":      overall,
                "updated_at":   datetime.utcnow().isoformat(),
            }

        except Exception as exc:
            log.debug("FundamentalsAgent {}: {}", symbol, exc)
            return {"symbol": symbol, "error": str(exc)}

    def _evaluate(self, symbol: str, data: dict, params: dict) -> Optional[TradeSignal]:
        """Generuje sygnał na podstawie wskaźników fundamentalnych."""
        pe       = data.get("pe")
        peg      = data.get("peg")
        roe      = data.get("roe")
        overall  = data.get("overall", "neutral")

        score = 0
        reasons = []

        # P/E scoring
        if pe:
            if pe < params["pe_buy_threshold"]:
                score += 2
                reasons.append(f"P/E={pe} (niedowartościowany < {params['pe_buy_threshold']})")
            elif pe > params["pe_sell_threshold"]:
                score -= 2
                reasons.append(f"P/E={pe} (przewartościowany > {params['pe_sell_threshold']})")
            else:
                reasons.append(f"P/E={pe} (uczciwa wycena)")

        # PEG scoring
        if peg:
            if peg < params["peg_buy_threshold"]:
                score += 3
                reasons.append(f"PEG={peg} (tania względem wzrostu)")
            elif peg > params["peg_sell_threshold"]:
                score -= 2
                reasons.append(f"PEG={peg} (droga względem wzrostu)")

        # ROE scoring
        if roe:
            if roe >= params["min_roe"]:
                score += 1
                reasons.append(f"ROE={roe}% (dobra rentowność)")
            else:
                score -= 1
                reasons.append(f"ROE={roe}% (słaba rentowność)")

        if abs(score) < 2:
            return None

        direction  = SignalDirection.LONG if score > 0 else SignalDirection.SHORT
        confidence = min(0.70, 0.40 + abs(score) * 0.07)

        reasoning = (
            f"FundamentalsAgent {direction.value} | "
            + " | ".join(reasons)
        )

        try:
            from core.models import Bar
            import asyncio
            price = data.get("price") or 100.0
        except Exception:
            price = 100.0

        return TradeSignal(
            agent_name  = self.name,
            symbol      = symbol,
            direction   = direction,
            confidence  = confidence,
            entry_price = price,
            size_pct    = confidence * 30,
            reasoning   = reasoning,
            raw_indicators = {
                "pe": pe, "peg": peg, "roe": roe,
                "forward_pe": data.get("forward_pe"),
            },
            timeframe   = "fundamental",
        )

    # ── Interpretacje ─────────────────────────────────────────────────────────

    def _interpret_pe(self, pe: Optional[float]) -> str:
        if pe is None:     return "brak danych"
        if pe < 0:         return "🔴 ujemne (strata)"
        if pe < 10:        return "🟢 bardzo tanie"
        if pe < 20:        return "🟢 niedowartościowane"
        if pe < 30:        return "🟡 uczciwa wycena"
        if pe < 50:        return "🟠 drogie"
        return             "🔴 mocno przewartościowane"

    def _interpret_peg(self, peg: Optional[float]) -> str:
        if peg is None:  return "brak danych"
        if peg < 0:      return "🔴 ujemny wzrost"
        if peg < 1:      return "🟢 tania względem wzrostu"
        if peg < 2:      return "🟡 uczciwa wycena"
        return           "🔴 droga względem wzrostu"

    def _overall_signal(self, pe, peg, roe) -> str:
        score = 0
        if pe and 0 < pe < 20:  score += 1
        if peg and peg < 1:     score += 2
        if roe and roe > 15:    score += 1
        if pe and pe > 40:      score -= 2
        if peg and peg > 3:     score -= 1
        if score >= 2:   return "bullish"
        if score <= -1:  return "bearish"
        return "neutral"

    def _format_cap(self, cap: float) -> str:
        if not cap: return "N/A"
        if cap > 1e12: return f"${cap/1e12:.1f}T"
        if cap > 1e9:  return f"${cap/1e9:.1f}B"
        if cap > 1e6:  return f"${cap/1e6:.1f}M"
        return f"${cap:,.0f}"
