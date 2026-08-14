import pytest
from app.services.ingest import load_orders, load_events
from app.services.state_engine import StateEngine

@pytest.fixture
def engine():
    orders = load_orders()
    events, _ = load_events()
    return StateEngine(orders, events)

def test_derive_all_orders_count(engine):
    states = engine.derive_all_orders()
    # 154 orders in csv + 1 orphan order (ord_1008) = 155 total states
    assert len(states) == 155
    assert "ord_1008" in states
    assert states["ord_1008"].is_orphan is True

def test_priya_top_metric(engine):
    metrics = engine.calculate_metrics()
    assert "INR" in metrics.total_pending_payout_minor
    assert metrics.total_pending_payout_minor["INR"] > 0
    assert metrics.pending_orders_count > 0

def test_over_refunded_order(engine):
    states = engine.derive_all_orders()
    # ord_1003 has total 999.00 INR and refunds 500 + 600 = 1,100 INR
    state_1003 = states["ord_1003"]
    assert state_1003.refunded_succeeded_minor == 110000
    assert state_1003.is_over_refunded is True
    assert state_1003.remaining_refundable_minor == -10100

def test_chargeback_detection(engine):
    states = engine.derive_all_orders()
    # ord_1014 has a succeeded refund and an opened chargeback (CB-77401)
    state_1014 = states["ord_1014"]
    assert state_1014.has_chargeback is True
    assert len(state_1014.chargeback_events) == 1

def test_state_anomaly_bounced_refund(engine):
    states = engine.derive_all_orders()
    # ord_1006 rfnd_5050 went requested -> succeeded -> failed
    state_1006 = states["ord_1006"]
    rfnd_5050 = next((r for r in state_1006.refund_items if r.refund_id == "rfnd_5050"), None)
    assert rfnd_5050 is not None
    assert rfnd_5050.current_status == "failed"

def test_idempotency_double_click_protection(engine):
    refund_id = "rfnd_6116"
    key = "idemp_test_12345"
    
    # First attempt -> succeeds
    res1 = engine.record_decision(refund_id, "approve", "Valid reason", key)
    assert res1 is True
    
    # Duplicate second attempt -> fails (idempotent ignore)
    res2 = engine.record_decision(refund_id, "approve", "Valid reason", key)
    assert res2 is False
