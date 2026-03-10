# Phase 82: ETL Pipeline Reliability

**Status**: PLANNED
**Priority**: HIGH
**Depends on**: None

## Overview

Review identified connection management issues, race conditions in change detection, staging/transaction consistency gaps, and data loss risks in the ETL pipeline. These affect all 7 loaders and the core ETL infrastructure.

## Issues

### CRITICAL

#### 82-1: Load Manager Connection Leaks
- **File**: `fed_prospector/etl/load_manager.py` lines 26, 48, 54, 89, 116, 133, 154
- **Issue**: Every method opens a connection via `get_connection()`. The connection is used and committed but relies solely on finally blocks. After 100+ loader invocations, connection pool (size=5) can be exhausted, causing loads to hang.
- **Fix**: Use context manager pattern (`with get_connection() as conn:`) consistently. Ensure all methods release connections in finally blocks.

#### 82-2: Staging Race Condition — No Unique Constraint
- **File**: `fed_prospector/etl/staging_mixin.py` lines 46-60
- **Issue**: `_insert_staging()` computes raw_hash but no unique constraint on `(load_id, key_cols, raw_record_hash)`. Two concurrent loaders can insert duplicate raw records.
- **Fix**: Add unique index on staging tables: `UNIQUE INDEX idx_stg_dedup (load_id, <key_col>, raw_record_hash)`. Handle duplicate key errors gracefully.

#### 82-3: Stale Hash Cache on Long-Running Loads
- **File**: `fed_prospector/etl/change_detector.py` lines 25-41
- **Issue**: `get_existing_hashes()` fetches ALL hashes at load start. If load runs 1+ hours, concurrent loads insert new records not in the hash dict. Those records are treated as inserts instead of updates, creating duplicates.
- **Fix**: Options: (a) Refresh hash cache periodically during long loads, (b) Use database-level UPSERT (INSERT ON DUPLICATE KEY UPDATE) instead of check-then-insert, (c) Add advisory locks for same-source concurrent loads.

---

### HIGH

#### 82-4: Staging vs Main Transaction Inconsistency
- **File**: All loaders (e.g., `opportunity_loader.py` lines 131-243)
- **Issue**: Staging uses autocommit=True (separate connection), main data is transactional. If main INSERT fails after staging marks record as processed ('Y'), the record is skipped on retry — data silently lost.
- **Fix**: Either (a) mark staging processed AFTER main commit, or (b) use same transaction for staging and main data, or (c) add "reprocess" capability in load_manager to re-scan staging rows marked processed but not in main table.

#### 82-5: Bulk Loader Temp File Leak on FK Failure
- **File**: `fed_prospector/etl/bulk_loader.py` lines 228-238
- **Issue**: If `_load_into_mysql()` raises after temp files are written, the rollback at line 421 doesn't trigger the finally block at line 228 (which is outside the LOAD DATA try-except). Temp files leak.
- **Fix**: Move temp file cleanup into the same try-finally that wraps the LOAD DATA operation. Use `tempfile.TemporaryDirectory()` context manager.

#### 82-6: Hash Collision on Composite Keys (Pipe Separator)
- **Files**: `exclusions_loader.py` lines 51-60, `subaward_loader.py` lines 49-57, `awards_loader.py` lines 53-60
- **Issue**: Composite keys built with `|` separator: `f"{identifier}|{date}|{type}"`. If any field contains `|`, keys collide. Example: UEI="ABC|DEF" + date="2026-01-01" collides with UEI="ABCDE" + different fields.
- **Fix**: Use a separator that cannot appear in the data (e.g., `\x1F` unit separator) or hash each component separately then combine.

---

### MEDIUM

#### 82-7: Subaward Hash Key Mismatch
- **File**: `fed_prospector/etl/subaward_loader.py` lines 49-57, 127, 154-157
- **Issue**: `_make_subaward_key()` uses `prime_piid|sub_uei|sub_date` but lookup at line 127 uses `CONCAT(prime_piid,'|',sub_uei)` WITHOUT sub_date. Records with same contractor/prime but different dates are treated as unchanged.
- **Fix**: Align the SQL CONCAT with the Python key function — include sub_date in both.

#### 82-8: USASpending Soft Delete Re-Upsert Gap
- **File**: `fed_prospector/etl/usaspending_bulk_loader.py` lines 1180-1181, 1275
- **Issue**: Soft-delete sets `deleted_at = NOW()` WHERE `deleted_at IS NULL`. Re-upsert sets `deleted_at = NULL`. If PIID is deleted -> re-added -> deleted again, second soft-delete misses it (WHERE checks IS NULL but it's already NULL from re-add).
- **Fix**: Track delete generation or use a different deletion detection strategy (compare against full source dataset).

#### 82-9: USASpending Parent Fields Hardcoded to None
- **File**: `fed_prospector/etl/usaspending_loader.py` lines 253-254
- **Issue**: `recipient_parent_name` and `recipient_parent_uei` hardcoded to None in search results normalization. These fields are in the hash but never populated from search endpoint.
- **Fix**: Either (a) add parent fields to AWARD_SEARCH_FIELDS request, or (b) remove from hash fields to prevent false change detection, or (c) call detail endpoint for parent data.

#### 82-10: USASpending Bulk Loader Missing CSV Column Mappings
- **File**: `fed_prospector/etl/usaspending_bulk_loader.py` lines 23-51
- **Issue**: CSV_COLUMN_MAP missing: `recipient_parent_name`, `recipient_parent_uei`, `type_of_set_aside_description`, `solicitation_identifier`, `last_modified_date`. These columns exist in schema but are NULL on bulk loads.
- **Fix**: Add missing columns to CSV_COLUMN_MAP. Verify CSV headers match.

#### 82-11: CalcLoader Silent Failure on LOAD DATA INFILE
- **File**: `fed_prospector/etl/calc_loader.py` lines 164-174
- **Issue**: If CSV path invalid, both LOAD DATA and batch INSERT fallback fail silently (caught in except, logs warning). Load_id never marked FAILED — etl_load_log shows SUCCESS with 0 records.
- **Fix**: Re-raise exception after logging. Ensure load_manager.fail_load() is called.

#### 82-12: Entity Loader Pattern Deviation
- **File**: `fed_prospector/etl/entity_loader.py`
- **Issue**: Does NOT use StagingMixin (all other loaders do). Implements own staging write with separate connection. Uses streaming JSON parser. Different error handling patterns.
- **Fix**: Document why entity_loader diverges (likely performance reasons for large datasets). Consider refactoring to use StagingMixin if feasible.

---

### LOW

#### 82-13: Bulk Loader eft_indicator Not in Hash Fields
- **File**: `fed_prospector/etl/bulk_loader.py` lines 21-37
- **Issue**: `_ENTITY_HASH_FIELDS` excludes `eft_indicator` but `_ENTITY_COLUMNS` includes it. If only eft_indicator changes, hash stays same, update skipped.
- **Fix**: Add `eft_indicator` to hash fields.

#### 82-14: Staging Error Message Truncation
- **File**: `fed_prospector/etl/staging_mixin.py` line 71
- **Issue**: Error messages truncated to 500 chars. Large payloads lose context.
- **Fix**: Increase to 2000 chars or store full error in separate column.

---

## Verification

1. Run full load cycle for each loader — verify no connection pool exhaustion
2. Simulate concurrent loads — verify no duplicate records
3. Simulate partial failure — verify staging and main table consistency
4. Check temp file cleanup: `ls /tmp/fed_prospector*` after failed bulk load
5. All Python tests pass: `python -m pytest fed_prospector/tests/ -v`
