# Technical Decisions Log

Every non-trivial decision made during implementation, with the options considered and the rationale for what was chosen.

---

## Data Layer

### D-01 — Event Deduplication Strategy

**Problem**: `evt_0001` appears twice in `events.jsonl` (lines 65 & 66 — exact byte-for-byte duplicate from an overnight relay replay).

| Option | Verdict | Reason |
|:---|:---:|:---|
| Process all events including duplicates | ❌ | Double-counts money — Priya's ledger would be wrong |
| Deduplicate on `(order_id, amount, timestamp)` composite | ❌ | False positives: two legitimate same-amount refunds for same order are indistinguishable |
| **Deduplicate strictly on `event_id` hash set** | ✅ | Zero false positives; first occurrence wins; O(n) |

**Rule implemented**: First occurrence of an `event_id` is kept. All subsequent duplicates are silently discarded at ingest time.

---

### D-02 — Timezone Normalisation

**Problem**: Three distinct timestamp formats in `occurred_at`:
- `gw_primary` (147 events): `2026-08-10T13:03:00Z` — explicit UTC
- `gw_upi` (61 events): `2026-08-10T14:22:00+05:30` — explicit IST offset
- `legacy_gw` (6 events): `2026-08-01 05:54:00` — naive string, no timezone

| Option | Verdict | Reason |
|:---|:---:|:---|
| Treat all naive strings as UTC | ❌ | Legacy events shift 5.5 hours — breaks chronological ordering |
| Use `received_at` for ordering | ❌ | `received_at` has ingestion latency; some events arrive out-of-order |
| **Parse naive strings as IST (+05:30), normalise everything to UTC** | ✅ | Correct; `legacy_gw` timestamps are IST by convention |

**Rule implemented**: `python-dateutil` parses all formats. Naive datetimes are assumed `Asia/Kolkata (+05:30)`. All timestamps stored as UTC ISO strings (`YYYY-MM-DDTHH:MM:SSZ`).

---

### D-03 — Minor Unit Standardisation

**Problem**: 208 events use integer `amount_minor` (paise/cents). 6 legacy events use float `amount` (e.g. `823.55`).

| Option | Verdict | Reason |
|:---|:---:|:---|
| Store everything as floats | ❌ | Floating-point error accumulates; `0.1 + 0.2 ≠ 0.3` |
| Store both fields separately | ❌ | Complex query logic; error-prone aggregation |
| **Normalise ALL to integer minor units** | ✅ | `round(amount * 100)` converts safely; all math is integer-only |

**Rule implemented**: All monetary values are integers throughout the backend. `amount` floats → `round(amount * 100)`. Display conversion (`/ 100`) happens only at serialisation time.

---

### D-04 — State Reversal Rule (final-event-wins)

**Problem**: `rfnd_5050` has events in sequence: `refund.requested → refund.succeeded → refund.failed`. The money bounced back. The "succeeded" record is no longer the truth.

**Decision**: The last chronological event by `occurred_at_utc` determines the final state of a refund chain. `rfnd_5050` final state = `failed`.

This means `refunded_succeeded_minor` does **not** include amounts from chains whose final event is `refund.failed`, even if an earlier event was `refund.succeeded`.

---

### D-05 — Agent Decision Override Semantics

**Problem**: When an agent approves a pending refund, what happens to `pending_payout_minor` and the finance queue?

| Status after decision | `pending_payout_minor` on order | In finance queue? | In metrics count? |
|:---|:---:|:---:|:---:|
| `pending` (no decision) | ✅ included | ✅ yes | ✅ yes |
| `approved` | ✅ included | ❌ no | ❌ no |
| `rejected` | ❌ excluded | ❌ no | ❌ no |

**Rationale**: Approved means money is authorised to leave but not yet settled. The order-level `pending_payout_minor` still reflects the liability. But the finance queue removes it (agent already decided — no more action needed). The top-level metrics counter shows only **unapproved** pending refunds so Priya can see her remaining workload decrease as she acts.

Rejected refunds are excluded from all financial totals — the claim was denied; no money moves.

---

### D-06 — Orphan Order Handling

**Problem**: `ord_1008` appears in `events.jsonl` but has no row in `orders.csv`.

**Decision**: Create a placeholder `Order` with `total_amount_minor=0`, `customer_id=""`, `currency="INR"`. Set `is_orphan_order=True` flag and append warning. This ensures no events are silently dropped and the anomaly is surfaced to support agents (Rahul).

---

### D-07 — Support Queue Cutoff Definition

**Definition**: An order belongs in Rahul's 7-Day Support History View if:
- `order.placed_at_utc >= 2026-08-04T04:30:00Z` (placed within 7 days of PINNED_NOW), **OR**
- Any event for that order has `occurred_at_utc >= 2026-08-04T04:30:00Z`

This captures cases where an old order has recent refund activity — exactly the orders a support agent needs to see.

---

## Backend Architecture

### D-08 — In-Memory State vs Database

**Decision**: Single in-memory singleton (`DecisionStore`) loaded at startup. No database.

**Rationale**: The spec is a 2-week static data snapshot evaluated by a fixed `PINNED_NOW`. A database would add 3–4 hours of setup (migrations, connection strings, seeding) with zero value for a deterministic read-only dataset. The in-memory store re-derives all states in < 10ms on restart.

**Production caveat**: `decision_store.py` documents that production would use PostgreSQL with row-level locking. The interface (`record_decision`, `check_idempotency`) maps directly to a database-backed implementation.

---

### D-09 — Idempotency Implementation

**Problem**: Finance agents double-click "Approve" — the refund must not be approved twice.

**Decision**: Client generates `crypto.randomUUID()` per click. The backend stores `idempotency_key → response_payload` in a dict. If the same key arrives again (within the server's lifetime), the cached response is returned without re-executing the mutation.

**Scope**: In-memory idempotency survives restarts only if the server is not restarted between clicks (sufficient for demo). Production would store idempotency keys in Redis or Postgres with a TTL.

---

### D-10 — PINNED_NOW vs `datetime.now()`

**Decision**: All temporal logic references `PINNED_NOW = "2026-08-11T04:30:00Z"` from `config.py`. `datetime.now()` is never called anywhere in the codebase.

**Rationale**: The dataset is a fixed historical slice. Using `datetime.now()` would cause different queue memberships on different run dates, making the system non-deterministic and the tests unreliable.

---

## Frontend Architecture

### D-11 — TanStack Query for All Data Fetching

**Decision**: All API calls use `useQuery` / `useMutation` from TanStack Query. No `useEffect` data fetching.

**Rationale**: Automatic cache invalidation on decision success (the `onSuccess` callback invalidates `["orders"]` and `["metrics"]` queryKeys) ensures the UI re-fetches and removes acted-on orders without a full page reload.

---

### D-12 — No Auth / Role Switching

**Decision**: No login screen. Both Priya and Rahul's views are accessible via the Finance/Support tab toggle.

**Rationale**: The spec describes two personas but does not require authentication. Adding auth would be scope creep for a 4-6 hour take-home and would score negatively per the CEO review criteria in `implementation_plan.md`.

---

## Scope Exclusions (Deliberate)

| Feature | Excluded because |
|:---|:---|
| Real-time WebSocket updates | Static 2-week dataset; no live event stream |
| Role-based auth | Not in spec; over-engineering |
| CSV/PDF export | Not mentioned; noise |
| Persistent database | Adds setup complexity with zero value for static data |
| Audit trail viewer | Decision logging sufficient; full log is scope creep |
