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
from datetime import datetime, date

from db.connection import get_connection
from etl.change_detector import ChangeDetector
from etl.load_manager import LoadManager


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


class ExclusionsLoader:
    """Load SAM.gov Exclusions API data into sam_exclusion table.

    Usage:
        loader = ExclusionsLoader()
        load_id = loader.load_manager.start_load("SAM_EXCLUSIONS", "FULL")
        stats = loader.load_exclusions(exclusions_data, load_id)
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

        # Pre-fetch existing hashes for change detection.
        existing_hashes = self._get_existing_hashes()

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            batch_count = 0
            for raw in exclusions_data:
                stats["records_read"] += 1
                record_key = None
                try:
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
            "activation_date":        self._parse_date(first_action.get("activateDate")),
            "termination_date":       self._parse_date(first_action.get("terminationDate")),
            "additional_comments":    other_info.get("additionalComments"),
        }

    # =================================================================
    # Database operations
    # =================================================================

    def _get_existing_hashes(self):
        """Fetch existing exclusion-key -> hash mappings from sam_exclusion.

        Builds composite keys from uei/entity_name + activation_date + exclusion_type.

        Returns:
            dict of {"key": hash_string}
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT uei, entity_name, activation_date, exclusion_type, record_hash "
                "FROM sam_exclusion WHERE record_hash IS NOT NULL"
            )
            result = {}
            for row in cursor.fetchall():
                record = {
                    "uei": row["uei"],
                    "entity_name": row["entity_name"],
                    "activation_date": str(row["activation_date"]) if row["activation_date"] else "",
                    "exclusion_type": row["exclusion_type"],
                }
                key = _make_exclusion_key(record)
                result[key] = row["record_hash"]
            return result
        finally:
            cursor.close()
            conn.close()

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
    # Parsing helpers
    # =================================================================

    def _parse_date(self, date_str):
        """Parse date string to YYYY-MM-DD format.

        Handles: MM/DD/YYYY, MM-DD-YYYY, YYYY-MM-DD, ISO 8601 datetime, None/empty.

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

        # MM-DD-YYYY (SAM Exclusions API format)
        if len(s) == 10 and s[2] == "-" and s[5] == "-":
            return f"{s[6:10]}-{s[0:2]}-{s[3:5]}"

        # Fallback
        return s

    # =================================================================
    # Hash fields accessor
    # =================================================================

    @staticmethod
    def get_hash_fields():
        """Return the list of fields used for exclusion record hashing."""
        return list(_EXCLUSION_HASH_FIELDS)
