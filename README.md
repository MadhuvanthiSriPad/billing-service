# Billing Service

`billing-service` turns `api-core` session data into invoices and billing summaries. It is the accounting side of the demo and keeps its own invoice database.

## What It Handles

- Generate invoices for a team and billing period
- Store invoice line items and status
- Return billing summaries for the dashboard
- Price input, output, and cached tokens

## Important Folders

- `src/routes/`: invoice and billing endpoints
- `src/models/`: invoice models
- `src/clients/`: API client for `api-core`
- `tests/`: service tests

## Quick Start

```bash
pip install -r requirements.txt
uvicorn src.main:app --host 127.0.0.1 --port 8002 --reload
```

## Environment Variables

Settings use the `BILLING_` prefix:

- `BILLING_GATEWAY_URL`
- `BILLING_DATABASE_URL`
- `BILLING_API_CORE_API_KEY`

## Main Endpoints

- `/health`
- `/api/v1/invoices`
- `/api/v1/invoices/{invoice_id}`
- `/api/v1/billing/summary`

## Testing

```bash
pytest
```
