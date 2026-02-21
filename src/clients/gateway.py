"""HTTP client for the API Core service."""

from __future__ import annotations

import httpx

from src.config import settings

CALLER_HEADERS = {"X-Caller-Service": "billing-service"}


class GatewayClient:
    """Client for fetching session and cost data from api-core."""

    def __init__(self, base_url: str | None = None):
        self.base_url = base_url or settings.gateway_url
        self.prefix = "/api/v1"

    async def list_sessions(self, team_id: str | None = None, status: str | None = None) -> list[dict]:
        params = {}
        if team_id:
            params["team_id"] = team_id
        if status:
            params["status"] = status
        async with httpx.AsyncClient(headers=CALLER_HEADERS) as client:
            resp = await client.get(f"{self.base_url}{self.prefix}/sessions", params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_session(self, session_id: str) -> dict:
        async with httpx.AsyncClient(headers=CALLER_HEADERS) as client:
            resp = await client.get(f"{self.base_url}{self.prefix}/sessions/{session_id}")
            resp.raise_for_status()
            return resp.json()

    async def get_cost_by_team(self) -> list[dict]:
        async with httpx.AsyncClient(headers=CALLER_HEADERS) as client:
            resp = await client.get(f"{self.base_url}{self.prefix}/analytics/cost-by-team")
            resp.raise_for_status()
            return resp.json()

    async def get_teams(self) -> list[dict]:
        async with httpx.AsyncClient(headers=CALLER_HEADERS) as client:
            resp = await client.get(f"{self.base_url}{self.prefix}/teams")
            resp.raise_for_status()
            return resp.json()

    async def get_session_stats(self) -> dict:
        async with httpx.AsyncClient(headers=CALLER_HEADERS) as client:
            resp = await client.get(f"{self.base_url}{self.prefix}/sessions/stats")
            resp.raise_for_status()
            return resp.json()
