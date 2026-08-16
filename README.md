# Refund Review Console

Internal tool for finance and support teams to review, audit, and action refund decisions against a two-week payment event log.

## Quick Start

### Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Data is loaded from `refund-console-data/orders.csv` and `refund-console-data/events.jsonl` at startup. Agent decisions and idempotency keys are persisted in `backend/data/decisions.sqlite3`.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The app runs at `http://localhost:3000`. The frontend calls the FastAPI base URL directly at `http://localhost:8000/api`, so CORS must be enabled on the backend.

### Tests

```bash
cd backend
pytest -v
```

## What it does

- Finance view: actionable pending refunds only.
- Support view: recent refund history, including approved and rejected items.
- Order detail: chronological event timeline, flags, warnings, and refund status.
- Action control: approve/reject with reason and idempotency protection.
- Summary metric: total pending payout by currency.

## Architecture

- `backend/app/services/ingest.py` parses CSV/JSONL, deduplicates events, and normalises timestamps and amounts.
- `backend/app/services/state_engine.py` derives truth from the event chains and queue rules.
- `backend/app/services/decision_store.py` persists decisions and idempotency records in SQLite.
- `backend/app/routers/*` exposes the API.
- `frontend/src/components/refund/*` renders the console UI.

## API

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/metrics/summary` | Pending payout totals by currency |
| `GET` | `/api/orders?view=finance\|support&search=&page=&per_page=` | Paginated queue |
| `GET` | `/api/orders/{order_id}` | Full order detail with timeline |
| `POST` | `/api/refunds/{refund_id}/decision` | Approve or reject a refund |

## Notes

- All amounts are stored in minor units.
- All timestamps are normalised to UTC.
- `PINNED_NOW` is fixed for deterministic output.
- The project intentionally avoids auth, live updates, and export features.
