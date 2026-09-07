"""
AgentLearningEngine – system uczenia agentów na podstawie wyników sesji testowych.

Jak działa:
1. Po każdej sesji analizuje transakcje każdego agenta
2. Identyfikuje wzorce błędów (za wysoka pewność, zły kierunek, złe wyczucie czasu)
3. Dostosowuje parametry agenta (progi pewności, wagi wskaźników, interwały)
4. Zapisuje historię uczenia do pliku JSON
5. Generuje raport "czego się nauczyłem"

To NIE jest deep learning — to adaptacyjny system reguł oparty na statystykach.
Efekt: agenci z czasem stają się bardziej ostrożni tam gdzie często popełniają błędy.
"""
from __future__ import annotations

import json
import os
import random
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log = get_logger(__name__)

# Ścieżka do pliku z pamięcią agentów
MEMORY_FILE = Path("data/agent_memory.json")


# ─────────────────────────────────────────────────────────────────────────────
# Modele
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class AgentLesson:
    """Jedna lekcja — co agent zmienił po sesji."""
    session_id:    str
    timestamp:     str
    agent_name:    str
    win_rate:      float
    total_pnl:     float
    trades_count:  int

    # Co zmieniono
    changes:       list[dict] = field(default_factory=list)
    # Słowne podsumowanie
    summary:       str = ""
    # Nowe parametry po uczeniu
    new_params:    dict = field(default_factory=dict)


@dataclass
class AgentMemory:
    """Długoterminowa pamięć agenta — akumuluje się przez wiele sesji."""
    agent_name:        str
    sessions_count:    int = 0
    total_trades:      int = 0
    total_wins:        int = 0
    avg_win_rate:      float = 0.0
    avg_pnl:           float = 0.0
    best_symbols:      list[str] = field(default_factory=list)
    worst_symbols:     list[str] = field(default_factory=list)

    # Aktualne parametry (dostosowywane przez learning engine)
    confidence_threshold: float = 0.50   # minimalna pewność do otwarcia pozycji
    position_size_mult:   float = 1.0    # mnożnik wielkości pozycji (0.5 = ostrożniejszy)
    signal_cooldown_mult: float = 1.0    # mnożnik interwału (1.5 = rzadziej handluje)
    long_bias:            float = 0.5    # skłonność do LONG (0.5 = neutralny)

    lessons:              list[dict] = field(default_factory=list)


# ─────────────────────────────────────────────────────────────────────────────
# Silnik uczenia
# ─────────────────────────────────────────────────────────────────────────────

class AgentLearningEngine:
    """
    Analizuje wyniki sesji i dostosowuje parametry agentów.

    Użycie:
        engine  = AgentLearningEngine()
        lessons = engine.learn_from_session(session_report)
    """

    def __init__(self) -> None:
        self._memories: dict[str, AgentMemory] = {}
        self._load_memories()

    # ── Publiczne API ─────────────────────────────────────────────────────────

    def learn_from_session(self, report: dict) -> list[AgentLesson]:
        """
        Główna metoda — analizuje raport sesji i uczy agentów.
        Zwraca listę lekcji (jedna per agent).
        """
        session_id  = report.get("session_id", "unknown")
        agent_stats = report.get("agent_stats", {})
        trades      = report.get("trades", [])
        lessons     = []

        log.info("🎓 AgentLearningEngine: analizuję sesję {} ({} agentów)",
                 session_id, len(agent_stats))

        for agent_name, stats in agent_stats.items():
            agent_trades = [t for t in trades if t.get("agent") == agent_name
                           and t.get("status") in ("CLOSED", "EXPIRED")]

            if not agent_trades:
                continue

            lesson = self._analyze_agent(session_id, agent_name, stats, agent_trades)
            lessons.append(lesson)

            # Zapisz lekcję do pamięci agenta
            memory = self._get_or_create_memory(agent_name)
            memory.lessons.append(asdict(lesson))
            # Zachowaj max 50 lekcji
            if len(memory.lessons) > 50:
                memory.lessons = memory.lessons[-50:]

        self._save_memories()
        return lessons

    def get_agent_params(self, agent_name: str) -> dict:
        """Zwraca aktualne parametry agenta (po uczeniu)."""
        memory = self._get_or_create_memory(agent_name)
        return {
            "confidence_threshold": memory.confidence_threshold,
            "position_size_mult":   memory.position_size_mult,
            "signal_cooldown_mult": memory.signal_cooldown_mult,
            "long_bias":            memory.long_bias,
            "sessions_count":       memory.sessions_count,
            "avg_win_rate":         memory.avg_win_rate,
            "best_symbols":         memory.best_symbols,
            "worst_symbols":        memory.worst_symbols,
        }

    def get_all_memories(self) -> dict:
        """Zwraca pamięć wszystkich agentów (do wyświetlenia w UI)."""
        return {name: asdict(mem) for name, mem in self._memories.items()}

    def reset_agent(self, agent_name: str) -> None:
        """Resetuje pamięć agenta do domyślnych ustawień."""
        self._memories[agent_name] = AgentMemory(agent_name=agent_name)
        self._save_memories()
        log.info("🔄 Pamięć agenta {} zresetowana", agent_name)

    # ── Analiza agenta ────────────────────────────────────────────────────────

    def _analyze_agent(
        self,
        session_id: str,
        agent_name: str,
        stats: dict,
        trades: list[dict],
    ) -> AgentLesson:
        """Analizuje wyniki agenta i generuje lekcję z konkretnymi zmianami."""
        memory   = self._get_or_create_memory(agent_name)
        changes  = []
        win_rate = stats.get("win_rate", 0) / 100
        total_pnl = stats.get("total_pnl", 0)

        # ── Aktualizuj statystyki długoterminowe ──────────────────────────────
        memory.sessions_count += 1
        memory.total_trades   += stats.get("trades", 0)
        memory.total_wins     += stats.get("wins", 0)

        # Krocząca średnia win rate (ostatnie 5 sesji)
        alpha = 0.3  # współczynnik wygładzania
        memory.avg_win_rate = alpha * win_rate + (1 - alpha) * memory.avg_win_rate
        memory.avg_pnl      = alpha * total_pnl + (1 - alpha) * memory.avg_pnl

        # ── Analiza symboli ───────────────────────────────────────────────────
        symbol_pnl: dict[str, float] = {}
        for t in trades:
            sym = t.get("symbol", "")
            symbol_pnl[sym] = symbol_pnl.get(sym, 0) + (t.get("actual_pnl_usd") or 0)

        if symbol_pnl:
            best_sym  = max(symbol_pnl, key=symbol_pnl.get)
            worst_sym = min(symbol_pnl, key=symbol_pnl.get)

            # Aktualizuj listy najlepszych/najgorszych symboli
            if best_sym not in memory.best_symbols and symbol_pnl[best_sym] > 0:
                memory.best_symbols.append(best_sym)
                memory.best_symbols = memory.best_symbols[-5:]  # max 5

            if worst_sym not in memory.worst_symbols and symbol_pnl[worst_sym] < 0:
                memory.worst_symbols.append(worst_sym)
                memory.worst_symbols = memory.worst_symbols[-5:]  # max 5

        # ── Reguła 1: Zbyt niska win rate → podnieś próg pewności ────────────
        if win_rate < 0.40 and memory.sessions_count >= 1:
            old_thresh = memory.confidence_threshold
            increase   = min(0.05, (0.50 - win_rate) * 0.15)
            memory.confidence_threshold = min(0.85, old_thresh + increase)
            changes.append({
                "param":    "confidence_threshold",
                "old":      round(old_thresh, 3),
                "new":      round(memory.confidence_threshold, 3),
                "reason":   f"Win rate {win_rate:.0%} < 40% → wymagam wyższej pewności przed wejściem",
                "effect":   "Agent będzie otwierał mniej pozycji, ale bardziej pewnych",
            })

        elif win_rate > 0.65 and memory.confidence_threshold > 0.50:
            # Wysoka win rate → możemy poluzować próg
            old_thresh = memory.confidence_threshold
            memory.confidence_threshold = max(0.50, old_thresh - 0.02)
            changes.append({
                "param":  "confidence_threshold",
                "old":    round(old_thresh, 3),
                "new":    round(memory.confidence_threshold, 3),
                "reason": f"Win rate {win_rate:.0%} > 65% → mogę być odrobinę śmielszy",
                "effect": "Agent lekko zwiększy liczbę sygnałów",
            })

        # ── Reguła 2: Straty → zmniejsz wielkość pozycji ─────────────────────
        if total_pnl < -50:
            old_mult = memory.position_size_mult
            decrease = min(0.2, abs(total_pnl) / 500)
            memory.position_size_mult = max(0.3, old_mult - decrease)
            changes.append({
                "param":  "position_size_mult",
                "old":    round(old_mult, 3),
                "new":    round(memory.position_size_mult, 3),
                "reason": f"Strata ${total_pnl:.2f} → zmniejszam wielkość pozycji",
                "effect": "Agent będzie ryzykował mniejszą kwotą per transakcja",
            })

        elif total_pnl > 50 and memory.position_size_mult < 1.5:
            # Zyski → możemy delikatnie zwiększyć pozycje
            old_mult = memory.position_size_mult
            memory.position_size_mult = min(1.5, old_mult + 0.05)
            changes.append({
                "param":  "position_size_mult",
                "old":    round(old_mult, 3),
                "new":    round(memory.position_size_mult, 3),
                "reason": f"Zysk ${total_pnl:.2f} → nieznacznie zwiększam pozycje",
                "effect": "Agent będzie inwestował nieco więcej per sygnał",
            })

        # ── Reguła 3: Zbyt wiele przegranych LONG → zmniejsz long_bias ───────
        long_trades  = [t for t in trades if t.get("direction") == "LONG"]
        short_trades = [t for t in trades if t.get("direction") == "SHORT"]

        long_wins  = sum(1 for t in long_trades  if (t.get("actual_pnl_usd") or 0) > 0)
        short_wins = sum(1 for t in short_trades if (t.get("actual_pnl_usd") or 0) > 0)

        long_wr  = long_wins  / len(long_trades)  if long_trades  else 0.5
        short_wr = short_wins / len(short_trades) if short_trades else 0.5

        if long_trades and short_trades:
            if long_wr < short_wr - 0.15:
                old_bias = memory.long_bias
                memory.long_bias = max(0.25, memory.long_bias - 0.05)
                changes.append({
                    "param":  "long_bias",
                    "old":    round(old_bias, 3),
                    "new":    round(memory.long_bias, 3),
                    "reason": f"LONG WR {long_wr:.0%} vs SHORT WR {short_wr:.0%} → mniej pozycji LONG",
                    "effect": "Agent będzie częściej rozważał kierunek SHORT",
                })
            elif short_wr < long_wr - 0.15:
                old_bias = memory.long_bias
                memory.long_bias = min(0.75, memory.long_bias + 0.05)
                changes.append({
                    "param":  "long_bias",
                    "old":    round(old_bias, 3),
                    "new":    round(memory.long_bias, 3),
                    "reason": f"SHORT WR {short_wr:.0%} gorsza niż LONG WR {long_wr:.0%} → więcej LONG",
                    "effect": "Agent będzie preferował kierunek LONG",
                })

        # ── Reguła 4: Szybkie straty → dłużej obserwuj przed wejściem ────────
        quick_losses = [
            t for t in trades
            if (t.get("actual_pnl_usd") or 0) < -5
            and t.get("exit_time") and t.get("entry_time")
        ]

        if len(quick_losses) >= 2 and len(quick_losses) / max(len(trades), 1) > 0.3:
            old_cooldown = memory.signal_cooldown_mult
            memory.signal_cooldown_mult = min(2.0, old_cooldown + 0.15)
            changes.append({
                "param":  "signal_cooldown_mult",
                "old":    round(old_cooldown, 3),
                "new":    round(memory.signal_cooldown_mult, 3),
                "reason": f"{len(quick_losses)} szybkich strat ({len(quick_losses)/len(trades):.0%} transakcji) → wydłużam czas między sygnałami",
                "effect": "Agent będzie handlował rzadziej, dokładniej sprawdzał warunki",
            })

        # ── Reguła 5: Dobra seria → zmniejsz cooldown (odblokuj aktywność) ───
        if win_rate > 0.60 and memory.signal_cooldown_mult > 1.0:
            old_cooldown = memory.signal_cooldown_mult
            memory.signal_cooldown_mult = max(1.0, old_cooldown - 0.1)
            changes.append({
                "param":  "signal_cooldown_mult",
                "old":    round(old_cooldown, 3),
                "new":    round(memory.signal_cooldown_mult, 3),
                "reason": f"Dobra seria (WR {win_rate:.0%}) → skracam cooldown",
                "effect": "Agent będzie aktywniejszy po dobrej serii",
            })

        # ── Generuj słowne podsumowanie ───────────────────────────────────────
        summary = self._generate_summary(agent_name, win_rate, total_pnl, changes, memory)

        # ── Zapisz nowe parametry ─────────────────────────────────────────────
        new_params = {
            "confidence_threshold": round(memory.confidence_threshold, 3),
            "position_size_mult":   round(memory.position_size_mult, 3),
            "signal_cooldown_mult": round(memory.signal_cooldown_mult, 3),
            "long_bias":            round(memory.long_bias, 3),
        }

        lesson = AgentLesson(
            session_id   = session_id,
            timestamp    = datetime.now().isoformat(),
            agent_name   = agent_name,
            win_rate     = win_rate,
            total_pnl    = total_pnl,
            trades_count = len(trades),
            changes      = changes,
            summary      = summary,
            new_params   = new_params,
        )

        log.info("🎓 {} nauczył się {} rzeczy | WR={:.0%} PnL=${:.2f}",
                 agent_name, len(changes), win_rate, total_pnl)
        return lesson

    def _generate_summary(
        self,
        agent_name: str,
        win_rate: float,
        total_pnl: float,
        changes: list[dict],
        memory: AgentMemory,
    ) -> str:
        """Generuje czytelne podsumowanie w języku polskim."""
        lines = []

        # Ogólna ocena sesji
        if win_rate >= 0.60 and total_pnl > 0:
            lines.append(f"✅ Dobra sesja! Win rate {win_rate:.0%}, zarobiono ${total_pnl:+.2f}.")
        elif win_rate >= 0.50:
            lines.append(f"🟡 Przeciętna sesja. Win rate {win_rate:.0%}, PnL ${total_pnl:+.2f}.")
        else:
            lines.append(f"❌ Trudna sesja. Win rate tylko {win_rate:.0%}, strata ${total_pnl:.2f}.")

        # Co zmieniłem
        if changes:
            lines.append(f"📚 Nauczyłem się {len(changes)} rzeczy i zmieniłem swoje parametry:")
            for c in changes:
                lines.append(f"   • {c['reason']} ({c['param']}: {c['old']} → {c['new']})")
        else:
            lines.append("📚 Parametry bez zmian — wyniki w normie.")

        # Długoterminowy kontekst
        if memory.sessions_count > 1:
            lines.append(f"📊 Łącznie przeanalizowałem {memory.sessions_count} sesji, "
                        f"średni win rate: {memory.avg_win_rate:.0%}.")

        if memory.best_symbols:
            lines.append(f"💚 Najlepiej radzę sobie z: {', '.join(memory.best_symbols)}")
        if memory.worst_symbols:
            lines.append(f"🔴 Mam problem z: {', '.join(memory.worst_symbols)} — będę ostrożniejszy")

        return "\n".join(lines)

    # ── Pamięć (zapis/odczyt) ─────────────────────────────────────────────────

    def _get_or_create_memory(self, agent_name: str) -> AgentMemory:
        if agent_name not in self._memories:
            self._memories[agent_name] = AgentMemory(agent_name=agent_name)
        return self._memories[agent_name]

    def _load_memories(self) -> None:
        """Wczytaj pamięć z pliku JSON."""
        try:
            if MEMORY_FILE.exists():
                with open(MEMORY_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, mem_dict in data.items():
                    self._memories[name] = AgentMemory(**{
                        k: v for k, v in mem_dict.items()
                        if k in AgentMemory.__dataclass_fields__
                    })
                log.info("🧠 Wczytano pamięć {} agentów z {}", len(self._memories), MEMORY_FILE)
        except Exception as exc:
            log.warning("Nie można wczytać pamięci agentów: {}", exc)

    def _save_memories(self) -> None:
        """Zapisz pamięć do pliku JSON."""
        try:
            MEMORY_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {name: asdict(mem) for name, mem in self._memories.items()}
            with open(MEMORY_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            log.debug("💾 Pamięć agentów zapisana do {}", MEMORY_FILE)
        except Exception as exc:
            log.error("Błąd zapisu pamięci agentów: {}", exc)


# Singleton
_learning_engine: Optional[AgentLearningEngine] = None


def get_learning_engine() -> AgentLearningEngine:
    global _learning_engine
    if _learning_engine is None:
        _learning_engine = AgentLearningEngine()
    return _learning_engine
