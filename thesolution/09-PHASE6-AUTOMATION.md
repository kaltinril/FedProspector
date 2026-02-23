# Phase 6: Automation and Monitoring

**Status**: Not Started
**Dependencies**: Phase 3 (Opportunities Pipeline) minimum; ideally Phase 5 complete
**Deliverable**: Hands-off daily operation with automated refreshes and alerting

---

## Tasks

### 6.1 Job Scheduler Setup
- [ ] Configure APScheduler (or Windows Task Scheduler) with all jobs:

| Job | Schedule | Source | Priority |
|-----|----------|--------|----------|
| SAM Entity Daily Extract | 06:00 AM Tue-Sat | SAM Extracts API | High |
| SAM Opportunities Refresh | Every 4 hours | SAM Opportunities API | Critical |
| Federal Hierarchy Refresh | Sunday 02:00 AM | SAM Fed Hierarchy API | Medium |
| FPDS Awards Refresh | Saturday 03:00 AM | FPDS ATOM Feed | Medium |
| GSA CALC Rates Refresh | 1st of month 04:00 AM | CALC+ API | Low |
| USASpending Refresh | 1st of month 05:00 AM | USASpending API | Medium |
| Exclusions Check | Monday 06:00 AM | SAM Exclusions API | High |
| API Key Expiry Alert | Daily 08:00 AM | Internal check | Critical |
| Data Staleness Check | Daily 09:00 AM | Internal check | High |
| Saved Search Runner | Daily 07:00 AM | Internal | Medium |

- [ ] Implement `scheduler/job_runner.py`:
  - [ ] Job execution with error handling (one job failure doesn't block others)
  - [ ] Job logging to `etl_load_log`
  - [ ] Configurable enable/disable per job
  - [ ] Manual trigger capability via CLI: `run-job --name sam_opportunities`

### 6.2 API Key Management
- [ ] Track API key expiration dates:
  - [ ] SAM.gov keys expire every 90 days
  - [ ] Store key creation date in `.env` or config table
- [ ] Implement expiration warning:
  - [ ] Alert at 14 days before expiry
  - [ ] Alert at 7 days before expiry
  - [ ] Alert at 1 day before expiry
  - [ ] Block API calls after expiry (prevent wasting error responses)
- [ ] Document key renewal process

### 6.3 Data Staleness Detection
- [ ] Implement staleness check query:
  ```
  For each source_system in etl_load_log:
    - Find most recent successful load
    - Compare against expected refresh frequency
    - Alert if data is stale (e.g., entity data > 2 days old)
  ```
- [ ] Define staleness thresholds:
  - [ ] Entity data: > 2 days (excluding weekends)
  - [ ] Opportunity data: > 6 hours
  - [ ] Federal Hierarchy: > 14 days
  - [ ] FPDS Awards: > 14 days
  - [ ] CALC Rates: > 45 days
  - [ ] Exclusions: > 14 days

### 6.4 Error Alerting
- [ ] Implement alert mechanisms:
  - [ ] Log file alerts (ERROR level and above)
  - [ ] Console output for CLI monitoring
  - [ ] (Future) Email notifications
  - [ ] (Future) Slack/Teams webhook
- [ ] Alert on:
  - [ ] Load job failure (status = 'FAILED')
  - [ ] High error rate (records_errored / records_read > 5%)
  - [ ] Rate limit exhaustion (daily limit reached)
  - [ ] API key expiration warning
  - [ ] Data staleness threshold exceeded
  - [ ] Database connection failure

### 6.5 Health Check Dashboard
- [ ] Implement `check-status` CLI command showing:
  ```
  === Data Freshness ===
  Entity Data:       Last loaded 2026-02-22 06:15 (4 hours ago) [OK]
  Opportunities:     Last loaded 2026-02-22 10:00 (15 min ago)  [OK]
  Federal Hierarchy: Last loaded 2026-02-16 02:00 (6 days ago)  [OK]
  FPDS Awards:       Last loaded 2026-02-15 03:00 (7 days ago)  [OK]
  CALC Rates:        Last loaded 2026-02-01 04:00 (21 days ago) [OK]
  Exclusions:        Last loaded 2026-02-17 06:00 (5 days ago)  [OK]

  === Table Statistics ===
  entity:            576,432 records
  opportunity:       45,221 records (12,345 active)
  fpds_contract:     234,567 records
  federal_org:       8,432 records
  gsa_labor_rate:    51,863 records
  prospect:          47 records (12 active)

  === API Usage Today ===
  SAM.gov:           7 / 1,000 calls used
  CALC+:             0 / unlimited
  USASpending:       0 / unlimited

  === Alerts ===
  [WARN] SAM API key expires in 12 days - renew before 2026-03-06
  [OK] No failed loads in last 7 days
  [OK] All data within freshness thresholds
  ```

### 6.6 Saved Search Automation
- [ ] Run all active saved searches with `notification_enabled = 'Y'` daily
- [ ] Compare results to previous run
- [ ] Log new results count in `saved_search.last_new_results`
- [ ] (Future) Send notifications for new matching opportunities

### 6.7 Operational Documentation
- [ ] Create runbook covering:
  - [ ] How to start/stop the scheduler
  - [ ] How to manually trigger any load
  - [ ] How to check system health
  - [ ] How to renew SAM.gov API keys
  - [ ] How to add new NAICS codes to monitoring
  - [ ] How to add new team members
  - [ ] Troubleshooting common errors
  - [ ] Database backup procedures

### 6.8 Database Maintenance
- [ ] Implement periodic cleanup:
  - [ ] Archive old `entity_history` records (> 1 year)
  - [ ] Archive old `opportunity_history` records (> 1 year)
  - [ ] Purge old `stg_entity_raw` records (> 30 days)
  - [ ] Purge old `etl_load_error` records (> 90 days)
  - [ ] Update table statistics (ANALYZE TABLE)
- [ ] Implement backup strategy:
  - [ ] Daily mysqldump of operational tables
  - [ ] Weekly full backup
  - [ ] Document restore procedure

---

## Acceptance Criteria

1. All scheduled jobs run automatically without intervention
2. Failed jobs are logged and alerted
3. API key expiration warnings fire 14 days in advance
4. Data staleness is detected within expected thresholds
5. `check-status` provides a complete system health overview
6. Operational runbook covers all common scenarios
7. Database maintenance keeps table sizes manageable

---

## Windows Task Scheduler Alternative

If APScheduler is insufficient (e.g., needs to survive process restarts), use Windows Task Scheduler:

```
# Create task for opportunity refresh (every 4 hours)
schtasks /create /tn "FedContract_OpportunityRefresh" /tr "python main.py load-opportunities" /sc HOURLY /mo 4

# Create task for daily entity extract (6 AM weekdays)
schtasks /create /tn "FedContract_EntityDaily" /tr "python main.py load-entities --mode=daily" /sc WEEKLY /d TUE,WED,THU,FRI,SAT /st 06:00

# Create task for health check (9 AM daily)
schtasks /create /tn "FedContract_HealthCheck" /tr "python main.py check-status --alert" /sc DAILY /st 09:00
```
