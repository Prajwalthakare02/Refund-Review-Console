# Anti-Patterns & What to Avoid — Refund Review Console

## Executive Architectural Summary
This document defines explicit architectural anti-patterns, forbidden implementations, and premature optimizations that must be avoided during implementation to maintain high code quality and strict adherence to the project brief.

---

## 1. Architectural Anti-Patterns

### ❌ Floating-Point Financial Arithmetic
- **Anti-Pattern**: Using standard IEEE 754 floating-point numbers (`float` in Python or `Number` in JS) for financial calculations (e.g. `total_paid - refunded`).
- **Why Avoid**: Floating-point representation errors lead to trailing decimal artifacts (`0.30000000000000004`), causing mismatch with accounting ledgers.
- **Enforced Solution**: Standardize 100% of internal data representations into integer minor units (paise/cents). Convert to decimal strings strictly at the UI display formatting boundary.

### ❌ Wall-Clock Dependency
- **Anti-Pattern**: Using `datetime.now()` or `new Date()` in backend logic or UI relative time calculations.
- **Why Avoid**: Makes test outputs non-reproducible and invalidates historical sample evaluation.
- **Enforced Solution**: Reference canonical constant `PINNED_NOW = "2026-08-11T10:00:00+05:30"` across all modules.

### ❌ Business Logic in API Routers (Fat Controllers)
- **Anti-Pattern**: Writing event sorting, deduplication, or refund state machine evaluation directly inside FastAPI endpoint functions.
- **Why Avoid**: Violates MVC / Service-Layer separation, prevents unit testing of core business logic without spinning up HTTP test clients.
- **Enforced Solution**: Keep API routers paper-thin. Routers only validate request schemas, invoke pure functions in `services/`, and format response models.

---

## 2. Data Processing Anti-Patterns

### ❌ Sorting Events by `received_at`
- **Anti-Pattern**: Ordering payment events by system ingestion timestamp `received_at`.
- **Why Avoid**: Ingestion latency and relay job retries cause events to arrive out of order (e.g. `refund.succeeded` arriving before `refund.requested`).
- **Enforced Solution**: Always normalize and sort event sequences by gateway occurrence timestamp `occurred_at_utc`.

### ❌ Naive Timezone Assumptions
- **Anti-Pattern**: Assuming all naive string timestamps are UTC, or stripping timezone offsets before processing.
- **Why Avoid**: Legacy gateway timestamps in Hyderabad local time will be offset by 5 hours 30 minutes, corrupting event sequence ordering.
- **Enforced Solution**: Parse naive timestamps explicitly as `Asia/Kolkata` (`+05:30`) before converting to UTC ISO-8601 strings.

### ❌ Hiding or Auto-Correcting Data Anomalies
- **Anti-Pattern**: Silently clamping over-refund amounts to order totals, or suppressing currency mismatch events.
- **Why Avoid**: The core requirement is surfacing truthful payment state to Finance and Support. Hiding anomalies masks real production payment gateway issues.
- **Enforced Solution**: Display real derived amounts truthfully and surface anomaly warning pills (`⚠️ Over-refunded`, `⚠️ Currency Mismatch`, `🚨 Double Loss Risk`).

---

## 3. UI/UX Anti-Patterns

### ❌ Unprotected Decision Controls
- **Anti-Pattern**: Enabling approve/reject buttons without disabling state or idempotency token headers.
- **Why Avoid**: Network lag causes support agents to click "Approve" multiple times, issuing duplicate refund approvals.
- **Enforced Solution**: Disable action buttons immediately upon click, show loading spinners, and pass a unique client-generated `idempotency_key` with every request.

### ❌ Over-Nested Cards & Dashboard Clutter
- **Anti-Pattern**: Creating nested card hierarchies, decorative particle backgrounds, or multi-page routing structures.
- **Why Avoid**: Slows down support agents handling live phone calls and violates the brief requirement for a single-screen console.
- **Enforced Solution**: Maintain a clean, high-density single-page table layout with modal detail overlays.
