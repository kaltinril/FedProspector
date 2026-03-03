"""
Shared ETL utility functions.

Used by all ETL loaders. Import from here instead of reimplementing per-loader.
"""
import hashlib
import json
from datetime import datetime
from decimal import Decimal, InvalidOperation

from db.connection import get_connection


# ---------------------------------------------------------------------------
# Date parsing
# ---------------------------------------------------------------------------

_DATE_FORMATS = [
    "%Y-%m-%d",    # ISO: 2024-01-15
    "%Y%m%d",      # compact: 20240115
    "%m/%d/%Y",    # US: 01/15/2024
    "%m-%d-%Y",    # dash-US: 01-15-2024
]


def parse_date(value) -> str | None:
    """
    Normalize any SAM.gov / USASpending date string to YYYY-MM-DD.
    Handles None, empty string, ISO 8601 with time component, and all common formats.
    Returns None on failure — never raises.
    """
    if not value:
        return None
    s = str(value).strip()
    if "T" in s:
        s = s.split("T")[0]
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(s, fmt).strftime("%Y-%m-%d")
        except ValueError:
            continue
    return None


# ---------------------------------------------------------------------------
# Decimal parsing
# ---------------------------------------------------------------------------


def parse_decimal(value) -> str | None:
    """
    Normalize a dollar amount to a decimal string MySQL can store as DECIMAL.
    Strips commas, handles None and non-numeric. Returns None on failure.
    """
    if value is None:
        return None
    try:
        return str(Decimal(str(value).replace(",", "").strip()))
    except InvalidOperation:
        return None


# ---------------------------------------------------------------------------
# Change detection
# ---------------------------------------------------------------------------


def fetch_existing_hashes(table_name: str, key_col: str) -> dict:
    """
    Return a {key_value: record_hash} dict for all rows in table_name
    that already have a record_hash. Used for change-detection in ETL loaders.

    table_name and key_col come from class-level string constants — no injection risk.
    """
    conn = get_connection()
    cursor = conn.cursor()
    try:
        cursor.execute(
            f"SELECT {key_col}, record_hash FROM {table_name} WHERE record_hash IS NOT NULL"
        )
        return {row[0]: row[1] for row in cursor.fetchall()}
    finally:
        cursor.close()
        conn.close()


# ---------------------------------------------------------------------------
# Bulk loading helpers
# ---------------------------------------------------------------------------


def escape_tsv_value(value) -> str:
    """
    Escape a value for MySQL LOAD DATA INFILE TSV format.
    Handles None, newlines, tabs, backslashes, and carriage returns.
    """
    if value is None:
        return "\\N"
    s = str(value)
    s = s.replace("\\", "\\\\")
    s = s.replace("\t", "\\t")
    s = s.replace("\n", "\\n")
    s = s.replace("\r", "\\r")
    return s
