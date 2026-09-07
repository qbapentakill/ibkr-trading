"""
CoachAgent – "Szef" systemu tradingowego.

Działa jak trener piłkarski:
- Po każdym zamkniętym tradzie przyznaje lub odejmuje punkty
- Po każdej sesji testowej generuje raport z ocenami
- Dostosowuje pewność i agresywność agentów na podstawie historii
- Prowadzi ranking agentów
- Wysyła "wiadomości" do agentów z instrukcjami

System punktacji:
  +10  za trade z zyskiem > 2%
  +5   za trade z zyskiem 0.5-2%
  +2   za trade z małym zyskiem < 0.5%
  -2   za małą stratę < 0.5%
  -5   za stratę 0.5-2%
  -10  za dużą stratę > 2%
  +15  bonus za serię 3 wygranych z rzędu
  -15  kara za serię 3 przegranych z rzędu
  +20  bonus za najlepszy agent w sesji
  -10  kara za najgorszy agent w sesji
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Optional

from core.logger import get_logger

log = get_logger(__name__)

COACH_FILE = Path("data/coach_scores.json")


# ─────────────────────────────────────────────────────────────────────────────
# Modele danych
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class TradeReview:
    """Ocena pojedynczego trade'u przez Szefa."""
    trade_id:    str
    agent_name:  str
    symbol:      str
    direction:   str
    pnl_usd:     float
    pnl_pct:     float
    points:      int
    reason:      str
    timestamp:   str
    session_id:  Optional[str] = None


@dataclass
class AgentScore:
    """Wynik agenta — akumulowany przez wszystkie sesje i trades."""
    agent_name:       str
    total_points:     int   = 0
    total_trades:     int   = 0
    winning_trades:   int   = 0
    losing_trades:    int   = 0
    total_pnl:        float = 0.0
    best_trade_pnl:   float = 0.0
    worst_trade_pnl:  float = 0.0
    current_streak:   int   = 0   # + = seria wygranych, - = seria przegranych
    sessions_count:   int   = 0
    level:            str   = "Nowicjusz"
    reviews:          list  = field(default_factory=list)  # ostatnie 50 recenzji

    @property
    def win_rate(self) -> float:
        return self.winning_trades / max(self.total_trades, 1) * 100

    @property
    def avg_pnl(self) -> float:
        return self.total_pnl / max(self.total_trades, 1)


# Poziomy agentów na podstawie punktów
LEVELS = [
    (0,    "🥚 Nowicjusz"),
    (50,   "🌱 Stażysta"),
    (150,  "📊 Analityk"),
    (300,  "💼 Trader"),
    (500,  "⭐ Senior Trader"),
    (800,  "🏆 Ekspert"),
    (1200, "💎 Master"),
    (2000, "🚀 Legenda"),
]


def _get_level(points: int) -> str:
    level = LEVELS[0][1]
    for threshold, name in LEVELS:
        if points >= threshold:
            level = name
    return level


# ─────────────────────────────────────────────────────────────────────────────
# CoachAgent
# ─────────────────────────────────────────────────────────────────────────────

class CoachAgent:
    """
    Bot Szef — ocenia agentów i przyznaje/odejmuje punkty.

    Użycie:
        coach = CoachAgent()
        coach.review_trade(agent_name, pnl_usd, pnl_pct, ...)
        coach.review_session(session_report)
        scores = coach.get_ranking()
    """

    def __init__(self) -> None:
        self._scores: dict[str, AgentScore] = {}
        self._load()
        log.info("🎓 CoachAgent uruchomiony | Śledzę {} agentów", len(self._scores))

    # ── Publiczne API ─────────────────────────────────────────────────────────

    def review_trade(
        self,
        agent_name:  str,
        symbol:      str,
        direction:   str,
        pnl_usd:     float,
        pnl_pct:     float,
        trade_id:    str = "",
        session_id:  Optional[str] = None,
    ) -> TradeReview:
        """Ocenia pojedynczy trade i aktualizuje punkty agenta."""
        score  = self._get_or_create(agent_name)
        points = self._calculate_points(pnl_pct, agent_level=score.level)
        reason = self._generate_reason(agent_name, pnl_usd, pnl_pct, points, level=score.level)

        # Aktualizuj statystyki
        score.total_trades += 1
        score.total_pnl    += pnl_usd
        score.total_points += points

        if pnl_usd > 0:
            score.winning_trades += 1
            score.current_streak  = max(0, score.current_streak) + 1
            score.best_trade_pnl  = max(score.best_trade_pnl, pnl_usd)
        else:
            score.losing_trades  += 1
            score.current_streak  = min(0, score.current_streak) - 1
            score.worst_trade_pnl = min(score.worst_trade_pnl, pnl_usd)

        # Bonus/kara za serię
        streak_bonus = 0
        if score.current_streak >= 3:
            streak_bonus = 15
            points += streak_bonus
            score.total_points += streak_bonus
            reason += f" 🔥 Seria {score.current_streak} wygranych! +{streak_bonus}pkt"
        elif score.current_streak <= -3:
            streak_bonus = -15
            points += streak_bonus
            score.total_points += streak_bonus
            reason += f" ❄️ Seria {abs(score.current_streak)} przegranych! {streak_bonus}pkt"

        # Aktualizuj poziom
        score.level = _get_level(score.total_points)

        review = TradeReview(
            trade_id   = trade_id or f"T_{datetime.utcnow().timestamp():.0f}",
            agent_name = agent_name,
            symbol     = symbol,
            direction  = direction,
            pnl_usd    = round(pnl_usd, 2),
            pnl_pct    = round(pnl_pct, 2),
            points     = points,
            reason     = reason,
            timestamp  = datetime.now().strftime("%H:%M:%S"),
            session_id = session_id,
        )

        # Zapisz recenzję (max 50)
        score.reviews.insert(0, asdict(review))
        score.reviews = score.reviews[:50]

        self._save()

        log.info("🎓 Coach | {} | {} {} ${:.2f} | {:+d}pkt | {}",
                 agent_name, direction, symbol, pnl_usd, points, score.level)

        return review

    def review_session(self, session_report: dict) -> dict:
        """Ocenia całą sesję testową — przyznaje bonusy najlepszym, kary najgorszym."""
        agent_stats = session_report.get("agent_stats", {})
        trades      = session_report.get("trades", [])
        session_id  = session_report.get("session_id", "")
        reviews     = {}

        if not agent_stats:
            return reviews

        # Najpierw oceń każdy trade
        for t in trades:
            if t.get("status") not in ("CLOSED", "EXPIRED"):
                continue
            if t.get("actual_pnl_usd") is None:
                continue
            pnl_usd = t.get("actual_pnl_usd", 0)
            pnl_pct = t.get("actual_pnl_pct", 0)
            agent   = t.get("agent") or t.get("agent_name", "Unknown")
            if not agent or agent == "Unknown":
                continue
            self.review_trade(
                agent_name = agent,
                symbol     = t.get("symbol", ""),
                direction  = t.get("direction", ""),
                pnl_usd    = pnl_usd,
                pnl_pct    = pnl_pct or 0,
                trade_id   = t.get("trade_id", ""),
                session_id = session_id,
            )

        # Bonus dla najlepszego agenta sesji
        if agent_stats:
            best_agent  = max(agent_stats.items(), key=lambda x: x[1].get("total_pnl", 0))
            worst_agent = min(agent_stats.items(), key=lambda x: x[1].get("total_pnl", 0))

            if best_agent[1].get("total_pnl", 0) > 0:
                score = self._get_or_create(best_agent[0])
                score.total_points += 20
                score.sessions_count += 1
                score.level = _get_level(score.total_points)
                log.info("🏆 Coach | Najlepszy agent sesji: {} +20pkt", best_agent[0])

            if worst_agent[1].get("total_pnl", 0) < 0:
                score = self._get_or_create(worst_agent[0])
                score.total_points -= 10
                score.sessions_count += 1
                score.level = _get_level(score.total_points)
                log.info("📉 Coach | Najgorszy agent sesji: {} -10pkt", worst_agent[0])

            # Zwiększ licznik sesji dla pozostałych
            for agent_name in agent_stats:
                if agent_name not in (best_agent[0], worst_agent[0]):
                    score = self._get_or_create(agent_name)
                    score.sessions_count += 1

        self._save()

        # Generuj podsumowanie sesji
        summary = {
            "session_id": session_id,
            "ranking":    self.get_ranking(),
            "messages":   self._generate_session_messages(agent_stats),
        }
        return summary

    def get_ranking(self) -> list[dict]:
        """Zwraca ranking wszystkich agentów posortowany po punktach."""
        ranking = []
        for i, (name, score) in enumerate(
            sorted(self._scores.items(), key=lambda x: x[1].total_points, reverse=True), 1
        ):
            ranking.append({
                "rank":           i,
                "agent_name":     name,
                "level":          score.level,
                "total_points":   score.total_points,
                "total_trades":   score.total_trades,
                "win_rate":       round(score.win_rate, 1),
                "total_pnl":      round(score.total_pnl, 2),
                "avg_pnl":        round(score.avg_pnl, 2),
                "best_trade":     round(score.best_trade_pnl, 2),
                "worst_trade":    round(score.worst_trade_pnl, 2),
                "current_streak": score.current_streak,
                "sessions":       score.sessions_count,
                "recent_reviews": score.reviews[:5],
            })
        return ranking

    def get_agent_score(self, agent_name: str) -> dict:
        """Zwraca szczegółowy wynik konkretnego agenta."""
        score = self._get_or_create(agent_name)
        return {
            "agent_name":    agent_name,
            "level":         score.level,
            "total_points":  score.total_points,
            "total_trades":  score.total_trades,
            "win_rate":      round(score.win_rate, 1),
            "total_pnl":     round(score.total_pnl, 2),
            "best_trade":    round(score.best_trade_pnl, 2),
            "worst_trade":   round(score.worst_trade_pnl, 2),
            "streak":        score.current_streak,
            "sessions":      score.sessions_count,
            "next_level":    self._next_level_info(score.total_points),
            "reviews":       score.reviews[:20],
        }

    def reset_agent(self, agent_name: str) -> None:
        """Resetuje wynik agenta."""
        self._scores[agent_name] = AgentScore(agent_name=agent_name)
        self._save()
        log.info("🔄 Coach | Reset wyników agenta {}", agent_name)

    # ── Wewnętrzne ────────────────────────────────────────────────────────────

    def _calculate_points(self, pnl_pct: float) -> int:
        """Przelicza % PnL na punkty z uwzględnieniem poziomu agenta."""
        # Mnożnik trudności per poziom — im wyższy poziom, tym trudniej
        level_multipliers = {
            "🥚 Nowicjusz":       1.0,
            "🌱 Stażysta":        0.9,
            "📊 Analityk":        0.8,
            "💼 Trader":          0.7,
            "⭐ Senior Trader":   0.6,
            "🏆 Ekspert":         0.5,
            "💎 Master":          0.4,
            "🚀 Legenda":         0.3,
        }

        # Pobierz aktualny mnożnik dla agenta
        mult = level_multipliers.get(agent_level, 1.0)

        # Bazowe punkty
        if pnl_pct > 2.0:   base = +10
        elif pnl_pct > 0.5: base = +5
        elif pnl_pct > 0.0: base = +2
        elif pnl_pct > -0.5: base = -2
        elif pnl_pct > -2.0: base = -5
        else:               base = -10

        # Straty zawsze pełne — nagrody skalowane przez mnożnik
        if base > 0:
            return max(1, round(base * mult))
        return base  # kary bez zniżki

    def _generate_reason(self, agent: str, pnl_usd: float, pnl_pct: float, points: int, level: str = "") -> str:
        """Generuje komentarz Szefa do trade'u uwzględniający poziom agenta."""
        import random

        # Komunikaty motywujące uwzględniające poziom
        high_level = level in ("🏆 Ekspert", "💎 Master", "🚀 Legenda")
        mid_level  = level in ("💼 Trader", "⭐ Senior Trader")

        if points >= 10:
            msgs = [
                f"Doskonały trade! {pnl_pct:+.2f}% — tak trzymać!",
                f"Świetna robota, {agent}! Zysk ${pnl_usd:.2f}.",
                f"To jest właśnie to czego szukamy! {pnl_pct:+.2f}%",
            ]
            if high_level:
                msgs += [f"Imponujące na poziomie {level}! Na tym poziomie każdy punkt kosztuje — zasłużone!"]
        elif points >= 5:
            msgs = [
                f"Dobry trade, {pnl_pct:+.2f}% — solidnie.",
                f"Niezły wynik. Zysk ${pnl_usd:.2f}.",
                f"Dobra analiza, kontynuuj.",
            ]
            if high_level:
                msgs += [f"Na poziomie {level} oczekuję więcej niż {pnl_pct:+.2f}% — dasz radę lepiej."]
        elif points >= 2:
            msgs = [
                f"Mały zysk ${pnl_usd:.2f} — mogło być lepiej.",
                f"Wynik {pnl_pct:+.2f}% — nie ma co świętować ale ok.",
            ]
            if mid_level or high_level:
                msgs += [f"Przy poziomie {level} to za mało. Szukaj mocniejszych setupów."]
        elif points >= -2:
            msgs = [
                f"Mała strata ${pnl_usd:.2f} — analizuj wejście.",
                f"Zbyt wczesne wejście? Strata {pnl_pct:.2f}%.",
            ]
        elif points >= -5:
            msgs = [
                f"Zła decyzja! Strata ${pnl_usd:.2f}. Sprawdź sygnały.",
                f"Ten trade nie powinien być otwarty. {pnl_pct:.2f}%.",
            ]
            if high_level:
                msgs += [f"Hańba dla poziomu {level}! Strata {pnl_pct:.2f}% jest nieakceptowalna."]
        else:
            msgs = [
                f"NIEAKCEPTOWALNE! Strata ${pnl_usd:.2f}! Musisz poprawić stop-lossy!",
                f"Katastrofa. {pnl_pct:.2f}% straty. Wracaj do podstaw.",
            ]
            if high_level:
                msgs += [f"Agent na poziomie {level} NIE powinien tak tracić! {pnl_pct:.2f}% to skandal!"]

        return random.choice(msgs)

    def get_recent_activity(self, hours: int = 12) -> list[dict]:
        """Zwraca aktywność punktową z ostatnich X godzin."""
        import datetime as dt
        cutoff = dt.datetime.now() - dt.timedelta(hours=hours)

        activity = []
        for agent_name, score in self._scores.items():
            for review in score.reviews:
                # reviews to dicts (asdict(TradeReview))
                ts_str = review.get("timestamp", "") if isinstance(review, dict) else ""
                pts    = review.get("points", 0)    if isinstance(review, dict) else 0
                reason = review.get("reason", "")   if isinstance(review, dict) else ""

                if not ts_str:
                    continue
                try:
                    ts = dt.datetime.fromisoformat(ts_str)
                except Exception:
                    continue

                if ts >= cutoff:
                    activity.append({
                        "agent":     agent_name,
                        "points":    pts,
                        "reason":    reason,
                        "timestamp": ts.strftime("%H:%M:%S"),
                        "type":      "gain" if pts > 0 else "loss",
                    })

        activity.sort(key=lambda x: x["timestamp"], reverse=True)
        return activity

    def _generate_session_messages(self, agent_stats: dict) -> list[str]:
        """Generuje wiadomości dla agentów po sesji."""
        messages = []
        for agent, stats in agent_stats.items():
            wr  = stats.get("win_rate", 0)
            pnl = stats.get("total_pnl", 0)
            if wr >= 70 and pnl > 0:
                messages.append(f"✅ {agent}: Świetna sesja! WR={wr:.0f}% PnL=${pnl:.2f}")
            elif wr >= 50:
                messages.append(f"🟡 {agent}: Przeciętna sesja. WR={wr:.0f}% — pracuj nad selekcją wejść.")
            else:
                messages.append(f"❌ {agent}: Słaba sesja. WR={wr:.0f}% — zrewiduj strategię!")
        return messages

    def _next_level_info(self, points: int) -> dict:
        """Zwraca info o następnym poziomie."""
        for threshold, name in LEVELS:
            if points < threshold:
                return {"name": name, "points_needed": threshold - points, "threshold": threshold}
        return {"name": "MAX LEVEL", "points_needed": 0, "threshold": points}

    def _get_or_create(self, agent_name: str) -> AgentScore:
        if agent_name not in self._scores:
            self._scores[agent_name] = AgentScore(agent_name=agent_name)
        return self._scores[agent_name]

    def _load(self) -> None:
        try:
            if COACH_FILE.exists():
                with open(COACH_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for name, d in data.items():
                    self._scores[name] = AgentScore(**{
                        k: v for k, v in d.items()
                        if k in AgentScore.__dataclass_fields__
                    })
                log.info("📂 Coach: wczytano wyniki {} agentów", len(self._scores))
        except Exception as exc:
            log.warning("Coach: błąd wczytywania wyników: {}", exc)

    def _save(self) -> None:
        try:
            COACH_FILE.parent.mkdir(parents=True, exist_ok=True)
            data = {name: asdict(score) for name, score in self._scores.items()}
            with open(COACH_FILE, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as exc:
            log.error("Coach: błąd zapisu: {}", exc)


# Singleton
_coach: Optional[CoachAgent] = None


def get_coach() -> CoachAgent:
    global _coach
    if _coach is None:
        _coach = CoachAgent()
    return _coach
