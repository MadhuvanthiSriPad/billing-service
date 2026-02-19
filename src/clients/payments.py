"""HTTP client for the Payments API used by Billing Service."""

from __future__ import annotations

import httpx

PAYMENTS_API_URL = "http://payments-api:8001"


class PaymentsClient:
    """Client for fetching payment data from the Payments API."""

    def __init__(self, base_url: str = PAYMENTS_API_URL):
        self.base_url = base_url
        self.headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    def get_payment(self, payment_id: str) -> dict:
        """Retrieve payment details for invoice generation."""
        response = httpx.get(
            f"{self.base_url}/payments/{payment_id}",
            headers=self.headers,
        )
        response.raise_for_status()
        data = response.json()

        return {
            "payment_reference": data["payment_reference"],
            "amount": data["amount"],
            "first_name": data["first_name"],
            "last_name": data["last_name"],
            "status": data["status"],
            "created_at": data["created_at"],
        }

    def list_completed_payments(self) -> list[dict]:
        """Fetch all completed payments for billing reconciliation."""
        response = httpx.get(
            f"{self.base_url}/payments",
            params={"status": "completed"},
            headers=self.headers,
        )
        response.raise_for_status()
        payments = response.json()

        return [
            {
                "payment_reference": p["payment_reference"],
                "amount": p["amount"],
                "first_name": p["first_name"],
                "last_name": p["last_name"],
            }
            for p in payments
        ]
