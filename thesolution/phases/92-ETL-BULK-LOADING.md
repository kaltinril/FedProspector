# Phase 92 — ETL Bulk Loading Refactor

**Status**: BACKLOG
**Priority**: HIGH
**Depends on**: None

---

## Context

Award loads into `fpds_contract` take 1-10 seconds per 100 records due to row-by-row SQL inserts. Every record does **3 separate SQL round-trips**:

1. `_insert_staging()` — 1 INSERT per record with autocommit (fsync each row)
2. `_upsert_award()` — 1 INSERT...ON DUPLICATE KEY UPDATE per record, SQL string rebuilt every call
3. `_mark_staging()` — 1 UPDATE per record with autocommit (fsync each row)

This pattern is shared by all 6 StagingMixin-based loaders. Additionally, `_get_existing_hashes()` loads the entire target table (111K+ rows for fpds_contract) into a Python dict on every run.

**Target**: <0.1 seconds per 100 records (10-100x improvement) via `executemany()` and batched staging operations.

---

## Loader Classification

| Loader | Target Table | PK Type | Current Pattern | Batch Difficulty |
|--------|-------------|---------|-----------------|-----------------|
| awards | fpds_contract | Natural (composite) | INSERT ON DUP KEY | Low |
| fedhier | federal_organization | Natural (single) | INSERT ON DUP KEY | Low |
| usaspending | usaspending_award | Natural (single) | INSERT ON DUP KEY | Low |
| subaward | sam_subaward | Auto-increment | SELECT-then-UPDATE/INSERT | Moderate |
| exclusions | sam_exclusion | Auto-increment | SELECT-then-UPDATE/INSERT | Moderate-High |
| opportunity | opportunity | Natural (single) | INSERT ON DUP KEY + POC/history | High |
| calc | gsa_labor_rate | Auto | Already uses executemany + LOAD DATA INFILE | **Skip** |

---

## Existing Patterns to Reuse

| Pattern | Source File | Lines |
|---------|------------|-------|
| LOAD DATA INFILE with TSV temp files | `etl/bulk_loader.py` | 373-478 |
| `escape_tsv_value()` helper | `etl/etl_utils.py` | 92-104 |
| `executemany()` batch INSERT | `etl/calc_loader.py` | 311-338 |
| Row-by-row staging INSERT (to replace) | `etl/staging_mixin.py` | 46-65 |
| Row-by-row staging UPDATE (to replace) | `etl/staging_mixin.py` | 77-79 |
| Per-record upsert with SQL rebuild (to replace) | `etl/awards_loader.py` | 478-522 |
| Full-table hash fetch (to scope) | `etl/awards_loader.py` | 453-476 |
| Composite hash pre-fetch via CONCAT | `etl/subaward_loader.py` | 128-132 |
| Windows path handling for LOAD DATA INFILE | `etl/bulk_loader.py` | 447 |

---

## Items to Address

### HIGH PRIORITY

**P92-1 — StagingMixin: Add batch INSERT and UPDATE methods**
File: `fed_prospector/etl/staging_mixin.py`

Add batch counterparts alongside existing row-by-row methods:

- `_insert_staging_batch(stg_cursor, load_id, rows: list[tuple[dict, dict]]) -> list[int]`
  - Uses `cursor.executemany()` with single prepared INSERT
  - Wraps in explicit transaction (disable autocommit for the batch, commit after)
  - Returns list of staging IDs

- `_mark_staging_batch(stg_cursor, staging_ids: list[int], processed: str)`
  - Single `UPDATE ... WHERE id IN (...)` instead of N individual UPDATEs
  - Chunk into groups of 1000 if list exceeds MySQL max packet size

Keep existing `_insert_staging` / `_mark_staging` for error-path fallback (single records that fail batch).

---

**P92-2 — Batch upsert helper module**
New file: `fed_prospector/etl/batch_upsert.py`

- `build_upsert_sql(table, columns, pk_fields, timestamp_cols=None) -> str`
  - Returns static INSERT...ON DUPLICATE KEY UPDATE SQL string
  - Called once at loader init, not per record

- `executemany_upsert(cursor, sql, rows: list[tuple]) -> int`
  - Wraps `cursor.executemany()` with the pre-built SQL
  - Returns total rowcount

Covers awards, fedhier, usaspending, and opportunity (all INSERT ON DUP KEY loaders).

---

**P92-3 — Refactor AwardsLoader (reference implementation)**
File: `fed_prospector/etl/awards_loader.py`

Replace `_process_awards()` row-by-row loop (lines 154-273) with batch pipeline:

```
1. Normalize all records in Python (pure CPU, fast)
2. Compute hashes, classify into inserts/updates/unchanged via existing hash cache
3. Batch staging INSERT (P92-1)
4. Batch upsert changed records with executemany (P92-2)
5. Batch staging UPDATE (P92-1)
6. Commit
```

- Pre-compute upsert SQL as class constant (currently rebuilt in `_upsert_award` lines 489-504 every call)
- Keep per-record error handling: if executemany fails, fall back to row-by-row for that batch to isolate the bad record
- Keep 500-record batch commit cadence for transaction size management
- Process in batches of API pages (already natural boundary)

Also scope `_get_existing_hashes()` — add optional WHERE clause to limit rows fetched when loading a specific date range or NAICS.

---

**P92-4 — Apply batch pattern to fedhier and usaspending loaders**
Files: `fed_prospector/etl/fedhier_loader.py`, `fed_prospector/etl/usaspending_loader.py`

Same pattern as awards — straightforward INSERT ON DUP KEY with single natural keys, no side effects. Easiest ports.

---

### MEDIUM PRIORITY

**P92-5 — Apply batch pattern to subaward and exclusions loaders**
Files: `fed_prospector/etl/subaward_loader.py`, `fed_prospector/etl/exclusion_loader.py`

These use SELECT-then-UPDATE/INSERT because they have auto-increment PKs with composite logical keys. Two options:

**Option A (preferred):** Add unique indexes on the logical key columns, then switch to INSERT ON DUP KEY UPDATE like the other loaders. Validate no duplicate data first:
- subaward: `UNIQUE(prime_piid, sub_uei, sub_date)`
- exclusion: `UNIQUE(uei, activation_date, exclusion_type)` + handle the entity_name fallback

**Option B (fallback):** Batch the SELECT into one query (`WHERE (col1, col2, col3) IN (...)`), build in-memory lookup, then batch INSERT new / batch UPDATE changed.

> Before adding unique indexes, run duplicate checks:
> ```sql
> SELECT prime_piid, sub_uei, sub_date, COUNT(*) c
> FROM sam_subaward GROUP BY 1,2,3 HAVING c > 1;
> ```

---

**P92-6 — Apply batch pattern to opportunity loader**
File: `fed_prospector/etl/opportunity_loader.py`

Most complex — has side-effect writes to `contracting_officer`, `opportunity_poc`, `opportunity_history`. Strategy:

1. Batch the main `opportunity` upsert (same as awards)
2. Batch POC writes: collect all POC records, executemany into `contracting_officer` and `opportunity_poc`
3. History logging: batch-fetch old records for the update set in one `SELECT WHERE notice_id IN (...)`, diff in Python, then executemany the history inserts
4. Keep relationship detection (`populate_relationships`) as-is — it's a separate post-load operation

---

### LOW PRIORITY

**P92-7 — Consolidate duplicate `escape_tsv_value`**
Files: `fed_prospector/etl/etl_utils.py` (keep), `fed_prospector/etl/bulk_loader.py` (import from etl_utils)

The function exists identically in both files. Remove from bulk_loader.py, import from etl_utils.

---

## Execution Order

```
P92-1 (StagingMixin batch) ──┐
P92-2 (batch_upsert helper) ─┼─> P92-3 (Awards) ─> P92-4 (fedhier, usaspending)
                              │                  ─> P92-5 (subaward, exclusions)
                              │                  ─> P92-6 (opportunity)
P92-7 (consolidate escape)   ── independent
```

---

## Backward Compatibility

- Existing row-by-row methods on StagingMixin kept until all loaders migrated
- No schema changes for INSERT ON DUP KEY loaders (awards, fedhier, usaspending, opportunity)
- Schema change required for subaward/exclusions (Option A: add unique indexes) — validate data first
- Change detection logic unchanged — same hash fields, same SHA-256, just batch-friendly wrappers
- CLI interface unchanged — same commands, same arguments, just faster

---

## Risks and Mitigation

| Risk | Mitigation |
|------|------------|
| `executemany` hides which record caused an error | Fallback to row-by-row for failed batches to isolate bad record |
| Unique index on subaward/exclusion may fail (duplicate data) | Run duplicate check queries before adding indexes; use Option B if dupes exist |
| Opportunity history diffing needs old records pre-fetched | Batch-fetch old records in one SELECT before upsert |
| Large batch transactions could lock tables | Keep 500-record commit cadence (same as current) |

---

## Files Modified

| File | Change |
|------|--------|
| `fed_prospector/etl/staging_mixin.py` | Add `_insert_staging_batch`, `_mark_staging_batch` |
| `fed_prospector/etl/batch_upsert.py` | New — `build_upsert_sql`, `executemany_upsert` |
| `fed_prospector/etl/awards_loader.py` | Replace row-by-row loop with batch pipeline |
| `fed_prospector/etl/fedhier_loader.py` | Apply batch pattern |
| `fed_prospector/etl/usaspending_loader.py` | Apply batch pattern |
| `fed_prospector/etl/subaward_loader.py` | Add unique index + batch pattern |
| `fed_prospector/etl/exclusion_loader.py` | Add unique index + batch pattern |
| `fed_prospector/etl/opportunity_loader.py` | Batch upsert + batch POC/history writes |
| `fed_prospector/etl/etl_utils.py` | Keep canonical `escape_tsv_value` |
| `fed_prospector/etl/bulk_loader.py` | Import `escape_tsv_value` from etl_utils |
| `fed_prospector/db/schema/` | DDL for unique indexes (subaward, exclusion) if Option A |

---

## Verification Checklist

- [ ] Awards load: <0.1s per page of 100 records (`load awards --naics 541512 --years-back 1 --max-calls 5`)
- [ ] Record counts match before/after refactor for all loaders
- [ ] Staging table records still populated correctly
- [ ] Change detection still works: load same data twice, second load shows 0 new/updated
- [ ] Per-record errors still isolated and logged (not lost in batch)
- [ ] All existing tests pass: `pytest fed_prospector/tests/`
- [ ] Duplicate check passes before adding unique indexes (P92-5)
