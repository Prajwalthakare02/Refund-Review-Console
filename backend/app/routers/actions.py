"""
Actions router — agent approve / reject decisions.

POST /api/refunds/{refund_id}/decision
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.services.decision_store import store

router = APIRouter(prefix="/api/refunds", tags=["actions"])


class DecisionRequest(BaseModel):
    """Request body for recording an agent decision."""
    action: str        # "approve" | "reject"
    reason: str
    idempotency_key: str


@router.post("/{refund_id}/decision")
def record_decision(refund_id: str, body: DecisionRequest):
    """
    Record an agent approval or rejection for a pending refund.

    Idempotency: If the same idempotency_key has been seen before,
    return the cached response without mutating state.
    """
    # Validate action
    if body.action not in ("approve", "reject"):
        raise HTTPException(
            status_code=422,
            detail=f"Invalid action '{body.action}'. Must be 'approve' or 'reject'.",
        )

    # Validate reason is not empty
    if not body.reason.strip():
        raise HTTPException(
            status_code=422,
            detail="Reason is required and cannot be empty.",
        )

    # Idempotency check — return cached response if key already processed
    cached = store.check_idempotency(body.idempotency_key)
    if cached is not None:
        return cached

    # Verify refund_id exists in current state
    found = False
    for oss in store.order_states:
        for refund in oss.refunds:
            if refund.refund_id == refund_id:
                found = True
                break
        if found:
            break

    if not found:
        raise HTTPException(
            status_code=404,
            detail=f"Refund {refund_id} not found.",
        )

    # Record decision and get response
    response = store.record_decision(
        refund_id=refund_id,
        action=body.action,
        reason=body.reason.strip(),
        idempotency_key=body.idempotency_key,
    )

    return response
