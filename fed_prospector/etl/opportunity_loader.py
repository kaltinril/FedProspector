"""Opportunity loader: transforms SAM.gov opportunity API data into MySQL.

Loads opportunity records from the SAM.gov Opportunities API, with
change detection via SHA-256 hashing and field-level history tracking.
Follows the same patterns as entity_loader.py.
"""

import json
import logging
import re
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
    "department_name", "department_cgac", "sub_tier", "sub_tier_code", "office",
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
    "department_name", "department_cgac", "sub_tier", "sub_tier_code", "office",
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
    "fh_org_id",
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
        self._fh_org_cache = None  # Lazy-loaded in _get_fh_org_cache()

    def _get_fh_org_cache(self):
        """Build/return cached lookups for fh_org_id resolution.

        Returns dict with:
          'subtier': {agency_code -> fh_org_id} for Sub-Tier orgs
          'dept':    {cgac -> fh_org_id} for Department/Ind. Agency level-1 orgs
        """
        if self._fh_org_cache is not None:
            return self._fh_org_cache

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Sub-Tier: agency_code -> fh_org_id (unique per the plan)
            cursor.execute(
                "SELECT agency_code, fh_org_id FROM federal_organization "
                "WHERE fh_org_type = 'Sub-Tier' AND agency_code IS NOT NULL"
            )
            subtier = {row[0]: row[1] for row in cursor.fetchall()}

            # Department: cgac -> fh_org_id (level 1)
            cursor.execute(
                "SELECT cgac, MIN(fh_org_id) FROM federal_organization "
                "WHERE fh_org_type = 'Department/Ind. Agency' AND level = 1 "
                "AND cgac IS NOT NULL GROUP BY cgac"
            )
            dept = {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            cursor.close()
            conn.close()

        self._fh_org_cache = {"subtier": subtier, "dept": dept}
        self.logger.info(
            "fh_org_id cache loaded: %d sub-tier, %d department codes",
            len(subtier), len(dept),
        )
        return self._fh_org_cache

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
                    pre_phase3_stats = {
                        "records_inserted": stats["records_inserted"],
                        "records_updated": stats["records_updated"],
                        "records_unchanged": stats["records_unchanged"],
                        "records_errored": stats["records_errored"],
                    }
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
                            if old_hash is not None:
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
                        # Reset stats so the fallback loop doesn't double-count
                        # any records that were tallied before the exception.
                        stats["records_inserted"] = pre_phase3_stats["records_inserted"]
                        stats["records_updated"] = pre_phase3_stats["records_updated"]
                        stats["records_unchanged"] = pre_phase3_stats["records_unchanged"]
                        stats["records_errored"] = pre_phase3_stats["records_errored"]
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
                                # Extract column name from "Data too long for column 'X'" errors
                                err_detail = str(rec_exc)
                                col_match = re.search(r"column '(\w+)'", err_detail)
                                if col_match:
                                    col_name = col_match.group(1)
                                    val = opp_data.get(col_name) if opp_data else None
                                    if val is None and pocs:
                                        for p in pocs:
                                            if col_name in p:
                                                val = p[col_name]
                                                break
                                    err_detail += f" — len={len(str(val)) if val else 0}, value={val!r}"
                                self.logger.warning(
                                    "Error processing %s: %s", notice_id, err_detail
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

                # Progress logging only at 5000+ record intervals to reduce noise
                if stats["records_read"] % 5000 == 0:
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

        # JSON-encode resource links (skip if already a JSON string)
        resource_links_raw = raw.get("resourceLinks")
        if resource_links_raw is None:
            resource_links = None
        elif isinstance(resource_links_raw, str):
            resource_links = resource_links_raw
        else:
            resource_links = json.dumps(resource_links_raw)

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

        # Parse code hierarchy — save all three segments
        parent_code = raw.get("fullParentPathCode") or ""
        code_parts = [p.strip() for p in parent_code.split(".")] if parent_code else []
        department_cgac = code_parts[0] if len(code_parts) >= 1 else None
        sub_tier_code = code_parts[1] if len(code_parts) >= 2 else None
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
                "full_name":    full_name[:500],
                "email":        ((poc.get("email") or "").strip()[:200]) or None,
                "phone":        ((poc.get("phone") or "").strip()[:100]) or None,
                "fax":          ((poc.get("fax") or "").strip()[:100]) or None,
                "title":        ((poc.get("title") or "").strip()[:200]) or None,
                "officer_type": ((poc.get("type") or "").strip()[:50]) or None,
            })

        # Resolve fh_org_id from cached federal_organization data
        fh_org_id = None
        cache = self._get_fh_org_cache()
        if sub_tier_code:
            fh_org_id = cache["subtier"].get(sub_tier_code)
        if fh_org_id is None and department_cgac:
            fh_org_id = cache["dept"].get(department_cgac)

        return {
            "notice_id":             raw.get("noticeId"),
            "title":                 raw.get("title"),
            "solicitation_number":   raw.get("solicitationNumber"),
            "department_name":       department_name,
            "department_cgac":       department_cgac,
            "sub_tier":              sub_tier,
            "sub_tier_code":         sub_tier_code,
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
            "fh_org_id":             fh_org_id,
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
                # ON DUPLICATE KEY UPDATE: lastrowid is 0, need to look up.
                # Use NULL-safe equality (<=>) so a row with NULL email is
                # matched correctly — the unique key is (full_name, email).
                cursor.execute(
                    "SELECT officer_id FROM contracting_officer "
                    "WHERE full_name = %s AND email <=> %s",
                    (poc["full_name"], poc["email"]),
                )
                row = cursor.fetchone()
                if row is None:
                    raise RuntimeError(
                        f"contracting_officer lookup returned no row after "
                        f"upsert for full_name={poc['full_name']!r} "
                        f"email={poc['email']!r}"
                    )
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

    _NOT_FOUND = object()  # Sentinel for permanent 404/410 responses

    def fetch_description_text(self, description_url, api_key_number=2):
        """Fetch description text from a SAM.gov description URL.

        The description endpoint returns JSON: {"description": "<html>..."}
        Requires an API key appended as a query parameter.

        Args:
            description_url: Full SAM.gov description URL
                (e.g. https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=...)
            api_key_number: Which API key to use (1=free 10/day, 2=1000/day).

        Returns:
            str: The description text (HTML), _NOT_FOUND on 404/410, or None
            on transient failure.
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
        if api_key_number == 1:
            api_key = settings.SAM_API_KEY
        else:
            api_key = settings.SAM_API_KEY_2 or settings.SAM_API_KEY
        url = f"{description_url}{separator}api_key={api_key}"

        try:
            resp = req.get(url, timeout=15)
            if resp.status_code == 429:
                raise self.RateLimitError(
                    f"SAM.gov rate limit (429) hit fetching {description_url}"
                )
            if resp.status_code in (404, 410):
                return self._NOT_FOUND
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

    def _fetch_description_batch(self, rows, api_key_number, batch_size,
                                stats, cursor, conn, limit_remaining=None):
        """Fetch descriptions for a list of opportunity rows.

        Args:
            rows: List of dicts with notice_id and description_url.
            api_key_number: Which API key to use.
            batch_size: Number of opportunities to process per commit batch.
            stats: Mutable dict to accumulate fetched/failed counts.
            cursor: Open DB cursor.
            conn: Open DB connection.
            limit_remaining: Max API calls to make, or None for unlimited.

        Returns:
            int: Number of API calls made (fetched + failed).
        """
        import time

        calls_made = 0
        rate_limited = False

        for i, row in enumerate(rows):
            if limit_remaining is not None and calls_made >= limit_remaining:
                break

            try:
                text = self.fetch_description_text(
                    row["description_url"], api_key_number=api_key_number,
                )
                if text is self._NOT_FOUND:
                    cursor.execute(
                        "UPDATE opportunity "
                        "SET description_text = '', "
                        "    description_fetch_failures = description_fetch_failures + 1 "
                        "WHERE notice_id = %s",
                        (row["notice_id"],),
                    )
                    stats["failed"] += 1
                elif text:
                    cursor.execute(
                        "UPDATE opportunity SET description_text = %s, "
                        "    description_fetch_failures = 0 "
                        "WHERE notice_id = %s",
                        (text, row["notice_id"]),
                    )
                    stats["fetched"] += 1
                else:
                    # Transient failure (None) — mark empty so --missing-only won't retry immediately
                    cursor.execute(
                        "UPDATE opportunity SET description_text = '' "
                        "WHERE notice_id = %s",
                        (row["notice_id"],),
                    )
                    stats["failed"] += 1
                calls_made += 1
            except self.RateLimitError:
                self.logger.error(
                    "SAM.gov rate limit (429) hit after %d requests — "
                    "stopping description fetch. Fetched=%d, failed=%d.",
                    calls_made, stats["fetched"], stats["failed"],
                )
                conn.commit()
                rate_limited = True
                break
            except Exception as exc:
                self.logger.warning(
                    "Error fetching description for %s: %s",
                    row["notice_id"], exc,
                )
                cursor.execute(
                    "UPDATE opportunity SET description_text = '' "
                    "WHERE notice_id = %s",
                    (row["notice_id"],),
                )
                stats["failed"] += 1
                calls_made += 1

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

        if rate_limited:
            # Return negative to signal rate limit to caller
            return -1

        # Commit any remaining uncommitted rows
        conn.commit()
        return calls_made

    def fetch_descriptions(self, batch_size=100, missing_only=True,
                           days_back=None, notice_id=None, api_key_number=2,
                           naics_codes=None, set_aside_codes=None, limit=None):
        """Fetch and cache description text for opportunities.

        Queries opportunities with description_url but no description_text,
        fetches the description from SAM.gov, and updates the DB.

        When naics_codes or set_aside_codes are provided, performs a
        prioritized two-pass fetch: first fetches descriptions for
        opportunities matching those filters, then uses remaining budget
        for all other opportunities.

        Args:
            batch_size: Number of opportunities to process per commit batch.
            missing_only: If True (default), only fetch for rows where
                description_text IS NULL.
            days_back: If set, only fetch for opportunities posted in the
                last N days.
            notice_id: If set, fetch for a single notice ID.
            api_key_number: Which API key to use (1=free 10/day, 2=1000/day).
            naics_codes: Optional list of NAICS codes for priority fetch.
            set_aside_codes: Optional list of set-aside codes for priority fetch.
            limit: Max total descriptions to fetch (default: unlimited).

        Returns:
            dict with keys: total_found, fetched, failed, priority_fetched
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        stats = {"total_found": 0, "fetched": 0, "failed": 0, "priority_fetched": 0}
        prioritized = (naics_codes or set_aside_codes) and not notice_id

        try:
            if notice_id:
                # --- Single notice fetch (unchanged) ---
                conditions = ["description_url IS NOT NULL"]
                params = []
                if missing_only:
                    conditions.append("description_text IS NULL")
                conditions.append("notice_id = %s")
                params.append(notice_id)

                sql = (
                    "SELECT notice_id, description_url FROM opportunity "
                    "WHERE " + " AND ".join(conditions) +
                    " ORDER BY posted_date DESC"
                )
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                stats["total_found"] = len(rows)
                self.logger.info(
                    "Found %d opportunities needing description fetch", len(rows),
                )
                self._fetch_description_batch(
                    rows, api_key_number, batch_size, stats, cursor, conn,
                    limit_remaining=limit,
                )

            elif prioritized:
                # --- Priority pass: NAICS + set-aside filtered ---
                # Priority gets up to half the limit; no days_back filter,
                # but only active opportunities (response_deadline >= today).
                priority_limit = limit // 2 if limit else None
                conditions = ["description_url IS NOT NULL",
                              "description_fetch_failures < 3"]
                params = []
                if missing_only:
                    conditions.append("description_text IS NULL")
                conditions.append("response_deadline >= CURDATE()")
                if naics_codes:
                    conditions.append(
                        "naics_code IN (%s)" % ",".join(["%s"] * len(naics_codes))
                    )
                    params.extend(naics_codes)
                if set_aside_codes:
                    conditions.append(
                        "set_aside_code IN (%s)" % ",".join(["%s"] * len(set_aside_codes))
                    )
                    params.extend(set_aside_codes)

                sql = (
                    "SELECT notice_id, description_url FROM opportunity "
                    "WHERE " + " AND ".join(conditions) +
                    " ORDER BY posted_date DESC"
                )
                cursor.execute(sql, params)
                priority_rows = cursor.fetchall()
                stats["total_found"] += len(priority_rows)
                self.logger.info(
                    "Priority pass: found %d opportunities (NAICS+set-aside filtered, active only)",
                    len(priority_rows),
                )

                priority_calls = self._fetch_description_batch(
                    priority_rows, api_key_number, batch_size, stats, cursor, conn,
                    limit_remaining=priority_limit,
                )
                stats["priority_fetched"] = stats["fetched"]
                self.logger.info(
                    "Priority pass: fetched %d/%d (NAICS+set-aside filtered)",
                    stats["priority_fetched"], len(priority_rows),
                )

                # --- Remaining budget pass ---
                if priority_calls >= 0:  # not rate limited
                    budget_used = stats["fetched"] + stats["failed"]
                    remaining = None
                    if limit is not None:
                        remaining = limit - budget_used  # full limit minus priority usage
                        if remaining <= 0:
                            self.logger.info(
                                "Limit reached after priority pass, skipping remaining budget pass"
                            )
                        else:
                            self.logger.info(
                                "Remaining budget pass: %d calls remaining", remaining,
                            )

                    if remaining is None or remaining > 0:
                        conditions2 = ["description_url IS NOT NULL",
                                       "description_fetch_failures < 3"]
                        params2 = []
                        if missing_only:
                            conditions2.append("description_text IS NULL")
                        if days_back is not None:
                            conditions2.append(
                                "posted_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)"
                            )
                            params2.append(days_back)

                        # Exclude priority opportunities
                        exclude_parts = []
                        if naics_codes:
                            exclude_parts.append(
                                "naics_code IN (%s)" % ",".join(["%s"] * len(naics_codes))
                            )
                            params2.extend(naics_codes)
                        if set_aside_codes:
                            exclude_parts.append(
                                "set_aside_code IN (%s)" % ",".join(["%s"] * len(set_aside_codes))
                            )
                            params2.extend(set_aside_codes)
                        if exclude_parts:
                            conditions2.append(
                                "NOT (%s)" % " AND ".join(exclude_parts)
                            )

                        sql2 = (
                            "SELECT notice_id, description_url FROM opportunity "
                            "WHERE " + " AND ".join(conditions2) +
                            " ORDER BY posted_date DESC"
                        )
                        cursor.execute(sql2, params2)
                        remaining_rows = cursor.fetchall()
                        stats["total_found"] += len(remaining_rows)
                        self.logger.info(
                            "Remaining budget pass: found %d opportunities (all others)",
                            len(remaining_rows),
                        )

                        fetched_before = stats["fetched"]
                        self._fetch_description_batch(
                            remaining_rows, api_key_number, batch_size, stats,
                            cursor, conn, limit_remaining=remaining,
                        )
                        self.logger.info(
                            "Remaining budget pass: fetched %d/%d (all opportunities)",
                            stats["fetched"] - fetched_before, len(remaining_rows),
                        )

            else:
                # --- General pass (no priority filters) ---
                conditions = ["description_url IS NOT NULL",
                              "description_fetch_failures < 3"]
                params = []
                if missing_only:
                    conditions.append("description_text IS NULL")
                if days_back is not None:
                    conditions.append(
                        "posted_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)"
                    )
                    params.append(days_back)

                sql = (
                    "SELECT notice_id, description_url FROM opportunity "
                    "WHERE " + " AND ".join(conditions) +
                    " ORDER BY posted_date DESC"
                )
                cursor.execute(sql, params)
                rows = cursor.fetchall()
                stats["total_found"] = len(rows)
                self.logger.info(
                    "Found %d opportunities needing description fetch", len(rows),
                )
                self._fetch_description_batch(
                    rows, api_key_number, batch_size, stats, cursor, conn,
                    limit_remaining=limit,
                )

        finally:
            cursor.close()
            conn.close()

        self.logger.info(
            "Description fetch complete: total=%d, fetched=%d, failed=%d, priority=%d",
            stats["total_found"], stats["fetched"], stats["failed"],
            stats["priority_fetched"],
        )
        return stats

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
