# Phase 110E: Scheduled & Automated Analysis

**Status:** PLANNED
**Priority:** Low — manual CLI commands work fine for now
**Dependencies:** Phase 110C (AI analyzer module must exist first)

---

## Summary

Add scheduled/automated execution of AI document analysis and other recurring pipeline tasks. Currently all analysis runs via manual CLI commands or UI button clicks. This phase adds cron-style scheduling so batch analysis runs automatically as part of daily data loading.

---

## Scope

- Schedule daily AI analysis batch (`analyze attachments`) after daily opportunity/attachment loads complete
- Schedule column backfill (`backfill opportunity-intel`) after analysis
- Schedule attachment cleanup after analysis
- Potentially schedule other recurring tasks (data quality checks, etc.)

## Out of Scope

- The request poller service (handled in Phase 110F as part of `fed_prospector.py start/stop`)
- The AI analyzer module itself (Phase 110C)
- Award on-demand loading scheduling (Phase 43, already working)

## Design Considerations

- Could be a Python scheduler (APScheduler is already in requirements.txt)
- Could be Windows Task Scheduler tasks
- Could be a simple shell script that chains CLI commands
- Need to handle: ordering (load first, then analyze, then cleanup), failure handling, logging
- Should be configurable (enable/disable individual jobs, set times)

## Notes

- Don't over-engineer this. A batch script that runs the CLI commands in order may be sufficient.
- The existing `etl/scheduler.py` may already have patterns to follow — review before implementing.
