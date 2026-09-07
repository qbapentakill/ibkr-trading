"""
Message Bus – asynchroniczne przesyłanie wiadomości między komponentami.

Implementacja dwuwarstwowa:
1. asyncio.Queue (zawsze dostępny, używany domyślnie)
2. Redis Streams (opcjonalny, gdy REDIS_URL jest ustawiony)

Kanały:
  signals   – TradeSignal od agentów → Orchestrator
  orders    – OrderRequest od Orchestratora → IBKR
  alerts    – Alerty → AlertingService
  audit     – Zdarzenia auditowe → DB
"""
from __future__ import annotations

import asyncio
import json
from typing import Any, Callable, Coroutine, Optional

from core.logger import get_logger

log = get_logger(__name__)

Handler = Callable[[dict[str, Any]], Coroutine[Any, Any, None]]


class MessageBus:
    """
    Lekki wewnętrzny message bus oparty o asyncio.Queue.
    Obsługuje pub/sub z wieloma subskrybentami per kanał.
    """

    def __init__(self) -> None:
        self._channels: dict[str, asyncio.Queue] = {}
        self._subscribers: dict[str, list[Handler]] = {}
        self._dispatch_tasks: list[asyncio.Task] = []

    def _ensure_channel(self, channel: str) -> None:
        if channel not in self._channels:
            self._channels[channel] = asyncio.Queue(maxsize=1000)
            self._subscribers[channel] = []

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        """Publikuje wiadomość na kanale."""
        self._ensure_channel(channel)
        # Uruchom dispatch loop jeśli jeszcze nie działa
        await self._ensure_dispatch_loop(channel)
        try:
            self._channels[channel].put_nowait(message)
        except asyncio.QueueFull:
            log.warning("Kanał '{}' pełny – wiadomość odrzucona", channel)

    def subscribe(self, channel: str, handler: Handler) -> None:
        """Rejestruje handler (coroutine) dla danego kanału."""
        self._ensure_channel(channel)
        self._subscribers[channel].append(handler)
        log.debug("Subskrybent dodany do kanału '{}'", channel)

    async def start(self) -> None:
        """Uruchamia pętle dispatching dla wszystkich kanałów."""
        for channel in list(self._channels.keys()):
            await self._ensure_dispatch_loop(channel)
        log.info("MessageBus uruchomiony ({} kanałów)", len(self._channels))

    async def _ensure_dispatch_loop(self, channel: str) -> None:
        """Uruchamia dispatch loop dla kanału jeśli jeszcze nie działa."""
        running = [t for t in self._dispatch_tasks if t.get_name() == f"bus_dispatch_{channel}" and not t.done()]
        if not running:
            task = asyncio.create_task(
                self._dispatch_loop(channel),
                name=f"bus_dispatch_{channel}",
            )
            self._dispatch_tasks.append(task)

    async def stop(self) -> None:
        for task in self._dispatch_tasks:
            task.cancel()
        self._dispatch_tasks.clear()
        log.info("MessageBus zatrzymany")

    async def _dispatch_loop(self, channel: str) -> None:
        queue = self._channels[channel]
        while True:
            try:
                message = await queue.get()
                handlers = self._subscribers.get(channel, [])
                for handler in handlers:
                    try:
                        await handler(message)
                    except Exception as exc:
                        log.error(
                            "Błąd handlera na kanale '{}': {}", channel, exc
                        )
                queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as exc:
                log.error("Błąd pętli dispatching '{}': {}", channel, exc)

    async def drain(self, channel: str) -> None:
        """Opróżnia kolejkę kanału (używane przy emergency stop)."""
        q = self._channels.get(channel)
        if q:
            while not q.empty():
                try:
                    q.get_nowait()
                    q.task_done()
                except asyncio.QueueEmpty:
                    break


# ─────────────────────────────────────────────────────────────────────────────
# Opcjonalny Redis backend (używany jeśli redis dostępny)
# ─────────────────────────────────────────────────────────────────────────────

class RedisMessageBus(MessageBus):
    """
    Rozszerzenie MessageBus o Redis Streams.
    Używane gdy chcemy persystencję wiadomości lub wiele procesów.
    Fallback do in-memory jeśli Redis niedostępny.
    """

    def __init__(self, redis_url: str) -> None:
        super().__init__()
        self._redis_url = redis_url
        self._redis = None
        self._redis_available = False

    async def start(self) -> None:
        try:
            import aioredis
            self._redis = await aioredis.from_url(
                self._redis_url, encoding="utf-8", decode_responses=True
            )
            await self._redis.ping()
            self._redis_available = True
            log.info("Redis połączony: {}", self._redis_url)
        except Exception as exc:
            log.warning("Redis niedostępny ({}), używam in-memory bus", exc)
            self._redis_available = False

        await super().start()

    async def publish(self, channel: str, message: dict[str, Any]) -> None:
        # Zawsze publikuj lokalnie
        await super().publish(channel, message)
        # Opcjonalnie na Redis
        if self._redis_available and self._redis:
            try:
                await self._redis.xadd(
                    f"trading:{channel}",
                    {"data": json.dumps(message, default=str)},
                    maxlen=10000,
                )
            except Exception as exc:
                log.debug("Redis publish error: {}", exc)

    async def stop(self) -> None:
        await super().stop()
        if self._redis:
            await self._redis.close()
