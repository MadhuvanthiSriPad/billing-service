"""Invoice routes for the billing service."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.database import get_db
from src.models.invoice import Invoice, InvoiceLineItem, InvoiceStatus
from src.clients.gateway import GatewayClient
from src.schemas import (
    InvoiceResponse,
    GenerateInvoiceRequest,
    TeamCostSummary,
    BillingSummary,
)
from src.config import settings

router = APIRouter(tags=["invoices"])
gateway = GatewayClient()


@router.post("/invoices", response_model=InvoiceResponse, status_code=201)
async def generate_invoice(request: GenerateInvoiceRequest, db: AsyncSession = Depends(get_db)):
    """Generate an invoice for a team based on api-core data."""
    # Fetch sessions from api-core for this team
    try:
        sessions = await gateway.list_sessions(team_id=request.team_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Gateway API error: {e}")

    # Filter sessions within the billing period
    period_sessions = []
    for s in sessions:
        started = datetime.fromisoformat(s["started_at"])
        if request.period_start <= started <= request.period_end:
            period_sessions.append(s)

    if not period_sessions:
        raise HTTPException(status_code=404, detail="No sessions found for this team in the given period")

    # Fetch team info
    try:
        teams = await gateway.get_teams()
        team_info = next((t for t in teams if t["id"] == request.team_id), None)
    except Exception:
        team_info = None
    team_name = team_info["name"] if team_info else request.team_id

    # Group by agent+model for line items
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for s in period_sessions:
        key = (s.get("agent_name", "unknown"), s.get("model", "unknown"))
        groups[key].append(s)

    invoice_id = f"inv_{uuid.uuid4().hex[:12]}"
    line_items = []
    subtotal = 0.0

    for (agent_name, model), group_sessions in groups.items():
        input_tok = sum(s.get("input_tokens", 0) for s in group_sessions)
        output_tok = sum(s.get("output_tokens", 0) for s in group_sessions)
        cached_tok = sum(s.get("cached_tokens", 0) for s in group_sessions)
        amount = (
            (input_tok / 1000) * settings.input_token_price
            + (output_tok / 1000) * settings.output_token_price
            + (cached_tok / 1000) * settings.cached_token_price
        )
        amount = round(amount, 6)
        subtotal += amount

        line_items.append(InvoiceLineItem(
            invoice_id=invoice_id,
            description=f"{agent_name} on {model}",
            agent_name=agent_name,
            model=model,
            session_count=len(group_sessions),
            input_tokens=input_tok,
            output_tokens=output_tok,
            cached_tokens=cached_tok,
            amount=amount,
        ))

    tax_amount = round(subtotal * request.tax_rate, 2)
    total_amount = round(subtotal + tax_amount, 2)

    invoice = Invoice(
        id=invoice_id,
        team_id=request.team_id,
        team_name=team_name,
        period_start=request.period_start,
        period_end=request.period_end,
        total_sessions=len(period_sessions),
        total_input_tokens=sum(s.get("input_tokens", 0) for s in period_sessions),
        total_output_tokens=sum(s.get("output_tokens", 0) for s in period_sessions),
        total_cached_tokens=sum(s.get("cached_tokens", 0) for s in period_sessions),
        subtotal=round(subtotal, 6),
        tax_rate=request.tax_rate,
        tax_amount=tax_amount,
        total_amount=total_amount,
        status=InvoiceStatus.ISSUED,
        issued_at=datetime.now(timezone.utc),
        notes=request.notes,
    )
    invoice.line_items = line_items

    db.add(invoice)
    await db.commit()
    await db.refresh(invoice)

    # Re-query with eager loading
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.line_items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one()
    return invoice


@router.get("/invoices", response_model=list[InvoiceResponse])
async def list_invoices(team_id: str | None = None, status: str | None = None, db: AsyncSession = Depends(get_db)):
    """List all invoices, optionally filtered by team or status."""
    query = select(Invoice).options(selectinload(Invoice.line_items))
    if team_id:
        query = query.where(Invoice.team_id == team_id)
    if status:
        query = query.where(Invoice.status == status)
    query = query.order_by(Invoice.created_at.desc())
    result = await db.execute(query)
    return result.scalars().all()


@router.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def get_invoice(invoice_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single invoice by ID."""
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.line_items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return invoice


@router.patch("/invoices/{invoice_id}", response_model=InvoiceResponse)
async def update_invoice_status(invoice_id: str, status: str, db: AsyncSession = Depends(get_db)):
    """Update invoice status (e.g., mark as paid)."""
    result = await db.execute(
        select(Invoice).options(selectinload(Invoice.line_items)).where(Invoice.id == invoice_id)
    )
    invoice = result.scalar_one_or_none()
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    invoice.status = InvoiceStatus(status)
    await db.commit()
    await db.refresh(invoice)
    return invoice


@router.get("/billing/summary", response_model=BillingSummary)
async def billing_summary(db: AsyncSession = Depends(get_db)):
    """Get overall billing summary."""
    # Total revenue and counts
    total_result = await db.execute(select(func.sum(Invoice.total_amount), func.count(Invoice.id)))
    row = total_result.one()
    total_revenue = row[0] or 0.0
    total_invoices = row[1] or 0

    # By status
    status_result = await db.execute(
        select(Invoice.status, func.count(Invoice.id)).group_by(Invoice.status)
    )
    invoices_by_status = {str(r[0].value) if hasattr(r[0], 'value') else str(r[0]): r[1] for r in status_result.all()}

    # Top teams by cost from gateway
    top_teams = []
    try:
        cost_data = await gateway.get_cost_by_team()
        teams = await gateway.get_teams()
        team_map = {t["id"]: t for t in teams}
        for entry in cost_data[:5]:
            tid = entry.get("team_id", "")
            team = team_map.get(tid, {})
            top_teams.append(TeamCostSummary(
                team_id=tid,
                team_name=team.get("name", tid),
                total_sessions=entry.get("total_sessions", 0),
                total_cost=entry.get("total_cost", 0.0),
                budget=team.get("monthly_budget", 0.0),
                budget_used_pct=round(
                    (entry.get("total_cost", 0) / team["monthly_budget"] * 100)
                    if team.get("monthly_budget") else 0, 1
                ),
            ))
    except Exception:
        pass

    return BillingSummary(
        total_revenue=total_revenue,
        total_invoices=total_invoices,
        invoices_by_status=invoices_by_status,
        top_teams=top_teams,
    )
