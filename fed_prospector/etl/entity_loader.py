"""Entity loader: transforms SAM.gov JSON entity data into normalized MySQL tables.

Handles loading from both monthly/daily JSON extract files and API responses.
Normalizes nested JSON into 1 parent table (entity) and 8 child tables, with
change detection via SHA-256 hashing and field-level history tracking.
"""

import hashlib
import json
import logging
from datetime import datetime

from db.connection import get_connection
from etl.change_detector import ChangeDetector
from etl.data_cleaner import DataCleaner
from etl.etl_utils import parse_date
from etl.load_manager import LoadManager

# ---------------------------------------------------------------------------
# Registration status mapping: API text -> single-char DB code
# ---------------------------------------------------------------------------
_REG_STATUS_MAP = {
    "Active":   "A",
    "Inactive": "I",
    "Expired":  "E",
    "Draft":    "D",
}

# ---------------------------------------------------------------------------
# POC type keys in the JSON -> poc_type value stored in entity_poc
# ---------------------------------------------------------------------------
_POC_TYPES = [
    "governmentBusinessPOC",
    "electronicBusinessPOC",
    "governmentBusinessAlternatePOC",
    "electronicBusinessAlternatePOC",
    "pastPerformancePOC",
    "pastPerformanceAlternatePOC",
]

# ---------------------------------------------------------------------------
# Fields used for entity record hash (all meaningful business fields,
# excludes timestamps and load-tracking columns)
# ---------------------------------------------------------------------------
_ENTITY_HASH_FIELDS = [
    "uei_sam", "uei_duns", "cage_code", "dodaac",
    "registration_status", "purpose_of_registration",
    "initial_registration_date", "registration_expiration_date",
    "last_update_date", "activation_date",
    "legal_business_name", "dba_name",
    "entity_division", "entity_division_number",
    "dnb_open_data_flag", "entity_start_date",
    "fiscal_year_end_close", "entity_url",
    "entity_structure_code", "entity_type_code",
    "profit_structure_code", "organization_structure_code",
    "state_of_incorporation", "country_of_incorporation",
    "primary_naics",
    "credit_card_usage", "correspondence_flag",
    "debt_subject_to_offset", "exclusion_status_flag",
    "no_public_display_flag", "evs_source",
]


class EntityLoader:
    """Load SAM.gov entity data into normalised MySQL tables."""

    BATCH_SIZE = 1000

    # -----------------------------------------------------------------
    # Construction
    # -----------------------------------------------------------------
    def __init__(self, change_detector=None, data_cleaner=None, load_manager=None):
        self.logger = logging.getLogger("fed_prospector.etl.entity_loader")
        self.change_detector = change_detector or ChangeDetector()
        self.data_cleaner = data_cleaner or DataCleaner()
        self.load_manager = load_manager or LoadManager()

    # =================================================================
    # Public entry points
    # =================================================================

    def load_from_json_extract(self, json_file_path, mode="full"):
        """Load entities from a SAM.gov monthly/daily JSON extract file.

        Args:
            json_file_path: Path to the JSON file (may be large, streamed).
            mode: 'full' or 'incremental'.

        Returns:
            dict with load statistics.
        """
        load_type = "FULL" if mode == "full" else "INCREMENTAL"
        load_id = self.load_manager.start_load(
            source_system="SAM_ENTITY",
            load_type=load_type,
            source_file=str(json_file_path),
        )
        self.logger.info(
            "Starting %s entity load from %s (load_id=%d)",
            load_type, json_file_path, load_id,
        )

        try:
            self.data_cleaner.reset_stats()
            stats = self._process_entities(
                self._stream_json_file(json_file_path), load_id
            )
            stats["cleaning_stats"] = self.data_cleaner.get_stats()
            self.load_manager.complete_load(load_id, **{
                k: v for k, v in stats.items() if k != "cleaning_stats"
            })
            self.logger.info("Load %d complete: %s", load_id, stats)
            return stats
        except Exception as exc:
            self.load_manager.fail_load(load_id, str(exc))
            self.logger.exception("Load %d failed", load_id)
            raise

    def load_from_api_response(self, entity_data_list, mode="incremental",
                               extra_parameters=None):
        """Load entities already parsed from SAM.gov API responses.

        Args:
            entity_data_list: List of entity dicts (parsed JSON objects).
            mode: 'full' or 'incremental'.
            extra_parameters: Optional dict merged into load log parameters.

        Returns:
            dict with load statistics.
        """
        load_type = "FULL" if mode == "full" else "INCREMENTAL"
        params = {"source": "api", "count": len(entity_data_list)}
        if extra_parameters:
            params.update(extra_parameters)
        load_id = self.load_manager.start_load(
            source_system="SAM_ENTITY",
            load_type=load_type,
            parameters=params,
        )
        self.logger.info(
            "Starting %s entity load from API (%d records, load_id=%d)",
            load_type, len(entity_data_list), load_id,
        )

        try:
            stats = self._process_entities(iter(entity_data_list), load_id, write_staging=True)
            self.load_manager.complete_load(load_id, **stats)
            self.logger.info("Load %d complete: %s", load_id, stats)
            return stats
        except Exception as exc:
            self.load_manager.fail_load(load_id, str(exc))
            self.logger.exception("Load %d failed", load_id)
            raise

    def load_entity_batch(self, entity_data_list, load_id):
        """Process a batch of entities under an existing load_id.

        Unlike load_from_api_response, does NOT create or complete a load
        entry — the caller manages the load lifecycle. Used for page-by-page
        loading where progress is saved after each page.

        Args:
            entity_data_list: List of entity dicts (parsed JSON objects).
            load_id: Existing load_id from LoadManager.start_load().

        Returns:
            dict with batch statistics (records_read, records_inserted, etc.).
        """
        return self._process_entities(iter(entity_data_list), load_id, write_staging=True)

    # =================================================================
    # Core processing pipeline
    # =================================================================

    def _process_entities(self, entity_iter, load_id, write_staging=False):
        """Iterate over raw entities, normalise, clean, detect changes, upsert.

        Processes in batches of BATCH_SIZE and commits after each batch.
        Returns a stats dict compatible with LoadManager.complete_load().

        Args:
            entity_iter: Iterator of raw entity dicts.
            load_id: Current load identifier.
            write_staging: When True, writes each raw record to stg_entity_raw
                           before processing (used by load_from_api_response).
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
            "entity", "uei_sam", "record_hash"
        )

        # Open a dedicated autocommit connection for staging writes (API path only).
        # Initialize both to None before the try so the finally block can guard safely.
        stg_conn, stg_cursor = None, None
        if write_staging:
            try:
                stg_conn = get_connection()
                stg_conn.autocommit = True
                stg_cursor = stg_conn.cursor()
            except Exception:
                if stg_conn:
                    stg_conn.close()
                raise

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            batch_count = 0
            for raw_json in entity_iter:
                stats["records_read"] += 1
                uei_sam = None
                key_vals = None
                try:
                    # --- staging write (API path only) ----------------------------
                    if write_staging:
                        key_vals = self._extract_staging_key(raw_json)
                        self._insert_staging_entity(stg_cursor, load_id, key_vals, raw_json)

                    # --- clean (before normalisation, needs nested JSON) ----------
                    self.data_cleaner.clean_entity_record(raw_json)

                    # --- normalise -------------------------------------------------
                    entity_data = self._normalize_entity(raw_json)
                    uei_sam = entity_data.get("uei_sam")
                    if not uei_sam:
                        raise ValueError("Missing uei_sam in entity record")

                    # --- change detection ------------------------------------------
                    new_hash = self.change_detector.compute_hash(
                        entity_data, _ENTITY_HASH_FIELDS
                    )
                    entity_data["record_hash"] = new_hash

                    old_hash = existing_hashes.get(uei_sam)
                    if old_hash and old_hash == new_hash:
                        stats["records_unchanged"] += 1
                        if write_staging:
                            self._mark_staging_entity(stg_cursor, load_id, key_vals["uei_sam"], 'Y')
                        batch_count += 1
                        if batch_count >= self.BATCH_SIZE:
                            conn.commit()
                            batch_count = 0
                        continue

                    # --- fetch old record for history (updates only) ---------------
                    if old_hash is not None:
                        old_record = self._fetch_entity_row(cursor, uei_sam)
                    else:
                        old_record = None

                    # --- upsert parent ---------------------------------------------
                    outcome = self._upsert_entity(conn, cursor, entity_data, load_id)
                    if outcome == "inserted":
                        stats["records_inserted"] += 1
                    elif outcome == "updated":
                        stats["records_updated"] += 1
                    else:
                        stats["records_unchanged"] += 1

                    # --- history logging (updates only) ----------------------------
                    if old_record is not None and outcome == "updated":
                        diffs = self.change_detector.compute_field_diff(
                            old_record, entity_data, _ENTITY_HASH_FIELDS
                        )
                        if diffs:
                            self._insert_history(cursor, uei_sam, diffs, load_id)

                    # --- child records ---------------------------------------------
                    children = self._extract_child_records(raw_json, uei_sam)
                    for table_name, rows in children.items():
                        key_cols = _CHILD_KEY_COLUMNS.get(table_name, [])
                        self._sync_child_records(
                            conn, cursor, uei_sam, table_name, rows, key_cols
                        )

                    # Update in-memory hash cache
                    existing_hashes[uei_sam] = new_hash

                    # --- mark staging success (API path only) ----------------------
                    if write_staging:
                        self._mark_staging_entity(stg_cursor, load_id, key_vals["uei_sam"], 'Y')

                except Exception as rec_exc:
                    stats["records_errored"] += 1
                    identifier = uei_sam or f"record#{stats['records_read']}"
                    self.logger.warning(
                        "Error processing %s: %s", identifier, rec_exc
                    )
                    self.load_manager.log_record_error(
                        load_id,
                        record_identifier=identifier,
                        error_type=type(rec_exc).__name__,
                        error_message=str(rec_exc),
                        raw_data=json.dumps(raw_json) if isinstance(raw_json, dict) else str(raw_json),
                    )
                    # --- mark staging error (API path only) ------------------------
                    if write_staging and key_vals is not None:
                        stg_uei = key_vals.get("uei_sam", "")
                        self._mark_staging_entity(stg_cursor, load_id, stg_uei, 'E', str(rec_exc))
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
            if stg_cursor:
                stg_cursor.close()
            if stg_conn:
                stg_conn.close()

        return stats

    # =================================================================
    # JSON streaming
    # =================================================================

    @staticmethod
    def _stream_json_file(file_path):
        """Yield individual entity dicts from a JSON extract file.

        Supports two formats:
        - Top-level JSON array:  [{ ... }, { ... }, ...]
        - Object with entityData key: {"entityData": [{ ... }, ...]}

        Uses ijson for true streaming when available; falls back to
        loading the whole file with stdlib json.
        """
        try:
            import ijson  # optional streaming dependency

            with open(file_path, "rb") as fh:
                # Try the wrapper-object format first
                # SAM extracts commonly use {"entityData": [...]}
                found = False
                for entity in ijson.items(fh, "entityData.item"):
                    found = True
                    yield entity

                if not found:
                    # Rewind and try top-level array
                    fh.seek(0)
                    for entity in ijson.items(fh, "item"):
                        yield entity

        except ImportError:
            # Fallback: load entire file (fine for smaller files)
            with open(file_path, "r", encoding="utf-8") as fh:
                data = json.load(fh)

            if isinstance(data, list):
                yield from data
            elif isinstance(data, dict) and "entityData" in data:
                yield from data["entityData"]
            else:
                raise ValueError(
                    f"Unrecognised JSON structure in {file_path}. "
                    "Expected a top-level array or an object with 'entityData'."
                )

    # =================================================================
    # Normalisation helpers
    # =================================================================

    def _normalize_entity(self, raw_json):
        """Flatten nested SAM.gov JSON into a dict matching entity table columns."""
        reg = _safe_get(raw_json, "entityRegistration") or {}
        core = _safe_get(raw_json, "coreData") or {}
        info = _safe_get(core, "entityInformation") or {}
        gen = _safe_get(core, "generalInformation") or {}
        fin = _safe_get(core, "financialInformation") or {}
        assertions = _safe_get(raw_json, "assertions") or {}
        goods = _safe_get(assertions, "goodsAndServices") or {}

        status_text = reg.get("registrationStatus") or ""
        status_code = _REG_STATUS_MAP.get(status_text, status_text[:1] if status_text else None)

        return {
            "uei_sam":                     reg.get("ueiSAM"),
            "uei_duns":                    reg.get("ueiDUNS"),
            "cage_code":                   reg.get("cageCode"),
            "dodaac":                      reg.get("dodaac"),
            "registration_status":         status_code,
            "purpose_of_registration":     reg.get("purposeOfRegistrationCode"),
            "initial_registration_date":   parse_date(reg.get("registrationDate")),
            "registration_expiration_date": parse_date(reg.get("expirationDate")),
            "last_update_date":            parse_date(reg.get("lastUpdateDate")),
            "activation_date":             parse_date(reg.get("activationDate")),
            "legal_business_name":         reg.get("legalBusinessName"),
            "dba_name":                    reg.get("dbaName"),
            "entity_division":             info.get("entityDivisionName"),
            "entity_division_number":      info.get("entityDivisionNumber"),
            "dnb_open_data_flag":          reg.get("dnbOpenData"),
            "entity_start_date":           parse_date(info.get("entityStartDate")),
            "fiscal_year_end_close":       info.get("fiscalYearEndCloseDate"),
            "entity_url":                  info.get("entityURL"),
            "entity_structure_code":       gen.get("entityStructureCode"),
            "entity_type_code":            gen.get("entityTypeCode"),
            "profit_structure_code":       gen.get("profitStructureCode"),
            "organization_structure_code": gen.get("organizationStructureCode"),
            "state_of_incorporation":      gen.get("stateOfIncorporationCode"),
            "country_of_incorporation":    gen.get("countryOfIncorporationCode"),
            "primary_naics":               goods.get("primaryNaics"),
            "credit_card_usage":           fin.get("creditCardUsage"),
            "correspondence_flag":         reg.get("correspondenceFlag"),
            "debt_subject_to_offset":      fin.get("debtSubjectToOffset"),
            "exclusion_status_flag":       reg.get("exclusionStatusFlag"),
            "no_public_display_flag":      reg.get("noPublicDisplayFlag"),
            "evs_source":                  reg.get("evsSource"),
        }

    def _extract_child_records(self, raw_json, uei_sam):
        """Extract all child-table rows from nested JSON.

        Returns:
            dict of {table_name: [row_dict, ...]}
        """
        children = {}

        core = _safe_get(raw_json, "coreData") or {}
        assertions = _safe_get(raw_json, "assertions") or {}
        goods = _safe_get(assertions, "goodsAndServices") or {}
        disaster = _safe_get(assertions, "disasterReliefData") or {}
        pocs = _safe_get(raw_json, "pointsOfContact") or {}
        biz_types = _safe_get(core, "businessTypes") or {}

        # --- entity_address (physical + mailing) --------------------------
        addresses = []
        for addr_key, addr_type in [("physicalAddress", "PHYSICAL"), ("mailingAddress", "MAILING")]:
            addr = _safe_get(core, addr_key)
            if addr:
                addresses.append({
                    "uei_sam":              uei_sam,
                    "address_type":         addr_type,
                    "address_line_1":       addr.get("addressLine1"),
                    "address_line_2":       addr.get("addressLine2"),
                    "city":                 addr.get("city"),
                    "state_or_province":    addr.get("stateOrProvinceCode"),
                    "zip_code":             addr.get("zipCode"),
                    "zip_code_plus4":       addr.get("zipCodePlus4"),
                    "country_code":         addr.get("countryCode"),
                    "congressional_district": addr.get("congressionalDistrict"),
                })
        children["entity_address"] = addresses

        # --- entity_naics -------------------------------------------------
        naics_list = goods.get("naicsList") or []
        primary_naics = goods.get("primaryNaics")
        naics_rows = []
        for item in naics_list:
            code = item.get("naicsCode")
            if code:
                naics_rows.append({
                    "uei_sam":           uei_sam,
                    "naics_code":        str(code),
                    "is_primary":        "Y" if str(code) == str(primary_naics) else "N",
                    "sba_small_business": item.get("sbaSmallBusiness"),
                    "naics_exception":   item.get("naicsException"),
                })
        children["entity_naics"] = naics_rows

        # --- entity_psc ---------------------------------------------------
        psc_list = goods.get("pscList") or []
        children["entity_psc"] = [
            {"uei_sam": uei_sam, "psc_code": p.get("pscCode")}
            for p in psc_list if p.get("pscCode")
        ]

        # --- entity_business_type -----------------------------------------
        bt_list = biz_types.get("businessTypeList") or []
        children["entity_business_type"] = [
            {"uei_sam": uei_sam, "business_type_code": bt.get("businessTypeCode")}
            for bt in bt_list if bt.get("businessTypeCode")
        ]

        # --- entity_sba_certification -------------------------------------
        sba_list = biz_types.get("sbaBusinessTypeList") or []
        sba_rows = []
        for sba in sba_list:
            code = sba.get("sbaBusinessTypeCode")
            if code:
                sba_rows.append({
                    "uei_sam":                   uei_sam,
                    "sba_type_code":             code,
                    "sba_type_desc":             sba.get("sbaBusinessTypeDescription"),
                    "certification_entry_date":  parse_date(sba.get("certificationEntryDate")),
                    "certification_exit_date":   parse_date(sba.get("certificationExitDate")),
                })
        children["entity_sba_certification"] = sba_rows

        # --- entity_poc ---------------------------------------------------
        poc_rows = []
        for poc_key in _POC_TYPES:
            poc = _safe_get(pocs, poc_key)
            if poc and _has_poc_data(poc):
                poc_rows.append({
                    "uei_sam":          uei_sam,
                    "poc_type":         poc_key,
                    "first_name":       poc.get("firstName"),
                    "middle_initial":   poc.get("middleInitial"),
                    "last_name":        poc.get("lastName"),
                    "title":            poc.get("title"),
                    "address_line_1":   poc.get("addressLine1"),
                    "address_line_2":   poc.get("addressLine2"),
                    "city":             poc.get("city"),
                    "state_or_province": poc.get("stateOrProvince"),
                    "zip_code":         poc.get("zipCode"),
                    "zip_code_plus4":   poc.get("zipCodePlus4"),
                    "country_code":     poc.get("countryCode"),
                })
        children["entity_poc"] = poc_rows

        # --- entity_disaster_response -------------------------------------
        geo_list = disaster.get("geographicalAreaServed") or []
        dr_rows = []
        for geo in geo_list:
            dr_rows.append({
                "uei_sam":     uei_sam,
                "state_code":  geo.get("geographicalAreaServedStateCode"),
                "state_name":  geo.get("geographicalAreaServedStateName"),
                "county_code": geo.get("geographicalAreaServedCountyCode"),
                "county_name": geo.get("geographicalAreaServedCountyName"),
                "msa_code":    geo.get("geographicalAreaServedmetropolitanStatisticalAreaCode"),
                "msa_name":    geo.get("geographicalAreaServedmetropolitanStatisticalAreaName"),
            })
        children["entity_disaster_response"] = dr_rows

        return children

    # =================================================================
    # Staging helpers (API path only)
    # =================================================================

    def _extract_staging_key(self, raw: dict) -> dict:
        """Return the natural key dict for a raw entity record."""
        return {"uei_sam": raw.get("entityRegistration", {}).get("ueiSAM", "")}

    def _insert_staging_entity(self, stg_cursor, load_id, key_vals: dict, raw: dict):
        """Insert a raw entity record into stg_entity_raw before processing."""
        raw_str = json.dumps(raw, sort_keys=True, default=str)
        raw_hash = hashlib.sha256(raw_str.encode()).hexdigest()
        stg_cursor.execute(
            "INSERT INTO stg_entity_raw (load_id, uei_sam, raw_json, raw_record_hash) "
            "VALUES (%s, %s, %s, %s)",
            (load_id, key_vals["uei_sam"], raw_str, raw_hash),
        )
        # No lastrowid — tracking is done via uei_sam + load_id

    def _mark_staging_entity(self, stg_cursor, load_id, uei_sam, processed: str, error_msg=None):
        """Update the stg_entity_raw row with processing outcome."""
        stg_cursor.execute(
            "UPDATE stg_entity_raw SET processed=%s, processed_at=NOW(), error_message=%s "
            "WHERE load_id=%s AND uei_sam=%s",
            (processed, error_msg[:500] if error_msg else None, load_id, uei_sam),
        )

    # =================================================================
    # Database operations
    # =================================================================

    def _upsert_entity(self, conn, cursor, entity_data, load_id):
        """INSERT ... ON DUPLICATE KEY UPDATE for the entity table.

        Returns:
            'inserted', 'updated', or 'unchanged'
        """
        cols = [
            "uei_sam", "uei_duns", "cage_code", "dodaac",
            "registration_status", "purpose_of_registration",
            "initial_registration_date", "registration_expiration_date",
            "last_update_date", "activation_date",
            "legal_business_name", "dba_name",
            "entity_division", "entity_division_number",
            "dnb_open_data_flag", "entity_start_date",
            "fiscal_year_end_close", "entity_url",
            "entity_structure_code", "entity_type_code",
            "profit_structure_code", "organization_structure_code",
            "state_of_incorporation", "country_of_incorporation",
            "primary_naics",
            "credit_card_usage", "correspondence_flag",
            "debt_subject_to_offset", "exclusion_status_flag",
            "no_public_display_flag", "evs_source",
            "record_hash", "last_load_id",
        ]

        placeholders = ", ".join(["%s"] * len(cols))
        col_list = ", ".join(cols)

        # ON DUPLICATE KEY UPDATE: update all mutable columns
        update_pairs = ", ".join(
            f"{c} = VALUES({c})" for c in cols if c != "uei_sam"
        )
        # Also update last_loaded_at on every touch
        update_pairs += ", last_loaded_at = NOW()"

        sql = (
            f"INSERT INTO entity ({col_list}, first_loaded_at, last_loaded_at) "
            f"VALUES ({placeholders}, NOW(), NOW()) "
            f"ON DUPLICATE KEY UPDATE {update_pairs}"
        )

        values = [entity_data.get(c) for c in cols[:-1]]  # all except last_load_id
        values.append(load_id)  # last_load_id

        cursor.execute(sql, values)

        # MySQL returns rowcount: 0 = unchanged, 1 = inserted, 2 = updated
        rc = cursor.rowcount
        if rc == 1:
            return "inserted"
        elif rc == 2:
            return "updated"
        return "unchanged"

    def _sync_child_records(self, conn, cursor, uei_sam, table_name, new_records, key_columns):
        """Replace child records for a given uei_sam via delete + insert.

        Args:
            conn: Active database connection.
            cursor: Active cursor.
            uei_sam: Parent entity key.
            table_name: Child table name.
            new_records: List of row dicts to insert.
            key_columns: Not used in delete+insert strategy but kept for API consistency.
        """
        # Delete existing rows for this entity
        cursor.execute(f"DELETE FROM {table_name} WHERE uei_sam = %s", (uei_sam,))

        if not new_records:
            return

        # Build the INSERT statement from the first record's keys
        # (exclude 'id' since it is auto-increment)
        cols = [k for k in new_records[0].keys() if k != "id"]
        col_list = ", ".join(cols)
        placeholders = ", ".join(["%s"] * len(cols))
        sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"

        rows = [tuple(row.get(c) for c in cols) for row in new_records]
        cursor.executemany(sql, rows)

    # =================================================================
    # History / fetch helpers
    # =================================================================

    def _fetch_entity_row(self, cursor, uei_sam):
        """Fetch the current entity row as a dict for diff comparison."""
        cursor.execute("SELECT * FROM entity WHERE uei_sam = %s", (uei_sam,))
        row = cursor.fetchone()
        if row is None:
            return None
        # cursor is dictionary=True, so row is already a dict.
        # Convert date/datetime values to strings for comparison.
        clean = {}
        for k, v in row.items():
            if isinstance(v, (datetime,)):
                clean[k] = v.strftime("%Y-%m-%d %H:%M:%S")
            elif hasattr(v, "isoformat"):
                clean[k] = v.isoformat()
            else:
                clean[k] = v
        return clean

    def _insert_history(self, cursor, uei_sam, diffs, load_id):
        """Write field-level change records to entity_history."""
        sql = (
            "INSERT INTO entity_history (uei_sam, field_name, old_value, new_value, load_id) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        rows = [
            (uei_sam, field, _str_or_none(old_val), _str_or_none(new_val), load_id)
            for field, old_val, new_val in diffs
        ]
        cursor.executemany(sql, rows)

    # =================================================================
    # Hash fields accessor
    # =================================================================

    @staticmethod
    def _get_entity_hash_fields():
        """Return the list of fields used for entity record hashing."""
        return list(_ENTITY_HASH_FIELDS)


# =====================================================================
# Module-level helper functions
# =====================================================================

# Key columns used by _sync_child_records (for documentation / future use)
_CHILD_KEY_COLUMNS = {
    "entity_address":           ["uei_sam", "address_type"],
    "entity_naics":             ["uei_sam", "naics_code"],
    "entity_psc":               ["uei_sam", "psc_code"],
    "entity_business_type":     ["uei_sam", "business_type_code"],
    "entity_sba_certification": ["uei_sam", "sba_type_code"],
    "entity_poc":               ["uei_sam", "poc_type"],
    "entity_disaster_response": ["uei_sam"],
}


def _safe_get(d, key):
    """Return d[key] if d is a dict and key exists, else None."""
    if isinstance(d, dict):
        return d.get(key)
    return None


def _str_or_none(val):
    """Convert a value to str for history logging, preserving None."""
    if val is None:
        return None
    return str(val)


def _has_poc_data(poc_dict):
    """Return True if the POC dict contains at least a name."""
    return bool(
        poc_dict.get("firstName")
        or poc_dict.get("lastName")
    )
