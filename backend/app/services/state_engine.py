"""
State derivation engine for the Refund Review Console.

Operates entirely on integer minor units.  Never references the wall clock.
Implements Rules 4-15 from docs/04_DATABASE_AND_DATA_ENGINE.md.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Optional

from app.config import (
    HIGH_VALUE_THRESHOLDS,
    PINNED_NOW_ISO,
    SUPPORT_QUEUE_CUTOFF_ISO,
)
from app.models.schemas import (
    AgentDecision,
    CurrencyPendingSummary,
    Event,
    Order,
    OrderFlags,
    OrderStateSummary,
    RefundState,
    SystemMetricsSummary,
)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _group_events_by_order(events: list[Event]) -> dict[str, list[Event]]:
    """Group events by order_id."""
    grouped: dict[str, list[Event]] = defaultdict(list)
    for evt in events:
        grouped[evt.order_id].append(evt)
    return dict(grouped)


def _group_events_by_refund(events: list[Event]) -> dict[Optional[str], list[Event]]:
    """Group events by refund_id (None key collects chargebacks)."""
    grouped: dict[Optional[str], list[Event]] = defaultdict(list)
    for evt in events:
        grouped[evt.refund_id].append(evt)
    return dict(grouped)


def _is_high_value(amount_minor: int, currency: str) -> bool:
    """Rule 14: Check if amount meets high-value threshold for its currency."""
    threshold = HIGH_VALUE_THRESHOLDS.get(currency, 0)
    return abs(amount_minor) >= threshold


# ---------------------------------------------------------------------------
# Per-order state derivation
# ---------------------------------------------------------------------------

def derive_order_state(
    order: Order,
    order_events: list[Event],
    decisions: Optional[dict[str, AgentDecision]] = None,
) -> OrderStateSummary:
    """
    Derive the truthful financial state for a single order.

    Parameters
    ----------
    order : Order
        Parsed order record (may have total_amount_minor=0 for orphans).
    order_events : list[Event]
        All events belonging to this order (already deduplicated & normalised).
    decisions : dict[str, AgentDecision] | None
        Agent decisions keyed by refund_id.

    Returns
    -------
    OrderStateSummary
        Complete derived state including refund breakdowns, flags, and warnings.
    """
    decisions = decisions or {}

    # Sort all events chronologically by occurred_at_utc (Rule 12)
    sorted_events = sorted(order_events, key=lambda e: e.occurred_at_utc)

    # Group by refund_id
    by_refund = _group_events_by_refund(sorted_events)

    refunded_succeeded: int = 0
    pending_payout: int = 0
    chargeback_amount: int = 0
    has_chargeback = False
    has_currency_mismatch = False
    any_high_value = False
    refund_states: list[RefundState] = []
    warnings: list[str] = []

    for refund_id, chain in by_refund.items():
        # Sort chain chronologically (Rule 12)
        chain = sorted(chain, key=lambda e: e.occurred_at_utc)

        # --- Chargeback handling (Rule 9) ---
        if refund_id is None or any(e.type == "chargeback.opened" for e in chain):
            for evt in chain:
                if evt.type == "chargeback.opened":
                    chargeback_amount += evt.amount_minor
                    has_chargeback = True
            continue

        latest_event = chain[-1]
        amount = latest_event.amount_minor

        # Rule 6: Currency mismatch detection
        if latest_event.currency != order.currency:
            has_currency_mismatch = True

        # Rule 14: High-value detection
        refund_high_value = _is_high_value(amount, latest_event.currency)
        if refund_high_value:
            any_high_value = True

        # Rule 15: Agent decision overrides
        decision = decisions.get(refund_id)

        if decision and decision.action in ("reject", "rejected"):
            # Rejected: remove from pending, do NOT deduct from remaining
            refund_states.append(RefundState(
                refund_id=refund_id,
                order_id=order.order_id,
                currency=latest_event.currency,
                amount_minor=amount,
                status="rejected",
                reason=decision.reason,
                is_high_value=refund_high_value,
                events=chain,
            ))
            continue

        if decision and decision.action in ("approve", "approved"):
            # Approved: no longer actionable in Finance Queue.
            # Once the agent has approved it, it should stop counting as
            # pending payout in the review console.
            refund_states.append(RefundState(
                refund_id=refund_id,
                order_id=order.order_id,
                currency=latest_event.currency,
                amount_minor=amount,
                status="approved",
                reason=decision.reason,
                is_high_value=refund_high_value,
                events=chain,
            ))
            continue

        # No manual decision — derive from gateway events
        # Rule 8: Last chronological event determines final state
        if latest_event.type == "refund.succeeded":
            refunded_succeeded += amount
            refund_states.append(RefundState(
                refund_id=refund_id,
                order_id=order.order_id,
                currency=latest_event.currency,
                amount_minor=amount,
                status="succeeded",
                is_high_value=refund_high_value,
                events=chain,
            ))
        elif latest_event.type == "refund.failed":
            # Rule 8: Failed (possibly after succeeded = money bounced back)
            refund_states.append(RefundState(
                refund_id=refund_id,
                order_id=order.order_id,
                currency=latest_event.currency,
                amount_minor=amount,
                status="failed",
                failure_code=latest_event.failure_code,
                is_high_value=refund_high_value,
                events=chain,
            ))
        elif latest_event.type == "refund.requested":
            # Rule 4 & 5: amount_minor can be negative or zero — process literally
            pending_payout += amount
            refund_states.append(RefundState(
                refund_id=refund_id,
                order_id=order.order_id,
                currency=latest_event.currency,
                amount_minor=amount,
                status="pending",
                reason=latest_event.reason,
                is_high_value=refund_high_value,
                events=chain,
            ))

    # --- Derive aggregate metrics ---
    total_paid = order.total_amount_minor
    remaining = total_paid - refunded_succeeded - pending_payout

    # Rule 7: Over-refund detection
    is_over_refunded = (refunded_succeeded + pending_payout) > total_paid and total_paid > 0

    # Rule 9: Double-loss risk (chargeback + successful refund on same order)
    has_double_loss = has_chargeback and refunded_succeeded > 0

    # Rule 10: Orphan order detection
    is_orphan = total_paid == 0 and order.customer_id == ""

    # Build flags
    flags = OrderFlags(
        is_high_value=any_high_value,
        is_over_refunded=is_over_refunded,
        has_chargeback=has_chargeback,
        has_currency_mismatch=has_currency_mismatch,
        is_orphan_order=is_orphan,
        has_double_loss_risk=has_double_loss,
    )

    # Build warnings list
    if is_over_refunded:
        total_out = refunded_succeeded + pending_payout
        pct = round(total_out / total_paid * 100, 1) if total_paid else 0
        warnings.append(
            f"OVER-REFUNDED: {total_out} of {total_paid} minor units ({pct}%)"
        )
    if has_double_loss:
        warnings.append(
            f"DOUBLE LOSS RISK: Chargeback of {chargeback_amount} minor units "
            f"opened on order with {refunded_succeeded} minor units already refunded"
        )
    if has_currency_mismatch:
        warnings.append("CURRENCY MISMATCH: Refund event currency differs from order currency")
    if is_orphan:
        warnings.append("ORPHAN ORDER: Order not found in orders.csv export")
    if any_high_value:
        warnings.append("HIGH VALUE: One or more refund requests exceed approval threshold")

    return OrderStateSummary(
        order=order,
        refunded_succeeded_minor=refunded_succeeded,
        pending_payout_minor=pending_payout,
        remaining_refundable_minor=remaining,
        chargeback_amount_minor=chargeback_amount,
        flags=flags,
        refunds=refund_states,
        events=sorted_events,
        warnings=warnings,
    )


# ---------------------------------------------------------------------------
# System-wide state derivation
# ---------------------------------------------------------------------------

def derive_all_order_states(
    orders: list[Order],
    events: list[Event],
    decisions: Optional[dict[str, AgentDecision]] = None,
) -> list[OrderStateSummary]:
    """
    Derive state for every order in the system.

    Rule 10: Events referencing unknown order_ids create orphan placeholders.
    """
    decisions = decisions or {}
    events_by_order = _group_events_by_order(events)

    # Build lookup of known orders
    order_map: dict[str, Order] = {o.order_id: o for o in orders}

    # Rule 10: Detect orphan orders (events reference order_ids not in CSV)
    all_order_ids = set(order_map.keys()) | set(events_by_order.keys())

    results: list[OrderStateSummary] = []

    for oid in sorted(all_order_ids):
        order = order_map.get(oid)
        if order is None:
            # Rule 10: Create orphan placeholder
            order = Order(
                order_id=oid,
                customer_id="",
                currency="INR",
                total_amount_minor=0,
                placed_at_utc="",
                channel="",
                region="",
            )

        order_events = events_by_order.get(oid, [])
        state = derive_order_state(order, order_events, decisions)

        # Mark orphan flag
        if oid not in order_map:
            state.flags.is_orphan_order = True
            if "ORPHAN ORDER" not in " ".join(state.warnings):
                state.warnings.append("ORPHAN ORDER: Order not found in orders.csv export")

        results.append(state)

    return results


# ---------------------------------------------------------------------------
# Priya's top metric: total pending payout by currency
# ---------------------------------------------------------------------------

def compute_system_metrics(
    order_states: list[OrderStateSummary],
) -> SystemMetricsSummary:
    """
    Compute system-wide pending payout broken down by currency.

    Counts only refunds in 'pending' status (awaiting agent decision).
    Approved refunds are tracked separately as authorised-pending-settlement.
    """
    pending_by_currency: dict[str, CurrencyPendingSummary] = {}

    for oss in order_states:
        for refund in oss.refunds:
            if refund.status == "pending":
                cur = refund.currency
                if cur not in pending_by_currency:
                    pending_by_currency[cur] = CurrencyPendingSummary()

                summary = pending_by_currency[cur]
                summary.amount_minor += refund.amount_minor
                summary.count += 1

    return SystemMetricsSummary(
        pinned_now=PINNED_NOW_ISO,
        pending_payout=pending_by_currency,
    )


# ---------------------------------------------------------------------------
# Queue filters
# ---------------------------------------------------------------------------

def filter_finance_queue(
    order_states: list[OrderStateSummary],
) -> list[OrderStateSummary]:
    """
    Finance Outflow Queue: only orders with actionable pending refunds.

    Excludes orders where all refunds are succeeded/failed/rejected/approved.
    """
    results: list[OrderStateSummary] = []
    for oss in order_states:
        has_actionable = any(r.status == "pending" for r in oss.refunds)
        if has_actionable:
            results.append(oss)
    return results


def filter_support_queue(
    order_states: list[OrderStateSummary],
) -> list[OrderStateSummary]:
    """
    Support History Queue: orders with any refund activity in the past 7 days.

    Rule 13: An order qualifies if:
      - at least one refund/chargeback event occurred_at_utc >= SUPPORT_QUEUE_CUTOFF
      - and the order was placed recently OR has recent refund activity
    """
    cutoff = SUPPORT_QUEUE_CUTOFF_ISO

    results: list[OrderStateSummary] = []
    for oss in order_states:
        recent_refund_activity = any(
            e.occurred_at_utc >= cutoff
            and e.type in {"refund.requested", "refund.succeeded", "refund.failed", "chargeback.opened"}
            for e in oss.events
        )
        if not recent_refund_activity:
            continue
        if oss.order.placed_at_utc and oss.order.placed_at_utc >= cutoff:
            results.append(oss)
            continue
        if any(e.occurred_at_utc >= cutoff for e in oss.events):
            results.append(oss)

    return results
