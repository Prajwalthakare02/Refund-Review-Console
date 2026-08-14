from typing import Optional, List
from fastapi import APIRouter, HTTPException, Query
from app.models.schemas import DerivedOrderStateSchema

router = APIRouter(prefix="/api/orders", tags=["queue"])

state_engine_ref = None

def set_state_engine(engine):
    global state_engine_ref
    state_engine_ref = engine

@router.get("", response_model=List[DerivedOrderStateSchema])
def get_orders(
    view: str = Query("finance", description="View mode: 'finance' (outflow control) or 'support' (7-day history)"),
    search: Optional[str] = Query(None, description="Search by order_id, customer_id, or refund_id"),
    currency: Optional[str] = Query(None, description="Filter by currency (INR, USD)"),
    high_value_only: bool = Query(False, description="Filter high value refunds only")
):
    states_dict = state_engine_ref.derive_all_orders()
    results = []

    for state in states_dict.values():
        # View Filtering Rule
        if view == "finance":
            # Finance Queue: Only show orders where money can move (pending payout > 0 or has active pending item)
            if state.pending_payout_minor <= 0:
                continue
        elif view == "support":
            # Support View: Show all orders with refund activity in past 7 days or any refund item
            if not state.refund_items and not state.chargeback_events:
                continue

        # Currency Filter
        if currency and state.currency != currency:
            continue

        # High Value Filter
        if high_value_only and not state.has_high_value:
            continue

        # Search Filter (order_id, customer_id, or refund_ids)
        if search:
            query = search.strip().lower()
            match_order = query in state.order.order_id.lower()
            match_customer = query in state.order.customer_id.lower()
            match_refund = any(query in r.refund_id.lower() for r in state.refund_items)
            if not (match_order or match_customer or match_refund):
                continue

        results.append(state)

    # Sort: High value pending refunds first, then by order_id
    results.sort(key=lambda s: (not s.has_high_value, -s.pending_payout_minor, s.order.order_id))
    return results

@router.get("/{order_id}", response_model=DerivedOrderStateSchema)
def get_order_detail(order_id: str):
    states_dict = state_engine_ref.derive_all_orders()
    if order_id not in states_dict:
        raise HTTPException(status_code=404, detail=f"Order '{order_id}' not found.")
    return states_dict[order_id]
