"""Tests for the AgentBoard Billing Service."""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from src.database import Base, get_db
from src.main import app

# Use SQLite for tests
test_engine = create_async_engine("sqlite+aiosqlite:///", echo=False)
TestSession = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSession() as session:
        yield session


app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


MOCK_SESSIONS = [
    {
        "session_id": "sess_001",
        "team_id": "team_eng",
        "agent_name": "code-reviewer",
        "model": "gpt-4o",
        "status": "completed",
        "input_tokens": 5000,
        "output_tokens": 2000,
        "cached_tokens": 500,
        "total_cost": 0.045075,
        "started_at": "2025-01-15T10:00:00+00:00",
        "ended_at": "2025-01-15T10:05:00+00:00",
    },
    {
        "session_id": "sess_002",
        "team_id": "team_eng",
        "agent_name": "bug-fixer",
        "model": "gpt-4o",
        "status": "completed",
        "input_tokens": 3000,
        "output_tokens": 1000,
        "cached_tokens": 200,
        "total_cost": 0.02403,
        "started_at": "2025-01-15T14:00:00+00:00",
        "ended_at": "2025-01-15T14:03:00+00:00",
    },
]

MOCK_TEAMS = [
    {"id": "team_eng", "name": "Engineering", "plan": "enterprise", "monthly_budget": 5000.0},
]


class TestHealth:
    @pytest.mark.asyncio
    async def test_health(self, client):
        resp = await client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "billing-service"


class TestGenerateInvoice:
    @pytest.mark.asyncio
    @patch("src.routes.invoices.gateway")
    async def test_generate_invoice(self, mock_gw, client):
        mock_gw.list_sessions = AsyncMock(return_value=MOCK_SESSIONS)
        mock_gw.get_teams = AsyncMock(return_value=MOCK_TEAMS)

        resp = await client.post("/api/v1/invoices", json={
            "team_id": "team_eng",
            "period_start": "2025-01-01T00:00:00Z",
            "period_end": "2025-01-31T23:59:59Z",
            "tax_rate": 0.1,
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["team_id"] == "team_eng"
        assert data["team_name"] == "Engineering"
        assert data["total_sessions"] == 2
        assert data["status"] == "issued"
        assert data["total_input_tokens"] == 8000
        assert data["total_output_tokens"] == 3000
        assert data["subtotal"] > 0
        assert data["tax_amount"] > 0
        assert data["total_amount"] > data["subtotal"]
        assert len(data["line_items"]) == 2  # 2 agents

    @pytest.mark.asyncio
    @patch("src.routes.invoices.gateway")
    async def test_generate_invoice_no_sessions(self, mock_gw, client):
        mock_gw.list_sessions = AsyncMock(return_value=[])
        resp = await client.post("/api/v1/invoices", json={
            "team_id": "team_eng",
            "period_start": "2025-01-01T00:00:00Z",
            "period_end": "2025-01-31T23:59:59Z",
        })
        assert resp.status_code == 404


class TestListInvoices:
    @pytest.mark.asyncio
    @patch("src.routes.invoices.gateway")
    async def test_list_invoices(self, mock_gw, client):
        mock_gw.list_sessions = AsyncMock(return_value=MOCK_SESSIONS)
        mock_gw.get_teams = AsyncMock(return_value=MOCK_TEAMS)

        # Create an invoice first
        await client.post("/api/v1/invoices", json={
            "team_id": "team_eng",
            "period_start": "2025-01-01T00:00:00Z",
            "period_end": "2025-01-31T23:59:59Z",
        })

        resp = await client.get("/api/v1/invoices")
        assert resp.status_code == 200
        invoices = resp.json()
        assert len(invoices) == 1
        assert invoices[0]["team_id"] == "team_eng"

    @pytest.mark.asyncio
    @patch("src.routes.invoices.gateway")
    async def test_get_invoice_by_id(self, mock_gw, client):
        mock_gw.list_sessions = AsyncMock(return_value=MOCK_SESSIONS)
        mock_gw.get_teams = AsyncMock(return_value=MOCK_TEAMS)

        create_resp = await client.post("/api/v1/invoices", json={
            "team_id": "team_eng",
            "period_start": "2025-01-01T00:00:00Z",
            "period_end": "2025-01-31T23:59:59Z",
        })
        invoice_id = create_resp.json()["id"]

        resp = await client.get(f"/api/v1/invoices/{invoice_id}")
        assert resp.status_code == 200
        assert resp.json()["id"] == invoice_id

    @pytest.mark.asyncio
    async def test_get_invoice_not_found(self, client):
        resp = await client.get("/api/v1/invoices/inv_nonexistent")
        assert resp.status_code == 404


class TestUpdateInvoice:
    @pytest.mark.asyncio
    @patch("src.routes.invoices.gateway")
    async def test_mark_invoice_paid(self, mock_gw, client):
        mock_gw.list_sessions = AsyncMock(return_value=MOCK_SESSIONS)
        mock_gw.get_teams = AsyncMock(return_value=MOCK_TEAMS)

        create_resp = await client.post("/api/v1/invoices", json={
            "team_id": "team_eng",
            "period_start": "2025-01-01T00:00:00Z",
            "period_end": "2025-01-31T23:59:59Z",
        })
        invoice_id = create_resp.json()["id"]

        resp = await client.patch(f"/api/v1/invoices/{invoice_id}", params={"status": "paid"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"


class TestBillingSummary:
    @pytest.mark.asyncio
    @patch("src.routes.invoices.gateway")
    async def test_billing_summary(self, mock_gw, client):
        mock_gw.list_sessions = AsyncMock(return_value=MOCK_SESSIONS)
        mock_gw.get_teams = AsyncMock(return_value=MOCK_TEAMS)
        mock_gw.get_cost_by_team = AsyncMock(return_value=[
            {"team_id": "team_eng", "total_sessions": 100, "total_cost": 250.0},
        ])

        # Create an invoice
        await client.post("/api/v1/invoices", json={
            "team_id": "team_eng",
            "period_start": "2025-01-01T00:00:00Z",
            "period_end": "2025-01-31T23:59:59Z",
        })

        resp = await client.get("/api/v1/billing/summary")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_invoices"] == 1
        assert data["total_revenue"] > 0
        assert len(data["top_teams"]) == 1
        assert data["top_teams"][0]["team_id"] == "team_eng"
