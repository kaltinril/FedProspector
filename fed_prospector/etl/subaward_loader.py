"""SAM.gov Subaward loader.

Transforms SAM.gov Acquisition Subaward Reporting API responses into the
sam_subaward table. Follows the same patterns as exclusions_loader.py:
batch upserts with change detection via SHA-256 hashing.

The sam_subaward table has a single-column auto-increment PK (id).
Change detection uses prime_piid as the logical key for hash lookups.
"""

import json
import logging
from datetime import datetime, date

from db.connection import get_connection
from etl.change_detector import ChangeDetector
from etl.load_manager import LoadManager
from etl.etl_utils import parse_date, parse_decimal
from etl.staging_mixin import StagingMixin


logger = logging.getLogger("fed_prospector.etl.subaward_loader")

# Fields used for record hash (business-meaningful fields only;
# excludes load-tracking timestamps)
_SUBAWARD_HASH_FIELDS = [
    "prime_piid", "prime_agency_id", "prime_agency_name",
    "prime_uei", "prime_name",
    "sub_uei", "sub_name", "sub_amount", "sub_date",
    "sub_description", "naics_code", "psc_code",
    "sub_business_type",
    "pop_state", "pop_country", "pop_zip",
    "recovery_model_q1", "recovery_model_q2",
]

# All sam_subaward columns used in upsert (order matters for values list)
_UPSERT_COLS = [
    "prime_piid", "prime_agency_id", "prime_agency_name",
    "prime_uei", "prime_name",
    "sub_uei", "sub_name", "sub_amount", "sub_date",
    "sub_description", "naics_code", "psc_code",
    "sub_business_type",
    "pop_state", "pop_country", "pop_zip",
    "recovery_model_q1", "recovery_model_q2",
    "record_hash", "last_load_id",
]


def _make_subaward_key(record):
    """Build a composite key string for hash lookups.

    Uses prime_piid + sub_uei + sub_date as the logical key.
    """
    piid = record.get("prime_piid") or ""
    sub_uei = record.get("sub_uei") or ""
    sub_date = record.get("sub_date") or ""
    return f"{piid}|{sub_uei}|{sub_date}"


class SubawardLoader(StagingMixin):
    """Load SAM.gov Subaward API data into sam_subaward table.

    Usage:
        loader = SubawardLoader()
        load_id = loader.load_manager.start_load("SAM_SUBAWARD", "FULL")
        stats = loader.load_subawards(subaward_data, load_id)
        loader.load_manager.complete_load(load_id, **stats)
    """

    BATCH_SIZE = 500
    _STG_TABLE = "stg_subaward_raw"
    _STG_KEY_COLS = ["prime_piid", "sub_uei"]

    def __init__(self, db_connection=None, change_detector=None, load_manager=None):
        """Initialize with optional DB connection, change detector, load manager.

        Args:
            db_connection: Not used (connections obtained from pool). Kept for
                           interface compatibility.
            change_detector: Optional ChangeDetector instance.
            load_manager: Optional LoadManager instance.
        """
        self.logger = logging.getLogger("fed_prospector.etl.subaward_loader")
        self.change_detector = change_detector or ChangeDetector()
        self.load_manager = load_manager or LoadManager()

    # =================================================================
    # Public entry points
    # =================================================================

    def load_subawards(self, subawards_data, load_id):
        """Main entry point. Process list of raw SAM Subaward API response dicts.

        Args:
            subawards_data: list of raw subaward dicts from SAM Subaward API
                (items from the data[] array).
            load_id: etl_load_log ID for this load.

        Returns:
            dict with keys: records_read, records_inserted, records_updated,
                records_unchanged, records_errored.
        """
        # Materialize generator (if any) to allow len() and re-iteration.
        subawards_data = list(subawards_data)
        self.logger.info(
            "Starting SAM Subaward load (%d records, load_id=%d)",
            len(subawards_data), load_id,
        )

        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_unchanged": 0,
            "records_errored": 0,
        }

        # Pre-fetch existing hashes keyed on composite prime_piid|sub_uei.
        # Keying on prime_piid alone caused hash collisions when a prime had
        # multiple subawards: the dict only retained the last hash per prime,
        # which silently skipped real updates for other subawards on that prime.
        # Fixed: composite key now prevents this collision.
        conn_h = get_connection()
        cur_h = conn_h.cursor()
        try:
            cur_h.execute(
                "SELECT CONCAT(COALESCE(prime_piid,''), '|', COALESCE(sub_uei,'')), record_hash "
                "FROM sam_subaward WHERE record_hash IS NOT NULL"
            )
            existing_hashes = {row[0]: row[1] for row in cur_h.fetchall()}
        finally:
            cur_h.close()
            conn_h.close()

        # Staging connection: autocommit=True so each staging row is committed
        # immediately and independently of the main batch-commit connection.
        stg_conn, stg_cursor = self._open_stg_conn()

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            batch_count = 0
            for raw in subawards_data:
                stats["records_read"] += 1
                record_key = None
                staging_id = None
                try:
                    # --- staging write (before normalization) --------------
                    key_vals = self._extract_staging_key(raw)
                    staging_id = self._insert_staging(stg_cursor, load_id, key_vals, raw)

                    # --- normalise ----------------------------------------
                    subaward_data = self._normalize_subaward(raw)
                    record_key = (
                        f"{subaward_data.get('prime_piid', '')}"
                        f"|{subaward_data.get('sub_uei', '')}"
                    )

                    # --- change detection ---------------------------------
                    new_hash = self.change_detector.compute_hash(
                        subaward_data, _SUBAWARD_HASH_FIELDS
                    )
                    subaward_data["record_hash"] = new_hash

                    old_hash = existing_hashes.get(record_key)
                    if old_hash and old_hash == new_hash:
                        stats["records_unchanged"] += 1
                        self._mark_staging(stg_cursor, staging_id, "Y")
                        batch_count += 1
                        if batch_count >= self.BATCH_SIZE:
                            conn.commit()
                            batch_count = 0
                        continue

                    # --- upsert -------------------------------------------
                    outcome = self._upsert_subaward(cursor, subaward_data, load_id)
                    if outcome == "inserted":
                        stats["records_inserted"] += 1
                    elif outcome == "updated":
                        stats["records_updated"] += 1
                    else:
                        stats["records_unchanged"] += 1

                    # Update in-memory hash cache
                    existing_hashes[record_key] = new_hash

                    self._mark_staging(stg_cursor, staging_id, "Y")

                except Exception as rec_exc:
                    stats["records_errored"] += 1
                    identifier = record_key or f"record#{stats['records_read']}"
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
                        self._mark_staging(stg_cursor, staging_id, "E", str(rec_exc))
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
            "SAM Subaward load complete (load_id=%d): read=%d ins=%d upd=%d unch=%d err=%d",
            load_id,
            stats["records_read"],
            stats["records_inserted"],
            stats["records_updated"],
            stats["records_unchanged"],
            stats["records_errored"],
        )
        return stats

    def load_subaward_batch(self, batch_data, load_id):
        """Process a batch of subawards under an existing load_id.

        Unlike load_subawards, does NOT create or complete the load
        entry -- the caller manages the load lifecycle. Used for page-by-page
        loading where progress is saved after each page.

        Args:
            batch_data: List of raw subaward dicts (from one API page).
            load_id: Existing load_id from LoadManager.start_load().

        Returns:
            dict with batch statistics (records_read, records_inserted, etc.).
        """
        return self.load_subawards(batch_data, load_id)

    def full_refresh(self, client, load_id, **search_kwargs):
        """Reload subawards from the API using the provided search filters.

        Fetches subaward records via the client and loads them into
        the sam_subaward table. Existing records are updated via change
        detection; truly new records are inserted.

        Args:
            client: SAMSubawardClient instance (already configured with API key).
            load_id: etl_load_log ID for this load.
            **search_kwargs: Filters passed to client.search_subcontracts_all().

        Returns:
            dict with load stats.
        """
        self.logger.info("Starting subaward refresh (load_id=%d)", load_id)

        all_subawards = list(client.search_subcontracts_all(**search_kwargs))
        self.logger.info("Fetched %d subaward records from API", len(all_subawards))

        return self.load_subawards(all_subawards, load_id)

    def find_teaming_partners(self, naics_code=None, min_subawards=2, limit=50):
        """Find primes who frequently subcontract to small businesses.

        Queries the local sam_subaward table to identify prime contractors
        that have awarded multiple subcontracts, optionally filtered by NAICS.
        Useful for identifying potential teaming partners.

        Args:
            naics_code: Optional NAICS code filter.
            min_subawards: Minimum number of subcontracts to qualify (default: 2).
            limit: Maximum number of primes to return (default: 50).

        Returns:
            list[dict]: Prime contractors with sub counts. Each dict has keys:
                prime_uei, prime_name, sub_count, total_sub_amount,
                unique_subs, naics_codes.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            where_clause = ""
            params = []
            if naics_code:
                where_clause = "WHERE s.naics_code = %s"
                params.append(naics_code)

            sql = f"""
                SELECT
                    s.prime_uei,
                    s.prime_name,
                    COUNT(*) AS sub_count,
                    SUM(s.sub_amount) AS total_sub_amount,
                    COUNT(DISTINCT s.sub_uei) AS unique_subs,
                    GROUP_CONCAT(DISTINCT s.naics_code ORDER BY s.naics_code SEPARATOR ', ')
                        AS naics_codes
                FROM sam_subaward s
                {where_clause}
                GROUP BY s.prime_uei, s.prime_name
                HAVING COUNT(*) >= %s
                ORDER BY sub_count DESC
                LIMIT %s
            """
            params.extend([min_subawards, limit])

            cursor.execute(sql, params)
            results = cursor.fetchall()

            self.logger.info(
                "Teaming partner search: found %d primes with >= %d subcontracts%s",
                len(results), min_subawards,
                f" (NAICS {naics_code})" if naics_code else "",
            )
            return results
        finally:
            cursor.close()
            conn.close()

    # =================================================================
    # Raw staging helpers
    # =================================================================

    def _extract_staging_key(self, raw):
        """Return natural key fields for stg_subaward_raw from a raw API record.

        Args:
            raw: Single raw subaward dict from SAM Subaward API.

        Returns:
            dict with prime_piid and sub_uei.
        """
        return {
            "prime_piid": raw.get("piid", "") or "",
            "sub_uei": raw.get("subEntityUei", "") or "",
        }

    # =================================================================
    # Normalisation
    # =================================================================

    def _normalize_subaward(self, raw):
        """Flatten the SAM Subaward API response to a flat dict matching
        sam_subaward columns.

        Args:
            raw: Single subaward dict from SAM Subaward API data[].

        Returns:
            dict: Normalised subaward data matching sam_subaward columns.
        """
        # Extract nested organization info
        org_info = raw.get("primeOrganizationInfo") or {}
        contracting_agency = org_info.get("contractingAgency") or {}

        # Extract nested address info — try placeOfPerformance first, fall back to entityPhysicalAddress
        pop_address = raw.get("placeOfPerformance") or {}
        address = pop_address if pop_address else (raw.get("entityPhysicalAddress") or {})
        state_obj = address.get("state") or {}
        country_obj = address.get("country") or {}

        # Extract business types as comma-separated string
        biz_types = raw.get("subBusinessType") or []
        biz_type_str = None
        if biz_types:
            codes = [bt.get("code", "") for bt in biz_types if bt.get("code")]
            biz_type_str = ", ".join(codes) if codes else None

        # SAM.gov returns some fields as objects (code/description) in live
        # responses but as plain strings in test fixtures — handle both.
        _naics = raw.get("primeNaics")
        _rmq1 = raw.get("recoveryModelQ1")
        _rmq2 = raw.get("recoveryModelQ2")
        _desc = raw.get("subAwardDescription")

        return {
            "prime_piid":         raw.get("piid"),
            "prime_agency_id":    contracting_agency.get("code") or raw.get("agencyId"),
            "prime_agency_name":  contracting_agency.get("name"),
            "prime_uei":          raw.get("primeEntityUei"),
            "prime_name":         raw.get("primeEntityName"),
            "sub_uei":            raw.get("subEntityUei"),
            "sub_name":           raw.get("subEntityLegalBusinessName"),
            "sub_amount":         parse_decimal(raw.get("subAwardAmount")),
            "sub_date":           parse_date(raw.get("subAwardDate")),
            "sub_description":    _desc.get("description") if isinstance(_desc, dict) else _desc,
            "naics_code":         _naics.get("code") if isinstance(_naics, dict) else _naics,
            "psc_code":           None,  # Not in API response
            "sub_business_type":  biz_type_str,
            "pop_state":          state_obj.get("code") if isinstance(state_obj, dict) else state_obj,
            "pop_country":        country_obj.get("code") if isinstance(country_obj, dict) else country_obj,
            "pop_zip":            address.get("zip"),
            "recovery_model_q1":  _rmq1.get("description") if isinstance(_rmq1, dict) else _rmq1,
            "recovery_model_q2":  _rmq2.get("description") if isinstance(_rmq2, dict) else _rmq2,
        }

    # =================================================================
    # Database operations
    # =================================================================

    def _upsert_subaward(self, cursor, subaward_data, load_id):
        """INSERT or UPDATE for sam_subaward.

        Since there is no natural unique key on subawards (the PK is auto-increment),
        we check for existing records by matching on prime_piid + sub_uei + sub_date.
        If found, we update; otherwise we insert.

        Args:
            cursor: Active DB cursor.
            subaward_data: Normalised subaward dict.
            load_id: Current load ID.

        Returns:
            'inserted', 'updated', or 'unchanged'.
        """
        prime_piid = subaward_data.get("prime_piid")
        sub_uei = subaward_data.get("sub_uei")
        sub_date = subaward_data.get("sub_date")

        # Use NULL-safe comparison (<=> ) for nullable composite key fields
        cursor.execute(
            "SELECT id, record_hash FROM sam_subaward "
            "WHERE prime_piid <=> %s AND sub_uei <=> %s AND sub_date <=> %s "
            "LIMIT 1",
            (prime_piid, sub_uei, sub_date),
        )

        existing = cursor.fetchone()

        if existing:
            # Update existing record
            existing_id = existing["id"]
            set_pairs = ", ".join(f"{c} = %s" for c in _UPSERT_COLS)
            sql = (
                f"UPDATE sam_subaward SET {set_pairs}, last_updated_at = NOW() "
                f"WHERE id = %s"
            )
            values = [subaward_data.get(c) if c != "last_load_id" else load_id
                      for c in _UPSERT_COLS]
            values.append(existing_id)
            cursor.execute(sql, values)
            return "updated"
        else:
            # Insert new record
            col_list = ", ".join(_UPSERT_COLS)
            placeholders = ", ".join(["%s"] * len(_UPSERT_COLS))
            sql = (
                f"INSERT INTO sam_subaward ({col_list}, first_loaded_at, last_updated_at) "
                f"VALUES ({placeholders}, NOW(), NOW())"
            )
            values = [subaward_data.get(c) if c != "last_load_id" else load_id
                      for c in _UPSERT_COLS]
            cursor.execute(sql, values)
            return "inserted"

    # =================================================================
    # Hash fields accessor
    # =================================================================

    @staticmethod
    def get_hash_fields():
        """Return the list of fields used for subaward record hashing."""
        return list(_SUBAWARD_HASH_FIELDS)
