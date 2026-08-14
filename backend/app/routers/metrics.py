from fastapi import APIRouter
from app.models.schemas import MetricSummarySchema

router = APIRouter(prefix="/api/metrics", tags=["metrics"])

# Global state_engine instance reference (initialized in main.py)
state_engine_ref = None

def set_state_engine(engine):
    global state_engine_ref
    state_engine_ref = engine

@router.get("/summary", response_model=MetricSummarySchema)
def get_metrics_summary():
    """
    Priya's Metric: Trustworthy total pending payout right now
    broken down by currency.
    """
    return state_engine_ref.calculate_metrics()
