"""
Pydantic models for the Refund Review Console.

Every monetary field is typed as `int` and represents **minor units**
(paise for INR, cents for USD).  No floats cross the schema boundary.
"""

from __future__ import annotations

from typing import Optional
from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Core data models (used internally after ingestion)
# ---------------------------------------------------------------------------

class Order(BaseModel):
    """Parsed row from orders.csv with amount converted to minor units."""
    order_id: str
    customer_id: str
    currency: str
    total_amount_minor: int          # round(total_amount * 100)
    placed_at_utc: str               # ISO-8601 UTC string
    channel: str
    region: str


class Event(BaseModel):
    """Parsed line from events.jsonl after dedup and normalisation."""
    event_id: str
    type: str                        # refund.requested | .succeeded | .failed | chargeback.opened
    order_id: str
    refund_id: Optional[str] = None  # null for chargeback.opened
    currency: str
    amount_minor: int                # always integer minor units
    occurred_at_utc: str             # ISO-8601 UTC string (canonical ordering key)
    received_at_utc: str             # ISO-8601 UTC string (ingestion timestamp)
    source: str                      # gw_primary | gw_upi | legacy_gw
    reason: Optional[str] = None
    failure_code: Optional[str] = None
    requested_by: Optional[str] = None
    network_case_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Flags derived per order by the state engine
# ---------------------------------------------------------------------------

class OrderFlags(BaseModel):
    """Boolean anomaly / attention flags for an order."""
    is_high_value: bool = False
    is_over_refunded: bool = False
    has_chargeback: bool = False
    has_currency_mismatch: bool = False
    is_orphan_order: bool = False
    has_double_loss_risk: bool = False


# ---------------------------------------------------------------------------
# Per-refund state (grouped by refund_id)
# ---------------------------------------------------------------------------

class RefundState(BaseModel):
    """Derived state for a single refund_id."""
    refund_id: str
    order_id: str
    currency: str
    amount_minor: int
    status: str                      # pending | succeeded | failed | approved | rejected
    reason: Optional[str] = None
    failure_code: Optional[str] = None
    is_high_value: bool = False
    events: list[Event] = []


# ---------------------------------------------------------------------------
# Aggregate per-order state summary
# ---------------------------------------------------------------------------

class OrderStateSummary(BaseModel):
    """Full derived state for a single order."""
    order: Order
    refunded_succeeded_minor: int = 0
    pending_payout_minor: int = 0
    approved_decision_minor: int = 0
    rejected_decision_minor: int = 0
    remaining_refundable_minor: int = 0
    chargeback_amount_minor: int = 0
    flags: OrderFlags = OrderFlags()
    refunds: list[RefundState] = []
    events: list[Event] = []
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# System-wide summary metric (Priya's top number)
# ---------------------------------------------------------------------------

class CurrencyPendingSummary(BaseModel):
    """Pending payout for a single currency."""
    amount_minor: int = 0
    count: int = 0


class SystemMetricsSummary(BaseModel):
    """Aggregate pending payout liability across the entire system."""
    pinned_now: str
    pending_payout: dict[str, CurrencyPendingSummary] = {}


# ---------------------------------------------------------------------------
# Agent decision record
# ---------------------------------------------------------------------------

class AgentDecision(BaseModel):
    """Durable record of an agent approve / reject action."""
    refund_id: str
    action: str                      # "approve" | "reject"
    reason: str
    idempotency_key: str
    recorded_at: str                 # ISO-8601 UTC string
