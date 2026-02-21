"""Billing service configuration."""

from __future__ import annotations

import os


class Settings:
    gateway_url: str = os.getenv("GATEWAY_URL", "http://api-core:8001")
    database_url: str = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///billing.db")

    # Default token pricing (mirrors api-core)
    input_token_price: float = 0.003   # per 1K tokens
    output_token_price: float = 0.015  # per 1K tokens
    cached_token_price: float = 0.00015

    api_prefix: str = "/api/v1"


settings = Settings()
