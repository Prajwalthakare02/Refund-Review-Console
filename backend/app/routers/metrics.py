"""
Metrics router — Priya's top summary number.

GET /api/metrics/summary
"""

from fastapi import APIRouter

from app.config import PINNED_NOW_IST
from app.services.decision_store import store

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


def _format_amount(amount_minor: int, currency: str) -> str:
    """Format minor units to human-readable currency string."""
    major = amount_minor / 100
    if currency == "INR":
        return f"₹{major:,.2f}"
    elif currency == "USD":
        return f"${major:,.2f}"
    return f"{major:,.2f} {currency}"


@router.get("/summary")
def get_metrics_summary():
    """
    Return system-wide pending payout liability by currency.

    Response matches docs/03_SYSTEM_ARCHITECTURE.md API contract.
    """
    metrics = store.get_system_metrics()

    # Enrich with formatted display strings
    response = {
        "pinned_now": metrics.pinned_now,
        "pinned_now_ist": PINNED_NOW_IST.isoformat(),
        "pending_payout": {},
    }

    for currency, summary in metrics.pending_payout.items():
        response["pending_payout"][currency] = {
            "amount_minor": summary.amount_minor,
            "amount_formatted": _format_amount(summary.amount_minor, currency),
            "count": summary.count,
        }

    return response
