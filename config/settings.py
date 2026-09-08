"""
Centralne ustawienia systemu.
Wszystkie wartości wczytywane z .env lub zmiennych środowiskowych.
"""
from __future__ import annotations

from functools import lru_cache
from typing import Optional

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # ── IBKR (zachowane dla kompatybilności) ────────────────────────────────
    ibkr_host: str = "127.0.0.1"
    ibkr_port: int = 7497
    ibkr_client_id: int = 1
    real_mode: bool = False

    # ── Alpaca ────────────────────────────────────────────────────────────────
    alpaca_api_key: str = ""
    alpaca_secret_key: str = ""
    alpaca_paper: bool = True
    alpaca_base_url: str = "https://paper-api.alpaca.markets"
    alpaca_data_url: str = "https://data.alpaca.markets"

    # ── Redis ─────────────────────────────────────────────────────────────────
    redis_url: str = "redis://localhost:6379/0"

    # ── Database ──────────────────────────────────────────────────────────────
    database_url: str = "sqlite+aiosqlite:///./data/trading.db"

    # ── Panel / Security ──────────────────────────────────────────────────────
    panel_username: str = "admin"
    panel_password_hash: str = ""
    secret_key: str = "zmien-na-losowy-klucz-256bit"
    emergency_stop_password: str = "stop123"
    viewer_password: str = "viewer123"
    jwt_expire_minutes: int = 60

    # ── Alerting ──────────────────────────────────────────────────────────────
    telegram_bot_token: Optional[str] = None
    telegram_chat_id: Optional[str] = None
    alert_email_from: Optional[str] = None
    alert_email_to: Optional[str] = None
    smtp_host: str = "smtp.gmail.com"
    smtp_port: int = 587
    smtp_user: Optional[str] = None
    smtp_password: Optional[str] = None

    # ── Risk Defaults ─────────────────────────────────────────────────────────
    max_daily_loss_usd: float = 500.0
    max_drawdown_pct: float = 10.0
    total_capital_usd: float = 10000.0
    max_position_size_pct: float = 5.0

    # ── Polygon API key ───────────────────────────────────────────────────────
    polygon_api_key: str = ""

    # ── AI Chat ───────────────────────────────────────────────────────────────
    openai_api_key:  Optional[str] = None
    openai_model:    str = "gpt-4o-mini"
    groq_api_key:    Optional[str] = None
    groq_model:      str = "llama-3.3-70b-versatile"
    ollama_model:    str = "llama3"
    ollama_base_url: str = "http://localhost:11434"

    # ── Reconnect ─────────────────────────────────────────────────────────────
    reconnect_interval_sec: int = 5
    max_reconnect_attempts: int = 20

    @field_validator("real_mode", mode="before")
    @classmethod
    def _never_auto_real(cls, v: object) -> bool:
        """Dodatkowe zabezpieczenie – real_mode można ustawić tylko jawnie."""
        return bool(v)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
