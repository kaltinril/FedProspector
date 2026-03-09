---
name: scaffold-etl-loader
description: "Scaffold a new Python ETL loader following FedProspect patterns: loader class with StagingMixin, change detection, CLI command, DDL stubs, and tests. Use this skill whenever the user wants to add a new data source, create a new loader, or integrate a new API into the ETL pipeline. Usage: /scaffold-etl-loader <EntityName> <SourceSystem>"
argument-hint: "<EntityName> <SourceSystem> [--no-api-client] [--no-history]"
disable-model-invocation: true
---

# Scaffold ETL Loader

## Arguments

Parse `$ARGUMENTS`:

| Argument | Example | Purpose |
|----------|---------|---------|
| EntityName | `Contract` | PascalCase entity name -> class prefix |
| SourceSystem | `SAM` | Uppercase source system for load_manager |
| --no-api-client | flag | Skip API client scaffolding |
| --no-history | flag | Skip history table and change logging |

Derive names:
- Module: `{entity_name}_loader.py` (snake_case)
- Class: `{EntityName}Loader`
- Staging table: `stg_{entity_name}_raw`
- Target table: `{entity_name}`
- History table: `{entity_name}_history` (unless --no-history)
- CLI module: `cli/{entity_name_plural}.py`
- Source system: `{SOURCE}_{ENTITY}` (e.g., `SAM_CONTRACT`)

## Workflow

### Step 1: Read reference files
Read `references/conventions.md` for critical patterns (staging mixin, change detection, load manager lifecycle). Read `references/templates.md` for code templates.

### Step 2: Create loader class
Create `fed_prospector/etl/{entity_name}_loader.py` using the loader template. The class MUST:
- Inherit from `StagingMixin`
- Define `_STG_TABLE`, `_STG_KEY_COLS`, `BATCH_SIZE`
- Implement `_extract_staging_key(raw)` returning dict matching `_STG_KEY_COLS`
- Define `_HASH_FIELDS` at module level (list of business-meaningful fields)
- Follow the standard processing loop: staging -> normalize -> hash -> upsert -> history

### Step 3: Create DDL stubs
Add to `fed_prospector/db/schema/`:
- Staging table DDL in `tables/80_raw_staging.sql` (append)
- Target table DDL in appropriate numbered file (ask user which)
- History table DDL alongside target (unless --no-history)

### Step 4: Create CLI command
Create `fed_prospector/cli/{entity_name_plural}.py` with Click command. Register in `fed_prospector/main.py` under the `load` group.

### Step 5: Create tests
Create `fed_prospector/tests/test_etl/test_{entity_name}_loader.py` with:
- Test construction (init sets attributes)
- Test normalize method (field mapping)
- Test upsert method (insert vs update detection)
- Test staging key extraction
- Test hash fields completeness

### Step 6: Build and verify
```bash
cd fed_prospector && python -c "from etl.{entity_name}_loader import {EntityName}Loader; print('Import OK')"
python -m pytest tests/test_etl/test_{entity_name}_loader.py -v
```

## Conventions Summary

| Item | Pattern |
|------|---------|
| Logger name | `fed_prospector.etl.{module_name}` |
| Stats dict keys | records_read, records_inserted, records_updated, records_unchanged, records_errored |
| Batch commit | Every `BATCH_SIZE` (default 500) records |
| Staging autocommit | `_open_stg_conn()` returns autocommit=True connection |
| Change detection | `compute_hash(normalized, _HASH_FIELDS)` before upsert |
| Upsert return | MySQL rowcount: 1=insert, 2=update, 0=unchanged |
| Error handling | Per-record try/except, log to `etl_load_error`, continue |

## Quick Reference
See `references/checklist.md` for a condensed scaffolding checklist.
