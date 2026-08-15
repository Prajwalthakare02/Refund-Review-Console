# PRD & MVP Scope — Refund Review Console

## Executive Overview
The **Refund Review Console** is a single-screen internal application engineered to serve Support Agents and Finance Leads. It provides a single, unassailable source of truth regarding order refund states, pending liabilities, and decision capabilities.

---

## 1. Core Personas & User Stories

### Persona A: Priya (Finance Lead)
- **Goal**: Outflow control, financial liability tracking, auditability.
- **Pain Points**: High-value payouts slipping through without approval; unknown daily total pending liability; inability to reconcile console numbers with payment gateway ledgers.
- **Key Requirements**:
  1. **Top Summary Metric**: Real-time total pending payout liability broken down by currency (`INR`, `USD`).
  2. **Finance Outflow Queue**: A dedicated queue displaying *only* active, actionable pending refunds.
  3. **High-Value Flags**: Prominent visual identification of high-value refund requests requiring sign-off. Exact thresholds in minor units:
     - **INR**: `>= 5,000,000 paise` (₹50,000 × 100)
     - **USD**: `>= 50,000 cents` ($500 × 100)
  4. **Ledger Auditability**: Every derived number must map directly back to a chain of raw, verifiable payment gateway events.

### Persona B: Rahul (Support Lead)
- **Goal**: First-contact customer resolution, agent efficiency, operational safety.
- **Pain Points**: Support agents bouncing between 3 internal tools and spreadsheets; accidental double-approvals when internal UI hangs.
- **Key Requirements**:
  1. **Support History Queue**: Access to all orders with refund activity in the last 7 days (from pinned NOW anchor).
  2. **Comprehensive Order Detail Modal**: Instant chronological timeline of all events for a given order so agents can explain status live over the phone.
  3. **Idempotent Decision Control**: Approve/Reject controls with mandatory reason input and strict double-click prevention.

---

## 2. Pinned Time Anchor
- **Canonical "NOW"**: `2026-08-11T10:00:00+05:30` (UTC: `2026-08-11T04:30:00Z`).
- All relative date calculations (such as Rahul's 7-day support queue window) are strictly computed relative to this timestamp anchor. Wall-clock system time must never be referenced.

---

## 3. Core Functional Requirements (MVP Scope)

### Part A — Data State Engine
- Ingest `orders.csv` and `events.jsonl`.
- Apply strict deduplication, timezone normalization, and currency unit standardization.
- Derive exact per-order metrics: `total_paid_minor`, `refunded_succeeded_minor`, `pending_payout_minor`, and `remaining_refundable_minor`.

### Part B — Full-Stack Console
- **Summary Header**: Display total pending payout by currency.
- **Tabbed Queue Views**: Switch between "Finance Outflow Queue" (actionable pending items) and "Support History View" (all orders with activity within past 7 days).
- **Order Search & Filter**: Search by `order_id` or `customer_id`.
- **Order Detail Timeline**: Render chronological event lifecycle with status pills and warning flags.
- **Action Control**: Approve or Reject pending refunds with reason logging and double-click idempotency guard.

---

## 4. Scope Boundaries (What is OUT of Scope)
To ensure a high-quality 4–6 hour implementation focused on correctness:
- **Authentication & RBAC**: No multi-tenant user login system (Priya vs Rahul logins). Role perspectives are presented via clean tabbed views.
- **Real-Time WebSockets**: Data is ingested cleanly on startup; state updates in-memory upon agent actions.
- **Payment Gateway Payout Integration**: Actions durably record approval/rejection decisions without calling real external bank APIs.
- **CSV/PDF Export**: Reporting exports are omitted; focus remains on the live console interface.
