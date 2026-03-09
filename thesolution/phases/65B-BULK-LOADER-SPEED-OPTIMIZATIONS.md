# Phase 65B: Bulk Loader Speed Optimizations

Sub-phase of Phase 65 (USASpending Bulk Loader Improvements).

Phase 65 handled checkpoint/resume, index management, and progress. Phase 65B focuses on raw speed optimizations.

## Problem

The bulk loader works but has several speed bottlenecks beyond the upsert PK lookup issue (addressed by buffer pool tuning in 65):

- ZIP extraction: 51 seconds using Python's single-threaded zipfile module for a 1.8GB ZIP
- CSV parsing: ~7 seconds per 100K rows using csv.DictReader (creates a dict per row, expensive at millions of rows)
- MySQL generates large binary log and undo log files during bulk loads, adding I/O overhead

## Goals

1. Faster ZIP extraction via 7-Zip (multi-threaded) with Python zipfile fallback
2. Faster CSV parsing by switching from DictReader to index-based csv.reader
3. Reduce MySQL I/O overhead during bulk loads by temporarily disabling binary logging and adjusting undo log settings

## Implementation Plan

### Task 1: Fast ZIP extraction

- [ ] Try shelling out to `7z` (7-Zip) first — multi-threaded, significantly faster on large archives
- [ ] Fall back to Python `zipfile` if 7z is not on PATH
- [ ] Log which method was used and extraction time

### Task 2: Fast CSV parsing

- [ ] Switch from `csv.DictReader` to `csv.reader` with a header-to-index mapping
- [ ] Build column index map from the header row once, then access by index instead of key
- [ ] This avoids creating a dict for every row (millions of rows)
- [ ] Expected improvement: 2-3x faster CSV reading

### Task 3: MySQL bulk load session optimizations

- [ ] At the start of a bulk load session, run these SET statements (session-scoped, not global):
  ```sql
  SET SESSION sql_log_bin = 0;              -- disable binary logging for this session
  SET SESSION innodb_flush_log_at_trx_commit = 2;  -- flush log once per second instead of every commit
  SET SESSION unique_checks = 0;            -- skip unique constraint checks (we trust our data)
  SET SESSION foreign_key_checks = 0;       -- skip FK checks (no FKs on this table, but just in case)
  ```
- [ ] Restore defaults at end of load (or just let session close)
- [ ] Log that bulk optimizations are active
- [ ] Note: `sql_log_bin` requires SUPER or SESSION_VARIABLES_ADMIN privilege. If fed_app doesn't have it, skip gracefully and log a warning.

### Task 4: Reduce binary log / undo log file bloat

- [ ] Document in this file: users can purge old binlogs with `PURGE BINARY LOGS BEFORE NOW() - INTERVAL 1 DAY`
- [ ] Document: binary logging can be disabled entirely for dev/single-server setups by adding `skip-log-bin` to my.ini
- [ ] Add `skip-log-bin` to the reference my.ini at thesolution/reference/mysql-my.ini with a comment explaining when it's safe (single server, no replication)
- [ ] Document: `innodb_undo_log_truncate = ON` and `innodb_max_undo_log_size` can limit undo tablespace growth

## Files to Modify

| File | Changes |
|------|---------|
| `fed_prospector/etl/usaspending_bulk_loader.py` | 7z extraction, csv.reader switch, session SET statements |
| `thesolution/reference/mysql-my.ini` | Add skip-log-bin and undo log settings |

## Performance Expectations

| Operation | Current | After 65B |
|-----------|---------|-----------|
| ZIP extraction (1.8GB) | ~51s (Python zipfile) | ~10-15s (7-Zip) |
| CSV reading (1M rows) | ~70s (DictReader) | ~25-35s (csv.reader) |
| Per-batch I/O overhead | High (binlog + fsync every commit) | Low (no binlog, async flush) |

## Notes

- These optimizations stack with Phase 65's buffer pool tuning (Option 1) and checkpoint/resume
- The session SET statements only affect the bulk loader's connection, not other queries
- 7-Zip must be installed separately (not bundled). Common paths: C:\Program Files\7-Zip\7z.exe or just `7z` on PATH
- `skip-log-bin` should NOT be used on production replicated setups — only single-server or dev environments

## Status

**Status**: NOT STARTED
**Priority**: Medium
**Depends on**: Phase 65
