"""
Główna aplikacja FastAPI.
Uruchamiana przez: uvicorn panel.api.app:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from core.logger import setup_logging, get_logger
from database.database import init_db
from panel.api.routes import router

log = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    await init_db()
    log.info("FastAPI backend uruchomiony")
    yield
    log.info("FastAPI backend zatrzymany")


app = FastAPI(
    title="IBKR Multi-Agent Trading System",
    version="1.0.0",
    description="Panel sterowania systemem automatycznego tradingu",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # W produkcji ogranicz do adresu panelu
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(router, prefix="/api")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "ibkr-trading-api"}
