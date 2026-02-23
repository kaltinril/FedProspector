# Data Overlap and Rate Limit Strategy

## Data Overlap Matrix

The same data often appears in multiple federal sources. This matrix shows where to get each data type, with the recommended primary source and alternatives.

| Data Type | Primary Source | Backup Source(s) | Notes |
|-----------|---------------|-------------------|-------|
| Active Solicitations/RFPs | SAM.gov Opportunities API | None | Authoritative single source |
| Entity Registration Data | SAM.gov Monthly Extract | SAM.gov Entity API (targeted) | Extract bypasses rate limits |
| Entity Daily Updates | SAM.gov Daily Extract | SAM.gov Entity API | Extract preferred over API |
| SBA Certifications (WOSB/8a) | SAM.gov Entity API `sbaBusinessTypeList` | MySBA Certifications (web only) | API has entry/exit dates |
| Historical Contract Awards | SAM.gov Contract Awards API | USASpending.gov, FPDS ATOM | Contract Awards is newest; FPDS has deepest history |
| Aggregate Spending Analysis | USASpending.gov API | FPDS (underlying data) | USASpending has no rate limits |
| Federal Agency Hierarchy | SAM.gov Federal Hierarchy API | USASpending agency endpoints | SAM is authoritative |
| Exclusion/Debarment Status | SAM.gov Exclusions API | SAM.gov Exclusions Extract | API for targeted; extract for bulk |
| Subcontracting Data | SAM.gov Subaward Reporting API | eSRS (decommissioning Feb 2026) | Use SAM going forward |
| Labor Rate Pricing | GSA CALC+ API | GovWin IQ (paid) | CALC+ is free, nightly refresh |
| PSC Codes | SAM.gov PSC API | Local CSV (`PSC April 2022`) | API for latest; CSV already on disk |
| NAICS Codes | Local CSV (already on disk) | USASpending references API | CSV loaded in Phase 1 |
| SBA Size Standards | Local CSV (already on disk) | SBA.gov (manual) | CSV loaded in Phase 1 |
| Procurement Forecasts | Acquisition Gateway FCO | Individual agency sites | No single API; per-agency |

## Rate Limit Budget

### SAM.gov API Rate Limits (Shared Pool)

All SAM.gov APIs share the same rate limit based on your account type:

| Account Type | Daily Limit | Typical Use |
|-------------|-------------|-------------|
| Personal, no role | **10 calls/day** | Initial setup. Very limited. |
| Personal, with role | **1,000 calls/day** | Standard operation. Adequate for daily use. |
| System Account (non-federal) | **1,000 calls/day** | Same as personal with role. |
| Federal System Account | **10,000 calls/day** | High-volume federal use. |

**Recommendation**: Get a role assigned immediately. 10 calls/day is barely functional. 1,000/day is adequate.

### Daily Budget Allocation (10 calls/day - No Role)

With only 10 calls, every call must count:

| Allocation | Calls | Strategy |
|------------|-------|----------|
| SAM Opportunities (WOSB) | 2 | One morning, one evening check |
| SAM Opportunities (8(a)) | 2 | One morning, one evening check |
| SAM Entity Daily Extract | 1 | Download daily file |
| SAM Entity Lookup (on-demand) | 3 | Reserved for specific entity lookups |
| Reserve | 2 | Emergency/ad-hoc queries |
| **Total** | **10** | |

**Mitigation**: Use bulk extracts (monthly/daily files) instead of API pagination. One extract download = one API call = complete dataset.

### Daily Budget Allocation (1,000 calls/day - With Role)

| Allocation | Calls | Strategy |
|------------|-------|----------|
| SAM Opportunities (all set-asides) | 72 | 12 set-aside types x 6 times/day |
| SAM Entity Daily Extract | 1 | Download daily file |
| SAM Entity Lookups | 100 | On-demand entity details |
| SAM Contract Awards | 50 | Historical award searches |
| SAM Federal Hierarchy | 10 | Weekly refresh (Sunday only) |
| SAM Exclusions | 10 | Weekly check (Monday only) |
| SAM Subaward Reporting | 20 | Weekly analysis |
| Reserve | 737 | Growth, ad-hoc, burst |
| **Total** | **1,000** | |

### Unlimited APIs (No Rate Limits)

These APIs have no documented rate limits and should be used for heavy lifting:

| Source | Auth Required | Best For |
|--------|--------------|----------|
| USASpending.gov | None | Aggregate spending analysis, bulk downloads |
| GSA CALC+ | None | Labor rate analysis (~52K records) |
| FPDS ATOM Feed | None | Historical contract data (10 records/search, unlimited searches) |
| Federal Register | None | Regulatory monitoring |

### Rate Limit Tracking

The `etl_rate_limit` table tracks usage per source per day:

```sql
SELECT source_system, request_date, requests_made, max_requests,
       (max_requests - requests_made) AS remaining
FROM etl_rate_limit
WHERE request_date = CURDATE()
ORDER BY remaining ASC;
```

Before every API call, the `BaseAPIClient._check_rate_limit()` method verifies budget remains. If exhausted, it raises `RateLimitExceeded` instead of making the call.

## Data Refresh Strategy

### Recommended Refresh Schedule

```
Source                     | Frequency       | Method           | Rate Impact
---------------------------|-----------------|------------------|------------
Entity Master Data         | Monthly         | Bulk extract DL  | 1 call
Entity Incremental         | Daily (Tue-Sat) | Daily extract DL | 1 call/day
Opportunities              | Every 4 hours   | API search       | 6-72 calls/day
Contract Awards            | Weekly          | API search       | 50 calls/week
Federal Hierarchy          | Weekly          | API pagination   | 10 calls/week
GSA CALC Rates             | Monthly         | API pagination   | 260 calls/month
USASpending Awards         | Monthly         | Bulk CSV DL      | 0 (no limit)
Exclusions                 | Weekly          | API search       | 10 calls/week
FPDS Historical            | Weekly          | ATOM feed        | 0 (no limit)
Subaward Reporting         | Monthly         | API search       | 20 calls/month
Reference Data (NAICS/PSC) | Quarterly       | Manual CSV load  | 0
```

### Initial Load Strategy

For the first-time bulk load of each source:

| Source | Strategy | Time Estimate |
|--------|----------|---------------|
| Entities | Monthly extract download (1 call) | 1-2 hours (download + parse + load) |
| Opportunities (2 year history) | API pagination over multiple days | 3-5 days at 10/day; 1 day at 1,000/day |
| Contract Awards | API pagination + USASpending bulk download | 2-3 days |
| Federal Hierarchy | API pagination | 1 day |
| GSA CALC | API pagination (260 pages) | 1 hour |
| USASpending | Bulk CSV archive download | 2-4 hours per fiscal year |
| FPDS Historical | ATOM feed pagination | 3-5 days (no rate limit, but slow XML) |

## Caching Strategy

### Local File Cache

Downloaded files (extracts, bulk downloads) are cached locally:

```
data/
    downloads/
        sam_entity/
            SAM_PUBLIC_UTF-8_MONTHLY_V2_20260201.ZIP
            SAM_PUBLIC_DAILY_V2_20260218.ZIP
            SAM_PUBLIC_DAILY_V2_20260219.ZIP
        usaspending/
            FY2025_All_Contracts_Full_20260201.zip
            FY2024_All_Contracts_Full_20260201.zip
        calc/
            calc_rates_20260201.json
```

Retention: Keep last 3 monthly extracts, last 30 daily extracts. Purge older files.

### Database as Cache

The MySQL database itself acts as the persistent cache layer:
- API responses are transformed and stored in normalized tables
- Record hashes enable efficient change detection
- `etl_load_log` tracks what was loaded and when
- Re-downloading a file and re-running a load is idempotent (same result)

## Handling API Downtime

When an API is unavailable:
1. Log the error with timestamp and HTTP status
2. Mark the load as 'FAILED' in `etl_load_log`
3. Retry on next scheduled run (don't consume rate limit on retries that will fail)
4. If failure persists > 24 hours, trigger staleness alert
5. For SAM.gov: check https://sam.gov/content/status for maintenance windows (typically weekends)
