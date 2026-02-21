"""Billing Service — generates invoices and tracks costs for AgentBoard."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.database import init_db
from src.routes import invoices
from src.config import settings


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(
    title="Billing Service",
    description="Invoice generation and cost tracking for AgentBoard",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(invoices.router, prefix=settings.api_prefix)


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "billing-service", "version": "1.0.0"}
