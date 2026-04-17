# Phase 117: Daily Job Optimization

**Status**: PLANNED
**Priority**: High
**Depends on**: Phase 116 (baseline measurements)

## Objective

Reduce daily ETL job wall-clock time by ~22 minutes (from ~33m overhead across 5 steps down to ~11m) through targeted fixes for each bottleneck identified in Phase 116 analysis.

## Problem Statement

Phase 116 daily run analysis (2026-04-13) identified 5 performance bottlenecks in the daily ETL pipeline. Each has a different root cause — no single fix addresses them all.

| Step | Current Time | Root Cause |
|------|-------------|------------|
| `extract attachment-text` | 10m 28s | No per-file timeout; large PDFs stall workers |
| `extract attachment-intel` | 8m 23s | Serial processing; no parallelism |
| `download attachments` | 11m 24s | Only 5 threads, 0.1s delay; underutilized concurrency |
| `usaspending_award_summary` refresh | 2m 00s | Full 28.7M-row scan; missing covering index |
| `load opportunities` pagination | 46s | Fetches 25K records to find 1.5K new ones |

---

## Tasks

### 117A: Add covering index for usaspending_award_summary (10 min effort)

**Problem**: `refresh_usaspending_award_summary()` in `fed_prospector/etl/etl_utils.py:222` references a covering index `idx_usa_summary_cover` in comments, but the index does not exist in `fed_prospector/db/schema/tables/70_usaspending.sql`. The GROUP BY + ROLLUP query scans the clustered index (28.7M rows of full row data) instead of a compact 4-column index.

**Fix**:
- [ ] Add index to DDL: `CREATE INDEX idx_usa_summary_cover ON usaspending_award (naics_code, awarding_agency_cgac, recipient_uei, total_obligation)`
- [ ] Apply to live database
- [ ] Verify with `EXPLAIN` that the summary query shows `Using index`

**Files**: `fed_prospector/db/schema/tables/70_usaspending.sql`

**Expected**: 2m -> ~30-45s

---

### 117B: Increase download concurrency (20 min effort)

**Problem**: `AttachmentDownloader.download_attachments()` in `fed_prospector/etl/attachment_downloader.py:81` defaults to 5 threads with 0.1s inter-request delay. SAM.gov attachment downloads are static file serves (S3-backed), not rate-limited like the search API. Current settings leave bandwidth on the table.

**Fix**:
- [ ] Change default `workers` from 5 to 20
- [ ] Change default `delay` from 0.1 to 0.02 (20ms)
- [ ] Add `requests.Session()` with `HTTPAdapter(pool_connections=20, pool_maxsize=20)` for TCP connection reuse
- [ ] Verify no HTTP 429 errors in logs after change

**Files**: `fed_prospector/etl/attachment_downloader.py`

**Expected**: 11m -> ~3m

---

### 117C: Per-file timeout for PDF text extraction (30 min effort)

**Problem**: `extract_text()` in `fed_prospector/etl/attachment_text_extractor.py:894` uses `ProcessPoolExecutor(max_workers=10)` but has no per-file wall-clock timeout. Table detection is skipped for >30-page PDFs, but raw text extraction on 500+ page documents can still stall a worker for minutes. The last ~170 files (of 1,631) took 7 minutes — likely a few monster PDFs blocking worker slots.

**Fix**:
- [ ] Use `future.result(timeout=120)` when collecting futures in the `as_completed` loop
- [ ] On `TimeoutError`: log filename + page count, mark `extraction_status='timeout'`, continue
- [ ] Add `--timeout` CLI flag to `extract attachment-text` (default 120s)
- [ ] Log timed-out files at WARNING level for manual review

**Files**: `fed_prospector/etl/attachment_text_extractor.py`, `fed_prospector/cli/attachments.py`

**Expected**: 10m -> ~5m (worst-case files capped at 2m each)

---

### 117D: Narrow opportunity pagination window (45 min effort)

**Problem**: SAM.gov `/opportunities/v2/search` has no `modifiedSince` parameter. The loader in `fed_prospector/etl/opportunity_loader.py` fetches the full date range (typically 7 days = 25,892 records), hashes all of them, and finds only 1,539 are new. 94% of API calls and hash comparisons are wasted.

**Fix**:
- [ ] After successful load, persist the `postedTo` date in `etl_load_log.parameters`
- [ ] Add `--days=auto` mode: read last successful load's `postedTo`, set `postedFrom = last_postedTo - 1 day` (1-day overlap for safety)
- [ ] Keep `--days=N` as manual override for backfill
- [ ] Add `--since=YYYY-MM-DD` for explicit date control

**Files**: `fed_prospector/etl/opportunity_loader.py`, `fed_prospector/cli/opportunities.py`

**Expected**: 25K records -> ~5K records, 46s -> ~10s

---

### 117E: Parallelize intel keyword extraction (1-2 hr effort)

**Problem**: `extract_intel()` in `fed_prospector/etl/attachment_intel_extractor.py:449` processes notices in a serial `for nid in notice_ids` loop. Each notice runs ~70 regex patterns across all its text sources. With 777 notices, this takes 8m 23s (~0.65s per notice). The work is CPU-bound and embarrassingly parallel.

**Fix**:
- [ ] Replace serial loop with `ProcessPoolExecutor(max_workers=workers)`
- [ ] Each worker runs `_process_notice()` independently (already self-contained per notice)
- [ ] Each worker gets its own DB connection (use `get_connection()` factory)
- [ ] Default workers=6 (CPU-bound; match typical core count)
- [ ] Add `--workers` CLI flag to `extract attachment-intel`
- [ ] Aggregate stats from futures after completion
- [ ] Verify result counts match serial execution

**Files**: `fed_prospector/etl/attachment_intel_extractor.py`, `fed_prospector/cli/attachments.py`

**Consideration**: `_process_notice()` does DB reads (gather text sources) and DB writes (upsert intel rows). Each worker needs an independent connection to avoid cursor conflicts.

**Expected**: 8m -> ~2m (6 workers on CPU-bound regex)

---

## Implementation Order

| Priority | Task | Effort | Savings |
|----------|------|--------|---------|
| 1 | 117A — Covering index | 10 min | ~1.5m |
| 2 | 117B — Download concurrency | 20 min | ~8m |
| 3 | 117C — Extraction timeout | 30 min | ~5m |
| 4 | 117D — Pagination window | 45 min | ~36s |
| 5 | 117E — Intel parallelism | 1-2 hr | ~6m |

## Verification

After each task:
1. Run the affected CLI command and compare wall-clock time to Phase 116 baseline
2. Check `etl_load_log` for error counts — no regressions
3. For 117A: `EXPLAIN` the summary query to confirm `Using index`
4. For 117B: Check logs for HTTP 429 responses
5. For 117C: Review WARNING-level timeout logs for files to investigate
6. For 117E: Compare intel row counts and evidence row counts to serial baseline
