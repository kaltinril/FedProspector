# Phase 78: Entity CLI Consolidation

**Status**: COMPLETE
**Priority**: Medium
**Depends on**: Phase 44 (entity bulk loader), Phase 65 (bulk loader improvements)

## Problem

Under `python main.py load`, there are 3 overlapping entity commands that are confusing and partially broken:

1. **`entities`** (`load_entities` in cli/entities.py) -- Load from local file only (`--file` required)
2. **`entities-download`** (`download_extract`) -- Download monthly bulk ZIP only, no loading
3. **`entities-refresh`** (`refresh_entities`) -- Download + load. `--type=monthly` works. `--type=daily` is BROKEN -- uses paginated API at 10 records/page instead of bulk daily extract (1 API call)

This phase consolidates all 3 into a single `load entities` command with a `--type` option.

## Research Findings

### SAM.gov Entity Management API limitations (confirmed by live testing)

- **Max page size = 10 records** -- hard limit, server returns 400 error if you try higher: `"Size Cannot Exceed 10 Records"`
- **10,000 record cap** -- `page * size` cannot exceed 10,000
- **Single business type code per request** -- `businessTypeCode` and `sbaBusinessTypeCode` each accept ONE value
- **Rate limits** -- Key 1: 10/day free tier, Key 2: 1,000/day

### SAM.gov Bulk Extract API

- **Monthly extract**: `SAM_PUBLIC_MONTHLY_V2_YYYYMMDD.ZIP` -- all ~867K active entities in 1 API call. Published first Sunday of month.
- Both already implemented in `sam_extract_client.py` (`download_monthly_extract()` and `download_daily_extract()`)

### FOUO Daily Extract Finding

Daily entity bulk extracts (`SAM_FOUO_DAILY_V2_YYYYMMDD.ZIP`) are **FOUO/CUI only** -- they require a Federal System Account and are NOT available with personal API keys. Only monthly public extracts (`SAM_PUBLIC_MONTHLY_V2_YYYYMMDD.ZIP`) exist for public API key holders. The `--type=daily` option has been removed from the CLI design as a result.

### The Bug

The daily extract was never wired into the CLI. `_refresh_daily()` in entities.py calls the paginated search API instead of `download_daily_extract()`. For 10,756 entities updated on a given day, this means 1,076 API calls instead of 1.

### Last Monthly Load

March 1, 2026 file (`SAM_PUBLIC_MONTHLY_V2_20260301.dat`), loaded March 3rd -- 867,137 entities in ~4 minutes via LOAD DATA INFILE.

## Existing Code Assets

| Component | File | Status |
|-----------|------|--------|
| `download_daily_extract()` | `api_clients/sam_extract_client.py` | Implemented, never wired to CLI |
| `download_monthly_extract()` | `api_clients/sam_extract_client.py` | Implemented, used by `--type=monthly` |
| `stream_json_entities()` | `api_clients/sam_extract_client.py` | Implemented, available for daily JSON |
| `BulkLoader.bulk_load_entities()` | `etl/bulk_loader.py` | Implemented, used for monthly DAT |
| `EntityLoader.load_from_json_extract()` | `etl/entity_loader.py` | Implemented, for JSON extracts |
| `EntityLoader.load_entity_batch()` | `etl/entity_loader.py` | Implemented, for API page-by-page |
| `EntityLoader.load_from_api_response()` | `etl/entity_loader.py` | Implemented, for API response lists |
| `search_entities(**filters)` | `api_clients/sam_entity_client.py` | Implemented, accepts arbitrary SAM params |
| `iter_entity_pages_by_date()` | `api_clients/sam_entity_client.py` | Implemented, paginated by date |
| `get_entity_by_uei()` | `api_clients/sam_entity_client.py` | Implemented, single entity lookup |
| DAT parser | `etl/dat_parser.py` | Implemented, for monthly V2 DAT files |

## Design Specification

### Single command: `python main.py load entities`

**Types:**

| `--type` | What it does | API calls | When to use |
|----------|-------------|-----------|-------------|
| `monthly` | Download monthly bulk extract ZIP + LOAD DATA INFILE | 1 | Full refresh |
| `api` (default) | Paginated API query with filters | 10/page | Targeted/incremental lookups |

> **Note**: `--type=daily` was removed. Daily entity bulk extracts are FOUO/CUI only (require Federal System Account). Use `--type=api` for incremental updates between monthly loads.

`--file=X` loads from a local file (skip download), works with .dat or .json.

### Smart Defaults (zero-arg = api query)

| Option | `monthly` | `api` (default) |
|--------|-----------|-----------------|
| `--date` | -- | today |
| `--year/--month` | current | -- |
| `--key` | 1 | 1 |
| `--max-calls` | -- | 100 |
| `--status` | -- | A (active) |

### API Filters (`--type=api` only)

```
--date=2026-03-07         # updated on date (default: today)
--uei=ABC123DEF456        # specific entity
--name="Acme"             # partial name match
--naics=541512,541511     # comma-separated, splits into multiple queries
--set-aside=8W            # business type code (8W=WOSB, 8E=EDWOSB, A4=8(a))
--status=A                # A=active, E=expired (default: A)
--max-calls=100           # safety cap (default: 100)
```

If filter options are passed with `--type=monthly`, print a warning and ignore them.

Comma-separated `--naics` values are split and run as separate API queries (API only accepts one NAICS per request).

### Available API Filters Reference

From OpenAPI spec and sam_entity_client.py:

- `ueiSAM` -- 12-digit UEI, max 100 comma-separated
- `legalBusinessName` -- partial/complete match
- `registrationStatus` -- "A" (Active) or "E" (Expired)
- `updateDate` -- date or range (MM/DD/YYYY)
- `naicsCode` -- 6-digit NAICS
- `primaryNaics` -- primary NAICS only
- `businessTypeCode` -- 2-char code, SINGLE VALUE ONLY (8W=WOSB, 8E=EDWOSB, etc.)
- `sbaBusinessTypeCode` -- 2-char code, SINGLE VALUE ONLY (A4=8(a))
- `cageCode` -- 5-char CAGE
- `physicalAddressProvinceOrStateCode` -- 2-char state
- `physicalAddressCity`, `physicalAddressZipPostalCode`
- `pscCode` -- 4-char PSC code

### Help Text

```
Usage: main.py load entities [OPTIONS]

  Load SAM.gov entity data into the database.

Options:
  --type [monthly|api]        Load method (default: api)
                              monthly: Monthly full extract (1 API call)
                              api:     Targeted API query with filters
  --date TEXT                 Date (YYYY-MM-DD, default: today)
  --year INTEGER              Year for monthly extract (default: current)
  --month INTEGER             Month for monthly extract (default: current)
  --file PATH                 Load from local file (skip download)
  --key [1|2]                 SAM.gov API key (default: 1)

  API filters (--type=api only):
  --uei TEXT                  Filter by UEI (exact match)
  --name TEXT                 Filter by entity name (partial match)
  --naics TEXT                NAICS codes, comma-separated
  --set-aside TEXT            Business type code (8W=WOSB, 8E=EDWOSB, A4=8(a))
  --status [A|E]              Registration status (default: A)
  --max-calls INTEGER         Max API calls safety cap (default: 100)
  --force                     Reload even if already loaded
```

## Files to Change

| File | Change |
|------|--------|
| `fed_prospector/cli/entities.py` | Merge 3 commands into 1 unified `load_entities`. Wire `--type=api` to `search_entities()` with filter options. Delete `download_extract`, `refresh_entities`. Keep `_refresh_monthly` logic (rename). Add new `_load_via_api` with filter support. No `--type=daily` (FOUO only). |
| `fed_prospector/main.py` | Remove `entities-download` and `entities-refresh` registrations (lines 169-170). Remove imports for `download_extract`, `refresh_entities`. |
| `fed_prospector/etl/scheduler.py` (line 46) | References `entities-refresh` -- update to `entities --type=api` |
| `fed_prospector/cli/schedule_setup.py` (line 37) | References `entities-refresh` -- update to `entities --type=api` |
| `fed_prospector/tests/test_cli_load.py` | Update test references for removed commands, add tests for new unified command |

## Downstream References to Check

These files may reference the old command names in strings, comments, or docs:

- `thesolution/reference/vendor-apis/SAM-ENTITY-API.md`
- `thesolution/reference/vendor-apis/SAM-ENTITY-EXTRACTS.md`
- Any phase docs that reference `entities-refresh` or `entities-download`

## Tasks

### Task 1: Rewrite `cli/entities.py` -- unified `load_entities` command

- [x] Define new Click command with all options (type, date, year, month, file, key, uei, name, naics, set-aside, status, max-calls, force)
- [x] Implement routing: `--file` -> local file load, `--type=monthly` -> bulk monthly, `--type=api` -> filtered API query
- [x] Warn and ignore filter options when type is not `api`
- [x] Keep `search_entities` CLI command unchanged (it's under `search`, not `load`)

### Task 2: ~~Wire `--type=daily` to bulk extract~~ — REMOVED (N/A)

> **Research finding**: Daily entity bulk extracts (`SAM_FOUO_DAILY_V2_YYYYMMDD.ZIP`) are FOUO/CUI only — require a Federal System Account, NOT available with personal API keys. Only monthly public extracts exist. Use `--type=api` for incremental updates between monthly loads.

### Task 3: Wire `--type=api` with filters

- [x] Build SAM.gov query params from CLI options (uei, name, naics, set-aside, status, date)
- [x] Handle comma-separated `--naics` by splitting into multiple API queries
- [x] Handle `--set-aside` mapping to `businessTypeCode` or `sbaBusinessTypeCode` (A4 -> sbaBusinessTypeCode, others -> businessTypeCode)
- [x] Use `search_entities(**filters)` from sam_entity_client.py
- [x] Enforce `--max-calls` safety cap (default 100)
- [x] Keep resume support from existing `_refresh_daily` for partial API loads
- [x] Load results via `EntityLoader.load_from_api_response()` or `load_entity_batch()`

### Task 4: Clean up `--type=monthly` (keep existing logic)

- [x] Move `_refresh_monthly` logic into the unified command
- [x] No functional changes needed -- already works correctly

### Task 5: Clean up `--file` option (keep existing logic)

- [x] Move `load_entities` file-loading logic into unified command
- [x] Auto-detect .dat vs .json format
- [x] .dat -> BulkLoader, .json -> EntityLoader

### Task 6: Update main.py registrations

- [x] Remove `entities-download` and `entities-refresh` from `load.add_command()`
- [x] Remove imports for `download_extract`, `refresh_entities`
- [x] Keep single `load.add_command(load_entities, name="entities")`

### Task 7: Update downstream references

- [x] Update `etl/scheduler.py` -- change `entities-refresh` to `entities --type=api`
- [x] Update `cli/schedule_setup.py` -- change `entities-refresh` to `entities --type=api`
- [x] Grep for any other references to `entities-refresh` or `entities-download` in code and docs

### Task 8: Update tests

- [x] Update `tests/test_cli_load.py` for new unified command
- [x] Test `--type=monthly`, `--type=api`, `--file` paths
- [x] Test filter validation (warn on filters with non-api type)
- [x] Test comma-separated NAICS splitting

### Task 9: Delete dead code

- [x] Remove `download_extract` function from entities.py
- [x] Remove `refresh_entities` function from entities.py
- [x] Remove old `_refresh_daily` (paginated API version)
- [x] Clean up any orphaned helper functions

## Risks

1. **FOUO daily extracts**: Daily entity bulk extracts are FOUO/CUI only (require Federal System Account). We cannot use them with personal API keys. Incremental updates must use `--type=api` instead, which is slower (10 records/page) but functional. This is an inherent SAM.gov limitation.
2. **NAICS splitting**: Multiple API queries for comma-separated NAICS means multiple result sets that could have overlapping entities. Need dedup or accept minor duplicate processing.
3. **Resume support**: The existing resume-by-page logic in `_refresh_daily` is specific to the paginated API. For `--type=api` we keep it.
4. **Scheduler references**: `etl/scheduler.py` and `cli/schedule_setup.py` reference old command names -- must update or the scheduled jobs break.
5. **API budget for incremental**: Without daily bulk extracts, incremental updates via `--type=api` consume more API calls (10 records/page vs 1 call for bulk). Budget planning must account for this.

## Out of Scope

- Changes to `sam_extract_client.py` or `sam_entity_client.py` (these work fine)
- Changes to `BulkLoader` or `EntityLoader` (these work fine)
- Changes to `search entities` command (separate concern under `search` group)
- Adding new API filters beyond the agreed set (uei, name, naics, set-aside, status, date, max-calls)
