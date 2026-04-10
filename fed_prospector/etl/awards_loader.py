"""SAM.gov Contract Awards loader.

Transforms SAM.gov Contract Awards API responses into the fpds_contract table.
Follows the same patterns as usaspending_loader.py: batch upserts with
change detection via SHA-256 hashing.

The fpds_contract table has a composite PK of (contract_id, modification_number).
Change detection uses a concatenated key for hash lookups.
"""

import json
import logging

from db.connection import get_connection
from etl.batch_upsert import build_upsert_sql, executemany_upsert
from etl.change_detector import ChangeDetector
from etl.etl_utils import parse_date, parse_decimal, resolve_fpds_fh_org_ids
from etl.load_manager import LoadManager
from etl.staging_mixin import StagingMixin


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
    "funding_subtier_code", "funding_subtier_name",
    "vendor_uei", "vendor_name", "vendor_duns",
    "date_signed", "effective_date", "completion_date", "last_modified_date",
    "dollars_obligated", "base_and_all_options",
    "naics_code", "psc_code", "set_aside_type", "type_of_contract",
    "description", "pop_state", "pop_country", "pop_zip",
    "extent_competed", "number_of_offers",
    "far1102_exception_code", "far1102_exception_name",
    "reason_for_modification", "solicitation_number",
    "solicitation_date", "ultimate_completion_date",
    "type_of_contract_pricing", "co_bus_size_determination",
    "fh_org_id",
    "record_hash", "last_load_id",
]


def _make_composite_key(contract_id, modification_number):
    """Build a composite key string for hash lookups.

    The fpds_contract PK is (contract_id, modification_number).
    We concatenate with a pipe separator for the in-memory hash dict.
    The pipe character does not appear in PIIDs or modification numbers
    (government alphanumeric identifiers), so collisions are not a concern.
    """
    mod = modification_number or "0"
    return f"{contract_id}|{mod}"


class AwardsLoader(StagingMixin):
    """Load SAM.gov Contract Awards API data into fpds_contract table.

    Usage:
        loader = AwardsLoader()
        load_id = loader.load_manager.start_load("SAM_AWARDS", "INCREMENTAL")
        stats = loader.load_awards(awards_data, load_id)
        loader.load_manager.complete_load(load_id, **stats)
    """

    _STG_TABLE = "stg_fpds_award_raw"
    _STG_KEY_COLS = ["contract_id", "modification_number"]

    BATCH_SIZE = 500

    # Pre-computed upsert SQL (built once, not per record)
    _UPSERT_SQL = build_upsert_sql(
        table="fpds_contract",
        columns=_UPSERT_COLS,
        pk_fields={"contract_id", "modification_number"},
    )

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
        self._fh_org_cache = None  # Lazy-loaded

    def _get_fh_org_cache(self):
        """Build/return cached lookups for fh_org_id resolution.

        Returns dict with:
          'office': {oldfpds_office_code -> fh_org_id}
          'dept':   {agency_code -> fh_org_id} for Department/Ind. Agency level-1
        """
        if self._fh_org_cache is not None:
            return self._fh_org_cache

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # oldfpds_office_code -> fh_org_id (MIN for deterministic dedup)
            cursor.execute(
                "SELECT oldfpds_office_code, MIN(fh_org_id) "
                "FROM federal_organization "
                "WHERE oldfpds_office_code IS NOT NULL "
                "GROUP BY oldfpds_office_code"
            )
            office = {row[0]: row[1] for row in cursor.fetchall()}

            # Department: agency_code -> fh_org_id (level 1)
            cursor.execute(
                "SELECT agency_code, MIN(fh_org_id) "
                "FROM federal_organization "
                "WHERE fh_org_type = 'Department/Ind. Agency' AND level = 1 "
                "AND agency_code IS NOT NULL "
                "GROUP BY agency_code"
            )
            dept = {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            cursor.close()
            conn.close()

        self._fh_org_cache = {"office": office, "dept": dept}
        self.logger.info(
            "fh_org_id cache loaded: %d office codes, %d department codes",
            len(office), len(dept),
        )
        return self._fh_org_cache

    # =================================================================
    # Public entry points
    # =================================================================

    def load_awards_batch(self, awards_data, load_id):
        """Process a batch of awards under an existing load_id.

        Unlike load_awards(), does NOT start or complete a load — caller
        manages the load lifecycle.  Pre-fetches existing hashes on first
        call (lazy init).

        Args:
            awards_data: list of raw award dicts from SAM Contract Awards API.
            load_id: Existing load_id from LoadManager.start_load().

        Returns:
            dict with keys: records_read, records_inserted, records_updated,
                records_unchanged, records_errored.
        """
        # Lazy-init hash cache on first call
        if not hasattr(self, "_existing_hashes") or self._existing_hashes is None:
            self._existing_hashes = self._get_existing_hashes()

        return self._process_awards(list(awards_data), load_id, self._existing_hashes)

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
        awards_data = list(awards_data)
        self.logger.info(
            "Starting SAM Awards load (%d records, load_id=%d)",
            len(awards_data), load_id,
        )

        existing_hashes = self._get_existing_hashes()
        stats = self._process_awards(awards_data, load_id, existing_hashes)

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
    # Core processing pipeline
    # =================================================================

    def _process_awards(self, awards_data, load_id, existing_hashes):
        """Process a list of raw award dicts: stage, normalise, hash-compare, upsert.

        Uses batch operations for staging writes, upserts, and staging marks.
        Falls back to row-by-row processing if a batch upsert fails, to isolate
        the bad record.

        Args:
            awards_data: list of raw award dicts.
            load_id: Current load ID.
            existing_hashes: Mutable dict of composite_key -> hash_string.
                Updated in-place as records are processed.

        Returns:
            dict with records_read/inserted/updated/unchanged/errored counts.
        """
        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_unchanged": 0,
            "records_errored": 0,
        }

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        stg_conn, stg_cursor = self._open_stg_conn()

        try:
            # Process in BATCH_SIZE chunks
            for batch_start in range(0, len(awards_data), self.BATCH_SIZE):
                batch_raw = awards_data[batch_start : batch_start + self.BATCH_SIZE]

                # --- Phase 1: Normalize all records, compute hashes, classify ---
                staging_rows = []    # (key_vals, raw) for batch staging insert
                normalized = []      # (raw, award_data, record_key, new_hash)
                unchanged_indices = []  # indices into normalized for unchanged records
                changed_records = []    # (raw, award_data, record_key, new_hash) for upsert

                for raw in batch_raw:
                    stats["records_read"] += 1
                    try:
                        key_vals = self._extract_staging_key(raw)
                        staging_rows.append((key_vals, raw))

                        award_data = self._normalize_award(raw)
                        contract_id = award_data.get("contract_id")
                        mod_number = award_data.get("modification_number", "0")
                        if not contract_id:
                            raise ValueError("Missing piid in award record")

                        record_key = _make_composite_key(contract_id, mod_number)

                        new_hash = self.change_detector.compute_hash(
                            award_data, _AWARD_HASH_FIELDS
                        )
                        award_data["record_hash"] = new_hash

                        old_hash = existing_hashes.get(record_key)
                        if old_hash and old_hash == new_hash:
                            stats["records_unchanged"] += 1
                            unchanged_indices.append(len(normalized))
                        else:
                            changed_records.append(
                                (raw, award_data, record_key, new_hash)
                            )

                        normalized.append((raw, award_data, record_key, new_hash))

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
                        # Add placeholder so staging_rows indices stay aligned
                        normalized.append(None)

                # --- Phase 2: Batch staging INSERT ---
                staging_ids = self._insert_staging_batch(
                    stg_cursor, load_id, staging_rows
                )

                # --- Phase 3: Batch upsert changed records ---
                if changed_records:
                    try:
                        upsert_rows = []
                        for _raw, award_data, _rk, _nh in changed_records:
                            values = []
                            for col in _UPSERT_COLS:
                                if col == "last_load_id":
                                    values.append(load_id)
                                else:
                                    values.append(award_data.get(col))
                            upsert_rows.append(tuple(values))

                        executemany_upsert(cursor, self._UPSERT_SQL, upsert_rows)

                        # Count inserts vs updates: with executemany we cannot
                        # distinguish per-row, so count based on hash cache
                        for _raw, award_data, record_key, new_hash in changed_records:
                            if record_key in existing_hashes:
                                stats["records_updated"] += 1
                            else:
                                stats["records_inserted"] += 1
                            existing_hashes[record_key] = new_hash

                    except Exception as batch_exc:
                        self.logger.warning(
                            "Batch upsert failed (%d records), falling back to row-by-row: %s",
                            len(changed_records), batch_exc,
                        )
                        conn.rollback()
                        # Fall back to row-by-row for this batch
                        for raw, award_data, record_key, new_hash in changed_records:
                            try:
                                outcome = self._upsert_award(cursor, award_data, load_id)
                                if outcome == "inserted":
                                    stats["records_inserted"] += 1
                                elif outcome == "updated":
                                    stats["records_updated"] += 1
                                else:
                                    stats["records_unchanged"] += 1
                                existing_hashes[record_key] = new_hash
                            except Exception as rec_exc:
                                stats["records_errored"] += 1
                                self.logger.warning(
                                    "Error processing %s: %s", record_key, rec_exc
                                )
                                self.load_manager.log_record_error(
                                    load_id,
                                    record_identifier=record_key,
                                    error_type=type(rec_exc).__name__,
                                    error_message=str(rec_exc),
                                    raw_data=json.dumps(raw) if isinstance(raw, dict) else str(raw),
                                )
                                conn.rollback()

                # --- Phase 4: Batch mark staging as processed ---
                # Mark all successfully processed staging rows
                success_staging_ids = []
                for idx, entry in enumerate(normalized):
                    if entry is not None and idx < len(staging_ids):
                        success_staging_ids.append(staging_ids[idx])
                if success_staging_ids:
                    self._mark_staging_batch(stg_cursor, success_staging_ids, 'Y')

                # Commit the batch
                conn.commit()

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

        finally:
            cursor.close()
            conn.close()
            stg_cursor.close()
            stg_conn.close()

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
        # --- Top-level blocks ---
        contract_id_block = raw.get("contractId") or {}
        core_data = raw.get("coreData") or {}
        award_details = raw.get("awardDetails") or {}

        # --- contractId sub-blocks ---
        reason_mod = contract_id_block.get("reasonForModification") or {}

        # --- coreData sub-blocks ---
        fed_org = core_data.get("federalOrganization") or {}
        contracting_info = fed_org.get("contractingInformation") or {}
        contracting_dept = contracting_info.get("contractingDepartment") or {}
        contracting_office = contracting_info.get("contractingOffice") or {}
        funding_info = fed_org.get("fundingInformation") or {}
        funding_dept = funding_info.get("fundingDepartment") or {}
        funding_subtier = funding_info.get("fundingSubtier") or {}
        pop = core_data.get("principalPlaceOfPerformance") or {}
        pop_state = pop.get("state") or {}
        pop_country = pop.get("country") or {}
        product_info = core_data.get("productOrServiceInformation") or {}
        competition_info = core_data.get("competitionInformation") or {}
        set_aside = competition_info.get("typeOfSetAside") or {}
        sol_procedures = competition_info.get("solicitationProcedures") or {}
        extent_competed_obj = competition_info.get("extentCompeted") or {}
        award_or_idv = core_data.get("awardOrIDVType") or {}
        acq_data = core_data.get("acquisitionData") or {}
        contract_pricing = acq_data.get("typeOfContractPricing") or {}

        # --- coreData.productOrServiceInformation sub-blocks ---
        psc = product_info.get("productOrService") or {}
        naics_list = product_info.get("principalNaics")
        naics_code = None
        if isinstance(naics_list, list) and naics_list:
            naics_code = naics_list[0].get("code")
        elif isinstance(naics_list, dict):
            naics_code = naics_list.get("code")

        # --- awardDetails sub-blocks ---
        award_dates = award_details.get("dates") or {}
        total_dollars = award_details.get("totalContractDollars") or {}
        award_competition = award_details.get("competitionInformation") or {}
        pref_programs = award_details.get("preferenceProgramsInformation") or {}
        award_product_info = award_details.get("productOrServiceInformation") or {}
        awardee_data = award_details.get("awardeeData") or {}
        awardee_header = awardee_data.get("awardeeHeader") or {}
        uei_info = awardee_data.get("awardeeUEIInformation") or {}
        far_exception = awardee_data.get("far41102Exception") or {}
        transaction_data = award_details.get("transactionData") or {}

        # CO business size determination can be an array; take first entry
        co_biz_size_list = pref_programs.get(
            "contractingOfficerBusinessSizeDetermination"
        )
        co_biz_size = None
        if isinstance(co_biz_size_list, list) and co_biz_size_list:
            co_biz_size = co_biz_size_list[0].get("code")
        elif isinstance(co_biz_size_list, dict):
            co_biz_size = co_biz_size_list.get("code")

        # Helper to strip whitespace from string values
        def _s(val):
            return val.strip() if isinstance(val, str) else val

        def _int(val):
            if val is None:
                return None
            try:
                return int(val)
            except (ValueError, TypeError):
                return None

        return {
            "contract_id":              _s(contract_id_block.get("piid")),
            "idv_piid":                 _s(contract_id_block.get("referencedIDVPiid")),
            "modification_number":      _s(contract_id_block.get("modificationNumber", "0")),
            "transaction_number":       _s(contract_id_block.get("transactionNumber")),
            "agency_id":                _s(contracting_dept.get("code")),
            "agency_name":              _s(contracting_dept.get("name")),
            "contracting_office_id":    _s(contracting_office.get("code")),
            "contracting_office_name":  _s(contracting_office.get("name")),
            "funding_agency_id":        _s(funding_dept.get("code")),
            "funding_agency_name":      _s(funding_dept.get("name")),
            "funding_subtier_code":     _s(funding_subtier.get("code")),
            "funding_subtier_name":     _s(funding_subtier.get("name")),
            "vendor_uei":               _s(uei_info.get("uniqueEntityId")),
            "vendor_name":              _s(awardee_header.get("awardeeName")),
            "vendor_duns":              None,
            "date_signed":              parse_date(
                                            award_dates.get("dateSigned")
                                        ),
            "effective_date":           parse_date(
                                            award_dates.get("periodOfPerformanceStartDate")
                                        ),
            "completion_date":          parse_date(
                                            award_dates.get("currentCompletionDate")
                                        ),
            "last_modified_date":       parse_date(
                                            transaction_data.get("lastModifiedDate")
                                        ),
            "dollars_obligated":        parse_decimal(
                                            total_dollars.get("totalActionObligation")
                                        ),
            "base_and_all_options":     parse_decimal(
                                            total_dollars.get("totalBaseAndAllOptionsValue")
                                        ),
            "naics_code":               _s(naics_code),
            "psc_code":                 _s(psc.get("code")),
            "set_aside_type":           _s(set_aside.get("code")),
            "type_of_contract":         _s(award_or_idv.get("code")),
            "description":              _s(award_product_info.get(
                                            "descriptionOfContractRequirement"
                                        )),
            "pop_state":                _s(pop_state.get("code")),
            "pop_country":              _s(pop_country.get("code")),
            "pop_zip":                  _s(pop.get("zipCode")),
            "extent_competed":          _s(extent_competed_obj.get("code")),
            "number_of_offers":         _int(award_competition.get("numberOfOffersReceived")),
            "far1102_exception_code":   _s(far_exception.get("code")),
            "far1102_exception_name":   _s(far_exception.get("name")),
            "reason_for_modification":  _s(reason_mod.get("code")),
            "solicitation_number":      _s(core_data.get("solicitationId")),
            "solicitation_date":        parse_date(
                                            core_data.get("solicitationDate")
                                        ),
            "ultimate_completion_date": parse_date(
                                            award_dates.get("ultimateCompletionDate")
                                        ),
            "type_of_contract_pricing": _s(contract_pricing.get("code")),
            "co_bus_size_determination": _s(co_biz_size),
            "fh_org_id":                self._resolve_fh_org_id(
                                            _s(contracting_office.get("code")),
                                            _s(contracting_dept.get("code")),
                                        ),
        }

    def _resolve_fh_org_id(self, contracting_office_code, agency_id):
        """Resolve fh_org_id from contracting office code or agency_id.

        Args:
            contracting_office_code: oldfpds_office_code (e.g. 'SPE7LX')
            agency_id: department-level code (e.g. '9700')

        Returns:
            int fh_org_id or None
        """
        cache = self._get_fh_org_cache()
        fh_org_id = None
        if contracting_office_code:
            fh_org_id = cache["office"].get(contracting_office_code)
        if fh_org_id is None and agency_id:
            fh_org_id = cache["dept"].get(agency_id)
        return fh_org_id

    # =================================================================
    # Staging helpers
    # =================================================================

    def _open_stg_conn(self):
        """Open a dedicated autocommit connection for staging writes.

        Overrides StagingMixin._open_stg_conn to use the module-local
        get_connection binding so test patches apply correctly.
        """
        conn = get_connection()
        conn.autocommit = True
        return conn, conn.cursor()

    def _extract_staging_key(self, raw):
        """Extract the business key fields from a raw award dict.

        Returns:
            dict with contract_id and modification_number.
        """
        contract_id_block = raw.get("contractId") or {}
        return {
            "contract_id": contract_id_block.get("piid", ""),
            "modification_number": contract_id_block.get("modificationNumber", "0"),
        }

    # =================================================================
    # Database operations
    # =================================================================

    def _get_existing_hashes(self, where_clause=None, where_params=None):
        """Fetch existing composite-key -> hash mappings from fpds_contract.

        Since the PK is (contract_id, modification_number), we concatenate
        them with a pipe separator for the in-memory dict.

        Args:
            where_clause: Optional additional WHERE condition (e.g.
                "AND naics_code = %s"). Must start with "AND".
            where_params: Parameters for the where_clause placeholders.

        Returns:
            dict of {"contract_id|modification_number": hash_string}
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = (
                "SELECT contract_id, modification_number, record_hash "
                "FROM fpds_contract WHERE record_hash IS NOT NULL"
            )
            params = []
            if where_clause:
                sql += f" {where_clause}"
                params = list(where_params or [])

            cursor.execute(sql, params)
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
        """Parse date string to YYYY-MM-DD format. Delegates to etl_utils.parse_date."""
        return parse_date(date_str)

    def _parse_decimal(self, value):
        """Parse a value to Decimal-compatible string. Delegates to etl_utils.parse_decimal."""
        return parse_decimal(value)

    # =================================================================
    # Hash fields accessor
    # =================================================================

    @staticmethod
    def get_hash_fields():
        """Return the list of fields used for award record hashing."""
        return list(_AWARD_HASH_FIELDS)
