import csv
import json
import os
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Tuple, Set
from dateutil import parser as date_parser

from app.models.schemas import OrderSchema, PaymentEventSchema
from app.config import ORDERS_CSV_PATH, EVENTS_JSONL_PATH

# IST Timezone offset (+05:30)
IST = timezone(timedelta(hours=5, minutes=30))

def parse_timestamp(ts_str: str) -> datetime:
    """
    Parses timestamp string to timezone-aware UTC datetime.
    - If string is ISO with 'Z' or offset (+05:30), parse directly and convert to UTC.
    - If string is naive datetime (e.g. "2026-08-01 05:54:00"), treat as IST (Asia/Kolkata) and convert to UTC.
    """
    dt = date_parser.parse(ts_str)
    if dt.tzinfo is None:
        # Naive timestamp from legacy_gw -> assume IST
        dt = dt.replace(tzinfo=IST)
    return dt.astimezone(timezone.utc)

def load_orders(csv_path: str = ORDERS_CSV_PATH) -> Dict[str, OrderSchema]:
    """
    Reads orders.csv and returns a dictionary of order_id -> OrderSchema.
    Normalizes amounts to minor units (paise/cents).
    """
    orders = {}
    if not os.path.exists(csv_path):
        return orders

    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            order_id = row["order_id"].strip()
            total_float = float(row["total_amount"])
            total_minor = int(round(total_float * 100))
            placed_at = parse_timestamp(row["placed_at"])
            
            orders[order_id] = OrderSchema(
                order_id=order_id,
                customer_id=row["customer_id"].strip(),
                currency=row["currency"].strip(),
                total_amount_minor=total_minor,
                placed_at=placed_at,
                channel=row["channel"].strip(),
                region=row["region"].strip(),
                is_orphan=False
            )
    return orders

def load_events(jsonl_path: str = EVENTS_JSONL_PATH) -> Tuple[List[PaymentEventSchema], Set[str]]:
    """
    Reads events.jsonl and returns (list_of_events, seen_event_ids).
    Rules enforced:
    1. Deduplication: Duplicate event_ids are skipped.
    2. Timezone Normalization: All timestamps converted to UTC.
    3. Currency Minor Unit Scaling: 'amount' float is scaled by 100 to 'amount_minor' integer.
    """
    events = []
    seen_event_ids = set()

    if not os.path.exists(jsonl_path):
        return events, seen_event_ids

    with open(jsonl_path, "r", encoding="utf-8") as f:
        for line in f:
            line_str = line.strip()
            if not line_str:
                continue
            data = json.loads(line_str)
            event_id = data["event_id"].strip()

            # Rule 1: Deduplication (Overnight relay duplicates)
            if event_id in seen_event_ids:
                continue
            seen_event_ids.add(event_id)

            # Rule 2: Amount Normalization (Minor Units)
            if "amount_minor" in data and data["amount_minor"] is not None:
                amount_minor = int(data["amount_minor"])
            elif "amount" in data and data["amount"] is not None:
                amount_minor = int(round(float(data["amount"]) * 100))
            else:
                amount_minor = 0

            # Rule 3: Timezone Normalization
            occurred_at = parse_timestamp(data["occurred_at"])
            received_at = parse_timestamp(data["received_at"])

            event_schema = PaymentEventSchema(
                event_id=event_id,
                type=data["type"].strip(),
                order_id=data["order_id"].strip(),
                refund_id=data.get("refund_id"),
                currency=data["currency"].strip(),
                occurred_at=occurred_at,
                received_at=received_at,
                source=data["source"].strip(),
                amount_minor=amount_minor,
                reason=data.get("reason"),
                failure_code=data.get("failure_code"),
                requested_by=data.get("requested_by"),
                network_case_id=data.get("network_case_id")
            )
            events.append(event_schema)

    # Sort all events strictly by occurred_at (Rule: occurred_at is truth for timeline ordering)
    events.sort(key=lambda e: e.occurred_at)
    return events, seen_event_ids
