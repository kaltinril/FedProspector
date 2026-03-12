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

    # =================================================================
    # Batch staging methods (P92-1)
    # =================================================================

    def _insert_staging_batch(self, stg_cursor, load_id: int,
                              rows: list[tuple[dict, dict]]) -> list[int]:
        """Batch-insert raw JSON rows into the staging table using executemany.

        Args:
            stg_cursor: Staging DB cursor.
            load_id: Current load ID.
            rows: List of (key_vals, raw) tuples. key_vals is a dict mapping
                _STG_KEY_COLS to values; raw is the raw API response dict.

        Returns:
            List of staging IDs (auto-increment). If executemany is used,
            MySQL returns lastrowid of the first inserted row; we compute
            sequential IDs from there.
        """
        if not rows:
            return []

        col_names = ", ".join(
            ["load_id"] + self._STG_KEY_COLS + ["raw_json", "raw_record_hash"]
        )
        placeholders = ", ".join(["%s"] * (3 + len(self._STG_KEY_COLS)))
        sql = f"INSERT INTO {self._STG_TABLE} ({col_names}) VALUES ({placeholders})"

        batch_values = []
        for key_vals, raw in rows:
            raw_str = json.dumps(raw, sort_keys=True, default=str)
            raw_hash = hashlib.sha256(raw_str.encode()).hexdigest()
            vals = (
                [load_id]
                + [key_vals[c] for c in self._STG_KEY_COLS]
                + [raw_str, raw_hash]
            )
            batch_values.append(vals)

        try:
            # Disable autocommit for the batch, then commit explicitly
            old_autocommit = stg_cursor._connection.autocommit
            stg_cursor._connection.autocommit = False
            try:
                stg_cursor.executemany(sql, batch_values)
                first_id = stg_cursor.lastrowid
                stg_cursor._connection.commit()
            finally:
                stg_cursor._connection.autocommit = old_autocommit

            # executemany with auto-increment: lastrowid is the first inserted ID
            # IDs are sequential within a single executemany call
            return list(range(first_id, first_id + len(rows)))
        except Exception as exc:
            logger.warning(
                "Batch staging insert failed for %s (load_id=%d, %d rows): %s",
                self._STG_TABLE, load_id, len(rows), exc,
            )
            try:
                stg_cursor._connection.rollback()
            except Exception:
                pass
            # Fall back to row-by-row
            ids = []
            for key_vals, raw in rows:
                sid = self._insert_staging(stg_cursor, load_id, key_vals, raw)
                ids.append(sid)
            return ids

    def _mark_staging_batch(self, stg_cursor, staging_ids: list[int],
                            processed: str):
        """Batch-update staging rows using WHERE id IN (...).

        Args:
            stg_cursor: Staging DB cursor.
            staging_ids: List of staging table IDs to mark.
            processed: 'Y' (success) or 'E' (error).
        """
        # Filter out None IDs (from failed staging inserts)
        valid_ids = [sid for sid in staging_ids if sid is not None]
        if not valid_ids:
            return

        # Chunk into groups of 1000 to avoid exceeding max_allowed_packet
        chunk_size = 1000
        for i in range(0, len(valid_ids), chunk_size):
            chunk = valid_ids[i : i + chunk_size]
            placeholders = ", ".join(["%s"] * len(chunk))
            stg_cursor.execute(
                f"UPDATE {self._STG_TABLE} SET processed=%s "
                f"WHERE id IN ({placeholders})",
                [processed] + chunk,
            )
