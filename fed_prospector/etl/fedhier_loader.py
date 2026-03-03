"""Federal Hierarchy loader.

Transforms SAM.gov Federal Hierarchy API responses into the federal_organization
table. Supports full refresh (TRUNCATE + reload) and incremental upserts with
SHA-256 change detection.

The federal_organization table has a single PK of fh_org_id (INT).
Parent-child relationships are tracked via parent_org_id (self-referencing FK).
"""

import json
import logging

from db.connection import get_connection
from etl.change_detector import ChangeDetector
from etl.etl_utils import fetch_existing_hashes, parse_date
from etl.load_manager import LoadManager
from etl.staging_mixin import StagingMixin


logger = logging.getLogger("fed_prospector.etl.fedhier_loader")

# Fields used for record hash (business-meaningful fields only;
# excludes load-tracking timestamps)
_ORG_HASH_FIELDS = [
    "fh_org_id", "fh_org_name", "fh_org_type", "description", "status",
    "agency_code", "oldfpds_office_code", "cgac", "parent_org_id", "level",
]

# All federal_organization columns used in upsert (order matters for values list)
_UPSERT_COLS = [
    "fh_org_id", "fh_org_name", "fh_org_type", "description", "status",
    "agency_code", "oldfpds_office_code", "cgac", "parent_org_id", "level",
    "created_date", "last_modified_date",
    "record_hash", "last_load_id",
]


# Mapping from fhorgtype API values to hierarchy level
_ORG_TYPE_LEVELS = {
    "Department/Ind. Agency": 1,
    "Sub-Tier": 2,
    "Office": 3,
}


class FedHierLoader(StagingMixin):
    """Load SAM.gov Federal Hierarchy API data into federal_organization table.

    Usage:
        loader = FedHierLoader()
        load_id = loader.load_manager.start_load("SAM_FEDHIER", "FULL")
        stats = loader.load_organizations(orgs_data, load_id)
        loader.load_manager.complete_load(load_id, **stats)
    """

    BATCH_SIZE = 500
    _STG_TABLE = "stg_fedhier_raw"
    _STG_KEY_COLS = ["fh_org_id"]

    def __init__(self, db_connection=None, change_detector=None, load_manager=None):
        """Initialize with optional DB connection, change detector, load manager.

        Args:
            db_connection: Not used (connections obtained from pool). Kept for
                           interface compatibility.
            change_detector: Optional ChangeDetector instance.
            load_manager: Optional LoadManager instance.
        """
        self.logger = logging.getLogger("fed_prospector.etl.fedhier_loader")
        self.change_detector = change_detector or ChangeDetector()
        self.load_manager = load_manager or LoadManager()

    # =================================================================
    # Public entry points
    # =================================================================

    def load_organizations(self, orgs_data, load_id):
        """Process list of raw Federal Hierarchy API response dicts.

        Uses upsert with change detection (SHA-256 hashing) for each record.

        Args:
            orgs_data: list of raw org dicts from Federal Hierarchy API
                (items from the orglist[] array).
            load_id: etl_load_log ID for this load.

        Returns:
            dict with keys: records_read, records_inserted, records_updated,
                records_unchanged, records_errored.
        """
        # Materialize generator (if any) so len() is safe and we can iterate twice
        orgs_data = list(orgs_data)
        self.logger.info(
            "Starting Federal Hierarchy load (%d records, load_id=%d)",
            len(orgs_data), load_id,
        )

        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_unchanged": 0,
            "records_errored": 0,
        }

        # Pre-fetch existing hashes for change detection
        existing_hashes = fetch_existing_hashes("federal_organization", "fh_org_id")

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        stg_conn, stg_cursor = self._open_stg_conn()
        try:
            batch_count = 0
            for raw in orgs_data:
                stats["records_read"] += 1
                record_key = None
                staging_id = None
                try:
                    # --- staging write ------------------------------------
                    key_vals = self._extract_staging_key(raw)
                    staging_id = self._insert_staging(stg_cursor, load_id, key_vals, raw)

                    # --- normalise ----------------------------------------
                    org_data = self._normalize_org(raw)
                    fh_org_id = org_data.get("fh_org_id")
                    if not fh_org_id:
                        raise ValueError("Missing fhorgid in organization record")

                    record_key = str(fh_org_id)

                    # --- change detection ---------------------------------
                    new_hash = self.change_detector.compute_hash(
                        org_data, _ORG_HASH_FIELDS
                    )
                    org_data["record_hash"] = new_hash

                    old_hash = existing_hashes.get(fh_org_id)
                    if old_hash and old_hash == new_hash:
                        stats["records_unchanged"] += 1
                        self._mark_staging(stg_cursor, staging_id, "Y")
                        batch_count += 1
                        if batch_count >= self.BATCH_SIZE:
                            conn.commit()
                            batch_count = 0
                        continue

                    # --- upsert -------------------------------------------
                    outcome = self._upsert_org(cursor, org_data, load_id)
                    if outcome == "inserted":
                        stats["records_inserted"] += 1
                    elif outcome == "updated":
                        stats["records_updated"] += 1
                    else:
                        stats["records_unchanged"] += 1

                    # Update in-memory hash cache
                    existing_hashes[fh_org_id] = new_hash

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
            stg_cursor.close()
            stg_conn.close()
            cursor.close()
            conn.close()

        self.logger.info(
            "Federal Hierarchy load complete (load_id=%d): read=%d ins=%d upd=%d unch=%d err=%d",
            load_id,
            stats["records_read"],
            stats["records_inserted"],
            stats["records_updated"],
            stats["records_unchanged"],
            stats["records_errored"],
        )
        return stats

    def full_refresh(self, orgs_data, load_id):
        """Clear and reload all data in federal_organization atomically.

        Used for periodic full refreshes where the entire hierarchy should
        be replaced with fresh data from the API.

        NOTE: We use DELETE FROM instead of TRUNCATE TABLE because MySQL
        TRUNCATE acquires a metadata lock and implicitly commits — it cannot
        be rolled back. DELETE FROM is slower but fully transactional, so if
        load_organizations() fails mid-load the delete is rolled back and the
        table retains its previous data.

        Args:
            orgs_data: list or generator of raw org dicts from the Federal
                Hierarchy API.
            load_id: etl_load_log ID for this load.

        Returns:
            dict with load statistics.
        """
        self.logger.info("Full refresh: clearing federal_organization table")
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("DELETE FROM federal_organization")
            conn.commit()
            cursor.close()
            conn.close()
        except Exception:
            conn.rollback()
            cursor.close()
            conn.close()
            raise

        return self.load_organizations(orgs_data, load_id)

    # =================================================================
    # Normalisation
    # =================================================================

    def _normalize_org(self, raw):
        """Flatten the Federal Hierarchy API response to a flat dict matching
        federal_organization columns.

        Args:
            raw: Single org dict from Federal Hierarchy API orglist[].

        Returns:
            dict: Normalised org data matching federal_organization columns.
        """
        fh_org_type = raw.get("fhorgtype", "")

        # Extract CGAC from cgaclist array (first entry)
        cgac_list = raw.get("cgaclist") or []
        cgac = cgac_list[0].get("cgac") if cgac_list else None

        # Determine parent org ID from parent history (most recent entry)
        parent_org_id = self._extract_parent_org_id(raw)

        # Determine hierarchy level from org type
        level = _ORG_TYPE_LEVELS.get(fh_org_type)

        # Parse fhorgid as integer
        fh_org_id = raw.get("fhorgid")
        if fh_org_id is not None:
            try:
                fh_org_id = int(fh_org_id)
            except (ValueError, TypeError):
                pass

        if parent_org_id is not None:
            try:
                parent_org_id = int(parent_org_id)
            except (ValueError, TypeError):
                parent_org_id = None

        return {
            "fh_org_id":            fh_org_id,
            "fh_org_name":          raw.get("fhorgname"),
            "fh_org_type":          fh_org_type,
            "description":          None,
            "status":               raw.get("status"),
            "agency_code":          raw.get("agencycode"),
            "oldfpds_office_code":  raw.get("oldfpdsofficecode"),
            "cgac":                 cgac,
            "parent_org_id":        parent_org_id,
            "level":                level,
            "created_date":         parse_date(raw.get("createddate")),
            "last_modified_date":   parse_date(raw.get("lastupdateddate")),
        }

    def _extract_parent_org_id(self, raw):
        """Extract the parent org ID from the org's parent history.

        The API returns fhorgparenthistory as a list with the most recent
        parent path. The fhfullparentpathid contains dot-separated org IDs
        from root to immediate parent. We take the last segment.

        For Department/Ind. Agency orgs, parent_org_id is NULL (top-level).

        Args:
            raw: Single org dict from the API.

        Returns:
            str or None: Parent org ID, or None for top-level orgs.
        """
        # Department/Ind. Agency orgs have no parent
        if raw.get("fhorgtype") == "Department/Ind. Agency":
            return None

        # The fhdeptindagencyorgid field gives the department-level parent
        # for sub-tier orgs. For offices, we need the full path.
        parent_history = raw.get("fhorgparenthistory") or []
        if parent_history:
            # Take the most recent entry
            latest = parent_history[0]
            full_path_id = latest.get("fhfullparentpathid", "")
            if full_path_id:
                # Path is dot-separated: "100000000.100123456.100234567"
                # The last segment is the immediate parent
                parts = full_path_id.split(".")
                if parts:
                    return parts[-1]

        # Fallback: use fhdeptindagencyorgid for sub-tiers
        dept_id = raw.get("fhdeptindagencyorgid")
        if dept_id:
            return dept_id

        return None

    # =================================================================
    # Staging helpers
    # =================================================================

    def _extract_staging_key(self, raw: dict) -> dict:
        """Extract the natural key for stg_fedhier_raw from a raw API record."""
        return {"fh_org_id": int(raw.get("fhorgid", 0))}

    # =================================================================
    # Database operations
    # =================================================================

    def _upsert_org(self, cursor, org_data, load_id):
        """INSERT ... ON DUPLICATE KEY UPDATE for federal_organization.

        Args:
            cursor: Active DB cursor.
            org_data: Normalised org dict.
            load_id: Current load ID.

        Returns:
            'inserted', 'updated', or 'unchanged'.
        """
        placeholders = ", ".join(["%s"] * len(_UPSERT_COLS))
        col_list = ", ".join(_UPSERT_COLS)

        # ON DUPLICATE KEY UPDATE: update all columns except the PK
        pk_fields = {"fh_org_id"}
        update_pairs = ", ".join(
            f"{c} = VALUES({c})" for c in _UPSERT_COLS
            if c not in pk_fields
        )
        update_pairs += ", last_loaded_at = NOW()"

        sql = (
            f"INSERT INTO federal_organization ({col_list}, first_loaded_at, last_loaded_at) "
            f"VALUES ({placeholders}, NOW(), NOW()) "
            f"ON DUPLICATE KEY UPDATE {update_pairs}"
        )

        # Build values list matching _UPSERT_COLS order
        values = []
        for col in _UPSERT_COLS:
            if col == "last_load_id":
                values.append(load_id)
            else:
                values.append(org_data.get(col))

        cursor.execute(sql, values)

        # MySQL: rowcount 0 = unchanged, 1 = inserted, 2 = updated
        rc = cursor.rowcount
        if rc == 1:
            return "inserted"
        elif rc == 2:
            return "updated"
        return "unchanged"

    # =================================================================
    # Hash fields accessor
    # =================================================================

    @staticmethod
    def get_hash_fields():
        """Return the list of fields used for org record hashing."""
        return list(_ORG_HASH_FIELDS)
