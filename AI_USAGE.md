# AI Usage Log

Transparent record of how AI assistance was used during this project, what was generated, and what required human review and correction.

---

## Tool Used

**Antigravity (Google DeepMind)** — an agentic coding assistant running inside the IDE.

---

## Summary

AI was used as a **senior pair-programmer**, not as a code generator. Every output was reviewed, tested against real data, and corrected where it diverged from the spec. The human made all architectural decisions; AI implemented them.

---

## Phase 0 — Architecture & Planning

**Prompt strategy**: Provided the full assignment brief plus two parallel data-analysis subagents that exhaustively read `orders.csv` (155 rows) and `events.jsonl` (215 events) and reported all anomalies, field types, timestamp formats, and edge cases before any code was written.

**AI contribution**:
- Drafted the 5 architecture documents in `docs/`
- Structured the 12 anomaly rules from the raw data analysis
- Identified the three timestamp format variants (UTC Z, explicit +05:30, naive IST)
- Identified the `amount` vs `amount_minor` dual-field problem in legacy events

**Human correction**: Added the Support Queue Cutoff definition (7-day window based on OR logic covering both `placed_at` and event timestamps), high-value thresholds in exact minor units, and agent decision override semantics — none of which were in the initial AI draft.

---

## Phase 1 — Data Engine (CHUNK-01)

**AI contribution**: Generated `ingest.py`, `state_engine.py`, `schemas.py`, and 46 unit tests covering all 12 rules.

**Issues caught by tests**:
- Initial `amount` float-to-minor conversion used `int(amount * 100)` (truncating) instead of `round(amount * 100)` — caught by Rule 3 test for `823.55` → expected `82355`
- Legacy timezone handling initially used `dateutil.parser.parse()` without explicit `default` timezone — fixed to explicitly assign `Asia/Kolkata` for naive strings

**Human review**: Verified all 12 anomaly test cases against the raw data files manually. Confirmed `rfnd_5050` state-reversal edge case and `ord_1003` over-refund amounts match the raw CSV/JSONL values.

---

## Phase 2 — FastAPI Backend (CHUNK-02)

**AI contribution**: Generated `main.py`, four routers, `decision_store.py`, and 31 API endpoint tests.

**Issues caught during testing**:
- `query.py` initially used `regex=` instead of `pattern=` in FastAPI `Query()` — deprecated in Pydantic v2, caught by deprecation warning, fixed immediately
- `_serialise_order_summary` initially omitted `pending_payout_formatted` and `refunded_succeeded_formatted` — discovered when live API audit showed the frontend falling back to client-side `formatMinor()`
- `compute_system_metrics` initially counted both `pending` and `approved` refunds — metrics counter did not drop after Priya approved a refund. Fixed to count only `status == "pending"` so the dashboard workload number decreases as agents act

**Human correction**: Idempotency semantics — initial version stored decisions by `refund_id` only. Human confirmed the idempotency key must also be cached separately to handle the double-click case where the same UUID arrives twice (different from approving the same refund twice with different keys).

---

## Phase 3 — React Frontend (CHUNK-03)

**AI contribution**: The Lovable-generated frontend was integrated as a base. AI corrected the following issues:

| Bug | Root Cause | Fix |
|:---|:---|:---|
| Finance queue showed "No orders match this view" | `rowsOf()` checked `res?.items \|\| res?.data` but backend returns `res?.orders` | Added `res?.orders` as first fallback in `rowsOf()` |
| MetricBar showed `—` for both currencies | `pick()` checked `data[code]` but metrics live in `data.pending_payout[code]` | Added `pending_payout` lookup path |
| "Action Decision" button never appeared | `needsDecision` checked `ev.status === "pending_approval"` — backend never sets `status` on timeline events | Removed the dead status check |
| `has_double_loss_risk` flag never rendered | Missing from `OrderFlags` TypeScript type | Added to type and to `FlagPills` PILLS array |
| `has_chargeback` pill was labelled "Double Loss Risk" | Copy-paste error in initial PILLS array | Split into two distinct pills with correct labels |

**Human review**: Traced each bug by querying the live backend directly via Python `urllib.request`, comparing JSON structure against TypeScript type definitions, then reading component render paths.

---

## What AI Did Not Do

- Did not choose the technology stack (FastAPI + React + TanStack Query was already specified)
- Did not decide scope boundaries (those were CEO-level decisions in `DECISIONS.md`)
- Did not decide anomaly rules (rules were derived from reading the actual data and the assignment brief)
- Did not write the final commit messages (those followed the `CHUNK-NN:` convention set by the human)
- Did not run any terminal command without explicit human approval (all `run_command` calls required permission)

---

## Verification Approach

Every AI-generated code block was verified by:
1. **Automated tests** — `pytest -v` after every chunk (77 tests total, 0 failures)
2. **Live API queries** — Python `urllib.request` against the running FastAPI server to inspect actual JSON responses
3. **Data cross-referencing** — Manually checking edge-case orders (`ord_1003`, `ord_1008`, `ord_1014`, `ord_1024`) against raw CSV and JSONL files
