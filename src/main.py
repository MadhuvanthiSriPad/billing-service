"""Billing Service — generates invoices from payment records."""

from __future__ import annotations

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

from src.clients.payments import PaymentsClient
from src.models.invoice import Invoice, InvoiceStatus

app = FastAPI(title="Billing Service", version="1.0.0")
payments_client = PaymentsClient()

# In-memory invoice storage
invoices_db: dict[str, Invoice] = {}


class CreateInvoiceRequest(BaseModel):
    payment_id: str


class InvoiceResponse(BaseModel):
    invoice_id: str
    customer_name: str
    total_amount: float
    status: str
    line_items: list[dict]


class ReconciliationResponse(BaseModel):
    total_revenue: float
    invoice_count: int
    customers: list[str]


@app.get("/health")
def health_check():
    return {"status": "healthy", "service": "billing-service", "version": "1.0.0"}


@app.post("/invoices", response_model=InvoiceResponse, status_code=201)
def create_invoice(request: CreateInvoiceRequest):
    """Create an invoice from a payment record."""
    try:
        payment = payments_client.get_payment(request.payment_id)
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Payments API error: {e}")

    invoice = Invoice.from_payment(payment)
    invoices_db[invoice.invoice_id] = invoice

    return InvoiceResponse(**invoice.to_dict())


@app.get("/invoices/{invoice_id}", response_model=InvoiceResponse)
def get_invoice(invoice_id: str):
    """Retrieve an invoice by ID."""
    invoice = invoices_db.get(invoice_id)
    if not invoice:
        raise HTTPException(status_code=404, detail=f"Invoice {invoice_id} not found")
    return InvoiceResponse(**invoice.to_dict())


@app.get("/invoices", response_model=list[InvoiceResponse])
def list_invoices():
    """List all invoices."""
    return [InvoiceResponse(**inv.to_dict()) for inv in invoices_db.values()]


@app.get("/reconciliation", response_model=ReconciliationResponse)
def get_reconciliation():
    """Get billing reconciliation summary from completed payments."""
    try:
        completed_payments = payments_client.list_completed_payments()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Payments API error: {e}")

    total_revenue = sum(p["amount"] for p in completed_payments)
    customers = list({p["customer_name"] for p in completed_payments})

    return ReconciliationResponse(
        total_revenue=total_revenue,
        invoice_count=len(completed_payments),
        customers=customers,
    )
