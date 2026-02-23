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
from etl.change_detector import ChangeDetector
from etl.load_manager import LoadManager


logger = logging.getLogger("fed_prospector.etl.usaspending_loader")

# Fields used for record hash (business-meaningful fields only;
# excludes load-tracking timestamps and description)
_AWARD_HASH_FIELDS = [
    "generated_unique_award_id", "piid", "fain", "uri", "award_type",
    "recipient_name", "recipient_uei",
    "recipient_parent_name", "recipient_parent_uei",
    "total_obligation", "base_and_all_options_value",
    "start_date", "end_date", "last_modified_date",
    "awarding_agency_name", "awarding_sub_agency_name", "funding_agency_name",
    "naics_code", "naics_description", "psc_code",
    "type_of_set_aside", "type_of_set_aside_description",
    "pop_state", "pop_country", "pop_zip", "pop_city",
    "solicitation_identifier",
]


class USASpendingLoader:
    """Load USASpending.gov award data into usaspending_award table.

    Usage:
        loader = USASpendingLoader()
        load_id = loader.load_manager.start_load("USASPENDING", "INCREMENTAL")
        stats = loader.load_awards(awards_data, load_id)
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
        existing_hashes = self.change_detector.get_existing_hashes(
            "usaspending_award", "generated_unique_award_id", "record_hash"
        )

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            batch_count = 0
            for raw in awards_data:
                stats["records_read"] += 1
                award_id = None
                try:
                    # --- normalise ----------------------------------------
                    award_data = self._normalize_award(raw)
                    award_id = award_data.get("generated_unique_award_id")
                    if not award_id:
                        raise ValueError("Missing generated_unique_award_id in award record")

                    # --- change detection ---------------------------------
                    new_hash = self.change_detector.compute_hash(
                        award_data, _AWARD_HASH_FIELDS
                    )
                    award_data["record_hash"] = new_hash

                    old_hash = existing_hashes.get(award_id)
                    if old_hash and old_hash == new_hash:
                        stats["records_unchanged"] += 1
                        batch_count += 1
                        if batch_count >= self.BATCH_SIZE:
                            conn.commit()
                            batch_count = 0
                        continue

                    # --- upsert -------------------------------------------
                    outcome = self._upsert_award(cursor, award_data, load_id)
                    if outcome == "inserted":
                        stats["records_inserted"] += 1
                    elif outcome == "updated":
                        stats["records_updated"] += 1
                    else:
                        stats["records_unchanged"] += 1

                    # Update in-memory hash cache
                    existing_hashes[award_id] = new_hash

                except Exception as rec_exc:
                    stats["records_errored"] += 1
                    identifier = award_id or f"record#{stats['records_read']}"
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
            "USASpending load complete (load_id=%d): read=%d ins=%d upd=%d unch=%d err=%d",
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
            "total_obligation":          self._parse_decimal(raw.get("Award Amount")),
            "base_and_all_options_value": self._parse_decimal(raw.get("Base and All Options Value")),
            "start_date":                self._parse_date(raw.get("Start Date")),
            "end_date":                  self._parse_date(raw.get("End Date")),
            "last_modified_date":        self._parse_date(raw.get("Last Date to Order")),
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
            award_data["last_modified_date"] = self._parse_date(period["last_modified_date"])

        # Award type code from detail (more precise than description)
        if detail.get("type"):
            award_data["award_type"] = detail["type"]

        return award_data

    # =================================================================
    # Database operations
    # =================================================================

    def _upsert_award(self, cursor, award_data, load_id):
        """INSERT ... ON DUPLICATE KEY UPDATE for usaspending_award.

        Args:
            cursor: Active DB cursor.
            award_data: Normalised award dict.
            load_id: Current load ID.

        Returns:
            'inserted', 'updated', or 'unchanged'.
        """
        cols = [
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

        placeholders = ", ".join(["%s"] * len(cols))
        col_list = ", ".join(cols)

        # ON DUPLICATE KEY UPDATE: update all columns except the PK
        update_pairs = ", ".join(
            f"{c} = VALUES({c})" for c in cols
            if c != "generated_unique_award_id"
        )
        update_pairs += ", last_loaded_at = NOW()"

        sql = (
            f"INSERT INTO usaspending_award ({col_list}, first_loaded_at, last_loaded_at) "
            f"VALUES ({placeholders}, NOW(), NOW()) "
            f"ON DUPLICATE KEY UPDATE {update_pairs}"
        )

        values = [award_data.get(c) for c in cols[:-1]]  # all except last_load_id
        values.append(load_id)  # last_load_id

        cursor.execute(sql, values)

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
    # Parsing helpers
    # =================================================================

    def _parse_date(self, date_str):
        """Parse date string to YYYY-MM-DD format.

        Handles: YYYY-MM-DD, MM/DD/YYYY, None/empty.

        Returns:
            str in YYYY-MM-DD format, or None.
        """
        if not date_str:
            return None
        s = str(date_str).strip()
        if not s:
            return None

        # Already ISO YYYY-MM-DD
        if len(s) >= 10 and s[4] == "-" and s[7] == "-":
            return s[:10]

        # MM/DD/YYYY
        if len(s) == 10 and s[2] == "/" and s[5] == "/":
            return f"{s[6:10]}-{s[0:2]}-{s[3:5]}"

        # Fallback
        return s

    def _parse_decimal(self, value):
        """Parse a value to Decimal-compatible string.

        Award amounts can be negative (de-obligations) -- stored as-is.

        Returns:
            String representation of the decimal, or None.
        """
        if value is None:
            return None
        try:
            d = Decimal(str(value))
            return str(d)
        except (InvalidOperation, ValueError):
            self.logger.warning("Could not parse amount: %r", value)
            return None

    # =================================================================
    # Hash fields accessor
    # =================================================================

    @staticmethod
    def get_hash_fields():
        """Return the list of fields used for award record hashing."""
        return list(_AWARD_HASH_FIELDS)
