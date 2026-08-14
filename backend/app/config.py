import os
from datetime import datetime, timezone

# Base workspace paths
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
DATA_DIR = os.path.join(BASE_DIR, "refund-console-data")
ORDERS_CSV_PATH = os.path.join(DATA_DIR, "orders.csv")
EVENTS_JSONL_PATH = os.path.join(DATA_DIR, "events.jsonl")

# Pinned "NOW" timestamp: 2026-08-11T10:00:00+05:30 -> UTC 2026-08-11T04:30:00Z
NOW_TIMESTAMP_ISO = "2026-08-11T10:00:00+05:30"
NOW_UTC = datetime(2026, 8, 11, 4, 30, 0, tzinfo=timezone.utc)

# High value refund threshold (in minor units)
HIGH_VALUE_THRESHOLDS_MINOR = {
    "INR": 5000000,  # ₹50,000.00 -> 5,000,000 paise
    "USD": 50000      # $500.00 -> 50,000 cents
}
