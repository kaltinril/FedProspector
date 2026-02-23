"""Change detection using SHA-256 record hashing.

Strategy:
1. When loading data, compute SHA-256 hash of key fields
2. Compare against stored hash in the target table's record_hash column
3. If hash differs: compute field-level diff, log to *_history table, update record
4. If hash matches: skip (record unchanged)
5. If no existing record: insert new
"""

import logging

from db.connection import get_connection
from utils.hashing import compute_record_hash


class ChangeDetector:
    def __init__(self):
        self.logger = logging.getLogger("fed_prospector.etl.change_detector")

    def compute_hash(self, record: dict, fields: list) -> str:
        """Compute SHA-256 hash for a record."""
        return compute_record_hash(record, fields)

    def get_existing_hashes(self, table_name, key_field, hash_field="record_hash"):
        """Fetch all existing key -> hash mappings from a table.

        Returns:
            dict of {key_value: hash_string}
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"SELECT {key_field}, {hash_field} FROM {table_name} "
                f"WHERE {hash_field} IS NOT NULL"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            cursor.close()
            conn.close()

    def classify_records(self, new_records, existing_hashes, key_field, hash_fields):
        """Classify new records as inserts, updates, or unchanged.

        Args:
            new_records: List of dicts
            existing_hashes: Dict from get_existing_hashes()
            key_field: Name of the primary key field in the records
            hash_fields: List of field names to include in hash

        Returns:
            dict with 'inserts', 'updates', 'unchanged' lists
        """
        result = {"inserts": [], "updates": [], "unchanged": []}

        for record in new_records:
            key = record[key_field]
            new_hash = self.compute_hash(record, hash_fields)
            record["_computed_hash"] = new_hash

            if key not in existing_hashes:
                result["inserts"].append(record)
            elif existing_hashes[key] != new_hash:
                result["updates"].append(record)
            else:
                result["unchanged"].append(record)

        self.logger.info(
            "Change detection: %d inserts, %d updates, %d unchanged",
            len(result["inserts"]), len(result["updates"]), len(result["unchanged"]),
        )
        return result

    def compute_field_diff(self, old_record, new_record, fields):
        """Return list of (field_name, old_value, new_value) for changed fields."""
        diffs = []
        for field in fields:
            old_val = str(old_record.get(field, "")) if old_record.get(field) is not None else None
            new_val = str(new_record.get(field, "")) if new_record.get(field) is not None else None
            if old_val != new_val:
                diffs.append((field, old_val, new_val))
        return diffs

    def log_changes(self, diffs, entity_key, load_id, history_table, key_column="uei_sam"):
        """Insert field-level changes into the appropriate history table."""
        if not diffs:
            return
        conn = get_connection()
        cursor = conn.cursor()
        try:
            sql = (
                f"INSERT INTO {history_table} "
                f"({key_column}, field_name, old_value, new_value, load_id) "
                f"VALUES (%s, %s, %s, %s, %s)"
            )
            rows = [(entity_key, field, old_val, new_val, load_id) for field, old_val, new_val in diffs]
            cursor.executemany(sql, rows)
            conn.commit()
            self.logger.debug(
                "Logged %d field changes for %s in %s",
                len(diffs), entity_key, history_table,
            )
        finally:
            cursor.close()
            conn.close()
