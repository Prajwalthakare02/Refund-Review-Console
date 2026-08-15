# Refund Review Console

Internal tool for finance and support teams to review, audit, and action refund decisions against a two-week payment event log.

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+ / Bun

### 1 — Backend

```bash
cd backend
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

Data files are read from `refund-console-data/orders.csv` and `refund-console-data/events.jsonl` at startup. No database required.

### 2 — Frontend

```bash
cd frontend
bun install        # or: npm install
bun run dev        # or: npm run dev
```

Opens at `http://localhost:3000`. The Vite dev server proxies `/api/*` to FastAPI on port 8000.

### 3 — Tests

```bash
cd backend
pytest -v          # 77 tests, all pass
```

---

## Architecture

```
refund-console-data/
  orders.csv          ← 155 orders (CSV)
  events.jsonl        ← 217 refund/chargeback events (JSONL)

backend/
  app/
    config.py         ← PINNED_NOW, cutoff constants, high-value thresholds
    models/
      schemas.py      ← Pydantic models (Order, Event, RefundState, …)
    services/
      ingest.py       ← Parse, deduplicate, normalise to UTC + minor units
      state_engine.py ← Pure derivation engine (12 anomaly rules)
      decision_store.py ← In-memory singleton, holds state + decisions
    routers/
      metrics.py      ← GET /api/metrics/summary
      queue.py        ← GET /api/orders, GET /api/orders/{id}
      actions.py      ← POST /api/refunds/{id}/decision
    main.py           ← FastAPI app, CORS, lifespan loader
  tests/
    test_state_engine.py   ← 46 unit tests (all 12 anomaly rules)
    test_api_endpoints.py  ← 31 HTTP integration tests

frontend/
  src/
    lib/
      refund-api.ts   ← Typed fetch helpers, rowsOf(), formatMinor()
    components/refund/
      MetricBar.tsx   ← Pending payout by currency (INR + USD cards)
      QueueTable.tsx  ← Tabbed queue (Finance / Support), search, pagination
      OrderDetail.tsx ← Modal: event timeline, flags, warnings
      ActionDialog.tsx← Approve / Reject with reason, idempotency guard
      FlagPills.tsx   ← Risk flag badges
    routes/
      index.tsx       ← Main page layout
```

---

## API Reference

| Method | Path | Description |
|:---|:---|:---|
| `GET` | `/api/metrics/summary` | Pending payout totals by currency |
| `GET` | `/api/orders?view=finance\|support&search=&page=&per_page=` | Paginated order queue |
| `GET` | `/api/orders/{order_id}` | Full order detail with event timeline |
| `POST` | `/api/refunds/{refund_id}/decision` | Approve or reject a pending refund |

### Decision request body

```json
{
  "action": "approve" | "reject",
  "reason": "Verified return receipt",
  "idempotency_key": "<uuid>"
}
```

---

## Personas

| Persona | View | Key need |
|:---|:---|:---|
| **Priya** (Finance Lead) | Finance Outflow Queue | Approve/reject pending refunds, see payout liability |
| **Rahul** (Support Agent) | Support History View | 7-day audit trail, anomaly flags, order context |

---

## Data Anomalies Handled

| Rule | Anomaly | Resolution |
|:---|:---|:---|
| 1 | Duplicate `event_id` | First occurrence wins; duplicates silently dropped |
| 2 | Mixed timezones (UTC Z, +05:30, naive IST) | All normalised to UTC ISO strings |
| 3 | `amount` float vs `amount_minor` int | All amounts stored as integer minor units (paise/cents) |
| 4 | Negative amounts | Processed literally; reduce pending payout |
| 5 | Zero-amount events | Processed; no monetary effect |
| 6 | Currency mismatch (refund ≠ order currency) | Flagged with warning |
| 7 | Over-refund (refunded > paid) | Flagged with percentage overage |
| 8 | State reversal (succeeded → failed) | Last chronological event wins |
| 9 | Double-loss risk (chargeback + refund) | Flagged 🚨 |
| 10 | Orphan orders (events with no CSV record) | Placeholder order created |
| 11 | Cross-gateway relay (same refund across gateways) | Grouped by `refund_id` |
| 12 | Out-of-order event arrival | Sorted by `occurred_at`, not `received_at` |

---

## Constants (pinned for deterministic test output)

```
PINNED_NOW              = 2026-08-11T04:30:00Z
SUPPORT_QUEUE_CUTOFF    = 2026-08-04T04:30:00Z  (7 days prior)
HIGH_VALUE_INR          = 5,000,000 paise  (₹50,000)
HIGH_VALUE_USD          = 50,000 cents     ($500)
```