"""HTTP client for the API Core service."""

from __future__ import annotations

import httpx

from src.config import settings


def _headers() -> dict[str, str]:
    headers = {"X-Caller-Service": "billing-service"}
    if settings.api_core_api_key:
        headers["X-API-Key"] = settings.api_core_api_key
    return headers


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
        async with httpx.AsyncClient(headers=_headers(), timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}{self.prefix}/sessions", params=params)
            resp.raise_for_status()
            return resp.json()

    async def get_session(self, session_id: str, max_cost_usd: float = 0.0) -> dict:
        """Fetch a single session by ID.

        Args:
            session_id: The session identifier.
            max_cost_usd: Required cost cap for the session (added in latest
                api-core contract).  Defaults to ``0.0`` (no cap).
        """
        async with httpx.AsyncClient(headers=_headers(), timeout=30.0) as client:
            resp = await client.get(
                f"{self.base_url}{self.prefix}/sessions/{session_id}",
                params={"max_cost_usd": max_cost_usd},
            )
            resp.raise_for_status()
            return resp.json()

    async def get_cost_by_team(self) -> list[dict]:
        async with httpx.AsyncClient(headers=_headers(), timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}{self.prefix}/analytics/cost-by-team")
            resp.raise_for_status()
            return resp.json()

    async def get_teams(self) -> list[dict]:
        async with httpx.AsyncClient(headers=_headers(), timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}{self.prefix}/teams")
            resp.raise_for_status()
            return resp.json()

    async def create_session(
        self,
        team_id: str,
        agent_name: str,
        priority: str,
        max_cost_usd: float,
        model: str = "devin-default",
        prompt: str | None = None,
        tags: str | None = None,
    ) -> dict:
        payload: dict = {
            "team_id": team_id,
            "agent_name": agent_name,
            "priority": priority,
            "max_cost_usd": max_cost_usd,
            "model": model,
        }
        if prompt is not None:
            payload["prompt"] = prompt
        if tags is not None:
            payload["tags"] = tags
        async with httpx.AsyncClient(headers=_headers()) as client:
            resp = await client.post(f"{self.base_url}{self.prefix}/sessions", json=payload)
            resp.raise_for_status()
            return resp.json()

    async def get_session_stats(self) -> dict:
        async with httpx.AsyncClient(headers=_headers(), timeout=30.0) as client:
            resp = await client.get(f"{self.base_url}{self.prefix}/sessions/stats")
            resp.raise_for_status()
            return resp.json()
