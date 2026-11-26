"""
Panel Developerski - strony z 100% wglądem w system.

Moduł zawiera:
  page_dev_monitor()   - Audit Log + Activity Feed + live rejestrator
  page_pnl_timeline()  - Historyczny wykres equity i PnL per agent
  page_logs_pro()      - Logi z filtrowaniem po poziomie/module/czasie
  page_signals_pro()   - Sygnały z raw_indicators, approved/rejected
  page_system_health() - CPU/RAM/IBKR/latency monitoring
  page_dev_export()    - Export CSV wszystkich danych

Importuj w dashboard.py:
  from panel.frontend.dev_pages import (
      page_dev_monitor, page_pnl_timeline, page_logs_pro,
      page_signals_pro, page_system_health, page_dev_export,
  )
"""
from __future__ import annotations

import io
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import requests
import streamlit as st

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _api(path: str, default: Any = None) -> Any:
    """Wrapper na GET do backendu."""
    try:
        base = st.session_state.get("api_base", "http://localhost:8000")
        tok  = st.session_state.get("token", "")
        headers = {"Authorization": f"Bearer {tok}"} if tok else {}
        r = requests.get(f"{base}{path}", headers=headers, timeout=5)
        if r.status_code == 200:
            return r.json()
    except Exception:
        pass
    return default

def _badge(text: str, color: str) -> str:
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:11px;font-weight:600;">{text}</span>'
    )

def _event_color(event_type: str) -> str:
    colors = {
        "signal_generated":  "#3b82f6",
        "signal_approved":   "#10b981",
        "signal_rejected":   "#f59e0b",
        "order_placed":      "#8b5cf6",
        "order_filled":      "#34d399",
        "order_cancelled":   "#6b7280",
        "position_opened":   "#06b6d4",
        "position_closed":   "#f97316",
        "agent_started":     "#4ade80",
        "agent_stopped":     "#94a3b8",
        "agent_error":       "#ef4444",
        "risk_triggered":    "#fbbf24",
        "emergency_stop":    "#dc2626",
    }
    return colors.get(event_type, "#64748b")

def _fmt_dt(dt_str: str) -> str:
    """ISO string → czytelna data po polsku."""
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        # Konwersja na CET (UTC+1) lub CEST (UTC+2) - uproszczona
        dt_pl = dt + timedelta(hours=2)
        return dt_pl.strftime("%d.%m %H:%M:%S")
    except Exception:
        return dt_str[:16] if dt_str else "—"

LOG_DIR = Path(__file__).parent.parent.parent / "logs"


# ═════════════════════════════════════════════════════════════════════════════
# STRONA 1: DEV MONITOR - Audit Log + Activity Feed
# ═════════════════════════════════════════════════════════════════════════════

def page_dev_monitor() -> None:
    st.title("Dev Monitor")
    st.markdown("Kompletny rejestr wszystkich zdarzeń systemu w czasie rzeczywistym.")

    tab1, tab2, tab3 = st.tabs(["Audit Log", "Activity Feed", "Statystyki"])

    # ── Tab 1: Audit Log ─────────────────────────────────────────────────────
    with tab1:
        st.markdown("#### Historia wszystkich akcji użytkownika i systemu")

        col1, col2, col3 = st.columns([2, 2, 1])
        with col1:
            search = st.text_input("Szukaj", placeholder="np. enable_agent, AAPL, admin", key="audit_search")
        with col2:
            action_filter = st.selectbox("Typ akcji", [
                "Wszystkie", "login", "enable_agent", "disable_agent",
                "update_agent_config", "update_risk_limits", "EMERGENCY_STOP",
                "backtest_run", "paper_session_start", "switch_to_paper", "switch_to_real",
            ], key="audit_action_filter")
        with col3:
            limit = st.selectbox("Pokaż", [50, 100, 200, 500], key="audit_limit")

        audit_data = _api(f"/dev/audit-log?limit={limit}") or []

        if not audit_data:
            st.info("Brak danych audit log. Backend offline lub brak historii.")
            _render_mock_audit()
            return

        # Filtrowanie
        df = pd.DataFrame(audit_data)
        if search:
            mask = df.apply(lambda row: search.lower() in str(row).lower(), axis=1)
            df = df[mask]
        if action_filter != "Wszystkie":
            df = df[df["action"] == action_filter]

        st.markdown(f"**{len(df)} wpisów**")

        for _, row in df.iterrows():
            action = row.get("action", "")
            user   = row.get("user", "system")
            ts     = _fmt_dt(str(row.get("timestamp", "")))
            details = row.get("details", {})
            color  = _event_color(action)

            with st.expander(f"{ts}  |  {action}  |  {user}", expanded=False):
                c1, c2 = st.columns([1, 3])
                with c1:
                    st.markdown(_badge(action, color), unsafe_allow_html=True)
                    st.markdown(f"**User:** {user}")
                    st.markdown(f"**Czas:** {ts}")
                    ip = row.get("ip_address", "")
                    if ip:
                        st.markdown(f"**IP:** {ip}")
                with c2:
                    if details:
                        st.json(details)
                    else:
                        st.caption("Brak szczegółów")

    # ── Tab 2: Activity Feed ─────────────────────────────────────────────────
    with tab2:
        st.markdown("#### Rejestr zdarzeń agentów — każde posunięcie bota")

        col1, col2, col3, col4 = st.columns(4)
        with col1:
            agent_filter = st.selectbox("Agent", ["Wszystkie",
                "scalper", "trend_follower", "momentum_surfer", "breakout_hunter",
                "mean_reversion", "gap_trader", "divergence_hunter", "vix_trader",
                "sentiment_trader", "options_flow", "scalp_king",
                "orchestrator", "risk_manager",
            ], key="feed_agent")
        with col2:
            event_filter = st.selectbox("Typ zdarzenia", [
                "Wszystkie", "signal_generated", "signal_approved", "signal_rejected",
                "order_placed", "order_filled", "order_cancelled",
                "position_opened", "position_closed",
                "agent_error", "risk_triggered", "emergency_stop",
            ], key="feed_event")
        with col3:
            symbol_filter = st.text_input("Symbol", placeholder="AAPL", key="feed_symbol")
        with col4:
            feed_limit = st.selectbox("Wierszy", [100, 200, 500], key="feed_limit")

        # Build URL
        url = f"/dev/agent-events?limit={feed_limit}"
        if agent_filter != "Wszystkie":
            url += f"&agent={agent_filter}"
        if event_filter != "Wszystkie":
            url += f"&event_type={event_filter}"
        if symbol_filter:
            url += f"&symbol={symbol_filter.upper()}"

        events = _api(url) or []

        if not events:
            st.info("Brak zdarzeń. Uruchom bota żeby zaczął rejestrować aktywność.")
            _render_mock_feed()
        else:
            _render_activity_feed(events)

    # ── Tab 3: Statystyki ────────────────────────────────────────────────────
    with tab3:
        st.markdown("#### Statystyki aktywności za ostatnie 24h")

        stats = _api("/dev/stats/24h") or {}

        if not stats:
            st.info("Backend offline — brak statystyk")
            return

        c1, c2, c3, c4, c5 = st.columns(5)
        metrics = [
            ("Sygnały", stats.get("signals_24h", 0), ""),
            ("Zlecenia", stats.get("orders_24h", 0), ""),
            ("Zatwierdzone", stats.get("approved_24h", 0), ""),
            ("Odrzucone", stats.get("rejected_24h", 0), ""),
            ("Błędy", stats.get("errors_24h", 0), ""),
        ]
        for col, (label, val, icon) in zip([c1, c2, c3, c4, c5], metrics):
            col.metric(label, val)

        # Wykres aktywności per agent
        agent_stats = stats.get("per_agent", {})
        if agent_stats:
            df_agents = pd.DataFrame([
                {"agent": k, "sygnały": v.get("signals", 0), "błędy": v.get("errors", 0)}
                for k, v in agent_stats.items()
            ]).sort_values("sygnały", ascending=False)

            fig = px.bar(
                df_agents, x="agent", y=["sygnały", "błędy"],
                title="Aktywność agentów (24h)",
                color_discrete_map={"sygnały": "#3b82f6", "błędy": "#ef4444"},
                template="plotly_dark",
            )
            fig.update_layout(
                plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
                font_color="#e2e8f0", height=350,
            )
            st.plotly_chart(fig, use_container_width=True)


def _render_activity_feed(events: list) -> None:
    """Renderuje listę zdarzeń agentów."""
    for ev in events:
        agent     = ev.get("agent_name", "unknown")
        etype     = ev.get("event_type", "unknown")
        symbol    = ev.get("symbol", "")
        direction = ev.get("direction", "")
        price     = ev.get("price")
        pnl       = ev.get("pnl")
        conf      = ev.get("confidence")
        reasoning = ev.get("reasoning", "")
        ts        = _fmt_dt(str(ev.get("timestamp", "")))
        color     = _event_color(etype)
        paper     = ev.get("paper_mode", True)

        # Kompaktowa linia
        parts = [f"`{ts}`", _badge(etype, color), f"**{agent}**"]
        if symbol:
            dir_color = "#34d399" if direction == "BUY" else "#f87171"
            parts.append(f"| {_badge(direction or symbol, dir_color)} **{symbol}**")
        if price:
            parts.append(f"@ ${price:,.2f}")
        if pnl is not None:
            pnl_color = "#34d399" if pnl >= 0 else "#f87171"
            sign = "+" if pnl >= 0 else ""
            parts.append(f"| {_badge(f'PnL {sign}${pnl:.2f}', pnl_color)}")
        if conf is not None:
            parts.append(f"| conf: **{conf*100:.0f}%**")
        if paper:
            parts.append("[paper]")

        line = " ".join(parts)

        if reasoning:
            with st.expander(line.replace("**", "").replace("`", ""), expanded=False):
                st.markdown(line, unsafe_allow_html=True)
                st.caption(f"{reasoning}")
                details = ev.get("details", {})
                if details:
                    st.json(details)
        else:
            st.markdown(line, unsafe_allow_html=True)


def _render_mock_audit() -> None:
    """Mock data gdy API offline."""
    st.markdown("---")
    st.caption("Przykład — dane testowe (backend offline)")
    mock = [
        {"ts": "29.10 14:32:11", "action": "enable_agent",    "user": "admin", "details": {"agent": "momentum_surfer"}},
        {"ts": "29.10 14:28:05", "action": "update_risk_limits", "user": "admin", "details": {"max_drawdown_pct": 8.0}},
        {"ts": "29.10 14:15:33", "action": "login",            "user": "admin", "details": {"role": "admin"}},
        {"ts": "29.10 13:50:17", "action": "paper_session_start", "user": "admin", "details": {"capital": 10000, "agents": 3}},
    ]
    for m in mock:
        color = _event_color(m["action"])
        with st.expander(f"{m['ts']}  |  {m['action']}  |  {m['user']}"):
            st.markdown(_badge(m["action"], color), unsafe_allow_html=True)
            st.json(m["details"])


def _render_mock_feed() -> None:
    """Mock activity feed gdy brak danych."""
    st.markdown("---")
    st.caption("Przykład — jak będzie wyglądał feed po uruchomieniu bota")
    mock_events = [
        {"agent_name": "momentum_surfer", "event_type": "signal_generated",
         "symbol": "AAPL", "direction": "BUY", "confidence": 0.84,
         "reasoning": "RSI(14)=28 oversold + volume 2.3x avg, MACD crossover bullish",
         "timestamp": "2026-10-29T14:35:22Z", "paper_mode": True},
        {"agent_name": "risk_manager", "event_type": "signal_approved",
         "symbol": "AAPL", "direction": "BUY", "confidence": 0.84,
         "reasoning": "Drawdown 2.1% < limit 10%, position size OK",
         "timestamp": "2026-10-29T14:35:23Z", "paper_mode": True},
        {"agent_name": "orchestrator", "event_type": "order_placed",
         "symbol": "AAPL", "direction": "BUY", "price": 178.45, "quantity": 5,
         "timestamp": "2026-10-29T14:35:24Z", "paper_mode": True},
        {"agent_name": "orchestrator", "event_type": "order_filled",
         "symbol": "AAPL", "direction": "BUY", "price": 178.47, "quantity": 5,
         "timestamp": "2026-10-29T14:35:25Z", "paper_mode": True},
        {"agent_name": "trend_follower", "event_type": "signal_rejected",
         "symbol": "TSLA", "direction": "SELL", "confidence": 0.61,
         "reasoning": "Risk manager: max daily positions (5) reached",
         "timestamp": "2026-10-29T14:34:10Z", "paper_mode": True},
    ]
    _render_activity_feed(mock_events)


# ═════════════════════════════════════════════════════════════════════════════
# STRONA 2: PnL TIMELINE - historyczne wykresy
# ═════════════════════════════════════════════════════════════════════════════

def page_pnl_timeline() -> None:
    st.title("PnL Timeline")
    st.markdown("Historyczny wykres equity i PnL per agent.")

    col1, col2, col3 = st.columns([2, 2, 2])
    with col1:
        period = st.selectbox("Okres", [
            "Ostatnie 24h", "Ostatnie 7 dni", "Ostatnie 30 dni", "Wszystko"
        ], key="pnl_period")
    with col2:
        view = st.selectbox("Widok", [
            "Equity curve", "PnL dzienny", "PnL per agent", "Drawdown"
        ], key="pnl_view")
    with col3:
        smoothing = st.slider("Wygładzanie (min)", 1, 60, 5, key="pnl_smooth")

    # Mapowanie okresu na godziny
    hours_map = {"Ostatnie 24h": 24, "Ostatnie 7 dni": 168,
                 "Ostatnie 30 dni": 720, "Wszystko": 99999}
    hours = hours_map[period]

    data = _api(f"/dev/equity-history?hours={hours}") or []

    if not data:
        st.info("Brak danych historycznych. Bot musi działać przez jakiś czas żeby zebrać dane.")
        _render_mock_equity_chart()
        return

    df = pd.DataFrame(data)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp")

    if view == "Equity curve":
        _chart_equity_curve(df, smoothing)
    elif view == "PnL dzienny":
        _chart_daily_pnl(df)
    elif view == "PnL per agent":
        _chart_agent_pnl(df)
    elif view == "Drawdown":
        _chart_drawdown(df)

    # Metryki sumaryczne
    st.markdown("---")
    st.markdown("#### Metryki okresu")
    _show_period_metrics(df)


def _chart_equity_curve(df: pd.DataFrame, smoothing: int) -> None:
    if "net_liquidation" not in df.columns:
        st.warning("Brak danych net_liquidation")
        return

    # Wygładzanie rolling average
    df["equity_smooth"] = df["net_liquidation"].rolling(smoothing, min_periods=1).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["net_liquidation"],
        name="Equity", mode="lines",
        line=dict(color="#3b82f6", width=1),
        opacity=0.4,
    ))
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=df["equity_smooth"],
        name=f"Equity ({smoothing}min MA)", mode="lines",
        line=dict(color="#60a5fa", width=2),
    ))

    # Zaznacz wartość startową i końcową
    if len(df) > 1:
        start_val = df["net_liquidation"].iloc[0]
        end_val   = df["net_liquidation"].iloc[-1]
        change    = end_val - start_val
        change_pct = (change / start_val * 100) if start_val else 0
        sign = "+" if change >= 0 else ""
        title = f"Equity Curve  |  {sign}${change:,.2f}  ({sign}{change_pct:.2f}%)"
    else:
        title = "Equity Curve"

    fig.update_layout(
        title=title, template="plotly_dark",
        plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
        font_color="#e2e8f0", height=420,
        xaxis_title="Czas", yaxis_title="Kapitał ($)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)


def _chart_daily_pnl(df: pd.DataFrame) -> None:
    if "daily_pnl" not in df.columns:
        st.warning("Brak danych daily_pnl")
        return

    # Resample do 1h dla czytelności
    df = df.set_index("timestamp")
    df_hourly = df["daily_pnl"].resample("1H").last().reset_index()
    df_hourly["color"] = df_hourly["daily_pnl"].apply(lambda x: "#34d399" if x >= 0 else "#f87171")

    fig = go.Figure(go.Bar(
        x=df_hourly["timestamp"], y=df_hourly["daily_pnl"],
        marker_color=df_hourly["color"],
        name="PnL",
    ))
    fig.update_layout(
        title="PnL dzienny (1h bins)", template="plotly_dark",
        plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
        font_color="#e2e8f0", height=380,
        xaxis_title="Czas", yaxis_title="PnL ($)",
    )
    st.plotly_chart(fig, use_container_width=True)


def _chart_agent_pnl(df: pd.DataFrame) -> None:
    if "agent_pnl" not in df.columns:
        st.warning("Brak danych agent_pnl")
        return

    # Rozpakowywanie JSON kolumny agent_pnl
    agent_records = []
    for _, row in df.iterrows():
        pnl_dict = row["agent_pnl"]
        if isinstance(pnl_dict, dict):
            for agent, pnl in pnl_dict.items():
                agent_records.append({"timestamp": row["timestamp"], "agent": agent, "pnl": pnl})

    if not agent_records:
        st.info("Brak danych PnL per agent")
        return

    df_agents = pd.DataFrame(agent_records)
    agents = df_agents["agent"].unique().tolist()

    selected_agents = st.multiselect(
        "Wybierz agentów", agents, default=agents[:5],
        key="pnl_agents_select"
    )

    fig = go.Figure()
    colors = px.colors.qualitative.Set3
    for i, agent in enumerate(selected_agents):
        agent_df = df_agents[df_agents["agent"] == agent].sort_values("timestamp")
        fig.add_trace(go.Scatter(
            x=agent_df["timestamp"], y=agent_df["pnl"],
            name=agent, mode="lines",
            line=dict(color=colors[i % len(colors)], width=2),
        ))

    fig.update_layout(
        title="PnL per Agent w czasie", template="plotly_dark",
        plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
        font_color="#e2e8f0", height=420,
        xaxis_title="Czas", yaxis_title="PnL ($)",
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02),
    )
    st.plotly_chart(fig, use_container_width=True)


def _chart_drawdown(df: pd.DataFrame) -> None:
    if "drawdown_pct" not in df.columns:
        st.warning("Brak danych drawdown_pct")
        return

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=df["timestamp"], y=-df["drawdown_pct"],
        name="Drawdown %", mode="lines",
        fill="tozeroy",
        line=dict(color="#f87171", width=2),
        fillcolor="rgba(248,113,113,0.2)",
    ))

    # Linia max drawdown
    max_dd = df["drawdown_pct"].max()
    fig.add_hline(
        y=-max_dd, line_dash="dash", line_color="#fbbf24",
        annotation_text=f"Max: -{max_dd:.2f}%",
        annotation_position="bottom right",
    )

    fig.update_layout(
        title="Drawdown %", template="plotly_dark",
        plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
        font_color="#e2e8f0", height=380,
        xaxis_title="Czas", yaxis_title="Drawdown %",
    )
    st.plotly_chart(fig, use_container_width=True)


def _show_period_metrics(df: pd.DataFrame) -> None:
    cols = st.columns(5)
    metrics_def = [
        ("Kapitał końcowy",  "net_liquidation", "last",  "${:.2f}"),
        ("Łączny PnL",       "daily_pnl",       "sum",   "${:+.2f}"),
        ("Max Drawdown",     "drawdown_pct",     "max",   "{:.2f}%"),
        ("Śr. dzienny PnL",  "daily_pnl",       "mean",  "${:+.2f}"),
        ("Otwarte pozycje",  "open_positions",  "last",  "{:.0f}"),
    ]
    for col, (label, field, agg, fmt) in zip(cols, metrics_def):
        if field in df.columns:
            val = getattr(df[field], agg)()
            col.metric(label, fmt.format(val))
        else:
            col.metric(label, "—")


def _render_mock_equity_chart() -> None:
    """Mock equity curve gdy brak danych."""
    st.caption("Przykład equity curve po uruchomieniu bota")
    import numpy as np
    np.random.seed(42)
    dates = pd.date_range("2026-10-01", periods=200, freq="1h")
    returns = np.random.normal(0.001, 0.005, 200)
    equity = 10000 * (1 + returns).cumprod()

    fig = go.Figure(go.Scatter(
        x=dates, y=equity, mode="lines",
        line=dict(color="#3b82f6", width=2),
        fill="tozeroy", fillcolor="rgba(59,130,246,0.1)",
    ))
    fig.update_layout(
        title="Przykład: Equity Curve (dane demo)", template="plotly_dark",
        plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
        font_color="#e2e8f0", height=380,
    )
    st.plotly_chart(fig, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# STRONA 3: LOGI PRO - filtrowanie, 3 pliki
# ═════════════════════════════════════════════════════════════════════════════

def page_logs_pro() -> None:
    st.title("Logi PRO")
    st.markdown("Pełny dostęp do logów systemu z filtrowaniem.")

    tab_sys, tab_err, tab_trade = st.tabs(["System", "Błędy", "Trading"])

    for tab, log_file, label in [
        (tab_sys,   "system.log",  "system"),
        (tab_err,   "errors.log",  "errors"),
        (tab_trade, "trading.log", "trading"),
    ]:
        with tab:
            _render_log_tab(log_file, label)


def _render_log_tab(filename: str, label: str) -> None:
    log_path = LOG_DIR / filename

    col1, col2, col3, col4 = st.columns([2, 2, 2, 1])
    with col1:
        level_filter = st.selectbox(
            "Poziom", ["Wszystkie", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
            key=f"log_level_{label}"
        )
    with col2:
        module_filter = st.text_input(
            "Moduł/Agent", placeholder="np. momentum_surfer, orchestrator",
            key=f"log_module_{label}"
        )
    with col3:
        time_filter = st.text_input(
            "Zawiera tekst", placeholder="np. AAPL, BUY, error",
            key=f"log_text_{label}"
        )
    with col4:
        n_lines = st.selectbox("Wierszy", [100, 200, 500, 1000], key=f"log_n_{label}")

    if not log_path.exists():
        st.warning(f"Plik `{filename}` nie istnieje. Bot jeszcze nie uruchomiony.")
        _render_mock_log()
        return

    # Wczytaj ostatnie n_lines
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            lines = f.readlines()
        lines = lines[-n_lines:]
    except Exception as e:
        st.error(f"Błąd odczytu pliku: {e}")
        return

    # Filtrowanie
    filtered = lines
    if level_filter != "Wszystkie":
        filtered = [l for l in filtered if level_filter in l]
    if module_filter:
        filtered = [l for l in filtered if module_filter.lower() in l.lower()]
    if time_filter:
        filtered = [l for l in filtered if time_filter.lower() in l.lower()]

    # Kolorowanie poziomów
    st.markdown(
        f"**{len(filtered)}** wierszy  "
        f"({len(lines)} ostatnich z pliku `{filename}`)"
    )

    # Podświetlony output
    colored_lines = []
    for line in reversed(filtered):  # od najnowszych
        line = line.rstrip()
        if "ERROR" in line or "CRITICAL" in line:
            colored_lines.append(f"[ERR] {line}")
        elif "WARNING" in line:
            colored_lines.append(f"[WRN] {line}")
        elif "SUCCESS" in line or "[OK]" in line or "filled" in line.lower():
            colored_lines.append(f"[OK]  {line}")
        else:
            colored_lines.append(f"      {line}")

    log_text = "\n".join(colored_lines[:500])  # max 500 na ekran
    st.code(log_text, language=None)

    # Download przycisku
    raw_text = "".join(filtered)
    st.download_button(
        f"Pobierz {filename}",
        data=raw_text.encode("utf-8"),
        file_name=filename,
        mime="text/plain",
        key=f"dl_log_{label}",
    )


def _render_mock_log() -> None:
    mock = """2026-10-29 14:35:22.413 | INFO     | momentum_surfer | Signal generated: AAPL BUY conf=0.84
2026-10-29 14:35:23.102 | INFO     | risk_manager    | Signal approved: AAPL BUY (drawdown=2.1%)
2026-10-29 14:35:24.891 | INFO     | orchestrator    | Order placed: AAPL BUY 5 @ 178.45
2026-10-29 14:35:25.003 | INFO     | orchestrator    | Order filled: AAPL BUY 5 @ 178.47
2026-10-29 14:34:10.557 | WARNING  | risk_manager    | Signal rejected: TSLA SELL (max positions reached)
2026-10-29 14:30:00.001 | INFO     | system          | MetricsCollector: snapshot saved
2026-10-29 14:25:33.219 | ERROR    | ibkr_connector  | Reconnect attempt 1/3...
2026-10-29 14:25:35.441 | INFO     | ibkr_connector  | Connected to IBKR TWS (paper mode)"""
    st.code(mock, language=None)


# ═════════════════════════════════════════════════════════════════════════════
# STRONA 4: SYGNAŁY PRO - pełne dane z raw_indicators
# ═════════════════════════════════════════════════════════════════════════════

def page_signals_pro() -> None:
    st.title("Sygnały PRO")
    st.markdown("Pełne dane każdego sygnału z wskaźnikami technicznymi.")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        agent_f = st.selectbox("Agent", ["Wszystkie",
            "scalper", "trend_follower", "momentum_surfer", "breakout_hunter",
            "mean_reversion", "gap_trader", "divergence_hunter", "vix_trader",
            "sentiment_trader", "options_flow", "scalp_king",
        ], key="sigpro_agent")
    with col2:
        status_f = st.selectbox("Status", [
            "Wszystkie", "Zatwierdzone", "Odrzucone", "Oczekujące"
        ], key="sigpro_status")
    with col3:
        symbol_f = st.text_input("Symbol", placeholder="AAPL", key="sigpro_symbol")
    with col4:
        sig_limit = st.selectbox("Pokaż", [50, 100, 200], key="sigpro_limit")

    url = f"/dev/signals-pro?limit={sig_limit}"
    if agent_f != "Wszystkie":
        url += f"&agent={agent_f}"
    if symbol_f:
        url += f"&symbol={symbol_f.upper()}"
    if status_f == "Zatwierdzone":
        url += "&approved=true"
    elif status_f == "Odrzucone":
        url += "&approved=false"

    signals = _api(url) or []

    if not signals:
        st.info("Brak sygnałów. Backend offline lub brak historii.")
        _render_mock_signals()
        return

    # Nagłówki tabeli skrótowej
    df = pd.DataFrame(signals)
    display_cols = ["timestamp", "agent_name", "symbol", "direction",
                    "confidence", "approved", "reject_reason"]
    existing = [c for c in display_cols if c in df.columns]
    st.dataframe(
        df[existing].head(sig_limit),
        use_container_width=True,
        height=300,
    )

    st.markdown("---")
    st.markdown("#### Szczegóły sygnałów z wskaźnikami technicznymi")

    for sig in signals[:30]:  # max 30 expanderów
        agent   = sig.get("agent_name", "?")
        symbol  = sig.get("symbol", "?")
        direction = sig.get("direction", "?")
        conf    = sig.get("confidence", 0)
        approved = sig.get("approved")
        ts      = _fmt_dt(str(sig.get("timestamp", "")))
        reasoning = sig.get("reasoning", "")
        raw     = sig.get("raw_indicators", {})
        reject  = sig.get("reject_reason", "")

        # Status badge
        if approved is True:
            status_badge = _badge("Approved", "#10b981")
        elif approved is False:
            status_badge = _badge("Rejected", "#ef4444")
        else:
            status_badge = _badge("Pending", "#f59e0b")

        dir_color = "#34d399" if direction == "BUY" else "#f87171"
        title = f"{ts} | {agent} | {_badge(direction, dir_color)} {symbol} | conf: {conf*100:.0f}%"

        with st.expander(f"{ts}  {agent}  {direction} {symbol}  {conf*100:.0f}%", expanded=False):
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown(status_badge, unsafe_allow_html=True)
                st.markdown(f"**Agent:** {agent}")
                st.markdown(f"**Symbol:** {symbol}")
                st.markdown(f"**Kierunek:** {_badge(direction, dir_color)}", unsafe_allow_html=True)
                st.markdown(f"**Confidence:** {conf*100:.1f}%")
                entry = sig.get("entry_price")
                sl    = sig.get("stop_loss")
                tp    = sig.get("take_profit")
                if entry:
                    st.markdown(f"**Entry:** ${entry:,.2f}")
                if sl:
                    st.markdown(f"**Stop Loss:** ${sl:,.2f}")
                if tp:
                    st.markdown(f"**Take Profit:** ${tp:,.2f}")
                if reject:
                    st.error(f"Odrzucony: {reject}")
            with c2:
                if reasoning:
                    st.markdown(f"**Reasoning:**\n\n{reasoning}")
                if raw:
                    st.markdown("**Raw Indicators:**")
                    st.json(raw)


def _render_mock_signals() -> None:
    st.caption("Przykład sygnałów PRO")
    mock = [
        {
            "timestamp": "2026-10-29T14:35:22Z",
            "agent_name": "momentum_surfer",
            "symbol": "AAPL",
            "direction": "BUY",
            "confidence": 0.84,
            "approved": True,
            "reasoning": "RSI(14)=28 oversold, MACD bullish crossover, volume 2.3x average",
            "raw_indicators": {
                "rsi_14": 28.3,
                "macd_signal": 0.12,
                "macd_hist": 0.08,
                "volume_ratio": 2.31,
                "sma_20": 177.50,
                "sma_50": 175.20,
                "bb_position": 0.05,
            },
            "entry_price": 178.45,
            "stop_loss": 175.50,
            "take_profit": 184.00,
        },
        {
            "timestamp": "2026-10-29T14:34:10Z",
            "agent_name": "trend_follower",
            "symbol": "TSLA",
            "direction": "SELL",
            "confidence": 0.61,
            "approved": False,
            "reject_reason": "Max daily positions (5) reached",
            "reasoning": "Death cross + bearish engulfing candle",
            "raw_indicators": {
                "rsi_14": 72.1,
                "sma_20": 242.0,
                "sma_50": 248.5,
                "adx": 28.4,
            },
        },
    ]
    for sig in mock:
        agent = sig["agent_name"]
        symbol = sig["symbol"]
        direction = sig["direction"]
        conf = sig["confidence"]
        approved = sig.get("approved")
        ts = _fmt_dt(sig["timestamp"])
        dir_color = "#34d399" if direction == "BUY" else "#f87171"

        if approved is True:
            status = _badge("Approved", "#10b981")
        else:
            status = _badge("Rejected", "#ef4444")

        with st.expander(f"{ts}  {agent}  {direction} {symbol}  {conf*100:.0f}%"):
            c1, c2 = st.columns([1, 2])
            with c1:
                st.markdown(status, unsafe_allow_html=True)
                st.markdown(f"**{_badge(direction, dir_color)}** {symbol}", unsafe_allow_html=True)
                st.markdown(f"Confidence: **{conf*100:.0f}%**")
                if sig.get("reject_reason"):
                    st.error(sig["reject_reason"])
            with c2:
                st.markdown(f"**Reasoning:** {sig.get('reasoning', '')}")
                st.json(sig.get("raw_indicators", {}))


# ═════════════════════════════════════════════════════════════════════════════
# STRONA 5: SYSTEM HEALTH - CPU/RAM/IBKR
# ═════════════════════════════════════════════════════════════════════════════

def page_system_health() -> None:
    st.title("System Health")
    st.markdown("Monitorowanie zasobów systemowych i połączeń.")

    # Auto-refresh co 10s
    try:
        from streamlit_autorefresh import st_autorefresh
        st_autorefresh(interval=10_000, key="health_refresh")
    except ImportError:
        st.caption("Zainstaluj streamlit-autorefresh dla auto-odświeżania")

    # Aktualne metryki
    health = _api("/dev/health") or {}

    if not health:
        st.warning("Backend offline — pokazuję dane lokalne")
        _render_local_health()
    else:
        _render_health_from_api(health)

    st.markdown("---")

    # Historia metryk systemowych
    st.markdown("#### Historia zasobów (ostatnia godzina)")
    history = _api("/dev/system-metrics?hours=1") or []

    if history:
        df = pd.DataFrame(history)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        _chart_system_history(df)
    else:
        st.info("Brak historii metryk — zbieranie rozpocznie się po uruchomieniu bota")


def _render_local_health() -> None:
    """Pobiera metryki lokalnie przez psutil."""
    try:
        import psutil
        cpu = psutil.cpu_percent(interval=1)
        ram = psutil.virtual_memory()
        disk = psutil.disk_usage("/")

        c1, c2, c3, c4, c5 = st.columns(5)

        # CPU
        cpu_color = "#ef4444" if cpu > 80 else "#f59e0b" if cpu > 60 else "#34d399"
        c1.metric("CPU", f"{cpu:.1f}%")

        # RAM
        ram_color = "#ef4444" if ram.percent > 85 else "#f59e0b" if ram.percent > 70 else "#34d399"
        c2.metric("RAM", f"{ram.percent:.1f}%", f"{ram.used/1024/1024:.0f} MB")

        # Disk
        c3.metric("Dysk", f"{disk.percent:.1f}%", f"{disk.free/1024/1024/1024:.1f} GB free")

        # IBKR (z shared_state jeśli dostępny)
        try:
            from core.shared_state import shared_state
            snap = shared_state.snapshot()
            ibkr = snap.get("ibkr_connected", False)
            c4.metric("IBKR", "Connected" if ibkr else "Offline")
            c5.metric("Tryb", "PAPER" if snap.get("paper_mode", True) else "LIVE")
        except Exception:
            c4.metric("IBKR", "Unknown")
            c5.metric("Tryb", "—")

        # Gauge chart CPU
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=cpu,
            title={"text": "CPU %", "font": {"color": "#e2e8f0"}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#e2e8f0"},
                "bar": {"color": cpu_color},
                "bgcolor": "#1e293b",
                "steps": [
                    {"range": [0, 60], "color": "#0f2027"},
                    {"range": [60, 80], "color": "#1a1a2e"},
                    {"range": [80, 100], "color": "#2d1b1b"},
                ],
                "threshold": {"line": {"color": "#ef4444", "width": 3}, "value": 80},
            },
            number={"font": {"color": cpu_color}},
        ))
        fig_ram = go.Figure(go.Indicator(
            mode="gauge+number",
            value=ram.percent,
            title={"text": "RAM %", "font": {"color": "#e2e8f0"}},
            gauge={
                "axis": {"range": [0, 100], "tickcolor": "#e2e8f0"},
                "bar": {"color": ram_color},
                "bgcolor": "#1e293b",
                "steps": [
                    {"range": [0, 70], "color": "#0f2027"},
                    {"range": [70, 85], "color": "#1a1a2e"},
                    {"range": [85, 100], "color": "#2d1b1b"},
                ],
                "threshold": {"line": {"color": "#ef4444", "width": 3}, "value": 85},
            },
            number={"font": {"color": ram_color}},
        ))
        for fig_g in [fig, fig_ram]:
            fig_g.update_layout(
                paper_bgcolor="#0f172a", font_color="#e2e8f0", height=250
            )

        col_g1, col_g2 = st.columns(2)
        col_g1.plotly_chart(fig, use_container_width=True)
        col_g2.plotly_chart(fig_ram, use_container_width=True)

    except ImportError:
        st.error("psutil nie zainstalowany. Dodaj do requirements.txt")


def _render_health_from_api(health: dict) -> None:
    c1, c2, c3, c4, c5, c6 = st.columns(6)
    c1.metric("CPU", f"{health.get('cpu_pct', 0):.1f}%")
    c2.metric("RAM", f"{health.get('ram_pct', 0):.1f}%",
              f"{health.get('ram_mb', 0):.0f} MB")
    c3.metric("IBKR", "Connected" if health.get("ibkr_connected") else "Offline")
    c4.metric("Agenci", health.get("active_agents", 0))
    c5.metric("Sygnały dziś", health.get("signals_today", 0))
    c6.metric("Błędy dziś", health.get("errors_today", 0))


def _chart_system_history(df: pd.DataFrame) -> None:
    fig = go.Figure()
    if "cpu_pct" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["cpu_pct"],
            name="CPU %", mode="lines",
            line=dict(color="#3b82f6", width=2),
        ))
    if "ram_pct" in df.columns:
        fig.add_trace(go.Scatter(
            x=df["timestamp"], y=df["ram_pct"],
            name="RAM %", mode="lines",
            line=dict(color="#f59e0b", width=2),
        ))
    fig.update_layout(
        title="CPU i RAM (ostatnia godzina)",
        template="plotly_dark",
        plot_bgcolor="#0f172a", paper_bgcolor="#0f172a",
        font_color="#e2e8f0", height=300,
        yaxis=dict(range=[0, 100]),
        hovermode="x unified",
    )
    st.plotly_chart(fig, use_container_width=True)


# ═════════════════════════════════════════════════════════════════════════════
# STRONA 6: EXPORT CSV
# ═════════════════════════════════════════════════════════════════════════════

def page_dev_export() -> None:
    st.title("Export Danych")
    st.markdown("Pobierz surowe dane systemu do analizy w Excel/Python/R.")

    col1, col2 = st.columns(2)

    with col1:
        st.markdown("#### Export tabelaryczny")

        export_type = st.selectbox("Dane", [
            "Transakcje (orders)",
            "Sygnały (signals)",
            "Audit Log",
            "PnL History (equity snapshots)",
            "Zdarzenia agentów (agent_events)",
            "Metryki systemowe",
        ], key="export_type")

        date_from = st.date_input("Od", value=datetime.now().date() - timedelta(days=30),
                                  key="export_from")
        date_to   = st.date_input("Do", value=datetime.now().date(), key="export_to")
        fmt       = st.radio("Format", ["CSV", "JSON"], horizontal=True, key="export_fmt")

        if st.button("Przygotuj export", type="primary", use_container_width=True):
            _do_export(export_type, str(date_from), str(date_to), fmt)

    with col2:
        st.markdown("#### Szybkie statystyki")

        stats = _api("/dev/export-stats") or {}
        if stats:
            rows = [
                ("Transakcje łącznie", stats.get("total_orders", 0)),
                ("Sygnały łącznie",    stats.get("total_signals", 0)),
                ("Wpisy audit log",    stats.get("total_audit", 0)),
                ("Snapshoty equity",   stats.get("total_equity_snaps", 0)),
                ("Zdarzenia agentów",  stats.get("total_agent_events", 0)),
                ("DB size",            stats.get("db_size_mb", "—")),
            ]
            for label, val in rows:
                c1, c2 = st.columns([2, 1])
                c1.write(label)
                c2.write(f"**{val}**")
        else:
            st.info("Backend offline — statystyki niedostępne")

        st.markdown("---")
        st.markdown("#### Backup całej bazy")
        st.caption("Plik SQLite z całą historią tradingu")

        db_path = Path(__file__).parent.parent.parent / "data" / "trading.db"
        if db_path.exists():
            with open(db_path, "rb") as f:
                db_bytes = f.read()
            st.download_button(
                "Pobierz trading.db",
                data=db_bytes,
                file_name=f"trading_backup_{datetime.now().strftime('%Y%m%d_%H%M')}.db",
                mime="application/octet-stream",
                use_container_width=True,
            )
            size_mb = db_path.stat().st_size / 1024 / 1024
            st.caption(f"Rozmiar: {size_mb:.2f} MB")
        else:
            st.warning("Baza danych nie istnieje. Uruchom bota.")


def _do_export(export_type: str, date_from: str, date_to: str, fmt: str) -> None:
    """Pobiera dane z API i udostępnia do pobrania."""
    endpoint_map = {
        "Transakcje (orders)":             "/dev/export/orders",
        "Sygnały (signals)":               "/dev/export/signals",
        "Audit Log":                       "/dev/export/audit-log",
        "PnL History (equity snapshots)":  "/dev/export/equity",
        "Zdarzenia agentów (agent_events)": "/dev/export/agent-events",
        "Metryki systemowe":               "/dev/export/system-metrics",
    }

    endpoint = endpoint_map.get(export_type, "")
    url = f"{endpoint}?from={date_from}&to={date_to}"
    data = _api(url) or []

    if not data:
        st.warning("Brak danych do exportu lub backend offline.")
        _generate_mock_export(export_type, fmt)
        return

    if fmt == "CSV":
        df = pd.DataFrame(data)
        csv_bytes = df.to_csv(index=False).encode("utf-8")
        fname = f"{export_type.split()[0].lower()}_{date_from}_{date_to}.csv"
        st.download_button(
            f"Pobierz {fname}", data=csv_bytes,
            file_name=fname, mime="text/csv",
        )
        st.success(f"Gotowe! {len(df)} wierszy")
    else:
        json_bytes = json.dumps(data, indent=2, default=str).encode("utf-8")
        fname = f"{export_type.split()[0].lower()}_{date_from}_{date_to}.json"
        st.download_button(
            f"Pobierz {fname}", data=json_bytes,
            file_name=fname, mime="application/json",
        )
        st.success(f"Gotowe! {len(data)} rekordów")


def _generate_mock_export(export_type: str, fmt: str) -> None:
    """Generuje mock CSV gdy backend offline."""
    st.caption("Przykładowy CSV (backend offline)")
    mock_df = pd.DataFrame([
        {"timestamp": "2026-10-29 14:35:22", "symbol": "AAPL",
         "side": "BUY", "quantity": 5, "price": 178.47, "status": "FILLED", "agent": "momentum_surfer"},
        {"timestamp": "2026-10-29 13:10:05", "symbol": "MSFT",
         "side": "SELL", "quantity": 3, "price": 420.10, "status": "FILLED", "agent": "trend_follower"},
    ])
    csv = mock_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "Pobierz przykład (mock)", data=csv,
        file_name="mock_export.csv", mime="text/csv",
    )
