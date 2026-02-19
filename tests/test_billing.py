"""Tests for the Billing Service."""

from unittest.mock import patch

from fastapi.testclient import TestClient

from src.main import app

client = TestClient(app)


def _mock_payment(txn_id="txn_bill_001", amount=120.00, name="Alice Johnson"):
    return {
        "transaction_id": txn_id,
        "amount": amount,
        "customer_name": name,
        "status": "completed",
        "created_at": "2025-01-15T10:00:00Z",
    }


class TestHealthCheck:
    def test_health(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["service"] == "billing-service"


class TestCreateInvoice:
    @patch("src.clients.payments.PaymentsClient.get_payment")
    def test_create_invoice_from_payment(self, mock_get):
        mock_get.return_value = _mock_payment()
        resp = client.post("/invoices", json={"payment_id": "txn_bill_001"})
        assert resp.status_code == 201
        data = resp.json()
        assert data["customer_name"] == "Alice Johnson"
        assert data["total_amount"] == 120.00
        assert data["status"] == "issued"
        assert len(data["line_items"]) == 1
        assert data["line_items"][0]["amount"] == 120.00
        assert data["line_items"][0]["payment_transaction_id"] == "txn_bill_001"


class TestReconciliation:
    @patch("src.clients.payments.PaymentsClient.list_completed_payments")
    def test_reconciliation_summary(self, mock_list):
        mock_list.return_value = [
            {"transaction_id": "txn_001", "amount": 100.00, "customer_name": "Alice"},
            {"transaction_id": "txn_002", "amount": 200.00, "customer_name": "Bob"},
            {"transaction_id": "txn_003", "amount": 150.00, "customer_name": "Alice"},
        ]
        resp = client.get("/reconciliation")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_revenue"] == 450.00
        assert data["invoice_count"] == 3
        assert set(data["customers"]) == {"Alice", "Bob"}
