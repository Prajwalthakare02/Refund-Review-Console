from fastapi import APIRouter, HTTPException, Header
from pydantic import BaseModel, Field
from typing import Optional

router = APIRouter(prefix="/api/refunds", tags=["actions"])

state_engine_ref = None

def set_state_engine(engine):
    global state_engine_ref
    state_engine_ref = engine

class DecisionRequest(BaseModel):
    action: str = Field(..., description="'approve' or 'reject'")
    reason: str = Field(..., min_length=3, description="Mandatory decision reason")
    idempotency_key: str = Field(..., description="Unique UUID to prevent double-clicks")

@router.post("/{refund_id}/decision")
def record_refund_decision(refund_id: str, payload: DecisionRequest):
    """
    Records an agent approval/rejection decision.
    Includes double-click protection using idempotency_key.
    """
    action = payload.action.strip().lower()
    if action not in ("approve", "reject"):
        raise HTTPException(status_code=400, detail="Action must be 'approve' or 'reject'.")

    success = state_engine_ref.record_decision(
        refund_id=refund_id,
        action=action,
        reason=payload.reason.strip(),
        idempotency_key=payload.idempotency_key.strip()
    )

    if not success:
        # Idempotent return: already recorded without duplicate side-effects
        return {
            "status": "ignored_duplicate",
            "message": f"Decision for refund '{refund_id}' was already recorded (idempotent request).",
            "refund_id": refund_id,
            "action": action
        }

    return {
        "status": "success",
        "message": f"Refund '{refund_id}' successfully marked as '{action}'.",
        "refund_id": refund_id,
        "action": action,
        "reason": payload.reason
    }
