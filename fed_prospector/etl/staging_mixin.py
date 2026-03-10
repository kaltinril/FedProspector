"""
StagingMixin — raw JSON staging for ETL loaders.

Provides shared staging write methods for loaders that persist raw API
responses to stg_*_raw tables before normalization.

Usage:
    class MyLoader(StagingMixin):
        _STG_TABLE = "stg_fpds_award_raw"
        _STG_KEY_COLS = ["contract_id", "modification_number"]

        def _extract_staging_key(self, raw: dict) -> dict:
            return {
                "contract_id": raw.get("contractId", {}).get("piid", ""),
                "modification_number": raw.get("contractId", {}).get("modificationNumber", "0"),
            }

Entity loader is excluded from this mixin — stg_entity_raw has a different
schema (no auto-increment id, extra processed_at column). See entity_loader.py.
"""
import hashlib
import json
import logging

from db.connection import get_connection

logger = logging.getLogger(__name__)


class StagingMixin:
    """
    Mixin for ETL loaders that write raw JSON to a staging table before normalizing.

    Subclass must define:
        _STG_TABLE: str            — e.g. "stg_fpds_award_raw"
        _STG_KEY_COLS: list[str]   — e.g. ["contract_id", "modification_number"]
        _extract_staging_key(raw: dict) -> dict  — {col: val} for the key cols
    """

    def _open_stg_conn(self):
        """Open a dedicated autocommit connection for staging writes."""
        conn = get_connection()
        conn.autocommit = True
        return conn, conn.cursor()

    def _insert_staging(self, stg_cursor, load_id: int, key_vals: dict, raw: dict):
        """Write raw JSON to staging table. Returns lastrowid, or None on failure.

        Note: Staging tables have no unique constraint on the key columns, so
        concurrent loaders writing to the same staging table could produce
        duplicate raw rows. This is acceptable because: (1) this is a
        single-process CLI tool — concurrent loads for the same source are not
        expected, and (2) the main data tables use UPSERT (INSERT ON DUPLICATE
        KEY UPDATE), so duplicate staging rows do not cause data corruption.
        """
        try:
            raw_str = json.dumps(raw, sort_keys=True, default=str)
            raw_hash = hashlib.sha256(raw_str.encode()).hexdigest()
            col_names = ", ".join(["load_id"] + self._STG_KEY_COLS + ["raw_json", "raw_record_hash"])
            placeholders = ", ".join(["%s"] * (3 + len(self._STG_KEY_COLS)))
            vals = [load_id] + [key_vals[c] for c in self._STG_KEY_COLS] + [raw_str, raw_hash]
            stg_cursor.execute(
                f"INSERT INTO {self._STG_TABLE} ({col_names}) VALUES ({placeholders})", vals
            )
            return stg_cursor.lastrowid
        except Exception as exc:
            logger.warning("Staging insert failed for %s (load_id=%d): %s", self._STG_TABLE, load_id, exc)
            return None

    def _mark_staging(self, stg_cursor, staging_id, processed: str, error_msg=None):
        """Update staging row outcome. processed='Y' (success) or 'E' (error).

        No-op if staging_id is None (staging insert was skipped or failed).
        """
        if staging_id is None:
            return
        stg_cursor.execute(
            f"UPDATE {self._STG_TABLE} SET processed=%s, error_message=%s WHERE id=%s",
            (processed, error_msg[:2000] if error_msg else None, staging_id),
        )
