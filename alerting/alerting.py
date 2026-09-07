"""
AlertingService – wysyła powiadomienia przez Telegram i e-mail.

Eventy triggerujące alert:
- Emergency Stop aktywowany / odblokowany
- Przekroczenie dziennego limitu straty
- Przekroczenie max drawdown
- Błąd krytyczny agenta
- Zlecenie odrzucone przez RiskManager
- Wypełnione zlecenie (opcjonalnie)
- NEWS o HIGH impact
- Słaba wydajność agenta (sugestia wyłączenia)
"""
from __future__ import annotations

import asyncio
from datetime import datetime
from typing import Optional

import aiosmtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

from config.settings import get_settings
from core.logger import get_logger
from core.models import Alert, AlertLevel
from database.database import get_session
from database.models import DBAlert

log = get_settings
log = get_logger(__name__)
settings = get_settings()

# Cooldown: nie wysyłaj tego samego alertu częściej niż raz na N sekund
_cooldown_cache: dict[str, datetime] = {}
COOLDOWN_SEC = 300   # 5 minut


class AlertingService:
    """Asynchroniczny serwis alertów (Telegram + Email)."""

    def __init__(self) -> None:
        self._telegram_available = bool(settings.telegram_bot_token and settings.telegram_chat_id)
        self._email_available    = bool(settings.smtp_user and settings.smtp_password)
        log.info(
            "AlertingService: Telegram={} Email={}",
            self._telegram_available,
            self._email_available,
        )

    async def send(self, alert: Alert) -> None:
        """Wysyła alert przez wszystkie dostępne kanały."""
        # Cooldown check
        key = f"{alert.level}:{alert.title}"
        last = _cooldown_cache.get(key)
        if last and (datetime.utcnow() - last).total_seconds() < COOLDOWN_SEC:
            if alert.level not in (AlertLevel.EMERGENCY, AlertLevel.CRITICAL):
                return   # EMERGENCY / CRITICAL zawsze wysyłane

        _cooldown_cache[key] = datetime.utcnow()

        # Zapisz do DB
        await self._persist(alert)

        # Wyślij asynchronicznie
        tasks = []
        if self._telegram_available:
            tasks.append(self._send_telegram(alert))
        if self._email_available and alert.level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY):
            tasks.append(self._send_email(alert))

        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            for r in results:
                if isinstance(r, Exception):
                    log.error("Błąd wysyłania alertu: {}", r)

        log.info("🔔 Alert [{}] {} – {}", alert.level.value, alert.title, alert.message[:100])

    # ──────────────────────────────────────────────────────────────────────────
    # Telegram
    # ──────────────────────────────────────────────────────────────────────────

    async def _send_telegram(self, alert: Alert) -> None:
        icon_map = {
            AlertLevel.INFO:      "ℹ️",
            AlertLevel.WARNING:   "⚠️",
            AlertLevel.CRITICAL:  "🚨",
            AlertLevel.EMERGENCY: "🆘",
        }
        icon = icon_map.get(alert.level, "📢")
        ts   = alert.timestamp.strftime("%H:%M:%S UTC")

        text = (
            f"{icon} *{alert.level.value}* | {ts}\n"
            f"*{self._escape_md(alert.title)}*\n"
            f"{self._escape_md(alert.message)}\n"
            f"_Źródło: {alert.source}_"
        )

        try:
            import httpx
            url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(url, json={
                    "chat_id":    settings.telegram_chat_id,
                    "text":       text,
                    "parse_mode": "Markdown",
                })
        except Exception as exc:
            log.error("Telegram send error: {}", exc)

    # ──────────────────────────────────────────────────────────────────────────
    # E-mail
    # ──────────────────────────────────────────────────────────────────────────

    async def _send_email(self, alert: Alert) -> None:
        if not settings.alert_email_to:
            return
        try:
            msg = MIMEMultipart("alternative")
            msg["Subject"] = f"[TRADING {alert.level.value}] {alert.title}"
            msg["From"]    = settings.alert_email_from or settings.smtp_user
            msg["To"]      = settings.alert_email_to

            html = f"""
            <html><body style="font-family:sans-serif;background:#0e1117;color:#e0e0e0;padding:20px">
            <h2 style="color:{'#f85149' if alert.level in (AlertLevel.CRITICAL, AlertLevel.EMERGENCY) else '#e3b341'}">
                [{alert.level.value}] {alert.title}
            </h2>
            <p>{alert.message}</p>
            <hr style="border-color:#30363d"/>
            <small>Źródło: {alert.source} | {alert.timestamp.strftime('%Y-%m-%d %H:%M:%S UTC')}</small>
            </body></html>
            """
            msg.attach(MIMEText(html, "html"))

            await aiosmtplib.send(
                msg,
                hostname=settings.smtp_host,
                port=settings.smtp_port,
                username=settings.smtp_user,
                password=settings.smtp_password,
                use_tls=False,
                start_tls=True,
            )
        except Exception as exc:
            log.error("Email send error: {}", exc)

    # ──────────────────────────────────────────────────────────────────────────

    async def _persist(self, alert: Alert) -> None:
        try:
            async with get_session() as session:
                session.add(DBAlert(
                    level=alert.level.value,
                    title=alert.title,
                    message=alert.message,
                    source=alert.source,
                    sent=bool(self._telegram_available or self._email_available),
                    timestamp=alert.timestamp,
                ))
        except Exception as exc:
            log.error("Błąd zapisu alertu do DB: {}", exc)

    @staticmethod
    def _escape_md(text: str) -> str:
        """Escape Markdown special chars dla Telegram."""
        for ch in r"_*[]()~`>#+-=|{}.!":
            text = text.replace(ch, f"\\{ch}")
        return text

    # ──────────────────────────────────────────────────────────────────────────
    # Listener message bus
    # ──────────────────────────────────────────────────────────────────────────

    async def handle_bus_alert(self, message: dict) -> None:
        """Handler wywoływany przez MessageBus (kanał 'alerts')."""
        try:
            from core.models import AlertLevel
            alert = Alert(
                level=AlertLevel(message.get("level", "INFO")),
                title=message.get("title", "Alert"),
                message=message.get("message", ""),
                source=message.get("source", "system"),
            )
            await self.send(alert)
        except Exception as exc:
            log.error("Błąd handle_bus_alert: {}", exc)
