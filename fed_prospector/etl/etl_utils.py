"""
Shared ETL utility functions.

Used by all ETL loaders. Import from here instead of reimplementing per-loader.
"""
import hashlib
import json
import logging
from datetime import datetime
from decimal import Decimal, InvalidOperation

from db.connection import get_connection

logger = logging.getLogger("fed_prospector.etl_utils")


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


# ---------------------------------------------------------------------------
# Dynamic NAICS / Set-Aside derivation (Phase 91-E1+E2)
# ---------------------------------------------------------------------------


def get_tracked_naics() -> list[str]:
    """Union of NAICS codes from all active orgs' organization_naics.
    Falls back to settings.DEFAULT_AWARDS_NAICS if DB returns empty."""
    from config import settings

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT DISTINCT n.naics_code "
            "FROM organization_naics n "
            "JOIN organization o ON o.organization_id = n.organization_id "
            "WHERE o.is_active = 'Y'"
        )
        codes = [row["naics_code"] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

    if codes:
        logger.info("Dynamic awards filter: %d NAICS codes from org data", len(codes))
        return codes

    fallback = [c.strip() for c in settings.DEFAULT_AWARDS_NAICS.split(",") if c.strip()]
    logger.info("No org NAICS configured — using DEFAULT_AWARDS_NAICS (%d codes)", len(fallback))
    return fallback


def get_tracked_set_asides() -> list[str]:
    """Union of certification types from all active orgs' organization_certification,
    mapped to set-aside codes. Falls back to settings.DEFAULT_AWARDS_SET_ASIDES."""
    from config import settings

    # Map from certification type to set-aside codes
    cert_to_set_aside = {
        "8(a)": "8A",
        "WOSB": "WOSB",
        "EDWOSB": "WOSB",
        "HUBZone": "HZC",
        "SDVOSB": "SDVOSBC",
        "VOSB": "SDVOSBC",
        "SDB": "SBA",
    }

    conn = get_connection()
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT DISTINCT c.certification_type "
            "FROM organization_certification c "
            "JOIN organization o ON o.organization_id = c.organization_id "
            "WHERE o.is_active = 'Y' AND c.is_active = 'Y'"
        )
        types = [row["certification_type"] for row in cursor.fetchall()]
    finally:
        cursor.close()
        conn.close()

    if types:
        # Map cert types to set-aside codes
        set_asides = set()
        for cert_type in types:
            code = cert_to_set_aside.get(cert_type)
            if code:
                set_asides.add(code)
            else:
                # Try direct use as set-aside code
                set_asides.add(cert_type)
        result = sorted(set_asides)
        logger.info("Dynamic awards filter: %d set-aside codes from org data", len(result))
        return result

    fallback = [c.strip() for c in settings.DEFAULT_AWARDS_SET_ASIDES.split(",") if c.strip()]
    logger.info("No org certs configured — using DEFAULT_AWARDS_SET_ASIDES (%d codes)", len(fallback))
    return fallback
