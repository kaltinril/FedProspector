# Phase 97: USASpending Bulk — `--check-available` Option

## Status: PLANNED

## Problem
There is no way to check whether new USASpending bulk archive or delta files are available before committing to a download+load. The `list_archive_files()` API method exists on `USASpendingClient` but is not exposed through the CLI. Users must either run the full load blindly or drop into a Python one-liner to query the archive listing API.

This makes it hard to answer: "Is there a new monthly delta I should load?" or "When was the FY2026 full archive last updated?"

## Goal
Add a `--check-available` flag to the `usaspending-bulk` CLI command that queries the USASpending archive listing API and prints what files are available — without downloading or loading anything.

## Files to Change

| File | Change |
|------|--------|
| `fed_prospector/cli/bulk_spending.py` | Add `--check-available` flag, implement `_check_available()` helper |
| `fed_prospector/api_clients/usaspending_client.py` | No changes expected — `list_archive_files()` already exists |

## Tasks

### Task 1: Add `--check-available` CLI flag
**File:** `fed_prospector/cli/bulk_spending.py`

- Add `@click.option("--check-available", is_flag=True, ...)` to the `usaspending_bulk` command
- When `--check-available` is passed, call `_check_available()` and return (no download, no load)
- Mutually exclusive with `--delta`, `--skip-download`, `--fast` (those imply a load)

### Task 2: Implement `_check_available()` helper
**File:** `fed_prospector/cli/bulk_spending.py`

Create a `_check_available(fiscal_year, years_back)` function that:

1. Instantiates `USASpendingClient`
2. Calls `client.list_archive_files(fy)` for each fiscal year in scope
3. Prints a table with columns:
   - **File Name** — e.g., `FY2026P06_All_Contracts_Full_20260315.zip`
   - **Type** — `Full` or `Delta` (parsed from `_Full_` / `_Delta_` in filename)
   - **Updated** — `updated_date` from the API response
   - **Size** — file size if available in the response, otherwise `—`
4. Highlights delta files distinctly (e.g., prefix with `[DELTA]`)
5. Compares against local DB: query `etl_load_log` for the most recent `USASPENDING_BULK` load of each type (`FULL` / `DELTA`) and show whether the available file is newer than what was last loaded

### Task 3: Show local load status
In the `_check_available()` output, after the available-files table, print a "Last loaded" summary:

```
Last loaded:
  Full  FY2026: 2026-02-15 (load #1234, 1,245,678 records)
  Delta:        2026-03-01 (load #1250, 12,345 records)
```

Query `etl_load_log` where `source_system = 'USASPENDING_BULK'` and `status = 'COMPLETE'`, grouped by `load_type`.

### Task 4: Tests
**File:** `fed_prospector/tests/test_bulk_spending_cli.py` (new) or add to existing test file

- Test that `--check-available` calls `list_archive_files` and does NOT instantiate `USASpendingBulkLoader`
- Test output formatting with mock API responses (full + delta files)
- Test mutual exclusivity with `--fast`, `--skip-download`

## Example Usage

```bash
# Check all FYs (default: last 5)
python main.py load usaspending-bulk --check-available

# Check a specific FY
python main.py load usaspending-bulk --check-available --fiscal-year 2026

# Check last 2 FYs
python main.py load usaspending-bulk --check-available --years-back 2
```

## Expected Output

```
USASpending Archive Availability (Contracts)

FY2026:
  File Name                                       Type    Updated       Size
  FY2026P06_All_Contracts_Full_20260315.zip       Full    2026-03-15    2.1 GB
  FY2026P06_All_Contracts_Delta_20260315.zip      Delta   2026-03-15    145 MB

FY2025:
  FY2025P12_All_Contracts_Full_20251215.zip       Full    2025-12-15    4.3 GB

Last loaded:
  Full  FY2026: 2026-02-15 (load #1234, 1,245,678 records)
  Full  FY2025: 2025-11-01 (load #1180, 3,890,123 records)
  Delta:        2026-03-01 (load #1250, 12,345 records)

  → New delta available (2026-03-15) since last load (2026-03-01)
  → New FY2026 full archive available (2026-03-15) since last load (2026-02-15)
```

## Notes
- No API rate limits — USASpending has no daily quotas, so `--check-available` is safe to run anytime
- The archive listing endpoint is already used internally by `download_archive_file()` and `download_delta_file()` — this just exposes it to the user
- File size may not be in the API response — check the actual response shape and show `—` if absent
