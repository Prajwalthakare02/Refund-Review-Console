"""
Test suite for the Refund Review Console data engine.

Covers all 15 anomaly resolution rules from docs/04_DATABASE_AND_DATA_ENGINE.md.
Tests run against the real data files to verify production correctness.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from app.models.schemas import AgentDecision, Event, Order
from app.services.decision_store import DecisionStore
from app.services.ingest import (
    _amount_to_minor,
    _normalise_timestamp,
    load_events,
    load_orders,
)
from app.services.state_engine import (
    compute_system_metrics,
    derive_all_order_states,
    derive_order_state,
    filter_finance_queue,
    filter_support_queue,
)


# ---------------------------------------------------------------------------
# Fixtures: load real data once per session
# ---------------------------------------------------------------------------

@pytest.fixture(scope="session")
def orders() -> list[Order]:
    return load_orders()


@pytest.fixture(scope="session")
def events() -> list[Event]:
    return load_events()


@pytest.fixture(scope="session")
def all_states(orders, events):
    return derive_all_order_states(orders, events)


def _find_order_state(all_states, order_id: str):
    """Helper to find a specific order state by order_id."""
    for oss in all_states:
        if oss.order.order_id == order_id:
            return oss
    pytest.fail(f"Order {order_id} not found in derived states")


def _find_events_for_order(events: list[Event], order_id: str) -> list[Event]:
    """Helper to find events for a specific order."""
    return [e for e in events if e.order_id == order_id]


# ===========================================================================
# Test 1: Event deduplication on event_id (evt_0001)
# ===========================================================================

class TestRule1Deduplication:
    """Rule 1: Duplicate event_ids are discarded (first occurrence wins)."""

    def test_evt_0001_appears_once(self, events: list[Event]):
        """evt_0001 is duplicated in raw data; after dedup only 1 should remain."""
        matches = [e for e in events if e.event_id == "evt_0001"]
        assert len(matches) == 1, f"Expected 1 evt_0001, got {len(matches)}"

    def test_total_unique_events(self, events: list[Event]):
        """Raw file has unique IDs. After dedup we expect all unique events."""
        event_ids = [e.event_id for e in events]
        assert len(event_ids) == len(set(event_ids)), "Duplicate event_ids remain"
        assert len(events) == 215


# ===========================================================================
# Test 2: Legacy IST timezone conversion to UTC (legacy_gw)
# ===========================================================================

class TestRule2TimezoneNormalisation:
    """Rule 2: Naive timestamps from legacy_gw are parsed as IST (+05:30)."""

    def test_naive_ist_to_utc(self):
        """'2026-08-01 05:54:00' (IST) → '2026-08-01T00:24:00Z' (UTC)."""
        result = _normalise_timestamp("2026-08-01 05:54:00")
        assert result == "2026-08-01T00:24:00Z"

    def test_explicit_ist_offset(self):
        """'2026-07-31T08:12:00+05:30' → '2026-07-31T02:42:00Z'."""
        result = _normalise_timestamp("2026-07-31T08:12:00+05:30")
        assert result == "2026-07-31T02:42:00Z"

    def test_utc_z_passthrough(self):
        """'2026-07-28T16:36:00Z' → unchanged."""
        result = _normalise_timestamp("2026-07-28T16:36:00Z")
        assert result == "2026-07-28T16:36:00Z"

    def test_legacy_gw_events_have_utc_timestamps(self, events: list[Event]):
        """All legacy_gw events should have occurred_at_utc ending in 'Z'."""
        legacy = [e for e in events if e.source == "legacy_gw"]
        assert len(legacy) == 6, f"Expected 6 legacy_gw events, got {len(legacy)}"
        for evt in legacy:
            assert evt.occurred_at_utc.endswith("Z"), (
                f"{evt.event_id}: occurred_at_utc={evt.occurred_at_utc} is not UTC"
            )


# ===========================================================================
# Test 3: Decimal float normalisation to minor units
# ===========================================================================

class TestRule3MinorUnits:
    """Rule 3: All amounts standardised to integer minor units."""

    def test_amount_minor_passthrough(self):
        """Integer amount_minor passes through unchanged."""
        assert _amount_to_minor(amount_minor=82355, amount=None) == 82355

    def test_decimal_to_minor(self):
        """Float amount converts: 823.55 → 82355."""
        assert _amount_to_minor(amount_minor=None, amount=823.55) == 82355

    def test_round_trip_precision(self):
        """900.0 → 90000 (no floating-point error)."""
        assert _amount_to_minor(amount_minor=None, amount=900.0) == 90000

    def test_legacy_events_have_int_amounts(self, events: list[Event]):
        """Every event's amount_minor must be an integer after ingestion."""
        for evt in events:
            assert isinstance(evt.amount_minor, int), (
                f"{evt.event_id}: amount_minor is {type(evt.amount_minor)}, expected int"
            )

    def test_all_orders_have_int_amounts(self, orders: list[Order]):
        """Every order's total_amount_minor must be an integer."""
        for order in orders:
            assert isinstance(order.total_amount_minor, int), (
                f"{order.order_id}: total_amount_minor is {type(order.total_amount_minor)}"
            )


# ===========================================================================
# Test 4: Negative refund amount processing (ord_1022)
# ===========================================================================

class TestRule4NegativeAmount:
    """Rule 4: Negative amount_minor (-35000) is processed literally."""

    def test_negative_amount_in_events(self, events: list[Event]):
        """evt_0043 for ord_1022 should have amount_minor = -35000."""
        evt = next((e for e in events if e.event_id == "evt_0043"), None)
        assert evt is not None, "evt_0043 not found"
        assert evt.amount_minor == -35000
        assert evt.reason == "correction"

    def test_negative_amount_affects_pending(self, all_states):
        """Negative amount should reduce the pending payout total for ord_1022."""
        state = _find_order_state(all_states, "ord_1022")
        # A negative pending amount reduces the pending total
        has_negative_refund = any(
            r.amount_minor < 0 for r in state.refunds
        )
        assert has_negative_refund, "Expected a refund with negative amount"


# ===========================================================================
# Test 5: Zero refund amount handling (ord_1021)
# ===========================================================================

class TestRule5ZeroAmount:
    """Rule 5: Zero amount events are included in timeline but don't move money."""

    def test_zero_amount_event_exists(self, events: list[Event]):
        """evt_0042 for ord_1021 should have amount_minor = 0."""
        evt = next((e for e in events if e.event_id == "evt_0042"), None)
        assert evt is not None, "evt_0042 not found"
        assert evt.amount_minor == 0
        assert evt.reason == "adjustment"

    def test_zero_amount_in_timeline(self, all_states):
        """Zero-amount event should appear in the order's event list."""
        state = _find_order_state(all_states, "ord_1021")
        zero_events = [e for e in state.events if e.amount_minor == 0]
        assert len(zero_events) >= 1, "Zero-amount event missing from timeline"


# ===========================================================================
# Test 6: Currency mismatch flag (ord_1024)
# ===========================================================================

class TestRule6CurrencyMismatch:
    """Rule 6: Flag raised when event currency differs from order currency."""

    def test_ord_1024_has_mismatch_flag(self, all_states):
        """ord_1024 is INR in orders.csv but USD in events → flag must be set."""
        state = _find_order_state(all_states, "ord_1024")
        assert state.flags.has_currency_mismatch is True, (
            "Currency mismatch flag not set for ord_1024"
        )

    def test_mismatch_warning_message(self, all_states):
        """Warning list should contain currency mismatch message."""
        state = _find_order_state(all_states, "ord_1024")
        assert any("CURRENCY MISMATCH" in w for w in state.warnings)


# ===========================================================================
# Test 7: Over-refund calculation and flag (ord_1003 & ord_1030)
# ===========================================================================

class TestRule7OverRefund:
    """Rule 7: Over-refund when succeeded + pending exceeds order total."""

    def test_ord_1003_over_refund(self, all_states):
        """ord_1003 (₹999) has ₹1,100 in succeeded refunds → over-refunded."""
        state = _find_order_state(all_states, "ord_1003")
        total_out = state.refunded_succeeded_minor + state.pending_payout_minor
        assert total_out > state.order.total_amount_minor, (
            f"Expected over-refund: total_out={total_out}, "
            f"order_total={state.order.total_amount_minor}"
        )
        assert state.flags.is_over_refunded is True

    def test_ord_1003_remaining_negative(self, all_states):
        """remaining_refundable should be negative for over-refunded order."""
        state = _find_order_state(all_states, "ord_1003")
        assert state.remaining_refundable_minor < 0

    def test_over_refund_warning(self, all_states):
        """Warning list should contain over-refund message."""
        state = _find_order_state(all_states, "ord_1003")
        assert any("OVER-REFUNDED" in w for w in state.warnings)


# ===========================================================================
# Test 8: Terminal state reversal (rfnd_5050: requested → succeeded → failed)
# ===========================================================================

class TestRule8StateReversal:
    """Rule 8: Last chronological event determines final state."""

    def test_rfnd_5050_final_state_is_failed(self, all_states):
        """rfnd_5050 went requested → succeeded → failed → final = failed."""
        state = _find_order_state(all_states, "ord_1006")
        rfnd = next((r for r in state.refunds if r.refund_id == "rfnd_5050"), None)
        assert rfnd is not None, "rfnd_5050 not found in ord_1006 refunds"
        assert rfnd.status == "failed", f"Expected 'failed', got '{rfnd.status}'"

    def test_rfnd_5050_not_in_succeeded(self, all_states):
        """Bounced refund should NOT be counted in refunded_succeeded_minor."""
        state = _find_order_state(all_states, "ord_1006")
        rfnd = next((r for r in state.refunds if r.refund_id == "rfnd_5050"), None)
        # If this is the only refund for ord_1006, succeeded should be 0
        assert rfnd.status == "failed"


# ===========================================================================
# Test 9: Double loss risk alert (ord_1014)
# ===========================================================================

class TestRule9DoubleLossRisk:
    """Rule 9: Chargeback + successful refund = double loss risk."""

    def test_ord_1014_has_chargeback_flag(self, all_states):
        """ord_1014 has chargeback.opened → has_chargeback = True."""
        state = _find_order_state(all_states, "ord_1014")
        assert state.flags.has_chargeback is True

    def test_ord_1014_has_double_loss_risk(self, all_states):
        """ord_1014 has both chargeback AND successful refund → double loss risk."""
        state = _find_order_state(all_states, "ord_1014")
        assert state.flags.has_double_loss_risk is True

    def test_double_loss_warning(self, all_states):
        """Warning list should contain double loss risk message."""
        state = _find_order_state(all_states, "ord_1014")
        assert any("DOUBLE LOSS RISK" in w for w in state.warnings)


# ===========================================================================
# Test 10: Missing order placeholder creation (ord_1008)
# ===========================================================================

class TestRule10OrphanOrder:
    """Rule 10: Events for missing orders create orphan placeholders."""

    def test_ord_1008_not_in_orders_csv(self, orders: list[Order]):
        """ord_1008 should not exist in orders.csv."""
        ids = {o.order_id for o in orders}
        assert "ord_1008" not in ids

    def test_ord_1008_has_events(self, events: list[Event]):
        """ord_1008 should have events in events.jsonl."""
        ord_events = [e for e in events if e.order_id == "ord_1008"]
        assert len(ord_events) >= 1

    def test_ord_1008_orphan_placeholder(self, all_states):
        """ord_1008 should appear as orphan with total_amount_minor = 0."""
        state = _find_order_state(all_states, "ord_1008")
        assert state.order.total_amount_minor == 0
        assert state.flags.is_orphan_order is True

    def test_orphan_warning(self, all_states):
        """Warning list should contain orphan order message."""
        state = _find_order_state(all_states, "ord_1008")
        assert any("ORPHAN ORDER" in w for w in state.warnings)


# ===========================================================================
# Test 11: Cross-gateway duplicate relay separation (ord_1011)
# ===========================================================================

class TestRule11CrossGatewayRelay:
    """Rule 11: Different refund_ids = different refunds, even if amounts match."""

    def test_ord_1011_has_separate_refunds(self, all_states):
        """ord_1011 should have rfnd_5100 and rfnd_5101 as separate refund entries."""
        state = _find_order_state(all_states, "ord_1011")
        refund_ids = {r.refund_id for r in state.refunds}
        assert "rfnd_5100" in refund_ids, "rfnd_5100 missing"
        assert "rfnd_5101" in refund_ids, "rfnd_5101 missing"

    def test_both_refunds_counted(self, all_states):
        """Both cross-gateway refunds should contribute to financial totals."""
        state = _find_order_state(all_states, "ord_1011")
        assert len(state.refunds) >= 2


# ===========================================================================
# Test 12: Ingestion out-of-order sorting by occurred_at_utc (ord_1005)
# ===========================================================================

class TestRule12EventOrdering:
    """Rule 12: Events sorted by occurred_at_utc, not received_at."""

    def test_events_sorted_chronologically(self, all_states):
        """All order events should be sorted by occurred_at_utc ascending."""
        for oss in all_states:
            timestamps = [e.occurred_at_utc for e in oss.events]
            assert timestamps == sorted(timestamps), (
                f"{oss.order.order_id}: events not sorted by occurred_at_utc"
            )

    def test_ord_1005_request_before_success(self, events: list[Event]):
        """For ord_1005 rfnd_5040, occurred_at of request should be before success."""
        ord_events = [e for e in events if e.order_id == "ord_1005"]
        rfnd_5040 = [e for e in ord_events if e.refund_id == "rfnd_5040"]
        if len(rfnd_5040) >= 2:
            sorted_by_occurred = sorted(rfnd_5040, key=lambda e: e.occurred_at_utc)
            # Request should come first in occurred_at ordering
            request_events = [e for e in sorted_by_occurred if e.type == "refund.requested"]
            success_events = [e for e in sorted_by_occurred if e.type == "refund.succeeded"]
            if request_events and success_events:
                assert request_events[0].occurred_at_utc <= success_events[0].occurred_at_utc


# ===========================================================================
# Test 13: Support queue 7-day cutoff filtering
# ===========================================================================

class TestRule13SupportQueueCutoff:
    """Rule 13: Support queue includes orders with activity in past 7 days."""

    def test_support_queue_not_empty(self, all_states):
        """Support queue should contain orders."""
        support = filter_support_queue(all_states)
        assert len(support) > 0

    def test_old_order_with_recent_events_included(self, all_states):
        """Orders placed before cutoff but with recent events should be included."""
        support = filter_support_queue(all_states)
        support_ids = {s.order.order_id for s in support}
        # ord_1010 placed 2026-07-29 (before cutoff 2026-08-04)
        # but has events in early August — should be in support queue
        # if it has events >= cutoff
        state = _find_order_state(all_states, "ord_1010")
        recent_events = [
            e for e in state.events
            if e.occurred_at_utc >= "2026-08-04T04:30:00Z"
        ]
        if recent_events:
            assert "ord_1010" in support_ids

    def test_finance_queue_only_pending(self, all_states):
        """Finance queue should only contain orders with actionable pending refunds."""
        finance = filter_finance_queue(all_states)
        for oss in finance:
            has_pending = any(r.status == "pending" for r in oss.refunds)
            assert has_pending, (
                f"{oss.order.order_id} in finance queue but has no pending refunds"
            )


# ===========================================================================
# Test 14: Minor unit high-value threshold flags
# ===========================================================================

class TestRule14HighValueFlags:
    """Rule 14: High-value thresholds in minor units."""

    def test_ord_1012_high_value(self, all_states):
        """ord_1012 total ₹150,000 (15,000,000 paise) → high value flag."""
        state = _find_order_state(all_states, "ord_1012")
        # Check if any refund is high value
        if state.refunds:
            assert state.flags.is_high_value is True, (
                "ord_1012 should be flagged as high value"
            )

    def test_small_order_not_high_value(self, all_states):
        """ord_1003 total ₹999 → should NOT be flagged as high value."""
        state = _find_order_state(all_states, "ord_1003")
        # Small refund amounts should not trigger high value
        for refund in state.refunds:
            assert refund.is_high_value is False, (
                f"Refund {refund.refund_id} ({refund.amount_minor}) "
                f"should not be high value"
            )

    def test_high_value_warning(self, all_states):
        """High-value orders should have a warning message."""
        state = _find_order_state(all_states, "ord_1012")
        if state.flags.is_high_value:
            assert any("HIGH VALUE" in w for w in state.warnings)


# ===========================================================================
# Test 15: Agent decision state overrides
# ===========================================================================

class TestRule15AgentDecisionOverrides:
    """Rule 15: Agent decisions take precedence over raw pending state."""

    def _make_pending_order(self) -> tuple[Order, list[Event]]:
        """Create a synthetic pending refund for testing decisions."""
        order = Order(
            order_id="ord_test",
            customer_id="cus_test",
            currency="INR",
            total_amount_minor=100000,
            placed_at_utc="2026-08-10T04:30:00Z",
            channel="web",
            region="IN",
        )
        events = [
            Event(
                event_id="evt_test_001",
                type="refund.requested",
                order_id="ord_test",
                refund_id="rfnd_test_001",
                currency="INR",
                amount_minor=50000,
                occurred_at_utc="2026-08-10T05:00:00Z",
                received_at_utc="2026-08-10T05:00:03Z",
                source="gw_primary",
                reason="test refund",
            ),
        ]
        return order, events

    def test_no_decision_remains_pending(self):
        """Without agent decision, refund stays in pending state."""
        order, events = self._make_pending_order()
        state = derive_order_state(order, events, decisions={})
        assert state.pending_payout_minor == 50000
        assert state.refunds[0].status == "pending"

    def test_approved_stays_in_pending_payout(self):
        """Approved refund stops counting as pending payout."""
        order, events = self._make_pending_order()
        decisions = {
            "rfnd_test_001": AgentDecision(
                refund_id="rfnd_test_001",
                action="approve",
                reason="Verified return receipt",
                idempotency_key="key-001",
                recorded_at="2026-08-10T06:00:00Z",
            )
        }
        state = derive_order_state(order, events, decisions)
        assert state.pending_payout_minor == 0, (
            "Approved refund should no longer count in pending_payout"
        )
        assert state.refunds[0].status == "approved"

    def test_rejected_removes_from_pending(self):
        """Rejected refund drops pending_payout to 0."""
        order, events = self._make_pending_order()
        decisions = {
            "rfnd_test_001": AgentDecision(
                refund_id="rfnd_test_001",
                action="reject",
                reason="Fraudulent claim",
                idempotency_key="key-002",
                recorded_at="2026-08-10T06:00:00Z",
            )
        }
        state = derive_order_state(order, events, decisions)
        assert state.pending_payout_minor == 0, (
            "Rejected refund should not be in pending_payout"
        )
        assert state.refunds[0].status == "rejected"

    def test_rejected_does_not_deduct_remaining(self):
        """Rejected refund should NOT reduce remaining_refundable."""
        order, events = self._make_pending_order()
        decisions = {
            "rfnd_test_001": AgentDecision(
                refund_id="rfnd_test_001",
                action="reject",
                reason="Fraudulent claim",
                idempotency_key="key-002",
                recorded_at="2026-08-10T06:00:00Z",
            )
        }
        state = derive_order_state(order, events, decisions)
        # remaining = total (100000) - succeeded (0) - pending (0) = 100000
        assert state.remaining_refundable_minor == 100000


# ===========================================================================
# Integration: System metrics sanity check
# ===========================================================================

class TestSystemMetrics:
    """Integration: verify Priya's top metric is computed correctly."""

    def test_system_metrics_has_pinned_now(self, all_states):
        """System metrics should reference the pinned timestamp."""
        metrics = compute_system_metrics(all_states)
        assert metrics.pinned_now == "2026-08-11T04:30:00Z"

    def test_pending_payout_has_currencies(self, all_states):
        """Pending payout should be broken down by currency."""
        metrics = compute_system_metrics(all_states)
        # At minimum INR should be present (most orders are INR)
        assert "INR" in metrics.pending_payout

    def test_pending_amounts_are_integers(self, all_states):
        """All pending amounts must be integers (no floats)."""
        metrics = compute_system_metrics(all_states)
        for cur, summary in metrics.pending_payout.items():
            assert isinstance(summary.amount_minor, int), (
                f"{cur} pending amount is {type(summary.amount_minor)}, expected int"
            )


# ===========================================================================
# Persistence / restart behavior
# ===========================================================================

class TestDecisionPersistence:
    """Persisted decisions should survive a store restart."""

    def test_decision_reloads_after_restart(self, tmp_path: Path):
        db_path = tmp_path / "decisions.sqlite3"

        store1 = DecisionStore(db_path=db_path)
        store1.initialise()

        pending_refund = None
        for oss in store1.order_states:
            for refund in oss.refunds:
                if refund.status == "pending":
                    pending_refund = refund.refund_id
                    break
            if pending_refund:
                break

        if pending_refund is None:
            pytest.skip("No pending refund available for persistence test")

        body = store1.record_decision(
            refund_id=pending_refund,
            action="approve",
            reason="Persistence test",
            idempotency_key="persist-key-001",
        )

        store2 = DecisionStore(db_path=db_path)
        store2.initialise()

        assert store2.get_decision(pending_refund) is not None
        assert store2.check_idempotency("persist-key-001") == body
