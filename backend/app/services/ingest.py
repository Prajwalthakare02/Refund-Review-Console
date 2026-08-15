"""
Data ingestion pipeline for orders.csv and events.jsonl.

Responsibilities:
  - Parse CSV and JSONL files into typed Pydantic models.
  - Deduplicate events by event_id (Rule 1).
  - Normalise timestamps to UTC ISO-8601 (Rule 2).
  - Standardise amounts to integer minor units (Rule 3).
"""

from __future__ import annotations

import csv
import json
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from dateutil import parser as dtparser

from app.config import ORDERS_CSV_PATH, EVENTS_JSONL_PATH
from app.models.schemas import Order, Event


# ---------------------------------------------------------------------------
# Timezone helpers
# ---------------------------------------------------------------------------

_IST = timezone(timedelta(hours=5, minutes=30))


def _normalise_timestamp(raw: str) -> str:
    """
    Parse a timestamp string and return a UTC ISO-8601 string.

    Handles three formats found in the data:
      1. ISO-8601 with 'Z' suffix  → already UTC
      2. ISO-8601 with '+05:30'    → explicit IST offset
      3. Naive 'YYYY-MM-DD HH:MM:SS' (legacy_gw) → assume IST (Rule 2)
    """
    try:
        dt = dtparser.parse(raw)
    except (ValueError, TypeError):
        return raw

    if dt.tzinfo is None:
        # Naive timestamp → assume IST (Rule 2: legacy gateway posts in Hyderabad local time)
        dt = dt.replace(tzinfo=_IST)

    # Convert to UTC and return ISO-8601 string
    dt_utc = dt.astimezone(timezone.utc)
    return dt_utc.strftime("%Y-%m-%dT%H:%M:%SZ")


def _amount_to_minor(
    amount_minor: Optional[int],
    amount: Optional[float],
) -> int:
    """
    Return the canonical integer minor-unit amount (Rule 3).

    - If amount_minor is present (gw_primary, gw_upi), use it directly.
    - If only amount is present (legacy_gw), convert: round(amount * 100).
    """
    if amount_minor is not None:
        return int(amount_minor)
    if amount is not None:
        return round(amount * 100)
    return 0


# ---------------------------------------------------------------------------
# Orders ingestion
# ---------------------------------------------------------------------------

def load_orders(path: Optional[Path] = None) -> list[Order]:
    """
    Parse orders.csv into a list of Order models.

    Converts total_amount (decimal) to total_amount_minor (int).
    Normalises placed_at to UTC ISO-8601.
    """
    filepath = path or ORDERS_CSV_PATH
    orders: list[Order] = []

    with open(filepath, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total_str = row["total_amount"].strip()
            total_minor = round(float(total_str) * 100)

            placed_at_utc = _normalise_timestamp(row["placed_at"].strip())

            orders.append(Order(
                order_id=row["order_id"].strip(),
                customer_id=row["customer_id"].strip(),
                currency=row["currency"].strip(),
                total_amount_minor=total_minor,
                placed_at_utc=placed_at_utc,
                channel=row["channel"].strip(),
                region=row["region"].strip(),
            ))

    return orders


# ---------------------------------------------------------------------------
# Events ingestion
# ---------------------------------------------------------------------------

def load_events(path: Optional[Path] = None) -> list[Event]:
    """
    Parse events.jsonl into a list of Event models.

    Applies:
      Rule 1 — Deduplication by event_id (first occurrence wins).
      Rule 2 — Timestamp normalisation to UTC.
      Rule 3 — Amount normalisation to integer minor units.
    """
    filepath = path or EVENTS_JSONL_PATH
    events: list[Event] = []
    seen_ids: set[str] = set()

    with open(filepath, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            raw: dict = json.loads(line)
            event_id: str = raw["event_id"]

            # Rule 1: Deduplication — first occurrence wins
            if event_id in seen_ids:
                continue
            seen_ids.add(event_id)

            # Rule 2: Normalise timestamps to UTC
            occurred_utc = _normalise_timestamp(raw["occurred_at"])
            received_utc = _normalise_timestamp(raw["received_at"])

            # Rule 3: Normalise amount to integer minor units
            amount_minor = _amount_to_minor(
                amount_minor=raw.get("amount_minor"),
                amount=raw.get("amount"),
            )

            events.append(Event(
                event_id=event_id,
                type=raw["type"],
                order_id=raw["order_id"],
                refund_id=raw.get("refund_id"),
                currency=raw["currency"],
                amount_minor=amount_minor,
                occurred_at_utc=occurred_utc,
                received_at_utc=received_utc,
                source=raw["source"],
                reason=raw.get("reason"),
                failure_code=raw.get("failure_code"),
                requested_by=raw.get("requested_by"),
                network_case_id=raw.get("network_case_id"),
            ))

    return events
