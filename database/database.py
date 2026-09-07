"""
Asynchroniczna baza danych (SQLAlchemy + aiosqlite).
"""
from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from config.settings import get_settings
from database.models import Base

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker | None = None


async def init_db() -> None:
    """Tworzy tabele (jeśli nie istnieją) i inicjalizuje silnik."""
    global _engine, _session_factory
    settings = get_settings()

    _engine = create_async_engine(
        settings.database_url,
        echo=False,
        future=True,
        connect_args={"check_same_thread": False},
    )

    _session_factory = async_sessionmaker(
        bind=_engine,
        expire_on_commit=False,
        class_=AsyncSession,
    )

    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Seed domyślnych limitów ryzyka jeśli tabela pusta
    async with get_session() as session:
        from sqlalchemy import select
        from database.models import DBRiskLimits
        result = await session.execute(select(DBRiskLimits).limit(1))
        if result.scalars().first() is None:
            s = get_settings()
            session.add(DBRiskLimits(
                max_daily_loss_usd=s.max_daily_loss_usd,
                max_drawdown_pct=s.max_drawdown_pct,
                total_capital_usd=s.total_capital_usd,
                max_position_size_pct=s.max_position_size_pct,
            ))
            await session.commit()


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Context manager zwracający sesję bazodanową."""
    if _session_factory is None:
        raise RuntimeError("Baza danych nie zainicjalizowana. Wywołaj init_db() najpierw.")
    async with _session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_engine() -> AsyncEngine:
    if _engine is None:
        raise RuntimeError("Baza danych nie zainicjalizowana.")
    return _engine
