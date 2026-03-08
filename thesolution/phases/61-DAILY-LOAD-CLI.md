# Phase 61: Daily Load CLI Command

**Status**: IN PROGRESS
**Dependencies**: Phase 6 (Scheduler), Phase 50 (Capture Management)
**Deliverable**: `load daily` CLI command that runs a curated sequence of loads for the day
**Repository**: `fed_prospector/`

---

## Overview

Add a single `load daily` command that runs the typical daily ETL sequence in the correct order, with dependency awareness, progress reporting, and failure handling. This eliminates the need to manually invoke each loader every morning.

**User workflow this enables:**
> "I open a terminal, run `python main.py load daily`, and walk away. When I come back, all my data is fresh."

---

## Design

### Command: `load daily`

Runs a curated set of loads in dependency order. Each step is executed sequentially via `JobRunner.run_job_streaming()` so output is visible in real-time.

**Ordering principle:** Run cheapest API-call jobs first so the most data sources succeed before any single expensive job consumes the remaining daily budget. Saved searches always run last (local DB only, benefits from all prior loads being fresh).

**Default daily sequence (in order):**

| Step | Job | Why | Est. API Calls | API |
|------|-----|-----|----------------|-----|
| 1 | `opportunities` | Core data — cheapest and most critical | 5 | SAM Key 2 |
| 2 | `awards` | Enriches opportunity context | 10 | SAM Key 2 |
| 3 | `exclusions` | Compliance check — catches new exclusions | 20 | SAM Key 2 |
| 4 | `saved_searches` | Notifies users of new matches from steps 1-3 | 0 (local DB) | -- |
| **Total** | | | **~35 SAM calls** | |

Entity daily refresh and hierarchy are excluded by default (entity daily runs on its own schedule Tue-Sat; hierarchy is weekly). They can be included with `--full`.

### Options

```
python main.py load daily [OPTIONS]

Options:
  --key [1|2]       SAM.gov API key to use (default: 2)
  --full            Include entity refresh + hierarchy + subawards
  --skip TEXT       Skip specific jobs (repeatable, e.g. --skip awards --skip exclusions)
  --dry-run         Show what would run without executing
  --continue-on-failure  Continue to next job if one fails (default: stop on failure)
```

### Full sequence (`--full`)

Ordered cheapest-first so the most sources get refreshed before any single expensive job eats the budget:

| Step | Job | Est. API Calls | Cumulative |
|------|-----|----------------|------------|
| 1 | `entity_daily` | 1 | 1 |
| 2 | `opportunities` | 5 | 6 |
| 3 | `awards` | 10 | 16 |
| 4 | `exclusions` | 20 | 36 |
| 5 | `subawards` | 20 | 56 |
| 6 | `hierarchy` | 50 | 106 |
| 7 | `saved_searches` | 0 (local DB) | 106 |
| **Total** | | **~106 SAM calls** | |

### Behavior

1. Print the planned sequence with estimated API call budget
2. Check data freshness — skip jobs whose data is already fresh (e.g., opportunities loaded < 4h ago). Use `staleness_hours` from `JOBS`. Print `[SKIP - fresh]` for skipped jobs.
3. Run each job via `JobRunner.run_job_streaming()` — real-time console output
4. After each job, print a one-line summary: job name, duration, records loaded, status
5. If a job fails and `--continue-on-failure` is not set, stop and print remaining jobs that were skipped
6. At the end, print a summary table of all jobs: name, status, duration, records

### Freshness-Aware Skipping

Before running each job, query `etl_load_log` for the last successful load. If the last load was within `staleness_hours / 2` (i.e., the data is "comfortably fresh"), skip it. This prevents double-loading if the user runs `load-daily` twice in a day.

Override with `--force` to ignore freshness and run everything.

### Output Format

```
=== FedProspect Daily Load ===
  Key: 2 (1000/day limit)
  Mode: Standard (4 jobs)
  Est. API calls: ~35

  [1/4] opportunities ............ OK  (45s, 12 new, 3 updated)
  [2/4] exclusions ............... OK  (22s, 0 new, 0 updated)
  [3/4] awards ................... SKIP (fresh - loaded 2h ago)
  [4/4] saved_searches ........... OK  (8s, 3 searches run)

=== Summary ===
  Ran: 3    Skipped: 1    Failed: 0
  Total time: 1m 15s
  API calls used: ~25
```

---

## Tasks

> **Implementation approach:** shared `_run_batch()` helper in `cli/load_batch.py`, all three commands reuse it. `subawards` job added to JOBS dict in scheduler.py.

### 61.1 Add `load-daily` command
- [ ] Add `load-daily` Click command to `cli/load_batch.py`
- [ ] Options: `--key`, `--full`, `--skip`, `--dry-run`, `--continue-on-failure`, `--force`
- [ ] Define `DAILY_SEQUENCE` and `FULL_SEQUENCE` as ordered job lists
- [ ] Freshness check: query `etl_load_log` per job before running
- [ ] Real-time streaming output via `run_job_streaming()`
- [ ] Per-job timing and summary line
- [ ] Final summary table with totals
- [ ] Register commands in `main.py` load group

### 61.2 Add `load-weekly` and `load-monthly` commands
- [ ] `load weekly`: runs hierarchy + awards + exclusions + entity refresh + subawards
- [ ] `load monthly`: runs calc_rates + usaspending + everything in weekly
- [ ] Same options as `load-daily` (--key, --skip, --dry-run, --continue-on-failure, --force)
- [ ] Same output format and freshness-aware skipping

### 61.3 JobRunner enhancements
- [ ] Add `run_job_streaming()` return of records summary (parse from load output or query etl_load_log after completion)
- [ ] Add `get_freshness(job_name)` method — returns hours since last successful load and whether it's fresh

---

## Verification

- [ ] `python main.py load daily --dry-run` shows planned sequence without executing
- [ ] `python main.py load daily` runs all 4 default jobs in order with streaming output
- [ ] `python main.py load daily --full` includes entity/hierarchy/subawards
- [ ] `python main.py load daily --skip exclusions` skips exclusions
- [ ] Fresh data is auto-skipped (run twice — second run skips already-loaded jobs)
- [ ] `--force` overrides freshness check
- [ ] `--continue-on-failure` keeps going after a job failure
- [ ] Summary table shows correct stats at the end
