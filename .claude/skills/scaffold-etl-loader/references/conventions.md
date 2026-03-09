# ETL Loader Conventions

Critical patterns that agents MUST follow when scaffolding a new loader.

## Staging Mixin Contract

- Class must inherit `StagingMixin` (from `etl.staging_mixin`)
- Must define `_STG_TABLE` (pattern: `stg_{entity_name}_raw`)
- Must define `_STG_KEY_COLS` as a list of natural key column names
- Must implement `_extract_staging_key(self, raw: dict) -> dict` returning `{col_name: value}` for each col in `_STG_KEY_COLS`
- StagingMixin provides:
  - `_open_stg_conn()` — returns `(conn, cursor)` with `autocommit=True`
  - `_insert_staging(stg_cursor, load_id, key_vals, raw)` — writes raw JSON, returns `lastrowid`
  - `_mark_staging(stg_cursor, staging_id, processed, error_msg)` — processed='Y' or 'E'
- **CRITICAL**: Staging uses its own autocommit=True connection, independent of main transaction. This is by design — staging persists even if the main transaction rolls back.

## Change Detection

- Define `_{ENTITY}_HASH_FIELDS` at module level as a list of business-meaningful field names
- **Exclude**: timestamps (created_at, updated_at, last_loaded_at), descriptions/URLs, load-tracking columns (last_load_id)
- **Include**: ALL fields that would indicate a meaningful change to the record
- Missing a field = false "unchanged" detection (record skipped when it should update)
- Use `change_detector.compute_hash(normalized, _HASH_FIELDS)` -> SHA-256 hex string
- Use `change_detector.get_existing_hashes(table, key_col, "record_hash")` -> dict of `{key: hash}`
- Use `change_detector.compute_field_diff(old_record, new_record, _HASH_FIELDS)` -> list of `(field, old, new)`

## Load Manager Lifecycle

- `start_load(source_system, load_type, source_file=None, parameters=None)` -> load_id
- `complete_load(load_id, records_read=0, records_inserted=0, records_updated=0, records_unchanged=0, records_errored=0)`
- `fail_load(load_id, error_message)` — on unrecoverable error
- `save_load_progress(load_id, parameters, **stats)` — for resumable loads (after each page)
- `log_record_error(load_id, record_identifier, error_type, error_message, raw_data=None)` — per-record errors
- `get_last_load(source_system, status="SUCCESS")` -> dict — for resume detection

## Processing Loop Order

1. Write raw JSON to staging (autocommit) BEFORE any normalization
2. Normalize API response to flat dict matching DB columns
3. Compute hash from normalized record using _HASH_FIELDS
4. Check against existing hashes — skip upsert if unchanged
5. Fetch old record (for updates only) — needed for field-level diff
6. Upsert via INSERT ... ON DUPLICATE KEY UPDATE
7. Log field-level changes to history table (updates only)
8. Update hash cache, mark staging processed
9. Batch commit every BATCH_SIZE records
10. Per-record error handling: rollback failed record, log error, continue

## Standard Imports

```python
import json
import logging
from datetime import datetime, date, timezone
from decimal import Decimal, InvalidOperation

from db.connection import get_connection
from etl.change_detector import ChangeDetector
from etl.etl_utils import parse_date, parse_decimal
from etl.load_manager import LoadManager
from etl.staging_mixin import StagingMixin
```

## Naming Conventions

| Item | Pattern | Example |
|------|---------|---------|
| Loader class | `{EntityName}Loader` | `ContractLoader` |
| Module | `{entity_name}_loader.py` | `contract_loader.py` |
| Public method | `load_{entities}(data, load_id)` | `load_contracts(data, load_id)` |
| Process method | `_process_{entities}(iter, load_id)` | `_process_contracts(iter, load_id)` |
| Normalize | `_normalize_{entity}(raw)` | `_normalize_contract(raw)` |
| Upsert | `_upsert_{entity}(cursor, data, load_id)` | `_upsert_contract(cursor, data, load_id)` |
| Fetch row | `_fetch_{entity}_row(cursor, key)` | `_fetch_contract_row(cursor, key)` |
| Hash fields | `_{ENTITY}_HASH_FIELDS` | `_CONTRACT_HASH_FIELDS` |
| Staging table | `stg_{entity_name}_raw` | `stg_contract_raw` |
| History table | `{entity_name}_history` | `contract_history` |
| Source system | `{SOURCE}_{ENTITY}` | `SAM_CONTRACT` |
| Logger | `fed_prospector.etl.{module}` | `fed_prospector.etl.contract_loader` |

## Stats Dict

Every loader must return a dict with exactly these keys:

```python
stats = {
    "records_read": 0,
    "records_inserted": 0,
    "records_updated": 0,
    "records_unchanged": 0,
    "records_errored": 0,
}
```

These map directly to `LoadManager.complete_load()` keyword arguments.

## Error Handling

- Per-record try/except around the entire processing block (staging through upsert)
- On error: increment `records_errored`, call `load_manager.log_record_error()`, mark staging as 'E', `conn.rollback()`, reset `batch_count = 0`, `continue`
- Identifier for error logging: use natural key if available, else `record#{records_read}`
- Raw data logged as `json.dumps(raw)` for debugging

## Upsert Pattern

MySQL `INSERT ... ON DUPLICATE KEY UPDATE` returns rowcount:
- `1` = new row inserted
- `2` = existing row updated (at least one column changed)
- `0` = no change (all VALUES same as existing)

Map to outcomes: `"inserted"`, `"updated"`, `"unchanged"`.

## Canonical Example

`fed_prospector/etl/opportunity_loader.py` is the reference implementation for all patterns above.
