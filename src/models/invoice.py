"""Invoice models for the Billing Service."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Optional
import uuid


class InvoiceStatus(str, Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


@dataclass
class InvoiceLineItem:
    description: str
    amount: float
    payment_transaction_id: str


@dataclass
class Invoice:
    invoice_id: str
    customer_name: str
    line_items: list[InvoiceLineItem] = field(default_factory=list)
    status: InvoiceStatus = InvoiceStatus.DRAFT
    issued_at: Optional[datetime] = None
    total_amount: float = 0.0

    @classmethod
    def from_payment(cls, payment_data: dict) -> Invoice:
        """Create an invoice from a Payments API response."""
        invoice_id = f"inv_{uuid.uuid4().hex[:10]}"
        amount = payment_data["amount"]["value"]
        customer_name = f"{payment_data['first_name']} {payment_data['last_name']}".strip()
        payment_reference = payment_data["payment_reference"]

        line_item = InvoiceLineItem(
            description=f"Payment {payment_reference}",
            amount=amount,
            payment_transaction_id=payment_reference,
        )

        return cls(
            invoice_id=invoice_id,
            customer_name=customer_name,
            line_items=[line_item],
            total_amount=amount,
            issued_at=datetime.now(timezone.utc),
            status=InvoiceStatus.ISSUED,
        )

    def add_payment(self, payment_data: dict) -> None:
        """Add another payment as a line item to this invoice."""
        line_item = InvoiceLineItem(
            description=f"Payment {payment_data['payment_reference']}",
            amount=payment_data["amount"]["value"],
            payment_transaction_id=payment_data["payment_reference"],
        )
        self.line_items.append(line_item)
        self.total_amount += payment_data["amount"]["value"]

    def to_dict(self) -> dict:
        return {
            "invoice_id": self.invoice_id,
            "customer_name": self.customer_name,
            "total_amount": self.total_amount,
            "status": self.status.value,
            "line_items": [
                {
                    "description": li.description,
                    "amount": li.amount,
                    "payment_transaction_id": li.payment_transaction_id,
                }
                for li in self.line_items
            ],
        }
