# System Architecture — Refund Review Console

## Executive Architectural Summary
The Refund Review Console follows a strict Service-Layer architecture pattern. Controllers (FastAPI Routers) do not contain financial state logic. All data parsing, deduplication, timezone adjustment, and state machine transitions live inside isolated pure Python service modules.

---

## 1. High-Level Component Diagram

```
┌────────────────────────────────────────────────────────────────────────┐
│                        REACT FRONTEND CONSOLE                          │
│                                                                        │
│  ┌──────────────────┐  ┌─────────────────────┐  ┌───────────────────┐  │
│  │    MetricBar     │  │     QueueTable      │  │    OrderDetail    │  │
│  │ (Pending Payout) │  │  (Finance/Support)  │  │ (Event Timeline)  │  │
│  └────────┬─────────┘  └──────────┬──────────┘  └─────────┬─────────┘  │
└───────────┼───────────────────────┼───────────────────────┼────────────┘
            │                       │                       │
            └───────────────────────┼───────────────────────┘
                                    │ HTTP / JSON API
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                          FASTAPI BACKEND                               │
│                                                                        │
│   ROUTERS:                                                             │
│   ├── /api/metrics/summary   --> GET Total Pending Payout              │
│   ├── /api/orders            --> GET Filtered Orders Queue             │
│   ├── /api/orders/{id}       --> GET Single Order Timeline             │
│   └── /api/refunds/{id}/decision --> POST Approve/Reject (Idempotent) │
│                                                                        │
│   SERVICES:                                                            │
│   ├── Ingestion Service      --> Read CSV/JSONL, Dedup, Normalize      │
│   └── State Engine           --> Derive per-order truth & flags        │
│                                                                        │
│   DATA SOURCES:                                                        │
│   ├── refund-console-data/orders.csv                                   │
│   └── refund-console-data/events.jsonl                                 │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 2. API Contract Specification

### 1. `GET /api/metrics/summary`
Returns system-wide pending financial liability grouped by currency.

**Response Schema (`200 OK`)**:
```json
{
  "pinned_now": "2026-08-11T10:00:00+05:30",
  "pending_payout": {
    "INR": {
      "amount_minor": 1845200,
      "amount_formatted": "₹18,452.00",
      "count": 14
    },
    "USD": {
      "amount_minor": 24999,
      "amount_formatted": "$249.99",
      "count": 1
    }
  }
}
```

### 2. `GET /api/orders`
Returns paginated, filterable order queue.

**Query Parameters**:
- `view`: `finance` (default, pending items only) | `support` (all activity within past 7 days)
- `search`: String search matching `order_id` or `customer_id`
- `page`: Integer (default `1`)
- `per_page`: Integer (default `50`)

**Response Schema (`200 OK`)**:
```json
{
  "total": 42,
  "page": 1,
  "per_page": 50,
  "orders": [
    {
      "order_id": "ord_1012",
      "customer_id": "cus_412",
      "currency": "INR",
      "total_paid_minor": 15000000,
      "total_paid_formatted": "₹150,000.00",
      "refunded_succeeded_minor": 0,
      "pending_payout_minor": 15000000,
      "remaining_refundable_minor": 0,
      "status": "pending_approval",
      "placed_at": "2026-08-04T04:30:00Z",
      "flags": {
        "is_high_value": true,
        "is_over_refunded": false,
        "has_chargeback": false,
        "has_currency_mismatch": false,
        "is_orphan_order": false
      }
    }
  ]
}
```

### 3. `GET /api/orders/{order_id}`
Returns complete order detail including raw event history.

**Response Schema (`200 OK`)**:
```json
{
  "order": { ... },
  "timeline": [
    {
      "event_id": "evt_0094",
      "type": "refund.requested",
      "refund_id": "rfnd_6027",
      "currency": "INR",
      "amount_minor": 603071,
      "occurred_at_utc": "2026-07-29T07:35:00Z",
      "source": "gw_primary",
      "reason": "item damaged"
    }
  ],
  "warnings": [
    "HIGH VALUE: Payout request exceeds ₹50,000 approval threshold"
  ]
}
```

### 4. `POST /api/refunds/{refund_id}/decision`
Records an agent approval or rejection with mandatory idempotency key header or body payload.

**Request Body**:
```json
{
  "action": "approve",
  "reason": "Verified return receipt from logistics partner",
  "idempotency_key": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```

**Response Schema (`200 OK`)**:
```json
{
  "success": true,
  "refund_id": "rfnd_6027",
  "new_status": "approved",
  "recorded_at": "2026-08-11T10:00:00+05:30",
  "idempotency_key": "9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d"
}
```

---

## 3. Idempotency Architecture (Double-Click Prevention)

To fix Rahul's complaint regarding agents double-clicking when the UI lags:
1. **Frontend**: When the user submits an approval/rejection decision, the UI immediately:
   - Disables the action button.
   - Replaces the label with a loading spinner.
   - Generates a client-side UUID `idempotency_key` bound to the active modal session.
2. **Backend**: The decision handler maintains an in-memory/SQLite cache of processed `idempotency_key`s.
   - If an incoming request carries an `idempotency_key` already present in the cache, the backend bypasses execution and immediately returns the cached `200 OK` response without mutating state a second time.
