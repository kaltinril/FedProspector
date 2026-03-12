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
from etl.batch_upsert import build_upsert_sql, executemany_upsert
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

# All opportunity columns used in upsert (order matters for values list)
_UPSERT_COLS = [
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
    "awardee_cage_code", "awardee_city", "awardee_state", "awardee_zip",
    "full_parent_path_name", "full_parent_path_code",
    "description_url", "link", "resource_links",
    "contracting_office_id",
    "record_hash", "last_load_id",
]


class OpportunityLoader(StagingMixin):
    """Transform and load SAM.gov opportunity data into MySQL."""

    BATCH_SIZE = 500  # Smaller than entity since fewer records expected

    _STG_TABLE = "stg_opportunity_raw"
    _STG_KEY_COLS = ["notice_id"]

    # Pre-computed upsert SQL (built once, not per record)
    _UPSERT_SQL = build_upsert_sql(
        table="opportunity",
        columns=_UPSERT_COLS,
        pk_fields={"notice_id"},
    )

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
        return self._process_opportunities(iter(opportunities_data), load_id)

    def load_opportunity_batch(self, opps_data, load_id):
        """Process a batch of opportunities under an existing load_id.

        Unlike load_opportunities, does NOT create or complete the load
        entry -- the caller manages the load lifecycle. Used for page-by-page
        loading where progress is saved after each page.

        Args:
            opps_data: List of raw opportunity dicts (from one API page).
            load_id: Existing load_id from LoadManager.start_load().

        Returns:
            dict with batch statistics (records_read, records_inserted, etc.).
        """
        return self._process_opportunities(iter(opps_data), load_id)

    # =================================================================
    # Core processing pipeline
    # =================================================================

    def _process_opportunities(self, opps_iter, load_id):
        """Iterate over raw opportunities, normalise, detect changes, batch upsert.

        Uses batch operations for staging writes, upserts, and staging marks.
        POC writes and history logging are batched per BATCH_SIZE chunk.
        Falls back to row-by-row if a batch upsert fails.

        Args:
            opps_iter: Iterator of raw opportunity dicts.
            load_id: Current load identifier.
        """
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

        # Materialize iterator for batch slicing
        opps_list = list(opps_iter)

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Staging connection: autocommit=True so each raw row is persisted
        # immediately, independent of the production batch commit/rollback cycle.
        stg_conn, stg_cursor = self._open_stg_conn()

        try:
            for batch_start in range(0, len(opps_list), self.BATCH_SIZE):
                batch_raw = opps_list[batch_start : batch_start + self.BATCH_SIZE]

                # --- Phase 1: Normalize, compute hashes, classify ---
                staging_rows = []
                normalized = []
                changed_records = []  # (raw, opp_data, notice_id, new_hash, pocs, old_hash)

                for raw in batch_raw:
                    stats["records_read"] += 1
                    try:
                        key_vals = self._extract_staging_key(raw)
                        staging_rows.append((key_vals, raw))

                        opp_data = self._normalize_opportunity(raw)
                        notice_id = opp_data.get("notice_id")
                        if not notice_id:
                            raise ValueError("Missing noticeId in opportunity record")

                        new_hash = self.change_detector.compute_hash(
                            opp_data, _OPPORTUNITY_HASH_FIELDS
                        )
                        opp_data["record_hash"] = new_hash
                        pocs = opp_data.pop("_pocs", [])

                        old_hash = existing_hashes.get(notice_id)
                        if old_hash and old_hash == new_hash:
                            stats["records_unchanged"] += 1
                        else:
                            changed_records.append(
                                (raw, opp_data, notice_id, new_hash, pocs, old_hash)
                            )

                        normalized.append((raw, opp_data, notice_id, new_hash))

                    except Exception as rec_exc:
                        stats["records_errored"] += 1
                        identifier = f"record#{stats['records_read']}"
                        self.logger.warning(
                            "Error normalizing %s: %s", identifier, rec_exc
                        )
                        self.load_manager.log_record_error(
                            load_id,
                            record_identifier=identifier,
                            error_type=type(rec_exc).__name__,
                            error_message=str(rec_exc),
                            raw_data=json.dumps(raw) if isinstance(raw, dict) else str(raw),
                        )
                        normalized.append(None)

                # --- Phase 2: Batch staging INSERT ---
                staging_ids = self._insert_staging_batch(
                    stg_cursor, load_id, staging_rows
                )

                # --- Phase 2.5: Batch-fetch old records for history (updates only) ---
                update_notice_ids = [
                    notice_id for (_r, _od, notice_id, _nh, _p, old_hash)
                    in changed_records if old_hash is not None
                ]
                old_records = {}
                if update_notice_ids:
                    old_records = self._fetch_opportunity_rows(
                        cursor, update_notice_ids
                    )

                # --- Phase 3: Batch upsert changed records ---
                if changed_records:
                    try:
                        upsert_rows = []
                        for _raw, opp_data, _nid, _nh, _p, _oh in changed_records:
                            values = [opp_data.get(c) for c in _UPSERT_COLS[:-1]]
                            values.append(load_id)  # last_load_id
                            upsert_rows.append(tuple(values))

                        executemany_upsert(cursor, self._UPSERT_SQL, upsert_rows)

                        # Count inserts vs updates, upsert POCs, log history
                        all_history_rows = []
                        for _raw, opp_data, notice_id, new_hash, pocs, old_hash in changed_records:
                            if notice_id in existing_hashes:
                                stats["records_updated"] += 1
                                # History logging for updates
                                old_record = old_records.get(notice_id)
                                if old_record is not None:
                                    diffs = self.change_detector.compute_field_diff(
                                        old_record, opp_data, _OPPORTUNITY_HASH_FIELDS
                                    )
                                    if diffs:
                                        for field, old_val, new_val in diffs:
                                            all_history_rows.append((
                                                notice_id,
                                                field,
                                                _str_or_none(old_val),
                                                _str_or_none(new_val),
                                                load_id,
                                            ))
                            else:
                                stats["records_inserted"] += 1

                            # Upsert POCs (still per-record due to officer_id lookup)
                            if pocs:
                                self._upsert_pocs(cursor, notice_id, pocs)

                            existing_hashes[notice_id] = new_hash

                        # Batch insert history rows
                        if all_history_rows:
                            cursor.executemany(
                                "INSERT INTO opportunity_history "
                                "(notice_id, field_name, old_value, new_value, load_id) "
                                "VALUES (%s, %s, %s, %s, %s)",
                                all_history_rows,
                            )

                    except Exception as batch_exc:
                        self.logger.warning(
                            "Batch upsert failed (%d records), falling back to row-by-row: %s",
                            len(changed_records), batch_exc,
                        )
                        conn.rollback()
                        for raw, opp_data, notice_id, new_hash, pocs, old_hash in changed_records:
                            try:
                                outcome = self._upsert_opportunity(cursor, opp_data, load_id)
                                if outcome == "inserted":
                                    stats["records_inserted"] += 1
                                elif outcome == "updated":
                                    stats["records_updated"] += 1
                                else:
                                    stats["records_unchanged"] += 1

                                if pocs:
                                    self._upsert_pocs(cursor, notice_id, pocs)

                                old_record = old_records.get(notice_id)
                                if old_record is not None and outcome == "updated":
                                    diffs = self.change_detector.compute_field_diff(
                                        old_record, opp_data, _OPPORTUNITY_HASH_FIELDS
                                    )
                                    if diffs:
                                        self._log_changes(cursor, notice_id, diffs, load_id)

                                existing_hashes[notice_id] = new_hash
                            except Exception as rec_exc:
                                stats["records_errored"] += 1
                                self.logger.warning(
                                    "Error processing %s: %s", notice_id, rec_exc
                                )
                                self.load_manager.log_record_error(
                                    load_id,
                                    record_identifier=str(notice_id),
                                    error_type=type(rec_exc).__name__,
                                    error_message=str(rec_exc),
                                    raw_data=json.dumps(raw) if isinstance(raw, dict) else str(raw),
                                )
                                conn.rollback()

                # --- Phase 4: Batch mark staging ---
                success_staging_ids = []
                for idx, entry in enumerate(normalized):
                    if entry is not None and idx < len(staging_ids):
                        success_staging_ids.append(staging_ids[idx])
                if success_staging_ids:
                    self._mark_staging_batch(stg_cursor, success_staging_ids, 'Y')

                conn.commit()

                if stats["records_read"] % self.BATCH_SIZE == 0:
                    self.logger.info(
                        "Progress: read=%d ins=%d upd=%d unch=%d err=%d",
                        stats["records_read"],
                        stats["records_inserted"],
                        stats["records_updated"],
                        stats["records_unchanged"],
                        stats["records_errored"],
                    )

        finally:
            cursor.close()
            conn.close()
            stg_cursor.close()
            stg_conn.close()

        self.logger.info(
            "Opportunity batch complete (load_id=%d): read=%d ins=%d upd=%d unch=%d err=%d",
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

        # Awardee location (Item 1.2)
        awardee_location = self._safe_get(awardee, "location") or {}

        # Extract POC data (Item 1.1) — stored under _pocs, not a DB column
        pocs = []
        for poc in (raw.get("pointOfContact") or []):
            if not isinstance(poc, dict):
                continue
            full_name = (poc.get("fullName") or "").strip()
            if not full_name:
                continue
            pocs.append({
                "full_name":    full_name,
                "email":        (poc.get("email") or "").strip() or None,
                "phone":        (poc.get("phone") or "").strip() or None,
                "fax":          (poc.get("fax") or "").strip() or None,
                "title":        (poc.get("title") or "").strip() or None,
                "officer_type": (poc.get("type") or "").strip() or None,
            })

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
            "awardee_cage_code":     awardee.get("cageCode"),
            "awardee_city":          self._safe_get(awardee_location, "city", "name"),
            "awardee_state":         self._safe_get(awardee_location, "state", "code"),
            "awardee_zip":           awardee_location.get("zip"),
            "full_parent_path_name": parent_path or None,
            "full_parent_path_code": parent_code or None,
            "description_url":       raw.get("description"),
            "link":                  raw.get("uiLink"),
            "resource_links":        resource_links,
            "contracting_office_id": contracting_office_id,
            "_pocs":                 pocs,
        }

    # =================================================================
    # Database operations
    # =================================================================

    def _upsert_opportunity(self, cursor, opp_data, load_id):
        """INSERT ... ON DUPLICATE KEY UPDATE for the opportunity table.

        Per-record fallback method. The batch path uses executemany_upsert
        with self._UPSERT_SQL instead.

        Args:
            cursor: Active DB cursor.
            opp_data: Normalised opportunity dict.
            load_id: Current load ID.

        Returns:
            'inserted', 'updated', or 'unchanged'
        """
        values = [opp_data.get(c) for c in _UPSERT_COLS[:-1]]  # all except last_load_id
        values.append(load_id)  # last_load_id

        cursor.execute(self._UPSERT_SQL, values)

        # MySQL returns rowcount: 0 = unchanged, 1 = inserted, 2 = updated
        rc = cursor.rowcount
        if rc == 1:
            return "inserted"
        elif rc == 2:
            return "updated"
        return "unchanged"

    def _upsert_pocs(self, cursor, notice_id, pocs):
        """Upsert POC records into contracting_officer and opportunity_poc.

        For each POC:
        1. INSERT ... ON DUPLICATE KEY UPDATE into contracting_officer (dedup by full_name + email)
        2. Link via opportunity_poc junction table (notice_id + officer_id + poc_type)

        Args:
            cursor: Active DB cursor.
            notice_id: The opportunity notice_id.
            pocs: List of POC dicts from _normalize_opportunity (key '_pocs').
        """
        if not pocs:
            return

        officer_sql = (
            "INSERT INTO contracting_officer "
            "(full_name, email, phone, fax, title, officer_type) "
            "VALUES (%s, %s, %s, %s, %s, %s) "
            "ON DUPLICATE KEY UPDATE "
            "phone = COALESCE(VALUES(phone), phone), "
            "fax = COALESCE(VALUES(fax), fax), "
            "title = COALESCE(VALUES(title), title), "
            "officer_type = COALESCE(VALUES(officer_type), officer_type)"
        )

        poc_link_sql = (
            "INSERT INTO opportunity_poc (notice_id, officer_id, poc_type) "
            "VALUES (%s, %s, %s) "
            "ON DUPLICATE KEY UPDATE poc_type = VALUES(poc_type)"
        )

        for poc in pocs:
            # Upsert the contracting officer
            cursor.execute(officer_sql, (
                poc["full_name"],
                poc["email"],
                poc["phone"],
                poc["fax"],
                poc["title"],
                poc["officer_type"],
            ))

            # Get the officer_id (either newly inserted or existing)
            officer_id = cursor.lastrowid
            if officer_id == 0:
                # ON DUPLICATE KEY UPDATE: lastrowid is 0, need to look up
                cursor.execute(
                    "SELECT officer_id FROM contracting_officer "
                    "WHERE full_name = %s AND email = %s",
                    (poc["full_name"], poc["email"]),
                )
                row = cursor.fetchone()
                if row is None:
                    self.logger.warning(
                        "Could not find officer_id for %s / %s",
                        poc["full_name"], poc["email"],
                    )
                    continue
                officer_id = row["officer_id"]

            # Map POC type to uppercase for consistency
            poc_type = (poc["officer_type"] or "PRIMARY").upper()

            # Link officer to opportunity
            cursor.execute(poc_link_sql, (notice_id, officer_id, poc_type))

    # =================================================================
    # History / fetch helpers
    # =================================================================

    def _fetch_opportunity_row(self, cursor, notice_id):
        """Fetch the current opportunity row as a dict for diff comparison."""
        cursor.execute("SELECT * FROM opportunity WHERE notice_id = %s", (notice_id,))
        row = cursor.fetchone()
        if row is None:
            return None
        return self._clean_row(row)

    def _fetch_opportunity_rows(self, cursor, notice_ids):
        """Batch-fetch opportunity rows for diff comparison.

        Args:
            cursor: Active DB cursor (dictionary=True).
            notice_ids: List of notice_id strings.

        Returns:
            dict mapping notice_id -> cleaned row dict.
        """
        if not notice_ids:
            return {}

        placeholders = ", ".join(["%s"] * len(notice_ids))
        cursor.execute(
            f"SELECT * FROM opportunity WHERE notice_id IN ({placeholders})",
            notice_ids,
        )
        result = {}
        for row in cursor.fetchall():
            result[row["notice_id"]] = self._clean_row(row)
        return result

    @staticmethod
    def _clean_row(row):
        """Convert date/datetime/Decimal values to strings for comparison."""
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
    # Description text caching
    # =================================================================

    class RateLimitError(Exception):
        """Raised when SAM.gov returns 429 Too Many Requests."""
        pass

    def fetch_description_text(self, description_url):
        """Fetch description text from a SAM.gov description URL.

        The description endpoint returns JSON: {"description": "<html>..."}
        Requires an API key appended as a query parameter.

        Args:
            description_url: Full SAM.gov description URL
                (e.g. https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=...)

        Returns:
            str: The description text (HTML), or None on failure.
        """
        import requests as req
        from config import settings

        if not description_url:
            return None

        # SSRF protection: only allow SAM.gov URLs
        if not description_url.startswith("https://api.sam.gov/"):
            self.logger.warning("Skipping non-SAM.gov description URL: %s", description_url)
            return None

        # Append API key
        separator = "&" if "?" in description_url else "?"
        api_key = settings.SAM_API_KEY_2 or settings.SAM_API_KEY
        url = f"{description_url}{separator}api_key={api_key}"

        try:
            resp = req.get(url, timeout=15)
            if resp.status_code == 429:
                raise self.RateLimitError(
                    f"SAM.gov rate limit (429) hit fetching {description_url}"
                )
            resp.raise_for_status()
            data = resp.json()
            return data.get("description")
        except self.RateLimitError:
            raise
        except Exception as exc:
            self.logger.warning(
                "Failed to fetch description from %s: %s",
                description_url, exc,
            )
            return None

    def fetch_descriptions(self, batch_size=100, missing_only=True):
        """Fetch and cache description text for opportunities.

        Queries opportunities with description_url but no description_text,
        fetches the description from SAM.gov, and updates the DB.

        Args:
            batch_size: Number of opportunities to process per commit batch.
            missing_only: If True (default), only fetch for rows where
                description_text IS NULL.

        Returns:
            dict with keys: total_found, fetched, failed
        """
        import time

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        stats = {"total_found": 0, "fetched": 0, "failed": 0}

        try:
            if missing_only:
                sql = (
                    "SELECT notice_id, description_url FROM opportunity "
                    "WHERE description_text IS NULL AND description_url IS NOT NULL"
                )
            else:
                sql = (
                    "SELECT notice_id, description_url FROM opportunity "
                    "WHERE description_url IS NOT NULL"
                )
            cursor.execute(sql)
            rows = cursor.fetchall()
            stats["total_found"] = len(rows)

            self.logger.info(
                "Found %d opportunities needing description fetch", len(rows),
            )

            for i, row in enumerate(rows):
                try:
                    text = self.fetch_description_text(row["description_url"])
                    if text:
                        cursor.execute(
                            "UPDATE opportunity SET description_text = %s "
                            "WHERE notice_id = %s",
                            (text, row["notice_id"]),
                        )
                        stats["fetched"] += 1
                    else:
                        # Mark as empty string so --missing-only won't retry
                        cursor.execute(
                            "UPDATE opportunity SET description_text = '' "
                            "WHERE notice_id = %s",
                            (row["notice_id"],),
                        )
                        stats["failed"] += 1
                except self.RateLimitError:
                    self.logger.error(
                        "SAM.gov rate limit (429) hit after %d requests — "
                        "stopping description fetch. Fetched=%d, failed=%d.",
                        i, stats["fetched"], stats["failed"],
                    )
                    conn.commit()
                    break
                except Exception as exc:
                    self.logger.warning(
                        "Error fetching description for %s: %s",
                        row["notice_id"], exc,
                    )
                    # Mark as empty string so --missing-only won't retry
                    cursor.execute(
                        "UPDATE opportunity SET description_text = '' "
                        "WHERE notice_id = %s",
                        (row["notice_id"],),
                    )
                    stats["failed"] += 1

                # Commit and log progress in batches
                if (i + 1) % batch_size == 0:
                    conn.commit()
                    self.logger.info(
                        "Progress: %d/%d (fetched=%d, failed=%d)",
                        i + 1, len(rows), stats["fetched"], stats["failed"],
                    )

                # Small delay between requests to be polite
                time.sleep(0.1)
            else:
                # Final commit (only if loop completed without break)
                conn.commit()

        finally:
            cursor.close()
            conn.close()

        self.logger.info(
            "Description fetch complete: total=%d, fetched=%d, failed=%d",
            stats["total_found"], stats["fetched"], stats["failed"],
        )
        return stats

    # =================================================================
    # Resource link metadata enrichment
    # =================================================================

    def enrich_resource_links(self, notice_ids=None, batch_size=100):
        """Enrich resource_links JSON with filename/content_type metadata.

        Finds opportunities whose resource_links contain plain URL strings
        (not yet enriched objects) and HEAD-requests SAM.gov to resolve
        filenames and content types.

        Args:
            notice_ids: Optional list of notice_ids to process. If None,
                        processes all un-enriched opportunities.
            batch_size: Number of opportunities to process per batch.

        Returns:
            dict with keys: opportunities_enriched, links_resolved
        """
        from etl.resource_link_resolver import resolve_resource_links

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        stats = {"opportunities_enriched": 0, "links_resolved": 0}

        try:
            # Find opportunities needing enrichment
            if notice_ids:
                placeholders = ", ".join(["%s"] * len(notice_ids))
                sql = (
                    f"SELECT notice_id, resource_links FROM opportunity "
                    f"WHERE notice_id IN ({placeholders}) "
                    f"AND resource_links IS NOT NULL"
                )
                cursor.execute(sql, notice_ids)
            else:
                sql = (
                    "SELECT notice_id, resource_links FROM opportunity "
                    "WHERE resource_links IS NOT NULL"
                )
                cursor.execute(sql)

            rows = cursor.fetchall()
            total = len(rows)
            self.logger.info("Found %d opportunities with resource_links to check", total)

            # Filter to only those needing enrichment
            to_enrich = []
            for row in rows:
                if self._needs_enrichment(row["resource_links"]):
                    to_enrich.append(row)

            self.logger.info(
                "%d of %d opportunities need resource link enrichment",
                len(to_enrich), total,
            )

            # Process in batches
            for i in range(0, len(to_enrich), batch_size):
                batch = to_enrich[i : i + batch_size]
                batch_links = 0

                for row in batch:
                    try:
                        urls = json.loads(row["resource_links"])
                        if not urls:
                            continue

                        enriched = resolve_resource_links(urls)
                        enriched_json = json.dumps(enriched)

                        cursor.execute(
                            "UPDATE opportunity SET resource_links = %s WHERE notice_id = %s",
                            (enriched_json, row["notice_id"]),
                        )
                        stats["opportunities_enriched"] += 1
                        resolved_count = sum(1 for e in enriched if e.get("filename"))
                        stats["links_resolved"] += resolved_count
                        batch_links += len(urls)
                    except Exception as exc:
                        self.logger.warning(
                            "Error enriching resource links for %s: %s",
                            row["notice_id"], exc,
                        )

                conn.commit()
                self.logger.info(
                    "Enriched %d/%d opportunities (%d links resolved)",
                    stats["opportunities_enriched"],
                    len(to_enrich),
                    stats["links_resolved"],
                )

                # Pause between batches to avoid overwhelming SAM.gov
                if i + batch_size < len(to_enrich):
                    import time
                    time.sleep(0.5)

        finally:
            cursor.close()
            conn.close()

        return stats

    @staticmethod
    def _needs_enrichment(resource_links_json):
        """Check if resource_links JSON needs enrichment.

        Returns True if the JSON is an array of strings (old format).
        Returns False if it's an array of dicts with "url" key (already enriched),
        or if parsing fails / empty.
        """
        try:
            data = json.loads(resource_links_json)
        except (json.JSONDecodeError, TypeError):
            return False

        if not isinstance(data, list) or not data:
            return False

        # If first element is a string, needs enrichment
        # If first element is a dict with "url" key, already enriched
        first = data[0]
        if isinstance(first, str):
            return True
        if isinstance(first, dict) and "url" in first:
            return False

        return False

    # =================================================================
    # Opportunity relationship detection
    # =================================================================

    # Maps (parent_type_group, child_type_group) -> relationship_type
    _RELATIONSHIP_RULES = [
        # RFI/SRCSGT -> PRESOL or COMBINED  =>  RFI_TO_RFP
        ({"RFI", "SRCSGT"}, {"PRESOL", "COMBINED"}, "RFI_TO_RFP"),
        # PRESOL -> COMBINED  =>  PRESOL_TO_SOL
        ({"PRESOL"}, {"COMBINED"}, "PRESOL_TO_SOL"),
        # COMBINED or PRESOL -> AWARD  =>  SOL_TO_AWARD
        ({"COMBINED", "PRESOL"}, {"AWARD"}, "SOL_TO_AWARD"),
    ]

    def populate_relationships(self):
        """Detect and populate opportunity_relationship rows from existing data.

        Finds opportunities sharing the same solicitation_number, detects
        lifecycle progressions (RFI->RFP, PRESOL->SOL, SOL->AWARD), and
        inserts relationship rows using INSERT IGNORE to handle re-runs.

        Returns:
            dict with counts by relationship type and total.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        stats = {"RFI_TO_RFP": 0, "PRESOL_TO_SOL": 0, "SOL_TO_AWARD": 0, "total": 0}

        try:
            # Find all solicitation_numbers with 2+ opportunities
            cursor.execute(
                "SELECT solicitation_number, "
                "       GROUP_CONCAT(notice_id ORDER BY posted_date, notice_id) AS notice_ids, "
                "       GROUP_CONCAT(type ORDER BY posted_date, notice_id) AS types "
                "FROM opportunity "
                "WHERE solicitation_number IS NOT NULL "
                "  AND solicitation_number != '' "
                "GROUP BY solicitation_number "
                "HAVING COUNT(*) >= 2"
            )
            groups = cursor.fetchall()
            self.logger.info(
                "Found %d solicitation_number groups with 2+ opportunities",
                len(groups),
            )

            insert_sql = (
                "INSERT IGNORE INTO opportunity_relationship "
                "(parent_notice_id, child_notice_id, relationship_type) "
                "VALUES (%s, %s, %s)"
            )

            batch_count = 0
            for group in groups:
                notice_ids = group["notice_ids"].split(",")
                types = group["types"].split(",")

                if len(notice_ids) != len(types):
                    continue

                # Build pairs: compare each earlier notice to each later notice
                for i in range(len(notice_ids)):
                    for j in range(i + 1, len(notice_ids)):
                        parent_id = notice_ids[i]
                        child_id = notice_ids[j]
                        parent_type = types[i]
                        child_type = types[j]

                        # Skip if same type (e.g., two COMBINEDs = amendments)
                        if parent_type == child_type:
                            continue

                        # Skip if same notice_id
                        if parent_id == child_id:
                            continue

                        # Check against rules
                        for parent_set, child_set, rel_type in self._RELATIONSHIP_RULES:
                            if parent_type in parent_set and child_type in child_set:
                                cursor.execute(insert_sql, (parent_id, child_id, rel_type))
                                if cursor.rowcount > 0:
                                    stats[rel_type] += 1
                                    stats["total"] += 1
                                    batch_count += 1
                                break

                if batch_count >= 500:
                    conn.commit()
                    batch_count = 0

            conn.commit()

        finally:
            cursor.close()
            conn.close()

        self.logger.info(
            "Relationship population complete: RFI_TO_RFP=%d PRESOL_TO_SOL=%d "
            "SOL_TO_AWARD=%d total=%d",
            stats["RFI_TO_RFP"],
            stats["PRESOL_TO_SOL"],
            stats["SOL_TO_AWARD"],
            stats["total"],
        )
        return stats

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
