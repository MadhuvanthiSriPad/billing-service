"""Invoice models for AgentBoard billing."""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import Column, String, Float, Integer, DateTime, Enum, ForeignKey, Text
from sqlalchemy.orm import relationship

from src.database import Base


class InvoiceStatus(str, enum.Enum):
    DRAFT = "draft"
    ISSUED = "issued"
    PAID = "paid"
    OVERDUE = "overdue"
    CANCELLED = "cancelled"


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(String, primary_key=True)
    team_id = Column(String, nullable=False, index=True)
    team_name = Column(String, nullable=False)
    period_start = Column(DateTime, nullable=False)
    period_end = Column(DateTime, nullable=False)
    total_sessions = Column(Integer, default=0)
    total_input_tokens = Column(Integer, default=0)
    total_output_tokens = Column(Integer, default=0)
    total_cached_tokens = Column(Integer, default=0)
    subtotal = Column(Float, default=0.0)
    tax_rate = Column(Float, default=0.0)
    tax_amount = Column(Float, default=0.0)
    total_amount = Column(Float, default=0.0)
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.DRAFT)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    issued_at = Column(DateTime, nullable=True)
    notes = Column(Text, nullable=True)

    line_items = relationship("InvoiceLineItem", back_populates="invoice", cascade="all, delete-orphan")


class InvoiceLineItem(Base):
    __tablename__ = "invoice_line_items"

    id = Column(Integer, primary_key=True, autoincrement=True)
    invoice_id = Column(String, ForeignKey("invoices.id"), nullable=False)
    description = Column(String, nullable=False)
    agent_name = Column(String, nullable=True)
    model = Column(String, nullable=True)
    session_count = Column(Integer, default=0)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cached_tokens = Column(Integer, default=0)
    amount = Column(Float, default=0.0)

    invoice = relationship("Invoice", back_populates="line_items")
