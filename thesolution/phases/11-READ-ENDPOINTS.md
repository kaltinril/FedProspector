# Phase 11: Read-Only Query Endpoints

**Status**: COMPLETE (2026-03-01)
**Dependencies**: Phase 10 (API Foundation) complete
**Deliverable**: All GET/search endpoints implemented and tested
**Repository**: `api/` (monorepo -- same repo as Python ETL)

## Overview

Implement all read-only endpoints that query the MySQL database. These endpoints expose the data that Python ETL has loaded. No data is modified -- pure query and response.

**Total endpoints this phase: 17 endpoints (14 GET, 2 POST, 1 DELETE)**

---

## 11.1 OpportunitiesController

### `GET /api/v1/opportunities` -- Search opportunities

- [x] Implement with filters: `setAside`, `naics`, `keyword` (title search), `daysOut` (deadline within N days), `openOnly` (default true), `department`, `state`
- [x] Pagination: `page`, `pageSize`, `sortBy` (posted_date, response_deadline, title), `sortDirection`
- [x] Source: `opportunity` table JOINed to `ref_naics_code`, `ref_set_aside_type`, `ref_sba_size_standard`
- [x] Include the existing Python search SQL as reference (copy from opportunities.py)

**Python SQL reference** (from `fed_prospector/cli/opportunities.py`):

```sql
SELECT o.title, o.set_aside_code, o.naics_code,
  o.response_deadline, o.posted_date, o.department_name,
  n.description
FROM opportunity o
LEFT JOIN ref_naics_code n ON o.naics_code = n.naics_code
WHERE o.posted_date >= %s
  AND o.set_aside_code = %s          -- optional
  AND o.naics_code = %s              -- optional
  AND o.response_deadline > NOW()    -- if open_only
  AND o.active = 'Y'                 -- if open_only
ORDER BY o.response_deadline ASC
LIMIT %s
```

Response DTO:

```json
{
  "items": [
    {
      "noticeId": "string",
      "title": "string",
      "solicitationNumber": "string",
      "departmentName": "string",
      "office": "string",
      "postedDate": "2026-01-15",
      "responseDeadline": "2026-03-15",
      "daysUntilDue": 30,
      "setAsideCode": "WOSB",
      "setAsideDescription": "Women-Owned Small Business",
      "setAsideCategory": "Women-Owned",
      "naicsCode": "541512",
      "naicsDescription": "Computer Systems Design Services",
      "naicsSector": "Professional, Scientific, and Technical Services",
      "sizeStandard": "$34.0 million",
      "baseAndAllOptions": 500000.00,
      "popState": "VA",
      "popCity": "Arlington",
      "prospectStatus": "PURSUING",
      "assignedUser": "jdoe"
    }
  ],
  "totalCount": 245,
  "page": 1,
  "pageSize": 25,
  "totalPages": 10
}
```

### `GET /api/v1/opportunities/{noticeId}` -- Opportunity detail

- [x] Full opportunity record with all fields
- [x] Include related awards from `fpds_contract` (JOIN on solicitation_number)
- [x] Include prospect status if tracked (LEFT JOIN to prospect)
- [x] Include USASpending award info if available (JOIN on solicitation_identifier)

Response includes nested objects:

```json
{
  "opportunity": { "/* all fields */" : "" },
  "relatedAwards": [ "/* fpds_contract matches */" ],
  "prospect": { "/* if tracked */" : "" },
  "usaspendingAward": { "/* if available */" : "" }
}
```

### `GET /api/v1/opportunities/targets` -- WOSB/8(a) target opportunities

- [x] Backed by `v_target_opportunities` view (just SELECT with pagination)
- [x] Additional filters: `minValue`, `maxValue`, `naicsSector`
- [x] Include the full view SQL as a comment/reference in the code

**View SQL reference** (from `fed_prospector/db/schema/views/10_target_opportunities.sql`):

```sql
CREATE OR REPLACE VIEW v_target_opportunities AS
SELECT
    o.notice_id,
    o.title,
    o.solicitation_number,
    o.department_name,
    o.office,
    o.posted_date,
    o.response_deadline,
    DATEDIFF(o.response_deadline, NOW()) AS days_until_due,
    o.set_aside_code,
    o.set_aside_description,
    sa.category AS set_aside_category,
    o.naics_code,
    n.description AS naics_description,
    n.level_name AS naics_level,
    sector.description AS naics_sector,
    ss.size_standard,
    ss.size_type,
    o.award_amount,
    o.pop_state,
    o.pop_city,
    o.description,
    o.link,
    p.prospect_id,
    p.status AS prospect_status,
    p.priority AS prospect_priority,
    u.display_name AS assigned_to
FROM opportunity o
LEFT JOIN ref_naics_code n ON n.naics_code = o.naics_code
LEFT JOIN ref_naics_code sector
    ON sector.naics_code = LEFT(o.naics_code, 2)
    AND sector.code_level = 1
LEFT JOIN ref_sba_size_standard ss ON ss.naics_code = o.naics_code
LEFT JOIN ref_set_aside_type sa ON sa.set_aside_code = o.set_aside_code
LEFT JOIN prospect p ON p.notice_id = o.notice_id
LEFT JOIN app_user u ON u.user_id = p.assigned_to
WHERE o.active = 'Y'
  AND o.set_aside_code IN ('WOSB', 'EDWOSB', 'WOSBSS', 'EDWOSBSS', 'SBA', '8A', '8AN')
  AND o.response_deadline > NOW();
```

---

## 11.2 AwardsController

### `GET /api/v1/awards` -- Search historical contract awards

- [x] Filters: `solicitation`, `naics`, `agency`, `vendorUei`, `vendorName`, `setAside`, `minValue`, `maxValue`, `dateFrom`, `dateTo`
- [x] Source: `fpds_contract` table
- [x] Pagination with sort by date_signed, dollars_obligated, vendor_name

Response DTO:

```json
{
  "items": [
    {
      "contractId": "string",
      "solicitationNumber": "string",
      "agencyName": "string",
      "contractingOfficeName": "string",
      "vendorName": "string",
      "vendorUei": "string",
      "dateSigned": "2025-06-15",
      "effectiveDate": "2025-07-01",
      "completionDate": "2026-06-30",
      "dollarsObligated": 1500000.00,
      "baseAndAllOptions": 3000000.00,
      "naicsCode": "541512",
      "pscCode": "D302",
      "setAsideType": "WOSB",
      "typeOfContract": "FIRM_FIXED_PRICE",
      "numberOfOffers": 5,
      "extentCompeted": "FULL_AND_OPEN",
      "description": "IT Support Services"
    }
  ],
  "totalCount": 50,
  "page": 1,
  "pageSize": 25,
  "totalPages": 2
}
```

### `GET /api/v1/awards/{contractId}` -- Award detail

- [x] Full fpds_contract record
- [x] Include USASpending transactions if available (JOIN on PIID)
- [x] Include vendor entity profile (JOIN on vendor_uei -> entity)

### `GET /api/v1/awards/{contractId}/burn-rate` -- Monthly spend analysis

- [x] Source: `usaspending_transaction` aggregated by month
- [x] Copy exact SQL from Python `calculate_burn_rate()` (include it in the doc)
- [x] Calculate: total_obligated, months_elapsed, monthly_rate, monthly_breakdown

**Burn rate SQL reference** (from `fed_prospector/etl/usaspending_loader.py`):

```sql
SELECT DATE_FORMAT(action_date, '%Y-%m') AS year_month,
       SUM(federal_action_obligation) AS monthly_total,
       COUNT(*) AS txn_count
FROM usaspending_transaction
WHERE award_id = %s
  AND federal_action_obligation IS NOT NULL
GROUP BY year_month
ORDER BY year_month
```

Python logic for months_elapsed:

```python
# Parse first and last year_month strings (YYYY-MM)
fy, fm = int(first_month[:4]), int(first_month[5:7])
ly, lm = int(last_month[:4]), int(last_month[5:7])
months = (ly - fy) * 12 + (lm - fm) + 1  # inclusive

monthly_rate = total / months if months > 0 else 0
```

Response DTO:

```json
{
  "contractId": "string",
  "totalObligated": 1500000.00,
  "baseAndAllOptions": 3000000.00,
  "percentSpent": 50.0,
  "monthsElapsed": 12,
  "monthlyRate": 125000.00,
  "transactionCount": 15,
  "monthlyBreakdown": [
    { "yearMonth": "2025-07", "amount": 150000.00, "transactionCount": 2 },
    { "yearMonth": "2025-08", "amount": 125000.00, "transactionCount": 1 }
  ]
}
```

---

## 11.3 EntitiesController

### `GET /api/v1/entities` -- Search contractors

- [x] Filters: `name` (partial match), `uei`, `naics`, `state`, `businessType`, `sbaCertification`, `registrationStatus`
- [x] Source: `entity` JOINed to child tables
- [x] Pagination with sort by legal_business_name, last_update_date

### `GET /api/v1/entities/{uei}` -- Full entity profile

- [x] All entity fields
- [x] Nested child data: addresses[], naicsCodes[], pscCodes[], businessTypes[], sbaCertifications[], pointsOfContact[]
- [x] Source: `entity` + all 6 child tables (entity_address, entity_naics, entity_psc, entity_business_type, entity_sba_certification, entity_poc)

### `GET /api/v1/entities/{uei}/competitor-profile` -- Aggregated intelligence

- [x] Backed by `v_competitor_analysis` view
- [x] Include the full view SQL as reference
- [x] Returns aggregated business types, SBA certs, past contract count, total obligated, most recent award

**View SQL reference** (from `fed_prospector/db/schema/views/20_competitor_analysis.sql`):

```sql
CREATE OR REPLACE VIEW v_competitor_analysis AS
SELECT
    e.uei_sam,
    e.legal_business_name,
    e.primary_naics,
    n.description AS naics_description,
    sector.description AS naics_sector,
    es.description AS entity_structure,
    GROUP_CONCAT(DISTINCT CONCAT(ebt.business_type_code, ':', COALESCE(rbt.description, ''))
        ORDER BY ebt.business_type_code SEPARATOR '; ') AS business_types,
    GROUP_CONCAT(DISTINCT rbt.category ORDER BY rbt.category SEPARATOR ', ') AS business_type_categories,
    GROUP_CONCAT(DISTINCT CONCAT(esc.sba_type_code, ':', COALESCE(rst.description, ''))
        ORDER BY esc.sba_type_code SEPARATOR '; ') AS sba_certifications,
    COUNT(DISTINCT fc.contract_id) AS past_contracts,
    SUM(fc.dollars_obligated) AS total_obligated,
    MAX(fc.date_signed) AS most_recent_award
FROM entity e
LEFT JOIN ref_naics_code n ON n.naics_code = e.primary_naics
LEFT JOIN ref_naics_code sector
    ON sector.naics_code = LEFT(e.primary_naics, 2)
    AND sector.code_level = 1
LEFT JOIN ref_entity_structure es ON es.structure_code = e.entity_structure_code
LEFT JOIN entity_business_type ebt ON ebt.uei_sam = e.uei_sam
LEFT JOIN ref_business_type rbt ON rbt.business_type_code = ebt.business_type_code
LEFT JOIN entity_sba_certification esc ON esc.uei_sam = e.uei_sam
LEFT JOIN ref_sba_type rst ON rst.sba_type_code = esc.sba_type_code
LEFT JOIN fpds_contract fc ON fc.vendor_uei = e.uei_sam
WHERE e.registration_status = 'A'
GROUP BY e.uei_sam, e.legal_business_name, e.primary_naics,
         n.description, sector.description, es.description;
```

### `GET /api/v1/entities/{uei}/exclusion-check` -- Debarment status

- [x] Source: `sam_exclusion` table
- [x] Query by UEI, also check by entity name (fuzzy match)
- [x] Return: is_excluded (boolean), active exclusions list with type, agency, dates

Response DTO:

```json
{
  "uei": "string",
  "entityName": "string",
  "isExcluded": false,
  "activeExclusions": [
    {
      "exclusionType": "Ineligible (Proceedings Completed)",
      "excludingAgencyName": "Department of Defense",
      "activationDate": "2024-01-15",
      "terminationDate": "2027-01-15",
      "additionalComments": "..."
    }
  ],
  "checkedAt": "2026-02-28T14:30:00Z"
}
```

---

## 11.4 SubawardsController

### `GET /api/v1/subawards/teaming-partners` -- Prime-sub relationships

- [x] Filters: `naics`, `minSubawards` (threshold), `primeUei`, `subUei`
- [x] Source: `sam_subaward` GROUP BY prime
- [x] Copy exact SQL from Python `find_teaming_partners()` (include in doc)
- [x] Returns: prime info, sub count, unique subs, total sub amount, NAICS codes

**Teaming partners SQL reference** (from `fed_prospector/etl/subaward_loader.py`):

```sql
SELECT
    s.prime_uei,
    s.prime_name,
    COUNT(*) AS sub_count,
    SUM(s.sub_amount) AS total_sub_amount,
    COUNT(DISTINCT s.sub_uei) AS unique_subs,
    GROUP_CONCAT(DISTINCT s.naics_code ORDER BY s.naics_code SEPARATOR ', ')
        AS naics_codes
FROM sam_subaward s
WHERE s.naics_code = %s              -- optional
GROUP BY s.prime_uei, s.prime_name
HAVING COUNT(*) >= %s                -- min_subawards threshold
ORDER BY sub_count DESC
LIMIT %s
```

**Search subawards SQL reference** (from `fed_prospector/cli/subaward.py`):

```sql
SELECT prime_piid, prime_name, prime_uei,
       sub_name, sub_uei, sub_amount, sub_date,
       naics_code, sub_business_type, pop_state
FROM sam_subaward
WHERE prime_uei = %s                 -- optional
  AND sub_uei = %s                   -- optional
  AND naics_code = %s                -- optional
  AND prime_piid = %s                -- optional
ORDER BY sub_date DESC
LIMIT %s
```

---

## 11.5 DashboardController

### `GET /api/v1/dashboard` -- Pipeline overview

- [x] 6 sub-queries aggregated into one response:
  1. Open prospects by status (count per status)
  2. Opportunities due this week (deadline within 7 days)
  3. Workload by assigned user (count per user)
  4. Win/loss metrics (counts and amounts for WON/LOST)
  5. Recent saved search results (last run dates and new result counts)
  6. Total open prospects (count of non-terminal prospects)
- [x] Copy dashboard SQL from Python `get_dashboard_data()`

**Dashboard SQL reference** (from `fed_prospector/etl/prospect_manager.py`):

```sql
-- 1. Prospects by status
SELECT status, COUNT(*) AS cnt
FROM prospect
GROUP BY status
ORDER BY status;

-- 2. Due this week (response_deadline within 7 days, open prospects only)
SELECT p.prospect_id, p.status, p.priority,
  o.title, o.response_deadline, o.set_aside_code,
  u.username AS assigned_to
FROM prospect p
JOIN opportunity o ON p.notice_id = o.notice_id
LEFT JOIN app_user u ON p.assigned_to = u.user_id
WHERE p.status NOT IN ('WON', 'LOST', 'DECLINED', 'NO_BID')
  AND o.response_deadline BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 7 DAY)
ORDER BY o.response_deadline ASC;

-- 3. By assignee (open prospects only)
SELECT u.username, u.display_name, COUNT(*) AS cnt
FROM prospect p
JOIN app_user u ON p.assigned_to = u.user_id
WHERE p.status NOT IN ('WON', 'LOST', 'DECLINED', 'NO_BID')
GROUP BY u.user_id, u.username, u.display_name
ORDER BY cnt DESC;

-- 4. Win/loss stats
SELECT outcome, COUNT(*) AS cnt
FROM prospect
WHERE outcome IS NOT NULL
GROUP BY outcome
ORDER BY outcome;

-- 5. Saved searches
SELECT s.search_id, s.search_name, s.last_run_at,
  s.last_new_results, u.username
FROM saved_search s
JOIN app_user u ON s.user_id = u.user_id
WHERE s.is_active = 'Y'
ORDER BY s.search_name;

-- 6. Total open prospects
SELECT COUNT(*) AS cnt
FROM prospect
WHERE status NOT IN ('WON', 'LOST', 'DECLINED', 'NO_BID');
```

---

## 11.6 AdminController

### `GET /api/v1/admin/etl-status` -- ETL health check

- [x] Source: `etl_load_log` table
- [x] Show last successful load per source_system
- [x] Calculate hours since last load
- [x] Flag stale data (>6h for opportunities, >48h for entities, >14d for others)
- [x] Requires admin role

**Staleness thresholds** (from `fed_prospector/etl/health_check.py`):

| Source | Threshold | Warning at 80% |
|--------|-----------|-----------------|
| SAM_OPPORTUNITY | 6 hours | 4.8 hours |
| SAM_ENTITY | 48 hours | 38.4 hours |
| SAM_FED_HIERARCHY | 336 hours (14d) | 268.8 hours |
| SAM_AWARDS | 336 hours (14d) | 268.8 hours |
| GSA_CALC | 1080 hours (45d) | 864 hours |
| SAM_EXCLUSIONS | 336 hours (14d) | 268.8 hours |
| USASPENDING | 1080 hours (45d) | 864 hours |
| SAM_SUBAWARD | 1080 hours (45d) | 864 hours |

---

## 11.7 SavedSearchesController

### `GET /api/v1/saved-searches` -- List user's saved searches
- [x] Return all active saved searches for the authenticated user

### `POST /api/v1/saved-searches` -- Create a saved search
- [x] Store search name and filter criteria (maps to Python `save-search` CLI command)

### `POST /api/v1/saved-searches/{id}/run` -- Execute a saved search and return results
- [x] Run the saved search filters and return matching opportunities (maps to Python `run-search` CLI command)

### `DELETE /api/v1/saved-searches/{id}` -- Delete a saved search
- [x] Soft-delete by setting `is_active = 'N'`

---

## Acceptance Criteria

1. [x] All 17 endpoints return correct data from MySQL
2. [x] Pagination works on all list endpoints (page, pageSize, totalCount, totalPages)
3. [x] Filters applied correctly (verified with known test data)
4. [x] Swagger documentation shows all endpoints with request/response examples
5. [x] Burn rate calculation matches Python output for same contract
6. [x] Views (v_target_opportunities, v_competitor_analysis) queryable through endpoints
7. [x] All endpoints require JWT auth (except health check)
8. [x] Response times < 500ms for paginated queries on production data volumes
9. [x] Empty results return 200 with empty items array (not 404)

---

## SQL Reference Summary

All SQL in this document was copied from the Python codebase source files:

| Query | Source File |
|-------|------------|
| Opportunity search | `fed_prospector/cli/opportunities.py` |
| v_target_opportunities view | `fed_prospector/db/schema/views/10_target_opportunities.sql` |
| v_competitor_analysis view | `fed_prospector/db/schema/views/20_competitor_analysis.sql` |
| Burn rate aggregation | `fed_prospector/etl/usaspending_loader.py` |
| Teaming partners GROUP BY | `fed_prospector/etl/subaward_loader.py` |
| Subaward search | `fed_prospector/cli/subaward.py` |
| Dashboard sub-queries (6) | `fed_prospector/etl/prospect_manager.py` |

---

## Deliverables

### New Files Created (~61)
- 4 view models (`api/src/FedProspector.Core/Models/Views/`)
- ~30 DTOs across 7 subdirectories (`api/src/FedProspector.Core/DTOs/`)
- 6 validators (`api/src/FedProspector.Core/Validators/`)
- 7 service interfaces (`api/src/FedProspector.Core/Interfaces/`)
- 7 service implementations (`api/src/FedProspector.Infrastructure/Services/`)
- 7 controllers (`api/src/FedProspector.Api/Controllers/`)

### Modified Files
- `FedProspectorDbContext.cs` -- 4 view DbSets + keyless entity configuration
- `MappingProfile.cs` -- AutoMapper mappings for views + entity child tables
- `Program.cs` -- 7 service DI registrations

### Endpoints (17 total)
| Controller | Route | Endpoints |
|-----------|-------|-----------|
| OpportunitiesController | `api/v1/opportunities` | GET / (search), GET /targets, GET /{noticeId} |
| AwardsController | `api/v1/awards` | GET / (search), GET /{contractId}, GET /{contractId}/burn-rate |
| EntitiesController | `api/v1/entities` | GET / (search), GET /{uei}, GET /{uei}/competitor-profile, GET /{uei}/exclusion-check |
| SubawardsController | `api/v1/subawards` | GET /teaming-partners |
| DashboardController | `api/v1/dashboard` | GET / |
| AdminController | `api/v1/admin` | GET /etl-status |
| SavedSearchesController | `api/v1/saved-searches` | GET /, POST /, POST /{id}/run, DELETE /{id} |
