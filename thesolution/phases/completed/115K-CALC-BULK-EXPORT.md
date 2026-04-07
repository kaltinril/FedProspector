# Phase 115K: CALC+ Bulk Export & Daily Refresh

**Status:** COMPLETE
**Priority:** HIGH -- simple change, big data coverage improvement
**Dependencies:** Phase 115B (normalization chain already hooked into load-calc CLI)

---

## Summary

GSA decommissioned the legacy CALC Rates API in February 2025 and replaced it with a modernized version powered by AWS OpenSearch. The new DX CALC+ Quick Rate API (docs: https://open.gsa.gov/api/dx-calc-api/) is at the same base URL we already use (`https://api.gsa.gov/acquisition/calc/v3/api/ceilingrates/`) but now supports:

- **Proper pagination**: `page=` and `page_size=` parameters
- **Bulk CSV export**: Append `&export=y` to any API call to download the full dataset as CSV
- **Daily refresh**: GSA refreshes the data "everyday overnight"

---

## Current State

- Multi-sort Elasticsearch hack in `calc_client.py`: 18 queries with different sort orderings, each getting 10K results, de-duplicated by ES `_id`
- Gets ~124K of ~258K total records (missing ~134K records stuck in the middle of sort orders)
- Runs monthly via Windows Task Scheduler (scheduler.py: `calc_rates`, schedule `1st of month 04:00`, staleness 45 days)
- Takes ~60 seconds
- Post-load chain from 115B: normalize labor categories -> refresh summary table

## Problems with Current Approach

1. Missing ~52% of the data (124K out of 258K)
2. Complex multi-sort logic in `get_all_rates()` that is fragile if ES behavior changes
3. Monthly schedule misses daily updates from GSA
4. 18 API calls when 1 would suffice

---

## Feature 1: Switch to CSV Bulk Export

Replace the multi-sort client with a single `&export=y` CSV download.

### Changes to `calc_client.py`

- Add `download_full_csv(self, output_path: Path) -> Path` method
- Single GET request: `GET /ceilingrates/?format=csv&export=y`
- Saves CSV to temp file, returns path
- No pagination needed -- GSA returns the full dataset
- Keep the existing `search_rates_all()` method for on-demand queries (still useful)
- Deprecate `get_all_rates()` (the multi-sort method)

### Changes to `calc_loader.py`

- Add `full_refresh_csv(self, client, load_manager=None)` method
- Must mirror `full_refresh()`'s load management pattern for ETL audit log: call `lm.start_load()` with `parameters={"method": "csv_bulk_export"}`, `lm.complete_load()` on success, `lm.fail_load()` on error
- Use existing `load_from_csv()` path which already does LOAD DATA INFILE
- Full refresh pattern: TRUNCATE -> `download_full_csv()` -> `load_from_csv()`
- Expected: ~258K rows in a single bulk load

### Changes to `cli/calc.py`

- Update `load_calc()` to use CSV export by default
- Add `--legacy` flag to fall back to the multi-sort API method
- Post-load normalization chain (normalize -> refresh summary) already in place from 115B

---

## Feature 2: Daily Schedule

### Changes to `etl/scheduler.py`

- Change `calc_rates` job from `schedule: "1st of month 04:00"` to `schedule: "daily 04:00"`
- Reduce `staleness_hours` from 1080 (45 days) to 36 (1.5 days)
- Also reduce `daily_freshness_hours` from 504 (21 days) to ~48 (2 days) -- both keys need updating
- GSA refreshes overnight, so 4:00 AM local time catches the latest data

### Update Windows Task Scheduler command

```
schtasks /change /tn "FedContract_CalcRates" /sc DAILY /st 04:00
```

---

## Feature 3: Change Detection (Optional Optimization)

Since we are going daily, we could add change detection to avoid full TRUNCATE + reload every day when most data has not changed.

- Compare downloaded CSV row count to current `gsa_labor_rate` count
- If counts match and a sample of record hashes match, skip the load
- If counts differ or hashes differ, do the full refresh
- Log the decision either way for audit trail

This is optional -- the full reload only takes ~60 seconds even with normalization, so the overhead is minimal. But it would reduce unnecessary normalization + summary refreshes on days when nothing changed.

---

## Implementation Estimate

| Item | Effort |
|------|--------|
| CSV download method in `calc_client.py` | Small -- single HTTP GET + file write |
| `full_refresh_csv()` in `calc_loader.py` | Small -- orchestrates existing `load_from_csv()` |
| CLI updates in `cli/calc.py` | Trivial -- swap client call, add `--legacy` flag |
| Scheduler change in `etl/scheduler.py` | Trivial -- two config keys |
| Change detection | Medium -- optional |

**Important**: CSV column headers from the bulk export will likely differ from the JSON API field names used in `_API_FIELD_MAP` and `_normalize_rate()`. Either add a separate `_CSV_FIELD_MAP` for column name translation or verify that CSV headers match the existing mapping before loading. Do not assume they are identical.

---

## Data Impact

| Metric | Before | After |
|--------|--------|-------|
| Records loaded | ~124K | ~258K |
| Data coverage | ~48% | ~100% |
| API calls per load | 18 | 1 |
| Load frequency | Monthly | Daily |
| Load time | ~60s | TBD (likely faster -- single CSV vs 18 API calls) |
| Normalization coverage | Partial (only mapped categories from 124K subset) | Full (all categories from complete dataset) |

---

## Risks

- CSV export format may differ from API JSON field names -- need to map column headers during implementation
- CSV export may be rate-limited or have a file size cap (unknown, needs testing)
- Daily loads increase DB write volume -- monitor InnoDB buffer pool usage
- More records means more unmapped categories for the normalizer -- may need to expand canonical categories in `labor_category_mapping`

---

## Testing

1. Download CSV manually: `curl "https://api.gsa.gov/acquisition/calc/v3/api/ceilingrates/?format=csv&export=y" -o calc_export.csv`
2. Check row count vs current ~124K in `gsa_labor_rate`
3. Compare CSV column headers to existing `_API_FIELD_MAP` in `calc_loader.py`
4. Test LOAD DATA INFILE with the CSV (existing `load_from_csv()` path)
5. Verify normalization still works on the larger dataset
6. Verify `--legacy` flag still works with the multi-sort method

---

## Files Modified

| File | Change |
|------|--------|
| `fed_prospector/api_clients/calc_client.py` | Add `download_full_csv()` method |
| `fed_prospector/etl/calc_loader.py` | Add `full_refresh_csv()` orchestration method |
| `fed_prospector/cli/calc.py` | Default to CSV export, add `--legacy` flag |
| `fed_prospector/etl/scheduler.py` | Change `calc_rates` to daily schedule |

---

### Post-Migration: Re-evaluate Canonical Labor Categories

After 115K is complete and we're loading the full ~258K CALC+ dataset (up from ~124K), re-run the canonical labor category analysis:

1. **Repeat gap analysis** — With ~134K additional records, new high-frequency labor categories will appear that aren't in our canonical list. Run the unmapped-by-frequency query against the larger dataset.
2. **Update canonical_labor_categories.csv** — Add any new high-frequency categories discovered.
3. **Re-tune fuzzy matching** — The larger dataset may shift optimal thresholds or reveal new abbreviation patterns.
4. **Measure coverage improvement** — Compare mapping rates (currently ~20% on 124K rows) against the full 258K dataset.
5. **Re-assess summary table performance** — With 2x the source data, re-benchmark the live aggregation query vs the pre-computed summary table to confirm whether `labor_rate_summary` is still worth maintaining.

This is a follow-up task, not a blocker for the 115K migration itself.

---

## Research & Implementation Findings (2026-04-06)

### Problem Statement

The original multi-sort API strategy (`get_all_rates()`) only retrieves ~124K of ~260K records
(48% coverage) due to the Elasticsearch `max_result_window=10000` limit. Each of 18 sorted
queries returns at most 10K records from the extremes of each sort order; the middle of each
distribution is unreachable. Phase 115K aimed to find a way to get full coverage.

### Approaches Tested

#### 1. Single CSV Bulk Export — FAILED
- **Tried:** `?format=csv&export=y` as documented in old CALC API docs
- **Result:** 404 error. `format=csv` is not a valid parameter in the DX CALC+ API (migrated to OpenSearch Feb 2025).
- **Also tried:** `?export=y` without keyword → returns JSON (20 records), not CSV
- **Conclusion:** There is no single-URL full dataset download

#### 2. Simple JSON Pagination — BLOCKED BY ES LIMIT
- **Tried:** Paginating with `page` and `page_size` parameters
- **Result:** `page * page_size > 10000` returns HTTP 500. Confirmed at page=201, page_size=50.
- **Also tried:** `search_after` query parameter (ES deep pagination) → silently ignored, returns same results
- **Conclusion:** JSON pagination is hard-capped at 10,000 records per sort order

#### 3. API Key Authentication — NOT APPLICABLE
- **Tried:** SAM.gov API keys with various endpoints
- **Result:** HTTP 403. CALC+ does not accept SAM.gov API keys — the API is fully public with no auth.
- **Conclusion:** No auth tier unlocks additional capabilities

#### 4. Keyword CSV Export — WORKS
- **Discovery:** `?keyword=X&export=y` returns ALL matching records as CSV, bypassing the 10K window
- **Key insight:** The keyword search is full-text across `labor_category` (and partially vendor_name, contract#)
- **`wage_stats.count`** in the aggregations response gives the TRUE filtered count (unlike `hits.total` which caps at 10K with `relation: "gte"`)
- **Single-char keywords** (a, e, i, o, u) return empty CSV (29 bytes) — minimum 2 characters required

#### 5. Keyword Strategy Optimization

**Phase A — Job Title Keywords (94 API calls → 96.6%)**
Tested 94 common job-title words (engineer, analyst, manager, specialist, etc.). Coverage
plateaued at 96.6% with diminishing returns after ~30 keywords. Many keywords overlapped
heavily (e.g., "senior" records already captured by "engineer").

**Phase B — Two-Letter Bigrams (8 API calls → 99.8%)**
Key insight: every English word contains common letter pairs. Two-letter substrings like "in",
"er", "te" appear in virtually every labor category name.

| Bigrams Added | Cumulative Coverage | API Calls |
|---------------|-------------------|-----------|
| `in` | 75.2% (195K) | 1 |
| `er` | 91.1% (237K) | 2 |
| `te` | 95.3% (248K) | 3 |
| `on` | 98.0% (255K) | 4 |
| `an` | 99.1% (258K) | 5 |
| `al` | 99.5% (259K) | 6 |
| `ti` | 99.7% (259K) | 7 |
| `or` | 99.8% (259K) | 8 |

**The remaining 0.2% (~230 records):** Contain special Unicode characters in the `labor_category`
field that the CALC+ search engine doesn't index:
- En-dash `–` (U+2013): "Cyber Data Scientist – Senior"
- Non-breaking space `\xa0`: "Advanced\xa0Technology\xa0Project\xa0Manager"
- Accented chars: "Protégé" in mentor-protégé entries
- Smart quotes and other typographic characters

These records ARE returned by the multi-sort JSON approach, which doesn't rely on keyword matching.
However, 99.8% coverage was deemed sufficient — the 230 missing records are data entry anomalies.

### CSV Format Details

**Preamble (must be skipped):**
```
SEARCH VALUES
keyword
<the_keyword>

Contract #,Labor Category,...data rows...
```

**CSV Headers (human-readable, NOT matching JSON field names):**
`Contract #, Labor Category, Business Size, Schedule, Site, Security Clearance, Category,
Subcategory, Begin Date, End Date, SIN, Vendor Name, Education Level,
Minimum Years Experience, Current Year Labor Price, Next Year Labor Price,
Second Year Labor Price`

**No ID column** — the CSV export does not include the Elasticsearch `_id` field.

### Unique Key Analysis

With 259,607 rows loaded into a staging table, tested composite key uniqueness:

| Composite Key | Dupe Groups |
|---------------|------------|
| contract + labor_cat + vendor | 40,625 |
| + sin + education + experience + site | 2,404 |
| + current_price | 77 |
| + all 3 prices | 76 |

The 2,404 dupe groups (without price) are the same labor category offered at different price
points under the same contract — likely different option year tiers. The final 76 are true
duplicates in GSA's data (identical across all 17 columns, confirmed via JSON `_id` — each has
a unique ES document ID but identical field values).

**Decision:** No unique key needed. Since we do a full TRUNCATE + reload monthly via the bigram
sweep, deduplication happens in memory before INSERT. No upsert, no `es_id` column required.

### Data Quality Notes

- **Max `labor_category` length:** 1,899 chars (one vendor, HARRIS GRANT LLC, pasted full job
  descriptions with bullet points instead of titles — 6 records total)
- **Length distribution:** 96.8% ≤50 chars, 99.98% ≤200 chars
- **Total dataset:** 259,837 records (from `aggregations.wage_stats.count`)
- **Business size values:** `small business`, `other than small business`
- **Site values:** `Contractor_Facility`, `Customer Facility`, `Both` (inconsistent underscores)

### Why Monthly, Not Daily

1. GSA CALC+ data updates infrequently — contract ceiling rates change on option year exercises
   or contract modifications, not daily
2. The 8-bigram sweep takes ~2 minutes and downloads ~90MB of CSV data
3. Post-load normalization (labor category mapping + summary refresh) adds ~60 seconds
4. Daily reload provides no meaningful freshness benefit for ceiling rate data
5. The staleness check (`LoadManager.get_last_load`) prevents redundant reloads

### Final Implementation

1. **Client:** `CalcPlusClient.download_bigram_csvs()` — 8 keyword CSV exports, streamed to temp files
2. **Loader:** `CalcLoader.full_refresh_csv()` — parse CSVs (skip preamble), dedup in memory, write combined file, TRUNCATE + LOAD DATA INFILE
3. **CLI:** `load-calc` defaults to bigram CSV with 30-day staleness check. `--force` bypasses check. `--legacy` uses old multi-sort.
4. **Scheduler:** Monthly at 04:00, `staleness_hours: 744` (31 days)
5. **Batch:** `calc_rates` in `MONTHLY_SEQUENCE`, not daily
6. **Post-load:** `LaborNormalizer.normalize()` + `refresh_summary()` runs automatically after load

### API Reference (corrected from original docs)

| Parameter | Behavior |
|-----------|----------|
| `keyword=X` | Full-text search on labor_category (and partially other fields) |
| `export=y` | With keyword: returns full CSV of all matches (no 10K cap). Without keyword: returns JSON (20 records) |
| `format=csv` | **Invalid** — returns 404 |
| `page_size` | Max effective value depends on context; `page * page_size > 10000` → 500 error |
| `search_after` | **Silently ignored** as query parameter |
| `ordering` / `sort` | Sort field and direction for JSON results |
| API key | **Not accepted** — SAM.gov keys return 403. API is fully public |
| Rate limits | None observed. `max_daily_requests` set to 999999 |
| `hits.total` | Caps at 10,000 with `relation: "gte"`. Use `aggregations.wage_stats.count` for true count |
| Total records | 259,837 (as of 2026-04-06) |
