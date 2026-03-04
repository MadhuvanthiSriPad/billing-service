"""Billing service configuration."""

from __future__ import annotations

try:
    from pydantic_settings import BaseSettings

    _USES_PYDANTIC_SETTINGS = True
except ModuleNotFoundError:
    # Compatibility fallback for environments where only pydantic is installed.
    # pydantic v2 exposes v1 settings under pydantic.v1; v1 exposes BaseSettings directly.
    try:
        from pydantic.v1 import BaseSettings  # type: ignore[attr-defined]
    except ImportError:
        from pydantic import BaseSettings  # type: ignore[no-redef]

    _USES_PYDANTIC_SETTINGS = False


class Settings(BaseSettings):
    service_name: str = "billing-service"
    gateway_url: str = "http://api-core:8001"
    database_url: str = "sqlite+aiosqlite:///billing.db"
    api_core_api_key: str = ""

    # Default token pricing (per 1K tokens)
    input_token_price: float = 0.003
    output_token_price: float = 0.015
    cached_token_price: float = 0.00015

    api_prefix: str = "/api/v1"
    api_version: str = "1.0.0"

    if _USES_PYDANTIC_SETTINGS:
        model_config = {"env_prefix": "BILLING_"}
    else:
        class Config:
            env_prefix = "BILLING_"


settings = Settings()
