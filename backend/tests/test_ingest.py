import pytest
from datetime import datetime, timezone
from app.services.ingest import parse_timestamp, load_orders, load_events

def test_parse_timestamp_utc():
    ts = "2026-08-06T02:30:00Z"
    dt = parse_timestamp(ts)
    assert dt.tzinfo == timezone.utc
    assert dt.hour == 2
    assert dt.minute == 30

def test_parse_timestamp_ist_naive():
    # Legacy naive timestamp -> assume IST (+05:30)
    ts = "2026-08-01 05:54:00"
    dt = parse_timestamp(ts)
    assert dt.tzinfo == timezone.utc
    # 05:54 IST = 00:24 UTC
    assert dt.hour == 0
    assert dt.minute == 24

def test_parse_timestamp_ist_offset():
    ts = "2026-07-30T14:42:00+05:30"
    dt = parse_timestamp(ts)
    assert dt.tzinfo == timezone.utc
    # 14:42 IST = 09:12 UTC
    assert dt.hour == 9
    assert dt.minute == 12

def test_load_orders():
    orders = load_orders()
    assert len(orders) == 154
    assert "ord_1001" in orders
    assert orders["ord_1001"].total_amount_minor == 129900  # ₹1,299.00 -> 129,900 paise
    assert orders["ord_1004"].currency == "USD"
    assert orders["ord_1004"].total_amount_minor == 24999    # $249.99 -> 24,999 cents

def test_load_events_deduplication():
    events, seen_ids = load_events()
    # 214 total lines, 1 duplicate evt_0001 -> 213 unique events
    assert len(events) == 213
    assert len(seen_ids) == 213
    assert "evt_0001" in seen_ids

def test_legacy_amount_scaling():
    events, _ = load_events()
    legacy_evt = next(e for e in events if e.event_id == "evt_0201")
    # Legacy amount was float 823.55 -> 82355 paise
    assert legacy_evt.amount_minor == 82355
