"""Tests for the billing service."""

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


@pytest_asyncio.fixture(scope="session", autouse=True)
async def dispose_test_engine():
    yield
    await test_engine.dispose()


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
        "priority": "high",
        "usage": {"input_tokens": 5000, "output_tokens": 2000, "cache_read_tokens": 500},
        "billing": {"total_usd": 0.045075},
        "started_at": "2025-01-15T10:00:00+00:00",
        "ended_at": "2025-01-15T10:05:00+00:00",
        "duration_seconds": 300.0,
        "error_message": None,
        "tags": None,
    },
    {
        "session_id": "sess_002",
        "team_id": "team_eng",
        "agent_name": "bug-fixer",
        "model": "gpt-4o",
        "status": "completed",
        "priority": "medium",
        "usage": {"input_tokens": 3000, "output_tokens": 1000, "cache_read_tokens": 200},
        "billing": {"total_usd": 0.02403},
        "started_at": "2025-01-15T14:00:00+00:00",
        "ended_at": "2025-01-15T14:03:00+00:00",
        "duration_seconds": 180.0,
        "error_message": None,
        "tags": None,
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
        assert data["total_input_tokens"] == 8000  # 5000 + 3000
        assert data["total_output_tokens"] == 3000  # 2000 + 1000
        assert data["subtotal"] > 0
        assert data["tax_amount"] > 0
        assert data["total_amount"] > data["subtotal"]
        assert len(data["line_items"]) == 2  # 2 agents

    @pytest.mark.asyncio
    @patch("src.routes.invoices.gateway")
    async def test_generate_invoice_no_sessions(self, mock_gw, client):
        mock_gw.list_sessions = AsyncMock(return_value=[])
        mock_gw.get_teams = AsyncMock(return_value=[])
        resp = await client.post("/api/v1/invoices", json={
            "team_id": "team_eng",
            "period_start": "2025-01-01T00:00:00Z",
            "period_end": "2025-01-31T23:59:59Z",
        })
        assert resp.status_code == 201
        data = resp.json()
        assert data["total_sessions"] == 0
        assert data["total_amount"] == 0


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

        resp = await client.patch(f"/api/v1/invoices/{invoice_id}", json={"status": "paid"})
        assert resp.status_code == 200
        assert resp.json()["status"] == "paid"


class TestCreateSession:
    @pytest.mark.asyncio
    @patch("src.clients.gateway.httpx.AsyncClient")
    async def test_create_session_sends_max_cost_usd(self, mock_client_cls):
        """Verify that create_session includes max_cost_usd in the POST body."""
        from unittest.mock import MagicMock
        from src.clients.gateway import GatewayClient

        expected_response = {
            "session_id": "sess_new",
            "team_id": "team_eng",
            "agent_name": "code-reviewer",
            "model": "gpt-4o",
            "status": "running",
            "priority": "high",
            "usage": {"input_tokens": 0, "output_tokens": 0, "cached_tokens": 0},
            "billing": {"total": 0.0},
            "started_at": "2025-01-15T10:00:00+00:00",
            "ended_at": None,
            "duration_seconds": 0.0,
            "error_message": None,
            "tags": None,
        }

        mock_response = MagicMock()
        mock_response.json.return_value = expected_response
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_instance

        gw = GatewayClient(base_url="http://test-api")
        result = await gw.create_session(
            team_id="team_eng",
            agent_name="code-reviewer",
            priority="high",
            max_cost_usd=10.0,
            model="gpt-4o",
        )

        mock_instance.post.assert_called_once()
        call_args = mock_instance.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["max_cost_usd"] == 10.0
        assert payload["team_id"] == "team_eng"
        assert payload["agent_name"] == "code-reviewer"
        assert payload["priority"] == "high"
        assert payload["model"] == "gpt-4o"
        assert result["session_id"] == "sess_new"

    @pytest.mark.asyncio
    @patch("src.clients.gateway.httpx.AsyncClient")
    async def test_create_session_optional_fields(self, mock_client_cls):
        """Verify that optional fields (prompt, tags) are included when provided."""
        from unittest.mock import MagicMock
        from src.clients.gateway import GatewayClient

        mock_response = MagicMock()
        mock_response.json.return_value = {"session_id": "sess_new"}
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_instance

        gw = GatewayClient(base_url="http://test-api")
        await gw.create_session(
            team_id="team_eng",
            agent_name="code-reviewer",
            priority="high",
            max_cost_usd=25.5,
            prompt="Fix the bug",
            tags="urgent",
        )

        call_args = mock_instance.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert payload["max_cost_usd"] == 25.5
        assert payload["prompt"] == "Fix the bug"
        assert payload["tags"] == "urgent"

    @pytest.mark.asyncio
    @patch("src.clients.gateway.httpx.AsyncClient")
    async def test_create_session_omits_none_optional_fields(self, mock_client_cls):
        """Verify that prompt and tags are omitted from payload when not provided."""
        from unittest.mock import MagicMock
        from src.clients.gateway import GatewayClient

        mock_response = MagicMock()
        mock_response.json.return_value = {"session_id": "sess_new"}
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.post = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_instance

        gw = GatewayClient(base_url="http://test-api")
        await gw.create_session(
            team_id="team_eng",
            agent_name="code-reviewer",
            priority="high",
            max_cost_usd=5.0,
        )

        call_args = mock_instance.post.call_args
        payload = call_args.kwargs.get("json") or call_args[1].get("json")
        assert "prompt" not in payload
        assert "tags" not in payload
        assert payload["max_cost_usd"] == 5.0


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


MOCK_CONTRACT_CHANGE_DETAIL = {
    "id": 42,
    "base_ref": "abc123",
    "head_ref": "def456",
    "created_at": "2025-06-01T12:00:00+00:00",
    "is_breaking": False,
    "severity": "low",
    "summary_json": '{"info": "non-breaking"}',
    "changed_routes_json": '["GET /api/v1/contracts/changes/{change_id}"]',
    "changed_fields_json": None,
    "affected_services": 1,
    "affected_routes": 1,
    "total_calls_last_7d": 15,
    "impacted_services": ["billing-service"],
    "changed_routes": ["GET /api/v1/contracts/changes/{change_id}"],
    "impact_sets": [
        {
            "id": 1,
            "caller_service": "billing-service",
            "route_template": "/api/v1/contracts/changes/{change_id}",
            "method": "GET",
            "calls_last_7d": 15,
            "confidence": "high",
            "notes": None,
        },
        {
            "id": 2,
            "caller_service": "dashboard-service",
            "route_template": "/api/v1/contracts/changes/{change_id}",
            "method": None,
            "calls_last_7d": 5,
            "confidence": "medium",
            "notes": "inferred from logs",
        },
    ],
    "remediation_jobs": [],
}

MOCK_CONTRACT_CHANGES_LIST = [
    {
        "id": 42,
        "base_ref": "abc123",
        "head_ref": "def456",
        "created_at": "2025-06-01T12:00:00+00:00",
        "is_breaking": False,
        "severity": "low",
        "summary_json": '{"info": "non-breaking"}',
        "changed_routes_json": '["GET /api/v1/contracts/changes/{change_id}"]',
        "changed_fields_json": None,
        "affected_services": 1,
        "impacted_services": ["billing-service"],
        "target_repos": ["billing-service"],
        "source_repo": "api-core",
        "active_jobs": 0,
        "pr_count": 0,
        "remediation_status": "pending",
        "estimated_hours_saved": 0.0,
        "incident_risk_score": "low",
    },
]


class TestContractChangeClient:
    """Tests for the contract-change gateway client methods."""

    @pytest.mark.asyncio
    @patch("src.clients.gateway.httpx.AsyncClient")
    async def test_get_contract_change_returns_detail_with_method(self, mock_client_cls):
        """Verify get_contract_change parses the response including the new method field."""
        from unittest.mock import MagicMock
        from src.clients.gateway import GatewayClient

        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_CONTRACT_CHANGE_DETAIL
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_instance

        gw = GatewayClient(base_url="http://test-api")
        result = await gw.get_contract_change(change_id=42)

        mock_instance.get.assert_called_once()
        call_args = mock_instance.get.call_args
        assert "/contracts/changes/42" in call_args[0][0]

        # Validate full response structure
        assert result["id"] == 42
        assert result["is_breaking"] is False
        assert len(result["impact_sets"]) == 2

        # The new `method` field must be present
        assert result["impact_sets"][0]["method"] == "GET"
        assert result["impact_sets"][1]["method"] is None

    @pytest.mark.asyncio
    @patch("src.clients.gateway.httpx.AsyncClient")
    async def test_get_contract_change_handles_no_impact_sets(self, mock_client_cls):
        """Verify get_contract_change works when impact_sets is empty."""
        from unittest.mock import MagicMock
        from src.clients.gateway import GatewayClient

        detail = {**MOCK_CONTRACT_CHANGE_DETAIL, "impact_sets": [], "remediation_jobs": []}
        mock_response = MagicMock()
        mock_response.json.return_value = detail
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_instance

        gw = GatewayClient(base_url="http://test-api")
        result = await gw.get_contract_change(change_id=42)
        assert result["impact_sets"] == []

    @pytest.mark.asyncio
    @patch("src.clients.gateway.httpx.AsyncClient")
    async def test_list_contract_changes(self, mock_client_cls):
        """Verify list_contract_changes sends limit param and returns list."""
        from unittest.mock import MagicMock
        from src.clients.gateway import GatewayClient

        mock_response = MagicMock()
        mock_response.json.return_value = MOCK_CONTRACT_CHANGES_LIST
        mock_response.raise_for_status = MagicMock()

        mock_instance = AsyncMock()
        mock_instance.get = AsyncMock(return_value=mock_response)
        mock_instance.__aenter__ = AsyncMock(return_value=mock_instance)
        mock_instance.__aexit__ = AsyncMock(return_value=False)
        mock_client_cls.return_value = mock_instance

        gw = GatewayClient(base_url="http://test-api")
        result = await gw.list_contract_changes(limit=10)

        mock_instance.get.assert_called_once()
        call_args = mock_instance.get.call_args
        assert "/contracts/changes" in call_args[0][0] or "/contracts/changes" in str(call_args)
        params = call_args.kwargs.get("params") or call_args[1].get("params", {})
        assert params["limit"] == 10
        assert len(result) == 1
        assert result[0]["id"] == 42


class TestImpactSetSchema:
    """Verify the ImpactSetItem schema properly handles the new method field."""

    def test_impact_set_with_method(self):
        from src.schemas import ImpactSetItem

        item = ImpactSetItem(
            id=1,
            caller_service="billing-service",
            route_template="/api/v1/contracts/changes/{change_id}",
            method="GET",
            calls_last_7d=15,
            confidence="high",
        )
        assert item.method == "GET"

    def test_impact_set_method_nullable(self):
        from src.schemas import ImpactSetItem

        item = ImpactSetItem(
            id=2,
            caller_service="dashboard-service",
            route_template="/api/v1/contracts/changes/{change_id}",
            method=None,
            calls_last_7d=5,
            confidence="medium",
        )
        assert item.method is None

    def test_impact_set_method_default_none(self):
        from src.schemas import ImpactSetItem

        item = ImpactSetItem(
            id=3,
            caller_service="some-service",
            route_template="/api/v1/sessions",
            calls_last_7d=0,
            confidence="low",
        )
        assert item.method is None

    def test_contract_change_detail_schema(self):
        from src.schemas import ContractChangeDetail

        detail = ContractChangeDetail(**MOCK_CONTRACT_CHANGE_DETAIL)
        assert detail.id == 42
        assert len(detail.impact_sets) == 2
        assert detail.impact_sets[0].method == "GET"
        assert detail.impact_sets[1].method is None
