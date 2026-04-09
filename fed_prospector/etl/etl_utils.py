"""
Shared ETL utility functions.

Used by all ETL loaders. Import from here instead of reimplementing per-loader.
"""
import hashlib
import json
import logging
import re
import time
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


# ---------------------------------------------------------------------------
# Resource GUID extraction (Phase 110ZZZ — Attachment Deduplication)
# ---------------------------------------------------------------------------

_RESOURCE_GUID_RE = re.compile(r'/resources/files/([0-9a-f]{32})/download', re.IGNORECASE)


def extract_resource_guid(url: str) -> str | None:
    """Extract the 32-char hex resource GUID from a SAM.gov attachment URL.

    Returns the lowercase GUID or None if the URL doesn't match the expected pattern.
    """
    if not url:
        return None
    m = _RESOURCE_GUID_RE.search(url)
    return m.group(1).lower() if m else None


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


# ---------------------------------------------------------------------------
# USASpending award summary refresh (Phase 115I)
# ---------------------------------------------------------------------------


def refresh_usaspending_award_summary(conn):
    """Refresh the usaspending_award_summary table from usaspending_award.

    Pre-computes vendor count, contract count, and total value per
    NAICS+agency combination for sub-millisecond scoring lookups.
    Called after usaspending and awards loads.
    """
    logger.info("Refreshing usaspending_award_summary...")
    t0 = time.time()

    cursor = conn.cursor()
    cursor.execute("TRUNCATE TABLE usaspending_award_summary")
    cursor.execute("""
        INSERT INTO usaspending_award_summary
            (naics_code, agency_cgac, agency_name, vendor_count, contract_count, total_value, computed_at)
        SELECT
            naics_code,
            awarding_agency_cgac,
            MAX(awarding_agency_name),
            COUNT(DISTINCT recipient_uei),
            COUNT(*),
            COALESCE(SUM(total_obligation), 0),
            NOW()
        FROM usaspending_award
        WHERE naics_code IS NOT NULL
          AND awarding_agency_cgac IS NOT NULL
          AND recipient_uei IS NOT NULL
        GROUP BY naics_code, awarding_agency_cgac
    """)
    row_count = cursor.rowcount

    # Add NAICS-level totals with true distinct vendor count (agency_cgac = '*')
    cursor.execute("""
        INSERT INTO usaspending_award_summary
            (naics_code, agency_cgac, agency_name, vendor_count, contract_count, total_value, computed_at)
        SELECT
            naics_code,
            '*',
            'All Agencies',
            COUNT(DISTINCT recipient_uei),
            COUNT(*),
            COALESCE(SUM(total_obligation), 0),
            NOW()
        FROM usaspending_award
        WHERE naics_code IS NOT NULL
          AND recipient_uei IS NOT NULL
        GROUP BY naics_code
    """)
    naics_total_count = cursor.rowcount
    conn.commit()

    elapsed = time.time() - t0
    logger.info("usaspending_award_summary refreshed: %d agency rows + %d NAICS totals in %.1fs",
                row_count, naics_total_count, elapsed)
    return row_count + naics_total_count


def resolve_usaspending_agency_codes(conn):
    """Resolve NULL CGAC codes on usaspending_award after a load.

    Queries distinct agency names with NULL codes, resolves via
    AgencyResolver, and runs per-name UPDATEs. Only touches NULL rows
    so it's safe to call repeatedly.

    Called after refresh_usaspending_award_summary() in both the
    bulk loader and API loader.
    """
    from etl.agency_resolver import AgencyResolver

    resolver = AgencyResolver()
    cursor = conn.cursor()
    total_updated = 0

    for cgac_col, name_col in [
        ("awarding_agency_cgac", "awarding_agency_name"),
        ("funding_agency_cgac", "funding_agency_name"),
    ]:
        cursor.execute(
            f"SELECT DISTINCT {name_col} FROM usaspending_award "
            f"WHERE {cgac_col} IS NULL AND {name_col} IS NOT NULL"
        )
        names = [row[0] for row in cursor.fetchall()]
        if not names:
            continue

        mapping = resolver.resolve_bulk(names)
        for name, cgac in mapping.items():
            if cgac:
                cursor.execute(
                    f"UPDATE usaspending_award SET {cgac_col} = %s "
                    f"WHERE {name_col} = %s AND {cgac_col} IS NULL",
                    (cgac, name),
                )
                total_updated += cursor.rowcount
        conn.commit()

    logger.info("Resolved %d usaspending_award agency code rows", total_updated)
    return total_updated
