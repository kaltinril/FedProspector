# Phase 90 — Smart Daily Load (Watermark Resume System)

**Status**: COMPLETE
**Priority**: HIGH
**Depends on**: None (Phase 89 can proceed in parallel)

---

## Context

The daily load system (`python main.py load daily`) has four problems:

1. **Awards always queries 3 years back** — wasteful for daily runs; should only fetch since last successful load
2. **Awards doesn't resume** — if a run exhausts its API budget mid-way, the next run starts over from page 0 instead of picking up where it left off (opportunities and subawards already do this correctly)
3. **Awards scheduler command is broken** — `load awards --key 2` has no filters and errors with "At least one filter required"
4. **Exclusions bulk load is impractical** — 10 records/page, no date filter, 167K records = not viable for daily batch; should be on-demand only

Additionally, the `--dry-run` output doesn't show what parameters (date range, filters) each job would use.

**The fix:** make loaders behave like a worker with an 8-hour shift — save your progress, come back tomorrow and finish what's left.

---

## Target Data

- **24 NAICS codes**: 336611, 488190, 519210, 541219, 541330, 541511, 541512, 541513, 541519, 541611, 541612, 541613, 541690, 541990, 561110, 561210, 561510, 561990, 611430, 611710, 621111, 621399, 624190, 812910
- **3 set-aside types**: 8(a), WOSB, SBA
- **= 72 (NAICS x set-aside) combinations** to iterate through with resume tracking

---

## Existing Patterns to Reuse

| Pattern | Source File | Lines |
|---------|------------|-------|
| Resume lookup (query etl_load_log for partial loads) | `cli/opportunities.py` | 131-183 |
| Multi-iterator tracking (completed_set_asides) | `cli/opportunities.py` | 366-435 |
| Page-by-page checkpoint (save_load_progress per page) | `etl/load_manager.py` | 80-112 |
| Nested resume (PIID index + page) | `cli/subaward.py` | 155-188 |
| Batch loader method (caller manages lifecycle) | `etl/awards_loader.py` | 97-116 |

---

## Items to Address

### HIGH PRIORITY

**P90-1 — LoadManager: Add `get_resumable_load()` + `get_watermark()` helpers**
File: `fed_prospector/etl/load_manager.py`

Current awards `parameters` JSON (pre-Phase 90):
```json
{"naics": "541511,...", "set_aside": "SBA", "date_from": "2021-03-10",
 "date_to": "2026-03-09", "calls_made": 217, "total_fetched": 21700}
```
**No `complete` field exists yet.** Phase 90 adds it.

`get_resumable_load(source_system)` — find an incomplete load to resume:
```sql
SELECT * FROM etl_load_log
WHERE source_system = %s AND status = 'SUCCESS'
  AND JSON_EXTRACT(parameters, '$.complete') = false
ORDER BY started_at DESC LIMIT 1
```
- Returns `(row_dict, parsed_parameters)` or `(None, None)`
- Old loads (no `complete` field) → `JSON_EXTRACT` returns NULL → `= false` doesn't match → correctly ignored
- Only Phase 90+ loads with explicit `"complete": false` are resumable

**Stale RUNNING cleanup:** If a process is killed before the first `save_load_progress()`, the load stays RUNNING forever (invisible to both resume and watermark queries). Add a guard: before starting a new load, check for any `status = 'RUNNING' AND started_at < NOW() - INTERVAL 2 HOUR` rows for the same source_system and mark them FAILED. This is a pre-existing issue (not Phase 90-specific) but Phase 90 should fix it.

`get_watermark(source_system, date_key="date_to")` — find last completed load's date value:
```sql
SELECT parameters FROM etl_load_log
WHERE source_system = %s AND status = 'SUCCESS'
  AND (JSON_EXTRACT(parameters, '$.complete') = true
       OR JSON_EXTRACT(parameters, '$.complete') IS NULL)
ORDER BY started_at DESC LIMIT 1
```
- Old loads (no `complete` field) → NULL IS NULL → treated as completed → watermark works
- Extracts the value of `date_key` from the matched row's `parameters` JSON (e.g., `parameters[date_key]`)
- Different source systems use different date keys: awards uses `date_to`, opportunities uses `posted_to`
- Returns the parsed date string or None
- First Phase 90 run picks up from existing watermark `date_to = 2026-03-09`

---

**P90-2 — Awards CLI: Watermark + resume + nested (NAICS x set-aside) iterator**
File: `fed_prospector/cli/awards.py`

**2a. Watermark-based date range** (replace `--years-back 3` default)
- When no explicit `--years-back` or `--fiscal-year` is given, auto-detect:
  - Call `get_watermark("SAM_AWARDS")` to get last completed load's `date_to`
  - Set `date_from = previous date_to`, `date_to = today`
  - If no previous load exists, fall back to `--years-back 1`
- If watermark `date_to` equals today (no new window to query), skip awards with a message: `"Awards data is current (last load: today). Skipping."` — avoids wasting API calls on a zero-width date range.
- Keep `--years-back` and `--fiscal-year` as explicit overrides

**2b. Default NAICS + set-aside for scheduler**
- When no `--naics` and no `--set-aside` specified, use `DEFAULT_AWARDS_NAICS` and `DEFAULT_AWARDS_SET_ASIDES` from settings
- This fixes the broken scheduler command (currently errors with "At least one filter required")
- The `--set-aside` CLI option currently accepts a single value. When no `--set-aside` is specified, use the `DEFAULT_AWARDS_SET_ASIDES` list and iterate over all values. When user passes `--set-aside WOSB`, iterate only that one value (no multi-set-aside loop needed).

**2c. Nested (NAICS x set-aside) iteration with resume tracking**
- Outer loop: set-aside types (8A, WOSB, SBA)
- Inner loop: NAICS codes within each set-aside
- Innermost: page pagination within each (NAICS, set-aside) pair
- Parameters saved after each page via `save_load_progress()`:
  ```json
  {
    "naics": "541512,541511,...",
    "set_aside": "8A,WOSB,SBA",
    "date_from": "2026-03-09",
    "date_to": "2026-03-11",
    "completed_combos": [["541512", "8A"], ["541511", "8A"]],
    "current_set_aside": "8A",
    "current_naics": "541513",
    "current_page": 2,
    "complete": false,
    "calls_made": 47,
    "total_fetched": 4700
  }
  ```
- **Format convention:** `naics` and `set_aside` stay as comma-separated strings (matching existing awards/opportunities parameter format). The CLI receives strings; store them as-is. Split to lists in code only when iterating.

**Completion signal:** When all combos are done, set `params_dict["complete"] = True` and call `save_load_progress()` — do NOT use `complete_load()`. The current `complete_load()` at `awards.py` line 202 does not write parameters, so `complete=true` would never be persisted. Replace it with a final `save_load_progress()` call, matching the opportunities pattern (`cli/opportunities.py` lines 432-434).

> **Note:** This changes the current loop order. Currently `awards.py` iterates NAICS codes in the outer loop with no set-aside iteration. Phase 90 adds set-aside as the outer loop and NAICS as the inner loop, which is a structural rewrite of lines 121-190 in `awards.py`.

**Zero-result combos:** If a NAICS+set-aside pair returns 0 records, the current `save_load_progress()` call won't fire (it's inside `if records:` at `awards.py` line 153). The new nested iterator must add zero-result combos to `completed_combos` explicitly — otherwise they'd be retried on every resume. After the inner pagination loop exits with no results, append the combo and save progress.

**2d. Resume from partial load**
- Before starting, call `get_resumable_load("SAM_AWARDS")`
- If found with matching date range + filter set:
  - Create a **new** `load_id` for each run (matches the opportunities pattern at `cli/opportunities.py` line 252)
  - Read resume state (`completed_combos`, current position) from the previous load's parameters
  - This preserves audit trail — each invocation is a separate log entry
  - Skip combos in `completed_combos`
  - Start from `current_set_aside` / `current_naics` / `current_page`
- If not found or filters differ, start fresh

**2e. Add `--force` flag** to skip resume and start fresh

**2f. Dynamic `load_type`** — set `load_type = "INCREMENTAL"` when using watermark-based dates, `"HISTORICAL"` when user passes explicit `--years-back` or `--fiscal-year`. Currently hardcoded as `"HISTORICAL"` at `awards.py` line 102.

**2g. Add `--dry-run` flag to `load-awards`** — prints watermark date range, NAICS x set-aside matrix, resume state (if any), and estimated API calls, then exits. Required by verification checklist item 1.

**2h. Error handling**
- **Rate limit / KeyboardInterrupt:** Progress is already checkpointed via `save_load_progress()`. The current load has `status = 'SUCCESS'` and `complete = false`. Next run finds it via `get_resumable_load()` and creates a new load_id to continue.
- **Fatal exception:** Call `fail_load()` on the current load_id. The previous resumable load (if any) retains its `SUCCESS` status and remains findable for resume.
- **Budget exhaustion (`--max-calls` reached):** Same as rate limit — progress is saved, `complete` stays `false`. This is the primary expected reason for partial loads (72 combos across a 1,000/day shared budget).

---

**P90-3 — Exclusions: Remove from daily batch, on-demand only**
Files: `fed_prospector/cli/load_batch.py`, `fed_prospector/etl/scheduler.py`

Exclusions = federal blacklist of vendors barred from contracting. Used for due diligence on teaming partners, not daily prospecting.

- Remove `exclusions` from `DAILY_SEQUENCE` and `FULL_SEQUENCE` in `load_batch.py`
- Also remove `exclusions` from `MONTHLY_SEQUENCE` (line 24 in `load_batch.py`). Exclusions stays only in `WEEKLY_SEQUENCE` for budget-limited sweeps.
- Keep `exclusions` in `WEEKLY_SEQUENCE` (budget-limited sweep, nice to have)
- Existing `check-exclusion --uei` and `check-prospects` commands handle on-demand checks against local data
- No code changes to the exclusions loader — it works fine for manual/weekly use

---

### MEDIUM PRIORITY

**P90-4 — Config: Default NAICS + set-asides**
File: `fed_prospector/config/settings.py`

```python
DEFAULT_AWARDS_NAICS = os.getenv(
    "DEFAULT_AWARDS_NAICS",
    "336611,488190,519210,541219,541330,541511,541512,541513,541519,"
    "541611,541612,541613,541690,541990,561110,561210,561510,561990,"
    "611430,611710,621111,621399,624190,812910"
)
DEFAULT_AWARDS_SET_ASIDES = os.getenv("DEFAULT_AWARDS_SET_ASIDES", "8A,WOSB,SBA")
```

---

**P90-5 — Scheduler: Update awards command and estimates**
File: `fed_prospector/etl/scheduler.py`

- Awards command stays as `["python", "main.py", "load", "awards", "--key", "2"]` — watermark + default NAICS/set-asides are now automatic
- Update `estimated_api_calls` from 10 to reflect 72 combinations (though budget-limited per run)

---

**P90-6 — Dry-run parameter preview**
File: `fed_prospector/cli/load_batch.py`

In the dry-run path, after freshness status, show key parameters:
- Awards: `watermark: 2026-03-09 -> today | 24 NAICS x 3 set-asides | resume: 541513/8A page 2`
- Helper function queries etl_load_log for watermark/resume state

---

## API Gotchas to Handle

1. **Awards API uses PAGE INDEX pagination** (offset = page number, not record offset) — different from Opportunities API
2. **`totalRecords` returned as STRING** — must `int()` parse
3. **Date format is `[MM/DD/YYYY,MM/DD/YYYY]`** — not ISO 8601
4. **Only ONE set-aside per request** — can't pass multiple; must loop through each
5. **Offset-shifting risk** — new records can shift page offsets between runs; mitigated by watermark (fresh date window each run)
6. **Shared 1,000/day rate limit** across ALL SAM APIs — budget must account for opportunities, entities, hierarchy too

---

## Backward Compatibility

No parameter format migration needed — Phase 90 keeps the same `naics` and `set_aside` key names as comma-separated strings. New fields (`completed_combos`, `current_*`, `complete`) are additive:
- `get_resumable_load()` only matches loads with `$.complete = false` — old loads don't have this field, so they're never matched for resume.
- `get_watermark()` matches old loads (no `$.complete` field → NULL IS NULL → matched). It reads `date_to`, which exists in both old and new formats.

---

## Risks and Mitigation

| Risk | Mitigation |
|------|-----------|
| 72 combinations is a lot — may take multiple days | Resume system handles this naturally; each run progresses further |
| Deduplication across set-asides (same award in WOSB + SBA) | SHA-256 change detection counts these as `records_unchanged` |
| First run with no watermark falls back to 1 year | Can use `--years-back N` for explicit initial backfill |
| Multiple simultaneous loads could conflict | Known limitation (opportunities has same issue); document as single-instance |
| `save_load_progress()` sets status to SUCCESS for partial loads | By design — the `$.complete` JSON field is the true completion indicator, not the status column. Document this clearly in code comments. |
| Loop order change (NAICS outer → set-aside outer) | Structural rewrite of awards.py lines 121-190. Test thoroughly with `--max-calls` to verify checkpoint/resume across the new loop structure. |
| `--set-aside` currently single-value | Default multi-value handled internally; explicit `--set-aside X` overrides to single value. No CLI signature change needed. |
| Stale RUNNING loads from crashed processes | Pre-load cleanup marks RUNNING loads older than 2 hours as FAILED. Prevents invisible orphan rows. |
| Zero-result NAICS+set-aside combos | Explicitly add to `completed_combos` after pagination loop exits with no results. Prevents infinite retries. |
| Watermark date_to == today | Skip awards load with informational message. No API calls wasted. |

---

## Files Modified

| File | Change |
|------|--------|
| `fed_prospector/etl/load_manager.py` | Add `get_resumable_load()` + `get_watermark()` |
| `fed_prospector/cli/awards.py` | Watermark, resume, nested iterator, default filters, `--force`, `--dry-run` flag, dynamic `load_type`, loop order restructure |
| `fed_prospector/config/settings.py` | Add `DEFAULT_AWARDS_NAICS`, `DEFAULT_AWARDS_SET_ASIDES` |
| `fed_prospector/cli/load_batch.py` | Remove exclusions from daily/monthly, add dry-run parameter preview |
| `fed_prospector/etl/scheduler.py` | Update estimated_api_calls for awards |

---

## Verification Checklist

- [x] `python main.py load awards --dry-run` shows watermark date range, NAICS x set-aside matrix, resume state
- [x] `python main.py load awards --max-calls 5` partial run saves progress with combo tracking in etl_load_log
- [x] `python main.py load awards` re-run resumes from saved combo/page
- [x] `python main.py load awards --force` starts fresh ignoring resume state
- [x] `python main.py load daily --dry-run` excludes exclusions, awards shows parameters
- [x] `python main.py load daily` full daily run with watermark + resume working
- [x] `etl_load_log.parameters` JSON contains correct `complete`, `completed_combos`, `current_*` fields
- [x] First run with no prior watermark falls back to 1-year lookback
- [x] `python main.py load awards --years-back 2` overrides watermark correctly
- [x] `python main.py load awards --fiscal-year 2025` overrides watermark correctly
- [x] When last load's `date_to` is today, awards is skipped with "data is current" message
- [x] Zero-result NAICS+set-aside combos are added to `completed_combos` and not retried
- [x] Stale RUNNING loads older than 2 hours are cleaned up on next run
