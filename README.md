# 📈 IBKR Multi-Agent Trading System

Kompleksowy, produkcyjny system automatycznego tradingu oparty o **Interactive Brokers**,
zbudowany w Pythonie 3.11+ z architekturą multi-agentową, asynchronicznym silnikiem,
panelem sterowania oraz wbudowanym AI Chatem.

> ⚠️ **OSTRZEŻENIE:** System domyślnie uruchamia się w trybie **Paper Trading** (konto demo).
> Przejście na handel realny wymaga jawnego potwierdzenia w panelu + hasła bezpieczeństwa.
> Handel na rynkach finansowych wiąże się z ryzykiem utraty kapitału.

---

## 📋 Spis treści

1. [Wymagania](#wymagania)
2. [Instalacja](#instalacja)
3. [Konfiguracja IBKR](#konfiguracja-ibkr)
4. [Konfiguracja systemu (.env)](#konfiguracja-env)
5. [Uruchomienie](#uruchomienie)
6. [Panel sterowania](#panel-sterowania)
7. [AI Chat](#ai-chat)
8. [Agenci tradingowi](#agenci-tradingowi)
9. [Backtester](#backtester)
10. [Alerting](#alerting)
11. [Architektura](#architektura)
12. [Ostrzeżenia i bezpieczeństwo](#bezpieczeństwo)

---

## Wymagania

| Wymaganie | Wersja |
|-----------|--------|
| Python | 3.11+ |
| Interactive Brokers TWS lub IB Gateway | aktualny |
| Redis (opcjonalny) | 7.x |
| RAM | min. 2 GB |
| OS | Windows 10/11, Linux, macOS |

### Konto IBKR
- **Paper Trading Account** – darmowe, wymagane do startu
- Aktywna subskrypcja TWS lub IB Gateway
- Pobierz TWS: https://www.interactivebrokers.com/en/trading/tws.php
- Pobierz IB Gateway: https://www.interactivebrokers.com/en/trading/ibgateway-stable.php

---

## Instalacja

### 1. Sklonuj / pobierz projekt

```bash
# Wejdź do folderu projektu
cd ibkr_trading_system
```

### 2. Utwórz środowisko wirtualne

```bash
# Windows (PowerShell)
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# Linux / macOS
python3.11 -m venv .venv
source .venv/bin/activate
```

### 3. Zainstaluj zależności

```bash
pip install -r requirements.txt
```

> 💡 **Szybszy install** z uv (opcjonalnie):
> ```bash
> pip install uv
> uv pip install -r requirements.txt
> ```

### 4. Utwórz plik .env

```bash
# Windows
copy .env.example .env

# Linux / macOS
cp .env.example .env
```

Edytuj `.env` w dowolnym edytorze tekstowym.

### 5. Wygeneruj hash hasła do panelu

```bash
python scripts/generate_password.py
```

Skopiuj wynik do `.env` jako `PANEL_PASSWORD_HASH`.

---

## Konfiguracja IBKR

### TWS (Trader Workstation) – zalecane dla beginnerów

1. Pobierz i zainstaluj TWS: https://www.interactivebrokers.com/en/trading/tws.php
2. Zaloguj się na **konto papierowe** (Paper Trading)
3. W TWS: `Edit → Global Configuration → API → Settings`
   - ✅ Enable ActiveX and Socket Clients
   - ✅ Allow connections from localhost only
   - Port: **7497** (paper) lub **7496** (real)
   - Trusted IPs: `127.0.0.1`
4. Upewnij się że TWS jest uruchomiony **przed** startem systemu

### IB Gateway – zalecane dla serwerów

1. Pobierz IB Gateway
2. Zaloguj się na konto papierowe
3. Tryb: **IB API**
4. Port: **4002** (paper) lub **4001** (real)
5. Ustaw w `.env`: `IBKR_PORT=4002`

### Ustawienia portów

| Aplikacja | Tryb | Port |
|-----------|------|------|
| TWS | Paper Trading | 7497 |
| TWS | Real Trading | 7496 |
| IB Gateway | Paper Trading | 4002 |
| IB Gateway | Real Trading | 4001 |

---

## Konfiguracja .env

Otwórz plik `.env` i wypełnij wymagane pola:

```env
# ── IBKR ─────────────────────────────────────────────────────────────────────
IBKR_HOST=127.0.0.1
IBKR_PORT=7497          # TWS Paper Trading
IBKR_CLIENT_ID=1
REAL_MODE=false          # NIGDY nie zmieniaj ręcznie

# ── Panel ─────────────────────────────────────────────────────────────────────
PANEL_USERNAME=admin
PANEL_PASSWORD_HASH=     # wynik z: python scripts/generate_password.py
SECRET_KEY=              # losowy string 32+ znaków
EMERGENCY_STOP_PASSWORD= # hasło do przycisku Emergency Stop

# ── Risk (dostosuj do swojego kapitału) ───────────────────────────────────────
MAX_DAILY_LOSS_USD=500.0
MAX_DRAWDOWN_PCT=10.0
TOTAL_CAPITAL_USD=10000.0
MAX_POSITION_SIZE_PCT=5.0

# ── AI Chat (opcjonalne) ──────────────────────────────────────────────────────
OPENAI_API_KEY=          # GPT-4o; jeśli puste → Ollama lub wbudowany parser
OPENAI_MODEL=gpt-4o-mini

# ── Alerting (opcjonalne) ─────────────────────────────────────────────────────
TELEGRAM_BOT_TOKEN=
TELEGRAM_CHAT_ID=
```

### Jak uzyskać Telegram Bot Token?
1. Napisz do [@BotFather](https://t.me/BotFather) na Telegramie
2. Wpisz `/newbot` i postępuj zgodnie z instrukcjami
3. Skopiuj token do `TELEGRAM_BOT_TOKEN`
4. Wyślij dowolną wiadomość do swojego bota
5. Otwórz: `https://api.telegram.org/bot<TOKEN>/getUpdates`
6. Skopiuj `chat.id` do `TELEGRAM_CHAT_ID`

---

## Uruchomienie

### Krok 1: Uruchom TWS lub IB Gateway

Upewnij się że TWS/Gateway jest uruchomiony i zalogowany na konto papierowe.

### Krok 2: (Opcjonalnie) Uruchom Redis

```bash
# Windows – pobierz Redis z: https://github.com/microsoftarchive/redis/releases
redis-server

# Linux
sudo systemctl start redis

# Docker (najłatwiej)
docker run -d -p 6379:6379 redis:7-alpine
```

> System działa **bez Redis** (fallback na asyncio queues).

### Krok 3: Uruchom system

```bash
# Główny system (agenci + API backend)
python main.py

# Tylko API bez agentów (do testów panelu)
python main.py --no-agents

# Wymuszony paper mode
python main.py --paper
```

### Krok 4: Uruchom panel sterowania (osobny terminal)

```bash
streamlit run panel/frontend/dashboard.py
```

Panel będzie dostępny pod: **http://localhost:8501**

### Krok 5: Zaloguj się do panelu

- Login: `admin` (lub wartość `PANEL_USERNAME` z .env)
- Hasło: wartość `PANEL_PASSWORD_HASH` (przed hashowaniem)

### Szybki start – wszystko w jednym skrypcie

```bash
# Windows
.\scripts\start.ps1

# Linux / macOS
./scripts/start.sh
```

---

## Panel sterowania

Panel dostępny pod: `http://localhost:8501`

### Strony panelu

| Strona | Opis |
|--------|------|
| 📊 **Dashboard** | Przegląd systemu: metryki, status agentów, ostatnie sygnały |
| 🤖 **Agenci** | Włącz/wyłącz agentów, zmień alokację i parametry |
| 📋 **Pozycje** | Otwarte pozycje z PnL w czasie rzeczywistym |
| 📡 **Sygnały** | Historia sygnałów z uzasadnieniami decyzji |
| ⚠️ **Ryzyko** | Globalne limity: dzienna strata, drawdown, kapitał |
| 📈 **Wydajność** | Win rate, Sharpe, Profit Factor per agent + sugestie |
| 📰 **Newsy** | RSS feed z klasyfikacją HIGH/MEDIUM/LOW impact |
| 🔬 **Backtester** | Testy historyczne + Walk-Forward + Monte Carlo |
| 🤖 **AI Chat** | Sterowanie systemem głosem poleceń naturalnym językiem |
| 📜 **Logi** | Logi systemowe w czasie rzeczywistym |
| 🚨 **Emergency Stop** | Natychmiastowe zatrzymanie systemu |

### Emergency Stop

Czerwony przycisk zatrzymuje system natychmiast:
- Blokuje otwieranie nowych pozycji przez **wszystkich** agentów
- Opcjonalnie zamyka wszystkie otwarte pozycje rynkowo
- Wymaga hasła (`EMERGENCY_STOP_PASSWORD`)
- Odblokowanie wymaga ponownego podania hasła

---

## AI Chat

Steruj systemem naturalnym językiem na stronie **🤖 AI Chat**.

### Przykładowe komendy

```
# Informacje
"jaki jest status systemu?"
"pokaż otwarte pozycje"
"ile wynosi dzisiejszy PnL?"
"który agent ma najlepszy win rate?"
"pokaż newsy HIGH impact z ostatnich 4 godzin"

# Sterowanie agentami
"wyłącz Scalper"
"włącz TrendFollower"
"ustaw alokację MeanReversion na 20%"
"zmień limit straty na 300 dolarów"

# Bezpieczeństwo
"aktywuj emergency stop"  → wymaga potwierdzenia 'tak'
```

### Backendy AI (w kolejności priorytetów)

1. **OpenAI GPT-4o** – najlepsze wyniki; ustaw `OPENAI_API_KEY` w `.env`
2. **Ollama (lokalny LLM)** – prywatność, brak kosztów; zainstaluj z [ollama.com](https://ollama.com)
   ```bash
   ollama pull llama3
   ollama serve
   ```
3. **Wbudowany parser** – bez LLM, działa zawsze (obsługuje podstawowe komendy)

---

## Agenci tradingowi

| Agent | Charakter | Metody | Timeframe |
|-------|-----------|--------|-----------|
| **TrendFollower** | Cierpliwy Strateg | EMA 9/21/50/200 + ADX + price action (HH/HL) | 1H + 4H |
| **MeanReversion** | Matematyczny Kontrarian | Bollinger Bands + RSI + Z-score + vol exhaustion | 15m + 1H |
| **Scalper** | Agresywny Spekulant | Volume spikes + EMA3/8 + momentum 3 świece | 1m + 5m |
| **BreakoutHunter** | Oportunista | S/R breakout + ATR expansion + volume confirm | 15m + 1H |
| **SentimentTrader** | Narracyjny | RSS + VADER NLP + specjalne wagi Fed/Trump/Musk | event-driven |

### Agenci pomocniczy

| Agent | Rola |
|-------|------|
| **MarketAnalyst** | Regime detection (trend/range/volatile), korelacje |
| **NewsAnalyst** | RSS feeds, klasyfikacja HIGH/MEDIUM/LOW impact |
| **ResearchAgent** | Multi-timeframe analiza, fundamenty (yfinance) |
| **SmartMoneyTracker** | OBV, CMF, akumulacja/dystrybucja instytucji |
| **RiskManager** | Absolutne VETO, position sizing, limity |
| **PerformanceReviewer** | Post-trade analytics, Sharpe, sugestie optymalizacji |
| **PortfolioAllocator** | Kelly Criterion (capped), dynamiczna alokacja |

### Konfiguracja agentów w panelu

Każdy agent można skonfigurować w sekcji **🤖 Agenci**:
- **Włącz/Wyłącz** – natychmiastowy toggle
- **Maks. alokacja (%)** – ile % kapitału może użyć
- **Maks. ryzyko per trade (%)** – max strata na jedną transakcję
- **Parametry strategii** – zaawansowane ustawienia (przez AI Chat lub API)

---

## Backtester

### Przez panel (UI)

1. Wejdź na stronę **🔬 Backtester**
2. Wybierz symbol, daty, agenta, timeframe
3. Opcjonalnie włącz Walk-Forward Analysis i Monte Carlo
4. Kliknij **▶ Uruchom Backtest**

### Przez Python (skrypt)

```python
import asyncio
from backtester.engine import Backtester, BacktestConfig, WalkForwardAnalysis, MonteCarloSimulation
from backtester.data_loader import load_data
from agents.trading.trend_follower import TrendFollower

async def main():
    config = BacktestConfig(
        symbol="AAPL",
        start="2023-01-01",
        end="2024-01-01",
        timeframe="1h",
        initial_capital=10000,
        commission=1.0,
    )

    df = await load_data("AAPL", "2023-01-01", "2024-01-01", "1h")

    bt      = Backtester(config)
    results = await bt.run_with_data(df, TrendFollower)
    print(results.summary())

    # Walk-Forward
    wfa = WalkForwardAnalysis(config, n_splits=5)
    wfa_results = await wfa.run(df, TrendFollower)
    print(f"Avg OOS Return: {wfa_results['avg_oos_return']:.2f}%")

    # Monte Carlo
    mc = MonteCarloSimulation(n_simulations=1000)
    mc_results = mc.run(results)
    print(f"P(profit): {mc_results['prob_profitable_pct']:.1f}%")

asyncio.run(main())
```

---

## Alerting

### Telegram

1. Ustaw `TELEGRAM_BOT_TOKEN` i `TELEGRAM_CHAT_ID` w `.env`
2. Alerty wysyłane przy: Emergency Stop, przekroczeniu limitów, HIGH impact news, błędach krytycznych

### E-mail

1. Ustaw dane SMTP w `.env` (np. Gmail z App Password)
2. E-maile wysyłane tylko dla poziomów CRITICAL i EMERGENCY

### Typy alertów

| Poziom | Przykład |
|--------|---------|
| INFO | Agent uruchomiony/zatrzymany |
| WARNING | HIGH impact news, słaba wydajność agenta |
| CRITICAL | Przekroczenie dziennego limitu straty, drawdown |
| EMERGENCY | Emergency Stop aktywowany |

---

## Architektura

```
ibkr_trading_system/
├── main.py                      ← punkt startowy
├── config/
│   └── settings.py              ← pydantic-settings, .env loader
├── core/
│   ├── ibkr_connector.py        ← IBKR connection, orders, market data
│   ├── message_bus.py           ← asyncio + Redis pub/sub
│   ├── models.py                ← Pydantic modele danych
│   ├── shared_state.py          ← globalny stan systemu (singleton)
│   └── logger.py                ← loguru setup
├── agents/
│   ├── base_agent.py            ← abstrakcyjna klasa agenta
│   ├── risk_manager.py          ← RiskManager z prawem VETO
│   ├── orchestrator.py          ← agregacja sygnałów → zlecenia
│   ├── trading/                 ← 5 agentów tradingowych
│   │   ├── trend_follower.py
│   │   ├── mean_reversion.py
│   │   ├── scalper.py
│   │   ├── breakout_hunter.py
│   │   └── sentiment_trader.py
│   └── auxiliary/               ← 6 agentów pomocniczych
│       ├── market_analyst.py
│       ├── news_analyst.py
│       ├── research_agent.py
│       ├── smart_money_tracker.py
│       ├── performance_reviewer.py
│       └── portfolio_allocator.py
├── services/
│   └── market_data.py           ← OHLCV + wskaźniki techniczne
├── database/
│   ├── models.py                ← SQLAlchemy ORM (SQLite/TimescaleDB)
│   └── database.py              ← async engine, session factory
├── panel/
│   ├── ai_chat.py               ← AI Chat Engine (OpenAI/Ollama/builtin)
│   ├── api/
│   │   ├── app.py               ← FastAPI app
│   │   ├── auth.py              ← JWT autentykacja
│   │   └── routes.py            ← wszystkie endpointy REST + WebSocket
│   └── frontend/
│       └── dashboard.py         ← Streamlit panel (11 stron)
├── backtester/
│   ├── engine.py                ← Backtester + WFA + Monte Carlo
│   └── data_loader.py           ← yfinance + CSV data loader
├── alerting/
│   └── alerting.py              ← Telegram + email alerting
├── data/                        ← SQLite DB + CSV pliki danych
├── logs/                        ← pliki logów
├── scripts/                     ← skrypty pomocnicze
├── tests/                       ← testy jednostkowe
├── .env                         ← konfiguracja (NIE commituj!)
├── .env.example                 ← szablon konfiguracji
└── requirements.txt
```

### Przepływ sygnału do zlecenia

```
Agent.analyze(symbol)
    → TradeSignal (z reasoning + wskaźniki)
    → MessageBus.publish("signals", signal)
    → Orchestrator._on_signal()
    → Agregacja (okno 5s, waga per agent)
    → RiskManager.evaluate() ← VETO lub APPROVE
    → RiskManager.build_order()
    → IBKRConnector.place_order()
    → OrderResult → DB + audit log
```

---

## Bezpieczeństwo

### ⚠️ Krytyczne zasady

1. **NIGDY** nie ustawiaj `REAL_MODE=true` bez pełnego zrozumienia systemu
2. Przejście na real trading wymaga **3 kroków**: panel → podwójne potwierdzenie → hasło
3. Zacznij od małego kapitału na koncie papierowym (min. 30 dni testów)
4. Ustaw rozsądne limity ryzyka **zanim** włączysz agentów:
   - `MAX_DAILY_LOSS_USD` – max dzienna strata (zacznij od $50-100)
   - `MAX_DRAWDOWN_PCT` – max drawdown (zacznij od 5%)
   - `MAX_POSITION_SIZE_PCT` – max rozmiar pozycji (zacznij od 2%)
5. Emergency Stop jest zawsze dostępny – nie bój się go używać
6. Regularnie sprawdzaj logi i raporty wydajności
7. Nie uruchamiaj Scalpera bez sprawdzenia kosztów prowizji (może handlować często)

### Pliki do ochrony

```
.env                  ← NIGDY nie commituj do git
data/trading.db       ← baza danych – backup regularnie
logs/                 ← logi – mogą zawierać dane wrażliwe
```

Dodaj do `.gitignore`:
```
.env
data/
logs/
__pycache__/
.venv/
*.pyc
```

---

## FAQ

**Q: System nie łączy się z IBKR**
- Sprawdź czy TWS/Gateway jest uruchomiony i zalogowany
- Sprawdź port w `.env` (7497 dla TWS Paper)
- W TWS: `Edit → Global Config → API → Enable API`
- Sprawdź logi: `logs/system.log`

**Q: Panel pokazuje "Brak połączenia z API"**
- Upewnij się że `python main.py` działa w osobnym terminalu
- API dostępne pod: http://localhost:8000/health

**Q: Agenci nie generują sygnałów**
- Sprawdź czy są włączeni w panelu (🤖 Agenci)
- Sprawdź czy Emergency Stop nie jest aktywny
- Sprawdź logi agenta – może brakować danych historycznych
- IBKR może ograniczać pobieranie danych poza godzinami sesji

**Q: AI Chat nie działa**
- Bez klucza OpenAI używa wbudowanego parsera (podstawowe komendy)
- Dla pełnych możliwości dodaj `OPENAI_API_KEY` do `.env`
- Lokalnie: zainstaluj [Ollama](https://ollama.com) i uruchom `ollama pull llama3`

**Q: Backtester zwraca błąd danych**
- Zainstaluj yfinance: `pip install yfinance`
- Sprawdź czy symbol jest poprawny (AAPL, TSLA, SPY, itp.)
- Dane intraday (1h) dostępne tylko dla ostatnich ~730 dni w yfinance

---

## Licencja i odpowiedzialność

System jest dostarczany **wyłącznie w celach edukacyjnych**.
Autor nie ponosi odpowiedzialności za straty finansowe wynikające z użycia systemu.
Przed użyciem na realnym kapitale skonsultuj się z doradcą finansowym.

**Trading na rynkach finansowych wiąże się z ryzykiem utraty całego kapitału.**
