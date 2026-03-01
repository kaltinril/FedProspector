"""SAM.gov Contract Awards loader.

Transforms SAM.gov Contract Awards API responses into the fpds_contract table.
Follows the same patterns as usaspending_loader.py: batch upserts with
change detection via SHA-256 hashing.

The fpds_contract table has a composite PK of (contract_id, modification_number).
Change detection uses a concatenated key for hash lookups.
"""

import json
import logging
from datetime import datetime, date
from decimal import Decimal, InvalidOperation

from db.connection import get_connection
from etl.change_detector import ChangeDetector
from etl.load_manager import LoadManager


logger = logging.getLogger("fed_prospector.etl.awards_loader")

# Fields used for record hash (business-meaningful fields only;
# excludes load-tracking timestamps and description)
_AWARD_HASH_FIELDS = [
    "contract_id", "modification_number", "vendor_uei", "vendor_name",
    "dollars_obligated", "base_and_all_options", "naics_code", "psc_code",
    "set_aside_type", "extent_competed", "number_of_offers",
    "date_signed", "effective_date", "completion_date",
    "pop_state", "pop_country",
]

# All fpds_contract columns used in upsert (order matters for values list)
_UPSERT_COLS = [
    "contract_id", "idv_piid", "modification_number", "transaction_number",
    "agency_id", "agency_name", "contracting_office_id", "contracting_office_name",
    "funding_agency_id", "funding_agency_name",
    "vendor_uei", "vendor_name", "vendor_duns",
    "date_signed", "effective_date", "completion_date", "last_modified_date",
    "dollars_obligated", "base_and_all_options",
    "naics_code", "psc_code", "set_aside_type", "type_of_contract",
    "description", "pop_state", "pop_country", "pop_zip",
    "extent_competed", "number_of_offers",
    "far1102_exception_code", "far1102_exception_name",
    "reason_for_modification", "solicitation_date", "ultimate_completion_date",
    "type_of_contract_pricing", "co_bus_size_determination",
    "record_hash", "last_load_id",
]


def _make_composite_key(contract_id, modification_number):
    """Build a composite key string for hash lookups.

    The fpds_contract PK is (contract_id, modification_number).
    We concatenate with a pipe separator for the in-memory hash dict.
    """
    mod = modification_number or "0"
    return f"{contract_id}|{mod}"


class AwardsLoader:
    """Load SAM.gov Contract Awards API data into fpds_contract table.

    Usage:
        loader = AwardsLoader()
        load_id = loader.load_manager.start_load("SAM_AWARDS", "INCREMENTAL")
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
        self.logger = logging.getLogger("fed_prospector.etl.awards_loader")
        self.change_detector = change_detector or ChangeDetector()
        self.load_manager = load_manager or LoadManager()

    # =================================================================
    # Public entry point
    # =================================================================

    def load_awards(self, awards_data, load_id):
        """Main entry point. Process list of raw SAM Awards API response dicts.

        Args:
            awards_data: list of raw award dicts from SAM Contract Awards API
                (items from the data[] array).
            load_id: etl_load_log ID for this load.

        Returns:
            dict with keys: records_read, records_inserted, records_updated,
                records_unchanged, records_errored.
        """
        self.logger.info(
            "Starting SAM Awards load (%d records, load_id=%d)",
            len(awards_data), load_id,
        )

        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_unchanged": 0,
            "records_errored": 0,
        }

        # Pre-fetch existing hashes for change detection.
        # fpds_contract has composite PK so we build concatenated keys.
        existing_hashes = self._get_existing_hashes()

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            batch_count = 0
            for raw in awards_data:
                stats["records_read"] += 1
                record_key = None
                try:
                    # --- normalise ----------------------------------------
                    award_data = self._normalize_award(raw)
                    contract_id = award_data.get("contract_id")
                    mod_number = award_data.get("modification_number", "0")
                    if not contract_id:
                        raise ValueError("Missing contractNumber in award record")

                    record_key = _make_composite_key(contract_id, mod_number)

                    # --- change detection ---------------------------------
                    new_hash = self.change_detector.compute_hash(
                        award_data, _AWARD_HASH_FIELDS
                    )
                    award_data["record_hash"] = new_hash

                    old_hash = existing_hashes.get(record_key)
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
            "SAM Awards load complete (load_id=%d): read=%d ins=%d upd=%d unch=%d err=%d",
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
        """Flatten the nested SAM Awards API response to a flat dict matching
        fpds_contract columns.

        The API returns deeply nested JSON. This maps each nested path to
        the corresponding DB column name.

        Args:
            raw: Single award dict from SAM Contract Awards API data[].

        Returns:
            dict: Normalised award data matching fpds_contract columns.
        """
        contract_id_block = raw.get("contractId") or {}
        awardee_data = raw.get("awardeeData") or {}
        awardee_header = awardee_data.get("awardeeHeader") or {}
        uei_info = awardee_header.get("awardeeUEIInformation") or {}
        award_contract = raw.get("awardContractData") or {}
        date_signed_block = award_contract.get("dateSignedFormat") or {}
        pop = award_contract.get("placeOfPerformance") or {}

        return {
            "contract_id":              contract_id_block.get("contractNumber"),
            "idv_piid":                 None,
            "modification_number":      contract_id_block.get("modificationNumber", "0"),
            "transaction_number":       contract_id_block.get("transactionNumber"),
            "agency_id":                None,
            "agency_name":              None,
            "contracting_office_id":    None,
            "contracting_office_name":  None,
            "funding_agency_id":        None,
            "funding_agency_name":      None,
            "vendor_uei":               uei_info.get("uniqueEntityId"),
            "vendor_name":              awardee_header.get("awardeeName"),
            "vendor_duns":              None,
            "date_signed":              self._parse_date(
                                            date_signed_block.get("dateSignedShortFormat")
                                        ),
            "effective_date":           self._parse_date(
                                            award_contract.get("effectiveDate")
                                        ),
            "completion_date":          self._parse_date(
                                            award_contract.get("completionDate")
                                        ),
            "last_modified_date":       self._parse_date(
                                            award_contract.get("lastModifiedDate")
                                        ),
            "dollars_obligated":        self._parse_decimal(
                                            award_contract.get("dollarsObligated")
                                        ),
            "base_and_all_options":     self._parse_decimal(
                                            award_contract.get("baseAndAllOptionsValue")
                                        ),
            "naics_code":               award_contract.get("naicsCode"),
            "psc_code":                 award_contract.get("productOrServiceCode"),
            "set_aside_type":           award_contract.get("typeOfSetAsideCode"),
            "type_of_contract":         award_contract.get("typeOfContractCode"),
            "description":              award_contract.get("contractDescription"),
            "pop_state":                pop.get("stateCode"),
            "pop_country":              pop.get("countryCode"),
            "pop_zip":                  pop.get("zipCode"),
            "extent_competed":          award_contract.get("extentCompetedCode"),
            "number_of_offers":         award_contract.get("numberOfOffersReceived"),
            "far1102_exception_code":   award_contract.get("far1102ExceptionCode"),
            "far1102_exception_name":   None,
            "reason_for_modification":  None,
            "solicitation_date":        None,
            "ultimate_completion_date": None,
            "type_of_contract_pricing": award_contract.get("typeOfContractPricingCode"),
            "co_bus_size_determination": None,
        }

    # =================================================================
    # Database operations
    # =================================================================

    def _get_existing_hashes(self):
        """Fetch existing composite-key -> hash mappings from fpds_contract.

        Since the PK is (contract_id, modification_number), we concatenate
        them with a pipe separator for the in-memory dict.

        Returns:
            dict of {"contract_id|modification_number": hash_string}
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT contract_id, modification_number, record_hash "
                "FROM fpds_contract WHERE record_hash IS NOT NULL"
            )
            result = {}
            for row in cursor.fetchall():
                key = _make_composite_key(row[0], row[1])
                result[key] = row[2]
            return result
        finally:
            cursor.close()
            conn.close()

    def _upsert_award(self, cursor, award_data, load_id):
        """INSERT ... ON DUPLICATE KEY UPDATE for fpds_contract.

        Args:
            cursor: Active DB cursor.
            award_data: Normalised award dict.
            load_id: Current load ID.

        Returns:
            'inserted', 'updated', or 'unchanged'.
        """
        placeholders = ", ".join(["%s"] * len(_UPSERT_COLS))
        col_list = ", ".join(_UPSERT_COLS)

        # ON DUPLICATE KEY UPDATE: update all columns except the PK fields
        pk_fields = {"contract_id", "modification_number"}
        update_pairs = ", ".join(
            f"{c} = VALUES({c})" for c in _UPSERT_COLS
            if c not in pk_fields
        )
        update_pairs += ", last_loaded_at = NOW()"

        sql = (
            f"INSERT INTO fpds_contract ({col_list}, first_loaded_at, last_loaded_at) "
            f"VALUES ({placeholders}, NOW(), NOW()) "
            f"ON DUPLICATE KEY UPDATE {update_pairs}"
        )

        # Build values list matching _UPSERT_COLS order
        values = []
        for col in _UPSERT_COLS:
            if col == "last_load_id":
                values.append(load_id)
            else:
                values.append(award_data.get(col))

        cursor.execute(sql, values)

        # MySQL: rowcount 0 = unchanged, 1 = inserted, 2 = updated
        rc = cursor.rowcount
        if rc == 1:
            return "inserted"
        elif rc == 2:
            return "updated"
        return "unchanged"

    # =================================================================
    # Parsing helpers
    # =================================================================

    def _parse_date(self, date_str):
        """Parse date string to YYYY-MM-DD format.

        Handles: MM/DD/YYYY (SAM Awards API format), YYYY-MM-DD, None/empty.

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
