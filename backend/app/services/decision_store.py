"""
In-memory decision store and application state manager.

Holds:
  - Parsed orders and events (loaded once at startup).
  - Derived order states (recomputed when decisions mutate state).
  - Agent decisions keyed by refund_id.
  - Idempotency cache keyed by idempotency_key.
"""

from __future__ import annotations

from typing import Any, Optional

from app.config import PINNED_NOW_ISO
from app.models.schemas import (
    AgentDecision,
    Event,
    Order,
    OrderStateSummary,
)
from app.services.ingest import load_events, load_orders
from app.services.state_engine import (
    compute_system_metrics,
    derive_all_order_states,
    filter_finance_queue,
    filter_support_queue,
)


class DecisionStore:
    """
    Singleton-style in-memory store for the refund console.

    Thread-safety note: this is a single-worker dev application.
    For production, decisions would go into a database with row-level locking.
    """

    def __init__(self) -> None:
        self._orders: list[Order] = []
        self._events: list[Event] = []
        self._decisions: dict[str, AgentDecision] = {}
        self._idempotency_cache: dict[str, dict[str, Any]] = {}
        self._order_states: list[OrderStateSummary] = []
        self._initialised = False

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def initialise(self) -> None:
        """Load data files and derive initial state. Call once at startup."""
        self._orders = load_orders()
        self._events = load_events()
        self._rebuild_states()
        self._initialised = True

    def _rebuild_states(self) -> None:
        """Re-derive all order states from scratch using current decisions."""
        self._order_states = derive_all_order_states(
            self._orders, self._events, self._decisions
        )

    # ------------------------------------------------------------------
    # Read operations
    # ------------------------------------------------------------------

    @property
    def order_states(self) -> list[OrderStateSummary]:
        return self._order_states

    def get_order_state(self, order_id: str) -> Optional[OrderStateSummary]:
        """Look up a single order by ID."""
        for oss in self._order_states:
            if oss.order.order_id == order_id:
                return oss
        return None

    def get_system_metrics(self):
        """Compute Priya's top metric from current state."""
        return compute_system_metrics(self._order_states)

    def get_finance_queue(self) -> list[OrderStateSummary]:
        """Orders with actionable pending refunds."""
        return filter_finance_queue(self._order_states)

    def get_support_queue(self) -> list[OrderStateSummary]:
        """Orders with activity in past 7 days."""
        return filter_support_queue(self._order_states)

    # ------------------------------------------------------------------
    # Write operations (decisions)
    # ------------------------------------------------------------------

    def check_idempotency(self, key: str) -> Optional[dict[str, Any]]:
        """Return cached response if this idempotency_key was already processed."""
        return self._idempotency_cache.get(key)

    def record_decision(
        self,
        refund_id: str,
        action: str,
        reason: str,
        idempotency_key: str,
    ) -> dict[str, Any]:
        """
        Record an agent decision and re-derive affected order state.

        Returns the response payload (also cached for idempotency).
        """
        decision = AgentDecision(
            refund_id=refund_id,
            action=action,
            reason=reason,
            idempotency_key=idempotency_key,
            recorded_at=PINNED_NOW_ISO,
        )

        # Store decision
        self._decisions[refund_id] = decision

        # Re-derive all states with updated decisions
        self._rebuild_states()

        # Build response payload
        response = {
            "success": True,
            "refund_id": refund_id,
            "new_status": "approved" if action in ("approve", "approved") else "rejected",
            "recorded_at": PINNED_NOW_ISO,
            "idempotency_key": idempotency_key,
        }

        # Cache for idempotency
        self._idempotency_cache[idempotency_key] = response

        return response

    def get_decision(self, refund_id: str) -> Optional[AgentDecision]:
        """Look up decision for a specific refund_id."""
        return self._decisions.get(refund_id)


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------
store = DecisionStore()
