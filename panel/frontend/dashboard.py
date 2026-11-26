"""
Panel sterowania – IBKR Multi-Agent Trading System
Streamlit dashboard z ciemnym motywem.

Uruchomienie:
    streamlit run panel/frontend/dashboard.py
"""
from __future__ import annotations

import streamlit as st

# Import stron developerskich
try:
    from panel.frontend.dev_pages import (
        page_dev_monitor,
        page_pnl_timeline,
        page_logs_pro,
        page_signals_pro,
        page_system_health,
        page_dev_export,
    )
    _DEV_PAGES_LOADED = True
except ImportError as _e:
    _DEV_PAGES_LOADED = False
    import traceback; traceback.print_exc()

# 
# Konfiguracja strony (MUSI być pierwsza komenda Streamlit)
# 
st.set_page_config(
    page_title="IBKR Trading System",
    page_icon="",
    layout="wide",
    initial_sidebar_state="collapsed",
)

# 
# CSS – Apple dark mode (macOS style)
# 
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=SF+Mono:wght@400;500&display=swap');

    /* Ukryj sidebar */
    [data-testid="stSidebar"] { display: none; }
    
    /* Górna nawigacja */
    .top-nav {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: #000000;
        border-bottom: 1px solid rgba(255, 255, 255, 0.1);
        padding: 0 32px;
        height: 44px;
        display: flex;
        align-items: center;
        justify-content: space-between;
        z-index: 9999;
    }
    .top-nav-logo {
        font-size: 16px;
        font-weight: 600;
        color: #f5f5f7;
        letter-spacing: -0.3px;
        min-width: 180px;
    }
    .top-nav-menu {
        display: flex;
        gap: 28px;
        align-items: center;
        flex: 1;
        justify-content: center;
    }
    .top-nav-item {
        font-size: 14px;
        color: #f5f5f7;
        text-decoration: none;
        opacity: 0.8;
        transition: opacity 0.2s;
        cursor: pointer;
        padding: 4px 0;
        white-space: nowrap;
    }
    .top-nav-item:hover {
        opacity: 1;
    }
    .top-nav-item.active {
        opacity: 1;
        font-weight: 600;
    }
    .top-nav-status {
        display: flex;
        align-items: center;
        gap: 12px;
        font-size: 12px;
        min-width: 180px;
        justify-content: flex-end;
    }
    .status-badge {
        padding: 4px 10px;
        border-radius: 4px;
        font-weight: 600;
        font-size: 11px;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    .status-active {
        background: #16a34a;
        color: white;
    }
    .status-inactive {
        background: #dc2626;
        color: white;
    }

    /*  Tło i font (Apple dark)  */
    .stApp {
        background: #0a0a0a;
        color: #f5f5f7;
        font-family: -apple-system, BlinkMacSystemFont, 'Inter', 'SF Pro Text', sans-serif;
        padding-top: 44px;
        min-height: 100vh;
    }
    .main .block-container { 
        padding: 2rem 3rem 10rem 3rem; 
        max-width: 100%; 
        min-height: 100vh;
    }

    /*  Ticker bar  */
    .ticker-wrapper {
        background: linear-gradient(90deg, #0d1321, #111827, #0d1321);
        border-bottom: 1px solid #1e3a5f;
        padding: 8px 0;
        overflow: hidden;
        position: sticky;
        top: 0;
        z-index: 999;
        margin: -1rem -2rem 1.5rem -2rem;
    }
    .ticker-track {
        display: flex;
        animation: ticker-scroll 40s linear infinite;
        white-space: nowrap;
        width: max-content;
    }
    .ticker-track:hover { animation-play-state: paused; }
    @keyframes ticker-scroll {
        0%   { transform: translateX(0); }
        100% { transform: translateX(-50%); }
    }
    .ticker-item {
        display: inline-flex;
        align-items: center;
        padding: 0 24px;
        font-family: 'JetBrains Mono', monospace;
        font-size: 12px;
        border-right: 1px solid #1e3a5f;
        gap: 8px;
    }
    .ticker-symbol { color: #93c5fd; font-weight: 600; }
    .ticker-price  { color: #e2e8f0; }
    .ticker-up     { color: #34d399; }
    .ticker-down   { color: #f87171; }

    /*  Header logo  */
    .app-header {
        display: flex;
        align-items: center;
        justify-content: space-between;
        padding: 12px 0 16px 0;
        border-bottom: 1px solid #1e3a5f;
        margin-bottom: 20px;
    }
    .app-logo {
        font-size: 22px;
        font-weight: 700;
        background: linear-gradient(135deg, #3b82f6, #06b6d4);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        letter-spacing: -0.5px;
    }
    .app-mode-badge {
        font-size: 11px;
        font-weight: 600;
        padding: 4px 10px;
        border-radius: 4px;
        background: #1a2744;
        border: 1px solid #3b82f6;
        color: #93c5fd;
        letter-spacing: 1px;
        text-transform: uppercase;
    }

    /*  Sidebar  */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #0d1321 0%, #080c14 100%);
        border-right: 1px solid #1e3a5f;
    }
    [data-testid="stSidebar"] * { color: #94a3b8; }
    [data-testid="stSidebar"] .stButton button {
        background: transparent;
        border: none;
        color: #94a3b8;
        text-align: left;
        font-size: 13px;
        padding: 8px 12px;
        border-radius: 6px;
        transition: all 0.2s;
        font-family: 'Inter', sans-serif;
    }
    [data-testid="stSidebar"] .stButton button:hover {
        background: #1e3a5f33;
        color: #e2e8f0;
        border-left: 2px solid #3b82f6;
    }

    /*  Karty metryki  */
    [data-testid="metric-container"] {
        background: linear-gradient(135deg, #111827, #1a2744);
        border: 1px solid #1e3a5f;
        border-radius: 12px;
        padding: 16px;
        box-shadow: 0 4px 24px rgba(0,0,0,0.3);
        transition: transform 0.2s, box-shadow 0.2s;
    }
    [data-testid="metric-container"]:hover {
        transform: translateY(-2px);
        box-shadow: 0 8px 32px rgba(59,130,246,0.15);
        border-color: #3b82f6;
    }
    [data-testid="stMetricLabel"] { color: #64748b; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; }
    [data-testid="stMetricValue"] { color: #e2e8f0; font-weight: 700; font-size: 24px; }
    [data-testid="stMetricDelta"] { font-size: 12px; }

    /*  Karty agentów  */
    .agent-card {
        background: linear-gradient(135deg, #111827, #1a2744);
        border: 1px solid #1e3a5f;
        border-radius: 12px;
        padding: 16px;
        margin: 6px 0;
        transition: all 0.2s;
        position: relative;
        overflow: hidden;
    }
    .agent-card::before {
        content: '';
        position: absolute;
        top: 0; left: 0; right: 0;
        height: 2px;
        background: linear-gradient(90deg, #3b82f6, #06b6d4);
    }
    .agent-card:hover {
        border-color: #3b82f6;
        box-shadow: 0 4px 20px rgba(59,130,246,0.2);
        transform: translateY(-1px);
    }
    .agent-name { font-size: 14px; font-weight: 600; color: #e2e8f0; }
    .agent-status-active  { color: #34d399; font-size: 12px; }
    .agent-status-error   { color: #f87171; font-size: 12px; }
    .agent-status-idle    { color: #64748b; font-size: 12px; }

    /*  Sygnały  */
    .signal-card {
        background: #111827;
        border: 1px solid #1e3a5f;
        border-radius: 10px;
        padding: 12px 16px;
        margin: 4px 0;
        display: flex;
        align-items: center;
        gap: 12px;
        transition: all 0.2s;
    }
    .signal-card:hover { border-color: #3b82f6; background: #1a2744; }
    .signal-long  { border-left: 3px solid #34d399; }
    .signal-short { border-left: 3px solid #f87171; }
    .signal-dir-long  { color: #34d399; font-weight: 700; font-size: 13px; }
    .signal-dir-short { color: #f87171; font-weight: 700; font-size: 13px; }

    /*  Tabele  */
    .stDataFrame { border-radius: 10px; overflow: hidden; }
    [data-testid="stDataFrameResizable"] {
        border: 1px solid #1e3a5f;
        border-radius: 10px;
    }

    /*  Przyciski  */
    .stButton button {
        background: linear-gradient(135deg, #1d4ed8, #1e40af);
        color: white;
        border: none;
        border-radius: 8px;
        font-weight: 500;
        font-family: 'Inter', sans-serif;
        transition: all 0.2s;
    }
    .stButton button:hover {
        background: linear-gradient(135deg, #2563eb, #1d4ed8);
        box-shadow: 0 4px 12px rgba(59,130,246,0.4);
        transform: translateY(-1px);
    }

    /*  Navigation buttons — prevent text wrapping  */
    [data-testid="column"] .stButton button {
        white-space: nowrap;
        min-width: 90px;
        font-size: 12px;
        padding: 4px 8px;
        background: transparent;
        border: none;
        color: #f5f5f7;
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    [data-testid="column"] .stButton button:hover {
        background: rgba(255,255,255,0.08);
        box-shadow: none;
        transform: none;
        color: #fff;
    }

    /*  Emergency button  */
    .emergency-btn button {
        background: linear-gradient(135deg, #dc2626, #b91c1c) !important;
        color: white !important;
        font-size: 18px !important;
        font-weight: bold !important;
        border-radius: 10px !important;
        width: 100%;
        padding: 18px;
        box-shadow: 0 0 20px rgba(220,38,38,0.4);
    }

    /*  Badges  */
    .badge-active   { color: #34d399; font-weight: 600; font-size: 12px; }
    .badge-error    { color: #f87171; font-weight: 600; font-size: 12px; }
    .badge-disabled { color: #475569; font-weight: 600; font-size: 12px; }

    /*  AI Chat  */
    .chat-user {
        background: linear-gradient(135deg, #1d4ed822, #1e40af22);
        border: 1px solid #1d4ed844;
        border-radius: 12px 12px 4px 12px;
        padding: 10px 14px;
        margin: 6px 0 6px 40px;
        font-size: 14px;
    }
    .chat-bot {
        background: #111827;
        border: 1px solid #1e3a5f;
        border-radius: 12px 12px 12px 4px;
        padding: 10px 14px;
        margin: 6px 40px 6px 0;
        font-size: 14px;
    }
    .chat-container { max-height: 450px; overflow-y: auto; }

    /*  Nagłówki  */
    h1 { font-size: 22px !important; font-weight: 700 !important; color: #e2e8f0 !important; }
    h2 { font-size: 17px !important; font-weight: 600 !important; color: #cbd5e1 !important; }
    h3 { font-size: 15px !important; font-weight: 600 !important; color: #94a3b8 !important; }

    /*  Separator  */
    hr { border: none; border-top: 1px solid #1e3a5f; margin: 16px 0; }

    /*  Expander  */
    [data-testid="stExpander"] {
        background: #111827;
        border: 1px solid #1e3a5f;
        border-radius: 10px;
    }

    /*  Input  */
    .stTextInput input, .stSelectbox select, .stNumberInput input {
        background: #111827 !important;
        border: 1px solid #1e3a5f !important;
        color: #e2e8f0 !important;
        border-radius: 8px !important;
    }

    /*  Scrollbar  */
    ::-webkit-scrollbar { width: 6px; height: 6px; }
    ::-webkit-scrollbar-track { background: #0d1321; }
    ::-webkit-scrollbar-thumb { background: #1e3a5f; border-radius: 3px; }
    ::-webkit-scrollbar-thumb:hover { background: #3b82f6; }

    /*  Login page  */
    .login-card {
        background: linear-gradient(135deg, #111827, #1a2744);
        border: 1px solid #1e3a5f;
        border-radius: 16px;
        padding: 40px;
        box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    }

    /*  Ticker  */
    .ticker-wrapper {
        width: 100%;
        overflow: hidden;
        background: #050a12;
        border-bottom: 1px solid #1e3a5f;
        padding: 6px 0;
        margin-bottom: 8px;
    }
    .ticker-track {
        display: flex;
        animation: ticker-scroll 40s linear infinite;
        white-space: nowrap;
    }
    .ticker-track:hover { animation-play-state: paused; }
    @keyframes ticker-scroll {
        0%   { transform: translateX(0); }
        100% { transform: translateX(-50%); }
    }
    .ticker-item {
        display: inline-flex;
        align-items: center;
        gap: 6px;
        padding: 0 20px;
        border-right: 1px solid #1e3a5f;
        font-size: 13px;
        font-family: 'JetBrains Mono', monospace;
    }
    .ticker-symbol { color: #93c5fd; font-weight: 700; }
    .ticker-price  { color: #e2e8f0; }
    .ticker-up     { color: #34d399; }
    .ticker-down   { color: #f87171; }
</style>
""", unsafe_allow_html=True)


# 
# Session state – inicjalizacja
# 
def _init_session() -> None:
    defaults = {
        "logged_in":    False,
        "token":        None,
        "username":     "",
        "active_page":  "Dashboard",
        "chat_history": [],
        "api_base":     "http://localhost:8000/api",
    }
    for k, v in defaults.items():
        if k not in st.session_state:
            st.session_state[k] = v

_init_session()


# 
# HTTP helper
# 
import requests
import random
import time as _time
from datetime import timezone as _tz
import datetime as _datetime_module

#  Konwersja czasu UTC → Polska 
_POLAND_OFFSET = _datetime_module.timedelta(hours=2)  # UTC+2 lato / UTC+1 zima

def _to_poland_time(dt) -> _datetime_module.datetime:
    """Konwertuje datetime UTC na czas polski."""
    import datetime as _dt
    if dt is None:
        return dt
    if isinstance(dt, str):
        try:
            dt = _dt.datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except Exception:
            return dt
    if hasattr(dt, 'tzinfo') and dt.tzinfo is not None:
        # Już ma strefę — konwertuj na UTC potem +2
        import calendar
        utc_ts = calendar.timegm(dt.timetuple())
        dt = _dt.datetime.utcfromtimestamp(utc_ts)
    return dt + _POLAND_OFFSET

def _fmt_poland(dt, fmt: str = "%d.%m %H:%M") -> str:
    """Formatuje datetime jako czas polski."""
    try:
        pl = _to_poland_time(dt)
        if isinstance(pl, _datetime_module.datetime):
            return pl.strftime(fmt)
    except Exception:
        pass
    return str(dt)

def _convert_timestamps_to_poland(timestamps: list) -> list:
    """Konwertuje listę timestamps na czas polski."""
    return [_to_poland_time(t) for t in timestamps]

def _headers() -> dict:
    return {"Authorization": f"Bearer {st.session_state.token}"}

def _api_online() -> bool:
    """Zwraca czy API jest dostępne — na podstawie tokenu."""
    return st.session_state.get("api_online", False)

def _get(path: str) -> dict | list | None:
    if not _api_online():
        return None
    try:
        r = requests.get(
            f"{st.session_state.api_base}{path}",
            headers=_headers(), timeout=2
        )
        if r.status_code == 200:
            return r.json()
        return None
    except Exception:
        st.session_state.api_online = False
        return None

def _get_status() -> dict:
    """Cache statusu — jedno zapytanie na odświeżenie strony."""
    if "cached_status" not in st.session_state:
        st.session_state.cached_status = _get("/status") or {}
    return st.session_state.cached_status


def _is_viewer() -> bool:
    """Zwraca True jeśli zalogowany jako viewer (read-only)."""
    return st.session_state.get("role", "admin") == "viewer"


_REFRESH_OPTIONS = {
    "5s": 5_000, "10s": 10_000, "30s": 30_000,
    "1 min": 60_000, "5 min": 300_000, "15 min": 900_000, "Wyłączony": 0
}


def _page_autorefresh(page_key: str, default: str = "30s") -> None:
    """Renderuje mini-kontrolkę auto-refresh dla bieżącej zakładki."""
    from streamlit_autorefresh import st_autorefresh
    key = f"refresh_{page_key}"
    if key not in st.session_state:
        st.session_state[key] = default
    col1, col2 = st.columns([6, 1])
    with col2:
        selected = st.selectbox(
            "",
            options=list(_REFRESH_OPTIONS.keys()),
            index=list(_REFRESH_OPTIONS.keys()).index(st.session_state[key]),
            key=f"sel_{page_key}",
            label_visibility="collapsed",
        )
        st.session_state[key] = selected
    ms = _REFRESH_OPTIONS[selected]
    if ms > 0:
        st_autorefresh(interval=ms, key=f"ar_{page_key}")

def _post(path: str, data: dict) -> dict | None:
    try:
        r = requests.post(
            f"{st.session_state.api_base}{path}",
            json=data, headers=_headers(), timeout=5
        )
        if r.status_code == 200:
            return r.json()
        else:
            return {"error": f"HTTP {r.status_code}: {r.text[:200]}"}
    except Exception as e:
        return {"error": str(e)}

def _put(path: str, data: dict) -> dict | None:
    try:
        r = requests.put(
            f"{st.session_state.api_base}{path}",
            json=data, headers=_headers(), timeout=10
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


# 
# Strona logowania
# 


# 
# Ticker bar + Header
# 

_TICKER_DATA = [
    # ETF-y
    ("SPY",   445.22, +0.82), ("QQQ",  375.18, +1.24), ("IWM",  195.44, -0.31),
    ("DIA",   384.90, +0.55), ("ARKK",  48.32, -1.10), ("TQQQ",  55.80, +3.62),
    # Mega-cap
    ("AAPL",  175.43, +0.63), ("MSFT",  421.10, +0.92), ("NVDA",  481.50, +2.15),
    ("GOOGL", 176.22, +0.44), ("AMZN",  186.30, +1.10), ("META",  512.40, +1.88),
    ("TSLA",  246.80, -1.42),
    # Crypto ETF / indeksy
    ("COIN",  226.30, +3.41), ("MSTR",  185.40, +5.20), ("BITO",  24.80, +2.10),
    # Inne popularne
    ("AMD",   166.20, +1.55), ("PLTR",   25.80, +2.30), ("SOFI",   8.42, -0.80),
    # Crypto (symulowane)
    ("BTC/USD", 67420, +2.14), ("ETH/USD", 3480, +1.88), ("SOL/USD", 158, +3.20),
    ("BNB/USD",  580,  +0.95), ("XRP/USD", 0.52, -0.44), ("DOGE/USD", 0.14, +1.20),
]

def _render_ticker() -> None:
    """Renderuje przewijający się ticker w stylu Bloomberg/Fox Business."""
    items_html = ""
    for symbol, base_price, base_chg in _TICKER_DATA:
        noise    = random.uniform(-0.3, 0.3)
        price    = base_price * (1 + noise * 0.001)
        chg      = base_chg + noise * 0.1
        chg_cls  = "ticker-up" if chg >= 0 else "ticker-down"
        chg_sign = "+" if chg >= 0 else ""
        arrow    = "&#9650;" if chg >= 0 else "&#9660;"

        if price < 1:
            price_str = f"${price:.4f}"
        elif price < 100:
            price_str = f"${price:.2f}"
        elif price > 1000:
            price_str = f"${price:,.0f}"
        else:
            price_str = f"${price:.2f}"

        items_html += (
            f'<div class="ticker-item">'
            f'<span class="ticker-symbol">{symbol}</span>'
            f'<span class="ticker-price">{price_str}</span>'
            f'<span class="{chg_cls}">{arrow} {chg_sign}{chg:.2f}%</span>'
            f'</div>'
        )

    double_items = items_html + items_html

    html = (
        '<div class="ticker-wrapper">'
        '<div class="ticker-track">'
        + double_items +
        '</div></div>'
    )

    st.markdown(html, unsafe_allow_html=True)


def _render_header() -> None:
    """Renderuje header z logo i statusem trybu."""
    status     = _get_status() if st.session_state.logged_in else {}
    paper_mode = status.get("paper_mode", True) if status else True
    estop      = status.get("emergency_stop", False) if status else False

    import datetime
    now_str = datetime.datetime.now().strftime("%H:%M:%S")

    col_logo, col_right = st.columns([3, 1])
    with col_logo:
        st.markdown(
            '<span style="font-size:22px;font-weight:700;background:linear-gradient(135deg,#3b82f6,#06b6d4);'
            '-webkit-background-clip:text;-webkit-text-fill-color:transparent;"> IBKR Trading System</span>'
            '&nbsp;&nbsp;<span style="color:#475569;font-size:12px;">Multi-Agent AI</span>',
            unsafe_allow_html=True,
        )
    with col_right:
        mode_color = "#34d399" if paper_mode else "#ef4444"
        mode_text  = " PAPER" if paper_mode else " REAL"
        estop_text = "   E-STOP" if estop else ""
        st.markdown(
            f'<div style="text-align:right;font-size:12px;">'
            f'<span style="color:{mode_color};font-weight:600;">{mode_text}</span>'
            f'<span style="color:#ef4444;">{estop_text}</span>'
            f'<span style="color:#475569;margin-left:8px;">{now_str}</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
    st.markdown('<hr style="margin:8px 0 16px 0;border:none;border-top:1px solid #1e3a5f;">', unsafe_allow_html=True)


def page_login() -> None:
    _render_ticker()
    col1, col2, col3 = st.columns([1, 1.2, 1])
    with col2:
        st.markdown("""
        <div class="login-card">
            <div style="text-align:center;margin-bottom:24px;">
                <div style="font-size:48px;"></div>
                <div style="font-size:24px;font-weight:700;background:linear-gradient(135deg,#3b82f6,#06b6d4);
                    -webkit-background-clip:text;-webkit-text-fill-color:transparent;">
                    IBKR Trading System
                </div>
                <div style="color:#475569;font-size:13px;margin-top:4px;">Multi-Agent AI Platform</div>
            </div>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("")
        username = st.text_input("Login", value="admin", placeholder="Nazwa użytkownika")
        password = st.text_input("Hasło", type="password", placeholder="Hasło")
        st.markdown("")
        if st.button("Zaloguj się", use_container_width=True, type="primary"):
            try:
                r = requests.post(
                    f"{st.session_state.api_base}/auth/token",
                    data={"username": username, "password": password},
                    timeout=5,
                )
                if r.status_code == 200:
                    st.session_state.token     = r.json()["access_token"]
                    st.session_state.logged_in = True
                    st.session_state.username  = username
                    st.rerun()
                else:
                    st.error("Nieprawidłowy login lub hasło")
            except Exception as e:
                st.warning(f"Nie można połączyć z API: {e}\n\nUruchom system: `python main.py`")


# 
# Sidebar nawigacja
# 
PAGES = {
    "Dashboard":       "Dashboard",
    "Agenci":          "Agenci",
    "Pozycje":         "Pozycje",
    "Zlecenia":       "Transakcje",
    "Sygnały":         "Sygnały",
    "Ryzyko":         "Ryzyko",
    "Wyniki":          "Wydajność",
    "Szef / Ranking":  "Szef",
    "Krypto":           "Krypto",
    "Rynki":           "Rynki",
    "Fundamenty":      "Fundamenty",
    "Newsy":           "Newsy",
    "Backtester":      "Backtester",
    "Sesja Testowa":   "SesjaTestowa",
    "AI Chat":         "AI Chat",
    "Logi":            "Logi",
    "Użytkownicy":     "Uzytkownicy",
    "Emergency Stop":  "Emergency",
}

def render_top_nav() -> None:
    """Minimalistyczna nawigacja w stylu Apple z dropdown."""
    status = _get_status() if st.session_state.logged_in else {}
    agents_running = status.get("agents_running", True) if status else True
    current_page = st.session_state.get("active_page", "Dashboard")
    
    # Główne zakładki (zawsze widoczne - małe przyciski)
    main_pages = [
        ("Dashboard", "Dashboard"),
        ("Agenci", "Agenci"),
        ("Pozycje", "Pozycje"),
        ("Zlecenia", "Transakcje"),
        ("Sygnały", "Sygnały"),
        ("Wyniki", "Wydajność"),
        ("Szef", "Szef"),
    ]
    
    # Dodatkowe zakładki (w dropdown)
    more_pages = [
        ("Ryzyko", "Ryzyko"),
        ("Newsy", "Newsy"),
        ("AI Chat", "AI Chat"),
        ("Paper Session", "Paper Session"),
        ("Backtester", "Backtester"),
        ("Fundamentals", "Fundamentals"),
        ("Rynki", "Rynki"),
        ("Krypto", "Krypto"),
        ("Logi", "Logi"),
        # ── DEV PANEL ──────────────────────────────
        ("Dev Monitor",  "Dev Monitor"),
        ("PnL Timeline", "PnL Timeline"),
        ("Logi PRO",     "Logi PRO"),
        ("Sygnały PRO",  "Sygnały PRO"),
        ("System Health","System Health"),
        ("Export",       "Export"),
    ]
    if not _is_viewer():
        more_pages += [("Użytkownicy", "Uzytkownicy"), ("Emergency", "Emergency")]
    
    # Layout
    col_logo, col_nav, col_more, col_status = st.columns([1.2, 5.5, 1.3, 1.5])
    
    # Logo
    with col_logo:
        st.markdown("<div style='padding:6px 0;font-weight:600;font-size:14px;color:#f5f5f7;'>IBKR Trading</div>", unsafe_allow_html=True)
    
    # Główne przyciski (małe, płaskie)
    with col_nav:
        nav_cols = st.columns(len(main_pages))
        for i, (label, key) in enumerate(main_pages):
            with nav_cols[i]:
                is_active = key == current_page
                if is_active:
                    # Aktywna zakładka - primary button ale mniejszy
                    st.markdown(f"<div style='text-align:center;padding:8px 0;'><span style='color:#3b82f6;font-weight:600;font-size:12px;border-bottom:2px solid #3b82f6;padding-bottom:6px;'>{label}</span></div>", unsafe_allow_html=True)
                else:
                    if st.button(label, key=f"nav_{key}", use_container_width=True):
                        st.session_state.active_page = key
                        st.rerun()
    
    # Dropdown "Więcej"
    with col_more:
        more_labels = [label for label, _ in more_pages]
        current_in_more = any(key == current_page for _, key in more_pages)
        
        # Callback do zmiany strony
        def change_page_from_dropdown():
            selected = st.session_state.nav_dropdown
            if selected and selected != "Więcej ▾":
                for label, key in more_pages:
                    if label == selected:
                        st.session_state.active_page = key
                        break
        
        # Ustaw index na aktualną stronę jeśli jest w dropdown
        default_idx = 0
        if current_in_more:
            for idx, (label, key) in enumerate(more_pages):
                if key == current_page:
                    default_idx = idx + 1
                    break
        
        st.selectbox(
            "More",
            ["Więcej ▾"] + more_labels,
            index=default_idx,
            key="nav_dropdown",
            label_visibility="collapsed",
            on_change=change_page_from_dropdown
        )
    
    # Status + user
    with col_status:
        badge_color = "#16a34a" if agents_running else "#dc2626"
        status_text = "●" if agents_running else "●"
        st.markdown(
            f'<div style="text-align:right;padding:8px 0;font-size:12px;">'
            f'<span style="color:{badge_color};margin-right:8px;">{status_text}</span>'
            f'<span style="color:#86efac;font-weight:500;">{st.session_state.username}</span>'
            f'</div>',
            unsafe_allow_html=True
        )
    
    st.markdown("<div style='border-bottom:1px solid rgba(255,255,255,0.1);margin:8px 0 24px 0;'></div>", unsafe_allow_html=True)


# 
# Strony
# 

def page_dashboard() -> None:
    _page_autorefresh("dashboard", "30s")
    st.title("Dashboard")

    #  Pasek cenowy 
    _render_price_bar()

    status = _get_status()
    if not status:
        st.warning(" Brak połączenia z API. Uruchom `python main.py`")
        _render_demo_dashboard()
        return
    _render_live_dashboard(status)


def _render_price_bar() -> None:
    """Pasek z live cenami — Polygon dla akcji, Binance dla krypto."""
    import time

    cache_key = "price_bar_data"
    cache_ts  = "price_bar_ts"
    now = time.time()

    if cache_key not in st.session_state or (now - st.session_state.get(cache_ts, 0)) > 30:
        # Pobierz przez API backendu
        stock_syms  = ["AAPL","MSFT","NVDA","TSLA","META","GOOGL","SPY","QQQ","AMZN"]
        crypto_syms = ["BTC","ETH","DOGE"]

        prices = {}

        # Akcje przez Polygon
        if _api_online():
            try:
                import requests as _req
                from config.settings import get_settings
                key = get_settings().polygon_api_key
                for sym in stock_syms:
                    try:
                        r = _req.get(
                            f"https://api.polygon.io/v2/last/trade/{sym}?apiKey={key}",
                            timeout=2
                        )
                        if r.status_code == 200:
                            p = r.json().get("results", {}).get("p", 0)
                            if p:
                                prices[sym] = float(p)
                    except Exception:
                        pass
            except Exception:
                pass

            # Krypto przez Binance
            try:
                import requests as _req
                r = _req.get(
                    "https://api.binance.com/api/v3/ticker/price"
                    "?symbols=[%22BTCUSDT%22,%22ETHUSDT%22,%22DOGEUSDT%22]",
                    timeout=3
                )
                if r.status_code == 200:
                    for item in r.json():
                        sym_map = {"BTCUSDT":"BTC","ETHUSDT":"ETH","DOGEUSDT":"DOGE"}
                        sym = sym_map.get(item["symbol"])
                        if sym:
                            prices[sym] = float(item["price"])
            except Exception:
                pass

        # Fallback demo
        if not prices:
            prices = {
                "AAPL":175.0,"MSFT":420.0,"NVDA":480.0,"TSLA":245.0,
                "META":510.0,"GOOGL":175.0,"SPY":445.0,"QQQ":375.0,
                "BTC":62000.0,"ETH":3200.0,"DOGE":0.12,"AMZN":185.0,
            }

        st.session_state[cache_key] = prices
        st.session_state[cache_ts]  = now
    else:
        prices = st.session_state[cache_key]

    if not prices:
        return

    items = ""
    for sym, price in prices.items():
        if price >= 1000:   price_str = f"${price:,.0f}"
        elif price >= 1:    price_str = f"${price:.2f}"
        else:               price_str = f"${price:.4f}"
        color = "#f59e0b" if sym in ("BTC","ETH","DOGE") else "#93c5fd"
        items += (
            f'<span style="margin:0 16px;white-space:nowrap;">'
            f'<span style="color:{color};font-weight:700;">{sym}</span>'
            f'<span style="color:#e2e8f0;font-family:monospace;margin-left:6px;">{price_str}</span>'
            f'</span>'
        )

    st.markdown(
        f'<div style="background:#050a12;border:1px solid #1e3a5f;border-radius:8px;'
        f'padding:10px 16px;margin-bottom:16px;overflow-x:auto;white-space:nowrap;'
        f'font-size:13px;scrollbar-width:thin;">'
        f'<span style="color:#34d399;margin-right:12px;font-size:11px;"> LIVE</span>'
        f'{items}'
        f'</div>',
        unsafe_allow_html=True,
    )


def _render_candle_charts() -> None:
    """3 wykresy świecowe — wybrane przez użytkownika."""
    import plotly.graph_objects as go
    import requests as _req
    import datetime as _dt
    import time

    # Domyślne symbole
    default_syms = ["AAPL", "NVDA", "BTC"]
    all_syms = [
        "AAPL","MSFT","NVDA","TSLA","META","GOOGL","AMZN","SPY","QQQ",
        "AMD","INTC","AVGO","COIN","MSTR","IBIT","BTC","ETH","SOL",
        "JPM","V","MA","GLD","XOM","IWM","PLTR","HOOD","DOGE",
    ]

    cols_sel = st.columns(3)
    selected = []
    for i, col in enumerate(cols_sel):
        sym = col.selectbox(
            f"Wykres {i+1}",
            all_syms,
            index=all_syms.index(default_syms[i]) if default_syms[i] in all_syms else 0,
            key=f"chart_sym_{i}",
            label_visibility="collapsed",
        )
        selected.append(sym)

    tf_col, _ = st.columns([1, 3])
    timeframe = tf_col.selectbox("Timeframe", ["1m","5m","15m","1h","4h","1d"], index=3, key="chart_tf")

    tf_map = {"1m":(1,"minute",7),"5m":(5,"minute",30),"15m":(15,"minute",30),
              "1h":(1,"hour",30),"4h":(4,"hour",60),"1d":(1,"day",365)}
    mult, span, days = tf_map.get(timeframe, (1,"hour",30))

    def _fetch_candles(symbol: str) -> dict:
        cache_key = f"candle_{symbol}_{timeframe}"
        ts_key    = f"candle_ts_{symbol}_{timeframe}"
        now = time.time()
        if cache_key in st.session_state and (now - st.session_state.get(ts_key, 0)) < 60:
            return st.session_state[cache_key]
        try:
            from config.settings import get_settings
            key  = get_settings().polygon_api_key
            end  = _dt.date.today().isoformat()
            start = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
            r = _req.get(
                f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{mult}/{span}/{start}/{end}"
                f"?adjusted=true&sort=asc&limit=200&apiKey={key}",
                timeout=5,
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                if results:
                    import pandas as pd
                    df = pd.DataFrame(results)
                    df["t"] = pd.to_datetime(df["t"], unit="ms")
                    data = {"t": df["t"].tolist(), "o": df["o"].tolist(),
                            "h": df["h"].tolist(), "l": df["l"].tolist(),
                            "c": df["c"].tolist()}
                    st.session_state[cache_key] = data
                    st.session_state[ts_key]    = now
                    return data
        except Exception:
            pass
        # Demo fallback
        import random, pandas as pd
        base  = {"AAPL":175,"MSFT":420,"NVDA":480,"TSLA":245,"META":510,
                 "BTC":62000,"ETH":3200,"SPY":445,"QQQ":375}.get(symbol, 100)
        n     = 60
        dates = pd.date_range(end=_dt.datetime.now(), periods=n, freq="1h")
        price = float(base)
        o,h,l,c = [],[],[],[]
        for _ in range(n):
            op = price
            cl = round(price + random.gauss(0, base*0.008), 2)
            o.append(round(op,2)); c.append(round(cl,2))
            h.append(round(max(op,cl)+abs(random.gauss(0,base*0.003)),2))
            l.append(round(min(op,cl)-abs(random.gauss(0,base*0.003)),2))
            price = cl
        return {"t": dates.tolist(), "o":o, "h":h, "l":l, "c":c}

    chart_cols = st.columns(3)
    for i, (col, sym) in enumerate(zip(chart_cols, selected)):
        with col:
            data = _fetch_candles(sym)
            if not data or not data.get("t"):
                st.warning(f"Brak danych {sym}")
                continue

            last_c = data["c"][-1] if data["c"] else 0
            prev_c = data["c"][-2] if len(data["c"]) > 1 else last_c
            chg    = ((last_c - prev_c) / prev_c * 100) if prev_c else 0
            chg_col = "#34d399" if chg >= 0 else "#f87171"
            chg_sign = "+" if chg >= 0 else ""

            st.markdown(
                f'<div style="display:flex;justify-content:space-between;align-items:center;'
                f'padding:4px 2px;margin-bottom:4px;">'
                f'<span style="color:#93c5fd;font-weight:700;font-size:15px;">{sym}</span>'
                f'<span style="color:{chg_col};font-size:13px;">'
                f'{"${:,.2f}".format(last_c) if last_c >= 1 else "${:.4f}".format(last_c)}'
                f'  {chg_sign}{chg:.2f}%</span>'
                f'</div>',
                unsafe_allow_html=True,
            )

            fig = go.Figure(data=[go.Candlestick(
                x=_convert_timestamps_to_poland(data["t"]), open=data["o"], high=data["h"],
                low=data["l"], close=data["c"],
                increasing_line_color="#34d399",
                decreasing_line_color="#f87171",
                increasing_fillcolor="#34d399",
                decreasing_fillcolor="#f87171",
                line=dict(width=1),
            )])
            fig.update_layout(
                height=220,
                margin=dict(l=0, r=0, t=0, b=0),
                paper_bgcolor="#0d1321",
                plot_bgcolor="#0d1321",
                xaxis=dict(
                    showgrid=False, zeroline=False,
                    color="#475569", rangeslider_visible=False,
                    showticklabels=True, tickfont=dict(size=9),
                ),
                yaxis=dict(
                    showgrid=True, gridcolor="#1e3a5f",
                    zeroline=False, color="#475569",
                    tickfont=dict(size=9), side="right",
                ),
                showlegend=False,
            )
            st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": False})


def _render_demo_dashboard() -> None:
    st.info("Tryb demonstracyjny – dane przykładowe")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric(" Kapitał",    "$10,000",  "+$0")
    c2.metric(" Dzienny PnL","$0.00",    "0%")
    c3.metric(" Drawdown",   "0.00%",    "")
    c4.metric("Pozycje",    "0",        "")


def _render_live_dashboard(s: dict) -> None:
    acc    = s.get("account", {})
    cap    = acc.get("net_liquidation", 0)
    pnl    = s.get("daily_pnl", 0)
    dd     = s.get("drawdown_pct", 0)
    n_pos  = len(s.get("positions", {}))
    estop  = s.get("emergency_stop", False)
    paper  = s.get("paper_mode", True)

    if estop:
        st.error("Emergency Stop AKTYWNY – system wstrzymany!")
        st.markdown("---")

    #  Live metryki przez JS (aktualizowane co 2s bez przeładowania) 
    pnl_color  = "#34d399" if pnl >= 0 else "#f87171"
    pnl_sign   = "+" if pnl >= 0 else ""
    api_base   = st.session_state.get("api_base", "http://localhost:8000/api")
    token      = st.session_state.get("token", "")

    st.markdown(f"""
    <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;margin-bottom:16px;">
        <div style="background:#111827;border:1px solid #1e3a5f;border-radius:10px;padding:14px;">
            <div style="color:#64748b;font-size:11px;text-transform:uppercase;"> Kapitał</div>
            <div id="live-capital" style="color:#e2e8f0;font-size:22px;font-weight:700;">${cap:,.2f}</div>
        </div>
        <div style="background:#111827;border:1px solid #1e3a5f;border-radius:10px;padding:14px;">
            <div style="color:#64748b;font-size:11px;text-transform:uppercase;"> Dzienny PnL</div>
            <div id="live-pnl" style="color:{pnl_color};font-size:22px;font-weight:700;">{pnl_sign}${pnl:,.2f}</div>
        </div>
        <div style="background:#111827;border:1px solid #1e3a5f;border-radius:10px;padding:14px;">
            <div style="color:#64748b;font-size:11px;text-transform:uppercase;"> Drawdown</div>
            <div id="live-drawdown" style="color:#fbbf24;font-size:22px;font-weight:700;">{dd:.2f}%</div>
        </div>
        <div style="background:#111827;border:1px solid #1e3a5f;border-radius:10px;padding:14px;">
            <div style="color:#64748b;font-size:11px;text-transform:uppercase;">Pozycje</div>
            <div id="live-positions" style="color:#93c5fd;font-size:22px;font-weight:700;">{n_pos}</div>
        </div>
        <div style="background:#111827;border:1px solid #1e3a5f;border-radius:10px;padding:14px;">
            <div style="color:#64748b;font-size:11px;text-transform:uppercase;"> Tryb</div>
            <div style="color:{'#4ade80' if paper else '#ef4444'};font-size:18px;font-weight:700;">{' PAPER' if paper else ' REAL'}</div>
        </div>
    </div>

    <script>
    (function() {{
        const API  = "{api_base}";
        const TOK  = "{token}";
        const HEADERS = {{"Authorization": "Bearer " + TOK}};

        function fmt(n) {{
            return n >= 0 ? "+$" + n.toFixed(2) : "-$" + Math.abs(n).toFixed(2);
        }}

        async function update() {{
            try {{
                const r = await fetch(API + "/status", {{headers: HEADERS, signal: AbortSignal.timeout(3000)}});
                if (!r.ok) return;
                const d = await r.json();
                const acc = d.account || {{}};
                const cap = acc.net_liquidation || 0;
                const pnl = d.daily_pnl || 0;
                const dd  = d.drawdown_pct || 0;
                const pos = Object.keys(d.positions || {{}}).length;

                const el_cap = document.getElementById("live-capital");
                const el_pnl = document.getElementById("live-pnl");
                const el_dd  = document.getElementById("live-drawdown");
                const el_pos = document.getElementById("live-positions");

                if (el_cap) el_cap.textContent = "$" + cap.toLocaleString("en-US", {{minimumFractionDigits:2, maximumFractionDigits:2}});
                if (el_pnl) {{
                    el_pnl.textContent = (pnl >= 0 ? "+" : "") + "$" + Math.abs(pnl).toFixed(2);
                    el_pnl.style.color = pnl >= 0 ? "#34d399" : "#f87171";
                }}
                if (el_dd)  el_dd.textContent  = dd.toFixed(2) + "%";
                if (el_pos) el_pos.textContent = pos;
            }} catch(e) {{}}
        }}

        // Aktualizuj co 2 sekundy
        update();
        setInterval(update, 2000);
    }})();
    </script>
    """, unsafe_allow_html=True)

    #  Przełącznik Paper / Real 
    st.markdown("---")
    col_sw1, col_sw2, col_sw3 = st.columns([2, 1, 2])
    with col_sw2:
        st.markdown(
            '<div style="text-align:center;color:#64748b;font-size:12px;'
            'text-transform:uppercase;letter-spacing:1px;margin-bottom:6px;">Tryb handlu</div>',
            unsafe_allow_html=True,
        )
        if paper:
            st.markdown(
                '<div style="text-align:center;background:#052e16;border:1px solid #16a34a;'
                'border-radius:10px;padding:8px;color:#4ade80;font-weight:700;font-size:13px;">'
                ' PAPER TRADING</div>',
                unsafe_allow_html=True,
            )
            if not _is_viewer():
                if st.button(" Przełącz na REAL", use_container_width=True, key="switch_to_real"):
                    r = _post("/trading-mode/real", {})
                    if r and r.get("ok"):
                        st.warning(" Przełączono na REAL MONEY — zlecenia idą na prawdziwe konto!")
                        st.rerun()
        else:
            st.markdown(
                '<div style="text-align:center;background:#3f0d0d;border:1px solid #dc2626;'
                'border-radius:10px;padding:8px;color:#f87171;font-weight:700;font-size:13px;">'
                ' REAL TRADING</div>',
                unsafe_allow_html=True,
            )
            if not _is_viewer():
                if st.button(" Przełącz na PAPER", use_container_width=True, key="switch_to_paper"):
                    r = _post("/trading-mode/paper", {})
                    if r and r.get("ok"):
                        st.success(" Przełączono na Paper Trading")
                        st.rerun()

    st.markdown("---")

    #  Wykresy świecowe 
    _render_candle_charts()

    # Agenci – status grid
    st.subheader("Status agentów")
    agents = s.get("agents", {})
    cols   = st.columns(4)
    for i, (name, data) in enumerate(agents.items()):
        st_status = data["state"]["status"]
        alloc     = data["config"]["max_allocation_pct"]
        icon  = "[●]" if st_status == "active" else "" if st_status == "error" else ""
        cls   = "agent-status-active" if st_status == "active" else "agent-status-error" if st_status == "error" else "agent-status-idle"
        with cols[i % 4]:
            st.markdown(f"""
            <div class="agent-card">
                <div class="agent-name">{name}</div>
                <div class="{cls}">{icon} {st_status.upper()}</div>
                <div style="color:#475569;font-size:11px;margin-top:4px;">
                    Alokacja: <span style="color:#93c5fd">{alloc:.1f}%</span>
                </div>
            </div>
            """, unsafe_allow_html=True)

    st.markdown("---")

    #  Live sygnały przez JS 
    st.subheader("Ostatnie sygnały — Live")
    st.markdown(f"""
    <div id="live-signals-container">
        <div style="color:#475569;padding:20px;text-align:center;">Ładowanie sygnałów...</div>
    </div>

    <script>
    (function() {{
        const API = "{api_base}";
        const TOK = "{token}";
        const HDR = {{"Authorization": "Bearer " + TOK}};

        async function updateSignals() {{
            try {{
                const r = await fetch(API + "/signals?limit=8", {{headers: HDR, signal: AbortSignal.timeout(3000)}});
                if (!r.ok) return;
                const sigs = await r.json();
                const el = document.getElementById("live-signals-container");
                if (!el) return;

                if (!sigs || sigs.length === 0) {{
                    el.innerHTML = '<div style="color:#475569;padding:10px;">Brak sygnałów</div>';
                    return;
                }}

                let html = "";
                sigs.forEach(sig => {{
                    const dir   = sig.direction || "?";
                    const sym   = sig.symbol || "";
                    const conf  = ((sig.confidence || 0) * 100).toFixed(0);
                    const agent = (sig.agent_name || "").replace("AgentName.", "");
                    const isLong = dir === "LONG";
                    const color  = isLong ? "#34d399" : "#f87171";
                    const arrow  = isLong ? "" : "";
                    const ts     = (sig.timestamp || "").substring(11,19);
                    html += `<div style="background:#0d1321;border-left:3px solid ${{color}};border-radius:0 6px 6px 0;padding:8px 12px;margin:3px 0;display:flex;align-items:center;gap:12px;">
                        <span style="color:${{color}};font-weight:700;min-width:70px">${{arrow}} ${{dir}}</span>
                        <span style="color:#93c5fd;font-weight:600;min-width:55px">${{sym}}</span>
                        <span style="color:#64748b;font-size:12px">${{agent}}</span>
                        <span style="color:#fbbf24;font-size:12px;margin-left:auto">${{conf}}%</span>
                        <span style="color:#334155;font-size:11px">${{ts}}</span>
                    </div>`;
                }});
                el.innerHTML = html;
            }} catch(e) {{}}
        }}

        updateSignals();
        setInterval(updateSignals, 3000);
    }})();
    </script>
    """, unsafe_allow_html=True)


def page_agents() -> None:
    _page_autorefresh("agents", "30s")
    st.title("Agenci")
    if _is_viewer():
        st.info(" Tryb podglądu — tylko odczyt")
    agents = _get("/agents")
    if not agents:
        st.warning("Brak danych – sprawdź połączenie z API")
        return

    # Grupowanie agentów
    TRADING_AGENTS = {
        "TrendFollower","MeanReversion","Scalper","BreakoutHunter","SentimentTrader",
        "OptionsFlow","GapTrader","MomentumSurfer","VIXTrader","DivergenceHunter","ScalpKing"
    }
    AUX_AGENTS = {
        "MarketAnalyst","NewsAnalyst","ResearchAgent","SmartMoneyTracker",
        "PerformanceReviewer","PortfolioAllocator","FundamentalsAgent",
        "EarningsWatcher","MacroAnalyst","CorrelationGuard",
        "HeatmapAnalyst","WhaleTracker","EconomicCalendar"
    }
    SYSTEM_AGENTS = {"RiskManager","Orchestrator"}

    AGENT_DESC = {
        "TrendFollower":    "Śledzi trendy EMA/ADX multi-TF",
        "MeanReversion":    "Powroty do średniej BB/RSI/Z-score",
        "Scalper":          "Szybkie impulsy wolumenowe 5m",
        "BreakoutHunter":   "Wybicia z konsolidacji S/R",
        "SentimentTrader":  "Reaguje na newsy i narrację rynku",
        "OptionsFlow":      "Śledzi unusual activity opcji",
        "GapTrader":        "Handluje lukami przy otwarciu",
        "MomentumSurfer":   "Najsilniejsze momentum ROC+RSI",
        "VIXTrader":        "Kupuje panikę, sprzedaje euforię",
        "DivergenceHunter": "Dywergencje RSI/MACD vs cena",
        "ScalpKing":        "Ultra-szybki scalp 9:30-10:45 EST",
        "MarketAnalyst":    "Analiza rynku i trendów makro",
        "NewsAnalyst":      "Klasyfikuje newsy HIGH/LOW impact",
        "ResearchAgent":    "Głęboka analiza fundamentalna",
        "SmartMoneyTracker":"Śledzi instytucjonalne przepływy",
        "PerformanceReviewer":"Recenzja wyników agentów",
        "PortfolioAllocator":"Dynamiczna alokacja kapitału",
        "EarningsWatcher":  "Monitoruje kalendarze wyników",
        "MacroAnalyst":     "Dane makro → agresywność systemu",
        "CorrelationGuard": "Wykrywa skupienie korelacji",
        "HeatmapAnalyst":   "Analiza sektorów rynku",
        "WhaleTracker":     "Tropiciel dużych transakcji",
        "EconomicCalendar": "Blokada przed Fed/NFP/CPI",
    }

    for group_name, group_set, group_icon in [
        ("Trading Boty", TRADING_AGENTS, ""),
        ("Boty Pomocnicze", AUX_AGENTS, ""),
        ("System", SYSTEM_AGENTS, ""),
    ]:
        group_agents = {k: v for k, v in agents.items() if k in group_set}
        # Do Trading trafią też boty nieznane żadnej grupie
        if group_name == "Trading Boty":
            known = TRADING_AGENTS | AUX_AGENTS | SYSTEM_AGENTS
            group_agents.update({k: v for k, v in agents.items() if k not in known})
        if not group_agents:
            continue
        st.subheader(f"{group_icon} {group_name}")

        for name, data in group_agents.items():
                cfg   = data["config"]
                state = data["state"]
                status_icon = "[ON]" if state["status"] == "active" else \
                              "[ERR]" if state["status"] == "error"  else "[OFF]"
                desc  = AGENT_DESC.get(name, "")
                # Unikalny klucz per grupa + nazwa
                key_prefix = f"{group_name}_{name}"

                with st.expander(f"{status_icon} **{name}** — {state['status']}", expanded=False):
                    if desc:
                        st.caption(desc)
                    c1, c2 = st.columns([2, 1])
                    with c1:
                        enabled = st.toggle(
                            "Włączony", value=cfg["enabled"], key=f"enabled_{key_prefix}"
                        )
                        if enabled != cfg["enabled"]:
                            ep = "/enable" if enabled else "/disable"
                            _post(f"/agents/{name}{ep}", {})
                            st.rerun()
                        alloc = st.slider(
                            "Maks. alokacja (%)", 0.0, 50.0, float(cfg["max_allocation_pct"]), 0.5,
                            key=f"alloc_{key_prefix}"
                        )
                        risk_pt = st.slider(
                            "Maks. ryzyko per trade (%)", 0.1, 5.0, float(cfg["max_risk_per_trade_pct"]), 0.1,
                            key=f"risk_{key_prefix}"
                        )
                        if not _is_viewer():
                            if st.button(" Zapisz zmiany", key=f"save_{key_prefix}"):
                                _put(f"/agents/{name}/config", {
                                    "max_allocation_pct":     alloc,
                                    "max_risk_per_trade_pct": risk_pt,
                                })
                                st.success("Zapisano")
                    with c2:
                        st.markdown(f"**Status:** `{state['status']}`")
                        st.markdown(f"**Sygnały dziś:** `{state.get('signals_today', 0)}`")
                        if state.get("last_error"):
                            st.error(f"Błąd: {state['last_error']}")
                        if state.get("last_signal"):
                            sig = state["last_signal"]
                            st.markdown("**Ostatni sygnał:**")
                            st.caption(f"{sig.get('direction')} {sig.get('symbol')} conf={sig.get('confidence', 0):.0%}")
        st.markdown("---")


def page_positions() -> None:
    _page_autorefresh("positions", "30s")
    st.title(" Otwarte pozycje")
    positions = _get("/positions")
    if not positions:
        st.info("Brak otwartych pozycji")
        return

    import pandas as pd
    rows = []
    for sym, pos in positions.items():
        rows.append({
            "Symbol":   sym,
            "Ilość":    pos["quantity"],
            "Śr. cena": f"${pos['avg_cost']:.4f}",
            "Aktualna": f"${pos['current_price']:.4f}",
            "PnL (U)":  f"${pos['unrealized_pnl']:+.2f}",
            "PnL (R)":  f"${pos['realized_pnl']:+.2f}",
            "Agent":    pos.get("agent_name", "—"),
        })
    df = pd.DataFrame(rows)
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_signals() -> None:
    _page_autorefresh("signals", "30s")
    st.title("Sygnały agentów")
    signals = _get("/signals?limit=50")
    if not signals:
        st.info("Brak sygnałów w bazie danych")
        return

    import pandas as pd
    df = pd.DataFrame(signals)
    if "confidence" in df.columns:
        df["confidence"] = df["confidence"].apply(lambda x: f"{x:.0%}")
    if "reasoning" in df.columns:
        df["reasoning"] = df["reasoning"].apply(lambda x: str(x)[:100])
    st.dataframe(df, use_container_width=True, hide_index=True)


def page_risk() -> None:
    st.title(" Zarządzanie ryzykiem")
    limits = _get("/risk")
    if not limits:
        st.warning("Brak danych")
        return

    st.markdown("### Globalne limity ryzyka")
    c1, c2 = st.columns(2)

    with c1:
        daily_loss = st.number_input(
            "Maks. dzienna strata ($)",
            min_value=10.0, max_value=100000.0,
            value=float(limits["max_daily_loss_usd"]), step=50.0
        )
        drawdown = st.number_input(
            "Maks. drawdown (%)",
            min_value=1.0, max_value=50.0,
            value=float(limits["max_drawdown_pct"]), step=0.5
        )

    with c2:
        capital = st.number_input(
            "Kapitał całkowity ($)",
            min_value=100.0, max_value=10_000_000.0,
            value=float(limits["total_capital_usd"]), step=500.0
        )
        pos_size = st.number_input(
            "Maks. rozmiar pozycji (%)",
            min_value=0.1, max_value=25.0,
            value=float(limits["max_position_size_pct"]), step=0.5
        )

    if not _is_viewer():
        if st.button(" Zapisz limity ryzyka", type="primary"):
            result = _put("/risk", {
                "max_daily_loss_usd":    daily_loss,
                "max_drawdown_pct":      drawdown,
                "total_capital_usd":     capital,
                "max_position_size_pct": pos_size,
            })
            if result and result.get("ok"):
                st.success(" Limity ryzyka zapisane")
            else:
                st.error(" Błąd zapisu")


def page_performance() -> None:
    st.title("Wyniki agentów")
    perf = _get("/performance")
    if not perf:
        st.info("Brak danych wydajnościowych (system musi być aktywny przez jakiś czas)")
        return

    import pandas as pd
    rows = []
    for agent, report in perf.items():
        rows.append({
            "Agent":          agent,
            "Status":         report.get("status", "—"),
            "Transakcje":     report.get("trade_count", 0),
            "Win Rate":       f"{report.get('win_rate', 0):.1%}",
            "Profit Factor":  f"{report.get('profit_factor', 0):.2f}",
            "Total PnL":      f"${report.get('total_pnl', 0):+.2f}",
            "Sharpe":         f"{report.get('sharpe', 0):.2f}",
        })

    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    st.markdown("---")
    st.subheader("Sugestie optymalizacji")
    for agent, report in perf.items():
        issues  = report.get("issues", [])
        suggs   = report.get("suggestions", [])
        if issues:
            with st.expander(f" {agent}", expanded=True):
                for i in issues:
                    st.warning(i)
                for s in suggs:
                    st.info(f" {s}")
                st.markdown("")
                if not _is_viewer():
                    if st.button(f" Wyślij sugestie do Szefa — {agent}",
                                 key=f"send_coach_{agent}", use_container_width=True):
                        # Wywołaj endpoint który wymusi ocenę przez CoachAgent
                        r = _post(f"/performance/send-to-coach/{agent}", {
                            "issues":      issues,
                            "suggestions": suggs,
                            "win_rate":    report.get("win_rate", 0),
                            "profit_factor": report.get("profit_factor", 0),
                        })
                        if r and r.get("ok"):
                            st.success(f" Szef otrzymał raport dla {agent} i wyciągnie konsekwencje!")
                        elif r and r.get("error"):
                            st.error(f"Błąd: {r['error']}")
                        else:
                            st.error("Błąd — sprawdź połączenie z API lub zaloguj się ponownie")


def page_news() -> None:
    st.title("Newsy rynkowe")
    news = _get("/news?limit=30")
    if not news:
        st.info("Brak newsów (NewsAnalyst musi być aktywny)")
        return

    for item in news:
        impact = item.get("impact", "LOW")
        icon   = "" if impact == "HIGH" else "[●]" if impact == "MEDIUM" else ""
        pub    = item.get("published", "")
        if hasattr(pub, "strftime"):
            pub = pub.strftime("%H:%M")
        elif isinstance(pub, str):
            pub = pub[:16]

        with st.container():
            st.markdown(
                f"{icon} **[{impact}]** `{pub}` — {item.get('title', '')}"
            )
            if item.get("summary"):
                st.caption(item["summary"][:200])
            st.markdown("---")


def _groq_direct(message: str, history: list) -> str:
    """Wywołuje Groq bezpośrednio z panelu — bez pośrednika API."""
    import os, requests as _req
    api_key = os.environ.get("GROQ_API_KEY", "")
    if not api_key:
        # Spróbuj wczytać z .env
        try:
            with open("/opt/ibkr/.env") as f:
                for line in f:
                    if line.startswith("GROQ_API_KEY="):
                        api_key = line.strip().split("=", 1)[1]
                        break
        except Exception:
            pass
    if not api_key:
        return " Brak klucza GROQ_API_KEY w .env"

    # Pobierz kontekst systemu
    status = _get("/status") or {}
    positions = _get("/positions") or []
    n_pos = len(positions) if isinstance(positions, list) else 0
    capital = status.get("account", {}).get("net_liquidation", 0)
    pnl = status.get("daily_pnl", 0)

    system_prompt = f"""Jesteś inteligentnym asystentem AI systemu automatycznego tradingu IBKR Multi-Agent Trading System.

AKTUALNY STAN SYSTEMU:
- Kapitał: ${capital:,.2f}
- Dzienny PnL: ${pnl:,.2f}
- Otwarte pozycje: {n_pos}
- Tryb: PAPER TRADING (symulacja)
- Emergency Stop: {"AKTYWNY" if status.get("emergency_stop") else "Nieaktywny"}

MOŻESZ ODPOWIADAĆ NA:
- Pytania o rynek (akcje, krypto, ETF, forex, surowce)
- Analizę techniczną (RSI, MACD, Bollinger Bands, EMA, ADX)
- Strategie tradingowe (trend following, mean reversion, scalping)
- Makroekonomię (Fed, inflacja, stopy procentowe)
- Wyniki i działanie agentów w systemie
- Zarządzanie ryzykiem
- Ogólne pytania finansowe i inwestycyjne

AGENCI: TrendFollower, MeanReversion, Scalper, BreakoutHunter, SentimentTrader, OptionsFlow, GapTrader, MomentumSurfer, VIXTrader, DivergenceHunter, ScalpKing, WhaleTracker + 12 analitycznych

Odpowiadaj po POLSKU. Bądź konkretny, pomocny i profesjonalny jak doświadczony trader."""

    messages = [{"role": "system", "content": system_prompt}]
    for h in history[-10:]:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    try:
        resp = _req.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            json={"model": "openai/gpt-oss-120b", "messages": messages, "temperature": 0.4, "max_tokens": 2000},
            timeout=30,
        )
        data = resp.json()
        if resp.status_code == 200:
            return data["choices"][0]["message"]["content"]
        else:
            return f" Błąd Groq: {data.get('error', {}).get('message', str(data))}"
    except Exception as e:
        return f" Błąd połączenia z Groq: {e}"


def page_ai_chat() -> None:
    st.title("AI Chat – asystent tradingowy")
    st.caption("Pytaj o rynek, strategie, krypto, agentów — odpowiem na wszystko ")

    # Historia czatu
    chat_container = st.container()
    with chat_container:
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                st.markdown(
                    f'<div class="chat-user"> <b>Ty:</b> {msg["content"]}</div>',
                    unsafe_allow_html=True
                )
            else:
                st.markdown(
                    f'<div class="chat-bot"> <b>AI:</b> {msg["content"]}</div>',
                    unsafe_allow_html=True
                )

    st.markdown("---")

    # Input
    with st.form("chat_form", clear_on_submit=True):
        c1, c2 = st.columns([5, 1])
        user_input = c1.text_input(
            "Wiadomość", placeholder="Np: 'co sądzisz o NVDA?', 'jak działa RSI?', 'status systemu'",
            label_visibility="collapsed"
        )
        send = c2.form_submit_button(" Wyślij", use_container_width=True)

    if send and user_input.strip():
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        with st.spinner("AI myśli…"):
            response = _groq_direct(user_input, st.session_state.chat_history[:-1])
        st.session_state.chat_history.append({"role": "assistant", "content": response})
        st.rerun()

    # Przycisk czyszczenia historii
    if st.session_state.chat_history:
        if st.button(" Wyczyść historię czatu"):
            st.session_state.chat_history = []
            st.rerun()

    # Podpowiedzi szybkich komend
    st.markdown("###  Szybkie pytania")
    quick_cmds = [
        "Co sądzisz o NVDA teraz?", "Jak działa RSI?", "Co to jest short selling?",
        "Jaki jest status systemu?", "Wyjaśnij strategię mean reversion", "Co to jest VIX?",
        "Jakie są najlepsze ETF-y?", "Co to jest market cap?", "Jak czytać wykres świecowy?",
    ]
    cols = st.columns(3)
    for i, cmd in enumerate(quick_cmds):
        if cols[i % 3].button(f" {cmd}", key=f"quick_{i}"):
            st.session_state.chat_history.append({"role": "user", "content": cmd})
            with st.spinner("…"):
                response = _groq_direct(cmd, [])
            st.session_state.chat_history.append({"role": "assistant", "content": response})
            st.rerun()


def page_logs() -> None:
    st.title("Logi systemowe")
    lines = st.slider("Liczba linii", 20, 500, 100, 10)
    logs  = _get(f"/logs?lines={lines}")

    if logs is None:
        st.warning("Brak danych")
        return

    log_text = "\n".join(logs) if isinstance(logs, list) else str(logs)
    st.code(log_text, language="")

    if st.button(" Odśwież"):
        st.rerun()


def page_backtester() -> None:
    st.title("Backtester")
    st.caption("Testuj strategie na danych historycznych (yfinance)")

    c1, c2, c3 = st.columns(3)
    symbol    = c1.text_input("Symbol", value="AAPL")
    start_dt  = c2.date_input("Od", value=__import__("datetime").date(2023, 1, 1))
    end_dt    = c3.date_input("Do",  value=__import__("datetime").date(2024, 1, 1))

    c4, c5, c6 = st.columns(3)
    agent_name = c4.selectbox("Agent", [
        "TrendFollower", "MeanReversion", "Scalper",
        "BreakoutHunter", "SentimentTrader"
    ])
    timeframe = c5.selectbox("Timeframe", ["1h", "4h", "1d", "15m"])
    capital   = c6.number_input("Kapitał ($)", 1000.0, 1_000_000.0, 10000.0, 500.0)

    col_wf, col_mc = st.columns(2)
    run_wfa = col_wf.checkbox("Walk-Forward Analysis", value=False)
    run_mc  = col_mc.checkbox("Monte Carlo (1000 sim)", value=False)

    if st.button(" Uruchom Backtest", type="primary", use_container_width=True):
        with st.spinner(f"Ładuję dane {symbol} i uruchamiam backtest…"):
            result = _post("/backtest/run", {
                "symbol":    symbol,
                "start":     str(start_dt),
                "end":       str(end_dt),
                "timeframe": timeframe,
                "agent":     agent_name,
                "capital":   capital,
                "run_wfa":   run_wfa,
                "run_mc":    run_mc,
            })

        if not result or result.get("error"):
            st.error(f" {result.get('error', 'Błąd backtestów') if result else 'Brak odpowiedzi API'}")
            st.info(" Upewnij się że system działa i `yfinance` jest zainstalowany")
            return

        bt = result.get("backtest", {})

        st.success(f" Backtest zakończony – {bt.get('total_trades', 0)} transakcji")

        # Metryki
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Zwrot",          f"{bt.get('total_return_pct', 0):+.2f}%")
        m2.metric("Sharpe",         f"{bt.get('sharpe_ratio', 0):.3f}")
        m3.metric("Max Drawdown",   f"{bt.get('max_drawdown_pct', 0):.2f}%")
        m4.metric("Win Rate",       f"{bt.get('win_rate', 0):.1%}")
        m5.metric("Profit Factor",  f"{bt.get('profit_factor', 0):.2f}")

        # Equity curve
        equity = result.get("equity_curve", [])
        if equity:
            import pandas as pd, plotly.graph_objects as go
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                y=equity, mode="lines", name="Equity",
                line=dict(color="#3fb950", width=2)
            ))
            fig.add_hline(y=capital, line_dash="dash", line_color="#8b949e")
            fig.update_layout(
                template="plotly_dark", height=350,
                title=f"Equity Curve – {agent_name} / {symbol}",
                paper_bgcolor="#0e1117", plot_bgcolor="#0e1117",
            )
            st.plotly_chart(fig, use_container_width=True)

        # WFA
        if run_wfa and result.get("wfa"):
            st.markdown("### Walk-Forward Analysis")
            wfa = result["wfa"]
            import pandas as pd
            rows = []
            for w in wfa.get("windows", []):
                rows.append({
                    "Okno": w["window"],
                    "IS Return": f"{w['is_return']:+.2f}%",
                    "OOS Return": f"{w['oos_return']:+.2f}%",
                    "IS Sharpe": f"{w['is_sharpe']:.3f}",
                    "OOS Sharpe": f"{w['oos_sharpe']:.3f}",
                })
            st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
            c1, c2 = st.columns(2)
            c1.metric("Śr. OOS Return", f"{wfa.get('avg_oos_return', 0):+.2f}%")
            c2.metric("Okna zysk/strata", f"{wfa.get('positive_windows', 0)}/{wfa.get('total_windows', 0)}")

        # Monte Carlo
        if run_mc and result.get("mc"):
            st.markdown("### Monte Carlo (1000 symulacji)")
            mc = result["mc"]
            p  = mc.get("percentiles", {})
            r  = mc.get("returns_pct",  {})
            mc1, mc2, mc3 = st.columns(3)
            mc1.metric("P50 (mediana)",    f"${p.get('p50', 0):,.0f} ({r.get('p50', 0):+.1f}%)")
            mc2.metric("P5 (pesymistyczny)", f"${p.get('p5', 0):,.0f} ({r.get('p5', 0):+.1f}%)")
            mc3.metric("P(zysk)",           f"{mc.get('prob_profitable_pct', 0):.1f}%")
            st.metric("Avg Max Drawdown MC", f"{mc.get('avg_max_drawdown_pct', 0):.2f}%")


def page_fundamentals() -> None:
    st.title(" Analiza Fundamentalna")
    st.markdown("P/E, Forward P/E, PEG, ROE i inne wskaźniki dla każdego symbolu.")
    st.markdown("---")

    # Wybór symbolu
    col1, col2 = st.columns([2, 1])
    with col1:
        symbol = st.text_input(" Symbol", value="AAPL", placeholder="np. AAPL, TSLA, NVDA").upper().strip()
    with col2:
        st.markdown("<br>", unsafe_allow_html=True)
        fetch = st.button(" Pobierz dane", use_container_width=True, type="primary")

    # Szybkie przyciski
    quick = ["AAPL", "MSFT", "NVDA", "TSLA", "GOOGL", "AMZN", "META", "AMD"]
    cols  = st.columns(len(quick))
    for i, sym in enumerate(quick):
        with cols[i]:
            if st.button(sym, use_container_width=True, key=f"q_{sym}"):
                symbol = sym
                fetch  = True

    if not fetch and not symbol:
        st.info("Wpisz symbol i kliknij 'Pobierz dane'")
        return

    with st.spinner(f"Pobieram dane dla {symbol}..."):
        # Fundamenty mogą być wolne (yfinance) — dajemy 15s
        old_online = st.session_state.get("api_online")
        data = None
        if old_online:
            try:
                r = requests.get(
                    f"{st.session_state.api_base}/fundamentals/{symbol}",
                    headers=_headers(), timeout=15
                )
                data = r.json() if r.status_code == 200 else None
            except Exception:
                data = None

    if not data or data.get("error"):
        st.error(f"Brak danych dla {symbol}. Sprawdź czy symbol jest poprawny.")
        return

    #  Header firmy 
    overall    = data.get("overall", "neutral")
    ov_color   = "#34d399" if overall == "bullish" else "#f87171" if overall == "bearish" else "#fbbf24"
    ov_text    = " BULLISH" if overall == "bullish" else " BEARISH" if overall == "bearish" else " NEUTRALNY"

    st.markdown(
        f'<div style="background:#111827;border:1px solid #1e3a5f;border-radius:12px;padding:20px;margin-bottom:16px;">'
        f'<div style="display:flex;justify-content:space-between;align-items:center;">'
        f'<div>'
        f'<div style="font-size:22px;font-weight:700;color:#e2e8f0">{data.get("company", symbol)}</div>'
        f'<div style="color:#64748b;font-size:13px">{data.get("sector","N/A")} | Cap: {data.get("market_cap_str","N/A")}</div>'
        f'</div>'
        f'<div style="text-align:right;">'
        f'<div style="font-size:28px;font-weight:700;color:#93c5fd">${data.get("price","N/A")}</div>'
        f'<div style="color:{ov_color};font-weight:700;font-size:14px">{ov_text}</div>'
        f'</div></div></div>',
        unsafe_allow_html=True,
    )

    #  Wskaźniki wyceny 
    st.subheader(" Wskaźniki wyceny")
    c1, c2, c3, c4, c5 = st.columns(5)

    def _metric_card(col, label, value, interpretation, good_if_low=True):
        if value is None:
            col.metric(label, "N/A")
            return
        col.metric(label, f"{value:.1f}")
        col.caption(interpretation)

    _metric_card(c1, "P/E Ratio",     data.get("pe"),          data.get("pe_signal", ""))
    _metric_card(c2, "Forward P/E",   data.get("forward_pe"),  "prognozowana wycena")
    _metric_card(c3, "PEG Ratio",     data.get("peg"),         data.get("peg_signal", ""))
    _metric_card(c4, "P/B Ratio",     data.get("pb"),          "cena / wartość księgowa")
    _metric_card(c5, "EV/EBITDA",     data.get("ev_ebitda"),   "wartość przedsiębiorstwa")

    st.markdown("---")
    st.subheader(" Finanse")
    f1, f2, f3, f4, f5 = st.columns(5)
    f1.metric("EPS (TTM)",     f"${data.get('eps', 'N/A')}")
    f2.metric("Forward EPS",   f"${data.get('forward_eps', 'N/A')}")
    f3.metric("Wzrost EPS",    f"{data.get('eps_growth', 'N/A')}%" if data.get('eps_growth') else "N/A")
    f4.metric("ROE",           f"{data.get('roe', 'N/A')}%" if data.get('roe') else "N/A")
    f5.metric("Marża zysku",   f"{data.get('profit_margin', 'N/A')}%" if data.get('profit_margin') else "N/A")

    d1, d2 = st.columns(2)
    d1.metric("Debt/Equity",   f"{data.get('de_ratio', 'N/A')}")
    d2.metric("Dywidenda",     f"{data.get('dividend_yield', 0):.2f}%")

    st.markdown("---")

    #  Poradnik interpretacji 
    with st.expander("Jak interpretować wskaźniki?"):
        st.markdown("""
**P/E Ratio** (Cena / Zysk na akcję)
- Mówi ile płacisz za każdy $1 zysku firmy
- P/E < 15 → tania akcja | P/E 15-25 → uczciwa | P/E > 25 → droga
- Tech firmy często mają P/E > 30 — to normalne dla sektora wzrostowego

**Forward P/E** (Cena / Prognozowany przyszły zysk)
- Bazuje na oczekiwanych zyskach, nie historycznych
- Niższy Forward P/E niż P/E → firma ma rosnące zyski — dobry sygnał

**PEG Ratio** (P/E / Stopa wzrostu EPS)
- Uwzględnia wzrost firmy — lepsza miara niż samo P/E
- PEG < 1 → akcja tania względem wzrostu [●]
- PEG 1-2 → uczciwa wycena [●]
- PEG > 2 → droga względem wzrostu 

**ROE** (Zwrot z kapitału własnego)
- Mierzy jak efektywnie firma wykorzystuje kapitał
- ROE > 15% → dobra firma | ROE > 25% → świetna firma

**Debt/Equity**
- Stosunek zadłużenia do kapitału własnego
- D/E < 1 → bezpieczna firma | D/E > 2 → wysoko zadłużona
        """)

    st.caption(f"Dane: Polygon.io / yfinance | Zaktualizowano: {_fmt_poland(data.get('updated_at',''))}")


def page_coach() -> None:
    _page_autorefresh("coach", "30s")
    st.title("Szef / Ranking Agentów")
    st.markdown("Coach ocenia każdy trade i sesję — przyznaje punkty i awansuje agentów.")
    st.markdown("---")

    ranking = _get("/coach/ranking") or []

    if not ranking:
        st.info("Brak danych. Uruchom Sesję Testową żeby Coach zaczął oceniać agentów.")
        return

    #  Overall Stats 
    total_pnl    = sum(r["total_pnl"]   for r in ranking)
    total_trades = sum(r["total_trades"] for r in ranking)

    # Tylko agenci z min. 5 tradami i realnym PnL > $1 liczą się do średniej WR
    active = [r for r in ranking if r["total_trades"] >= 5 and abs(r["total_pnl"]) > 1.0]
    avg_wr = sum(r["win_rate"] for r in active) / len(active) if active else 0

    best_trade   = max((r["best_trade"]  for r in ranking), default=0)
    worst_trade  = min((r["worst_trade"] for r in ranking), default=0)
    best_agent   = max(ranking, key=lambda r: r["best_trade"],  default={}).get("agent_name", "—")
    worst_agent  = min(ranking, key=lambda r: r["worst_trade"], default={}).get("agent_name", "—")

    pnl_color = "#34d399" if total_pnl >= 0 else "#f87171"
    pnl_sign  = "+" if total_pnl >= 0 else ""

    st.markdown(
        f'<div style="background:linear-gradient(135deg,#0f172a,#1e3a5f);'
        f'border:1px solid #1e3a5f;border-radius:14px;padding:20px;margin-bottom:16px;">'
        f'<div style="color:#93c5fd;font-size:13px;font-weight:600;margin-bottom:12px;"> OVERALL — WSZYSCY AGENCI</div>'
        f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:12px;">'
        f'<div style="text-align:center;">'
        f'<div style="color:#64748b;font-size:11px;">ŁĄCZNY PnL</div>'
        f'<div style="color:{pnl_color};font-size:22px;font-weight:700;">{pnl_sign}${total_pnl:,.2f}</div>'
        f'</div>'
        f'<div style="text-align:center;">'
        f'<div style="color:#64748b;font-size:11px;">ŚR. WIN RATE</div>'
        f'<div style="color:#e2e8f0;font-size:22px;font-weight:700;">{avg_wr:.1f}%</div>'
        f'</div>'
        f'<div style="text-align:center;">'
        f'<div style="color:#64748b;font-size:11px;">ŁĄCZNIE TRADÓW</div>'
        f'<div style="color:#e2e8f0;font-size:22px;font-weight:700;">{total_trades}</div>'
        f'</div>'
        f'<div style="text-align:center;">'
        f'<div style="color:#64748b;font-size:11px;">NAJLEPSZY TRADE</div>'
        f'<div style="color:#34d399;font-size:22px;font-weight:700;">+${best_trade:,.2f}</div>'
        f'<div style="color:#64748b;font-size:10px;">{best_agent}</div>'
        f'</div>'
        f'<div style="text-align:center;">'
        f'<div style="color:#64748b;font-size:11px;">NAJGORSZY TRADE</div>'
        f'<div style="color:#f87171;font-size:22px;font-weight:700;">${worst_trade:,.2f}</div>'
        f'<div style="color:#64748b;font-size:10px;">{worst_agent}</div>'
        f'</div>'
        f'</div></div>',
        unsafe_allow_html=True,
    )

    st.markdown("---")

    #  Podium Top 3 
    st.subheader(" Podium")
    podium_cols = st.columns(3)
    podium_order = [1, 0, 2]  # srebro, złoto, brąz
    podium_colors = ["#94a3b8", "#fbbf24", "#cd7f32"]
    podium_labels = [" 2. miejsce", " 1. miejsce", " 3. miejsce"]

    for col_idx, rank_idx in enumerate(podium_order):
        if rank_idx < len(ranking):
            r = ranking[rank_idx]
            color = podium_colors[col_idx]
            with podium_cols[col_idx]:
                st.markdown(
                    f'<div style="background:#111827;border:2px solid {color};'
                    f'border-radius:12px;padding:16px;text-align:center;">'
                    f'<div style="font-size:24px;">{r["level"].split()[0]}</div>'
                    f'<div style="color:{color};font-weight:700;font-size:15px;">{r["agent_name"]}</div>'
                    f'<div style="color:#e2e8f0;font-size:22px;font-weight:700;">{r["total_points"]} pkt</div>'
                    f'<div style="color:#64748b;font-size:12px;">{r["level"]}</div>'
                    f'<div style="color:#64748b;font-size:11px;margin-top:6px;">'
                    f'WR: {r["win_rate"]:.0f}% | PnL: ${r["total_pnl"]:+.2f}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    st.markdown("---")

    #  Pełny ranking 
    st.subheader(" Pełny ranking")

    for r in ranking:
        pnl_color  = "#34d399" if r["total_pnl"] >= 0 else "#f87171"
        streak     = r.get("current_streak", 0)
        streak_str = f" {streak}" if streak > 0 else f" {abs(streak)}" if streak < 0 else "—"
        next_lvl   = ""

        with st.expander(
            f"#{r['rank']} {r['level']}  {r['agent_name']}  —  "
            f"{r['total_points']} pkt  |  WR: {r['win_rate']:.0f}%  |  "
            f"PnL: ${r['total_pnl']:+.2f}",
            expanded=(r["rank"] == 1),
        ):
            c1, c2, c3, c4, c5 = st.columns(5)
            c1.metric(" Punkty",     r["total_points"])
            c2.metric(" Win Rate",   f"{r['win_rate']:.0f}%")
            c3.metric(" Total PnL",  f"${r['total_pnl']:+.2f}")
            c4.metric(" Seria",      streak_str)
            c5.metric(" Tradów",     r["total_trades"])

            c6, c7 = st.columns(2)
            c6.metric(" Najlepszy trade", f"${r['best_trade']:+.2f}")
            c7.metric(" Najgorszy trade", f"${r['worst_trade']:+.2f}")

            # Info o trudności zdobywania punktów
            level_mults = {
                " Nowicjusz": (1.0, "Pełne punkty za każdy zysk"),
                " Stażysta":  (0.9, "−10% nagród — rośniesz"),
                " Analityk":  (0.8, "−20% nagród — standard coraz wyższy"),
                " Trader":    (0.7, "−30% nagród — tylko dobre setupy się liczą"),
                " Senior Trader": (0.6, "−40% nagród — wymagające środowisko"),
                " Ekspert":   (0.5, "Połowa nagród — elita musi udowodnić każdy trade"),
                " Master":    (0.4, "−60% nagród — tylko mistrzowie przetrwają"),
                " Legenda":   (0.3, "−70% nagród — każdy punkt to walka"),
            }
            lv = r.get("level", " Nowicjusz")
            mult, desc = level_mults.get(lv, (1.0, ""))
            bar_pct = int(mult * 100)
            bar_color = "#34d399" if mult > 0.6 else "#fbbf24" if mult > 0.4 else "#f87171"
            st.markdown(
                f'<div style="background:#0f172a;border:1px solid #1e3a5f;border-radius:8px;'
                f'padding:10px;margin:8px 0;">'
                f'<div style="color:#64748b;font-size:11px;margin-bottom:6px;"> TRUDNOŚĆ ZDOBYWANIA PUNKTÓW</div>'
                f'<div style="display:flex;align-items:center;gap:10px;">'
                f'<div style="background:#1e3a5f;border-radius:4px;height:8px;flex:1;">'
                f'<div style="background:{bar_color};height:8px;border-radius:4px;width:{bar_pct}%;"></div></div>'
                f'<span style="color:{bar_color};font-weight:700;font-size:13px;">{bar_pct}%</span></div>'
                f'<div style="color:#94a3b8;font-size:12px;margin-top:4px;">{desc}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            # Ostatnie recenzje Szefa
            reviews = r.get("recent_reviews", [])
            if reviews:
                st.markdown("** Ostatnie oceny Szefa:**")
                for rev in reviews[:5]:
                    pts    = rev.get("points", 0)
                    pts_color = "#34d399" if pts > 0 else "#f87171"
                    st.markdown(
                        f'<div style="background:#0d1321;border-left:3px solid {pts_color};'
                        f'padding:8px 12px;border-radius:0 6px 6px 0;margin:3px 0;font-size:13px;">'
                        f'<span style="color:{pts_color};font-weight:700;">{pts:+d} pkt</span>'
                        f'&nbsp;&nbsp;<span style="color:#93c5fd">{rev.get("symbol","")}</span>'
                        f'&nbsp;<span style="color:#64748b">{rev.get("direction","")}</span>'
                        f'&nbsp;&nbsp;<span style="color:#e2e8f0">{rev.get("reason","")}</span>'
                        f'<span style="color:#334155;float:right;font-size:11px;">{rev.get("timestamp","")}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )

            # Reset
        if not _is_viewer():
            if st.button(f" Resetuj {r['agent_name']}", key=f"reset_{r['agent_name']}"):
                result = _post(f"/coach/reset/{r['agent_name']}", {})
                if result and result.get("ok"):
                    st.success(f"Zresetowano wyniki {r['agent_name']}")
                    st.rerun()

    st.markdown("---")

    #  Legenda poziomów 
    st.subheader(" Poziomy agentów")
    levels = [
        (" Nowicjusz", 0), (" Stażysta", 50), (" Analityk", 150),
        (" Trader", 300), (" Senior Trader", 500),
        (" Ekspert", 800), (" Master", 1200), (" Legenda", 2000),
    ]
    level_cols = st.columns(4)
    for i, (name, pts) in enumerate(levels):
        with level_cols[i % 4]:
            st.markdown(
                f'<div style="background:#111827;border:1px solid #1e3a5f;'
                f'border-radius:8px;padding:8px;text-align:center;margin:3px 0;">'
                f'<div style="font-size:18px;">{name.split()[0]}</div>'
                f'<div style="color:#e2e8f0;font-size:12px;font-weight:600;">{" ".join(name.split()[1:])}</div>'
                f'<div style="color:#64748b;font-size:11px;">{pts}+ pkt</div>'
                f'</div>',
                unsafe_allow_html=True,
            )


def page_transactions() -> None:
    _page_autorefresh("transactions", "30s")
    st.title("Zlecenia")

    from streamlit_autorefresh import st_autorefresh
    st_autorefresh(interval=10000, key="tx_autorefresh")

    #  Filtry 
    col1, col2, col3 = st.columns(3)
    with col1:
        mode_filter = st.selectbox("Tryb", ["Wszystkie", "Paper", "Real"], index=0)
    with col2:
        status_filter = st.selectbox("Status", ["Wszystkie", "Filled", "Submitted", "Cancelled", "Rejected"], index=0)
    with col3:
        limit = st.selectbox("Liczba rekordów", [25, 50, 100, 250], index=0)

    #  Pobierz zlecenia z API 
    orders = _get(f"/orders?limit={limit}") or []

    if mode_filter == "Paper":
        orders = [o for o in orders if o.get("paper_mode")]
    elif mode_filter == "Real":
        orders = [o for o in orders if not o.get("paper_mode")]

    if status_filter != "Wszystkie":
        orders = [o for o in orders if o.get("status", "").lower() == status_filter.lower()]

    #  Metryki podsumowania 
    total   = len(orders)
    filled  = sum(1 for o in orders if o.get("status") == "filled")
    total_pnl = sum(float(o.get("avg_price", 0)) * float(o.get("filled_qty", 0)) *
                    (1 if o.get("side") == "BUY" else -1) for o in orders if o.get("filled_qty"))

    c1, c2, c3, c4 = st.columns(4)
    c1.metric(" Łącznie zleceń", total)
    c2.metric(" Wypełnionych", filled)
    c3.metric(" Innych", total - filled)
    c4.metric(" Auto-refresh", "5s")

    st.markdown("---")

    if not orders:
        st.info("Brak transakcji. Agenci zaczną handlować gdy giełda będzie otwarta (15:30 PL).")
        return

    #  Tabela transakcji 
    st.subheader(f" Historia zleceń ({total})")

    for o in orders:
        side     = o.get("side", "")
        symbol   = o.get("symbol", "")
        status   = o.get("status", "")
        qty      = o.get("filled_qty") or o.get("quantity", 0)
        price    = o.get("avg_price") or o.get("limit_price", 0)
        paper    = o.get("paper_mode", True)
        created_raw = o.get("created_at", "")
        created     = _fmt_poland(created_raw, "%d.%m %H:%M") if created_raw else ""
        is_buy   = side.upper() == "BUY"
        border   = "#34d399" if is_buy else "#f87171"
        mode_badge = (
            '<span style="background:#052e16;color:#4ade80;font-size:10px;'
            'padding:2px 6px;border-radius:4px;margin-left:6px;">PAPER</span>'
            if paper else
            '<span style="background:#3f0d0d;color:#f87171;font-size:10px;'
            'padding:2px 6px;border-radius:4px;margin-left:6px;">REAL</span>'
        )
        status_color = {"filled": "#34d399", "submitted": "#fbbf24",
                        "cancelled": "#64748b", "rejected": "#f87171"}.get(status.lower(), "#94a3b8")

        st.markdown(
            f'<div style="background:#111827;border-left:3px solid {border};'
            f'border-radius:0 8px 8px 0;padding:10px 16px;margin:3px 0;">'
            f'<div style="display:flex;align-items:center;gap:16px;flex-wrap:wrap;">'
            f'<span style="color:{border};font-weight:700;min-width:60px">'
            f'{" BUY" if is_buy else " SELL"}</span>'
            f'<span style="color:#93c5fd;font-weight:600;min-width:60px">{symbol}</span>'
            f'<span style="color:#e2e8f0;font-family:monospace">'
            f'{float(qty):.4f} szt. @ ${float(price):.2f}</span>'
            f'<span style="color:{status_color};font-size:12px;font-weight:600">'
            f'{status.upper()}</span>'
            f'{mode_badge}'
            f'<span style="color:#334155;font-size:11px;margin-left:auto">{created}</span>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.caption(" Dane odświeżane co 5 sekund automatycznie")


def page_paper_session() -> None:
    _page_autorefresh("paper_session", "30s")
    st.title("Sesja Testowa — Paper Trading")
    st.markdown("Agenci handlują **na sucho** przez wybrany czas. Po zakończeniu widzisz pełny raport.")
    st.markdown("---")

    #  Inicjalizacja session state 
    if "ps_session_id"  not in st.session_state: st.session_state.ps_session_id  = None
    if "ps_status"      not in st.session_state: st.session_state.ps_status      = "idle"
    if "ps_report"      not in st.session_state: st.session_state.ps_report      = None
    if "ps_live_trades" not in st.session_state: st.session_state.ps_live_trades = []
    if "ps_start_time"  not in st.session_state: st.session_state.ps_start_time  = None
    if "ps_duration"    not in st.session_state: st.session_state.ps_duration    = 5

    #  Auto-wznowienie aktywnej sesji po powrocie na stronę 
    if st.session_state.ps_status == "idle" or st.session_state.ps_session_id is None:
        active_sessions = _get("/paper-sessions") or []
        running = [s for s in active_sessions if s.get("status") == "running"]
        if running:
            # Wznów ostatnią aktywną sesję
            last = running[-1]
            sid  = last["session_id"]
            st.session_state.ps_session_id  = sid
            st.session_state.ps_status      = "running"
            st.session_state.ps_live_trades = []
            import datetime as _dt
            st.session_state.ps_start_time  = _dt.datetime.now().isoformat()
            # Oszacuj czas trwania z liczby tradów
            st.session_state.ps_duration    = last.get("duration_min", 5)

    #  Konfiguracja 
    if st.session_state.ps_status == "idle":
        st.subheader(" Konfiguracja sesji")
        col1, col2 = st.columns(2)
        with col1:
            duration = st.slider("Czas trwania (minuty)", 1, 360, 5)
            st.caption(f" {duration} min = {duration//60}h {duration%60}min")
            capital  = st.number_input(" Kapitał startowy ($)", 1000, 100000, 10000, step=1000)
        with col2:
            # Pobierz listę agentów z _AGENT_PROFILES
            try:
                import sys as _sys2
                _sys2.path.insert(0, ".")
                from backtester.paper_session import _AGENT_PROFILES
                all_agent_names = sorted(_AGENT_PROFILES.keys())
            except Exception:
                all_agent_names = ["TrendFollower","MeanReversion","Scalper",
                                   "BreakoutHunter","SentimentTrader","OptionsFlow",
                                   "GapTrader","MomentumSurfer","VIXTrader",
                                   "DivergenceHunter","ScalpKing","WhaleTracker"]

            agents = st.multiselect(
                "Agenci biorący udział",
                all_agent_names,
                default=all_agent_names,
            )

            import sys as _sys
            _sys.path.insert(0, ".")
            from core.symbols import SYMBOL_NAMES, CATEGORY_LABELS

            #  Wyszukiwarka symboli 
            st.markdown("** Wybierz symbole**")

            # Pasek wyszukiwania
            sym_search = st.text_input(" Szukaj symbolu", placeholder="np. Bitcoin, BTC, ARLN, SPY...",
                                        key="ps_sym_search", label_visibility="collapsed")

            # Filtr kategorii
            cat_options = ["Wszystkie"] + list(CATEGORY_LABELS.values())
            cat_sel = st.selectbox("Kategoria", cat_options, key="ps_cat_sel", label_visibility="collapsed")
            cat_map_rev = {v: k for k, v in CATEGORY_LABELS.items()}
            cat_filter = cat_map_rev.get(cat_sel)

            # Filtruj symbole
            all_symbols_raw = list(SYMBOL_NAMES.keys())
            if sym_search:
                q = sym_search.strip().upper()
                filtered = [s for s in all_symbols_raw
                            if q in s or q in SYMBOL_NAMES[s][0].upper()]
            else:
                filtered = all_symbols_raw
            if cat_filter:
                filtered = [s for s in filtered if SYMBOL_NAMES[s][1] == cat_filter]

            # Opcje z pełnymi nazwami
            sym_display = {s: f"{s} — {SYMBOL_NAMES[s][0]}" for s in filtered[:100]}

            # Szybkie przyciski
            quick_sets = {
                " Top US":   ["AAPL","MSFT","NVDA","TSLA","META","GOOGL","AMZN","SPY","QQQ"],
                "Krypto":    ["BTC","ETH","SOL","BNB","DOGE","AVAX","XRP","ADA"],
                " GPW":      ["ARLN","PKN","PKO","PZU","CDR","LPP","KGH"],
                " ETF":       ["SPY","QQQ","IWM","TQQQ","SQQQ","GLD","IBIT"],
            }
            qcols = st.columns(6)
            for i, (label, syms) in enumerate(quick_sets.items()):
                if qcols[i].button(label, key=f"qs_{i}", use_container_width=True):
                    st.session_state["ps_selected_syms"] = syms
                    st.rerun()
            if qcols[4].button(" Wszystkie", key="qs_all", use_container_width=True):
                st.session_state["ps_selected_syms"] = all_symbols_raw
                st.rerun()
            if qcols[5].button(" Wyczyść", key="qs_clear", use_container_width=True):
                st.session_state["ps_selected_syms"] = []
                st.rerun()

            # Multiselect z pełnymi nazwami
            current_selected = st.session_state.get("ps_selected_syms",
                               ["AAPL","TSLA","NVDA","SPY","QQQ","BTC","ETH"])
            # Tylko te które są w przefiltrowanej liście lub w all_symbols_raw
            valid_default = [s for s in current_selected if s in all_symbols_raw]

            selected_display = st.multiselect(
                "Wybrane",
                options=list(sym_display.values()),
                default=[sym_display[s] for s in valid_default if s in sym_display],
                key="ps_sym_multi",
                label_visibility="collapsed",
            )
            # Wyciągnij tickery z wybranych opcji
            symbols = [opt.split(" — ")[0] for opt in selected_display]
            if symbols:
                st.session_state["ps_selected_syms"] = symbols
            st.caption(f"Wybrano: {len(symbols)} symboli")

        if st.button(" Rozpocznij Sesję Testową", type="primary", use_container_width=True):
            if not agents:
                st.error("Wybierz co najmniej jednego agenta!")
            else:
                r = _post("/paper-session/start", {
                    "duration_min":     duration,
                    "capital":          capital,
                    "selected_agents":  agents,
                    "selected_symbols": symbols,
                })
                if r and "session_id" in r:
                    import datetime as _dt
                    st.session_state.ps_session_id  = r["session_id"]
                    st.session_state.ps_status      = "running"
                    st.session_state.ps_report      = None
                    st.session_state.ps_live_trades = []
                    st.session_state.ps_start_time  = _dt.datetime.now().isoformat()
                    st.session_state.ps_duration    = duration
                    st.rerun()
                else:
                    st.error(f" Błąd startu sesji: {r}")

    #  Sesja w toku 
    elif st.session_state.ps_status == "running":
        import datetime as _dt

        sid      = st.session_state.ps_session_id
        duration = st.session_state.ps_duration

        #  Pobierz dane z API 
        data = _get(f"/paper-session/{sid}/status")
        if data:
            if data.get("status") == "done":
                st.session_state.ps_status      = "done"
                st.session_state.ps_report      = data.get("report")
                st.session_state.ps_live_trades = data.get("live_trades", [])
                st.rerun()
            else:
                st.session_state.ps_live_trades = data.get("live_trades", [])

        trades   = st.session_state.ps_live_trades
        total    = len(trades)
        open_t   = sum(1 for t in trades if t.get("status") == "OPEN")
        closed_t = total - open_t
        now      = _dt.datetime.now()
        now_str  = now.strftime("%H:%M:%S")

        #  Oblicz pozostały czas 
        start_str  = st.session_state.ps_start_time
        try:
            start_time    = _dt.datetime.fromisoformat(start_str) if start_str else now
            elapsed_sec   = (now - start_time).total_seconds()
            total_sec     = duration * 60
            remaining_sec = max(0, total_sec - elapsed_sec)
            remaining_min = int(remaining_sec // 60)
            remaining_s   = int(remaining_sec % 60)
            progress_pct  = min(1.0, elapsed_sec / max(total_sec, 1))
            time_str      = f"{remaining_min}m {remaining_s:02d}s"
            if remaining_sec == 0:
                time_str = "Kończy się..."
        except Exception:
            time_str     = "—"
            progress_pct = 0.0

        #  Oblicz PnL z zamkniętych transakcji 
        closed    = [t for t in trades if t.get("status") in ("CLOSED","EXPIRED") and t.get("pnl_usd") is not None]
        total_pnl = sum(t["pnl_usd"] for t in closed)
        pnl_color = "#34d399" if total_pnl >= 0 else "#f87171"
        pnl_sign  = "+" if total_pnl >= 0 else ""

        #  Top 3 boty 
        agent_pnl: dict[str, float] = {}
        for t in closed:
            a = t.get("agent","?")
            agent_pnl[a] = agent_pnl.get(a, 0) + t["pnl_usd"]
        top3 = sorted(agent_pnl.items(), key=lambda x: x[1], reverse=True)[:3]

        #  Render header 
        st.markdown(
            f'<div style="background:#0d1321;border:1px solid #1e3a5f;border-radius:12px;'
            f'padding:20px;margin-bottom:16px;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:12px;">'
            f'<span style="color:#93c5fd;font-weight:700;font-size:16px;"> Sesja aktywna</span>'
            f'<span style="color:#334155;font-size:12px;font-family:monospace;">{sid}</span>'
            f'</div>'
            f'<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:12px;margin-bottom:14px;">'
            f'<div style="background:#111827;border:1px solid #1e3a5f;border-radius:8px;padding:10px;text-align:center;">'
            f'<div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;">P&L</div>'
            f'<div style="color:{pnl_color};font-weight:700;font-size:20px;">{pnl_sign}${total_pnl:.2f}</div>'
            f'</div>'
            f'<div style="background:#111827;border:1px solid #1e3a5f;border-radius:8px;padding:10px;text-align:center;">'
            f'<div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;">Pozostały czas</div>'
            f'<div style="color:#fbbf24;font-weight:700;font-size:20px;">{time_str}</div>'
            f'</div>'
            f'<div style="background:#111827;border:1px solid #1e3a5f;border-radius:8px;padding:10px;text-align:center;">'
            f'<div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;">Transakcji</div>'
            f'<div style="color:#e2e8f0;font-weight:700;font-size:20px;">{total}</div>'
            f'<div style="color:#64748b;font-size:11px;">({open_t} open / {closed_t} closed)</div>'
            f'</div>'
            f'<div style="background:#111827;border:1px solid #1e3a5f;border-radius:8px;padding:10px;text-align:center;">'
            f'<div style="color:#64748b;font-size:10px;text-transform:uppercase;letter-spacing:1px;">Aktualizacja</div>'
            f'<div style="color:#93c5fd;font-weight:600;font-size:16px;font-family:monospace;">{now_str}</div>'
            f'</div>'
            f'</div>'
            f'<div style="background:#1e3a5f;border-radius:4px;height:4px;margin-bottom:14px;">'
            f'<div style="background:linear-gradient(90deg,#3b82f6,#06b6d4);height:4px;'
            f'border-radius:4px;width:{progress_pct*100:.1f}%;"></div>'
            f'</div>'
            + (
                f'<div style="border-top:1px solid #1e3a5f;padding-top:12px;">'
                f'<div style="color:#64748b;font-size:11px;text-transform:uppercase;letter-spacing:1px;margin-bottom:8px;"> Top agenci</div>'
                f'<div style="display:flex;gap:8px;">'
                + "".join([
                    f'<div style="background:#111827;border:1px solid {"#16a34a" if p>=0 else "#dc2626"};'
                    f'border-radius:8px;padding:8px 12px;flex:1;text-align:center;">'
                    f'<div style="color:#94a3b8;font-size:11px;">{a}</div>'
                    f'<div style="color:{"#34d399" if p>=0 else "#f87171"};font-weight:700;font-size:15px;">{"+" if p>=0 else ""}${p:.2f}</div>'
                    f'</div>'
                    for a, p in top3
                ])
                + f'</div></div>'
                if top3 else
                f'<div style="border-top:1px solid #1e3a5f;padding-top:12px;color:#475569;font-size:12px;text-align:center;">Czekam na zamknięte transakcje...</div>'
            )
            + f'</div>',
            unsafe_allow_html=True,
        )

        #  Przyciski kontrolne 
        col1, col2 = st.columns(2)
        with col1:
            if st.button(" Odśwież", use_container_width=True):
                st.rerun()
        with col2:
            if st.button("Zakończ i pokaż raport", use_container_width=True, type="primary"):
                data = _get(f"/paper-session/{sid}/status")
                if data:
                    st.session_state.ps_status      = "done"
                    st.session_state.ps_report      = data.get("report") or _get(f"/paper-session/{sid}/report")
                    st.session_state.ps_live_trades = data.get("live_trades", [])
                    st.rerun()

        st.markdown("---")

        #  Live feed — aktualizuje się bez odświeżania strony 
        st.subheader(f" Ostatnie działania agentów")
        trade_container = st.container()
        with trade_container:
            if trades:
                for t in reversed(trades[-40:]):
                    is_long   = t["direction"] == "LONG"
                    pnl       = t.get("pnl_usd")
                    pnl_str   = f"<b style='color:{'#34d399' if (pnl or 0)>=0 else '#f87171'}'>{'+'if(pnl or 0)>=0 else ''}${pnl:.2f}</b>" if pnl is not None else "<span style='color:#fbbf24'>otwarta</span>"
                    border    = "#34d399" if is_long else "#f87171"
                    status    = t.get("status","")
                    status_color = "#34d399" if status=="CLOSED" else "#fbbf24" if status=="OPEN" else "#64748b"

                    st.markdown(
                        f'<div style="background:#0d1321;border-left:3px solid {border};'
                        f'border-radius:0 6px 6px 0;padding:8px 12px;margin:2px 0;">'
                        f'<span style="color:{border};font-weight:700;min-width:55px;display:inline-block">{" LONG" if is_long else " SHORT"}</span>'
                        f'<span style="color:#93c5fd;font-weight:600;margin:0 8px">{t["symbol"]}</span>'
                        f'<span style="color:#64748b;font-size:12px">{t["agent"]}</span>'
                        f'<span style="color:#475569;margin:0 6px">·</span>'
                        f'<span style="color:#e2e8f0;font-family:monospace">${t["entry_price"]:.2f}</span>'
                        f'<span style="color:#475569;margin:0 6px">→</span>'
                        f'{pnl_str}'
                        f'<span style="color:{status_color};font-size:11px;margin-left:8px">[{status}]</span>'
                        f'<span style="color:#334155;font-size:11px;float:right">{t["time"]}</span>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
            else:
                st.markdown('<div style="text-align:center;color:#475569;padding:30px;">Czekam na pierwsze sygnały...</div>', unsafe_allow_html=True)

        st.caption(" Kliknij ' Odśwież' aby zaktualizować dane")

    #  Raport końcowy 
    elif st.session_state.ps_status == "done":
        report = st.session_state.ps_report
        if not report:
            st.warning("Raport jeszcze się generuje... Odśwież za chwilę.")
            if st.button(" Odśwież"):
                st.rerun()
            return

        st.success(f" Sesja zakończona! Czas trwania: **{report.get('duration_min', 0):.1f} min**")
        st.markdown("---")

        #  Metryki główne 
        st.subheader(" Podsumowanie")
        c1, c2, c3, c4, c5 = st.columns(5)
        pnl      = report.get("total_pnl_usd", 0)
        pnl_pct  = report.get("total_pnl_pct", 0)
        win_rate = report.get("win_rate_pct", 0)
        c1.metric("Łączny PnL",     f"${pnl:+.2f}",  f"{pnl_pct:+.2f}%")
        c2.metric("Transakcji",     report.get("total_trades", 0))
        c3.metric("Wygranych",      report.get("winning_trades", 0))
        c4.metric("Przegranych",    report.get("losing_trades", 0))
        c5.metric("Win Rate",       f"{win_rate:.1f}%")

        c6, c7 = st.columns(2)
        c6.metric("Najlepsza transakcja", f"${report.get('best_trade_pnl', 0):+.2f}")
        c7.metric("Najgorsza transakcja", f"${report.get('worst_trade_pnl', 0):+.2f}")

        #  Stats per agent 
        agent_stats = report.get("agent_stats", {})
        if agent_stats:
            st.markdown("---")
            st.subheader(" Wyniki per Agent")
            cols = st.columns(len(agent_stats))
            for i, (agent, stats) in enumerate(agent_stats.items()):
                with cols[i]:
                    pnl_a = stats.get("total_pnl", 0)
                    st.metric(agent, f"${pnl_a:+.2f}", f"WR: {stats.get('win_rate', 0):.0f}%")
                    st.caption(f"Tradów: {stats.get('trades', 0)} | W: {stats.get('wins', 0)} / L: {stats.get('losses', 0)}")

        #  Szczegółowe transakcje 
        st.markdown("---")
        st.subheader(" Szczegóły transakcji")

        trades = report.get("trades", [])
        closed = [t for t in trades if t.get("status") in ("CLOSED", "EXPIRED")]

        if closed:
            # Sortuj po PnL (najlepsze na górze)
            closed_sorted = sorted(closed, key=lambda x: x.get("actual_pnl_usd") or 0, reverse=True)

            for t in closed_sorted:
                pnl_t  = t.get("actual_pnl_usd") or 0
                pred   = t.get("predicted_gain_pct") or 0
                actual = t.get("actual_pnl_pct") or 0
                icon   = "[●]" if pnl_t > 0 else ""
                dir_icon = "" if t["direction"] == "LONG" else ""

                with st.expander(
                    f"{icon} {dir_icon} **{t['agent']}** | {t['symbol']} | "
                    f"PnL: **${pnl_t:+.2f}** ({actual:+.2f}%) | "
                    f"Wejście: {t.get('entry_time','?')} → Wyjście: {t.get('exit_time','?')}"
                ):
                    col_a, col_b, col_c = st.columns(3)
                    col_a.metric("Cena wejścia",   f"${t.get('entry_price', 0):.2f}")
                    col_b.metric("Cena wyjścia",   f"${t.get('exit_price', 0):.2f}" if t.get('exit_price') else "—")
                    col_c.metric("Wolumen",         f"{t.get('quantity', 0):.4f} szt.")

                    col_d, col_e = st.columns(2)
                    col_d.metric("Przewidywany zysk", f"{pred:+.2f}%")
                    col_e.metric("Rzeczywisty zysk",  f"{actual:+.2f}%",
                                 delta=f"{actual - pred:+.2f}% vs prognoza")

                    st.markdown(f"** Reasoning agenta:**")
                    st.info(t.get("reasoning", "—"))
                    st.caption(f"Pewność sygnału: {t.get('confidence', 0):.0%} | Status: {t.get('status')}")
        else:
            st.info("Brak zamkniętych transakcji w tej sesji.")

        st.markdown("---")
        if st.button(" Nowa sesja", type="primary", use_container_width=True):
            st.session_state.ps_status      = "idle"
            st.session_state.ps_session_id  = None
            st.session_state.ps_report      = None
            st.session_state.ps_live_trades = []
            st.rerun()

        #  Sekcja uczenia 
        sid = st.session_state.ps_session_id
        if sid:
            data = _get(f"/paper-session/{sid}/status")
            lessons = data.get("lessons", []) if data else []

            if lessons:
                st.markdown("---")
                st.subheader(" Czego nauczyli się agenci?")
                st.markdown("Po tej sesji każdy agent przeanalizował swoje błędy i dostosował parametry.")

                for lesson in lessons:
                    agent   = lesson.get("agent_name", "?")
                    wr      = lesson.get("win_rate", 0)
                    pnl     = lesson.get("total_pnl", 0)
                    changes = lesson.get("changes", [])
                    summary = lesson.get("summary", "")
                    params  = lesson.get("new_params", {})

                    icon = "" if pnl > 0 else ""
                    with st.expander(
                        f"{icon} **{agent}** — WR: {wr:.0f}% | PnL: ${pnl:+.2f} | "
                        f"Zmian parametrów: {len(changes)}",
                        expanded=(len(changes) > 0),
                    ):
                        # Podsumowanie słowne
                        st.markdown("** Co agent mówi o sobie:**")
                        st.info(summary)

                        # Zmiany parametrów
                        if changes:
                            st.markdown("** Zmiany parametrów:**")
                            for c in changes:
                                delta = float(c.get("new", 0)) - float(c.get("old", 0))
                                arrow = "" if delta > 0 else ""
                                st.markdown(
                                    f"{arrow} **{c['param']}**: "
                                    f"`{c['old']}` → `{c['new']}`  \n"
                                    f"_{c['reason']}_  \n"
                                    f" Efekt: {c['effect']}"
                                )
                        else:
                            st.markdown("_Brak zmian — agent uznał wyniki za akceptowalne._")

                        # Aktualne parametry
                        if params:
                            st.markdown("** Aktualne parametry agenta:**")
                            pc1, pc2, pc3, pc4 = st.columns(4)
                            pc1.metric("Min. pewność",    f"{params.get('confidence_threshold', 0.5):.0%}")
                            pc2.metric("Wielk. pozycji",  f"{params.get('position_size_mult', 1.0):.2f}x")
                            pc3.metric("Cooldown",        f"{params.get('signal_cooldown_mult', 1.0):.2f}x")
                            pc4.metric("Bias LONG",       f"{params.get('long_bias', 0.5):.0%}")

                # Przycisk do podglądu całej historii uczenia
                st.markdown("---")
                st.markdown(" Parametry zostały zapisane — będą użyte w **następnej sesji testowej**.")

                if st.button(" Pokaż historię uczenia wszystkich agentów"):
                    mem_data = _get("/paper-session/memories") or {}
                    if mem_data:
                        for ag_name, mem in mem_data.items():
                            sessions = mem.get("sessions_count", 0)
                            avg_wr   = mem.get("avg_win_rate", 0)
                            st.markdown(f"**{ag_name}**: {sessions} sesji, avg WR: {avg_wr:.0%}")


def page_markets() -> None:
    _page_autorefresh("markets", "30s")
    st.title("Rynki — GPW & LSE")

    import plotly.graph_objects as go
    import requests as _req
    import datetime as _dt
    import time

    #  Wybór rynku 
    market = st.radio("Rynek", [" GPW — Polska", " LSE — Wielka Brytania"],
                      horizontal=True, label_visibility="collapsed")
    is_gpw = "GPW" in market

    # Listy symboli
    GPW_SYMS = {
        "PKN":"PKN Orlen", "PKO":"PKO Bank Polski", "PZU":"PZU SA",
        "CDR":"CD Projekt", "ALE":"Allegro", "LPP":"LPP SA",
        "KGH":"KGHM", "MBK":"mBank", "DNP":"Dino Polska", "PEO":"Bank Pekao",
        "ING":"ING Bank Śląski", "SPL":"Santander Bank Polska",
        "OPL":"Orange Polska", "ACP":"Asseco Poland", "ARLN":"Arlen SA",
        "JSW":"JSW", "CCC":"CCC SA", "ENA":"Enea", "PGE":"PGE", "TPE":"Tauron",
    }
    LSE_SYMS = {
        "HSBA":"HSBC Holdings", "BP":"BP plc", "SHEL":"Shell plc",
        "AZN":"AstraZeneca", "GSK":"GSK plc", "BARC":"Barclays",
        "LLOY":"Lloyds Banking", "VOD":"Vodafone", "RR":"Rolls-Royce",
        "BAE":"BAE Systems", "REL":"RELX", "DGE":"Diageo",
        "ULVR":"Unilever", "RIO":"Rio Tinto", "EXPN":"Experian",
        "LGEN":"Legal & General", "PRU":"Prudential", "STAN":"Standard Chartered",
        "NWG":"NatWest Group", "BT":"BT Group",
    }
    syms = GPW_SYMS if is_gpw else LSE_SYMS
    currency = "PLN" if is_gpw else "GBX"
    flag = "" if is_gpw else ""

    st.markdown(f"### {flag} {'Warszawa (GPW)' if is_gpw else 'Londyn (LSE)'} — dane przez Polygon.io")
    st.caption(f"Waluta: {currency} | Dane z opóźnieniem ~15 min (plan darmowy)")

    #  Tabela kursów 
    st.subheader(" Kursy")

    def _get_price(symbol: str) -> dict:
        cache_key = f"mkt_{symbol}"
        ts_key    = f"mkt_ts_{symbol}"
        now = time.time()
        if cache_key in st.session_state and (now - st.session_state.get(ts_key, 0)) < 120:
            return st.session_state[cache_key]
        try:
            from config.settings import get_settings
            key = get_settings().polygon_api_key
            # Polygon: dla GPW ticker format to np. PKN dla polskich akcji
            r = _req.get(
                f"https://api.polygon.io/v2/aggs/ticker/{symbol}/prev?adjusted=true&apiKey={key}",
                timeout=5
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                if results:
                    row = results[0]
                    data = {
                        "close": row.get("c", 0),
                        "open":  row.get("o", 0),
                        "high":  row.get("h", 0),
                        "low":   row.get("l", 0),
                        "volume":row.get("v", 0),
                        "chg":   ((row.get("c",0) - row.get("o",0)) / (row.get("o",1))) * 100,
                    }
                    st.session_state[cache_key] = data
                    st.session_state[ts_key]    = now
                    return data
        except Exception:
            pass
        return {}

    # Pobierz ceny dla wszystkich symboli
    cols_header = st.columns([2, 1.5, 1, 1, 1, 1])
    cols_header[0].markdown("**Spółka**")
    cols_header[1].markdown("**Ticker**")
    cols_header[2].markdown("**Cena**")
    cols_header[3].markdown("**Zmiana**")
    cols_header[4].markdown("**High**")
    cols_header[5].markdown("**Low**")
    st.markdown("---")

    for ticker, name in syms.items():
        price_data = _get_price(ticker)
        close  = price_data.get("close", 0)
        chg    = price_data.get("chg", 0)
        high   = price_data.get("high", 0)
        low    = price_data.get("low", 0)
        chg_color = "[●]" if chg >= 0 else ""
        price_str = f"{close:,.2f}" if close else "—"
        chg_str   = f"{chg:+.2f}%" if close else "—"

        row = st.columns([2, 1.5, 1, 1, 1, 1])
        row[0].markdown(f"**{name}**")
        row[1].markdown(f"`{ticker}`")
        row[2].markdown(f"**{price_str}** {currency}")
        row[3].markdown(f"{chg_color} {chg_str}")
        row[4].markdown(f"{high:,.2f}" if high else "—")
        row[5].markdown(f"{low:,.2f}"  if low  else "—")

    st.markdown("---")

    #  Wykres świecowy 
    st.subheader(" Wykres")
    sym_options = [f"{t} — {n}" for t, n in syms.items()]
    selected = st.selectbox("Wybierz spółkę", sym_options, label_visibility="collapsed")
    symbol   = selected.split(" — ")[0]

    tf = st.select_slider("Timeframe", ["1d", "5d", "1mo", "3mo", "1y"], value="1mo",
                          label_visibility="collapsed")
    tf_map = {"1d":1, "5d":5, "1mo":30, "3mo":90, "1y":365}
    days = tf_map.get(tf, 30)

    # Pobierz świece przez Polygon
    candles = None
    cache_key = f"mkt_candle_{symbol}_{tf}"
    now = time.time()
    if cache_key in st.session_state and (now - st.session_state.get(f"{cache_key}_ts", 0)) < 300:
        candles = st.session_state[cache_key]
    else:
        try:
            from config.settings import get_settings
            key   = get_settings().polygon_api_key
            end   = _dt.date.today().isoformat()
            start = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
            mult, span = (1, "day") if days >= 30 else (1, "hour") if days >= 5 else (30, "minute")
            r = _req.get(
                f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{mult}/{span}/{start}/{end}"
                f"?adjusted=true&sort=asc&limit=300&apiKey={key}",
                timeout=8
            )
            if r.status_code == 200:
                results = r.json().get("results", [])
                if results:
                    import pandas as pd
                    df = pd.DataFrame(results)
                    df["t"] = pd.to_datetime(df["t"], unit="ms")
                    candles = {
                        "t": _convert_timestamps_to_poland(df["t"].tolist()),
                        "o": df["o"].tolist(), "h": df["h"].tolist(),
                        "l": df["l"].tolist(), "c": df["c"].tolist(),
                        "v": df.get("v", pd.Series([0]*len(df))).tolist(),
                    }
                    st.session_state[cache_key]          = candles
                    st.session_state[f"{cache_key}_ts"]  = now
        except Exception:
            pass

    if not candles:
        # Demo fallback
        import random, pandas as pd
        base  = {"PKN":58,"PKO":42,"CDR":130,"HSBA":650,"BP":480,"AZN":11500}.get(symbol, 100)
        n     = 60
        dates = _convert_timestamps_to_poland(
            pd.date_range(end=_dt.datetime.now(), periods=n, freq="1D").tolist()
        )
        price = float(base)
        o,h,l,c,v = [],[],[],[],[]
        for _ in range(n):
            op = price
            cl = round(price + price*random.gauss(0, 0.012), 2)
            o.append(round(op,2)); c.append(round(cl,2))
            h.append(round(max(op,cl)+abs(price*random.gauss(0,0.004)),2))
            l.append(round(min(op,cl)-abs(price*random.gauss(0,0.004)),2))
            v.append(random.randint(10000,500000))
            price = cl
        candles = {"t":dates,"o":o,"h":h,"l":l,"c":c,"v":v}
        st.info("Brak danych z Polygon — pokazuję dane demo. Sprawdź klucz API.")

    # Render wykresu
    last  = candles["c"][-1] if candles["c"] else 0
    prev  = candles["c"][-2] if len(candles["c"]) > 1 else last
    chg_v = ((last - prev) / (prev + 1e-9)) * 100
    chg_c = "[●]" if chg_v >= 0 else ""
    st.markdown(f"**{syms.get(symbol, symbol)}** &nbsp; `{symbol}` &nbsp; "
                f"**{last:,.2f} {currency}** &nbsp; {chg_c} {chg_v:+.2f}%")

    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=candles["t"], open=candles["o"], high=candles["h"],
        low=candles["l"], close=candles["c"],
        increasing_line_color="#34d399", decreasing_line_color="#f87171",
        increasing_fillcolor="#34d399", decreasing_fillcolor="#f87171",
    ))
    if candles.get("v"):
        vol_colors = ["#34d399" if c >= o else "#f87171"
                      for o, c in zip(candles["o"], candles["c"])]
        fig.add_trace(go.Bar(
            x=candles["t"], y=candles["v"],
            marker_color=vol_colors, opacity=0.3,
            name="Wolumen", yaxis="y2",
        ))
    fig.update_layout(
        height=480, paper_bgcolor="#0d1321", plot_bgcolor="#0d1321",
        margin=dict(l=8, r=8, t=8, b=8),
        xaxis=dict(showgrid=False, zeroline=False, color="#475569",
                   rangeslider_visible=False, tickfont=dict(size=10, color="#64748b")),
        yaxis=dict(showgrid=True, gridcolor="#1e3a5f", zeroline=False,
                   color="#475569", tickfont=dict(size=10), side="right", domain=[0.25,1.0]),
        yaxis2=dict(showgrid=False, zeroline=False, domain=[0.0,0.22],
                    tickfont=dict(size=9, color="#334155")),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True,
                    config={"displayModeBar": True,
                            "modeBarButtonsToRemove": ["lasso2d","select2d"]})


def page_crypto() -> None:
    _page_autorefresh("crypto", "30s")
    st.title("₿ Wyszukiwarka Krypto")

    import plotly.graph_objects as go
    import requests as _req
    import datetime as _dt
    import time
    import sys
    sys.path.insert(0, ".")
    from core.symbols import SYMBOL_NAMES, get_full_name, CATEGORY_LABELS

    #  Wyszukiwarka 
    col_search, col_cat = st.columns([3, 1])
    with col_search:
        query = st.text_input(" Szukaj krypto", placeholder="np. Bitcoin, BTC, Ethereum...", label_visibility="collapsed")
    with col_cat:
        cat_filter = st.selectbox("Kategoria", ["Wszystkie", "Krypto", "Krypto ETF"], label_visibility="collapsed")

    cat_map = {"Krypto": "crypto", "Krypto ETF": "crypto_etf"}
    cat = cat_map.get(cat_filter)

    # Filtruj symbole
    crypto_syms = {k: v for k, v in SYMBOL_NAMES.items() if v[1] in ("crypto", "crypto_etf")}
    if query:
        q = query.strip().upper()
        crypto_syms = {k: v for k, v in crypto_syms.items()
                       if q in k or q in v[0].upper()}
    if cat:
        crypto_syms = {k: v for k, v in crypto_syms.items() if v[1] == cat}

    #  Wybór symbolu 
    if not crypto_syms:
        st.info("Brak wyników dla podanego zapytania.")
        return

    sym_options = [f"{k} — {v[0]}" for k, v in list(crypto_syms.items())[:50]]
    default_sym = "BTC — Bitcoin" if "BTC — Bitcoin" in sym_options else sym_options[0]

    selected_display = st.selectbox("Wybierz instrument", sym_options,
                                    index=sym_options.index(default_sym) if default_sym in sym_options else 0,
                                    label_visibility="collapsed")
    symbol = selected_display.split(" — ")[0]
    full_name = get_full_name(symbol)

    #  Timeframe 
    tf_options = ["1m", "5m", "15m", "1h", "4h", "1d"]
    tf = st.select_slider("Timeframe", options=tf_options, value="1h", label_visibility="collapsed")
    tf_map = {"1m":(1,"minute",2),"5m":(5,"minute",10),"15m":(15,"minute",20),
              "1h":(1,"hour",30),"4h":(4,"hour",60),"1d":(1,"day",365)}
    mult, span, days = tf_map[tf]

    #  Pobierz cenę live 
    live_price = None
    # Próbuj przez API backendu (Alpaca Crypto)
    if _api_online():
        quote = _get(f"/crypto/{symbol}/quote")
        if quote and quote.get("price", 0) > 0:
            live_price = float(quote["price"])
    # Fallback Polygon
    if not live_price:
        try:
            from config.settings import get_settings
            key = get_settings().polygon_api_key
            r = _req.get(
                f"https://api.polygon.io/v2/last/trade/{symbol}?apiKey={key}",
                timeout=3
            )
            if r.status_code == 200:
                live_price = float(r.json().get("results", {}).get("p", 0)) or None
        except Exception:
            pass

    #  Pobierz świece 
    candles = None
    cache_key = f"crypto_{symbol}_{tf}"
    now = time.time()
    if cache_key in st.session_state and (now - st.session_state.get(f"{cache_key}_ts", 0)) < 60:
        candles = st.session_state[cache_key]
    else:
        # Próbuj przez API backendu (Alpaca Crypto → Polygon fallback)
        if _api_online():
            bars = _get(f"/crypto/{symbol}/bars?timeframe={tf}")
            if bars:
                import pandas as pd
                candles = {
                    "t": pd.to_datetime([b["t"] for b in bars]).tolist(),
                    "o": [b["o"] for b in bars],
                    "h": [b["h"] for b in bars],
                    "l": [b["l"] for b in bars],
                    "c": [b["c"] for b in bars],
                    "v": [b.get("v", 0) for b in bars],
                }
                st.session_state[cache_key]         = candles
                st.session_state[f"{cache_key}_ts"] = now

        # Fallback bezpośrednio Polygon
        if not candles:
            try:
                from config.settings import get_settings
                key   = get_settings().polygon_api_key
                end   = _dt.date.today().isoformat()
                start = (_dt.date.today() - _dt.timedelta(days=days)).isoformat()
                r = _req.get(
                    f"https://api.polygon.io/v2/aggs/ticker/{symbol}/range/{mult}/{span}/{start}/{end}"
                    f"?adjusted=true&sort=asc&limit=300&apiKey={key}",
                    timeout=5
                )
                if r.status_code == 200:
                    results = r.json().get("results", [])
                    if results:
                        import pandas as pd
                        df = pd.DataFrame(results)
                        df["t"] = pd.to_datetime(df["t"], unit="ms")
                        candles = {"t": df["t"].tolist(), "o": df["o"].tolist(),
                                   "h": df["h"].tolist(), "l": df["l"].tolist(),
                                   "c": df["c"].tolist(), "v": df["v"].tolist()}
                        st.session_state[cache_key]         = candles
                        st.session_state[f"{cache_key}_ts"] = now
            except Exception:
                pass

    # Fallback demo
    if not candles:
        import random, pandas as pd
        base = {"BTC":62000,"ETH":3200,"SOL":145,"DOGE":0.12,"BNB":580,
                "AVAX":35,"ADA":0.45,"XRP":0.55,"LINK":14,"MATIC":0.85}.get(symbol, 50)
        n    = 60
        dates = pd.date_range(end=_dt.datetime.now(), periods=n, freq="1h")
        price = float(base)
        o,h,l,c,v = [],[],[],[],[]
        for _ in range(n):
            op = price
            cl = round(price + price*random.gauss(0, 0.01), 6)
            o.append(round(op,6)); c.append(round(cl,6))
            h.append(round(max(op,cl)+abs(price*random.gauss(0,0.003)),6))
            l.append(round(min(op,cl)-abs(price*random.gauss(0,0.003)),6))
            v.append(random.randint(1000,50000))
            price = cl
        candles = {"t": dates.tolist(), "o":o, "h":h, "l":l, "c":c, "v":v}
        live_price = candles["c"][-1]

    #  Metryki 
    last_c = candles["c"][-1]  if candles["c"] else 0
    prev_c = candles["c"][-2]  if len(candles["c"]) > 1 else last_c
    high   = max(candles["h"]) if candles["h"] else 0
    low    = min(candles["l"]) if candles["l"] else 0
    chg    = ((last_c - prev_c) / prev_c * 100) if prev_c else 0
    chg_color = "normal" if chg >= 0 else "inverse"
    price_display = live_price or last_c

    if price_display >= 1000:
        price_str = f"${price_display:,.2f}"
    elif price_display >= 1:
        price_str = f"${price_display:,.4f}"
    else:
        price_str = f"${price_display:.8f}"

    st.markdown(f"## {full_name} `({symbol})`")
    m1, m2, m3, m4 = st.columns(4)
    m1.metric(" Cena",       price_str,      f"{chg:+.2f}%")
    m2.metric(" Max (okres)", f"${high:,.4f}" if high < 1000 else f"${high:,.2f}")
    m3.metric(" Min (okres)", f"${low:,.4f}"  if low  < 1000 else f"${low:,.2f}")
    m4.metric(" Świec",       str(len(candles["c"])))

    #  Wykres świecowy 
    fig = go.Figure()

    # Świece
    fig.add_trace(go.Candlestick(
        x=_convert_timestamps_to_poland(candles["t"]),
        open=candles["o"], high=candles["h"],
        low=candles["l"],  close=candles["c"],
        increasing_line_color="#34d399",
        decreasing_line_color="#f87171",
        increasing_fillcolor="#34d399",
        decreasing_fillcolor="#f87171",
        name=symbol,
    ))

    # Wolumen jako słupki na dole
    if candles.get("v"):
        vol_colors = ["#34d399" if c >= o else "#f87171"
                      for o, c in zip(candles["o"], candles["c"])]
        fig.add_trace(go.Bar(
            x=_convert_timestamps_to_poland(candles["t"]), y=candles["v"],
            marker_color=vol_colors, opacity=0.3,
            name="Wolumen", yaxis="y2",
        ))

    fig.update_layout(
        height=500,
        paper_bgcolor="#0d1321",
        plot_bgcolor="#0d1321",
        margin=dict(l=8, r=8, t=16, b=8),
        xaxis=dict(
            showgrid=False, zeroline=False,
            color="#475569", rangeslider_visible=False,
            tickfont=dict(size=10, color="#64748b"),
        ),
        yaxis=dict(
            showgrid=True, gridcolor="#1e3a5f",
            zeroline=False, color="#475569",
            tickfont=dict(size=10, color="#64748b"),
            side="right", domain=[0.25, 1.0],
        ),
        yaxis2=dict(
            showgrid=False, zeroline=False,
            color="#475569", domain=[0.0, 0.22],
            tickfont=dict(size=9, color="#334155"),
        ),
        legend=dict(font=dict(color="#64748b"), bgcolor="rgba(0,0,0,0)"),
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True, config={"displayModeBar": True,
                                                             "modeBarButtonsToRemove": ["lasso2d","select2d"]})

    #  Popularne krypto 
    st.markdown("---")

    #  Globalne statystyki rynku 
    global_stats = _get("/crypto/market/global") or {}
    if global_stats:
        total_mcap = global_stats.get("total_market_cap_usd", 0)
        total_vol  = global_stats.get("total_volume_24h_usd", 0)
        btc_dom    = global_stats.get("btc_dominance", 0)
        eth_dom    = global_stats.get("eth_dominance", 0)
        mcap_chg   = global_stats.get("market_cap_change_24h", 0)
        mcap_color = "#34d399" if mcap_chg >= 0 else "#f87171"

        def _fmt_big(n: float) -> str:
            if n >= 1e12: return f"${n/1e12:.2f}T"
            if n >= 1e9:  return f"${n/1e9:.2f}B"
            if n >= 1e6:  return f"${n/1e6:.2f}M"
            return f"${n:.0f}"

        st.markdown(
            f'<div style="background:#0f172a;border:1px solid #1e3a5f;border-radius:12px;'
            f'padding:16px;margin-bottom:12px;">'
            f'<div style="color:#64748b;font-size:12px;margin-bottom:10px;"> GLOBALNY RYNEK KRYPTO</div>'
            f'<div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;text-align:center;">'
            f'<div><div style="color:#64748b;font-size:11px;">MARKET CAP</div>'
            f'<div style="color:#e2e8f0;font-weight:700;">{_fmt_big(total_mcap)}</div>'
            f'<div style="color:{mcap_color};font-size:11px;">{mcap_chg:+.1f}% 24h</div></div>'
            f'<div><div style="color:#64748b;font-size:11px;">VOLUME 24H</div>'
            f'<div style="color:#e2e8f0;font-weight:700;">{_fmt_big(total_vol)}</div></div>'
            f'<div><div style="color:#64748b;font-size:11px;">BTC DOM</div>'
            f'<div style="color:#f59e0b;font-weight:700;">{btc_dom:.1f}%</div></div>'
            f'<div><div style="color:#64748b;font-size:11px;">ETH DOM</div>'
            f'<div style="color:#818cf8;font-weight:700;">{eth_dom:.1f}%</div></div>'
            f'<div><div style="color:#64748b;font-size:11px;">AKTYWNYCH</div>'
            f'<div style="color:#e2e8f0;font-weight:700;">{global_stats.get("active_coins",0):,}</div></div>'
            f'</div></div>',
            unsafe_allow_html=True,
        )

    #  Top 20 ceny z Binance/CoinGecko/CoinCap 
    st.subheader(" Top Krypto — Live Ceny")
    top_symbols = ["BTC","ETH","SOL","BNB","XRP","DOGE","AVAX","ADA","LINK","UNI",
                   "MATIC","NEAR","PEPE","WIF","TIA","SUI","TON","RNDR","INJ","APT"]
    syms_str = ",".join(top_symbols)
    prices_data = _get(f"/crypto/market/prices?symbols={syms_str}") or {}

    if prices_data:
        cols_h = st.columns([1.5, 1, 1, 1, 1])
        cols_h[0].markdown("**Symbol**")
        cols_h[1].markdown("**Cena**")
        cols_h[2].markdown("**24h %**")
        cols_h[3].markdown("**Vol 24h**")
        cols_h[4].markdown("**Źródło**")
        st.markdown("---")

        for sym in top_symbols:
            d = prices_data.get(sym, {})
            if not d or not d.get("price"):
                continue
            price   = d["price"]
            chg     = d.get("change_24h", 0)
            vol     = d.get("volume_24h", 0)
            source  = d.get("source", "?")
            chg_c   = "#34d399" if chg >= 0 else "#f87171"
            chg_ico = "" if chg >= 0 else ""

            price_str = f"${price:,.2f}" if price >= 1 else f"${price:.6f}"
            vol_str   = _fmt_big(vol) if vol else "—"

            row = st.columns([1.5, 1, 1, 1, 1])
            row[0].markdown(f"**{sym}** <span style='color:#64748b;font-size:11px'>{get_full_name(sym)}</span>",
                           unsafe_allow_html=True)
            row[1].markdown(f"**{price_str}**")
            row[2].markdown(f'<span style="color:{chg_c}">{chg_ico} {abs(chg):.2f}%</span>',
                           unsafe_allow_html=True)
            row[3].markdown(vol_str)
            row[4].markdown(f'<span style="color:#475569;font-size:11px">{source}</span>',
                           unsafe_allow_html=True)

    #  Trending 
    trending = _get("/crypto/market/trending") or []
    if trending:
        st.markdown("---")
        st.subheader(" Trending (CoinGecko)")
        tr_cols = st.columns(len(trending))
        for i, coin in enumerate(trending):
            with tr_cols[i]:
                st.markdown(
                    f'<div style="background:#111827;border:1px solid #1e3a5f;border-radius:8px;'
                    f'padding:8px;text-align:center;">'
                    f'<div style="font-weight:700;color:#93c5fd">{coin["symbol"]}</div>'
                    f'<div style="font-size:11px;color:#64748b">{coin["name"][:15]}</div>'
                    f'<div style="font-size:11px;color:#475569">#{coin.get("rank","?")}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

    #  Popularne przyciski 
    st.markdown("---")
    st.subheader(" Popularne")
    popular = ["BTC","ETH","SOL","BNB","XRP","DOGE","AVAX","ADA","LINK","UNI","MATIC","NEAR"]
    pop_cols = st.columns(6)
    for i, sym in enumerate(popular):
        name = get_full_name(sym)
        if pop_cols[i % 6].button(f"{sym}\n{name}", key=f"pop_{sym}", use_container_width=True):
            st.session_state["crypto_search_sym"] = sym
            st.rerun()


def page_users() -> None:
    st.title("Użytkownicy")
    if _is_viewer():
        st.warning("Tylko admin może zarządzać użytkownikami.")
        return

    users = _get("/users") or []

    #  Oczekujące na zatwierdzenie 
    pending = [u for u in users if not u.get("approved") and not u.get("builtin")]
    if pending:
        st.subheader(f"Oczekujące na zatwierdzenie ({len(pending)})")
        for u in pending:
            col1, col2, col3 = st.columns([3, 1, 1])
            col1.markdown(f"**{u['username']}** — `viewer` — {u.get('created_at','')[:10]}")
            if col2.button(" Zatwierdź", key=f"approve_{u['username']}"):
                r = _post(f"/users/{u['username']}/approve", {})
                if r and r.get("ok"):
                    st.success(f"Zatwierdzono {u['username']}")
                    st.rerun()
            if col3.button(" Odrzuć", key=f"reject_{u['username']}"):
                r = _post(f"/users/{u['username']}/reject", {})
                if r and r.get("ok"):
                    st.warning(f"Odrzucono {u['username']}")
                    st.rerun()
        st.markdown("---")

    #  Aktywni użytkownicy 
    active = [u for u in users if u.get("approved") or u.get("builtin")]
    st.subheader(f" Aktywni użytkownicy ({len(active)})")
    for u in active:
        col1, col2 = st.columns([4, 1])
        builtin = u.get("builtin", False)
        role_badge = " admin" if u["role"] == "admin" else " viewer"
        builtin_badge = " *(wbudowane)*" if builtin else ""
        col1.markdown(f"**{u['username']}** — {role_badge}{builtin_badge}")
        if not builtin:
            if col2.button(" Usuń", key=f"del_{u['username']}"):
                r = _delete(f"/users/{u['username']}")
                if r and r.get("ok"):
                    st.success(f"Usunięto {u['username']}")
                    st.rerun()

    st.markdown("---")
    st.caption("Nowi użytkownicy mogą rejestrować się przez ekran logowania. Konta wymagają zatwierdzenia.")


def _delete(path: str) -> dict | None:
    try:
        r = requests.delete(
            f"{st.session_state.api_base}{path}",
            headers=_headers(), timeout=5
        )
        return r.json()
    except Exception as e:
        return {"error": str(e)}


def page_emergency() -> None:
    st.title("Emergency Stop")
    status = _get_status()
    estop  = status.get("emergency_stop", False) if status else False

    if estop:
        st.error("## Emergency Stop JEST AKTYWNY")
        st.markdown("System nie otwiera nowych pozycji.")
        st.markdown("---")
        st.subheader(" Odblokuj system")
        pwd = st.text_input("Hasło odblokowania", type="password")
        if st.button(" Odblokuj Emergency Stop", type="primary"):
            r = _post("/emergency/clear", {"password": pwd})
            if r and r.get("ok"):
                st.success(" System odblokowany")
                st.rerun()
            else:
                st.error("Błędne hasło lub błąd API")
    else:
        st.success("System działa normalnie")
        st.markdown("---")

        st.markdown("""
        ###  Emergency Stop zatrzyma:
        - Otwieranie nowych pozycji przez wszystkich agentów
        - Składanie nowych zleceń
        
        ### Opcjonalnie może:
        - Zamknąć wszystkie otwarte pozycje rynkowo
        """)

        st.markdown("---")
        close_pos = st.checkbox("Zamknij wszystkie otwarte pozycje", value=True)
        pwd = st.text_input("Hasło Emergency Stop", type="password")

        st.markdown('<div class="emergency-btn">', unsafe_allow_html=True)
        if not _is_viewer():
            if st.button(" AKTYWUJ EMERGENCY STOP", type="primary", use_container_width=True):
                if not pwd:
                    st.error(" Wpisz hasło Emergency Stop")
                else:
                    r = _post("/emergency/stop", {
                        "password":        pwd,
                        "close_positions": close_pos,
                    })
                    if r and r.get("ok"):
                        st.error("Emergency Stop AKTYWOWANY")
                        st.rerun()
                    else:
                        st.error(f" {r.get('detail', 'Błąd') if r else 'Brak połączenia'}")
        st.markdown("</div>", unsafe_allow_html=True)


# 
# Router – główna logika
# 
def main() -> None:
    # Reset cache statusu przy każdym odświeżeniu
    st.session_state.pop("cached_status", None)

    # Jeśli nie zalogowany — pokaż ekran logowania
    if not st.session_state.get("logged_in"):
        # Czysty ekran logowania bez tickera
        st.markdown("""
        <style>
        [data-testid="stSidebar"] {display: none;}
        .block-container {padding-top: 3rem;}
        </style>
        """, unsafe_allow_html=True)

        if "show_register" not in st.session_state:
            st.session_state.show_register = False

        _, col, _ = st.columns([1, 1.4, 1])
        with col:
            # Logo i tytuł
            st.markdown("""
            <div style="text-align:center;margin-bottom:32px;">
                <div style="font-size:48px;margin-bottom:8px;"></div>
                <div style="font-size:24px;font-weight:700;color:#93c5fd;margin-bottom:4px;">IBKR Trading System</div>
                <div style="font-size:13px;color:#475569;">Multi-Agent AI Trading Platform</div>
            </div>
            """, unsafe_allow_html=True)

            # Karta
            with st.container(border=True):
                if not st.session_state.show_register:
                    st.markdown("####  Logowanie")
                    username = st.text_input("Login", placeholder="Wpisz login", label_visibility="collapsed")
                    password = st.text_input("Hasło", type="password", placeholder="Wpisz hasło", label_visibility="collapsed")
                    st.markdown("")

                    if st.button("Zaloguj się", use_container_width=True, type="primary"):
                        if not username or not password:
                            st.warning("Wpisz login i hasło")
                        else:
                            try:
                                r = requests.post(
                                    f"{st.session_state.api_base}/auth/token",
                                    data={"username": username, "password": password},
                                    timeout=5,
                                )
                                if r.status_code == 200:
                                    data = r.json()
                                    try:
                                        import base64, json as _json
                                        payload = data["access_token"].split(".")[1]
                                        payload += "=" * (4 - len(payload) % 4)
                                        decoded = _json.loads(base64.b64decode(payload))
                                        role = decoded.get("role", "viewer")
                                    except Exception:
                                        role = "admin" if username == "admin" else "viewer"
                                    st.session_state.token      = data["access_token"]
                                    st.session_state.logged_in  = True
                                    st.session_state.username   = username
                                    st.session_state.api_online = True
                                    st.session_state.role       = role
                                    st.rerun()
                                else:
                                    st.error("Nieprawidłowy login lub hasło")
                            except Exception:
                                st.error("Brak połączenia z API — uruchom bota")

                    st.markdown("<div style='text-align:center;margin-top:12px;'>", unsafe_allow_html=True)
                    if st.button("Utwórz nowe konto →", use_container_width=False):
                        st.session_state.show_register = True
                        st.rerun()
                    st.markdown("</div>", unsafe_allow_html=True)

                else:
                    st.markdown("####  Rejestracja")
                    st.caption("Konto wymaga zatwierdzenia przez admina.")
                    new_user  = st.text_input("Login", placeholder="min. 3 znaki, litery i cyfry")
                    new_pass  = st.text_input("Hasło", type="password", placeholder="min. 6 znaków")
                    new_pass2 = st.text_input("Powtórz hasło", type="password", placeholder="Powtórz hasło")
                    st.markdown("")

                    if st.button("Zarejestruj się", use_container_width=True, type="primary"):
                        if not new_user or not new_pass:
                            st.warning("Wypełnij wszystkie pola")
                        elif new_pass != new_pass2:
                            st.error("Hasła nie są identyczne")
                        else:
                            try:
                                r = requests.post(
                                    f"{st.session_state.api_base}/auth/register",
                                    json={"username": new_user, "password": new_pass},
                                    timeout=5,
                                )
                                if r.status_code == 200:
                                    st.success("Konto utworzone — czeka na zatwierdzenie admina")
                                    st.session_state.show_register = False
                                    st.rerun()
                                else:
                                    st.error(r.json().get("detail", "Błąd rejestracji"))
                            except Exception:
                                st.error("Brak połączenia z API")

                    if st.button("← Wróć do logowania", use_container_width=True):
                        st.session_state.show_register = False
                        st.rerun()
        return

    # Zalogowany — sprawdź czy API działa
    if st.session_state.token and st.session_state.token != "dummy":
        st.session_state.api_online = True

    _render_ticker()
    _render_header()
    render_top_nav()

    page = st.session_state.active_page
    dispatch = {
        "Dashboard":     page_dashboard,
        "Agenci":        page_agents,
        "Pozycje":       page_positions,
        "Transakcje":    page_transactions,
        "Sygnały":       page_signals,
        "Ryzyko":        page_risk,
        "Wydajność":     page_performance,
        "Szef":          page_coach,
        "Fundamentals":  page_fundamentals,
        "Newsy":         page_news,
        "Backtester":    page_backtester,
        "Paper Session": page_paper_session,
        "AI Chat":       page_ai_chat,
        "Logi":          page_logs,
        "Uzytkownicy":   page_users,
        "Krypto":        page_crypto,
        "Rynki":         page_markets,
        "Emergency":     page_emergency,
    }
    # ── Dev Panel (ładowane dynamicznie) ─────────────────────────────────────
    if _DEV_PAGES_LOADED:
        dispatch.update({
            "Dev Monitor":   page_dev_monitor,
            "PnL Timeline":  page_pnl_timeline,
            "Logi PRO":      page_logs_pro,
            "Sygnały PRO":   page_signals_pro,
            "System Health": page_system_health,
            "Export":        page_dev_export,
        })
    else:
        for key in ("Dev Monitor", "PnL Timeline", "Logi PRO",
                    "Sygnały PRO", "System Health", "Export"):
            dispatch[key] = lambda: st.error(
                "Dev pages nie załadowane. Sprawdź logi konsoli."
            )
    dispatch.get(page, page_dashboard)()


if __name__ == "__main__":
    main()


