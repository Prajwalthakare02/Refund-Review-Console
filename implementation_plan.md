# Refund Review Console — Master Implementation Plan

> **Three-Lens Review**: CEO Strategy · Engineering Architecture · Design UX
> **Time Anchor**: `2026-08-11T10:00:00+05:30` (UTC: `2026-08-11T04:30:00Z`)

---

## Goal

Build a **Refund Review Console** — a single-screen internal tool that gives support agents and finance leads a trustworthy answer to: *"What is the state of this refund, and what can I still do about it?"*

The tool must ingest messy payment data (`orders.csv` + `events.jsonl`), derive truthful per-order refund states, display actionable queue and detail views, and record approval/rejection decisions safely.

---

## 🔴 CEO Strategic Review

### What matters most?
1. **Correctness over features** — The evaluators explicitly say: *"a small console that is right about a hard case beats a beautiful one that is quietly wrong."*
2. **Judgement under ambiguity** — The data is intentionally broken. Finding and documenting anomalies scores higher than adding features.
3. **Honest scope** — Knowing where to stop is part of the assessment. Over-building scores negatively.
4. **Commit history** — Evaluators read commits. One giant commit at the end scores badly.

### Strategic Decision: Scope Boundary
| Considered | Decision | Rationale |
| :--- | :--- | :--- |
| Add role-based auth (Priya vs Rahul login) | ❌ Skip | Not in spec. Over-engineering for 4-6 hour build. |
| Add real-time WebSocket updates | ❌ Skip | Spec says 2-week sample data, not live stream. |
| Add export to CSV/PDF | ❌ Skip | Not mentioned. Noise. |
| Add audit trail log viewer | ❌ Skip | Decision logging is enough. Full audit is scope creep. |
| Multi-currency aggregation in top metric | ✅ Include | Priya said "one number" but data has INR + USD. Must show both separately — cannot sum different currencies. |
| High-value flagging | ✅ Include | Priya explicitly asked for it. |
| 7-day historical view for support | ✅ Include | Rahul explicitly asked for it. |

---

## 🟡 Engineering Ar4chitecture Review

### Data Anomaly Debate & Resolution

#### Anomaly 1: Duplicate Events (Overnight Relay Replays)
**Finding**: `evt_0001` appears as an exact duplicate on lines 65 & 66.

| Option | Approach | Verdict |
| :--- | :--- | :--- |
| A | Ignore — process all events | ❌ Double-counts money |
| B | Deduplicate by `(order_id, amount, timestamp)` | ❌ False positives on legitimate same-amount refunds |
| **C (WINNER)** | **Deduplicate strictly by `event_id` hash set** | ✅ Exact, zero false positives |

**Rule**: First occurrence of an `event_id` wins. All subsequent duplicates are silently discarded.

---

#### Anomaly 2: Timezone Inconsistencies
**Finding**: Three distinct timestamp formats in `occurred_at`:
- `gw_primary` (147 events): ISO UTC with `Z` suffix
- `gw_upi` (61 events): ISO with explicit `+05:30` offset
- `legacy_gw` (6 events): Naive datetime string `"YYYY-MM-DD HH:MM:SS"` (no timezone)

| Option | Approach | Verdict |
| :--- | :--- | :--- |
| A | Treat all as UTC | ❌ Legacy events off by 5.5 hours, breaks chronological ordering |
| B | Use `received_at` instead of `occurred_at` for ordering | ❌ `received_at` has ingestion latency and out-of-order arrivals |
| **C (WINNER)** | **Parse naive strings as IST (`+05:30`), normalize ALL `occurred_at` to UTC epoch** | ✅ Correct ordering guaranteed |

**Rule**: If `occurred_at` has no timezone info, assume `Asia/Kolkata` (`+05:30`). Convert everything to UTC for storage and sorting. Use `occurred_at` (not `received_at`) as the canonical event timestamp.

---

#### Anomaly 3: Mixed Currency Units (`amount` vs `amount_minor`)
**Finding**: 208 events use integer `amount_minor` (paise/cents). 6 legacy events use float `amount` (major units like `823.55`).

| Option | Approach | Verdict |
| :--- | :--- | :--- |
| A | Store everything as floats | ❌ `0.1 + 0.2 = 0.30000000000000004` — Priya's ledger won't match |
| **B (WINNER)** | **Normalize ALL to integer minor units (paise/cents)** | ✅ Zero floating-point error, matches banking ledger precision |
| C | Store both fields separately | ❌ Complex query logic, error-prone aggregation |

**Rule**: `amount` floats are converted via `round(amount * 100)`. All math uses integers. Display converts back to major units on render only.

---

#### Anomaly 4: Negative Refund Amount (`-35000` on `ord_1022`)
**Finding**: `evt_0043` has `amount_minor: -35000` with reason `"correction"`.

| Option | Approach | Verdict |
| :--- | :--- | :--- |
| A | Treat as data error, ignore | ❌ Could be intentional correction from gateway |
| **B (WINNER)** | **Process literally — a negative refund.requested reduces the pending/refunded pool** | ✅ Corrections are a real pattern in payment systems |
| C | Take absolute value | ❌ Destroys the semantic meaning of a correction |

**Rule**: Negative amounts are valid corrections. They subtract from totals. Document this in `DECISIONS.md`.

---

#### Anomaly 5: Zero Refund Amount (`0` on `ord_1021`)
**Finding**: `evt_0042` has `amount_minor: 0` with reason `"adjustment"`.

| Option | Approach | Verdict |
| :--- | :--- | :--- |
| **A (WINNER)** | **Include in event timeline for auditability but exclude from monetary calculations** | ✅ Zero adds nothing to sums but provides audit context |
| B | Filter out entirely | ❌ Loses audit trail — Priya can't trace where numbers came from |

**Rule**: Zero-amount events appear in the order detail timeline but contribute nothing to all calculations.

---

#### Anomaly 6: Currency Mismatch (`ord_1024` — INR in orders, USD in events)
**Finding**: `ord_1024` has `total_amount: 7200.00, currency: INR` in orders.csv, but events reference `currency: USD, amount_minor: 720000`.

| Option | Approach | Verdict |
| :--- | :--- | :--- |
| A | Trust orders.csv, ignore event currency | ❌ Refund would show INR but gateway processed USD |
| B | Trust events.jsonl currency | ❌ Order total comparison breaks |
| **C (WINNER)** | **Trust the event's own currency for that refund line. Flag mismatch visually in detail view** | ✅ Shows truthful state while surfacing the discrepancy |

**Rule**: Each refund event carries its own currency. If event currency != order currency, display a warning badge. Do not silently convert.

---

#### Anomaly 7: Over-Refunds Exceeding Order Total
**Finding**:
- `ord_1003`: 999 INR order -> refunded 500 + 600 = 1,100 (110%)
- `ord_1030`: 12,500 INR order -> two 12,500 requests 2 seconds apart (200%)

| Option | Approach | Verdict |
| :--- | :--- | :--- |
| A | Cap refunds at order total | ❌ Hides real gateway behavior from finance |
| **B (WINNER)** | **Show actual amounts truthfully. Flag over-refund with warning badge** | ✅ Priya needs to see the real numbers, even uncomfortable ones |
| C | Block over-refund approval in UI | ❌ Not our call — we're building a review console, not a payment gateway |

**Rule**: Display real amounts. Show "Over-refunded" or "Exceeds order total" warning. `remaining_refundable` can go negative — this is informational.

---

#### Anomaly 8: State Anomaly — `rfnd_5050` (`requested -> succeeded -> failed`)
**Finding**: Refund was requested, then succeeded, then failed with `beneficiary_account_closed`.

| Option | Approach | Verdict |
| :--- | :--- | :--- |
| A | Last event wins (failed) | ❌ Money may have left the account before bouncing |
| B | First terminal event wins (succeeded) | ❌ Ignores the reversal |
| **C (WINNER)** | **Last event in chronological order determines final state. `failed` after `succeeded` = failed (money bounced back)** | ✅ Matches real-world payment reversal semantics |

**Rule**: Process events chronologically. Final terminal state wins. A `failed` after `succeeded` means the money bounced — treat as failed, amount returns to refundable pool.

---

#### Anomaly 9: Chargeback After Successful Refund (`ord_1014`)
**Finding**: Full refund of 5,600 INR succeeded, then a chargeback for 5,600 INR opened — double loss risk.

| Option | Approach | Verdict |
| :--- | :--- | :--- |
| **A (WINNER)** | **Show both truthfully. Flag with "Double Loss Risk" warning** | ✅ Finance needs to see this to dispute with card network |
| B | Subtract chargeback from refunded | ❌ Wrong — chargebacks and refunds are separate financial flows |

**Rule**: Chargebacks are tracked separately from refunds. Display chargeback info in order detail. If an order has both a successful refund AND an open chargeback, show a prominent "Double Loss Risk" alert.

---

#### Anomaly 10: Missing Order (`ord_1008` — events exist, order doesn't)
**Finding**: `evt_0020` references `ord_1008` but this order is absent from `orders.csv`.

| Option | Approach | Verdict |
| :--- | :--- | :--- |
| A | Silently skip these events | ❌ Loses money tracking |
| **B (WINNER)** | **Create an "orphan" order placeholder with `total_amount = unknown`. Show events but mark order as "Missing from export"** | ✅ Truthful — shows what we know without fabricating data |

**Rule**: Events referencing unknown `order_id`s create placeholder orders with `total_amount = null`. Display with "Order not in export" badge.

---

#### Anomaly 11: Cross-Gateway Duplicate Relay (`ord_1011`)
**Finding**: `rfnd_5101` (legacy_gw, 900.00 INR) and `rfnd_5100` (gw_upi, 900.00 INR) for the same order at the exact same second with near-identical reasons.

| Option | Approach | Verdict |
| :--- | :--- | :--- |
| A | Deduplicate by amount + timestamp | ❌ They have different `refund_id`s — could be legitimately separate |
| **B (WINNER)** | **Treat as separate refunds (different `refund_id`s). Flag potential duplicate visually** | ✅ We don't have enough info to auto-merge. Let humans decide. |

**Rule**: Different `refund_id` = different refund, even if amounts match. Show in timeline.

---

#### Anomaly 12: Out-of-Order Ingestion (`ord_1005`)
**Finding**: `refund.succeeded` was received 39 minutes BEFORE `refund.requested` due to ingestion latency.

| Option | Approach | Verdict |
| :--- | :--- | :--- |
| A | Use `received_at` for ordering | ❌ Creates impossible state transitions |
| **B (WINNER)** | **Use `occurred_at` for chronological ordering (after timezone normalization)** | ✅ `occurred_at` represents when the event actually happened at the gateway |

**Rule**: Always sort events by normalized `occurred_at`, never by `received_at`.

---

### Refund State Machine

```
[*] --> requested            (refund.requested)
requested --> succeeded      (refund.succeeded)
requested --> failed         (refund.failed)
succeeded --> failed         (refund.failed — money bounced)
requested --> approved       (Agent approves in console)
requested --> rejected       (Agent rejects in console)

Terminal states: succeeded, failed, rejected, approved
```

### Per-Order State Derivation Formula

```python
# For each order:
total_paid_minor = order.total_amount * 100  # Convert to minor units

# Group events by refund_id, sort by occurred_at
for each refund_id:
    final_state = last event type in chronological order
    
    if final_state == "refund.succeeded":
        refunded_minor += amount
    elif final_state == "refund.requested" and no agent decision:
        pending_minor += amount
    elif final_state == "refund.failed":
        pass  # Money returned to refundable pool
    elif agent_decision == "rejected":
        pass  # Declined, not counted

remaining_refundable = total_paid_minor - refunded_minor - pending_minor
# remaining_refundable CAN be negative (over-refund scenario)
```

### "High Value" Threshold
- INR: >= 50,000
- USD: >= 500

---

## 🟢 Design UX Review

### Layout Architecture

```
+--------------------------------------------------+
|  HEADER: "Refund Review Console"                  |
+--------------------------------------------------+
|  METRIC BAR                                       |
|  [Pending INR: X,XX,XXX.XX] [Pending USD: X,XXX] |
+--------------------------------------------------+
|  VIEW TABS: [Finance Queue] [Support History]     |
|  SEARCH: [________________] SORT: [Amount v]      |
+--------------------------------------------------+
|  QUEUE TABLE                                      |
|  Order   | Amount  | Status  | Flags   | Actions  |
|  ord_1012| 150,000 | Pending | HIGH    | Approve  |
|  ord_1003| 1,100   | Over-ref| OVER    | Detail   |
|  ord_1014| 5,600   | Refunded| CHRGBCK | Detail   |
+--------------------------------------------------+
|  ORDER DETAIL MODAL (on click)                    |
|  Order: ord_1003 | Customer: cus_403              |
|  Total Paid: 999.00 | Currency: INR               |
|  ---                                              |
|  EVENT TIMELINE:                                  |
|  Aug 04 refund.requested  500 rfnd_5020           |
|  Aug 04 refund.succeeded  500 rfnd_5020           |
|  Aug 05 refund.requested  600 rfnd_5021           |
|  Aug 05 refund.succeeded  600 rfnd_5021           |
|  ---                                              |
|  WARNING: OVER-REFUNDED 1,100 of 999 (110.1%)    |
|  ---                                              |
|  [Approve] [Reject] Reason: [________]            |
+--------------------------------------------------+
```

### Design Decisions
- **Layout**: Single-page with modal detail view (spec says "one screen")
- **Color**: Clean professional theme. Internal tool — clarity over aesthetics.
- **Badges**: Color-coded status pills for High Value, Over-refund, Chargeback, Pending, Succeeded, Failed
- **Metric separation**: Separate cards per currency (cannot sum INR + USD)
- **Double-click protection**: Button disables + spinner + UUID idempotency key

---

## Implementation Chunks

### Chunk 1: Data Engine & State Derivation + Tests
**Files**: `backend/requirements.txt`, `backend/app/config.py`, `backend/app/models/schemas.py`, `backend/app/services/ingest.py`, `backend/app/services/state_engine.py`, `backend/tests/`

**Key test cases**:
- Deduplication: `evt_0001` duplicate -> only 1 processed
- Timezone: Legacy `"2026-08-01 05:54:00"` -> `2026-08-01T00:24:00Z`
- Amount: Legacy `amount: 823.55` -> `amount_minor: 82355`
- Negative amount: `-35000` correctly reduces totals
- Zero amount: `0` excluded from monetary calculations
- Over-refund: `ord_1003` shows 1,100 refunded on 999 order
- State anomaly: `rfnd_5050` -> final state = `failed`
- Missing order: `ord_1008` -> placeholder with null total
- Out-of-order: Events sorted by `occurred_at` not `received_at`

**Exit gate**: `pytest -v` passes all tests.
**Commit**: `CHUNK-01: Core data engine & state derivation rules`

### Chunk 2: FastAPI Backend API
**Files**: `backend/app/main.py`, `backend/app/routers/metrics.py`, `backend/app/routers/queue.py`, `backend/app/routers/actions.py`

**Endpoints**:
- `GET /api/metrics/summary` -> pending by currency
- `GET /api/orders?view=finance|support&search=&page=&per_page=`
- `GET /api/orders/{order_id}` -> full detail + event timeline
- `POST /api/refunds/{refund_id}/decision` -> idempotent approve/reject

**Exit gate**: All endpoints return correct data. Idempotency prevents duplicates.
**Commit**: `CHUNK-02: FastAPI backend API & idempotency guard`

### Chunk 3: React Console UI
**Files**: All `frontend/` files

**Components**:
- `MetricBar`: Separate cards per currency showing pending payout
- `QueueTable`: Tabbed (Finance/Support), searchable, sortable, with status badges
- `OrderDetail`: Modal with event timeline, anomaly warnings, state summary
- `ActionDialog`: Approve/Reject with reason input, idempotency guard, double-click protection

**Exit gate**: UI loads, filters work, detail modal shows timeline, approve/reject works.
**Commit**: `CHUNK-03: React console dashboard & UI`

### Chunk 4: Documentation & Final Verification
**Files**: `DECISIONS.md`, `AI_USAGE.md`, `README.md`, `PROJECT_RECORD.md`

**Exit gate**: All 3 required docs complete. Full end-to-end flow verified.
**Commit**: `CHUNK-04: Documentation & final verification`

---

## Verification Plan

### Automated Tests
```bash
cd backend
pip install -r requirements.txt
pytest -v
```

### Manual Verification
1. Priya's Metric: Top metric shows correct pending payout per currency
2. Finance Queue: Only shows orders with actionable pending refunds
3. Support Queue: Shows all orders with refund activity in past 7 days
4. Order Detail (ord_1003): Shows over-refund warning (1,100 / 999)
5. Order Detail (ord_1014): Shows chargeback + refund double-loss warning
6. Order Detail (ord_1024): Shows currency mismatch warning
7. Order Detail (ord_1008): Shows "Order not in export" placeholder
8. Double-Click Test: Click Approve twice rapidly -> only 1 decision recorded
9. Negative Amount (ord_1022): Correction reduces total correctly
