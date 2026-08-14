from typing import Dict, List, Optional
from collections import defaultdict

from app.models.schemas import (
    OrderSchema, PaymentEventSchema, RefundItemState,
    DerivedOrderStateSchema, MetricSummarySchema
)
from app.config import HIGH_VALUE_THRESHOLDS_MINOR

class StateEngine:
    def __init__(self, orders: Dict[str, OrderSchema], events: List[PaymentEventSchema]):
        self.orders = orders
        self.events = events
        self.decisions: Dict[str, dict] = {}  # refund_id -> {"action": "approve"|"reject", "reason": str}
        self.idempotency_keys: set = set()

    def record_decision(self, refund_id: str, action: str, reason: str, idempotency_key: str) -> bool:
        """Records an agent decision with double-click idempotency protection."""
        if idempotency_key in self.idempotency_keys:
            return False  # Already processed
        self.idempotency_keys.add(idempotency_key)
        self.decisions[refund_id] = {
            "action": action,
            "reason": reason
        }
        return True

    def derive_all_orders(self) -> Dict[str, DerivedOrderStateSchema]:
        """Derives truthful refund states for all orders."""
        # 1. Group events by order_id
        events_by_order: Dict[str, List[PaymentEventSchema]] = defaultdict(list)
        for evt in self.events:
            events_by_order[evt.order_id].append(evt)

        # 2. Collect all order IDs (from orders.csv and orphan orders in events.jsonl)
        all_order_ids = set(self.orders.keys()).union(set(events_by_order.keys()))
        derived_states: Dict[str, DerivedOrderStateSchema] = {}

        for order_id in sorted(all_order_ids):
            order = self.orders.get(order_id)
            is_orphan = False

            if not order:
                # Anomaly: Missing order (e.g. ord_1008 in events but not in orders.csv)
                is_orphan = True
                order_events = events_by_order[order_id]
                first_evt_curr = order_events[0].currency if order_events else "INR"
                order = OrderSchema(
                    order_id=order_id,
                    customer_id="unknown",
                    currency=first_evt_curr,
                    total_amount_minor=0,
                    placed_at=None,
                    channel="unknown",
                    region="IN",
                    is_orphan=True
                )

            order_events = sorted(events_by_order.get(order_id, []), key=lambda e: e.occurred_at)
            derived_state = self._derive_order_state(order, order_events)
            derived_states[order_id] = derived_state

        return derived_states

    def _derive_order_state(self, order: OrderSchema, events: List[PaymentEventSchema]) -> DerivedOrderStateSchema:
        refund_events_by_id: Dict[str, List[PaymentEventSchema]] = defaultdict(list)
        chargeback_events: List[PaymentEventSchema] = []
        has_currency_mismatch = False

        for evt in events:
            if evt.currency != order.currency:
                has_currency_mismatch = True
            if evt.type == "chargeback.opened":
                chargeback_events.append(evt)
            elif evt.refund_id:
                refund_events_by_id[evt.refund_id].append(evt)

        refund_items: List[RefundItemState] = []
        refunded_succeeded_minor = 0
        pending_payout_minor = 0
        has_high_value = False

        for refund_id, r_events in refund_events_by_id.items():
            r_events_sorted = sorted(r_events, key=lambda e: e.occurred_at)
            latest_evt = r_events_sorted[-1]
            
            # Non-zero latest event with amount
            amount_minor = 0
            for e in reversed(r_events_sorted):
                if e.amount_minor != 0:
                    amount_minor = e.amount_minor
                    break

            currency = latest_evt.currency
            reason = next((e.reason for e in r_events_sorted if e.reason), None)
            failure_code = next((e.failure_code for e in r_events_sorted if e.failure_code), None)
            
            threshold = HIGH_VALUE_THRESHOLDS_MINOR.get(currency, 5000000)
            is_high_value = amount_minor >= threshold
            if is_high_value:
                has_high_value = True

            # Terminal state derivation logic
            current_status = "pending"
            agent_decision_info = self.decisions.get(refund_id)
            agent_decision = agent_decision_info["action"] if agent_decision_info else None
            decision_reason = agent_decision_info["reason"] if agent_decision_info else None

            # Calculate state based on event stream & agent decision
            final_event_type = latest_evt.type

            if final_event_type == "refund.succeeded":
                current_status = "succeeded"
                refunded_succeeded_minor += amount_minor
            elif final_event_type == "refund.failed":
                current_status = "failed"
            elif agent_decision == "rejected":
                current_status = "rejected"
            elif agent_decision == "approve":
                current_status = "approved"
                pending_payout_minor += amount_minor
            elif final_event_type == "refund.requested":
                current_status = "pending"
                pending_payout_minor += amount_minor

            item = RefundItemState(
                refund_id=refund_id,
                current_status=current_status,
                amount_minor=amount_minor,
                currency=currency,
                reason=reason,
                failure_code=failure_code,
                is_high_value=is_high_value,
                events=r_events_sorted,
                agent_decision=agent_decision,
                decision_reason=decision_reason
            )
            refund_items.append(item)

        total_paid_minor = order.total_amount_minor or 0
        remaining_refundable_minor = total_paid_minor - refunded_succeeded_minor - pending_payout_minor
        is_over_refunded = (refunded_succeeded_minor + pending_payout_minor) > total_paid_minor and total_paid_minor > 0
        has_chargeback = len(chargeback_events) > 0

        return DerivedOrderStateSchema(
            order=order,
            total_paid_minor=total_paid_minor,
            refunded_succeeded_minor=refunded_succeeded_minor,
            pending_payout_minor=pending_payout_minor,
            remaining_refundable_minor=remaining_refundable_minor,
            currency=order.currency,
            has_high_value=has_high_value,
            is_over_refunded=is_over_refunded,
            has_chargeback=has_chargeback,
            has_currency_mismatch=has_currency_mismatch,
            is_orphan=order.is_orphan,
            refund_items=refund_items,
            chargeback_events=chargeback_events
        )

    def calculate_metrics(self) -> MetricSummarySchema:
        """Priya's metric: Total Pending Payout across all active currencies right now."""
        states = self.derive_all_orders()
        pending_by_curr = defaultdict(int)
        pending_orders = 0
        high_value_pending = 0

        for state in states.values():
            if state.pending_payout_minor > 0:
                pending_orders += 1
                for item in state.refund_items:
                    if item.current_status in ("pending", "approved"):
                        pending_by_curr[item.currency] += item.amount_minor
                        if item.is_high_value:
                            high_value_pending += 1

        return MetricSummarySchema(
            total_pending_payout_minor=dict(pending_by_curr),
            pending_orders_count=pending_orders,
            high_value_pending_count=high_value_pending
        )
