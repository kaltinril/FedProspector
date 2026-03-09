# ETL Loader Templates

Code templates with placeholders. Replace:
- `{EntityName}` -> PascalCase (e.g., `Contract`)
- `{entity_name}` -> snake_case (e.g., `contract`)
- `{entities}` -> plural snake_case (e.g., `contracts`)
- `{ENTITY}` -> UPPER_SNAKE (e.g., `CONTRACT`)
- `{SOURCE}` -> uppercase source system (e.g., `SAM`)
- `{key_col}` -> natural key column name (e.g., `contract_id`)
- `{key_field}` -> API field name for natural key (e.g., `contractId`)

**Canonical example**: `fed_prospector/etl/opportunity_loader.py`

## 1. Loader Class Template

```python
"""{EntityName} loader: transforms {SOURCE} {entity_name} data into MySQL.

Loads {entity_name} records from the {SOURCE} API, with
change detection via SHA-256 hashing and field-level history tracking.
"""

import json
import logging
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation

from db.connection import get_connection
from etl.change_detector import ChangeDetector
from etl.etl_utils import parse_date, parse_decimal
from etl.load_manager import LoadManager
from etl.staging_mixin import StagingMixin

# ---------------------------------------------------------------------------
# Fields used for {entity_name} record hash (all meaningful business fields,
# excludes timestamps, descriptions, and load-tracking)
# ---------------------------------------------------------------------------
_{ENTITY}_HASH_FIELDS = [
    "{key_col}",
    # TODO: Add all business-meaningful fields here
]


def _str_or_none(val):
    """Convert a value to str for history logging, preserving None."""
    if val is None:
        return None
    return str(val)


class {EntityName}Loader(StagingMixin):
    """Transform and load {SOURCE} {entity_name} data into MySQL."""

    BATCH_SIZE = 500

    _STG_TABLE = "stg_{entity_name}_raw"
    _STG_KEY_COLS = ["{key_col}"]

    # -----------------------------------------------------------------
    # Construction
    # -----------------------------------------------------------------
    def __init__(self, db_connection=None, change_detector=None, load_manager=None):
        """Initialize with optional DB connection, change detector, load manager.

        Args:
            db_connection: Not used (connections obtained from pool). Kept for
                           interface compatibility.
            change_detector: Optional ChangeDetector instance.
            load_manager: Optional LoadManager instance.
        """
        self.logger = logging.getLogger("fed_prospector.etl.{entity_name}_loader")
        self.change_detector = change_detector or ChangeDetector()
        self.load_manager = load_manager or LoadManager()

    # =================================================================
    # Public entry point
    # =================================================================

    def load_{entities}(self, data, load_id):
        """Main entry point. Process list of raw API {entity_name} dicts.

        Args:
            data: list of raw {entity_name} dicts from API
            load_id: etl_load_log ID for this load

        Returns:
            dict with keys: records_read, records_inserted, records_updated,
                            records_unchanged, records_errored
        """
        data = list(data)
        self.logger.info(
            "Starting {entity_name} load (%d records, load_id=%d)",
            len(data), load_id,
        )
        return self._process_{entities}(iter(data), load_id)

    # =================================================================
    # Core processing pipeline
    # =================================================================

    def _process_{entities}(self, records_iter, load_id):
        """Iterate over raw records, normalise, detect changes, upsert.

        Processes in batches of BATCH_SIZE and commits after each batch.
        Returns a stats dict compatible with LoadManager.complete_load().
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
            "{entity_name}", "{key_col}", "record_hash"
        )

        conn = get_connection()
        cursor = conn.cursor(dictionary=True)

        # Staging connection: autocommit=True so each raw row is persisted
        # immediately, independent of the production batch commit/rollback cycle.
        stg_conn, stg_cursor = self._open_stg_conn()

        try:
            batch_count = 0
            for raw in records_iter:
                stats["records_read"] += 1
                record_key = None
                staging_id = None
                try:
                    # --- 1. write raw record to staging BEFORE normalization ---
                    key_vals = self._extract_staging_key(raw)
                    staging_id = self._insert_staging(stg_cursor, load_id, key_vals, raw)

                    # --- 2. normalise ---
                    normalized = self._normalize_{entity_name}(raw)
                    record_key = normalized.get("{key_col}")
                    if not record_key:
                        raise ValueError("Missing {key_col} in {entity_name} record")

                    # --- 3. change detection ---
                    new_hash = self.change_detector.compute_hash(
                        normalized, _{ENTITY}_HASH_FIELDS
                    )
                    normalized["record_hash"] = new_hash

                    # --- 4. check against existing hashes ---
                    old_hash = existing_hashes.get(record_key)
                    if old_hash and old_hash == new_hash:
                        stats["records_unchanged"] += 1
                        self._mark_staging(stg_cursor, staging_id, 'Y')
                        batch_count += 1
                        if batch_count >= self.BATCH_SIZE:
                            conn.commit()
                            batch_count = 0
                        continue

                    # --- 5. fetch old record for history (updates only) ---
                    if old_hash is not None:
                        old_record = self._fetch_{entity_name}_row(cursor, record_key)
                    else:
                        old_record = None

                    # --- 6. upsert ---
                    outcome = self._upsert_{entity_name}(cursor, normalized, load_id)
                    if outcome == "inserted":
                        stats["records_inserted"] += 1
                    elif outcome == "updated":
                        stats["records_updated"] += 1
                    else:
                        stats["records_unchanged"] += 1

                    # --- 7. history logging (updates only) ---
                    if old_record is not None and outcome == "updated":
                        diffs = self.change_detector.compute_field_diff(
                            old_record, normalized, _{ENTITY}_HASH_FIELDS
                        )
                        if diffs:
                            self._log_changes(cursor, record_key, diffs, load_id)

                    # --- 8. update hash cache, mark staging processed ---
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
                    # Rollback the failed record, then keep going
                    conn.rollback()
                    batch_count = 0
                    continue

                # --- 9. batch commit ---
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
            "{EntityName} batch complete (load_id=%d): read=%d ins=%d upd=%d unch=%d err=%d",
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

    def _normalize_{entity_name}(self, raw):
        """Flatten nested API response into flat dict matching DB columns.

        TODO: Map API fields to DB columns. Use parse_date() and
        parse_decimal() from etl_utils for type conversion.
        """
        return {
            "{key_col}": raw.get("{key_field}"),
            # TODO: Map remaining fields
        }

    # =================================================================
    # Database operations
    # =================================================================

    def _upsert_{entity_name}(self, cursor, data, load_id):
        """INSERT ... ON DUPLICATE KEY UPDATE for the {entity_name} table.

        Returns: 'inserted', 'updated', or 'unchanged'
        """
        cols = [
            "{key_col}",
            # TODO: Add all DB columns
            "record_hash", "last_load_id",
        ]

        placeholders = ", ".join(["%s"] * len(cols))
        col_list = ", ".join(cols)

        # ON DUPLICATE KEY UPDATE: update all mutable columns
        update_pairs = ", ".join(
            f"{c} = VALUES({c})" for c in cols if c != "{key_col}"
        )
        update_pairs += ", last_loaded_at = NOW()"

        sql = (
            f"INSERT INTO {entity_name} ({col_list}, first_loaded_at, last_loaded_at) "
            f"VALUES ({placeholders}, NOW(), NOW()) "
            f"ON DUPLICATE KEY UPDATE {update_pairs}"
        )

        values = [data.get(c) for c in cols[:-1]]  # all except last_load_id
        values.append(load_id)  # last_load_id

        cursor.execute(sql, values)

        # MySQL rowcount: 0 = unchanged, 1 = inserted, 2 = updated
        rc = cursor.rowcount
        if rc == 1:
            return "inserted"
        elif rc == 2:
            return "updated"
        return "unchanged"

    # =================================================================
    # History / fetch helpers
    # =================================================================

    def _fetch_{entity_name}_row(self, cursor, key_value):
        """Fetch the current {entity_name} row as a dict for diff comparison."""
        cursor.execute("SELECT * FROM {entity_name} WHERE {key_col} = %s", (key_value,))
        row = cursor.fetchone()
        if row is None:
            return None
        # cursor is dictionary=True, so row is already a dict.
        # Convert date/datetime/Decimal values to strings for comparison.
        clean = {}
        for k, v in row.items():
            if isinstance(v, datetime):
                clean[k] = v.strftime("%Y-%m-%d %H:%M:%S")
            elif isinstance(v, date):
                clean[k] = v.isoformat()
            elif isinstance(v, Decimal):
                clean[k] = str(v)
            else:
                clean[k] = v
        return clean

    def _log_changes(self, cursor, key_value, diffs, load_id):
        """Write field-level change records to {entity_name}_history."""
        sql = (
            "INSERT INTO {entity_name}_history ({key_col}, field_name, old_value, new_value, load_id) "
            "VALUES (%s, %s, %s, %s, %s)"
        )
        rows = [
            (key_value, field, _str_or_none(old_val), _str_or_none(new_val), load_id)
            for field, old_val, new_val in diffs
        ]
        cursor.executemany(sql, rows)

    # =================================================================
    # Raw staging helpers
    # =================================================================

    def _extract_staging_key(self, raw: dict) -> dict:
        """Extract natural key fields from a raw API record."""
        return {"{key_col}": raw.get("{key_field}", "")}

    # =================================================================
    # Hash fields accessor
    # =================================================================

    @staticmethod
    def get_hash_fields():
        """Return the list of fields used for {entity_name} record hashing."""
        return list(_{ENTITY}_HASH_FIELDS)
```

## 2. CLI Command Template

```python
"""{EntityName} loading CLI commands.

Commands: load-{entities}
"""

import sys

import click

from config.logging_config import setup_logging
from config import settings


@click.command("load-{entities}")
@click.option("--days-back", default=7, type=int,
              help="Load {entities} from the last N days (default: 7)")
@click.option("--key", "api_key_number", default=1, type=click.IntRange(1, 2),
              help="Which API key to use (1 or 2, default: 1)")
@click.option("--force", is_flag=True, default=False,
              help="Ignore previous progress and start a fresh load")
def load_{entities}(days_back, api_key_number, force):
    """Load {entities} from the {SOURCE} API.

    Fetches {entity_name} records and loads them into the local database
    with change detection and history tracking.

    Examples:
        python main.py load {entities}
        python main.py load {entities} --days-back=30
        python main.py load {entities} --force
    """
    logger = setup_logging()

    from etl.{entity_name}_loader import {EntityName}Loader
    from etl.load_manager import LoadManager

    lm = LoadManager()
    loader = {EntityName}Loader(load_manager=lm)

    load_id = lm.start_load("{SOURCE}_{ENTITY}", "API")
    try:
        # TODO: Create API client, fetch data, pass to loader
        # data = client.fetch_{entities}(days_back=days_back)
        # stats = loader.load_{entities}(data, load_id)
        # lm.complete_load(load_id, **stats)

        click.echo("TODO: Implement data fetching")
        lm.fail_load(load_id, "Not yet implemented")
        sys.exit(1)

    except Exception as exc:
        logger.error("Load failed: %s", exc, exc_info=True)
        lm.fail_load(load_id, str(exc))
        sys.exit(1)
```

### CLI Registration in main.py

Add to the `load` group in `fed_prospector/main.py`:

```python
from cli.{entity_name_plural} import load_{entities}
load_group.add_command(load_{entities})
```

## 3. Staging Table DDL Template

Append to `fed_prospector/db/schema/tables/80_raw_staging.sql`:

```sql
-- stg_{entity_name}_raw
CREATE TABLE IF NOT EXISTS stg_{entity_name}_raw (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    load_id INT NOT NULL,
    {key_col} VARCHAR(255) NOT NULL,
    raw_json LONGTEXT NOT NULL,
    raw_record_hash CHAR(64),
    processed CHAR(1) DEFAULT NULL,
    error_message VARCHAR(500),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (load_id) REFERENCES etl_load_log(load_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

For composite keys, add additional key columns before `raw_json`.

## 4. Target Table DDL Template (stub)

Create in appropriate `fed_prospector/db/schema/tables/` file:

```sql
-- {entity_name}
CREATE TABLE IF NOT EXISTS {entity_name} (
    {key_col} VARCHAR(255) PRIMARY KEY,
    -- TODO: Add business columns

    -- Standard tracking columns
    record_hash CHAR(64),
    first_loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_loaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    last_load_id INT,
    FOREIGN KEY (last_load_id) REFERENCES etl_load_log(load_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 5. History Table DDL Template

Create alongside the target table:

```sql
-- {entity_name}_history
CREATE TABLE IF NOT EXISTS {entity_name}_history (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    {key_col} VARCHAR(255) NOT NULL,
    field_name VARCHAR(100) NOT NULL,
    old_value TEXT,
    new_value TEXT,
    load_id INT NOT NULL,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY ({key_col}) REFERENCES {entity_name}({key_col}),
    FOREIGN KEY (load_id) REFERENCES etl_load_log(load_id),
    INDEX idx_{entity_name}_hist_key ({key_col}),
    INDEX idx_{entity_name}_hist_load (load_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## 6. Test File Template

```python
"""Tests for {EntityName}Loader."""

import pytest
from unittest.mock import MagicMock, patch

from etl.{entity_name}_loader import {EntityName}Loader, _{ENTITY}_HASH_FIELDS


class TestConstruction:
    """Test {EntityName}Loader initialization."""

    def test_init_defaults(self):
        loader = {EntityName}Loader()
        assert loader.logger is not None
        assert loader.change_detector is not None
        assert loader.load_manager is not None

    def test_init_custom_dependencies(self):
        cd = MagicMock()
        lm = MagicMock()
        loader = {EntityName}Loader(change_detector=cd, load_manager=lm)
        assert loader.change_detector is cd
        assert loader.load_manager is lm

    def test_staging_config(self):
        loader = {EntityName}Loader()
        assert loader._STG_TABLE == "stg_{entity_name}_raw"
        assert isinstance(loader._STG_KEY_COLS, list)
        assert len(loader._STG_KEY_COLS) >= 1
        assert loader.BATCH_SIZE == 500


class TestNormalize:
    """Test _normalize_{entity_name} field mapping."""

    def setup_method(self):
        self.loader = {EntityName}Loader()

    def test_maps_key_field(self):
        raw = {"{key_field}": "TEST-001"}
        result = self.loader._normalize_{entity_name}(raw)
        assert result["{key_col}"] == "TEST-001"

    def test_handles_missing_fields(self):
        raw = {}
        result = self.loader._normalize_{entity_name}(raw)
        assert result["{key_col}"] is None

    # TODO: Add tests for date parsing, decimal parsing, nested field flattening


class TestStagingKey:
    """Test _extract_staging_key."""

    def setup_method(self):
        self.loader = {EntityName}Loader()

    def test_extracts_key(self):
        raw = {"{key_field}": "TEST-001"}
        result = self.loader._extract_staging_key(raw)
        assert "{key_col}" in result
        assert result["{key_col}"] == "TEST-001"

    def test_missing_key_returns_empty_string(self):
        raw = {}
        result = self.loader._extract_staging_key(raw)
        assert result["{key_col}"] == ""


class TestHashFields:
    """Test hash fields list completeness."""

    def test_hash_fields_not_empty(self):
        assert len(_{ENTITY}_HASH_FIELDS) > 0

    def test_hash_fields_includes_key(self):
        assert "{key_col}" in _{ENTITY}_HASH_FIELDS

    def test_hash_fields_excludes_timestamps(self):
        for field in _{ENTITY}_HASH_FIELDS:
            assert field not in (
                "created_at", "updated_at", "last_loaded_at",
                "first_loaded_at", "last_load_id", "record_hash",
            ), f"Hash fields should not include tracking field: {field}"

    def test_get_hash_fields_returns_copy(self):
        fields = {EntityName}Loader.get_hash_fields()
        assert fields == _{ENTITY}_HASH_FIELDS
        assert fields is not _{ENTITY}_HASH_FIELDS  # must be a copy


class TestUpsert:
    """Test _upsert_{entity_name} outcome detection."""

    def setup_method(self):
        self.loader = {EntityName}Loader()

    def test_insert_returns_inserted(self):
        cursor = MagicMock()
        cursor.rowcount = 1
        result = self.loader._upsert_{entity_name}(
            cursor, {{"{key_col}": "TEST-001", "record_hash": "abc123"}}, load_id=1
        )
        assert result == "inserted"

    def test_update_returns_updated(self):
        cursor = MagicMock()
        cursor.rowcount = 2
        result = self.loader._upsert_{entity_name}(
            cursor, {{"{key_col}": "TEST-001", "record_hash": "abc123"}}, load_id=1
        )
        assert result == "updated"

    def test_unchanged_returns_unchanged(self):
        cursor = MagicMock()
        cursor.rowcount = 0
        result = self.loader._upsert_{entity_name}(
            cursor, {{"{key_col}": "TEST-001", "record_hash": "abc123"}}, load_id=1
        )
        assert result == "unchanged"
```

## Canonical Reference

`fed_prospector/etl/opportunity_loader.py` — the reference implementation showing all patterns in production use. Read it to understand real-world field mapping, nested object flattening, and POC handling.
