"""SAM.gov Subaward loader.

Transforms SAM.gov Acquisition Subaward Reporting API responses into the
sam_subaward table. Follows the same patterns as exclusions_loader.py:
batch upserts with change detection via SHA-256 hashing.

The sam_subaward table has a single-column auto-increment PK (id).
Change detection uses a composite of prime_piid|sub_uei|sub_date
as the logical key for hash lookups.
"""

import json
import logging
from datetime import datetime, date

from db.connection import get_connection
from etl.change_detector import ChangeDetector
from etl.load_manager import LoadManager


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


class SubawardLoader:
    """Load SAM.gov Subaward API data into sam_subaward table.

    Usage:
        loader = SubawardLoader()
        load_id = loader.load_manager.start_load("SAM_SUBAWARD", "FULL")
        stats = loader.load_subawards(subaward_data, load_id)
        loader.load_manager.complete_load(load_id, **stats)
    """

    BATCH_SIZE = 500

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

        # Pre-fetch existing hashes for change detection.
        existing_hashes = self._get_existing_hashes()

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            batch_count = 0
            for raw in subawards_data:
                stats["records_read"] += 1
                record_key = None
                try:
                    # --- normalise ----------------------------------------
                    subaward_data = self._normalize_subaward(raw)
                    record_key = _make_subaward_key(subaward_data)

                    # --- change detection ---------------------------------
                    new_hash = self.change_detector.compute_hash(
                        subaward_data, _SUBAWARD_HASH_FIELDS
                    )
                    subaward_data["record_hash"] = new_hash

                    old_hash = existing_hashes.get(record_key)
                    if old_hash and old_hash == new_hash:
                        stats["records_unchanged"] += 1
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

        # Extract nested address info
        address = raw.get("entityPhysicalAddress") or {}
        state_obj = address.get("state") or {}
        country_obj = address.get("country") or {}

        # Extract business types as comma-separated string
        biz_types = raw.get("subBusinessType") or []
        biz_type_str = None
        if biz_types:
            codes = [bt.get("code", "") for bt in biz_types if bt.get("code")]
            biz_type_str = ", ".join(codes) if codes else None

        return {
            "prime_piid":         raw.get("piid"),
            "prime_agency_id":    contracting_agency.get("code") or raw.get("agencyId"),
            "prime_agency_name":  contracting_agency.get("name"),
            "prime_uei":          raw.get("primeEntityUei"),
            "prime_name":         raw.get("primeEntityName"),
            "sub_uei":            raw.get("subEntityUei"),
            "sub_name":           raw.get("subEntityLegalBusinessName"),
            "sub_amount":         self._parse_amount(raw.get("subAwardAmount")),
            "sub_date":           self._parse_date(raw.get("subAwardDate")),
            "sub_description":    raw.get("subAwardDescription"),
            "naics_code":         raw.get("primeNaics"),
            "psc_code":           None,  # Not in API response
            "sub_business_type":  biz_type_str,
            "pop_state":          state_obj.get("code"),
            "pop_country":        country_obj.get("code"),
            "pop_zip":            address.get("zip"),
            "recovery_model_q1":  raw.get("recoveryModelQ1"),
            "recovery_model_q2":  raw.get("recoveryModelQ2"),
        }

    # =================================================================
    # Database operations
    # =================================================================

    def _get_existing_hashes(self):
        """Fetch existing subaward-key -> hash mappings from sam_subaward.

        Builds composite keys from prime_piid + sub_uei + sub_date.

        Returns:
            dict of {"key": hash_string}
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT prime_piid, sub_uei, sub_date, record_hash "
                "FROM sam_subaward WHERE record_hash IS NOT NULL"
            )
            result = {}
            for row in cursor.fetchall():
                record = {
                    "prime_piid": row["prime_piid"],
                    "sub_uei": row["sub_uei"],
                    "sub_date": str(row["sub_date"]) if row["sub_date"] else "",
                }
                key = _make_subaward_key(record)
                result[key] = row["record_hash"]
            return result
        finally:
            cursor.close()
            conn.close()

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
    # Parsing helpers
    # =================================================================

    def _parse_date(self, date_str):
        """Parse date string to YYYY-MM-DD format.

        Handles: MM/DD/YYYY, YYYY-MM-DD, ISO 8601 datetime, None/empty.

        Returns:
            str in YYYY-MM-DD format, or None.
        """
        if not date_str:
            return None
        s = str(date_str).strip()
        if not s:
            return None

        # Already ISO YYYY-MM-DD (possibly with time)
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10]

        # MM/DD/YYYY
        if len(s) == 10 and s[2] == "/" and s[5] == "/":
            return f"{s[6:10]}-{s[0:2]}-{s[3:5]}"

        # Fallback
        return s

    @staticmethod
    def _parse_amount(amount_str):
        """Parse dollar amount string to Decimal-safe float.

        The API returns amounts as strings. Strips currency symbols and commas.

        Args:
            amount_str: Dollar amount string (e.g. "150000.00" or "$150,000.00").

        Returns:
            float or None.
        """
        if not amount_str:
            return None
        s = str(amount_str).strip().replace("$", "").replace(",", "")
        if not s:
            return None
        try:
            return float(s)
        except (ValueError, TypeError):
            return None

    # =================================================================
    # Hash fields accessor
    # =================================================================

    @staticmethod
    def get_hash_fields():
        """Return the list of fields used for subaward record hashing."""
        return list(_SUBAWARD_HASH_FIELDS)
