"""Inicjalizuje nowych agentów w coach_scores.json"""
import json
from pathlib import Path

f = Path("data/coach_scores.json")
data = json.loads(f.read_text(encoding="utf-8")) if f.exists() else {}

new_agents = [
    "OptionsFlow", "GapTrader", "MomentumSurfer", "VIXTrader",
    "DivergenceHunter", "ScalpKing", "WhaleTracker",
    "EarningsWatcher", "MacroAnalyst", "CorrelationGuard",
    "HeatmapAnalyst", "EconomicCalendar",
]

added = 0
for name in new_agents:
    if name not in data:
        data[name] = {
            "agent_name":    name,
            "total_points":  0,
            "total_trades":  0,
            "winning_trades":0,
            "losing_trades": 0,
            "total_pnl":     0.0,
            "best_trade_pnl":0.0,
            "worst_trade_pnl":0.0,
            "current_streak":0,
            "sessions_count":0,
            "level":         "🥚 Nowicjusz",
            "reviews":       [],
        }
        added += 1

f.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
print(f"Dodano {added} nowych agentów. Łącznie: {len(data)}")
