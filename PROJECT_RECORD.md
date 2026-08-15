# Project Record — Refund Review Console

Living log of all implementation decisions, packages, files, environment variables, and chunk status.

---

## Chunk Status

| Chunk | Name | Status | Commit |
|:---:|:---|:---:|:---|
| 00 | Architecture & Planning Docs | ✅ Done | `CHUNK-00: Create Phase 0 architecture and planning documentation in docs/` |
| 00a | Doc refinements (cutoff, thresholds, overrides) | ✅ Done | `CHUNK-00: Refine docs with Support Queue cutoff, minor-unit thresholds, and agent override semantics` |
| 01 | Core Data Engine & 46 Unit Tests | ✅ Done | `CHUNK-01: Core data engine & state derivation rules` |
| 02 | FastAPI API Endpoints & Idempotency Store | ✅ Done | `CHUNK-02: FastAPI endpoints, queue routers, and idempotency store` |
| 03 | React Frontend Integration | ✅ Done | `CHUNK-03: Integrate Lovable React frontend into monorepo` |
| 03a | Frontend + backend bug fixes (rowsOf, metrics, flags, buttons) | ✅ Done | Multiple fix commits |
| 04 | Documentation & Final Verification | ✅ Done | `CHUNK-04: Documentation & final verification` |

---

## Packages Installed

### Backend (`backend/requirements.txt`)

| Package | Version | Purpose |
|:---|:---|:---|
| `fastapi` | latest | HTTP framework |
| `uvicorn` | latest | ASGI server |
| `pydantic` | v2 | Data validation and schemas |
| `python-dateutil` | latest | Timezone-aware timestamp parsing |
| `pytest` | latest | Test runner |
| `httpx` | latest | TestClient HTTP calls in tests |

### Frontend (`frontend/package.json`)

| Package | Purpose |
|:---|:---|
| `react` + `react-dom` | UI framework |
| `@tanstack/react-router` | File-based routing |
| `@tanstack/react-query` | Server state management |
| `tailwindcss` | Styling |
| `@radix-ui/*` | Accessible UI primitives |
| `vite` | Build tool |

---

## Files Created

### Root

| File | Purpose |
|:---|:---|
| `README.md` | Setup guide, architecture overview, API reference |
| `DECISIONS.md` | Technical decision log (12 decisions with rationale) |
| `AI_USAGE.md` | AI tool transparency log |
| `PROJECT_RECORD.md` | This file |
| `.gitignore` | Excludes `__pycache__`, `.pytest_cache`, `node_modules` |

### Backend (`backend/`)

| File | Purpose |
|:---|:---|
| `requirements.txt` | Python dependencies |
| `app/config.py` | `PINNED_NOW`, `SUPPORT_QUEUE_CUTOFF`, `HIGH_VALUE_THRESHOLDS` |
| `app/main.py` | FastAPI app, CORS middleware, lifespan data loader |
| `app/models/schemas.py` | Pydantic models: `Order`, `Event`, `RefundState`, `OrderStateSummary`, etc. |
| `app/services/ingest.py` | CSV + JSONL parser; dedup, timezone norm, minor unit conversion |
| `app/services/state_engine.py` | Pure derivation engine; 12 anomaly rules; queue filters; metrics |
| `app/services/decision_store.py` | In-memory singleton; holds states + decisions + idempotency cache |
| `app/routers/metrics.py` | `GET /api/metrics/summary` |
| `app/routers/queue.py` | `GET /api/orders`, `GET /api/orders/{id}` |
| `app/routers/actions.py` | `POST /api/refunds/{id}/decision` |
| `tests/test_state_engine.py` | 46 unit tests covering all 12 anomaly rules |
| `tests/test_api_endpoints.py` | 31 HTTP integration tests |

### Frontend (`frontend/src/`)

| File | Purpose |
|:---|:---|
| `lib/refund-api.ts` | Typed fetch helpers, `rowsOf()`, `formatMinor()` |
| `components/refund/MetricBar.tsx` | INR + USD pending payout summary cards |
| `components/refund/QueueTable.tsx` | Tabbed queue, search, pagination |
| `components/refund/OrderDetail.tsx` | Modal: event timeline, flags, warnings, action button |
| `components/refund/ActionDialog.tsx` | Approve/Reject dialog with idempotency |
| `components/refund/FlagPills.tsx` | Risk flag badge renderer |
| `routes/index.tsx` | Main page layout |

### Architecture Docs (`docs/`)

| File | Purpose |
|:---|:---|
| `01_PRD_AND_MVP_SCOPE.md` | Product requirements, personas, MVP boundary |
| `02_TECH_STACK_AND_SETUP.md` | Stack choices and dev environment setup |
| `03_SYSTEM_ARCHITECTURE.md` | API contracts, data flow, component diagram |
| `04_DATABASE_AND_DATA_ENGINE.md` | 12 anomaly rules, state machine, derivation formula |
| `05_WHAT_TO_AVOID.md` | Anti-patterns and explicit exclusions |

---

## Environment Variables

None required. All configuration is in `backend/app/config.py`:

```python
PINNED_NOW             = "2026-08-11T04:30:00Z"
SUPPORT_QUEUE_CUTOFF   = "2026-08-04T04:30:00Z"
HIGH_VALUE_INR_MINOR   = 5_000_000   # ₹50,000 * 100
HIGH_VALUE_USD_MINOR   = 50_000      # $500 * 100
DATA_DIR               = refund-console-data/
```

---

## Key Decisions (summary — see DECISIONS.md for full rationale)

| ID | Decision |
|:---|:---|
| D-01 | Dedup by `event_id` hash set; first occurrence wins |
| D-02 | Naive timestamps assumed IST; all normalised to UTC |
| D-03 | All amounts as integer minor units; `round(amount * 100)` |
| D-04 | Last chronological event determines final refund state |
| D-05 | Approved = removed from queue, but still in order's `pending_payout_minor` |
| D-06 | Orphan orders get placeholder with `total=0`, `is_orphan_order=True` |
| D-07 | Support queue uses OR logic: order OR any event within 7-day window |
| D-08 | In-memory state; no database needed for static dataset |
| D-09 | Client-side `crypto.randomUUID()` per click; server caches `key → response` |
| D-10 | `PINNED_NOW` constant; `datetime.now()` never called |
| D-11 | TanStack Query for all data fetching; `onSuccess` invalidates caches |
| D-12 | No auth; both views accessible via tab toggle |

---

## Blockers Encountered

| Date | Blocker | Resolution |
|:---|:---|:---|
| Session 2 | `refund-console-data/` directory emptied — data files missing | Restored from `git checkout 4938c49 -- refund-console-data/` |
| Session 2 | Finance queue showed "No orders match this view" | Root cause: `rowsOf()` did not check `res?.orders` key; fixed |
| Session 2 | MetricBar always showed `—` | Root cause: `pick()` did not check `data.pending_payout[code]`; fixed |
| Session 2 | "Action Decision" button never appeared in timeline | Root cause: `ev.status === "pending_approval"` guard — backend never sets status on timeline events; guard removed |
| Session 2 | Metrics count did not drop after approve | Root cause: `compute_system_metrics` counted both `pending` + `approved`; fixed to `pending` only |
| Session 2 | Port 8000 already bound when starting uvicorn | Pre-existing server process already running — queried it directly |

---

## Test Coverage

```
77 tests total — 0 failures — 0 warnings

test_state_engine.py   (46 tests)
  Rule 1:  Deduplication
  Rule 2:  Timezone normalisation
  Rule 3:  Minor unit conversion
  Rule 4:  Negative amounts
  Rule 5:  Zero amounts
  Rule 6:  Currency mismatch
  Rule 7:  Over-refund detection
  Rule 8:  State reversal
  Rule 9:  Double-loss risk
  Rule 10: Orphan orders
  Rule 11: Cross-gateway relay
  Rule 12: Event ordering
  Rule 13: Support queue cutoff
  Rule 14: High-value threshold flags
  Rule 15: Agent decision overrides
  Integration: System metrics

test_api_endpoints.py  (31 tests)
  Health check
  GET /api/metrics/summary  (5 tests)
  GET /api/orders?view=finance  (4 tests)
  GET /api/orders?view=support  (3 tests)
  GET /api/orders?search=  (3 tests)
  GET /api/orders/{id}  (9 tests)
  POST /api/refunds/{id}/decision  (6 tests — approve, reject, idempotency, 422s, 404)
```
