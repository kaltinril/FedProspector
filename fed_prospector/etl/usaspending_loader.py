"""USASpending.gov award loader.

Transforms USASpending API search results into the usaspending_award table.
Follows the same patterns as opportunity_loader.py: batch upserts with
change detection via SHA-256 hashing.

USASpending has no rate limits, so this loader can be called with large
result sets without concern for API quotas.
"""

import json
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from db.connection import get_connection
from etl.batch_upsert import build_upsert_sql, executemany_upsert
from etl.change_detector import ChangeDetector
from etl.etl_utils import fetch_existing_hashes, parse_date, parse_decimal, refresh_usaspending_award_summary, resolve_usaspending_agency_codes
from etl.load_manager import LoadManager
from etl.staging_mixin import StagingMixin


logger = logging.getLogger("fed_prospector.etl.usaspending_loader")

# Fields used for record hash (business-meaningful fields only;
# excludes load-tracking timestamps and description).
# NOTE: recipient_parent_name/uei, last_modified_date, type_of_set_aside_description,
# and solicitation_identifier are excluded because they are always None from the
# search endpoint (_normalize_award) and only populated by enrich_from_detail().
# Including them would cause false change detection on every search-only load.
_AWARD_HASH_FIELDS = [
    "generated_unique_award_id", "piid", "fain", "uri", "award_type",
    "recipient_name", "recipient_uei",
    "total_obligation", "base_and_all_options_value",
    "start_date", "end_date",
    "awarding_agency_name", "awarding_sub_agency_name", "funding_agency_name",
    "naics_code", "naics_description", "psc_code",
    "type_of_set_aside",
    "pop_state", "pop_country", "pop_zip", "pop_city",
]

# All usaspending_award columns used in upsert (order matters for values list)
_UPSERT_COLS = [
    "generated_unique_award_id", "piid", "fain", "uri", "award_type",
    "award_description",
    "recipient_name", "recipient_uei",
    "recipient_parent_name", "recipient_parent_uei",
    "total_obligation", "base_and_all_options_value",
    "start_date", "end_date", "last_modified_date",
    "awarding_agency_name", "awarding_sub_agency_name",
    "funding_agency_name",
    "naics_code", "naics_description", "psc_code",
    "type_of_set_aside", "type_of_set_aside_description",
    "pop_state", "pop_country", "pop_zip", "pop_city",
    "solicitation_identifier",
    "record_hash", "last_load_id",
]


class USASpendingLoader(StagingMixin):
    """Load USASpending.gov award data into usaspending_award table.

    Usage:
        loader = USASpendingLoader()
        load_id = loader.load_manager.start_load("USASPENDING", "INCREMENTAL")
        stats = loader.load_awards(awards_data, load_id)
        loader.load_manager.complete_load(load_id, **stats)
    """

    _STG_TABLE = "stg_usaspending_raw"
    _STG_KEY_COLS = ["award_id"]

    BATCH_SIZE = 500

    # Pre-computed upsert SQL (built once, not per record)
    _UPSERT_SQL = build_upsert_sql(
        table="usaspending_award",
        columns=_UPSERT_COLS,
        pk_fields={"generated_unique_award_id"},
    )

    def __init__(self, db_connection=None, change_detector=None, load_manager=None):
        """Initialize with optional DB connection, change detector, load manager.

        Args:
            db_connection: Not used (connections obtained from pool). Kept for
                           interface compatibility.
            change_detector: Optional ChangeDetector instance.
            load_manager: Optional LoadManager instance.
        """
        self.logger = logging.getLogger("fed_prospector.etl.usaspending_loader")
        self.change_detector = change_detector or ChangeDetector()
        self.load_manager = load_manager or LoadManager()

    # =================================================================
    # Public entry point
    # =================================================================

    def load_awards(self, awards_data, load_id):
        """Main entry point. Process list of raw USASpending award dicts.

        Args:
            awards_data: list of raw award dicts from USASpending API
                (search_awards results or search_awards_all generator output).
            load_id: etl_load_log ID for this load.

        Returns:
            dict with keys: records_read, records_inserted, records_updated,
                records_unchanged, records_errored.
        """
        # Materialize generator to allow len() and safe re-iteration
        awards_data = list(awards_data)
        self.logger.info(
            "Starting USASpending award load (%d records, load_id=%d)",
            len(awards_data), load_id,
        )

        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_unchanged": 0,
            "records_errored": 0,
        }

        # Pre-fetch existing hashes for change detection
        existing_hashes = fetch_existing_hashes("usaspending_award", "generated_unique_award_id")

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Staging connection: autocommit=True so each row is committed
        # immediately, independent of the main batch transaction.
        stg_conn, stg_cursor = self._open_stg_conn()

        try:
            for batch_start in range(0, len(awards_data), self.BATCH_SIZE):
                batch_raw = awards_data[batch_start : batch_start + self.BATCH_SIZE]

                # --- Phase 1: Normalize, compute hashes, classify ---
                staging_rows = []
                normalized = []
                changed_records = []

                for raw in batch_raw:
                    stats["records_read"] += 1
                    try:
                        key_vals = self._extract_staging_key(raw)
                        staging_rows.append((key_vals, raw))

                        award_data = self._normalize_award(raw)
                        award_id = award_data.get("generated_unique_award_id")
                        if not award_id:
                            raise ValueError("Missing generated_unique_award_id in award record")

                        new_hash = self.change_detector.compute_hash(
                            award_data, _AWARD_HASH_FIELDS
                        )
                        award_data["record_hash"] = new_hash

                        old_hash = existing_hashes.get(award_id)
                        if old_hash and old_hash == new_hash:
                            stats["records_unchanged"] += 1
                        else:
                            changed_records.append(
                                (raw, award_data, award_id, new_hash)
                            )

                        normalized.append((raw, award_data, award_id, new_hash))

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

                # --- Phase 3: Batch upsert changed records ---
                if changed_records:
                    try:
                        upsert_rows = []
                        for _raw, award_data, _aid, _nh in changed_records:
                            values = [award_data.get(c) for c in _UPSERT_COLS[:-1]]
                            values.append(load_id)  # last_load_id
                            upsert_rows.append(tuple(values))

                        executemany_upsert(cursor, self._UPSERT_SQL, upsert_rows)

                        for _raw, award_data, award_id, new_hash in changed_records:
                            if award_id in existing_hashes:
                                stats["records_updated"] += 1
                            else:
                                stats["records_inserted"] += 1
                            existing_hashes[award_id] = new_hash

                    except Exception as batch_exc:
                        self.logger.warning(
                            "Batch upsert failed (%d records), falling back to row-by-row: %s",
                            len(changed_records), batch_exc,
                        )
                        conn.rollback()
                        for raw, award_data, award_id, new_hash in changed_records:
                            try:
                                outcome = self._upsert_award(cursor, award_data, load_id)
                                if outcome == "inserted":
                                    stats["records_inserted"] += 1
                                elif outcome == "updated":
                                    stats["records_updated"] += 1
                                else:
                                    stats["records_unchanged"] += 1
                                existing_hashes[award_id] = new_hash
                            except Exception as rec_exc:
                                stats["records_errored"] += 1
                                self.logger.warning(
                                    "Error processing %s: %s", award_id, rec_exc
                                )
                                self.load_manager.log_record_error(
                                    load_id,
                                    record_identifier=str(award_id),
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
            "USASpending load complete (load_id=%d): read=%d ins=%d upd=%d unch=%d err=%d",
            load_id,
            stats["records_read"],
            stats["records_inserted"],
            stats["records_updated"],
            stats["records_unchanged"],
            stats["records_errored"],
        )

        # Refresh pre-computed award summary for scoring lookups
        if stats["records_inserted"] > 0 or stats["records_updated"] > 0:
            summary_conn = get_connection()
            try:
                refresh_usaspending_award_summary(summary_conn)
                resolve_usaspending_agency_codes(summary_conn)
            finally:
                summary_conn.close()

        return stats

    # =================================================================
    # Normalisation
    # =================================================================

    def _normalize_award(self, raw):
        """Flatten USASpending API search response to DB column dict.

        The API returns field names with spaces and mixed case (e.g.
        "Recipient Name", "Award Amount"). This maps them to snake_case
        DB columns.

        Note on IDs: The search endpoint returns "generated_internal_id"
        (e.g. "CONT_AWD_...") which is the same value as
        "generated_unique_award_id" from the detail endpoint. The search
        field "Award ID" is actually the contract PIID. The requested
        field "generated_unique_award_id" typically returns None in
        search results, so we fall back to "generated_internal_id".

        Args:
            raw: Single award dict from USASpending search results.

        Returns:
            dict: Normalised award data matching usaspending_award columns.
        """
        # Resolve the unique award ID: prefer the explicitly named field,
        # fall back to generated_internal_id from search results
        unique_id = raw.get("generated_unique_award_id") or raw.get("generated_internal_id")

        # "Award ID" in search results is the PIID (contract number)
        piid = raw.get("Award ID")

        return {
            "generated_unique_award_id": unique_id,
            "piid":                      piid,
            "fain":                      raw.get("FAIN"),
            "uri":                       raw.get("URI"),
            "award_type":                raw.get("Contract Award Type"),
            "award_description":         raw.get("Description"),
            "recipient_name":            raw.get("Recipient Name"),
            "recipient_uei":             raw.get("Recipient UEI"),
            "recipient_parent_name":     None,  # Only available from detail endpoint
            "recipient_parent_uei":      None,  # Only available from detail endpoint
            "total_obligation":          parse_decimal(raw.get("Award Amount")),
            "base_and_all_options_value": parse_decimal(raw.get("Base and All Options Value")),
            "start_date":                parse_date(raw.get("Start Date")),
            "end_date":                  parse_date(raw.get("End Date")),
            "last_modified_date":        None,  # Not in search results; populated by enrich_from_detail()
            "awarding_agency_name":      raw.get("Awarding Agency"),
            "awarding_sub_agency_name":  raw.get("Awarding Sub Agency"),
            "funding_agency_name":       raw.get("Funding Agency"),
            "naics_code":                raw.get("NAICS Code"),
            "naics_description":         raw.get("NAICS Description"),
            "psc_code":                  raw.get("PSC Code"),
            "type_of_set_aside":         raw.get("Type of Set Aside"),
            "type_of_set_aside_description": None,  # Only available from detail endpoint
            "pop_state":                 raw.get("Place of Performance State Code"),
            "pop_country":               raw.get("Place of Performance Country Code"),
            "pop_zip":                   raw.get("Place of Performance Zip5"),
            "pop_city":                  raw.get("Place of Performance City Code"),
            "solicitation_identifier":   None,  # Only available from detail endpoint
        }

    def enrich_from_detail(self, award_data, detail):
        """Enrich a normalised award dict with data from the award detail endpoint.

        Many fields are only available from the detail endpoint, not from
        search results. Call USASpendingClient.get_award() then pass the
        result here to fill in those fields.

        Args:
            award_data: Normalised award dict from _normalize_award.
            detail: Full award detail dict from get_award().

        Returns:
            dict: Updated award_data with additional fields.
        """
        if not detail:
            return award_data

        # Recipient parent info
        recipient = detail.get("recipient") or {}
        parent = recipient.get("parent_recipient_name")
        parent_uei = recipient.get("parent_recipient_uei")
        if parent:
            award_data["recipient_parent_name"] = parent
        if parent_uei:
            award_data["recipient_parent_uei"] = parent_uei

        # NAICS code and description from hierarchy
        naics = detail.get("naics_hierarchy") or {}
        base_naics = naics.get("base_code") or {}
        if base_naics.get("code"):
            award_data["naics_code"] = base_naics["code"]
        if base_naics.get("description"):
            award_data["naics_description"] = base_naics["description"]

        # PSC code from hierarchy
        psc = detail.get("psc_hierarchy") or {}
        base_psc = psc.get("base_code") or {}
        if base_psc.get("code"):
            award_data["psc_code"] = base_psc["code"]

        # Latest transaction contract data has set-aside and solicitation
        latest = detail.get("latest_transaction_contract_data") or {}

        sa = latest.get("type_of_set_aside")
        if sa:
            award_data["type_of_set_aside"] = sa
        sa_desc = latest.get("type_of_set_aside_description")
        if sa_desc:
            award_data["type_of_set_aside_description"] = sa_desc

        sol_id = latest.get("solicitation_identifier")
        if sol_id:
            award_data["solicitation_identifier"] = sol_id

        # Place of performance from detail (more complete than search)
        pop = detail.get("place_of_performance") or {}
        if pop.get("state_code"):
            award_data["pop_state"] = pop["state_code"]
        if pop.get("location_country_code"):
            award_data["pop_country"] = pop["location_country_code"]
        if pop.get("zip5"):
            award_data["pop_zip"] = pop["zip5"]
        if pop.get("city_name"):
            award_data["pop_city"] = pop["city_name"]

        # Period of performance dates
        period = detail.get("period_of_performance") or {}
        if period.get("last_modified_date"):
            award_data["last_modified_date"] = parse_date(period["last_modified_date"])

        # Award type code from detail (more precise than description)
        if detail.get("type"):
            award_data["award_type"] = detail["type"]

        return award_data

    # =================================================================
    # Database operations
    # =================================================================

    def _upsert_award(self, cursor, award_data, load_id):
        """INSERT ... ON DUPLICATE KEY UPDATE for usaspending_award.

        Per-record fallback method. The batch path uses executemany_upsert
        with self._UPSERT_SQL instead.

        Args:
            cursor: Active DB cursor.
            award_data: Normalised award dict.
            load_id: Current load ID.

        Returns:
            'inserted', 'updated', or 'unchanged'.
        """
        values = [award_data.get(c) for c in _UPSERT_COLS[:-1]]  # all except last_load_id
        values.append(load_id)  # last_load_id

        cursor.execute(self._UPSERT_SQL, values)

        # MySQL: rowcount 0 = unchanged, 1 = inserted, 2 = updated
        rc = cursor.rowcount
        if rc == 1:
            return "inserted"
        elif rc == 2:
            return "updated"
        return "unchanged"

    # =================================================================
    # Local DB lookup
    # =================================================================

    def find_incumbent(self, solicitation_number=None, naics_code=None,
                       agency_name=None, conn=None):
        """Look up incumbent from local usaspending_award table.

        Searches the local DB first. If no local data, returns None
        (caller can then use USASpendingClient.search_incumbent to query API).

        Args:
            solicitation_number: Solicitation ID to match.
            naics_code: NAICS code to match.
            agency_name: Awarding agency name to match.
            conn: Optional DB connection. One will be obtained if not provided.

        Returns:
            dict with recipient_name, recipient_uei, total_obligation, etc.,
            or None if no match found.
        """
        own_conn = conn is None
        if own_conn:
            conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            conditions = []
            params = []

            if solicitation_number:
                conditions.append("(solicitation_identifier = %s OR piid = %s)")
                params.extend([solicitation_number, solicitation_number])
            if naics_code:
                conditions.append("naics_code = %s")
                params.append(naics_code)
            if agency_name:
                conditions.append("awarding_agency_name LIKE %s")
                params.append(f"%{agency_name}%")

            if not conditions:
                return None

            where = " AND ".join(conditions)
            sql = (
                f"SELECT * FROM usaspending_award "
                f"WHERE {where} "
                f"ORDER BY total_obligation DESC "
                f"LIMIT 1"
            )

            cursor.execute(sql, params)
            row = cursor.fetchone()

            if row:
                # Convert Decimal/date values for clean return
                clean = {}
                for k, v in row.items():
                    if isinstance(v, Decimal):
                        clean[k] = float(v)
                    elif isinstance(v, (date, datetime)):
                        clean[k] = v.isoformat()
                    else:
                        clean[k] = v
                return clean

            return None

        finally:
            cursor.close()
            if own_conn:
                conn.close()

    # =================================================================
    # Transaction loading (for burn rate)
    # =================================================================

    def load_transactions(self, award_id, transactions, load_id):
        """Load transaction records for a specific award into usaspending_transaction.

        Inserts new transactions (skips duplicates by award_id + modification_number + action_date).

        Args:
            award_id: The generated_unique_award_id.
            transactions: Iterable of transaction dicts from the API.
            load_id: etl_load_log ID.

        Returns:
            dict with keys: records_read, records_inserted, records_skipped, records_errored.
        """
        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_skipped": 0,
            "records_errored": 0,
        }

        conn = get_connection()
        cursor = conn.cursor()
        try:
            for txn in transactions:
                stats["records_read"] += 1
                try:
                    sql = (
                        "INSERT IGNORE INTO usaspending_transaction "
                        "(award_id, action_date, modification_number, action_type, "
                        "action_type_description, federal_action_obligation, description, last_load_id) "
                        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"
                    )
                    values = (
                        award_id,
                        parse_date(txn.get("action_date")),
                        txn.get("modification_number"),
                        txn.get("action_type"),
                        txn.get("action_type_description"),
                        parse_decimal(txn.get("federal_action_obligation")),
                        txn.get("description"),
                        load_id,
                    )
                    cursor.execute(sql, values)
                    if cursor.rowcount > 0:
                        stats["records_inserted"] += 1
                    else:
                        stats["records_skipped"] += 1

                except Exception as e:
                    stats["records_errored"] += 1
                    self.logger.warning("Error loading transaction: %s", e)

                if stats["records_read"] % 500 == 0:
                    conn.commit()

            conn.commit()
        finally:
            cursor.close()
            conn.close()

        self.logger.info(
            "Transaction load for %s: read=%d ins=%d skip=%d err=%d",
            award_id, stats["records_read"], stats["records_inserted"],
            stats["records_skipped"], stats["records_errored"],
        )
        return stats

    def calculate_burn_rate(self, award_id, conn=None):
        """Calculate burn rate for an award from transaction history.

        Returns monthly obligation amounts and overall burn rate.

        Args:
            award_id: The generated_unique_award_id.
            conn: Optional DB connection.

        Returns:
            dict with keys:
                total_obligated: Total from all transactions
                months_elapsed: Months from first to last action
                monthly_rate: total / months (simple burn rate)
                monthly_breakdown: list of (year_month, amount) tuples
                transaction_count: Number of transactions
            Returns None if no transactions found.
        """
        own_conn = conn is None
        if own_conn:
            conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        try:
            # Get monthly breakdown
            cursor.execute(
                "SELECT LEFT(action_date, 7) AS yr_month, "
                "SUM(federal_action_obligation) AS monthly_total, "
                "COUNT(*) AS txn_count "
                "FROM usaspending_transaction "
                "WHERE award_id = %s AND federal_action_obligation IS NOT NULL "
                "GROUP BY yr_month "
                "ORDER BY yr_month",
                (award_id,),
            )
            rows = cursor.fetchall()

            if not rows:
                return None

            monthly = [(r["yr_month"], float(r["monthly_total"])) for r in rows]
            total = sum(amt for _, amt in monthly)
            txn_count = sum(r["txn_count"] for r in rows)

            # Calculate months elapsed
            first_month = rows[0]["yr_month"]
            last_month = rows[-1]["yr_month"]
            fy, fm = int(first_month[:4]), int(first_month[5:7])
            ly, lm = int(last_month[:4]), int(last_month[5:7])
            months = (ly - fy) * 12 + (lm - fm) + 1  # inclusive

            return {
                "total_obligated": total,
                "months_elapsed": months,
                "monthly_rate": total / months if months > 0 else 0,
                "monthly_breakdown": monthly,
                "transaction_count": txn_count,
            }
        finally:
            cursor.close()
            if own_conn:
                conn.close()

    # =================================================================
    # Parsing helpers
    # =================================================================

    def _parse_date(self, value):
        """Delegate to shared etl_utils.parse_date."""
        return parse_date(value)

    def _parse_decimal(self, value):
        """Delegate to shared etl_utils.parse_decimal."""
        return parse_decimal(value)

    # =================================================================
    # Raw staging helpers
    # =================================================================

    def _extract_staging_key(self, raw: dict) -> dict:
        """Extract the natural key from a raw API record for staging.

        Mirrors the fallback logic in _normalize_award: prefer
        generated_unique_award_id, fall back to generated_internal_id.
        """
        award_id = raw.get("generated_unique_award_id") or raw.get("generated_internal_id") or ""
        return {"award_id": award_id}

    # =================================================================
    # Hash fields accessor
    # =================================================================

    @staticmethod
    def get_hash_fields():
        """Return the list of fields used for award record hashing."""
        return list(_AWARD_HASH_FIELDS)
