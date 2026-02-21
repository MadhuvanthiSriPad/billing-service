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
