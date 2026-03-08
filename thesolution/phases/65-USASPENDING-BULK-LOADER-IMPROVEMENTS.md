# Phase 65: USASpending Bulk Loader Improvements

**Status**: NOT STARTED
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
- [ ] Add `usaspending_load_checkpoint` table:
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
- [ ] After each batch commit, update `completed_batches` in checkpoint table
- [ ] On startup, check for existing checkpoint for this FY + ZIP file
- [ ] If checkpoint exists and is IN_PROGRESS, skip to the next unprocessed CSV / batch
- [ ] If checkpoint exists and is COMPLETE, skip entirely (log "already loaded")

### Task 2: CSV-level skip logic
- [ ] Before processing a CSV, check if it's already COMPLETE in checkpoint table
- [ ] Log "Skipping CSV_file_1.csv (already loaded)" and move to next
- [ ] Track which CSV file (by name) within a ZIP has been fully processed

### Task 3: Batch-level resume
- [ ] When resuming a partially-loaded CSV, skip to batch N+1 (where N = completed_batches)
- [ ] During CSV reading, skip the first N * BATCH_SIZE rows (they're already loaded)
- [ ] This avoids re-reading and re-normalizing already-processed rows

### Task 4: Index management for faster bulk loads
- [ ] Before first batch of a load: `ALTER TABLE usaspending_award DISABLE KEYS` (or drop secondary indexes)
- [ ] After last batch of a load: `ALTER TABLE usaspending_award ENABLE KEYS` (or recreate indexes)
- [ ] Note: `DISABLE KEYS` only works on MyISAM. For InnoDB, need to explicitly DROP/CREATE indexes
- [ ] Store index definitions so they can be recreated exactly
- [ ] Add `--fast` flag to CLI to opt into index dropping (not default, since it blocks queries during rebuild)

### Task 5: FY-level deduplication awareness
- [ ] Before loading a FY, check if the archive file hash matches a previously loaded one
- [ ] If same file was already fully loaded, skip entirely
- [ ] Store archive file hash (SHA-256 of first 1MB + file size) in checkpoint table

### Task 6: Progress improvements (partially done)
- [x] CSV reading progress (every 100K rows)
- [x] Batch ETA calculation
- [x] Download progress (MB downloaded / total)
- [ ] Overall FY progress: "CSV 3/7, Batch 12/20 (overall: 45%)"
- [ ] Per-CSV timing summary at completion

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
