# Phase 65: USASpending Bulk Loader Improvements

**Status**: COMPLETE
**Priority**: High
**Depends on**: Phase 44 (original bulk loader)

## Problem

The USASpending bulk loader works but is slow and not resumable:
- FY2021 archive = 1.8GB ZIP, 7 CSV files, ~7M rows total
- Upsert time increases as table grows (10s → 30s+ per 50K batch) due to 9 secondary indexes
- No checkpoint/resume — if interrupted, re-processes everything from scratch
- No way to tell if a FY is already fully loaded
- Loading 5 years = multi-hour process that can't be interrupted safely

## Goals

1. **Resumable loads** — track progress so interrupted loads resume where they left off
2. **Skip already-loaded data** — detect when a FY/CSV/batch is already complete
3. **Faster upserts** — drop indexes during bulk load, rebuild after
4. **Better progress visibility** — ETA, throughput, file-level progress (partially done)

## Implementation Plan

### Task 1: Load checkpoint tracking
- [x] Add `usaspending_load_checkpoint` table:
  ```sql
  CREATE TABLE usaspending_load_checkpoint (
    id INT AUTO_INCREMENT PRIMARY KEY,
    load_id INT NOT NULL,
    fiscal_year INT NOT NULL,
    zip_file_name VARCHAR(255) NOT NULL,
    csv_file_name VARCHAR(255) NOT NULL,
    total_batches INT,
    completed_batches INT DEFAULT 0,
    status ENUM('IN_PROGRESS', 'COMPLETE', 'FAILED') DEFAULT 'IN_PROGRESS',
    started_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    UNIQUE KEY uq_load_csv (load_id, csv_file_name)
  );
  ```
- [x] After each batch commit, update `completed_batches` in checkpoint table
- [x] On startup, check for existing checkpoint for this FY + ZIP file
- [x] If checkpoint exists and is IN_PROGRESS, skip to the next unprocessed CSV / batch
- [x] If checkpoint exists and is COMPLETE, skip entirely (log "already loaded")

### Task 2: CSV-level skip logic
- [x] Before processing a CSV, check if it's already COMPLETE in checkpoint table
- [x] Log "Skipping CSV_file_1.csv (already loaded)" and move to next
- [x] Track which CSV file (by name) within a ZIP has been fully processed

### Task 3: Batch-level resume
- [x] When resuming a partially-loaded CSV, skip to batch N+1 (where N = completed_batches)
- [x] During CSV reading, skip the first N * BATCH_SIZE rows (they're already loaded)
- [x] This avoids re-reading and re-normalizing already-processed rows

### Task 4: Index management for faster bulk loads
- [x] Before first batch of a load: `ALTER TABLE usaspending_award DISABLE KEYS` (or drop secondary indexes)
- [x] After last batch of a load: `ALTER TABLE usaspending_award ENABLE KEYS` (or recreate indexes)
- [x] Note: `DISABLE KEYS` only works on MyISAM. For InnoDB, need to explicitly DROP/CREATE indexes
- [x] Store index definitions so they can be recreated exactly
- [x] Add `--fast` flag to CLI to opt into index dropping (not default, since it blocks queries during rebuild)

### Task 5: FY-level deduplication awareness
- [x] Before loading a FY, check if the archive file hash matches a previously loaded one
- [x] If same file was already fully loaded, skip entirely
- [x] Store archive file hash (SHA-256 of first 1MB + file size) in checkpoint table

### Task 6: Progress improvements (partially done)
- [x] CSV reading progress (every 100K rows)
- [x] Batch ETA calculation
- [x] Download progress (MB downloaded / total)
- [x] Overall FY progress: "CSV 3/7, Batch 12/20 (overall: 45%)"
- [x] Per-CSV timing summary at completion

## Files to Modify

| File | Changes |
|------|---------|
| `fed_prospector/db/schema/tables/70_usaspending.sql` | Add checkpoint table DDL |
| `fed_prospector/etl/usaspending_bulk_loader.py` | Checkpoint reads/writes, resume logic, index management |
| `fed_prospector/cli/bulk_spending.py` | Add `--fast` flag, display resume info |

## Performance Expectations

| Scenario | Current | After Phase 65 |
|----------|---------|----------------|
| Fresh FY load (7M rows) | ~2 hours | ~30 min (with index drop) |
| Re-run after completion | ~2 hours (full re-process) | ~5 seconds (skip) |
| Resume after interrupt at batch 50/140 | ~2 hours (restart) | ~45 min (resume from 50) |
| Batch upsert time | 10s → 30s+ (grows) | ~10s constant (no indexes) |

## Notes

- Archive download already skips if file exists locally (implemented in Phase 65 prep work)
- Batching at 50K rows per batch already implemented (Phase 65 prep work)
- The `--source archive` flag is already the default (smaller, faster files)
- Index rebuild after load is a one-time cost (~2-5 min for millions of rows) but saves cumulative time across all batches

## Resolved: FY Archive Scope (2026-03-08)

**Answer**: Archives are **NOT** scoped per-FY. They contain overlapping award IDs across fiscal years. Delete-then-insert is **NOT safe**.

**Test results**:

1. After FY2021 load: `SELECT fiscal_year, COUNT(*) FROM usaspending_award GROUP BY fiscal_year;`
   - FY2021: **5,682,188**
   - FY2026: 289,940 (from a prior accidental load)

2. After FY2022 load:
   - FY2021: **5,324,574** (dropped by ~358K — FY2022 archive overwrote FY2021 records)
   - FY2022: 5,855,671
   - FY2026: 282,876 (also changed slightly)

**Conclusion**: The FY2022 archive contains award IDs that also appear in FY2021 data. Upserts updated those rows, changing their `fiscal_year` value. This means:
- Must keep `INSERT ... ON DUPLICATE KEY UPDATE` (upserts)
- Cannot use `DELETE WHERE fiscal_year = X` + pure INSERT
- Fiscal year partitioning would NOT help (rows move between partitions)
- **Applicable optimizations**: Options 1-4 below (buffer pool tuning, staging table, larger batches, parallel pipeline)

**Observed batch slowdown**: FY2021 batches started at ~10s per 50K rows and grew to ~30s as the table filled. This is the PK B-tree getting larger, not secondary index overhead. `--fast` mode (dropping secondary indexes) does not help with this.

## Performance Options (if archives are NOT per-FY scoped)

If the FY test shows archives are cumulative (overlapping award IDs across FYs), we can't use delete-then-insert. These options address the PK lookup bottleneck while keeping upsert semantics:

### Option 1: InnoDB buffer pool tuning (try first — free perf)
Check `innodb_buffer_pool_size`. If it's smaller than the PK index + table data, MySQL does disk reads for every PK lookup during upsert. Bumping it to cover the full index in memory keeps lookups fast regardless of table size. Just a MySQL config change, no code.

### Option 2: Staging table pattern (best code-level fix)
Load each CSV into an empty temp table (constant speed, no PK conflicts), then bulk merge into the main table in one shot:
```sql
LOAD DATA INFILE ... INTO usaspending_staging;
INSERT INTO usaspending_award SELECT * FROM usaspending_staging
ON DUPLICATE KEY UPDATE col1=VALUES(col1), ...;
TRUNCATE usaspending_staging;
```
Still O(n log n) for the merge, but one merge per CSV instead of 20 per CSV. MySQL optimizes a single large merge better — buffer pool stays hot, fewer transaction commits.

### Option 3: Larger batch size
Increase from 50K to 500K+ rows per batch. Fewer transactions, fewer checkpoint updates, MySQL sorts the insert buffer more efficiently. Tradeoff: coarser checkpoint granularity (more re-work on resume).

### Option 4: Parallel read + load pipeline
Producer thread reads/parses CSV into temp files, consumer thread runs LOAD DATA. Overlaps I/O with DB work. ~20-30% improvement but doesn't fix the fundamental PK lookup cost. More complex error handling and checkpoint ordering.

### Option 5: Reduce PK overhead
`generated_unique_award_id` is VARCHAR(100) — every B-tree comparison is a string compare. A surrogate `BIGINT AUTO_INCREMENT` PK with the award ID as a UNIQUE index wouldn't speed up upserts (still needs the unique lookup), but would shrink every secondary index since they all carry the PK implicitly.

### Recommended order
1. Buffer pool tuning (Option 1) — check and fix first, zero code changes
2. Staging table (Option 2) — biggest code-level win
3. Larger batches (Option 3) — easy tweak if staging isn't enough
4. Pipeline / PK reduction only if still needed
