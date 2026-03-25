# Phase 110X: Scheduled & Automated Analysis

**Status:** COMPLETE
**Priority:** Medium — daily loads currently skip AI analysis and backfill
**Dependencies:** Phase 110C (AI analyzer — complete), Phase 110H (backfill ranking — complete)

---

## Summary

Integrate the attachment intelligence pipeline (AI analysis, backfill, cleanup) into the existing daily load automation. Currently `daily_load.bat` runs keyword extraction but skips AI analysis and the new per-field backfill. The scheduler's JOBS dict also lacks attachment pipeline entries.

This is NOT a new scheduling system — the infrastructure already exists (scheduler.py, load_batch.py, schedule_setup.py, daily_load.bat). This phase just adds the missing pipeline stages.

---

## Current State

`daily_load.bat` runs 10 steps but is missing:
- `extract attachment-ai` (AI analysis of downloaded docs)
- `backfill opportunity-intel` (per-field frequency-weighted backfill from 110H)
- Attachment cleanup runs but BEFORE AI analysis — should run AFTER

`etl/scheduler.py` JOBS dict has 11 jobs but none for attachment pipeline stages.

`cli/load_batch.py` `load daily` includes opportunities/awards/searches/prospects but no attachment stages.

---

## Tasks

### Task 1: Add attachment pipeline jobs to scheduler.py JOBS dict
- Add `attachment_ai` job: `extract attachment-ai --model haiku --batch-size 50`
- Add `intel_backfill` job: `backfill opportunity-intel`
- Add `attachment_cleanup` job: `cleanup attachment-files`
- Set appropriate staleness thresholds, priorities, and estimated API calls
- Note: download, text extraction, and keyword extraction are already in daily_load.bat — they don't need scheduler jobs since they run as part of the daily sequence

### Task 2: Update daily_load.bat with correct pipeline ordering
Current order ends with: `[9] extract attachment-intel` → `[10] cleanup attachment-files`

New order should be:
```
[9]  extract attachment-intel       (keyword extraction — existing)
[10] extract attachment-ai          (AI analysis — NEW)
[11] backfill opportunity-intel     (per-field backfill — NEW)
[12] cleanup attachment-files       (cleanup — MOVED to end)
```

### Task 3: Add attachment stages to load_batch.py daily sequence
Add `attachment_ai`, `intel_backfill`, and `attachment_cleanup` to the `load daily` batch after the existing attachment steps. These should run in the `--full` mode (not standard), since AI analysis uses API credits.

### Task 4: Add Windows Task Scheduler entries in schedule_setup.py
Add entries for the new jobs so `setup schedule-jobs` creates them. AI analysis should run after the daily load window (e.g., daily at 10:00 after the 07:00 daily load).

---

## Code Touchpoints

| File | What to do |
|------|------------|
| `fed_prospector/etl/scheduler.py` | Add 3 new JOBS entries |
| `daily_load.bat` | Add AI analysis + backfill steps, reorder cleanup to end |
| `fed_prospector/cli/load_batch.py` | Add attachment stages to daily --full |
| `fed_prospector/cli/schedule_setup.py` | Add Windows Task Scheduler entries |

---

## Tasks (continued)

### Task 5: Expand AUTO_RECOMPETE to include USASpending data

The current `AutoProspectService` recompete detection only queries `fpds_contracts` for expiring contracts. But `fpds_contracts` is filtered to our 24 tracked NAICS codes and set-asides, while `usaspending` has 5 years of ALL federal spending — much broader coverage.

**Problem:** A $50M expiring contract might not be in `fpds_contracts` if it was under a different NAICS or wasn't a small business set-aside, but it's almost certainly in USASpending. We're missing recompete opportunities.

**Fix:** Extend `AutoProspectService.GetRecompeteCandidatesAsync()` to ALSO query `usaspending_transaction` (or the relevant USASpending table) for expiring contracts:
- `period_of_performance_current_end_date` within 12 months
- `naics_code` matches org's NAICS codes
- Deduplicate against `fpds_contracts` results (same contract could appear in both)
- Use `awarding_agency_name`, `naics_code`, and `recipient_name` for opportunity matching

**Key fields available in USASpending:** `period_of_performance_current_end_date`, `naics_code`, `awarding_agency_name`, `recipient_name` (incumbent), `total_obligation` (contract value), `piid` (contract ID for solicitation matching).

---

## Code Touchpoints

| File | What to do |
|------|------------|
| `fed_prospector/etl/scheduler.py` | Add 3 new JOBS entries (Tasks 1 — DONE) |
| `daily_load.bat` | Add AI analysis + backfill steps, reorder cleanup to end (Task 2 — DONE) |
| `fed_prospector/cli/load_batch.py` | Add attachment stages to daily --full (Task 3 — DONE) |
| `fed_prospector/cli/schedule_setup.py` | Add Windows Task Scheduler entries (Task 4 — DONE) |
| `api/src/.../Services/AutoProspectService.cs` | Extend recompete detection to query USASpending (Task 5) |

---

## Out of Scope

- New scheduling framework (APScheduler, etc.) — existing infrastructure is sufficient
- The request poller service (Phase 110Y)
- Modifying the AI analyzer or backfill logic itself
