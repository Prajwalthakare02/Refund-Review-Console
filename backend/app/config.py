"""
Application-wide constants and configuration.

All temporal calculations reference PINNED_NOW — never the wall clock.
All financial thresholds are expressed in integer minor units (paise / cents).
"""

from pathlib import Path
from datetime import datetime, timezone, timedelta

# ---------------------------------------------------------------------------
# Project root is two levels above this file: backend/app/config.py -> project/
# ---------------------------------------------------------------------------
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent

# ---------------------------------------------------------------------------
# Time Anchor — pinned "now" for reproducible calculations
# ---------------------------------------------------------------------------
IST = timezone(timedelta(hours=5, minutes=30))

PINNED_NOW_IST = datetime(2026, 8, 11, 10, 0, 0, tzinfo=IST)
PINNED_NOW_UTC = PINNED_NOW_IST.astimezone(timezone.utc)
PINNED_NOW_ISO = "2026-08-11T04:30:00Z"

# ---------------------------------------------------------------------------
# Support Queue — 7-day lookback window (Rule 13)
# ---------------------------------------------------------------------------
SUPPORT_QUEUE_DAYS = 7
SUPPORT_QUEUE_CUTOFF_UTC = PINNED_NOW_UTC - timedelta(days=SUPPORT_QUEUE_DAYS)
SUPPORT_QUEUE_CUTOFF_ISO = "2026-08-04T04:30:00Z"

# ---------------------------------------------------------------------------
# High-Value Thresholds in minor units (Rule 14)
# ---------------------------------------------------------------------------
HIGH_VALUE_INR_MINOR: int = 5_000_000   # ₹50,000 × 100 paise
HIGH_VALUE_USD_MINOR: int = 50_000      # $500 × 100 cents

HIGH_VALUE_THRESHOLDS: dict[str, int] = {
    "INR": HIGH_VALUE_INR_MINOR,
    "USD": HIGH_VALUE_USD_MINOR,
}

# ---------------------------------------------------------------------------
# Data file paths
# ---------------------------------------------------------------------------
ORDERS_CSV_PATH: Path = _PROJECT_ROOT / "refund-console-data" / "orders.csv"
EVENTS_JSONL_PATH: Path = _PROJECT_ROOT / "refund-console-data" / "events.jsonl"
