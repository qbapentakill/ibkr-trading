"""
PaperTradingSession – sesja testowa "na sucho" w czasie rzeczywistym.

Agenci przez X minut podejmują decyzje na danych demo,
a po zakończeniu generowany jest pełny raport:
- Ile zainwestowali
- Dlaczego (reasoning z sygnału)
- Ile zysku przewidywano
- Ile rzeczywiście zarobili/stracili
"""
from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from core.logger import get_logger
from core.models import TradeSignal, SignalDirection

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Modele danych
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class PaperTrade:
    """Pojedyncza transakcja w sesji testowej."""
    trade_id:        str
    agent_name:      str
    symbol:          str
    direction:       str          # LONG / SHORT
    entry_price:     float
    quantity:        float
    entry_time:      datetime
    reasoning:       str
    confidence:      float
    predicted_gain_pct: float     # przewidywany zysk (%)

    exit_price:      Optional[float] = None
    exit_time:       Optional[datetime] = None
    actual_pnl_usd:  Optional[float] = None
    actual_pnl_pct:  Optional[float] = None
    status:          str = "OPEN"  # OPEN / CLOSED / EXPIRED


@dataclass
class SessionReport:
    """Pełny raport po zakończeniu sesji."""
    session_id:      str
    start_time:      datetime
    end_time:        datetime
    duration_min:    float
    initial_capital: float

    total_trades:    int = 0
    winning_trades:  int = 0
    losing_trades:   int = 0
    total_pnl_usd:   float = 0.0
    total_pnl_pct:   float = 0.0
    best_trade_pnl:  float = 0.0
    worst_trade_pnl: float = 0.0

    trades:          list[PaperTrade] = field(default_factory=list)
    agent_stats:     dict = field(default_factory=dict)

    def summary(self) -> dict:
        return {
            "session_id":      self.session_id,
            "duration_min":    round(self.duration_min, 1),
            "initial_capital": self.initial_capital,
            "total_trades":    self.total_trades,
            "winning_trades":  self.winning_trades,
            "losing_trades":   self.losing_trades,
            "win_rate_pct":    round(self.winning_trades / max(self.total_trades, 1) * 100, 1),
            "total_pnl_usd":   round(self.total_pnl_usd, 2),
            "total_pnl_pct":   round(self.total_pnl_pct, 2),
            "best_trade_pnl":  round(self.best_trade_pnl, 2),
            "worst_trade_pnl": round(self.worst_trade_pnl, 2),
            "agent_stats":     self.agent_stats,
            "trades":          [self._trade_to_dict(t) for t in self.trades],
        }

    def _trade_to_dict(self, t: PaperTrade) -> dict:
        return {
            "trade_id":         t.trade_id,
            "agent":            t.agent_name,
            "symbol":           t.symbol,
            "direction":        t.direction,
            "entry_price":      round(t.entry_price, 2),
            "exit_price":       round(t.exit_price, 2) if t.exit_price else None,
            "quantity":         round(t.quantity, 4),
            "entry_time":       t.entry_time.strftime("%H:%M:%S"),
            "exit_time":        t.exit_time.strftime("%H:%M:%S") if t.exit_time else None,
            "reasoning":        t.reasoning,
            "confidence":       round(t.confidence, 2),
            "predicted_gain_pct": round(t.predicted_gain_pct, 2),
            "actual_pnl_usd":   round(t.actual_pnl_usd, 2) if t.actual_pnl_usd is not None else None,
            "actual_pnl_pct":   round(t.actual_pnl_pct, 2) if t.actual_pnl_pct is not None else None,
            "status":           t.status,
        }


# ─────────────────────────────────────────────────────────────────────────────
# Silnik sesji
# ─────────────────────────────────────────────────────────────────────────────

# Bazowe ceny demo (symulowane)
_BASE_PRICES = {
    # ── Mega-cap US tech ──────────────────────────────────────────────────────
    "AAPL": 175.0, "MSFT": 420.0, "NVDA": 480.0, "GOOGL": 175.0,
    "AMZN": 185.0, "META": 510.0, "TSLA": 245.0, "NFLX": 680.0,
    # ── Chips & Semiconductors ────────────────────────────────────────────────
    "AMD":  165.0, "INTC": 35.0,  "QCOM": 175.0, "AVGO": 1350.0,
    "TSM":  155.0, "ASML": 950.0, "ARM":  125.0,  "MU":   110.0,
    "AMAT": 210.0, "LRCX": 900.0, "KLAC": 750.0,
    # ── Software / Cloud ──────────────────────────────────────────────────────
    "CRM":  290.0, "ORCL": 135.0, "SAP":  210.0, "ADBE": 480.0,
    "SNOW": 155.0, "PLTR": 25.0,  "UBER": 75.0,  "NOW":  780.0,
    "WDAY": 250.0, "TEAM": 195.0, "ZM":   65.0,  "OKTA": 90.0,
    # ── Finanse ───────────────────────────────────────────────────────────────
    "JPM":  200.0, "BAC": 38.0,   "GS":  460.0,  "MS":   95.0,
    "V":    275.0, "MA":  470.0,  "PYPL": 65.0,  "BRK-B": 370.0,
    "AXP":  230.0, "C":   65.0,   "WFC": 55.0,   "BLK":  850.0,
    # ── Healthcare ────────────────────────────────────────────────────────────
    "JNJ":  155.0, "PFE": 28.0,   "MRNA": 95.0,  "LLY":  780.0,
    "UNH":  520.0, "ABBV": 175.0, "BMY":  55.0,  "AMGN": 310.0,
    "GILD": 85.0,  "REGN": 950.0, "VRTX": 450.0,
    # ── Energia ───────────────────────────────────────────────────────────────
    "XOM":  115.0, "CVX": 155.0,  "NEE":  65.0,  "ENPH": 95.0,
    "SLB":  48.0,  "OXY": 62.0,   "BP":   35.0,  "SHEL": 65.0,
    # ── Consumer ──────────────────────────────────────────────────────────────
    "WMT":  65.0,  "COST": 730.0, "TGT":  145.0, "MCD":  290.0,
    "SBUX": 95.0,  "NKE":  95.0,  "DIS":  95.0,  "HD":   370.0,
    "LOW":  230.0, "AMZN": 185.0, "EBAY": 48.0,
    # ── Przemysł ──────────────────────────────────────────────────────────────
    "BA":   185.0, "CAT": 345.0,  "GE":   165.0, "HON":  205.0,
    "UPS":  135.0, "FDX": 255.0,  "DAL":  48.0,  "AAL":  14.0,
    "LMT":  475.0, "RTX": 115.0,  "NOC":  480.0,
    # ── Growth / Meme ─────────────────────────────────────────────────────────
    "COIN": 225.0, "HOOD": 18.0,  "RIVN": 12.0,  "LCID": 3.5,
    "SOFI": 8.0,   "RBLX": 42.0,  "SNAP": 15.0,  "PINS": 32.0,
    "RDDT": 65.0,  "ABNB": 135.0, "DASH": 115.0, "LYFT": 18.0,
    # ── ETF szerokie ──────────────────────────────────────────────────────────
    "SPY":  445.0, "QQQ": 375.0,  "IWM":  195.0, "DIA":  385.0,
    "VTI":  235.0, "VOO": 415.0,  "VEA":  48.0,  "VWO":  42.0,
    "EFA":  75.0,  "EEM": 42.0,
    # ── ETF sektorowe ─────────────────────────────────────────────────────────
    "XLK":  205.0, "XLF": 42.0,   "XLE":  88.0,  "XLV":  145.0,
    "XLI":  118.0, "XLU": 68.0,   "XLRE": 38.0,  "XLP":  72.0,
    "XLY":  175.0, "XLB": 88.0,   "XLC":  78.0,
    # ── ETF lewarowane ────────────────────────────────────────────────────────
    "TQQQ": 55.0,  "SQQQ": 12.0,  "UPRO": 72.0,  "SPXU": 8.0,
    "SOXL": 35.0,  "SOXS": 8.0,   "LABU": 12.0,  "LABD": 5.0,
    "FNGU": 28.0,  "FNGD": 6.0,
    # ── Krypto ETF / powiązane ────────────────────────────────────────────────
    "IBIT": 38.0,  "FBTC": 72.0,  "GBTC": 65.0,  "MSTR": 185.0,
    "BITO": 22.0,  "ARKB": 68.0,  "EZBC": 35.0,
    # ── Zagraniczne ADR ───────────────────────────────────────────────────────
    "BABA": 82.0,  "NIO":  5.5,   "JD":   28.0,  "PDD":  145.0,
    "SHOP": 72.0,  "SE":   48.0,  "MELI": 1850.0,"GRAB": 3.8,
    "DIDI": 4.2,   "XPEV": 9.5,   "LI":   22.0,  "BIDU": 95.0,
    # ── Polska GPW (ceny w PLN) ───────────────────────────────────────────────
    "PKN":  58.0,  "PKO":  42.0,  "PZU":  38.0,  "CDR":  130.0,
    "ALE":  20.0,  "LPP":  1900.0,"KGH":  120.0, "MBK":  390.0,
    "DNP":  68.0,  "PEO":  145.0, "ING":  220.0, "SPL":  410.0,
    "OPL":  7.5,   "PGN":  6.8,   "TPE":  3.2,   "ENA":  8.5,
    "PGE":  9.2,   "ACP":  72.0,  "ARLN": 8.5,   "JSW":  26.0,
    "CCC":  148.0,

    # ── Wielka Brytania LSE (ceny w GBX — groszach) ───────────────────────────
    "HSBA": 650.0, "BP":   480.0, "SHEL": 2600.0,"AZN":  11500.0,
    "GSK":  1650.0,"BARC": 220.0, "LLOY": 55.0,  "VOD":  70.0,
    "RR":   480.0, "BAE":  1250.0,"REL":  2800.0, "DGE":  2400.0,
    "CPG":  2100.0,"EXPN": 3500.0,"LGEN": 255.0,  "PRU":  820.0,
    "STAN": 680.0, "ULVR": 4200.0,"RIO":  5200.0, "AAL":  2100.0,
    "NWG":  310.0, "BT":   135.0, "IAG":  195.0,
    # ── Krypto bezpośrednie (futures/CFD proxy) ───────────────────────────────
    "BTC":  62000.0, "ETH": 3200.0, "SOL":  145.0, "BNB":  580.0,
    "XRP":  0.55,    "ADA": 0.45,   "AVAX": 35.0,  "DOT":  7.5,
    "LINK": 14.0,    "UNI": 8.5,    "MATIC": 0.85, "DOGE": 0.12,
    "SHIB": 0.000018,"LTC": 82.0,   "BCH":  385.0, "ATOM": 8.5,
    "NEAR": 5.5,     "APT": 9.5,    "ARB":  1.1,   "OP":   2.2,
    "INJ":  28.0,    "TIA": 8.5,    "PYTH": 0.45,  "WIF":  2.8,
    "PEPE": 0.000012,"BONK": 0.000025,
    # ── Commodities ETF ───────────────────────────────────────────────────────
    "GLD":  185.0, "SLV":  22.0,  "USO":  72.0,  "UNG":  15.0,
    "PDBC": 15.0,  "DBC":  24.0,  "CORN": 22.0,  "WEAT": 7.5,
}

# Profile agentów — jak często i z jaką pewnością generują sygnały
_AGENT_PROFILES = {
    "TrendFollower": {
        "interval_sec": 30,
        "symbols": ["AAPL", "NVDA", "SPY", "QQQ", "MSFT", "AMZN", "META", "GOOGL", "AVGO", "TSM"],
        "avg_confidence": 0.62,
        "avg_predicted_gain": 1.2,
        "strategies": [
            "EMA9 > EMA21 > EMA50, ADX={adx:.0f} – silny trend wzrostowy",
            "Price action: Higher High + Higher Low, EMA crossover potwierdza",
            "EMA200 support + ADX={adx:.0f} – trend dominujący, wchodzę long",
            "EMA death cross – EMA9 < EMA21, ADX={adx:.0f} trend spadkowy",
        ]
    },
    "MeanReversion": {
        "interval_sec": 20,
        "symbols": ["AAPL", "TSLA", "NVDA", "SPY", "AMD", "COIN", "PLTR", "SNAP", "RIVN"],
        "avg_confidence": 0.58,
        "avg_predicted_gain": 0.8,
        "strategies": [
            "RSI={rsi:.0f} – oversold, BB lower touch, zscore={z:.2f}",
            "RSI={rsi:.0f} – overbought, cena przy BB upper, reversion oczekiwana",
            "Zscore={z:.2f} odchylenie od średniej, BB squeeze + RSI dywergencja",
            "Cena -2.1σ od MA20, wolumen spada – wyczerpanie ruchu",
        ]
    },
    "Scalper": {
        "interval_sec": 8,
        "symbols": ["AAPL", "TSLA", "NVDA", "QQQ", "AMD", "META", "COIN", "TQQQ", "SQQQ"],
        "avg_confidence": 0.52,
        "avg_predicted_gain": 0.3,
        "strategies": [
            "Volume spike {vol:.1f}x + EMA3 > EMA8 – momentum 1m",
            "3 zielone świece z rosnącym wolumenem, EMA3/8 crossover",
            "Bid/ask imbalance + volume burst – scalp long 1m",
            "EMA3 < EMA8, volume {vol:.1f}x – krótki scalp short",
        ]
    },
    "BreakoutHunter": {
        "interval_sec": 25,
        "symbols": ["AAPL", "TSLA", "NVDA", "SPY", "QQQ", "MSFT", "GOOGL", "ARM", "SHOP", "BABA"],
        "avg_confidence": 0.60,
        "avg_predicted_gain": 1.5,
        "strategies": [
            "Breakout ponad resistance {res:.2f} + ATR={atr:.2f} rozszerzenie",
            "Konsolidacja 15 świec + volume breakout – wejście na przebicie",
            "S/R flip: dawny opór {res:.2f} staje się wsparciem",
            "ATR={atr:.2f} ekspansja + wolumen 2x – dynamiczny breakout",
        ]
    },
    "SentimentTrader": {
        "interval_sec": 35,
        "symbols": ["AAPL", "TSLA", "NVDA", "SPY", "META", "AMZN", "COIN", "MRNA", "NIO"],
        "avg_confidence": 0.55,
        "avg_predicted_gain": 1.0,
        "strategies": [
            "Sentiment BULLISH: {news} – VADER={vader:.2f}, HIGH impact",
            "Fed minutes – jastrzębi ton, sentiment BEARISH: VADER={vader:.2f}",
            "Earnings beat + analityk upgrade – sentiment BULLISH: {vader:.2f}",
            "Makro news negatywny: {news} – sentiment SHORT",
        ]
    },
    "OptionsFlow": {
        "interval_sec": 20,
        "symbols": ["AAPL","NVDA","TSLA","SPY","QQQ","MSFT","META","AMZN","AMD","GOOGL"],
        "avg_confidence": 0.60,
        "avg_predicted_gain": 1.1,
        "strategies": [
            "Unusual call buying {symbol} – vol={vol:.1f}x, RSI={rsi:.0f} → LONG",
            "Unusual put buying {symbol} – vol={vol:.1f}x, RSI={rsi:.0f} → SHORT",
            "Options flow bullish: call skew {pct:.1f}% | conf={conf:.2f}",
            "Large block call sweep {symbol} – smart money wchodzi LONG",
        ]
    },
    "GapTrader": {
        "interval_sec": 40,
        "symbols": ["AAPL","TSLA","NVDA","MSFT","AMZN","META","GOOGL","AMD","COIN","MSTR"],
        "avg_confidence": 0.58,
        "avg_predicted_gain": 0.9,
        "strategies": [
            "Gap up {pct:.1f}% przy otwarciu, wolumen={vol:.1f}x – gap fill SHORT",
            "Gap down {pct:.1f}% – gap fill LONG, target prev close={res:.2f}",
            "Opening gap {symbol} | ATR={atr:.2f} | fill strategy LONG",
            "Earnings gap up {pct:.1f}% – momentum LONG kontynuacja",
        ]
    },
    "MomentumSurfer": {
        "interval_sec": 18,
        "symbols": ["AAPL","NVDA","TSLA","META","AMZN","QQQ","SPY","AMD","AVGO","ARM"],
        "avg_confidence": 0.61,
        "avg_predicted_gain": 1.3,
        "strategies": [
            "ROC={rsi:.0f}% silne momentum LONG – riding the wave",
            "RSI={rsi:.0f} + vol={vol:.1f}x – momentum surfer wchodzi LONG",
            "Momentum surge {symbol}: ROC+RSI aligned | conf={conf:.2f}",
            "Bearish momentum – ROC negatywny + RSI={rsi:.0f} → SHORT",
        ]
    },
    "VIXTrader": {
        "interval_sec": 30,
        "symbols": ["SPY","QQQ","IWM","TQQQ","SQQQ"],
        "avg_confidence": 0.64,
        "avg_predicted_gain": 1.8,
        "strategies": [
            "VIX spike – panika na rynku, kupuję dip SPY LONG",
            "VIX={rsi:.0f} wysoki – fear extremum, kontrarien LONG",
            "VIX normalny – euforia, ostrożnie SHORT QQQ",
            "Fear index ekstremum – capitulation buying LONG",
        ]
    },
    "DivergenceHunter": {
        "interval_sec": 25,
        "symbols": ["AAPL","TSLA","NVDA","AMD","COIN","PLTR","META","AMZN","GOOGL","MSFT"],
        "avg_confidence": 0.63,
        "avg_predicted_gain": 1.4,
        "strategies": [
            "Bullish divergence RSI vs cena {symbol} | LONG – reversal oczekiwany",
            "Bearish divergence MACD {symbol} | SHORT – cena wyżej RSI niżej",
            "Hidden bullish div – trend up, RSI wyższe dna | LONG conf={conf:.2f}",
            "MACD histogram dywerguje vs price action | RSI={rsi:.0f}",
        ]
    },
    "ScalpKing": {
        "interval_sec": 6,
        "symbols": ["AAPL","TSLA","NVDA","AMD","QQQ","META","COIN","TQQQ","MSFT","AMZN"],
        "avg_confidence": 0.56,
        "avg_predicted_gain": 0.25,
        "strategies": [
            "Opening hour scalp – vol={vol:.1f}x momentum LONG 9:30-10:45",
            "EMA3>EMA8 + vol spike {vol:.1f}x – ScalpKing wchodzi LONG",
            "Bear momentum scalp – 3 czerwone świece + vol={vol:.1f}x SHORT",
            "First hour volatility play | BB_width={atr:.4f} | LONG",
        ]
    },
    "WhaleTracker": {
        "interval_sec": 15,
        "symbols": ["BTC","ETH","SOL","NVDA","AAPL","TSLA","MSTR","IBIT","COIN","AMD"],
        "avg_confidence": 0.65,
        "avg_predicted_gain": 1.6,
        "strategies": [
            "Whale alert – vol={vol:.1f}x normalnej | duży gracz wchodzi LONG",
            "Large block trade {symbol} – instytucja kupuje, idę za nią",
            "Whale dump – {vol:.1f}x vol + price drop | SHORT",
            "On-chain: duży transfer do exchange – sprzedaż, SHORT {symbol}",
        ]
    },
}

_NEWS_EXAMPLES = [
    "Fed signals rate pause",
    "NVDA earnings beat estimates",
    "Strong jobs report",
    "CPI lower than expected",
    "Tech selloff on yields",
    "Apple new product launch",
]


class PaperTradingSession:
    """
    Silnik sesji testowej.

    Uruchomienie:
        session = PaperTradingSession(duration_min=5, capital=10000)
        report  = await session.run(on_trade_callback=my_func)
    """

    def __init__(
        self,
        duration_min: float = 5.0,
        capital: float = 10_000.0,
        selected_agents: list[str] | None = None,
        selected_symbols: list[str] | None = None,
    ) -> None:
        self.duration_sec    = duration_min * 60
        self.capital         = capital
        self.selected_agents = selected_agents or list(_AGENT_PROFILES.keys())
        self.selected_symbols = selected_symbols or list(_BASE_PRICES.keys())
        self.session_id      = f"SES_{int(time.time())}"

        self._trades:   list[PaperTrade]  = []
        self._trade_id  = 0
        self._prices:   dict[str, float]  = {
            s: _BASE_PRICES.get(s, 100.0) for s in self.selected_symbols
        }
        self._running   = False
        self._on_trade  = None  # callback gdy pojawi się nowy trade
        self._lessons:  list   = []  # lekcje po zakończeniu sesji

    # ── Publiczne API ─────────────────────────────────────────────────────────

    async def run(self, on_trade=None) -> SessionReport:
        """Uruchamia sesję i zwraca raport po zakończeniu."""
        self._on_trade = on_trade
        self._running  = True
        start_time     = datetime.now()

        log.info("🚀 Sesja testowa {} uruchomiona ({:.0f} min, kapital=${:.0f})",
                 self.session_id, self.duration_sec / 60, self.capital)

        # Uruchom zadania agentów + symulację cen równolegle
        tasks = [self._price_simulation_loop()]
        for agent_name in self.selected_agents:
            if agent_name in _AGENT_PROFILES:
                tasks.append(self._agent_loop(agent_name))

        try:
            await asyncio.wait_for(
                asyncio.gather(*tasks, return_exceptions=True),
                timeout=self.duration_sec,
            )
        except asyncio.TimeoutError:
            pass  # Normalne zakończenie po czasie

        self._running = False
        end_time = datetime.now()

        # Zamknij otwarte pozycje po cenie rynkowej
        self._close_all_open_trades()

        # Generuj raport
        report = self._build_report(start_time, end_time)
        log.info("✅ Sesja zakończona: {} tradów, PnL=${:.2f} ({:.2f}%)",
                 report.total_trades, report.total_pnl_usd, report.total_pnl_pct)

        # ── Uczenie agentów na podstawie wyników ──────────────────────────────
        try:
            from agents.learning import get_learning_engine
            engine  = get_learning_engine()
            lessons = engine.learn_from_session(report.summary())
            self._lessons = [
                {
                    "agent_name":  l.agent_name,
                    "win_rate":    round(l.win_rate * 100, 1),
                    "total_pnl":   round(l.total_pnl, 2),
                    "trades":      l.trades_count,
                    "changes":     l.changes,
                    "summary":     l.summary,
                    "new_params":  l.new_params,
                }
                for l in lessons
            ]
            log.info("🎓 Uczenie zakończone: {} agentów zaktualizowało parametry", len(lessons))
        except Exception as exc:
            log.warning("Błąd uczenia agentów: {}", exc)
            self._lessons = []

        # ── Coach ocenia całą sesję ───────────────────────────────────────────
        try:
            from agents.auxiliary.coach import get_coach
            coach = get_coach()
            summary = report.summary()
            log.info("🏆 Coach: oceniam sesję {} z {} tradami",
                     summary.get("session_id"), len(summary.get("trades", [])))
            coach_summary = coach.review_session(summary)
            ranking = coach_summary.get("ranking", [])
            log.info("🏆 Coach ranking po sesji: top3={}",
                     [r["agent_name"] for r in ranking[:3]])
        except Exception as exc:
            log.error("Błąd CoachAgent review_session: {}", exc)
            import traceback
            log.debug(traceback.format_exc())
        except Exception as exc:
            log.warning("Błąd CoachAgent: {}", exc)

        return report

    def get_live_trades(self) -> list[dict]:
        """Zwraca aktualne transakcje (do live update w UI)."""
        return [self._trade_to_simple_dict(t) for t in self._trades]

    def get_lessons(self) -> list[dict]:
        """Zwraca lekcje po zakończeniu sesji."""
        return self._lessons

    # ── Wewnętrzne ────────────────────────────────────────────────────────────

    async def _price_simulation_loop(self) -> None:
        """Pobiera prawdziwe ceny live z Polygon.io co 5 sekund."""
        import requests as _req

        try:
            from config.settings import get_settings
            api_key = get_settings().polygon_api_key
        except Exception:
            api_key = None

        def _fetch_price(symbol: str) -> float:
            """Synchroniczne pobieranie ceny — uruchamiane w executor."""
            try:
                r = _req.get(
                    f"https://api.polygon.io/v2/last/trade/{symbol}?apiKey={api_key}",
                    timeout=3
                )
                if r.status_code == 200:
                    return float(r.json().get("results", {}).get("p", 0) or 0)
            except Exception:
                pass
            return 0.0

        loop = asyncio.get_event_loop()

        while self._running:
            if api_key:
                # Pobierz wszystkie ceny równolegle w tle (nie blokuje event loop)
                symbols = list(self._prices.keys())[:30]  # max 30 symboli naraz
                tasks   = [
                    loop.run_in_executor(None, _fetch_price, sym)
                    for sym in symbols
                ]
                try:
                    prices = await asyncio.wait_for(
                        asyncio.gather(*tasks, return_exceptions=True),
                        timeout=8.0
                    )
                    for sym, price in zip(symbols, prices):
                        if isinstance(price, float) and price > 0:
                            self._prices[sym] = price
                except asyncio.TimeoutError:
                    pass
            else:
                # Fallback bez klucza API
                for symbol in list(self._prices.keys()):
                    pct = random.gauss(0, 0.0001)
                    self._prices[symbol] = round(self._prices[symbol] * (1 + pct), 4)

            await asyncio.sleep(5)

    async def _agent_loop(self, agent_name: str) -> None:
        """Pętla agenta — co interval_sec generuje decyzję."""
        profile = _AGENT_PROFILES[agent_name]

        # ── Wczytaj nauczone parametry z poprzednich sesji ────────────────────
        try:
            from agents.learning import get_learning_engine
            learned = get_learning_engine().get_agent_params(agent_name)
            # Zastosuj nauczone parametry
            conf_threshold = learned.get("confidence_threshold", 0.45)
            size_mult      = learned.get("position_size_mult", 1.0)
            cooldown_mult  = learned.get("signal_cooldown_mult", 1.0)
            long_bias      = learned.get("long_bias", 0.5)
            sessions_done  = learned.get("sessions_count", 0)

            # Im więcej sesji, tym bardziej selektywny agent
            skip_prob = max(0.05, min(0.35, 0.15 + sessions_done * 0.02))

            log.debug("🧠 {} wczytał parametry: conf_min={:.2f} size_mult={:.2f} "
                      "cooldown={:.2f} long_bias={:.2f} (sesje: {})",
                      agent_name, conf_threshold, size_mult,
                      cooldown_mult, long_bias, sessions_done)
        except Exception:
            conf_threshold = 0.45
            size_mult      = 1.0
            cooldown_mult  = 1.0
            long_bias      = 0.5
            skip_prob      = 0.15

        # Interwał dostosowany przez cooldown_mult
        interval = profile["interval_sec"] * cooldown_mult

        # Losowy start żeby agenci nie generowali wszystkiego naraz
        await asyncio.sleep(random.uniform(1, 8))

        while self._running:
            # Pomijaj cykle z prawdopodobieństwem skip_prob (nauczonym)
            if random.random() < skip_prob:
                await asyncio.sleep(interval)
                continue

            # Wybierz symbol — unikaj "najgorszych" symboli z pamięci
            available = [s for s in profile["symbols"] if s in self._prices]
            try:
                from agents.learning import get_learning_engine
                worst = get_learning_engine().get_agent_params(agent_name).get("worst_symbols", [])
                # 70% szans że unikamy najgorszych symboli
                filtered = [s for s in available if s not in worst]
                if filtered and random.random() < 0.7:
                    available = filtered
            except Exception:
                pass

            if not available:
                await asyncio.sleep(interval)
                continue

            symbol = random.choice(available)
            price  = self._prices[symbol]

            # Generuj sygnał z nauczonym progiem pewności
            raw_conf   = random.gauss(profile["avg_confidence"], 0.08)
            confidence = min(0.95, max(conf_threshold, raw_conf))
            predicted  = random.gauss(profile["avg_predicted_gain"], 0.3)

            # Kierunek z long_bias (nauka preferowanego kierunku)
            direction = "LONG" if random.random() < long_bias else "SHORT"

            # Wybierz reasoning
            strategy_template = random.choice(profile["strategies"])
            reasoning = self._fill_reasoning(strategy_template, symbol, price)

            # Wielkość pozycji z size_mult (uczony mnożnik)
            position_pct = confidence * 0.02 * size_mult
            invest_usd   = self.capital * position_pct
            quantity     = invest_usd / price

            trade = PaperTrade(
                trade_id     = f"T{self._trade_id:04d}",
                agent_name   = agent_name,
                symbol       = symbol,
                direction    = direction,
                entry_price  = price,
                quantity     = quantity,
                entry_time   = datetime.now(),
                reasoning    = reasoning,
                confidence   = confidence,
                predicted_gain_pct = predicted,
            )
            self._trade_id += 1
            self._trades.append(trade)

            log.debug("📊 {} | {} {} @ ${:.2f} | conf={:.2f} | {}",
                      agent_name, direction, symbol,
                      price, confidence, reasoning[:60])

            if self._on_trade:
                try:
                    await self._on_trade(trade)
                except Exception:
                    pass

            # Czas trzymania pozycji — skalowany do długości sesji
            # Krótka sesja (5min) → hold 10-60s | Długa (2h) → hold 2-20min
            max_hold = min(self.duration_sec * 0.15, 1200)  # max 20 minut
            min_hold = max(10, self.duration_sec * 0.02)     # min 2% czasu sesji
            hold_sec = random.uniform(min_hold, max_hold)
            asyncio.create_task(self._close_trade_after(trade, hold_sec))

            await asyncio.sleep(interval)

    async def _close_trade_after(self, trade: PaperTrade, delay_sec: float) -> None:
        """Zamknij pozycję po delay_sec sekundach."""
        await asyncio.sleep(delay_sec)
        if trade.status == "OPEN" and self._running:
            self._close_trade(trade)

    def _close_trade(self, trade: PaperTrade) -> None:
        """Zamknij pozycję po aktualnej cenie rynkowej z realistycznym slippage."""
        if trade.status != "OPEN":
            return

        exit_price_raw = self._prices.get(trade.symbol, trade.entry_price)

        # ── Realistyczny slippage ─────────────────────────────────────────────
        # Alpaca: brak prowizji dla akcji US
        # Ale spread bid/ask + market impact:
        # - Małe zlecenia (<$1000): 0.02-0.04% slippage
        # - Średnie ($1000-$10000): 0.03-0.06%
        # - Losowy element (rynek się poruszył zanim dotarło zlecenie)
        trade_value = trade.entry_price * trade.quantity
        if trade_value < 1000:
            slippage_pct = random.uniform(0.0002, 0.0004)
        elif trade_value < 10000:
            slippage_pct = random.uniform(0.0003, 0.0006)
        else:
            slippage_pct = random.uniform(0.0005, 0.001)

        # Slippage idzie zawsze przeciwko nam
        if trade.direction == "LONG":
            # Zamykamy LONG przez SELL — dostajemy niższą cenę
            exit_price = exit_price_raw * (1 - slippage_pct)
        else:
            # Zamykamy SHORT przez BUY — płacimy wyższą cenę
            exit_price = exit_price_raw * (1 + slippage_pct)

        # ── Prowizje ──────────────────────────────────────────────────────────
        # Alpaca: $0 prowizji dla akcji US
        # Ale SEC fee: $0.0000278 × wartość (prawie 0 dla małych zleceń)
        sec_fee = trade_value * 0.0000278
        commission = round(sec_fee, 4)  # zazwyczaj <$0.01

        trade.exit_price = round(exit_price, 4)
        trade.exit_time  = datetime.now()

        if trade.direction == "LONG":
            pnl_usd = (exit_price - trade.entry_price) * trade.quantity - commission
        else:
            pnl_usd = (trade.entry_price - exit_price) * trade.quantity - commission

        trade.actual_pnl_usd = round(pnl_usd, 4)
        trade.actual_pnl_pct = round(
            (pnl_usd / (trade.entry_price * trade.quantity)) * 100, 4
        )
        trade.status = "CLOSED"

        # ── Coach ocenia trade ────────────────────────────────────────────────
        try:
            from agents.auxiliary.coach import get_coach
            get_coach().review_trade(
                agent_name = trade.agent_name,
                symbol     = trade.symbol,
                direction  = trade.direction,
                pnl_usd    = pnl_usd,
                pnl_pct    = trade.actual_pnl_pct,
                trade_id   = trade.trade_id,
                session_id = self.session_id,
            )
        except Exception:
            pass

    def _close_all_open_trades(self) -> None:
        """Zamknij wszystkie otwarte pozycje na koniec sesji."""
        for trade in self._trades:
            if trade.status == "OPEN":
                self._close_trade(trade)
                trade.status = "EXPIRED"

    def _build_report(self, start: datetime, end: datetime) -> SessionReport:
        """Zbuduj finalny raport sesji."""
        closed = [t for t in self._trades if t.status in ("CLOSED", "EXPIRED")]

        total_pnl  = sum(t.actual_pnl_usd or 0 for t in closed)
        winners    = [t for t in closed if (t.actual_pnl_usd or 0) > 0]
        losers     = [t for t in closed if (t.actual_pnl_usd or 0) <= 0]
        best_pnl   = max((t.actual_pnl_usd or 0 for t in closed), default=0)
        worst_pnl  = min((t.actual_pnl_usd or 0 for t in closed), default=0)

        # Stats per agent
        agent_stats = {}
        for agent in self.selected_agents:
            agent_trades = [t for t in closed if t.agent_name == agent]
            if not agent_trades:
                continue
            agent_pnl  = sum(t.actual_pnl_usd or 0 for t in agent_trades)
            agent_wins = sum(1 for t in agent_trades if (t.actual_pnl_usd or 0) > 0)
            agent_stats[agent] = {
                "trades":    len(agent_trades),
                "wins":      agent_wins,
                "losses":    len(agent_trades) - agent_wins,
                "win_rate":  round(agent_wins / len(agent_trades) * 100, 1),
                "total_pnl": round(agent_pnl, 2),
            }

        report = SessionReport(
            session_id      = self.session_id,
            start_time      = start,
            end_time        = end,
            duration_min    = (end - start).total_seconds() / 60,
            initial_capital = self.capital,
            total_trades    = len(closed),
            winning_trades  = len(winners),
            losing_trades   = len(losers),
            total_pnl_usd   = total_pnl,
            total_pnl_pct   = (total_pnl / self.capital) * 100,
            best_trade_pnl  = best_pnl,
            worst_trade_pnl = worst_pnl,
            trades          = self._trades,
            agent_stats     = agent_stats,
        )
        return report

    def _fill_reasoning(self, template: str, symbol: str, price: float) -> str:
        """Wypełnij template reasoning losowymi wartościami wskaźników."""
        try:
            return template.format(
                adx    = random.uniform(25, 65),
                rsi    = random.uniform(25, 75),
                z      = random.uniform(-2.5, 2.5),
                vol    = random.uniform(1.5, 4.0),
                res    = price * random.uniform(0.995, 1.01),
                atr    = price * random.uniform(0.005, 0.015),
                vader  = random.uniform(-0.8, 0.8),
                news   = random.choice(_NEWS_EXAMPLES),
                pct    = random.uniform(0.5, 3.5),
                conf   = random.uniform(0.50, 0.90),
                symbol = symbol,
            )
        except KeyError:
            return template  # zwróć surowy template jeśli brakuje zmiennej

    def _trade_to_simple_dict(self, t: PaperTrade) -> dict:
        return {
            "agent":       t.agent_name,
            "symbol":      t.symbol,
            "direction":   t.direction,
            "entry_price": round(t.entry_price, 2),
            "exit_price":  round(t.exit_price, 2) if t.exit_price else None,
            "pnl_usd":     round(t.actual_pnl_usd, 2) if t.actual_pnl_usd is not None else None,
            "status":      t.status,
            "reasoning":   t.reasoning,
            "time":        t.entry_time.strftime("%H:%M:%S"),
        }
