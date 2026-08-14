import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c

def test_health_check(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"

def test_get_metrics_summary_api(client):
    response = client.get("/api/metrics/summary")
    assert response.status_code == 200
    data = response.json()
    assert "total_pending_payout_minor" in data
    assert "INR" in data["total_pending_payout_minor"]

def test_get_orders_finance_queue_api(client):
    response = client.get("/api/orders?view=finance")
    assert response.status_code == 200
    orders = response.json()
    assert len(orders) > 0
    # Every order in finance queue must have pending payout > 0
    for order in orders:
        assert order["pending_payout_minor"] > 0

def test_get_orders_support_view_api(client):
    response = client.get("/api/orders?view=support")
    assert response.status_code == 200
    orders = response.json()
    assert len(orders) > 0

def test_get_order_detail_api(client):
    response = client.get("/api/orders/ord_1003")
    assert response.status_code == 200
    data = response.json()
    assert data["order"]["order_id"] == "ord_1003"
    assert data["is_over_refunded"] is True

def test_refund_decision_action_api(client):
    refund_id = "rfnd_6116"
    key = "api_idemp_key_999"
    
    # 1. Action Post
    resp1 = client.post(
        f"/api/refunds/{refund_id}/decision",
        json={"action": "approve", "reason": "Verified by support lead", "idempotency_key": key}
    )
    assert resp1.status_code == 200
    assert resp1.json()["status"] == "success"

    # 2. Duplicate Action Post -> Idempotent ignore
    resp2 = client.post(
        f"/api/refunds/{refund_id}/decision",
        json={"action": "approve", "reason": "Verified by support lead", "idempotency_key": key}
    )
    assert resp2.status_code == 200
    assert resp2.json()["status"] == "ignored_duplicate"
