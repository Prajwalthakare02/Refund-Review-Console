from typing import Optional, List
from datetime import datetime
from pydantic import BaseModel, Field

class OrderSchema(BaseModel):
    order_id: str
    customer_id: str
    currency: str
    total_amount_minor: Optional[int] = None
    placed_at: Optional[datetime] = None
    channel: str
    region: str
    is_orphan: bool = False  # True if missing from orders.csv but present in events

class PaymentEventSchema(BaseModel):
    event_id: str
    type: str  # refund.requested, refund.succeeded, refund.failed, chargeback.opened
    order_id: str
    refund_id: Optional[str] = None
    currency: str
    occurred_at: datetime
    received_at: datetime
    source: str
    amount_minor: int
    reason: Optional[str] = None
    failure_code: Optional[str] = None
    requested_by: Optional[str] = None
    network_case_id: Optional[str] = None

class RefundItemState(BaseModel):
    refund_id: str
    current_status: str  # pending, succeeded, failed, approved, rejected
    amount_minor: int
    currency: str
    reason: Optional[str] = None
    failure_code: Optional[str] = None
    is_high_value: bool = False
    events: List[PaymentEventSchema] = []
    agent_decision: Optional[str] = None
    decision_reason: Optional[str] = None

class DerivedOrderStateSchema(BaseModel):
    order: OrderSchema
    total_paid_minor: int
    refunded_succeeded_minor: int
    pending_payout_minor: int
    remaining_refundable_minor: int
    currency: str
    has_high_value: bool = False
    is_over_refunded: bool = False
    has_chargeback: bool = False
    has_currency_mismatch: bool = False
    is_orphan: bool = False
    refund_items: List[RefundItemState] = []
    chargeback_events: List[PaymentEventSchema] = []

class MetricSummarySchema(BaseModel):
    total_pending_payout_minor: dict  # {"INR": 12345, "USD": 6789}
    pending_orders_count: int
    high_value_pending_count: int
