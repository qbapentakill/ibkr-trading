"""
AI Chat Engine – naturalny język jako interfejs sterowania systemem.

Obsługuje:
- OpenAI GPT-4o / GPT-3.5-turbo (jeśli OPENAI_API_KEY ustawiony)
- Ollama (lokalny LLM, np. llama3, mistral) jako fallback
- Wbudowany parser komend (bez LLM) jako ostateczny fallback

Możliwości AI Chata:
──────────────────
INFORMACYJNE:
  "Jaki jest aktualny status systemu?"
  "Pokaż otwarte pozycje"
  "Jak radzi sobie TrendFollower?"
  "Ile wynosi dzisiejszy PnL?"
  "Jakie są ostatnie sygnały?"
  "Pokaż aktualne limity ryzyka"
  "Jakie są ostatnie newsy HIGH impact?"

STEROWANIE:
  "Wyłącz Scalper"
  "Włącz TrendFollower"
  "Ustaw max alokację MeanReversion na 15%"
  "Zmień dzienny limit straty na 300 dolarów"
  "Ustaw max drawdown na 8%"
  "Zmień pozycję size Scalpera na 2%"

BEZPIECZEŃSTWO:
  "Aktywuj emergency stop" → wymaga hasła z panelu
  "Zamknij wszystkie pozycje" → wymaga potwierdzenia

ANALITYCZNE:
  "Który agent ma najlepszy win rate?"
  "Dlaczego TrendFollower nie generuje sygnałów?"
  "Jakie są sugestie optymalizacji?"
  "Opisz reżim rynkowy"

Każda komenda sterująca jest logowana w audit logu.
"""
from __future__ import annotations

import asyncio
import json
import re
from datetime import datetime
from typing import Any, Optional

from config.settings import get_settings
from core.logger import get_logger
from core.models import AgentName, AgentStatus
from core.shared_state import shared_state

log      = get_logger(__name__)
settings = get_settings()


# ══════════════════════════════════════════════════════════════════════════════
# System Prompt
# ══════════════════════════════════════════════════════════════════════════════

SYSTEM_PROMPT = """Jesteś inteligentnym asystentem AI systemu automatycznego tradingu IBKR Multi-Agent.

TWOJA ROLA:
- Pomagasz użytkownikowi monitorować i sterować systemem tradingowym
- Odpowiadasz na pytania o rynek, strategie, kryptowaluty, akcje, ETF, wskaźniki techniczne
- Tłumaczysz jak działają agenci, ich strategie i wyniki
- Analizujesz dane rynkowe i dajesz rekomendacje
- Odpowiadasz po POLSKU (chyba że użytkownik pisze po angielsku)
- Jesteś precyzyjny, zwięzły i profesjonalny jak doświadczony trader

MOŻESZ ODPOWIADAĆ NA:
- Pytania o rynek (akcje, krypto, ETF, forex, surowce)
- Analizę techniczną (RSI, MACD, Bollinger Bands, EMA, ADX, itp.)
- Strategie tradingowe (trend following, mean reversion, scalping, breakout)
- Makroekonomię (Fed, inflacja, stopy procentowe, GDP, NFP)
- Wyniki i działanie agentów w systemie
- Zarządzanie ryzykiem i pozycjami
- Optymalizację strategii
- Ogólne pytania finansowe i inwestycyjne

AGENCI W SYSTEMIE:
1. TrendFollower – EMA+ADX multi-TF, cierpliwy strateg
2. MeanReversion – BB+RSI+zscore, matematyczny kontrarian
3. Scalper – volume spikes, agresywny krótkoterminowy
4. BreakoutHunter – S/R breakout + ATR, oportunista
5. SentimentTrader – RSS+VADER+NLP, reaguje na Fed/Trump/Musk
6. OptionsFlow – unusual options activity, śledzi smart money
7. GapTrader – luki cenowe przy otwarciu
8. MomentumSurfer – ROC+RSI, najsilniejsze momentum
9. VIXTrader – indeks strachu, kupuje panikę
10. DivergenceHunter – dywergencje RSI/MACD vs cena
11. ScalpKing – ultra-szybki scalp 9:30-10:45 EST
12. WhaleTracker – tropiciel dużych transakcji
13. MarketAnalyst – regime detection, korelacje sektorów
14. NewsAnalyst – HIGH/MEDIUM/LOW impact klasyfikacja
15. EarningsWatcher – kalendarze wyników spółek
16. MacroAnalyst – dane makro → agresywność systemu
17. CorrelationGuard – wykrywa skupienie korelacji
18. HeatmapAnalyst – analiza sektorów rynku
19. EconomicCalendar – blokada przed Fed/NFP/CPI
20. RiskManager – absolutne VETO, zarządza ryzykiem
21. PerformanceReviewer – post-trade analytics
22. PortfolioAllocator – Kelly Criterion, dynamiczna alokacja
23. ResearchAgent – MTF analiza fundamentalna
24. SmartMoneyTracker – OBV, CMF, akumulacja/dystrybucja

DOSTĘPNE KOMENDY SYSTEMOWE (JSON format):
- enable_agent, disable_agent, set_allocation, set_risk_param
- emergency_stop, get_status, get_positions, get_signals
- get_performance, get_news

ZASADY:
- Emergency Stop i zamykanie pozycji wymagają potwierdzenia
- Nigdy nie aktywuj real mode przez chat
- Bądź pomocny, edukacyjny i konkretny

FORMAT: Jeśli chcesz wykonać akcję systemową, dodaj blok:
```action
{"action": "...", ...}
```
"""

TWOJA ROLA:
- Pomagasz użytkownikowi monitorować i sterować systemem tradingowym
- Odpowiadasz po POLSKU (chyba że użytkownik pisze po angielsku)
- Jesteś precyzyjny, zwięzły i profesjonalny
- Przy poleceniach sterujących ZAWSZE pytasz o potwierdzenie przed wykonaniem

AGENCI W SYSTEMIE:
1. TrendFollower – EMA+ADX, TF 1H/4H, spokojny strateg
2. MeanReversion – BB+RSI+zscore, TF 15m/1H, matematyczny kontrarian
3. Scalper – volume spikes + krótkie MA, TF 1m/5m, agresywny
4. BreakoutHunter – S/R breakout + ATR, TF 15m/1H, oportunista
5. SentimentTrader – RSS+VADER+NLP, event-driven, reaguje na Fed/Trump/Musk
6. MarketAnalyst – regime detection, korelacje
7. NewsAnalyst – RSS feeds, HIGH/MEDIUM/LOW impact klasyfikacja
8. ResearchAgent – MTF analiza, fundamenty
9. SmartMoneyTracker – OBV, CMF, akumulacja/dystrybucja
10. RiskManager – absolutne VETO, zarządza ryzykiem
11. PerformanceReviewer – post-trade analytics, Sharpe, win rate
12. PortfolioAllocator – Kelly Criterion, dynamiczna alokacja

DOSTĘPNE KOMENDY SYSTEMOWE (JSON format):
- enable_agent: {"action": "enable_agent", "agent": "TrendFollower"}
- disable_agent: {"action": "disable_agent", "agent": "Scalper"}
- set_allocation: {"action": "set_allocation", "agent": "MeanReversion", "pct": 15.0}
- set_risk_param: {"action": "set_risk_param", "param": "max_daily_loss_usd", "value": 300}
- emergency_stop: {"action": "emergency_stop"} ← WYMAGA POTWIERDZENIA
- get_status: {"action": "get_status"}
- get_positions: {"action": "get_positions"}
- get_signals: {"action": "get_signals"}
- get_performance: {"action": "get_performance"}
- get_news: {"action": "get_news"}

ZASADY BEZPIECZEŃSTWA:
- Emergency Stop, zamykanie pozycji i zmiana limitów ryzyka wymagają jawnego potwierdzenia
- Zawsze informuj użytkownika o konsekwencjach przed wykonaniem polecenia sterującego
- Nigdy nie aktywuj real mode – to wymaga fizycznej interwencji w panelu
- Przy niejasnych poleceniach pytaj o doprecyzowanie

FORMAT ODPOWIEDZI:
Jeśli chcesz wykonać akcję systemową, umieść na końcu odpowiedzi blok JSON:
```action
{"action": "...", ...}
```
"""


# ══════════════════════════════════════════════════════════════════════════════
# Główny silnik
# ══════════════════════════════════════════════════════════════════════════════

class AIChatEngine:
    _instance: Optional["AIChatEngine"] = None

    def __init__(self) -> None:
        self._backend = self._detect_backend()
        self._pending_confirmations: dict[str, dict] = {}
        log.info("AI Chat Engine uruchomiony (backend: {})", self._backend)

    @classmethod
    def get_instance(cls) -> "AIChatEngine":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _detect_backend(self) -> str:
        s = get_settings()
        if getattr(s, "openai_api_key", None):
            return "openai"
        if getattr(s, "groq_api_key", None):
            return "groq"
        # Sprawdź czy Ollama działa lokalnie
        try:
            import httpx
            r = httpx.get("http://localhost:11434/api/tags", timeout=2)
            if r.status_code == 200:
                return "ollama"
        except Exception:
            pass
        return "builtin"

    # ──────────────────────────────────────────────────────────────────────────
    # Główna metoda chat
    # ──────────────────────────────────────────────────────────────────────────

    async def chat(
        self,
        message: str,
        history: list[dict],
        user: str = "admin",
    ) -> dict[str, Any]:
        """
        Przetwarza wiadomość użytkownika i zwraca odpowiedź + opcjonalną akcję.

        Zwraca:
        {
            "response": str,          – tekst odpowiedzi
            "action_taken": str|None, – nazwa wykonanej akcji
            "action_result": dict,    – wynik akcji
            "requires_confirmation": bool,
            "pending_action": dict|None,
        }
        """
        # Sprawdź czy to potwierdzenie oczekującej akcji
        pending_key = f"{user}_pending"
        if pending_key in self._pending_confirmations:
            if self._is_confirmation(message):
                pending = self._pending_confirmations.pop(pending_key)
                result  = await self._execute_action(pending, user)
                return {
                    "response":               f"✅ Wykonano: {result.get('message', 'OK')}",
                    "action_taken":           pending.get("action"),
                    "action_result":          result,
                    "requires_confirmation":  False,
                    "pending_action":         None,
                }
            elif self._is_cancellation(message):
                self._pending_confirmations.pop(pending_key)
                return {
                    "response":              "❌ Anulowano akcję.",
                    "action_taken":          None,
                    "action_result":         {},
                    "requires_confirmation": False,
                    "pending_action":        None,
                }

        # Przygotuj kontekst systemowy
        context = self._build_context()

        # Wywołaj LLM lub wbudowany parser
        if self._backend == "openai":
            raw_response = await self._openai_chat(message, history, context)
        elif self._backend == "groq":
            raw_response = await self._groq_chat(message, history, context)
        elif self._backend == "ollama":
            raw_response = await self._ollama_chat(message, history, context)
        else:
            raw_response = self._builtin_response(message, context)

        # Parsuj akcję z odpowiedzi
        text, action = self._parse_action(raw_response)

        if action is None:
            return {
                "response":              text,
                "action_taken":          None,
                "action_result":         {},
                "requires_confirmation": False,
                "pending_action":        None,
            }

        # Akcje wymagające potwierdzenia
        dangerous = {"emergency_stop", "close_all_positions", "disable_agent"}
        if action.get("action") in dangerous:
            self._pending_confirmations[pending_key] = action
            confirm_text = (
                f"{text}\n\n"
                f"⚠️ **Ta akcja wymaga potwierdzenia.** "
                f"Wpisz **'tak'** aby wykonać lub **'nie'** aby anulować.\n"
                f"Akcja: `{json.dumps(action, ensure_ascii=False)}`"
            )
            return {
                "response":              confirm_text,
                "action_taken":          None,
                "action_result":         {},
                "requires_confirmation": True,
                "pending_action":        action,
            }

        # Natychmiastowe wykonanie bezpiecznych akcji
        result = await self._execute_action(action, user)
        final_text = text
        if result.get("data"):
            final_text += f"\n\n```\n{json.dumps(result['data'], ensure_ascii=False, indent=2, default=str)}\n```"

        return {
            "response":              final_text,
            "action_taken":          action.get("action"),
            "action_result":         result,
            "requires_confirmation": False,
            "pending_action":        None,
        }

    # ──────────────────────────────────────────────────────────────────────────
    # LLM backends
    # ──────────────────────────────────────────────────────────────────────────

    async def _groq_chat(
        self, message: str, history: list[dict], context: str
    ) -> str:
        """Groq API — darmowy dostęp do Llama 3.3 70B."""
        try:
            import httpx
            api_key = get_settings().groq_api_key
            model   = get_settings().groq_model

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT + "\n\nAKTUALNY STAN SYSTEMU:\n" + context}
            ]
            for h in history[-10:]:
                messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": message})

            async with httpx.AsyncClient(timeout=30) as client:
                resp = await client.post(
                    "https://api.groq.com/openai/v1/chat/completions",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={
                        "model":       model,
                        "messages":    messages,
                        "temperature": 0.4,
                        "max_tokens":  2000,
                    },
                )
                data = resp.json()
                if resp.status_code == 200:
                    return data["choices"][0]["message"]["content"]
                else:
                    log.error("Groq error: {}", data)
                    return self._builtin_response(message, context)
        except Exception as exc:
            log.error("Groq error: {}", exc)
            return self._builtin_response(message, context)

    async def _openai_chat(
        self, message: str, history: list[dict], context: str
    ) -> str:
        try:
            from openai import AsyncOpenAI
            client = AsyncOpenAI(api_key=get_settings().openai_api_key)

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT + "\n\nAKTUALNY STAN SYSTEMU:\n" + context}
            ]
            # Ostatnie 10 wiadomości z historii
            for h in history[-10:]:
                messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": message})

            response = await client.chat.completions.create(
                model=getattr(get_settings(), "openai_model", "gpt-4o-mini"),
                messages=messages,
                temperature=0.3,
                max_tokens=1500,
            )
            return response.choices[0].message.content or ""
        except Exception as exc:
            log.error("OpenAI error: {}", exc)
            return self._builtin_response(message, context)

    async def _ollama_chat(
        self, message: str, history: list[dict], context: str
    ) -> str:
        try:
            import httpx
            model = getattr(get_settings(), "ollama_model", "llama3")

            messages = [
                {"role": "system", "content": SYSTEM_PROMPT + "\n\nSTAN:\n" + context}
            ]
            for h in history[-8:]:
                messages.append({"role": h["role"], "content": h["content"]})
            messages.append({"role": "user", "content": message})

            async with httpx.AsyncClient(timeout=60) as client:
                resp = await client.post(
                    "http://localhost:11434/api/chat",
                    json={"model": model, "messages": messages, "stream": False},
                )
                data = resp.json()
                return data.get("message", {}).get("content", "")
        except Exception as exc:
            log.error("Ollama error: {}", exc)
            return self._builtin_response(message, context)

    def _builtin_response(self, message: str, context: str) -> str:
        """
        Wbudowany parser komend – działa bez LLM.
        Obsługuje podstawowe zapytania i komendy przez regex.
        """
        msg = message.lower().strip()

        # ── Zapytania informacyjne ────────────────────────────────────────────
        if any(w in msg for w in ["status", "stan systemu", "jak działa"]):
            snap = shared_state.snapshot()
            emergency = "🚨 AKTYWNY" if snap["emergency_stop"] else "✅ Nieaktywny"
            return (
                f"**Stan systemu:**\n"
                f"- Emergency Stop: {emergency}\n"
                f"- Dzienny PnL: ${snap['daily_pnl']:.2f}\n"
                f"- Drawdown: {snap['drawdown_pct']:.2f}%\n"
                f"- Otwarte pozycje: {len(snap['positions'])}\n"
                f"- Kapitał: ${snap['account'].get('net_liquidation', 0):.2f}\n"
                "```action\n{\"action\": \"get_status\"}\n```"
            )

        if any(w in msg for w in ["pozycje", "positions", "otwarte"]):
            return "Pobieranie otwartych pozycji...\n```action\n{\"action\": \"get_positions\"}\n```"

        if any(w in msg for w in ["sygnały", "signals", "ostatnie sygnały"]):
            return "Pobieranie ostatnich sygnałów...\n```action\n{\"action\": \"get_signals\"}\n```"

        if any(w in msg for w in ["news", "newsy", "wiadomości"]):
            return "Pobieranie newsów...\n```action\n{\"action\": \"get_news\"}\n```"

        if any(w in msg for w in ["wydajność", "performance", "wyniki"]):
            return "Pobieranie raportów wydajności...\n```action\n{\"action\": \"get_performance\"}\n```"

        if any(w in msg for w in ["pnl", "zysk", "strata", "profit"]):
            snap = shared_state.snapshot()
            return (
                f"**PnL:**\n"
                f"- Dzienny PnL: **${snap['daily_pnl']:.2f}**\n"
                f"- Unrealized: ${snap['account'].get('unrealized_pnl', 0):.2f}\n"
                f"- Drawdown: {snap['drawdown_pct']:.2f}%"
            )

        # ── Komendy sterujące ─────────────────────────────────────────────────
        # Włącz agenta
        for agent in AgentName:
            if f"włącz {agent.value.lower()}" in msg or f"enable {agent.value.lower()}" in msg:
                return (
                    f"Czy na pewno chcesz **włączyć** agenta **{agent.value}**?\n"
                    f"Wpisz 'tak' aby potwierdzić.\n"
                    f"```action\n{{\"action\": \"enable_agent\", \"agent\": \"{agent.value}\"}}\n```"
                )
            if f"wyłącz {agent.value.lower()}" in msg or f"disable {agent.value.lower()}" in msg:
                return (
                    f"Czy na pewno chcesz **wyłączyć** agenta **{agent.value}**?\n"
                    f"Wpisz 'tak' aby potwierdzić.\n"
                    f"```action\n{{\"action\": \"disable_agent\", \"agent\": \"{agent.value}\"}}\n```"
                )

        # Alokacja
        alloc_match = re.search(
            r"alokacj[ęa]\s+(\w+)\s+na\s+(\d+(?:\.\d+)?)\s*%", msg
        )
        if alloc_match:
            agent_name = alloc_match.group(1).capitalize()
            pct        = float(alloc_match.group(2))
            return (
                f"Ustawiam alokację **{agent_name}** na **{pct}%**...\n"
                f"```action\n{{\"action\": \"set_allocation\", \"agent\": \"{agent_name}\", \"pct\": {pct}}}\n```"
            )

        # Limit straty
        loss_match = re.search(r"limit\s+strat[y]\s+na\s+(\d+(?:\.\d+)?)", msg)
        if loss_match:
            val = float(loss_match.group(1))
            return (
                f"Ustawiam dzienny limit straty na **${val:.0f}**...\n"
                f"```action\n{{\"action\": \"set_risk_param\", \"param\": \"max_daily_loss_usd\", \"value\": {val}}}\n```"
            )

        # Emergency stop
        if any(w in msg for w in ["emergency", "zatrzymaj wszystko", "stop all", "wyłącz wszystko"]):
            return (
                "⚠️ Czy na pewno chcesz aktywować **EMERGENCY STOP**?\n"
                "Zatrzyma to wszystkich agentów i (opcjonalnie) zamknie wszystkie pozycje.\n"
                "Wpisz **'tak'** aby potwierdzić lub **'nie'** aby anulować.\n"
                "```action\n{\"action\": \"emergency_stop\"}\n```"
            )

        # ── Domyślna odpowiedź ─────────────────────────────────────────────
        return (
            "Jestem asystentem AI systemu tradingowego. Mogę:\n\n"
            "📊 **Informacje:**\n"
            "- _'status'_ – stan systemu\n"
            "- _'pozycje'_ – otwarte pozycje\n"
            "- _'sygnały'_ – ostatnie sygnały agentów\n"
            "- _'wydajność'_ – raporty agentów\n"
            "- _'pnl'_ – aktualny zysk/strata\n\n"
            "⚙️ **Sterowanie:**\n"
            "- _'włącz/wyłącz [nazwa agenta]'_\n"
            "- _'ustaw alokację [agent] na X%'_\n"
            "- _'zmień limit straty na X dolarów'_\n\n"
            "🚨 **Bezpieczeństwo:**\n"
            "- _'emergency stop'_ – zatrzymaj wszystko\n\n"
            f"Backend AI: **{self._backend}** | "
            f"Aby użyć GPT-4o dodaj OPENAI_API_KEY do .env"
        )

    # ──────────────────────────────────────────────────────────────────────────
    # Wykonanie akcji
    # ──────────────────────────────────────────────────────────────────────────

    async def _execute_action(self, action: dict, user: str) -> dict[str, Any]:
        """Wykonuje akcję systemową wyodrębnioną z odpowiedzi LLM."""
        act = action.get("action", "")

        try:
            if act == "get_status":
                return {"ok": True, "data": shared_state.snapshot()}

            elif act == "get_positions":
                return {"ok": True, "data": {s: p.model_dump() for s, p in shared_state.positions.items()}}

            elif act == "get_signals":
                return {"ok": True, "data": [s.model_dump() for s in shared_state.recent_signals[:15]]}

            elif act == "get_performance":
                return {"ok": True, "data": getattr(shared_state, "performance_reports", {})}

            elif act == "get_news":
                news = getattr(shared_state, "latest_news", [])
                return {"ok": True, "data": news[:10]}

            elif act == "enable_agent":
                name = AgentName(action["agent"])
                cfg  = shared_state.agent_configs[name]
                cfg.enabled = True
                await shared_state.set_agent_config(cfg)
                await shared_state.set_agent_status(name, AgentStatus.ACTIVE)
                return {"ok": True, "message": f"Agent {name.value} włączony"}

            elif act == "disable_agent":
                name = AgentName(action["agent"])
                cfg  = shared_state.agent_configs[name]
                cfg.enabled = False
                await shared_state.set_agent_config(cfg)
                await shared_state.set_agent_status(name, AgentStatus.DISABLED)
                return {"ok": True, "message": f"Agent {name.value} wyłączony"}

            elif act == "set_allocation":
                name = AgentName(action["agent"])
                pct  = float(action["pct"])
                cfg  = shared_state.agent_configs[name]
                cfg.max_allocation_pct = max(0.0, min(50.0, pct))
                await shared_state.set_agent_config(cfg)
                return {"ok": True, "message": f"Alokacja {name.value} → {pct:.1f}%"}

            elif act == "set_risk_param":
                param = action["param"]
                value = float(action["value"])
                lim   = shared_state.risk_limits
                if hasattr(lim, param):
                    setattr(lim, param, value)
                    return {"ok": True, "message": f"Limit ryzyka {param} → {value}"}
                return {"ok": False, "message": f"Nieznany parametr: {param}"}

            elif act == "emergency_stop":
                await shared_state.trigger_emergency_stop(f"AI Chat: {user}")
                return {"ok": True, "message": "🚨 EMERGENCY STOP AKTYWOWANY"}

            else:
                return {"ok": False, "message": f"Nieznana akcja: {act}"}

        except Exception as exc:
            log.error("Błąd wykonania akcji AI {}: {}", act, exc)
            return {"ok": False, "message": str(exc)}

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    def _build_context(self) -> str:
        """Buduje zwięzły kontekst systemowy dla LLM."""
        snap = shared_state.snapshot()
        agents_summary = []
        for name, data in snap["agents"].items():
            state  = data["state"]
            config = data["config"]
            agents_summary.append(
                f"  {name}: status={state['status']} "
                f"enabled={config['enabled']} "
                f"alloc={config['max_allocation_pct']}%"
            )

        positions_summary = []
        for sym, pos in snap["positions"].items():
            positions_summary.append(
                f"  {sym}: qty={pos['quantity']} "
                f"avg_cost={pos['avg_cost']} "
                f"pnl={pos['unrealized_pnl']:.2f}"
            )

        return (
            f"Czas: {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}\n"
            f"Emergency Stop: {snap['emergency_stop']}\n"
            f"Dzienny PnL: ${snap['daily_pnl']:.2f}\n"
            f"Drawdown: {snap['drawdown_pct']:.2f}%\n"
            f"Kapitał netto: ${snap['account'].get('net_liquidation', 0):.2f}\n"
            f"Paper mode: {not settings.real_mode}\n"
            f"Agenci:\n" + "\n".join(agents_summary) + "\n"
            f"Otwarte pozycje ({len(snap['positions'])}):\n"
            + ("\n".join(positions_summary) if positions_summary else "  brak") + "\n"
            f"Risk limits:\n"
            f"  max_daily_loss={snap['risk_limits']['max_daily_loss_usd']}$\n"
            f"  max_drawdown={snap['risk_limits']['max_drawdown_pct']}%\n"
            f"  capital={snap['risk_limits']['total_capital_usd']}$"
        )

    def _parse_action(self, text: str) -> tuple[str, Optional[dict]]:
        """Wyodrębnia JSON akcji z bloku ```action ... ```."""
        pattern = r"```action\s*\n(.*?)\n```"
        match   = re.search(pattern, text, re.DOTALL)
        if not match:
            return text, None
        try:
            action = json.loads(match.group(1).strip())
            clean_text = text[:match.start()].strip()
            return clean_text, action
        except json.JSONDecodeError:
            return text, None

    def _is_confirmation(self, message: str) -> bool:
        return message.lower().strip() in {"tak", "yes", "potwierdzam", "ok", "confirm", "wykonaj"}

    def _is_cancellation(self, message: str) -> bool:
        return message.lower().strip() in {"nie", "no", "anuluj", "cancel", "cofnij"}
