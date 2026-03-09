# Scaffold ETL Loader -- Checklist

Quick reference for scaffolding a new ETL loader. See SKILL.md for detailed workflow.

## Files to Create

- [ ] `fed_prospector/etl/{entity_name}_loader.py`
- [ ] `fed_prospector/cli/{entity_name_plural}.py`
- [ ] `fed_prospector/tests/test_etl/test_{entity_name}_loader.py`
- [ ] DDL: staging table in `db/schema/tables/80_raw_staging.sql`
- [ ] DDL: target table in appropriate `db/schema/tables/` file
- [ ] DDL: history table (unless --no-history)

## Loader Class Requirements

- [ ] Inherits `StagingMixin`
- [ ] `_STG_TABLE = "stg_{entity_name}_raw"`
- [ ] `_STG_KEY_COLS = [...]` (natural key columns)
- [ ] `BATCH_SIZE = 500`
- [ ] `_extract_staging_key(raw)` implemented
- [ ] `_{ENTITY}_HASH_FIELDS` defined at module level
- [ ] `load_{entities}(data, load_id)` public entry point
- [ ] `_process_{entities}(iter, load_id)` with full loop
- [ ] `_normalize_{entity_name}(raw)` with parse_date/parse_decimal
- [ ] `_upsert_{entity_name}(cursor, data, load_id)` with ON DUPLICATE KEY UPDATE
- [ ] `_fetch_{entity_name}_row(cursor, key)` for diff comparison
- [ ] `_log_changes(cursor, key, diffs, load_id)` for history

## Critical Patterns

- [ ] Staging written BEFORE normalization (autocommit connection)
- [ ] Hash computed from normalized record, not raw
- [ ] Unchanged records skip upsert
- [ ] Per-record error handling (catch, log, rollback, continue)
- [ ] Batch commits every BATCH_SIZE
- [ ] Returns stats dict with all 5 keys
- [ ] Logger name: `fed_prospector.etl.{module_name}`

## CLI Command

- [ ] Click command with --key, --days-back, --force options
- [ ] Registered in main.py under `load` group
- [ ] Uses setup_logging()
- [ ] Creates LoadManager, calls start_load/complete_load/fail_load

## Tests

- [ ] Test construction (init sets attributes)
- [ ] Test normalize (field mapping, date/decimal parsing)
- [ ] Test upsert (insert=1, update=2, unchanged=0)
- [ ] Test staging key extraction
- [ ] Test hash fields list completeness

## Canonical References

- Loader: `fed_prospector/etl/opportunity_loader.py`
- CLI: `fed_prospector/cli/opportunities.py`
- Staging mixin: `fed_prospector/etl/staging_mixin.py`
- Change detector: `fed_prospector/etl/change_detector.py`
- Load manager: `fed_prospector/etl/load_manager.py`
- ETL utils: `fed_prospector/etl/etl_utils.py`

## Build & Test

```bash
cd fed_prospector
python -c "from etl.{entity_name}_loader import {EntityName}Loader; print('Import OK')"
python -m pytest tests/test_etl/test_{entity_name}_loader.py -v
```
