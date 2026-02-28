"""Pydantic schemas for billing service."""

from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel


class InvoiceLineItemResponse(BaseModel):
    id: int
    description: str
    agent_name: str | None = None
    model: str | None = None
    session_count: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cached_tokens: int = 0
    amount: float = 0.0

    model_config = {"from_attributes": True}


class InvoiceResponse(BaseModel):
    id: str
    team_id: str
    team_name: str
    period_start: datetime
    period_end: datetime
    total_sessions: int
    total_input_tokens: int
    total_output_tokens: int
    total_cached_tokens: int
    subtotal: float
    tax_rate: float
    tax_amount: float
    total_amount: float
    status: str
    created_at: datetime
    issued_at: datetime | None = None
    notes: str | None = None
    line_items: list[InvoiceLineItemResponse] = []

    model_config = {"from_attributes": True}


class GenerateInvoiceRequest(BaseModel):
    team_id: str
    period_start: datetime
    period_end: datetime
    tax_rate: float = 0.0
    notes: str | None = None


class UpdateInvoiceStatus(BaseModel):
    status: str


VALID_TRANSITIONS: dict[str, set[str]] = {
    "draft": {"issued", "cancelled"},
    "issued": {"paid", "overdue", "cancelled"},
    "overdue": {"paid", "cancelled"},
    "paid": set(),
    "cancelled": set(),
}


class TeamCostSummary(BaseModel):
    team_id: str
    team_name: str
    total_sessions: int
    total_cost: float
    budget: float
    budget_used_pct: float


class BillingSummary(BaseModel):
    total_revenue: float
    total_invoices: int
    invoices_by_status: dict[str, int]
    top_teams: list[TeamCostSummary]


# ---------------------------------------------------------------------------
# Contract-change schemas (mirrors api-core ImpactSetResponse / detail)
# ---------------------------------------------------------------------------


class ImpactSetItem(BaseModel):
    """A single impact-set entry returned by api-core."""

    id: int
    caller_service: str
    route_template: str
    method: str | None = None  # newly added nullable field
    calls_last_7d: int = 0
    confidence: str = "high"
    notes: str | None = None


class RemediationJobItem(BaseModel):
    job_id: int
    target_repo: str
    status: str
    devin_run_id: str | None = None
    devin_session_url: str | None = None
    pr_url: str | None = None
    created_at: str | None = None
    updated_at: str | None = None
    bundle_hash: str | None = None
    error_summary: str | None = None
    is_dry_run: bool = False


class ContractChangeDetail(BaseModel):
    """Full detail of a single contract change from api-core."""

    id: int
    base_ref: str | None = None
    head_ref: str | None = None
    created_at: str | None = None
    is_breaking: bool = False
    severity: str = "low"
    summary_json: str = ""
    changed_routes_json: str = ""
    changed_fields_json: str | None = None
    affected_services: int = 0
    affected_routes: int = 0
    total_calls_last_7d: int = 0
    impacted_services: list[str] = []
    changed_routes: list[str] = []
    impact_sets: list[ImpactSetItem] = []
    remediation_jobs: list[RemediationJobItem] = []


class ContractChangeSummary(BaseModel):
    """Abbreviated contract change returned by the list endpoint."""

    id: int
    base_ref: str | None = None
    head_ref: str | None = None
    created_at: str | None = None
    is_breaking: bool = False
    severity: str = "low"
    summary_json: str = ""
    changed_routes_json: str = ""
    changed_fields_json: str | None = None
    affected_services: int = 0
    impacted_services: list[str] = []
    target_repos: list[str] = []
    source_repo: str = "api-core"
    active_jobs: int = 0
    pr_count: int = 0
    remediation_status: str = "pending"
    estimated_hours_saved: float = 0.0
    incident_risk_score: str = "low"
