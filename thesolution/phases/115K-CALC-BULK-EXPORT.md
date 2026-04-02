# Phase 115K: CALC+ Bulk Export & Daily Refresh

**Status:** PLANNED
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
| Scheduler change in `etl/scheduler.py` | Trivial -- one line |
| Change detection | Medium -- optional |

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
