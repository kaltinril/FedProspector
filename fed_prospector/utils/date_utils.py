"""Date format conversion utilities for federal data."""

from datetime import date, datetime


def parse_yyyymmdd(date_str):
    """Convert YYYYMMDD string to Python date. Returns None on bad input.

    Handles: '20240115', '2024-01-15', '01/15/2024', None, empty string
    """
    if not date_str or not isinstance(date_str, str):
        return None

    cleaned = date_str.strip()
    if not cleaned:
        return None

    # YYYYMMDD (most common in SAM.gov extracts)
    if len(cleaned) == 8 and cleaned.isdigit():
        try:
            return date(int(cleaned[:4]), int(cleaned[4:6]), int(cleaned[6:8]))
        except ValueError:
            return None

    # YYYY-MM-DD
    if len(cleaned) >= 10 and cleaned[4] == "-":
        try:
            return date.fromisoformat(cleaned[:10])
        except ValueError:
            return None

    # MM/dd/yyyy (SAM.gov Opportunities API format)
    if len(cleaned) >= 10 and cleaned[2] == "/":
        try:
            return datetime.strptime(cleaned[:10], "%m/%d/%Y").date()
        except ValueError:
            return None

    return None


def format_sam_date(d):
    """Format a date as MM/dd/yyyy for SAM.gov API parameters."""
    if isinstance(d, date):
        return d.strftime("%m/%d/%Y")
    return d
