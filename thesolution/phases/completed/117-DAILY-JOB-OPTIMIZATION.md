# Phase 117: Daily Job Optimization

**Status**: COMPLETE (2026-04-17)
**Priority**: High
**Depends on**: Phase 116 (baseline measurements)

## Outcome

| Task | Result |
|------|--------|
| 117A — Covering index | ✅ Shipped. `usaspending_award_summary` refresh went from ~2m baseline to **70.3s** in first post-change run (~41% faster). `EXPLAIN` confirms `Using index`. |
| 117B — Downloader Session + 429 + workers 10 / delay 0.05 | ✅ Shipped. Verified engaging in post-change run (only 2 files to process — no perf measurement yet). Zero `max_retries_http_429` events. |
| 117C — Pebble ProcessPool timeout | ✅ Shipped. Verified engaging (`timeout=120` in logs). Schema migration applied live. No monsters hit the cap yet. |
| 117D — Narrow pagination window | 🚫 Deferred (correctness risk — SAM.gov has no `modifiedSince`; current 7-day window informally catches amendments). |
| 117E — Parallel intel extraction | ✅ Shipped. `workers=4` engaging (confirmed in logs). Hash-skip idempotency working (53 notices skipped in seconds on re-run). Smoke-tested against 10-notice shared-doc stress case: zero dupes, zero deadlocks. |

Actual total savings to be measured on next full daily run with real workload; only 117A got exercised against real volume this session.

## Objective

Reduce daily ETL job wall-clock time by ~17-20 minutes (from ~33m overhead across 5 steps) through targeted fixes for each bottleneck identified in Phase 116 analysis. Revised downward from the original ~22m estimate after code-level evaluation of each fix.

## Problem Statement

Phase 116 daily run analysis (2026-04-13) identified 5 performance bottlenecks in the daily ETL pipeline. Each has a different root cause — no single fix addresses them all.

| Step | Current Time | Root Cause |
|------|-------------|------------|
| `extract attachment-text` | 10m 28s | No per-file timeout; large PDFs stall `ProcessPoolExecutor` worker slots |
| `extract attachment-intel` | 8m 23s | Serial processing; no parallelism |
| `download attachments` | 11m 24s | Only 5 threads, 0.1s delay, no connection pooling; underutilized concurrency |
| `usaspending_award_summary` refresh | 2m 00s | Full 28.7M-row scan; missing covering index |
| `load opportunities` pagination | 46s | Fetches 25K records to find 1.5K new ones — **correctness risk, see 117D** |

---

## Tasks

### 117A: Add covering index for usaspending_award_summary (1-2 hr wall-clock with build time)

**Problem**: `refresh_usaspending_award_summary()` in [fed_prospector/etl/etl_utils.py:222](../../fed_prospector/etl/etl_utils.py#L222) references a covering index `idx_usa_summary_cover` in its docstring and inline comments, but the index does not exist in [fed_prospector/db/schema/tables/70_usaspending.sql](../../fed_prospector/db/schema/tables/70_usaspending.sql) (lines 66-81 define 11 indexes, none is this one). The GROUP BY + ROLLUP query scans the clustered index (28.7M rows of wide row data) instead of a compact 4-column index.

Actual query (etl_utils.py:250-271):
```sql
WHERE naics_code IS NOT NULL AND recipient_uei IS NOT NULL
GROUP BY naics_code, awarding_agency_cgac WITH ROLLUP
-- aggregates: COUNT(DISTINCT recipient_uei), COUNT(*), SUM(total_obligation)
```

**Fix**:
- [x] Add index to DDL: `CREATE INDEX idx_usa_summary_cover ON usaspending_award (naics_code, awarding_agency_cgac, recipient_uei, total_obligation)`
- [x] Apply to live database during a maintenance window (initial build on 28.7M rows will take 5-15 minutes)
- [x] Verify with `EXPLAIN` that the summary query shows `Using index` (no clustered-row access)
- [x] Capture before/after refresh timings in phase completion notes — **2m baseline → 70.3s post-change**

**Files**: `fed_prospector/db/schema/tables/70_usaspending.sql`

**Cost**: ~1.5-2 GB additional InnoDB index space. Negligible write overhead on daily loads (~1-2% slowdown on LOAD DATA INFILE).

**Expected**: 2m -> ~30-45s

---

### 117B: Increase download concurrency with Session pooling — **IMPLEMENTED (not yet run in prod)**

**Problem**: `AttachmentDownloader.download_attachments()` in [fed_prospector/etl/attachment_downloader.py:65-229](../../fed_prospector/etl/attachment_downloader.py#L65) defaulted to 5 threads with 0.1s inter-request delay. Each `requests.get()` created a new TCP+TLS connection — no `Session`, no 429 handling. The 303 redirect to S3 is confirmed (line 47 regex, line 500 comment).

**Dedup safety audit (pre-change)**: 8 dedup layers mapped; verified that increasing thread count does NOT open any race within a single CLI invocation:

| # | Layer | Enforcement |
|---|-------|-------------|
| 1 | `_dedup_by_guid` pre-pool assignment (`attachment_downloader.py:476`) | Python dict — workers pull disjoint GUIDs |
| 2 | `sam_attachment.resource_guid` UNIQUE index | `INSERT ... ON DUPLICATE KEY UPDATE` |
| 3 | Content hash SHA-256 on downloaded bytes (`sam_attachment.content_hash`, computed line 684) | Per-row, computed by owning thread |
| 4 | `opportunity_attachment` composite PK `(notice_id, attachment_id)` | `INSERT IGNORE` |
| 5 | `attachment_document` (designed for future content-level document dedup) | 1:1 with sam_attachment today |
| 6 | Text hash SHA-256 (`attachment_document.text_hash`) | Stored, informational |
| 7 | `document_intel_summary` UNIQUE `(document_id, extraction_method)` | `ON DUPLICATE KEY UPDATE` |
| 8 | `opportunity_attachment_summary` UNIQUE `(notice_id, extraction_method)` | `ON DUPLICATE KEY UPDATE` |

Because layer 1 runs *before* the thread pool, threads get disjoint GUIDs. 5→10 threads never race on the same GUID. Cross-*process* races (two concurrent CLI invocations) existed before and remain unchanged — NOT introduced by this change.

**What was implemented**:
- [x] Added `requests.Session()` with `HTTPAdapter(pool_connections=20, pool_maxsize=20, max_retries=0)` mounted on both `http://` and `https://`. Session stored as instance attribute, shared across worker threads.
- [x] Replaced both `requests.get()` calls in `_download_single` (initial + post-redirect) with `self.session.get()`.
- [x] Added 429 detection with `_parse_retry_after()` helper (handles integer-seconds and HTTP-date forms). On 429: log WARNING, sleep `Retry-After` seconds, retry. Cap at 3 attempts per file; on exhaustion mark `skip_reason="max_retries_http_429"`. Does NOT touch the permanent-failure retry counter.
- [x] Changed defaults: `workers` 5 → 10, `delay` 0.1 → 0.05. CLI flags preserved as overrides.

**Files changed**: `fed_prospector/etl/attachment_downloader.py` (~95 LOC), `fed_prospector/cli/attachments.py` (2 LOC defaults).

**Expected**: 11m → **~4-5m** (revised down from original 3m estimate — per-file DB connection setup (`_check_existing_guid` + `_upsert_attachment_row` ~4 conns/file) limits linear scaling).

**Verification after first prod run**:
- Wall-clock timing in `etl_load_log` for `download_attachments`
- Check `sam_attachment.skip_reason` for any `max_retries_http_429` entries
- No increase in `download_status='failed'` rate vs baseline

---

### 117C: Per-file timeout for PDF text extraction (2-3 hr effort — harder than original plan indicated)

**Problem**: `extract_text()` in [fed_prospector/etl/attachment_text_extractor.py:894](../../fed_prospector/etl/attachment_text_extractor.py#L894) uses `ProcessPoolExecutor(max_workers=10)` but has no per-file wall-clock timeout. Table detection is skipped for >30-page PDFs, but raw text extraction on 500+ page documents can still stall a worker for minutes. The last ~170 files (of 1,631) took 7 minutes — likely a few monster PDFs blocking worker slots.

**CRITICAL — the original plan's approach does not work**: `future.result(timeout=120)` inside an `as_completed` loop is a **no-op** — `as_completed` only yields already-completed futures, so the timeout never fires. And `future.cancel()` on a running `ProcessPoolExecutor` task returns `False` and does nothing — the worker keeps running, holding its slot. `signal.alarm()` is Unix-only; not viable on Windows.

**Fix — use one of these approaches** (decide during implementation):

Option 1 (preferred): **`pebble.ProcessPool`** — drop-in replacement that supports `schedule(fn, timeout=120)` and actually terminates (SIGTERM/SIGKILL) + respawns the worker. ~10 lines of code change, adds one dependency.

Option 2: **Custom `multiprocessing.Process` + `.terminate()`** — manage a pool with a work queue. Parent monitors wall-clock per worker; on overrun, `proc.terminate()` + spawn replacement. ~50 lines, no new dependency.

Tasks:
- [x] Decide Option 1 vs Option 2 — **chose Option 1 (pebble)**; `pebble>=5.0` added to `requirements.txt`
- [x] Implement timeout + worker respawn (pebble `ProcessPool.schedule(..., timeout=N)` in [attachment_text_extractor.py](../../fed_prospector/etl/attachment_text_extractor.py))
- [x] **Schema migration**: ENUM extended with `'timeout'` — DDL updated and ALTER applied to live DB
- [x] On timeout: log WARNING with filename/doc id/notice id, mark `extraction_status='timeout'` via `_mark_timeout`, record error via `log_record_error`, continue
- [x] Add `--timeout` CLI flag to `extract attachment-text` (default 120s)

**Files**: `fed_prospector/etl/attachment_text_extractor.py`, `fed_prospector/cli/attachments.py`, `fed_prospector/db/schema/tables/36_attachment.sql`

**Expected**: 10m -> ~5m (worst-case files capped at 2m each, rest unaffected)

---

### 117D: Narrow opportunity pagination window — **DEFERRED**

**Original proposal**: persist last `postedTo` in `etl_load_log.parameters`, add `--days=auto` to use `postedFrom = last_postedTo - 1 day`.

**Why deferred**:

1. **Correctness risk outweighs performance gain.** SAM.gov `/opportunities/v2/search` has no `modifiedSince` parameter (confirmed in [sam_opportunity_client.py:88-168](../../fed_prospector/api_clients/sam_opportunity_client.py#L88)). `postedDate` never moves when a notice is amended (deadline changes, attachments added, set-aside changes). A 1-day overlap protects against posted-date boundary flicker but does **not** catch amendments to notices posted days/weeks earlier. The current 7-day sliding window is an informal amendment-detector.
2. **Savings are small**: 46s / ~33m overhead = <3% of the optimization target. The smallest win in the phase.
3. **Other tasks dominate**: 117B (~6-7m), 117C (~5m), 117E (~5-6m), 117A (~1.5m) all offer more value.

**Revisit if**: SAM.gov publishes a modified-notices feed/extract, or daily wall-clock becomes gating after 117A/B/C/E ship.

---

### 117E: Parallelize intel keyword extraction — **IMPLEMENTED + SMOKE-TESTED**

**Problem**: `extract_intel()` at [fed_prospector/etl/attachment_intel_extractor.py](../../fed_prospector/etl/attachment_intel_extractor.py) processed notices in a serial `for nid in pbar` loop. Each notice runs ~70 compiled regex patterns. 777 notices at ~0.65s/notice = 8m 23s. Regex is CPU-bound; threads won't help due to GIL.

**Concurrency risk analysis**:

One `document_id` can map to many notices via `opportunity_attachment`. Measured shape (2026-04-17):
- 77,661 mapping rows, 48,094 distinct attachments, 18,684 distinct notices — **mean 1.615 notices per attachment**
- **65.8% independent**, 19.4% shared with 1 other notice, 8.7% with 2, 6.1% tail up to 10

Initial theory (duplicate evidence rows from racing DELETE+INSERT) was **disproven** by smoke test. `_replace_source_rows` uses a single InnoDB transaction (`autocommit=False`, explicit `commit()`), so InnoDB row locks already serialize the DELETE+INSERT pair per intel_id. The real failure mode under parallel force is **InnoDB deadlocks** (errno 1213) — two workers both cleaning up shared intel rows via `_cleanup_stale_intel_rows` or upserting same `(document_id, method)` key. Deadlocks cause the losing transaction to roll back, silently losing that notice's re-extraction work.

**Implementation (two complementary mechanisms)**:

1. **Hash-match idempotency skip** (`_get_existing_intel_hash` + check at top of per-document block):
   - Before running regex on a document, query `document_intel_summary.source_text_hash` for `(document_id, method)`.
   - If it matches the hash of the text about to be processed → skip regex scan + UPSERT + evidence replace entirely.
   - Stamp `keyword_analyzed_at` and move to the next document.
   - Keyed on **extracted-text hash** (post-extraction), NOT file-bytes hash — the skip fires even when the same content was uploaded as two different file formats (e.g., .docx + .pdf of same document).
   - `force=True` bypasses the check.
   - **Side benefit**: on the 34% shared-document work, subsequent workers hit the skip and do zero regex/write work → performance improvement PLUS a smaller race window.

2. **InnoDB deadlock retry wrapper** (`_process_notice_worker`):
   - Wraps the entire notice-processing call.
   - Catches `errno==1213` (deadlock) up to 3 times with exponential backoff + jitter (50ms * 2^attempt + 0-50ms).
   - Covers residual deadlocks from `_cleanup_stale_intel_rows` (only runs under `force=True`) and first-time UPSERT contention on shared documents.

**Smoke test results** (10 notices sharing 5 documents, `fed_prospector/test_117e_race_adhoc.py`):

| Run | Mode | Wall time | Worker errors | Evidence rows |
|-----|------|-----------|---------------|---------------|
| 1 | Serial, force=True (baseline) | 3.21s | 0 | 15 ✓ |
| 2 | Parallel workers=2, force=True | 2.44s | 0 (deadlock retry recovered) | 15 ✓ |
| 3 | Parallel workers=2, force=False | 1.84s | 0 | 15 ✓ |
| 4 | Parallel workers=2, force=False (re-run, all hash-skip) | 1.85s | 0 | 15 ✓ |

All four configurations produce identical evidence row counts and distribution. Hash-skip makes non-force runs ~25% faster than force runs on the same notices, with zero worker failures.

**Connection-limit caveat**: MySQL server `max_connections=100`. Each ProcessPoolExecutor worker creates its own pool with `DB_POOL_SIZE=10`. With parent process pool + N worker pools, realistic safe ceiling is **workers ≤ 4** on current server config. Smoke test used `workers=2` (test process itself consumes a pool). Consider raising `max_connections` to 200+ to support full `workers=4` on production daily jobs.

**Code landed**:
- [x] Module-level `_process_notice_worker(args)` with deadlock retry loop (Windows spawn-compatible)
- [x] `extract_intel(workers=N)`: serial path for `workers=1`; `ProcessPoolExecutor` + `executor.map(chunksize=10)` for N>1
- [x] `_get_existing_intel_hash(document_id, method)` helper
- [x] Hash-match skip in `_process_notice` per-document loop
- [x] CLI `--workers` flag (default 4) on `extract attachment-intel` and `extract description-intel`

**Files**: [fed_prospector/etl/attachment_intel_extractor.py](../../fed_prospector/etl/attachment_intel_extractor.py), [fed_prospector/cli/attachments.py](../../fed_prospector/cli/attachments.py).

**Expected savings**: 8m → **~3m** for daily runs (non-force + hash-skip on 34% of work). Parallel `--force` runs will be slightly slower due to deadlock retries but will not drop work.

**Pre-prod checklist**:
- [x] Raise MySQL `max_connections` from 100 to 200 — applied via `SET GLOBAL` + persisted in `E:/mysql/my.ini` (reference copy `thesolution/reference/mysql-my.ini` also updated)
- [x] First daily run: `workers=4` engagement confirmed in logs; hash-skip path exercised correctly (53 notices, 0 redundant inserts). Wall-clock measurement deferred to next daily with real volume.
- [x] Delete `fed_prospector/test_117e_race_adhoc.py` after verification

---

## Implementation Order

| Priority | Task | Status | Effort | Savings |
|----------|------|--------|--------|---------|
| 1 | 117A — Covering index | DDL in repo; live index build in progress | 1-2 hr (mostly build time) | ~1.5m |
| 2 | 117B — Download Session + concurrency | **IMPLEMENTED** — awaiting first prod run | 45-60 min | ~6-7m |
| 3 | 117E — Intel parallelism | **IMPLEMENTED** (hash-skip + deadlock retry, smoke-tested) | 2-3 hr | ~5m |
| 4 | 117C — Extraction timeout | Awaiting dep decision (pebble vs custom pool) | 2-3 hr | ~5m |
| — | 117D — Pagination window | DEFERRED (correctness risk) | — | — |

**Total expected savings**: ~17-20 minutes (revised down from original ~22m). 117D dropped.

## Verification

After each task:
1. Run the affected CLI command and compare wall-clock time to Phase 116 baseline
2. Check `etl_load_log` for error counts — no regressions
3. Compare row counts (intel rows, attachment rows, etc.) vs baseline to verify no data loss
4. For 117A: `EXPLAIN` the summary query to confirm `Using index` and no clustered-row access
5. For 117B: Check logs for any HTTP 429 responses; watch `sam_attachment.skip_reason` distribution
6. For 117C: Review WARNING-level timeout logs for files to investigate; spot-check `extraction_status='timeout'` rows
7. For 117E: Compare intel row counts, evidence row counts, and per-category stats to serial baseline
