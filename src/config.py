"""Billing service configuration."""

from __future__ import annotations

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    gateway_url: str = "http://api-core:8001"
    database_url: str = "sqlite+aiosqlite:///billing.db"

    # Default token pricing (per 1K tokens)
    input_token_price: float = 0.003
    output_token_price: float = 0.015
    cached_token_price: float = 0.00015

    api_prefix: str = "/api/v1"
    api_version: str = "1.0.0"

    model_config = {"env_prefix": "BILLING_"}


settings = Settings()
