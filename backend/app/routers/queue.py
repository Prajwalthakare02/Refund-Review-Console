"""
Queue router — order list and detail endpoints.

GET /api/orders         → Filterable paginated queue
GET /api/orders/{id}    → Single order detail with event timeline
"""

from fastapi import APIRouter, HTTPException, Query

from app.services.decision_store import store

router = APIRouter(prefix="/api/orders", tags=["orders"])


def _format_amount(amount_minor: int, currency: str) -> str:
    """Format minor units to human-readable currency string."""
    major = amount_minor / 100
    if currency == "INR":
        return f"₹{major:,.2f}"
    elif currency == "USD":
        return f"${major:,.2f}"
    return f"{major:,.2f} {currency}"


def _derive_order_status(oss) -> str:
    """Derive a single human-readable status string for queue display."""
    statuses = {r.status for r in oss.refunds}

    if "pending" in statuses:
        return "pending_approval"
    if statuses == {"approved"}:
        return "approved"
    if statuses == {"rejected"}:
        return "rejected"
    if "succeeded" in statuses and "failed" not in statuses:
        return "refunded"
    if "failed" in statuses and "succeeded" not in statuses:
        return "failed"
    if "succeeded" in statuses and "failed" in statuses:
        return "partially_refunded"
    return "no_refund_activity"


def _serialise_order_summary(oss) -> dict:
    """Serialise an OrderStateSummary to the queue list response shape."""
    cur = oss.order.currency
    return {
        "order_id": oss.order.order_id,
        "customer_id": oss.order.customer_id,
        "currency": cur,
        "total_paid_minor": oss.order.total_amount_minor,
        "total_paid_formatted": _format_amount(oss.order.total_amount_minor, cur),
        "refunded_succeeded_minor": oss.refunded_succeeded_minor,
        "refunded_succeeded_formatted": _format_amount(oss.refunded_succeeded_minor, cur),
        "pending_payout_minor": oss.pending_payout_minor,
        "pending_payout_formatted": _format_amount(oss.pending_payout_minor, cur),
        "remaining_refundable_minor": oss.remaining_refundable_minor,
        "status": _derive_order_status(oss),
        "placed_at": oss.order.placed_at_utc,
        "channel": oss.order.channel,
        "flags": oss.flags.model_dump(),
        "warning_count": len(oss.warnings),
    }


@router.get("")
def list_orders(
    view: str = Query("finance", pattern="^(finance|support)$"),
    search: str = Query("", description="Search by order_id or customer_id"),
    page: int = Query(1, ge=1),
    per_page: int = Query(50, ge=1, le=200),
):
    """
    Return paginated, filterable order queue.

    - view=finance: Only actionable orders with pending refunds.
    - view=support: All orders with refund activity in past 7 days.
    - search: Case-insensitive substring match on order_id or customer_id.
    """
    # Select queue based on view
    if view == "finance":
        queue = store.get_finance_queue()
    else:
        queue = store.get_support_queue()

    # Apply search filter
    if search:
        search_lower = search.lower()
        queue = [
            oss for oss in queue
            if search_lower in oss.order.order_id.lower()
            or search_lower in oss.order.customer_id.lower()
        ]

    # Pagination
    total = len(queue)
    start = (page - 1) * per_page
    end = start + per_page
    page_items = queue[start:end]

    return {
        "total": total,
        "page": page,
        "per_page": per_page,
        "orders": [_serialise_order_summary(oss) for oss in page_items],
    }


@router.get("/{order_id}")
def get_order_detail(order_id: str):
    """
    Return full order detail with chronological event timeline and warnings.
    """
    oss = store.get_order_state(order_id)
    if oss is None:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    # Serialise timeline events
    timeline = []
    for evt in oss.events:
        timeline.append({
            "event_id": evt.event_id,
            "type": evt.type,
            "refund_id": evt.refund_id,
            "currency": evt.currency,
            "amount_minor": evt.amount_minor,
            "amount_formatted": _format_amount(evt.amount_minor, evt.currency),
            "occurred_at_utc": evt.occurred_at_utc,
            "source": evt.source,
            "reason": evt.reason,
            "failure_code": evt.failure_code,
        })

    # Serialise refund breakdowns
    refunds = []
    for r in oss.refunds:
        refunds.append({
            "refund_id": r.refund_id,
            "currency": r.currency,
            "amount_minor": r.amount_minor,
            "amount_formatted": _format_amount(r.amount_minor, r.currency),
            "status": r.status,
            "reason": r.reason,
            "failure_code": r.failure_code,
            "is_high_value": r.is_high_value,
        })

    return {
        "order": {
            "order_id": oss.order.order_id,
            "customer_id": oss.order.customer_id,
            "currency": oss.order.currency,
            "total_paid_minor": oss.order.total_amount_minor,
            "total_paid_formatted": _format_amount(
                oss.order.total_amount_minor, oss.order.currency
            ),
            "placed_at": oss.order.placed_at_utc,
            "channel": oss.order.channel,
            "region": oss.order.region,
        },
        "refunded_succeeded_minor": oss.refunded_succeeded_minor,
        "pending_payout_minor": oss.pending_payout_minor,
        "remaining_refundable_minor": oss.remaining_refundable_minor,
        "chargeback_amount_minor": oss.chargeback_amount_minor,
        "flags": oss.flags.model_dump(),
        "refunds": refunds,
        "timeline": timeline,
        "warnings": oss.warnings,
    }
