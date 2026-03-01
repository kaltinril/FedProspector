# Phase 6: Automation and Monitoring

**Status**: COMPLETE (2026-02-28)
**Dependencies**: Phase 3 (Opportunities Pipeline) minimum; ideally Phase 5 complete
**Deliverable**: Hands-off daily operation with automated refreshes and alerting

---

## Tasks

### 6.1 Job Scheduler Setup
- [x] Implemented `etl/scheduler.py` with JOBS dict and JobRunner class (NOT a daemon — each invocation runs one job and exits):

| Job | Schedule | Source | Priority | Staleness |
|-----|----------|--------|----------|-----------|
| SAM Entity Daily Extract | Tue-Sat 06:00 | SAM Extracts API | High | 48h |
| SAM Opportunities Refresh | Every 4 hours | SAM Opportunities API | Critical | 6h |
| Federal Hierarchy Refresh | Sunday 02:00 | SAM Fed Hierarchy API | Medium | 336h (14d) |
| Contract Awards Refresh | Saturday 03:00 | SAM Contract Awards API | Medium | 336h (14d) |
| GSA CALC Rates Refresh | 1st of month 04:00 | CALC+ API | Low | 1080h (45d) |
| USASpending Refresh | 1st of month 05:00 | USASpending API | Medium | 1080h (45d) |
| Exclusions Check | Monday 06:00 | SAM Exclusions API | High | 336h (14d) |
| Saved Search Runner | Daily 07:00 | Internal | Medium | N/A |

- [x] `JobRunner` class with:
  - [x] `run_job(name)` — subprocess.run with 1h timeout, correct Python interpreter
  - [x] `list_jobs()` — all jobs with last-run status from etl_load_log
  - [x] `get_job_status(name)` — hours since last run, records, errors
- [x] Windows Task Scheduler schtasks commands documented in module docstring
- [x] CLI: `run-job <name>` to manually trigger, `run-job --list` to show all jobs

### 6.2 API Key Management
- [x] `HealthCheck.check_api_keys()` verifies SAM_API_KEY and SAM_API_KEY_2 are configured
- [x] Daily usage tracking via `etl_rate_limit` table
- [x] Alerts when API keys are missing from configuration
- [ ] (Future) Track key creation dates and expiration warnings (90-day cycle)

### 6.3 Data Staleness Detection
- [x] Implemented in `etl/health_check.py` with `STALENESS_THRESHOLDS` dict:
  - [x] Entity data: 48 hours
  - [x] Opportunity data: 6 hours
  - [x] Federal Hierarchy: 336 hours (14 days)
  - [x] Contract Awards: 336 hours (14 days)
  - [x] CALC Rates: 1080 hours (45 days)
  - [x] Exclusions: 336 hours (14 days)
  - [x] USASpending: 1080 hours (45 days)
  - [x] Subawards: 1080 hours (45 days)
- [x] `check_data_freshness()` queries etl_load_log, returns WARNING at 80% threshold, STALE at 100%

### 6.4 Error Alerting
- [x] `HealthCheck.get_alerts()` aggregates all alert types:
  - [x] Data freshness (WARNING/STALE per source)
  - [x] Missing API keys
  - [x] Recent load failures
  - [x] Rate limit exhaustion
- [x] Console output via `check-health` CLI command
- [x] `--json` flag for structured output (machine-readable)
- [ ] (Future) Email/Slack notifications

### 6.5 Health Check Dashboard
- [x] Implemented `check-health` CLI command (`cli/health.py`) showing:
  - [x] Data freshness per source with OK/WARNING/STALE status
  - [x] Table statistics with row counts, data size, index size
  - [x] API usage today (calls made vs. limits)
  - [x] Alerts summary
- [x] `HealthCheck` class with 6 methods:
  - `check_data_freshness()`, `get_table_stats()`, `get_api_usage_today()`
  - `check_api_keys()`, `get_recent_errors()`, `get_alerts()`

### 6.6 Saved Search Automation
- [x] `run-all-searches` CLI command runs all active saved searches
- [x] Uses `ProspectManager.run_search()` for each active search
- [x] Registered in scheduler as daily 07:00 job

### 6.7 Operational Documentation
- [x] Windows Task Scheduler commands documented in `etl/scheduler.py` docstring
- [x] All CLI commands have `--help` support (self-documenting)
- [x] QUICKSTART.md updated with Phase 6 commands
- [ ] (Future) Standalone runbook document

### 6.8 Database Maintenance
- [x] Implemented `etl/db_maintenance.py` with `DatabaseMaintenance` class:
  - [x] `archive_entity_history(days=365)` — batch delete in 10K row chunks
  - [x] `archive_opportunity_history(days=365)` — batch delete in 10K row chunks
  - [x] `purge_staging(days=30)` — clean old stg_entity_raw records
  - [x] `purge_load_errors(days=90)` — clean old etl_load_error records
  - [x] `analyze_tables()` — ANALYZE TABLE on all tables
  - [x] `get_table_sizes()` — data_mb, index_mb, row counts from information_schema
- [x] CLI: `maintain-db` with `--dry-run`, `--analyze`, `--sizes` options
- [x] Registered in scheduler as monthly 1st 01:00 job
- [ ] (Future) Backup strategy (mysqldump, restore procedure)

---

## Acceptance Criteria

1. [x] All scheduled jobs run automatically without intervention (via Windows Task Scheduler)
2. [x] Failed jobs are logged and alerted (etl_load_log + check-health)
3. [ ] API key expiration warnings fire 14 days in advance (future: track creation dates)
4. [x] Data staleness is detected within expected thresholds (WARNING at 80%, STALE at 100%)
5. [x] `check-health` provides a complete system health overview
6. [x] All CLI commands are self-documenting via `--help`
7. [x] Database maintenance keeps table sizes manageable (maintain-db with batch deletes)

---

## Windows Task Scheduler Setup

Jobs are triggered via Windows Task Scheduler. Full schtasks commands are in `etl/scheduler.py` docstring:

```bash
schtasks /create /tn "FedContract_Opportunities" /tr "python main.py load-opportunities --key 2" /sc HOURLY /mo 4
schtasks /create /tn "FedContract_EntityDaily" /tr "python main.py download-extract --type daily" /sc WEEKLY /d TUE,WED,THU,FRI,SAT /st 06:00
schtasks /create /tn "FedContract_Hierarchy" /tr "python main.py load-hierarchy --full-refresh --key 2" /sc WEEKLY /d SUN /st 02:00
schtasks /create /tn "FedContract_Awards" /tr "python main.py load-awards --key 2" /sc WEEKLY /d SAT /st 03:00
schtasks /create /tn "FedContract_CalcRates" /tr "python main.py load-calc" /sc MONTHLY /d 1 /st 04:00
schtasks /create /tn "FedContract_Exclusions" /tr "python main.py load-exclusions --key 2" /sc WEEKLY /d MON /st 06:00
schtasks /create /tn "FedContract_HealthCheck" /tr "python main.py check-health" /sc DAILY /st 09:00
schtasks /create /tn "FedContract_SavedSearches" /tr "python main.py run-all-searches" /sc DAILY /st 07:00
schtasks /create /tn "FedContract_Maintenance" /tr "python main.py maintain-db" /sc MONTHLY /d 1 /st 01:00
```

## Implementation Details

- **Architecture**: NOT a daemon — `etl/scheduler.py` defines job metadata; Windows Task Scheduler invokes CLI commands
- **Job Runner**: `JobRunner.run_job()` uses `subprocess.run()` with 1h timeout, resolves correct Python interpreter
- **Health Check**: `etl/health_check.py` with `HealthCheck` class (6 methods), threshold-based staleness detection
- **DB Maintenance**: `etl/db_maintenance.py` with `DatabaseMaintenance` class, batch-delete pattern (10K rows/batch)
- **CLI Module**: `cli/health.py` with 4 commands: check-health, run-job, maintain-db, run-all-searches
