# Phase 77: USASpending Delta Loader

**Status**: NOT STARTED
**Priority**: High
**Depends on**: Phase 65 (bulk loader improvements), Phase 44 (original bulk loader)

## Problem

Keeping `usaspending_award` current requires re-downloading and re-processing entire fiscal year Full archive files (~35-40M rows across all FYs). USASpending regenerates ALL archive files monthly — even closed FY files — because agencies post late modifications, corrections, de-obligations, and closeouts. Re-loading everything is expensive in time and bandwidth.

USASpending provides a Delta file (`FY(All)_All_Contracts_Delta_<date>.zip`) containing only records changed since the last monthly archive refresh. This file has the same 299-column format as Full files, plus one extra column (`correction_delete_ind`) to flag deletions. The delta file contains ~2M rows/month vs 35-40M in all Full files combined.

## Background

### Bulk CSV files are transaction-level, not award-level

The FY Full files contain transaction-level data — one row per contract modification. The existing `usaspending_bulk_loader.py` handles this by deduplicating with `ROW_NUMBER() OVER (PARTITION BY generated_unique_award_id ORDER BY last_modified_date DESC)` to keep only the latest row per award. It maps ~25 of the 299 columns via `CSV_COLUMN_MAP` and discards the rest.

### Delta file structure

- File: `FY(All)_All_Contracts_Delta_<date>.zip`
- Contains 2 CSVs, ~2M total rows (Feb 2026: 1M + 985K)
- Same 299-column format as Full files, plus `correction_delete_ind` (column 0)
- `correction_delete_ind` values per USASpending docs:
  - blank = **Added** (new record)
  - `"C"` = **Corrected** (modified record — treat as upsert)
  - `"D"` = **Deleted** (remove from local copy — agency corrections, duplicates, errors)
- D rows: 435 in ~2M rows (0.02%). ALL have blank `contract_award_unique_key` and empty dollar values
- D rows do have PIIDs and `contract_transaction_unique_key`, but NOT the award-level key we use as PK
- Verified: 3 of 5 sampled D-row PIIDs exist in our DB with proper award keys (e.g., PIID `70Z03825PN0000210` → `CONT_AWD_70Z03825PN0000210_7008_-NONE-_-NONE-`), but the D row's award key field is blank
- Cannot reliably reconstruct award key from transaction key — fails for delivery/task orders under IDVs where parent award info is needed
- **Practical impact**: D rows are a no-op for our pipeline since blank keys can't match any PK in `usaspending_award`
- Spans ALL fiscal years in one file (FY1979 through FY2026)
- Heavy on recent years: FY2026 ~590K rows, FY2025 ~485K rows

### Data semantics — cumulative vs incremental

The CSV files are transaction-level (one row per contract modification). Dollar columns have different semantics:

| Column | Semantics | In our column map? |
|--------|-----------|-------------------|
| `federal_action_obligation` | **Incremental** — just this modification's amount | No (not mapped) |
| `total_dollars_obligated` | **Cumulative** — running total through this mod | Yes → `total_obligation` |
| `current_total_value_of_award` | **Cumulative** — current ceiling including options | Yes → `base_and_all_options_value` |

Because we map only cumulative columns, keeping the latest modification per award (via `ROW_NUMBER() ... ORDER BY last_modified_date DESC`) is correct. No summation across modifications is needed.

Verified against real data: award `CONT_IDV_03310323D0072_0300` shows `federal_action_obligation` of $3000, -$3000, $0... while `total_dollars_obligated` stays at the running total.

### Delta vs Full file timing

The Full and Delta files for the same month are generated from the **same data snapshot**. The Feb 2026 files (`20260206`) share the same date — loading the Full files means the same-month Delta is redundant.

The Delta file contains changes since the **previous month's** archive generation. So:
- We loaded Feb 6 Full files → our DB is current as of Feb 6
- The Feb 6 Delta covers Jan→Feb changes → already included in the Feb Full files
- Our first useful Delta will be the **March** file (~Mar 15), covering Feb 6→Mar ~6 changes

### Current table sizes

| Table | Rows | Size |
|-------|------|------|
| `usaspending_award` | ~28M | 29 GB (11.5 GB data + 17.8 GB indexes) |
| `usaspending_transaction` | ~93 | On-demand API loads only |
| `fpds_contract` | ~12K | SAM.gov API loads only |

### Data loading philosophy

1. **Monthly bulk** (automated, free) — keep `usaspending_award` current via delta file
2. **On-demand per contract** (user-initiated, free) — load `usaspending_transaction` via USASpending API when user clicks "load" in UI
3. **On-demand per contract** (user-initiated, burns SAM token) — load `fpds_contract` via SAM.gov API (auto-chained from #2)

## Goals

1. **Delta loading** — add `--delta` flag to `load usaspending-bulk` to download and process the delta file instead of a Full file
2. **Delete handling** — process `correction_delete_ind = "D"` rows by deleting them from `usaspending_award`
3. **No fiscal year required** — delta file spans all FYs, so `--fy` should not be required when `--delta` is used
4. **Reuse existing pipeline** — leverage `_normalize_csv_row()`, `_upsert_from_temp()`, and checkpoint infrastructure

## Implementation Plan

### Task 1: USASpending client — delta file download

- [ ] Add `download_delta_file()` method to `usaspending_client.py`
- [ ] Current `download_archive_file()` constructs URLs for `_Full_` files with a fiscal year parameter
- [ ] Delta URL format: `https://files.usaspending.gov/generated_downloads/FY(All)_All_Contracts_Delta_<date>.zip`
- [ ] Discover available delta file via the archive API endpoint (same pattern as Full files)
- [ ] Return path to downloaded ZIP

### Task 2: Bulk loader — delta mode support

- [ ] Accept a `delta=True` parameter in `USASpendingBulkLoader`
- [ ] When in delta mode, skip the fiscal year requirement
- [ ] Add `correction_delete_ind` to the column map (or read it separately during CSV processing)
- [ ] During `_normalize_csv_row()`, preserve `correction_delete_ind` value for downstream use
- [ ] After the standard upsert pipeline runs, execute a DELETE pass for rows where `correction_delete_ind = "D"`
- [ ] DELETE query must use windowed dedup (same as upsert) to only delete awards where the LATEST modification is D-flagged:
  ```sql
  DELETE FROM usaspending_award WHERE generated_unique_award_id IN (
      SELECT generated_unique_award_id FROM (
          SELECT *, ROW_NUMBER() OVER (
              PARTITION BY generated_unique_award_id
              ORDER BY last_modified_date DESC
          ) AS rn FROM tmp_usaspending_bulk
      ) t WHERE t.rn = 1 AND t.correction_delete_ind = 'D'
  )
  ```
- [ ] In practice all 435 D rows in Feb 2026 delta had blank `contract_award_unique_key` — the delete query matches zero rows
- [ ] Log a warning for D rows with blank keys and skip them; only attempt delete for D rows with populated keys
- [ ] If future deltas provide populated keys, the windowed delete query handles them correctly
- [ ] Log delete count separately from upsert count

### Task 3: Temp table handling for deletes

- [ ] The existing `_upsert_from_temp()` uses `INSERT ... ON DUPLICATE KEY UPDATE` to merge temp into main
- [ ] For delta mode, split processing: upsert non-delete rows first, then delete "D" rows
- [ ] Option A: Filter in temp table (add WHERE clause to upsert SQL)
- [ ] Option B: Process deletes after upsert (simpler — upsert all, then delete "D" rows)
- [ ] Choose Option B for simplicity — upsert all rows first (including D-flagged), then delete
- [ ] D rows with blank award keys are skipped during upsert (no PK = can't insert) and skipped during delete (no PK = can't match)
- [ ] If future deltas provide populated keys, the windowed delete query handles them correctly

### Task 4: CLI changes

- [ ] Add `--delta` flag to `bulk_spending.py` CLI command
- [ ] When `--delta` is passed, `--fy` becomes optional (not required)
- [ ] When `--delta` is passed without `--fy`, load the delta file
- [ ] Error if both `--delta` and `--fy` are provided (they are mutually exclusive)
- [ ] Update `--help` text to explain delta vs full loading

### Task 5: Checkpoint integration

- [ ] Reuse existing `usaspending_load_checkpoint` table
- [ ] For delta loads, set `fiscal_year = 0` (or a sentinel value) since delta spans all FYs
- [ ] Set `zip_file_name` to the delta file name (includes date for uniqueness)
- [ ] Existing resume logic should work without modification — skip completed CSVs, resume partial batches

### Task 6: Logging and reporting

- [ ] Log summary at end of delta load: rows upserted, rows deleted, total time
- [ ] Log fiscal year distribution of processed rows (for operational visibility)
- [ ] Log the delta file date so operator knows how current the data is

## Alternatives Considered (Not Implementing)

### A. Bulk load all transactions into usaspending_transaction
Would give burn rate data for all ~28M awards without on-demand loading. Estimated ~35-40M rows, ~15-20 GB storage. Rejected: massive storage cost for data most users will never look at. The on-demand flow already works and is free.

### B. Keep CSVs on disk, query on demand
Options explored: SQLite files per FY, CSV with lightweight index (award_key -> file:offset). Rejected: adds complexity for marginal benefit. On-demand API loading is simpler and already implemented.

### C. Remove FPDS auto-chain from on-demand loader
Currently `_process_usaspending()` in `demand_loader.py` auto-queues an `FPDS_AWARD` request. Could make FPDS a separate UI button so user controls when SAM.gov tokens are spent. Deferred: not in scope for this phase, but noted for future consideration.

## Files to Modify

| File | Changes |
|------|---------|
| `fed_prospector/api_clients/usaspending_client.py` | Add `download_delta_file()` method |
| `fed_prospector/etl/usaspending_bulk_loader.py` | Delta mode: handle `correction_delete_ind`, delete pass, no FY requirement |
| `fed_prospector/cli/bulk_spending.py` | Add `--delta` flag, make `--fy` optional when delta is used |

## Testing

- [ ] Unit test: `_normalize_csv_row()` correctly passes through `correction_delete_ind`
- [ ] Unit test: delete query removes correct rows from temp table
- [ ] Integration test: load a small delta CSV with both upsert and delete rows
- [ ] Manual test: `python main.py load usaspending-bulk --delta` downloads and processes delta file
- [ ] Manual test: verify row counts before/after delta load (upserts increased, deletes removed)
- [ ] Manual test: verify `--delta` and `--fy` together produces an error

## Estimated Effort

- Delta download method: ~30 minutes
- Bulk loader delta mode: ~2 hours (most complexity is in delete handling and temp table logic)
- CLI changes: ~15 minutes
- Testing: ~1 hour
- **Total: ~4 hours**

## Operational Notes

- Delta file is regenerated monthly by USASpending, published by the 15th of each month
- Recommended schedule: run `--delta` monthly after the 15th when USASpending publishes new archives
- Delta loads should complete in minutes (2M rows) vs hours (35-40M rows for full reload)
- The `--fast` flag (index dropping) from Phase 65 is likely unnecessary for delta loads given the smaller row count, but remains compatible
