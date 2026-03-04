"""Opportunity loader: transforms SAM.gov opportunity API data into MySQL.

Loads opportunity records from the SAM.gov Opportunities API, with
change detection via SHA-256 hashing and field-level history tracking.
Follows the same patterns as entity_loader.py.
"""

import json
import logging
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation

from db.connection import get_connection
from etl.change_detector import ChangeDetector
from etl.etl_utils import parse_date, parse_decimal
from etl.load_manager import LoadManager
from etl.staging_mixin import StagingMixin

# ---------------------------------------------------------------------------
# Fields used for opportunity record hash (all meaningful business fields,
# excludes timestamps, description, link, resource_links, and load-tracking)
# ---------------------------------------------------------------------------
_OPPORTUNITY_HASH_FIELDS = [
    "notice_id", "title", "solicitation_number",
    "department_name", "sub_tier", "office",
    "posted_date", "response_deadline", "archive_date",
    "type", "base_type", "set_aside_code",
    "classification_code", "naics_code",
    "pop_state", "pop_zip", "pop_country", "pop_city",
    "active", "award_number", "award_date", "award_amount",
    "awardee_uei", "awardee_name", "contracting_office_id",
]


class OpportunityLoader(StagingMixin):
    """Transform and load SAM.gov opportunity data into MySQL."""

    BATCH_SIZE = 500  # Smaller than entity since fewer records expected

    _STG_TABLE = "stg_opportunity_raw"
    _STG_KEY_COLS = ["notice_id"]

    # -----------------------------------------------------------------
    # Construction
    # -----------------------------------------------------------------
    def __init__(self, db_connection=None, change_detector=None, load_manager=None):
        """Initialize with optional DB connection, change detector, load manager.

        Args:
            db_connection: Not used (connections obtained from pool). Kept for
                           interface compatibility.
            change_detector: Optional ChangeDetector instance.
            load_manager: Optional LoadManager instance.
        """
        self.logger = logging.getLogger("fed_prospector.etl.opportunity_loader")
        self.change_detector = change_detector or ChangeDetector()
        self.load_manager = load_manager or LoadManager()

    # =================================================================
    # Public entry point
    # =================================================================

    def load_opportunities(self, opportunities_data, load_id):
        """Main entry point. Process list of raw API opportunity dicts.

        Args:
            opportunities_data: list of raw opportunity dicts from API
            load_id: etl_load_log ID for this load

        Returns:
            dict with keys: records_read, inserted, updated, unchanged, errored
        """
        # Materialize generator to allow len() and safe re-iteration
        opportunities_data = list(opportunities_data)
        self.logger.info(
            "Starting opportunity load (%d records, load_id=%d)",
            len(opportunities_data), load_id,
        )

        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_unchanged": 0,
            "records_errored": 0,
        }

        # Pre-fetch existing hashes for change detection
        existing_hashes = self.change_detector.get_existing_hashes(
            "opportunity", "notice_id", "record_hash"
        )

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Staging connection: autocommit=True so each raw row is persisted
        # immediately, independent of the production batch commit/rollback cycle.
        stg_conn, stg_cursor = self._open_stg_conn()

        try:
            batch_count = 0
            for raw in opportunities_data:
                stats["records_read"] += 1
                notice_id = None
                staging_id = None
                try:
                    # --- write raw record to staging BEFORE normalization ---
                    key_vals = self._extract_staging_key(raw)
                    staging_id = self._insert_staging(stg_cursor, load_id, key_vals, raw)

                    # --- normalise ----------------------------------------
                    opp_data = self._normalize_opportunity(raw)
                    notice_id = opp_data.get("notice_id")
                    if not notice_id:
                        raise ValueError("Missing noticeId in opportunity record")

                    # --- change detection ---------------------------------
                    new_hash = self.change_detector.compute_hash(
                        opp_data, _OPPORTUNITY_HASH_FIELDS
                    )
                    opp_data["record_hash"] = new_hash

                    old_hash = existing_hashes.get(notice_id)
                    if old_hash and old_hash == new_hash:
                        stats["records_unchanged"] += 1
                        self._mark_staging(stg_cursor, staging_id, 'Y')
                        batch_count += 1
                        if batch_count >= self.BATCH_SIZE:
                            conn.commit()
                            batch_count = 0
                        continue

                    # --- fetch old record for history (updates only) -------
                    if old_hash is not None:
                        old_record = self._fetch_opportunity_row(cursor, notice_id)
                    else:
                        old_record = None

                    # --- upsert -------------------------------------------
                    outcome = self._upsert_opportunity(cursor, opp_data, load_id)
                    if outcome == "inserted":
                        stats["records_inserted"] += 1
                    elif outcome == "updated":
                        stats["records_updated"] += 1
                    else:
                        stats["records_unchanged"] += 1

                    # --- history logging (updates only) --------------------
                    if old_record is not None and outcome == "updated":
                        diffs = self.change_detector.compute_field_diff(
                            old_record, opp_data, _OPPORTUNITY_HASH_FIELDS
                        )
                        if diffs:
                            self._log_changes(cursor, notice_id, diffs, load_id)

                    # Update in-memory hash cache
                    existing_hashes[notice_id] = new_hash

                    # --- mark staging processed ----------------------------
                    self._mark_staging(stg_cursor, staging_id, 'Y')

                except Exception as rec_exc:
                    stats["records_errored"] += 1
                    identifier = notice_id or f"record#{stats['records_read']}"
                    self.logger.warning(
                        "Error processing %s: %s", identifier, rec_exc
                    )
                    self.load_manager.log_record_error(
                        load_id,
                        record_identifier=identifier,
                        error_type=type(rec_exc).__name__,
                        error_message=str(rec_exc),
                        raw_data=json.dumps(raw) if isinstance(raw, dict) else str(raw),
                    )
                    if staging_id:
                        self._mark_staging(stg_cursor, staging_id, 'E', str(rec_exc))
                    # Rollback the failed record, then keep going
                    conn.rollback()
                    batch_count = 0
                    continue

                batch_count += 1
                if batch_count >= self.BATCH_SIZE:
                    conn.commit()
                    batch_count = 0

                # Progress logging
                if stats["records_read"] % self.BATCH_SIZE == 0:
                    self.logger.info(
                        "Progress: read=%d ins=%d upd=%d unch=%d err=%d",
                        stats["records_read"],
                        stats["records_inserted"],
                        stats["records_updated"],
                        stats["records_unchanged"],
                        stats["records_errored"],
                    )

            # Final commit for any remaining records in the last partial batch
            conn.commit()

        finally:
            cursor.close()
            conn.close()
            stg_cursor.close()
            stg_conn.close()

        self.logger.info(
            "Opportunity load complete (load_id=%d): read=%d ins=%d upd=%d unch=%d err=%d",
            load_id,
            stats["records_read"],
            stats["records_inserted"],
            stats["records_updated"],
            stats["records_unchanged"],
            stats["records_errored"],
        )
        return stats

    # =================================================================
    # Normalisation
    # =================================================================

    def _normalize_opportunity(self, raw):
        """Flatten nested API response into flat dict matching DB columns.

        Handles nested placeOfPerformance and award objects.
        Converts dates to proper format, active Yes/No to Y/N,
        award amount to Decimal string, and JSON-encodes resourceLinks.
        """
        pop = self._safe_get(raw, "placeOfPerformance") or {}
        pop_state_obj = self._safe_get(pop, "state") or {}
        pop_country_obj = self._safe_get(pop, "country") or {}

        award = self._safe_get(raw, "award") or {}
        awardee = self._safe_get(award, "awardee") or {}

        # Convert active: "Yes" -> "Y", "No" -> "N", anything else -> first char or None
        active_raw = raw.get("active")
        if active_raw == "Yes":
            active = "Y"
        elif active_raw == "No":
            active = "N"
        elif active_raw:
            active = str(active_raw)[:1].upper()
        else:
            active = None

        # Parse award amount to string for Decimal column
        award_amount = self._parse_decimal(award.get("amount"))

        # JSON-encode resource links
        resource_links_raw = raw.get("resourceLinks")
        if resource_links_raw is not None:
            resource_links = json.dumps(resource_links_raw)
        else:
            resource_links = None

        # Parse department hierarchy from dot-separated path
        parent_path = raw.get("fullParentPathName") or ""
        path_parts = [p.strip() for p in parent_path.split(".")] if parent_path else []

        department_name = path_parts[0] if len(path_parts) >= 1 else None
        sub_tier = path_parts[1] if len(path_parts) >= 2 else None
        if len(path_parts) >= 3:
            office = path_parts[-1]
        elif len(path_parts) == 2:
            office = sub_tier  # only 2 segments: office same as sub_tier
        else:
            office = None

        # Parse code hierarchy for contracting_office_id (last segment)
        parent_code = raw.get("fullParentPathCode") or ""
        code_parts = [p.strip() for p in parent_code.split(".")] if parent_code else []
        contracting_office_id = code_parts[-1] if code_parts else None

        return {
            "notice_id":             raw.get("noticeId"),
            "title":                 raw.get("title"),
            "solicitation_number":   raw.get("solicitationNumber"),
            "department_name":       department_name,
            "sub_tier":              sub_tier,
            "office":                office,
            "posted_date":           self._parse_date(raw.get("postedDate")),
            "response_deadline":     self._parse_datetime(raw.get("responseDeadLine")),
            "archive_date":          self._parse_date(raw.get("archiveDate")),
            "type":                  raw.get("type"),
            "base_type":             raw.get("baseType"),
            "set_aside_code":        raw.get("typeOfSetAside"),
            "set_aside_description": raw.get("typeOfSetAsideDescription"),
            "classification_code":   raw.get("classificationCode"),
            "naics_code":            raw.get("naicsCode"),
            "pop_state":             pop_state_obj.get("code"),
            "pop_zip":               pop.get("zip"),
            "pop_country":           pop_country_obj.get("code"),
            "pop_city":              self._safe_get(pop, "city", "name"),
            "active":                active,
            "award_number":          award.get("number"),
            "award_date":            self._parse_date(award.get("date")),
            "award_amount":          award_amount,
            "awardee_uei":           awardee.get("ueiSAM"),
            "awardee_name":          awardee.get("name"),
            "description_url":       raw.get("description"),
            "link":                  raw.get("uiLink"),
            "resource_links":        resource_links,
            "contracting_office_id": contracting_office_id,
        }

    # =================================================================
    # Database operations
    # =================================================================

    def _upsert_opportunity(self, cursor, opp_data, load_id):
        """INSERT ... ON DUPLICATE KEY UPDATE for the opportunity table.

        Args:
            cursor: Active DB cursor.
            opp_data: Normalised opportunity dict.
            load_id: Current load ID.

        Returns:
            'inserted', 'updated', or 'unchanged'
        """
        cols = [
            "notice_id", "title", "solicitation_number",
            "department_name", "sub_tier", "office",
            "posted_date", "response_deadline", "archive_date",
            "type", "base_type",
            "set_aside_code", "set_aside_description",
            "classification_code", "naics_code",
            "pop_state", "pop_zip", "pop_country", "pop_city",
            "active",
            "award_number", "award_date", "award_amount",
            "awardee_uei", "awardee_name",
            "description_url", "link", "resource_links",
            "contracting_office_id",
            "record_hash", "last_load_id",
        ]

        placeholders = ", ".join(["%s"] * len(cols))
        col_list = ", ".join(cols)

        # ON DUPLICATE KEY UPDATE: update all mutable columns
        update_pairs = ", ".join(
            f"{c} = VALUES({c})" for c in cols if c != "notice_id"
        )
        # Also update last_loaded_at on every touch
        update_pairs += ", last_loaded_at = NOW()"

        sql = (
            f"INSERT INTO opportunity ({col_list}, first_loaded_at, last_loaded_at) "
            f"VALUES ({placeholders}, NOW(), NOW()) "
            f"ON DUPLICATE KEY UPDATE {update_pairs}"
        )

        values = [opp_data.get(c) for c in cols[:-1]]  # all except last_load_id
        values.append(load_id)  # last_load_id

        cursor.execute(sql, values)

        # MySQL returns rowcount: 0 = unchanged, 1 = inserted, 2 = updated
        rc = cursor.rowcount
        if rc == 1:
            return "inserted"
        elif rc == 2:
            return "updated"
        return "unchanged"

    # =================================================================
    # History / fetch helpers
    # =================================================================

    def _fetch_opportunity_row(self, cursor, notice_id):
        """Fetch the current opportunity row as a dict for diff comparison."""
        cursor.execute("SELECT * FROM opportunity WHERE notice_id = %s", (notice_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        # cursor is dictionary=True, so row is already a dict.
        # Convert date/datetime/Decimal values to strings for comparison.
        clean = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                clean[k] = v.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(v, date):
                clean[k] = v.isoformat()
            elif isinstance(v, Decimal):
                clean[k] = str(v)
            else:
                clean[k] = v
        return clean

    def _log_changes(self, cursor, notice_id, diffs, load_id):
        """Write field-level change records to opportunity_history."""
        sql = (
            "INSERT INTO opportunity_history (notice_id, field_name, old_value, new_value, load_id) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        rows = [
            (notice_id, field, _str_or_none(old_val), _str_or_none(new_val), load_id)
            for field, old_val, new_val in diffs
        ]
        cursor.executemany(sql, rows)

    # =================================================================
    # Raw staging helpers
    # =================================================================

    def _extract_staging_key(self, raw: dict) -> dict:
        """Extract natural key fields from a raw API record."""
        return {"notice_id": raw.get("noticeId", "")}

    # =================================================================
    # Parsing helpers
    # =================================================================

    def _parse_date(self, date_str):
        """Parse various date formats from API response.

        Delegates to etl_utils.parse_date which handles all common SAM.gov
        date formats: YYYY-MM-DD, YYYYMMDD, MM/DD/YYYY, ISO 8601 with time.

        Returns:
            date string in YYYY-MM-DD format or None.
        """
        return parse_date(date_str)

    def _parse_datetime(self, dt_str):
        """Parse datetime from API response (e.g., response_deadline).

        Handles ISO 8601 strings with various timezone formats.

        Returns:
            datetime string in YYYY-MM-DD HH:MM:SS format or None.
        """
        if not dt_str:
            return None
        s = str(dt_str).strip()
        if not s:
            return None

        # Try standard ISO formats
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",      # 2026-01-15T14:30:00-05:00 (tz-aware)
            "%Y-%m-%dT%H:%M:%S.%f%z",    # with microseconds (tz-aware)
            "%Y-%m-%dT%H:%M:%S",          # no timezone
            "%Y-%m-%dT%H:%M:%S.%f",       # no timezone, with microseconds
            "%Y-%m-%d %H:%M:%S",           # space-separated
            "%m/%d/%Y %H:%M:%S",           # US format
            "%m/%d/%Y %I:%M %p",           # US format 12h
        ):
            try:
                dt = datetime.strptime(s, fmt)
                # If timezone-aware, convert to UTC before stripping tz info
                # so stored values are consistently UTC (e.g. response_deadline)
                if dt.tzinfo is not None:
                    dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
                return dt.strftime("%Y-%m-%d %H:%M:%S")
            except ValueError:
                continue

        # If it looks like just a date, return with midnight time
        date_part = self._parse_date(s)
        if date_part:
            return f"{date_part} 00:00:00"

        # Fallback
        return s

    def _parse_decimal(self, value):
        """Parse a value to Decimal-compatible string.

        Delegates to etl_utils.parse_decimal.

        Returns:
            String representation of the decimal, or None.
        """
        return parse_decimal(value)

    def _safe_get(self, data, *keys, default=None):
        """Safely navigate nested dicts.

        e.g., _safe_get(data, 'award', 'amount') is equivalent to
        data.get('award', {}).get('amount')
        """
        current = data
        for key in keys:
            if isinstance(current, dict):
                current = current.get(key)
            else:
                return default
            if current is None:
                return default
        return current

    # =================================================================
    # Hash fields accessor
    # =================================================================

    @staticmethod
    def get_hash_fields():
        """Return the list of fields used for opportunity record hashing."""
        return list(_OPPORTUNITY_HASH_FIELDS)


# =====================================================================
# Module-level helper functions
# =====================================================================

def _str_or_none(val):
    """Convert a value to str for history logging, preserving None."""
    if val is None:
        return None
    return str(val)
