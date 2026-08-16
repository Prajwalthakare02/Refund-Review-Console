# Technical Decisions Log

Every non-trivial decision made during implementation, with the options considered and the rationale for what was chosen.

---

## Data Layer

### D-01 — Event Deduplication Strategy

**Problem**: `evt_0001` appears twice in `events.jsonl` (an overnight relay replay).

| Option | Verdict | Reason |
|:---|:---:|:---|
| Process all events including duplicates | ❌ | Double-counts money |
| Deduplicate on a composite key | ❌ | False positives for legitimate same-amount refunds |
| **Deduplicate strictly on `event_id`** | ✅ | Zero false positives; first occurrence wins |

**Rule implemented**: First occurrence of an `event_id` is kept. All subsequent duplicates are silently discarded at ingest time.

---

### D-02 — Timezone Normalisation

**Problem**: Three distinct timestamp formats exist in `occurred_at`:

- UTC `Z`
- explicit IST `+05:30`
- naive legacy gateway strings

| Option | Verdict | Reason |
|:---|:---:|:---|
| Treat naive timestamps as UTC | ❌ | Breaks ordering for legacy gateway events |
| Use `received_at` for ordering | ❌ | Ingestion latency makes this unreliable |
| **Parse naive strings as IST, normalise everything to UTC** | ✅ | Matches the legacy gateway convention |

**Rule implemented**: Naive timestamps are assumed `Asia/Kolkata (+05:30)`. All timestamps are stored as UTC ISO strings.

---

### D-03 — Minor Unit Standardisation

**Problem**: Some records provide `amount_minor`; legacy rows provide decimal `amount`.

| Option | Verdict | Reason |
|:---|:---:|:---|
| Store everything as floats | ❌ | Floating-point error accumulates |
| Store both fields separately | ❌ | Query logic becomes inconsistent |
| **Normalise all amounts to integer minor units** | ✅ | All math stays integer-only |

**Rule implemented**: All monetary values are integers throughout the backend. Decimal `amount` values are converted with `round(amount * 100)`.

---

### D-04 — State Reversal Rule

**Problem**: Some refunds transition `requested -> succeeded -> failed`.

**Decision**: The last chronological event by `occurred_at_utc` determines the final state of a refund chain.

This means `refunded_succeeded_minor` does not include amounts from chains whose final event is `refund.failed`.

---

### D-05 — Agent Decision Override Semantics

**Problem**: When an agent approves or rejects a refund, what should happen to the queue and metrics?

| Status after decision | `pending_payout_minor` on order | In finance queue? | In metrics count? |
|:---|:---:|:---:|:---:|
| `pending` (no decision) | ✅ included | ✅ yes | ✅ yes |
| `approved` | ❌ excluded | ❌ no | ❌ no |
| `rejected` | ❌ excluded | ❌ no | ❌ no |

**Rationale**: The console is an action queue, not a settlement ledger. Once an agent approves or rejects, that refund is no longer actionable and should stop counting as pending outflow in the UI and metrics. Approved/rejected remain visible in Support History for auditability.

---

### D-06 — Orphan Order Handling

**Problem**: Some events reference order IDs not present in `orders.csv`.

**Decision**: Create a placeholder `Order` with `total_amount_minor=0`, `customer_id=""`, `currency="INR"`. Set `is_orphan_order=True` and append a warning.

---

### D-07 — Support Queue Cutoff Definition

**Definition**: An order belongs in Rahul's 7-Day Support History View if:

- it has at least one refund or chargeback event in the last 7 days, and
- either the order was placed in the last 7 days or has recent refund activity.

This excludes recently created orders with no refund activity.

---

## Backend Architecture

### D-08 — Persistence Strategy

**Decision**: Startup-loaded order/event state plus a small SQLite file for decisions and idempotency records.

**Rationale**: The core dataset is static, but agent decisions must survive restarts. SQLite gives durability with minimal setup and keeps the implementation aligned with the take-home scope.

---

### D-09 — Idempotency Implementation

**Problem**: Finance agents double-click “Approve”.

**Decision**: Client generates one `crypto.randomUUID()` per modal session. The backend stores `idempotency_key -> response_payload` in SQLite and keeps an in-memory cache for hot-path lookups. If the same key arrives again, the cached response is returned without re-executing the mutation.

---

### D-10 — Pinned Time

**Decision**: All temporal logic references the pinned `PINNED_NOW` constant from `config.py`. `datetime.now()` is never called.

**Rationale**: The dataset is a fixed historical slice, so wall-clock time would make queue membership non-deterministic.

---

## Frontend Architecture

### D-11 — TanStack Query for Data Fetching

**Decision**: Use TanStack Query for all API calls and invalidate on successful mutation.

**Rationale**: The UI needs to reflect decisions immediately after approve/reject.

---

### D-12 — No Auth / Role Switching

**Decision**: No login screen. Finance and Support are tabbed views in a single internal console.

**Rationale**: Authentication is out of scope for the take-home.
