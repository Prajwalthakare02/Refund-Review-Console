"""
API endpoint tests for the Refund Review Console.

Uses FastAPI TestClient to verify all REST endpoints against real data.
"""

from __future__ import annotations

import uuid

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.services.decision_store import store


@pytest.fixture(scope="module", autouse=True)
def _init_store():
    """Ensure the store is initialised before API tests run."""
    if not store._initialised:
        store.initialise()


@pytest.fixture(scope="module")
def client():
    """Create a TestClient that skips lifespan (store already initialised)."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


# ===========================================================================
# Health check
# ===========================================================================

class TestHealthCheck:

    def test_root_returns_ok(self, client: TestClient):
        resp = client.get("/")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


# ===========================================================================
# GET /api/metrics/summary
# ===========================================================================

class TestMetricsSummary:

    def test_returns_200(self, client: TestClient):
        resp = client.get("/api/metrics/summary")
        assert resp.status_code == 200

    def test_has_pinned_now(self, client: TestClient):
        data = client.get("/api/metrics/summary").json()
        assert data["pinned_now"] == "2026-08-11T04:30:00Z"

    def test_pending_payout_has_inr(self, client: TestClient):
        data = client.get("/api/metrics/summary").json()
        assert "INR" in data["pending_payout"]

    def test_pending_amounts_are_integers(self, client: TestClient):
        data = client.get("/api/metrics/summary").json()
        for currency, summary in data["pending_payout"].items():
            assert isinstance(summary["amount_minor"], int), (
                f"{currency}: amount_minor should be int"
            )
            assert isinstance(summary["count"], int)

    def test_has_formatted_string(self, client: TestClient):
        data = client.get("/api/metrics/summary").json()
        for currency, summary in data["pending_payout"].items():
            assert "amount_formatted" in summary
            assert isinstance(summary["amount_formatted"], str)


# ===========================================================================
# GET /api/orders?view=finance
# ===========================================================================

class TestFinanceQueue:

    def test_returns_200(self, client: TestClient):
        resp = client.get("/api/orders?view=finance")
        assert resp.status_code == 200

    def test_response_shape(self, client: TestClient):
        data = client.get("/api/orders?view=finance").json()
        assert "total" in data
        assert "page" in data
        assert "per_page" in data
        assert "orders" in data
        assert isinstance(data["orders"], list)

    def test_all_orders_have_pending_refunds(self, client: TestClient):
        """Finance queue should only contain orders with actionable pending refunds."""
        data = client.get("/api/orders?view=finance").json()
        for order in data["orders"]:
            assert order["pending_payout_minor"] != 0 or order["status"] == "pending_approval", (
                f"{order['order_id']} in finance queue without pending payout"
            )

    def test_pagination_defaults(self, client: TestClient):
        data = client.get("/api/orders?view=finance").json()
        assert data["page"] == 1
        assert data["per_page"] == 50


# ===========================================================================
# GET /api/orders?view=support
# ===========================================================================

class TestSupportQueue:

    def test_returns_200(self, client: TestClient):
        resp = client.get("/api/orders?view=support")
        assert resp.status_code == 200

    def test_support_queue_not_empty(self, client: TestClient):
        data = client.get("/api/orders?view=support").json()
        assert data["total"] > 0, "Support queue should have orders"

    def test_support_queue_larger_than_finance(self, client: TestClient):
        """Support queue includes all activity, finance only pending."""
        finance = client.get("/api/orders?view=finance").json()
        support = client.get("/api/orders?view=support").json()
        assert support["total"] >= finance["total"]


# ===========================================================================
# GET /api/orders?search=
# ===========================================================================

class TestOrderSearch:

    def test_search_by_order_id(self, client: TestClient):
        data = client.get("/api/orders?view=support&search=ord_1003").json()
        assert data["total"] >= 1
        ids = [o["order_id"] for o in data["orders"]]
        assert "ord_1003" in ids

    def test_search_by_customer_id(self, client: TestClient):
        data = client.get("/api/orders?view=support&search=cus_403").json()
        assert data["total"] >= 1
        cids = [o["customer_id"] for o in data["orders"]]
        assert any("cus_403" in c for c in cids)

    def test_search_no_results(self, client: TestClient):
        data = client.get("/api/orders?view=finance&search=nonexistent_xyz").json()
        assert data["total"] == 0
        assert data["orders"] == []


# ===========================================================================
# GET /api/orders/{order_id} — detail
# ===========================================================================

class TestOrderDetail:

    def test_returns_200(self, client: TestClient):
        resp = client.get("/api/orders/ord_1001")
        assert resp.status_code == 200

    def test_404_for_unknown_order(self, client: TestClient):
        resp = client.get("/api/orders/ord_9999")
        assert resp.status_code == 404

    def test_has_timeline(self, client: TestClient):
        data = client.get("/api/orders/ord_1001").json()
        assert "timeline" in data
        assert isinstance(data["timeline"], list)
        assert len(data["timeline"]) > 0

    def test_timeline_sorted_chronologically(self, client: TestClient):
        data = client.get("/api/orders/ord_1001").json()
        timestamps = [e["occurred_at_utc"] for e in data["timeline"]]
        assert timestamps == sorted(timestamps), "Timeline not sorted chronologically"

    def test_has_flags(self, client: TestClient):
        data = client.get("/api/orders/ord_1003").json()
        assert "flags" in data
        assert data["flags"]["is_over_refunded"] is True

    def test_has_warnings(self, client: TestClient):
        data = client.get("/api/orders/ord_1003").json()
        assert "warnings" in data
        assert any("OVER-REFUNDED" in w for w in data["warnings"])

    def test_ord_1014_chargeback_and_double_loss(self, client: TestClient):
        data = client.get("/api/orders/ord_1014").json()
        assert data["flags"]["has_chargeback"] is True
        assert data["flags"]["has_double_loss_risk"] is True

    def test_ord_1008_orphan(self, client: TestClient):
        data = client.get("/api/orders/ord_1008").json()
        assert data["flags"]["is_orphan_order"] is True

    def test_ord_1024_currency_mismatch(self, client: TestClient):
        data = client.get("/api/orders/ord_1024").json()
        assert data["flags"]["has_currency_mismatch"] is True


# ===========================================================================
# POST /api/refunds/{refund_id}/decision — approve/reject + idempotency
# ===========================================================================

class TestDecisionEndpoint:

    def _find_pending_refund_id(self, client: TestClient) -> str:
        """Helper: find a refund_id that is currently in pending state."""
        data = client.get("/api/orders?view=finance").json()
        for order in data["orders"]:
            detail = client.get(f"/api/orders/{order['order_id']}").json()
            for refund in detail["refunds"]:
                if refund["status"] == "pending":
                    return refund["refund_id"]
        pytest.skip("No pending refunds available for testing")

    def test_approve_returns_success(self, client: TestClient):
        refund_id = self._find_pending_refund_id(client)
        key = str(uuid.uuid4())
        resp = client.post(
            f"/api/refunds/{refund_id}/decision",
            json={
                "action": "approve",
                "reason": "Test approval",
                "idempotency_key": key,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["refund_id"] == refund_id
        assert data["new_status"] == "approved"
        assert data["idempotency_key"] == key

    def test_reject_returns_success(self, client: TestClient):
        refund_id = self._find_pending_refund_id(client)
        key = str(uuid.uuid4())
        resp = client.post(
            f"/api/refunds/{refund_id}/decision",
            json={
                "action": "reject",
                "reason": "Fraudulent claim",
                "idempotency_key": key,
            },
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["success"] is True
        assert data["new_status"] == "rejected"

    def test_idempotency_returns_cached_response(self, client: TestClient):
        """Sending the same idempotency_key twice should return cached response."""
        refund_id = self._find_pending_refund_id(client)
        key = str(uuid.uuid4())
        body = {
            "action": "approve",
            "reason": "Idempotency test",
            "idempotency_key": key,
        }

        # First call — records decision
        resp1 = client.post(f"/api/refunds/{refund_id}/decision", json=body)
        assert resp1.status_code == 200

        # Second call — same key, should return cached result
        resp2 = client.post(f"/api/refunds/{refund_id}/decision", json=body)
        assert resp2.status_code == 200
        assert resp2.json() == resp1.json(), "Duplicate key should return identical response"

    def test_invalid_action_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/refunds/rfnd_5001/decision",
            json={
                "action": "cancel",
                "reason": "test",
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 422

    def test_empty_reason_returns_422(self, client: TestClient):
        resp = client.post(
            "/api/refunds/rfnd_5001/decision",
            json={
                "action": "approve",
                "reason": "   ",
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 422

    def test_unknown_refund_returns_404(self, client: TestClient):
        resp = client.post(
            "/api/refunds/rfnd_nonexistent/decision",
            json={
                "action": "approve",
                "reason": "test",
                "idempotency_key": str(uuid.uuid4()),
            },
        )
        assert resp.status_code == 404
