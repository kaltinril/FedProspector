"""SAM.gov Exclusions loader.

Transforms SAM.gov Exclusions API responses into the sam_exclusion table.
Follows the same patterns as awards_loader.py: batch upserts with
change detection via SHA-256 hashing.

The sam_exclusion table has a single-column auto-increment PK (id).
Change detection uses a composite of uei + activation_date + exclusion_type
as the logical key for hash lookups.
"""

import json
import logging

from db.connection import get_connection
from etl.change_detector import ChangeDetector
from etl.etl_utils import parse_date
from etl.load_manager import LoadManager
from etl.staging_mixin import StagingMixin


logger = logging.getLogger("fed_prospector.etl.exclusions_loader")

# Fields used for record hash (business-meaningful fields only;
# excludes load-tracking timestamps)
_EXCLUSION_HASH_FIELDS = [
    "uei", "cage_code", "entity_name",
    "first_name", "middle_name", "last_name", "suffix", "prefix",
    "exclusion_type", "exclusion_program",
    "excluding_agency_code", "excluding_agency_name",
    "activation_date", "termination_date",
    "additional_comments",
]

# All sam_exclusion columns used in upsert (order matters for values list)
_UPSERT_COLS = [
    "uei", "cage_code", "entity_name",
    "first_name", "middle_name", "last_name", "suffix", "prefix",
    "exclusion_type", "exclusion_program",
    "excluding_agency_code", "excluding_agency_name",
    "activation_date", "termination_date",
    "additional_comments",
    "record_hash", "last_load_id",
]


def _make_exclusion_key(record):
    """Build a composite key string for hash lookups.

    Since exclusions don't have a single natural key, we use a combination
    of uei (or entity_name for individuals) + activation_date + exclusion_type.
    """
    identifier = record.get("uei") or record.get("entity_name") or ""
    act_date = record.get("activation_date") or ""
    exc_type = record.get("exclusion_type") or ""
    return f"{identifier}|{act_date}|{exc_type}"


class ExclusionsLoader(StagingMixin):
    """Load SAM.gov Exclusions API data into sam_exclusion table.

    Usage:
        loader = ExclusionsLoader()
        load_id = loader.load_manager.start_load("SAM_EXCLUSIONS", "FULL")
        stats = loader.load_exclusions(exclusions_data, load_id)
        loader.load_manager.complete_load(load_id, **stats)
    """

    _STG_TABLE = "stg_exclusion_raw"
    _STG_KEY_COLS = ["record_id"]

    BATCH_SIZE = 500

    def __init__(self, db_connection=None, change_detector=None, load_manager=None):
        """Initialize with optional DB connection, change detector, load manager.

        Args:
            db_connection: Not used (connections obtained from pool). Kept for
                           interface compatibility.
            change_detector: Optional ChangeDetector instance.
            load_manager: Optional LoadManager instance.
        """
        self.logger = logging.getLogger("fed_prospector.etl.exclusions_loader")
        self.change_detector = change_detector or ChangeDetector()
        self.load_manager = load_manager or LoadManager()

    # =================================================================
    # Public entry points
    # =================================================================

    def load_exclusions(self, exclusions_data, load_id):
        """Main entry point. Process list of raw SAM Exclusions API response dicts.

        Args:
            exclusions_data: list of raw exclusion dicts from SAM Exclusions API
                (items from the excludedEntity[] array).
            load_id: etl_load_log ID for this load.

        Returns:
            dict with keys: records_read, records_inserted, records_updated,
                records_unchanged, records_errored.
        """
        # Materialize generator (if any) to allow len() and re-iteration.
        exclusions_data = list(exclusions_data)
        self.logger.info(
            "Starting SAM Exclusions load (%d records, load_id=%d)",
            len(exclusions_data), load_id,
        )

        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_unchanged": 0,
            "records_errored": 0,
        }

        # Pre-fetch existing hashes keyed on the composite business key
        # uei|activation_date|exclusion_type.  A single-column lookup on
        # uei alone would give every record a different lookup key from the
        # composite key used below, so all records would always appear new.
        conn_h = get_connection()
        cur_h = conn_h.cursor()
        try:
            cur_h.execute(
                "SELECT CONCAT(COALESCE(uei,''), '|', COALESCE(activation_date,''), '|', COALESCE(exclusion_type,'')), record_hash "
                "FROM sam_exclusion WHERE record_hash IS NOT NULL"
            )
            existing_hashes = {row[0]: row[1] for row in cur_h.fetchall()}
        finally:
            cur_h.close()
            conn_h.close()

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        stg_conn, stg_cursor = self._open_stg_conn()

        try:
            batch_count = 0
            for raw in exclusions_data:
                stats["records_read"] += 1
                record_key = None
                staging_id = None
                try:
                    # --- staging write (before normalization) --------------
                    key_vals = self._extract_staging_key(raw)
                    staging_id = self._insert_staging(stg_cursor, load_id, key_vals, raw)

                    # --- normalise ----------------------------------------
                    exclusion_data = self._normalize_exclusion(raw)
                    record_key = _make_exclusion_key(exclusion_data)

                    # --- change detection ---------------------------------
                    new_hash = self.change_detector.compute_hash(
                        exclusion_data, _EXCLUSION_HASH_FIELDS
                    )
                    exclusion_data["record_hash"] = new_hash

                    old_hash = existing_hashes.get(record_key)
                    if old_hash and old_hash == new_hash:
                        stats["records_unchanged"] += 1
                        self._mark_staging(stg_cursor, staging_id, 'Y')
                        batch_count += 1
                        if batch_count >= self.BATCH_SIZE:
                            conn.commit()
                            batch_count = 0
                        continue

                    # --- upsert -------------------------------------------
                    outcome = self._upsert_exclusion(cursor, exclusion_data, load_id)
                    if outcome == "inserted":
                        stats["records_inserted"] += 1
                    elif outcome == "updated":
                        stats["records_updated"] += 1
                    else:
                        stats["records_unchanged"] += 1

                    # Update in-memory hash cache
                    existing_hashes[record_key] = new_hash

                    self._mark_staging(stg_cursor, staging_id, 'Y')

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
                        self._mark_staging(stg_cursor, staging_id, 'E', str(rec_exc))
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
            "SAM Exclusions load complete (load_id=%d): read=%d ins=%d upd=%d unch=%d err=%d",
            load_id,
            stats["records_read"],
            stats["records_inserted"],
            stats["records_updated"],
            stats["records_unchanged"],
            stats["records_errored"],
        )
        return stats

    def full_refresh(self, client, load_id):
        """Reload all active exclusions from the API.

        Fetches all exclusion records via the client and loads them into
        the sam_exclusion table. Existing records are updated via change
        detection; truly new records are inserted.

        Args:
            client: SAMExclusionsClient instance (already configured with API key).
            load_id: etl_load_log ID for this load.

        Returns:
            dict with load stats.
        """
        self.logger.info("Starting full exclusions refresh (load_id=%d)", load_id)

        all_exclusions = list(client.search_exclusions_all())
        self.logger.info("Fetched %d exclusion records from API", len(all_exclusions))

        return self.load_exclusions(all_exclusions, load_id)

    def check_prospects(self):
        """Check all entities in prospect table against exclusions.

        Joins prospect -> opportunity to get related entity data, then
        checks prospect_team_member UEIs against sam_exclusion.

        Returns:
            list[dict]: Matching exclusion records with prospect info.
                Each dict has keys: prospect_id, notice_id, uei, entity_name,
                exclusion_type, activation_date, termination_date.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Check prospect team members against exclusions
            cursor.execute(
                "SELECT ptm.prospect_id, ptm.uei_sam, ptm.role, "
                "       se.entity_name, se.exclusion_type, se.exclusion_program, "
                "       se.activation_date, se.termination_date, "
                "       se.excluding_agency_name "
                "FROM prospect_team_member ptm "
                "INNER JOIN sam_exclusion se ON ptm.uei_sam = se.uei "
                "WHERE se.uei IS NOT NULL AND se.uei != '' "
                "ORDER BY ptm.prospect_id"
            )
            results = cursor.fetchall()

            if results:
                self.logger.warning(
                    "Found %d prospect team member(s) with active exclusions!",
                    len(results),
                )
            else:
                self.logger.info("No prospect team members found in exclusions list.")

            return results
        finally:
            cursor.close()
            conn.close()

    def check_team_members(self):
        """Check entities in prospect_team_member against exclusions.

        This is an alias/convenience wrapper that returns the same data
        as check_prospects() but focused on team member details.

        Returns:
            list[dict]: Matching exclusion records with team member info.
                Each dict has keys: prospect_id, uei_sam, role, entity_name,
                exclusion_type, exclusion_program, activation_date,
                termination_date, excluding_agency_name.
        """
        return self.check_prospects()

    # =================================================================
    # Normalisation
    # =================================================================

    def _normalize_exclusion(self, raw):
        """Flatten the SAM Exclusions API v4 nested response to a flat dict
        matching sam_exclusion columns.

        The API returns a nested structure:
          exclusionDetails: {exclusionType, exclusionProgram, excludingAgencyCode, ...}
          exclusionIdentification: {ueiSAM, cageCode, entityName, firstName, ...}
          exclusionActions: {listOfActions: [{activateDate, terminationDate, ...}]}
          exclusionOtherInformation: {additionalComments, ...}

        Args:
            raw: Single exclusion dict from SAM Exclusions API excludedEntity[].

        Returns:
            dict: Normalised exclusion data matching sam_exclusion columns.
        """
        details = raw.get("exclusionDetails") or {}
        ident = raw.get("exclusionIdentification") or {}
        actions = raw.get("exclusionActions") or {}
        other_info = raw.get("exclusionOtherInformation") or {}

        # Get dates from first action entry
        action_list = actions.get("listOfActions") or []
        first_action = action_list[0] if action_list else {}

        return {
            "uei":                    ident.get("ueiSAM"),
            "cage_code":              ident.get("cageCode"),
            "entity_name":            (ident.get("entityName") or "").strip() or None,
            "first_name":             ident.get("firstName"),
            "middle_name":            ident.get("middleName"),
            "last_name":              ident.get("lastName"),
            "suffix":                 ident.get("suffix"),
            "prefix":                 ident.get("prefix"),
            "exclusion_type":         details.get("exclusionType"),
            "exclusion_program":      details.get("exclusionProgram"),
            "excluding_agency_code":  details.get("excludingAgencyCode"),
            "excluding_agency_name":  details.get("excludingAgencyName"),
            "activation_date":        parse_date(first_action.get("activateDate")),
            "termination_date":       parse_date(first_action.get("terminationDate")),
            "additional_comments":    other_info.get("additionalComments"),
        }

    # =================================================================
    # Database operations
    # =================================================================

    def _upsert_exclusion(self, cursor, exclusion_data, load_id):
        """INSERT or UPDATE for sam_exclusion.

        Since there is no natural unique key on exclusions (the PK is auto-increment),
        we check for existing records by matching on uei + activation_date + exclusion_type.
        If found, we update; otherwise we insert.

        Args:
            cursor: Active DB cursor.
            exclusion_data: Normalised exclusion dict.
            load_id: Current load ID.

        Returns:
            'inserted', 'updated', or 'unchanged'.
        """
        # Check if this exclusion already exists
        uei = exclusion_data.get("uei")
        entity_name = exclusion_data.get("entity_name")
        activation_date = exclusion_data.get("activation_date")
        exclusion_type = exclusion_data.get("exclusion_type")

        if uei:
            cursor.execute(
                "SELECT id, record_hash FROM sam_exclusion "
                "WHERE uei = %s AND activation_date <=> %s AND exclusion_type <=> %s "
                "LIMIT 1",
                (uei, activation_date, exclusion_type),
            )
        elif entity_name:
            cursor.execute(
                "SELECT id, record_hash FROM sam_exclusion "
                "WHERE entity_name = %s AND activation_date <=> %s AND exclusion_type <=> %s "
                "AND (uei IS NULL OR uei = '') "
                "LIMIT 1",
                (entity_name, activation_date, exclusion_type),
            )
        else:
            # No UEI or entity_name -- always insert
            cursor.execute("SELECT NULL WHERE FALSE")

        existing = cursor.fetchone()

        if existing:
            # Update existing record
            existing_id = existing["id"]
            set_pairs = ", ".join(f"{c} = %s" for c in _UPSERT_COLS)
            sql = (
                f"UPDATE sam_exclusion SET {set_pairs}, last_updated_at = NOW() "
                f"WHERE id = %s"
            )
            values = [exclusion_data.get(c) if c != "last_load_id" else load_id
                      for c in _UPSERT_COLS]
            values.append(existing_id)
            cursor.execute(sql, values)
            return "updated"
        else:
            # Insert new record
            col_list = ", ".join(_UPSERT_COLS)
            placeholders = ", ".join(["%s"] * len(_UPSERT_COLS))
            sql = (
                f"INSERT INTO sam_exclusion ({col_list}, first_loaded_at, last_updated_at) "
                f"VALUES ({placeholders}, NOW(), NOW())"
            )
            values = [exclusion_data.get(c) if c != "last_load_id" else load_id
                      for c in _UPSERT_COLS]
            cursor.execute(sql, values)
            return "inserted"

    # =================================================================
    # Raw staging helpers
    # =================================================================

    def _extract_staging_key(self, raw):
        """Extract the composite business key from a raw exclusion dict.

        Mirrors the field extraction logic in _normalize_exclusion() so that
        the staging key matches the change-detection key.  The SAM.gov
        exclusions API nests these fields; reading top-level flat keys (e.g.
        "uei", "activationDate") always returns empty strings and produces an
        all-empty composite "||", making staging useless for replay/debugging.

        Returns:
            dict with record_id (composite key string, max 100 chars).
        """
        eid = raw.get("exclusionIdentification") or {}
        actions = (raw.get("exclusionActions") or {}).get("listOfActions") or [{}]
        uei = eid.get("ueiSAM") or eid.get("cageCode") or eid.get("npi") or ""
        act_date = actions[0].get("activateDate", "") if actions else ""
        ex_type_raw = raw.get("exclusionType")
        if isinstance(ex_type_raw, dict):
            ex_type = ex_type_raw.get("value", "")
        else:
            ex_type = ex_type_raw or ""
        composite = f"{uei}|{act_date}|{ex_type}"
        return {"record_id": composite[:100]}

    # =================================================================
    # Hash fields accessor
    # =================================================================

    @staticmethod
    def get_hash_fields():
        """Return the list of fields used for exclusion record hashing."""
        return list(_EXCLUSION_HASH_FIELDS)
