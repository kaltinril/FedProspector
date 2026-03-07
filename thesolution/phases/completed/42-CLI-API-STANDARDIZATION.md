# Phase 42: CLI/API Query Standardization

**Status:** COMPLETE (42D-2/3 deferred)
**Depends on:** Phase 41 (Detail View Fixes)
**Priority:** Medium — reduces maintenance burden and prevents query drift

## Goal

The Python CLI and C# API both query the same MySQL database but implement search/query logic independently. This creates divergence risk: a filter fix in one place doesn't propagate to the other. This phase audits all overlapping query paths, documents discrepancies, and standardizes where beneficial.

## Success Criteria

1. Every search/query that exists in both CLI and API produces equivalent results for the same inputs
2. Shared query logic lives in a single location (views, stored procs, or documented-accepted divergence)
3. Discrepancies documented below are resolved or explicitly accepted
4. No regressions in CLI or API behavior

---

## Audit Findings

### 1. Entity Search

**CLI:** `fed_prospector/cli/entities.py` `search_entities()` (lines 508-645)
**API:** `api/src/FedProspector.Infrastructure/Services/EntityService.cs` `SearchAsync()` (lines 21-102)

| Aspect | CLI (Python raw SQL) | API (EF Core) | Discrepancy |
|--------|---------------------|---------------|-------------|
| **Name filter** | `e.legal_business_name LIKE %name%` with `NO_INDEX(e idx_entity_name)` hint | `EF.Functions.Like` with `.TagWith("HINT:NO_INDEX(entity idx_entity_name)")` | **Equivalent** — both use leading-wildcard LIKE with the same index hint. |
| **UEI filter** | `e.uei_sam = %s` | `e.UeiSam == request.Uei` | Equivalent |
| **NAICS filter** | `EXISTS (SELECT 1 FROM entity_naics en WHERE en.uei_sam = e.uei_sam AND en.naics_code = %s)` — checks child table | `e.PrimaryNaics == request.Naics` — checks entity.primary_naics column only | **DISCREPANCY** — CLI searches ALL NAICS codes (child table), API only checks the primary NAICS code. CLI finds entities where the code is a secondary NAICS; API misses them. |
| **State filter** | `EXISTS (SELECT 1 FROM entity_address ea2 WHERE ea2.uei_sam = e.uei_sam AND ea2.state_or_province = %s)` — checks ALL addresses | `_context.EntityAddresses.Any(a => a.UeiSam == e.UeiSam && a.StateOrProvince == request.State)` — also checks all addresses | Equivalent |
| **Certification filter** | `EXISTS (SELECT 1 FROM entity_sba_certification ec WHERE ec.uei_sam = e.uei_sam AND ec.sba_type_code = %s AND (ec.certification_exit_date IS NULL OR ec.certification_exit_date > CURDATE()))` — filters for ACTIVE certs only | `_context.EntitySbaCertifications.Any(sc => sc.UeiSam == e.UeiSam && sc.SbaTypeCode == request.SbaCertification)` — no date check | **DISCREPANCY** — CLI filters out expired certifications; API returns entities with expired SBA certs too. |
| **Active-only filter** | `e.registration_status = 'A'` (opt-in `--active-only` flag) | `e.RegistrationStatus == request.RegistrationStatus` (arbitrary value) | **Different semantics** — CLI has a convenience flag; API uses a generic status filter. Acceptable divergence. |
| **Business type filter** | Not available | `EXISTS` on `EntityBusinessTypes` | API-only capability. Acceptable. |
| **Sort** | `ORDER BY e.legal_business_name` (fixed) | Default `OrderBy(e.LegalBusinessName)`, supports `lastUpdateDate`, `registrationExpirationDate` via `SortBy` | API is richer. Acceptable. |
| **Pagination** | `LIMIT %s` only (no offset) | `Skip/Take` with `Page/PageSize` | API has proper pagination. Acceptable — CLI is a quick lookup tool. |
| **Columns returned** | 7 columns (uei, name, cage, primary_naics, reg_status, reg_exp, state via LEFT JOIN) | 10 fields in DTO (adds DbaName, EntityStructureCode, EntityUrl, LastUpdateDate) | API returns more data. Acceptable. |
| **Address join** | `LEFT JOIN entity_address ea ON ... AND ea.address_type = 'PHYSICAL'` — explicit PHYSICAL filter | `PopState` derived from `_context.EntityAddresses.Where(a.AddressType == "physical")` in projection | **Case mismatch risk** — CLI uses `'PHYSICAL'` (uppercase), API uses `"physical"` (lowercase). If data stores uppercase, the API projection silently returns null for PopState. |

**Summary:** 3 discrepancies found — NAICS filter scope, certification date check, address type case.

---

### 2. Opportunity Search

**CLI:** `fed_prospector/cli/opportunities.py` `search()` (lines 437-583)
**API:** `api/src/FedProspector.Infrastructure/Services/OpportunityService.cs` `SearchAsync()` (lines 21-120)

| Aspect | CLI (Python raw SQL) | API (EF Core) | Discrepancy |
|--------|---------------------|---------------|-------------|
| **Date filter** | `o.posted_date >= %s` (mandatory, based on `--days` default 30) | No mandatory date filter; optional `DaysOut` filters by response deadline, not posted date | **DISCREPANCY** — CLI always filters by posted date; API does not. An API search with no filters returns ALL opportunities; CLI returns only last 30 days. |
| **Set-aside filter** | `o.set_aside_code = %s` | `o.SetAsideCode == request.SetAside` | Equivalent |
| **NAICS filter** | `o.naics_code = %s` | `o.NaicsCode == request.Naics` | Equivalent |
| **Open-only filter** | `o.response_deadline > NOW() AND o.active = 'Y'` | `o.Active == "Y" && o.ResponseDeadline > DateTime.UtcNow` | Equivalent |
| **Keyword filter** | Not available | `LIKE %keyword%` on title with escape | API-only. |
| **Department filter** | Not available | `LIKE %dept%` on department_name | API-only. |
| **State filter** | Not available | `o.PopState == request.State` | API-only. |
| **DaysOut filter** | Not available | `o.ResponseDeadline <= DateTime.UtcNow.AddDays(DaysOut)` | API-only. Different concept from CLI's `--days` (posted date). |
| **NAICS description join** | `LEFT JOIN ref_naics_code n ON o.naics_code = n.naics_code` | Joins ref_naics_code AND ref_set_aside_type AND prospect (for current org) AND app_user | API is much richer: includes set-aside category, prospect status, assigned user. |
| **Sort** | `ORDER BY o.response_deadline ASC` (fixed) | Default `ResponseDeadline ASC`, supports `PostedDate`, `Title` via SortBy | API is richer. |
| **Pagination** | `LIMIT` only | `Skip/Take` | API has proper pagination. |

**Summary:** 1 material discrepancy — date filter semantics differ. API has many more filter options, which is expected and acceptable.

---

### 3. Award Search

**CLI:** `fed_prospector/cli/awards.py` `search_awards()` (lines 190-345)
**API:** `api/src/FedProspector.Infrastructure/Services/AwardService.cs` `SearchAsync()` (lines 21-114)

| Aspect | CLI (Python raw SQL) | API (EF Core) | Discrepancy |
|--------|---------------------|---------------|-------------|
| **Base awards filter** | `modification_number = '0'` unless `--piid` is specified | `ModificationNumber == "0"` always | **DISCREPANCY** — CLI relaxes the mod-0 filter when searching by PIID (shows all mods); API always filters to base awards only. |
| **NAICS filter** | `naics_code = %s` | `c.NaicsCode == request.Naics` | Equivalent |
| **Set-aside filter** | `set_aside_type = %s` | `c.SetAsideType == request.SetAside` | Equivalent |
| **Agency filter** | `agency_id = %s OR agency_name LIKE %agency%` — searches both ID and name | `LIKE %agency%` on `AgencyName` only | **DISCREPANCY** — CLI also matches by agency_id (exact); API only does name search. |
| **Vendor filter** | `vendor_uei = %s OR vendor_name LIKE %vendor%` — single `--vendor` flag searches both | Separate `VendorUei` (exact) and `VendorName` (LIKE) parameters | **Different UX** — CLI combines into one flag; API separates. Not a correctness issue but a usability difference. |
| **PIID filter** | `contract_id = %s` | `c.SolicitationNumber == request.Solicitation` | **DISCREPANCY** — CLI searches by `contract_id` (the PIID); API searches by `solicitation_number`. These are different fields. API has no PIID search. |
| **Date filters** | `date_signed >= %s / <= %s` | `c.DateSigned >= DateFrom / <= DateTo` | Equivalent |
| **Min/Max value** | Not available | `BaseAndAllOptions >= MinValue / <= MaxValue` | API-only. |
| **Sort** | `ORDER BY date_signed DESC` (fixed) | Default `DateSigned DESC`, supports `value`, `vendorName`, `agencyName` | API richer. |
| **Columns returned** | 9 columns | 19 fields in DTO | API returns more data. |

**Summary:** 3 discrepancies — mod-0 filter behavior, agency filter scope, PIID vs solicitation number confusion.

---

### 4. Exclusion Check

**CLI:** `fed_prospector/cli/exclusions.py` `_check_local_only()` (lines 207-243)
**API:** `api/src/FedProspector.Infrastructure/Services/EntityService.cs` `CheckExclusionAsync()` (lines 232-274)

| Aspect | CLI (Python raw SQL) | API (EF Core) | Discrepancy |
|--------|---------------------|---------------|-------------|
| **UEI lookup** | `SELECT * FROM sam_exclusion WHERE uei = %s` | `ex.Uei == uei` | Equivalent |
| **Name lookup** | `WHERE entity_name LIKE %name%` (user provides name directly) | Looks up entity name from `entity` table by UEI, then `ex.EntityName.Contains(entityName)` | **Different approach** — CLI requires user to provide name; API auto-resolves name from entity table. API approach is richer. |
| **Active filter** | No date filter — returns ALL exclusions (active and terminated) | `ex.TerminationDate == null OR ex.TerminationDate > DateOnly.FromDateTime(DateTime.UtcNow)` | **DISCREPANCY** — CLI returns terminated exclusions too; API filters to active only. |
| **Combined search** | Either UEI or name (user chooses) | Always UEI, plus auto-adds entity name match if entity exists | **Different semantics** — API casts a wider net by also name-matching. |
| **Response format** | Prints all columns from sam_exclusion | Returns structured `ExclusionCheckDto` with IsExcluded boolean, ActiveExclusions list, CheckedAt timestamp | API is richer. |

**Summary:** 2 discrepancies — active-only filter in API but not CLI, and name resolution approach differs.

---

### 5. Prospect Management

**CLI:** `fed_prospector/etl/prospect_manager.py` + `fed_prospector/cli/prospecting.py`
**API:** `api/src/FedProspector.Infrastructure/Services/ProspectService.cs`

| Aspect | CLI (Python raw SQL) | API (EF Core) | Discrepancy |
|--------|---------------------|---------------|-------------|
| **Multi-tenancy** | No organization_id concept — single-tenant | All queries filter by `organizationId` | **MAJOR DISCREPANCY** — CLI has no org isolation. This is expected (CLI is admin tool) but creates data integrity risk if used alongside API. |
| **User resolution** | By username string | By user_id integer (from auth token) | Different but expected. |
| **Status flow** | Identical `STATUS_FLOW` dict | Identical `StatusFlow` dict | Equivalent |
| **Terminal statuses** | Identical set | Identical set | Equivalent |
| **Create prospect** | Validates notice_id, resolves username to user_id, INSERT, auto-note | Same + validates org membership, auto-calculates Go/No-Go score, creates notification | **API is richer** — adds scoring, notifications, org validation. |
| **List prospects** | `JOIN opportunity o ON p.notice_id = o.notice_id LEFT JOIN app_user u ON p.assigned_to = u.user_id ORDER BY o.response_deadline ASC` | Same join structure but adds NAICS/SetAside correlated subquery filters, CaptureManager join, proper pagination, multiple sort options | API is richer. |
| **Detail view** | `SELECT p.*, o.*, u.*` — 3 queries (prospect+opp, notes, team) | Same pattern but adds proposal data, richer DTOs | API is richer. |
| **Note types** | Allows manual STATUS_CHANGE notes | Blocks manual STATUS_CHANGE (system-only) | **DISCREPANCY** — CLI lets users manually create STATUS_CHANGE notes; API correctly prevents this. |

**Summary:** 2 material discrepancies — no org isolation in CLI, STATUS_CHANGE note type validation differs.

---

### 6. Saved Search

**CLI:** `fed_prospector/etl/prospect_manager.py` `run_search()` (lines 727-866)
**API:** `api/src/FedProspector.Infrastructure/Services/SavedSearchService.cs` `RunAsync()` (lines 74-173)

| Aspect | CLI (Python raw SQL) | API (EF Core) | Discrepancy |
|--------|---------------------|---------------|-------------|
| **Filter: set_aside_codes** | `o.set_aside_code IN (...)` | `.Where(o => criteria.SetAsideCodes.Contains(o.SetAsideCode))` | Equivalent |
| **Filter: naics_codes** | `o.naics_code IN (...)` | `.Where(o => criteria.NaicsCodes.Contains(o.NaicsCode))` | Equivalent |
| **Filter: states** | `o.pop_state IN (...)` | `.Where(o => criteria.States.Contains(o.PopState))` | Equivalent |
| **Filter: min/max_award_amount** | `o.award_amount >= / <=` | `o.AwardAmount >= / <=` | Equivalent |
| **Filter: open_only** | `o.response_deadline > NOW() AND o.active = 'Y'` | `o.Active == "Y" AND o.ResponseDeadline > DateTime.UtcNow` | Equivalent |
| **Filter: types** | `o.type IN (...)` | `.Where(o => criteria.Types.Contains(o.Type))` | Equivalent |
| **Filter: days_back** | `o.posted_date >= DATE_SUB(CURDATE(), INTERVAL %s DAY)` | `o.PostedDate >= DateOnly.FromDateTime(DateTime.UtcNow.AddDays(-criteria.DaysBack.Value))` | Equivalent |
| **New count logic** | Python loop: compare `first_loaded_at > last_run` in application code | EF Core: `COUNT(o => o.FirstLoadedAt > search.LastRunAt)` — SQL-side | **Implementation difference** — CLI counts in Python (loads all 200 rows first); API counts in SQL. Same result but API is more efficient. |
| **Result limit** | LIMIT 200 | Take(200) | Equivalent |
| **Sort** | `ORDER BY o.response_deadline ASC` | `OrderBy(o.ResponseDeadline)` | Equivalent |
| **Lookup** | By search_id or search_name | By search_id only (user-scoped) | CLI allows name lookup; API requires ID. |

**Summary:** No material discrepancies. Well-aligned.

---

### 7. Dashboard

**CLI:** `fed_prospector/etl/prospect_manager.py` `get_dashboard_data()` + `cli/prospecting.py` `dashboard()`
**API:** `api/src/FedProspector.Infrastructure/Services/DashboardService.cs` `GetDashboardAsync()`

| Aspect | CLI | API | Discrepancy |
|--------|-----|-----|-------------|
| **Multi-tenancy** | No org filter | Filters by `organizationId` | Expected divergence (CLI is admin tool). |
| **Pipeline value** | Not calculated | `SUM(EstimatedValue)` for open prospects | API-only. |
| **Parallelism** | Sequential queries | `Task.WhenAll` for 7 parallel queries | API is more performant. |
| **Data structure** | Dict with by_status, due_this_week, by_assignee, win_loss, saved_searches | Rich DTO with same concepts + PipelineValue | API richer. |

**Summary:** No material discrepancies beyond expected multi-tenancy difference.

---

## Discrepancy Summary

### Critical (different results for same input)

| # | Area | Issue | Impact |
|---|------|-------|--------|
| 1 | Entity NAICS filter | CLI searches all NAICS (child table); API checks primary_naics only | API misses entities where the searched NAICS is secondary |
| 2 | Entity cert filter | CLI filters expired certs; API does not | API returns entities with expired SBA certifications |
| 3 | Entity address type case | CLI uses `'PHYSICAL'`; API uses `"physical"` | PopState may be null in API if data stores uppercase |
| 4 | Exclusion active filter | CLI returns all exclusions; API filters to active only | CLI shows terminated exclusions that API hides |
| 5 | Award mod-0 filter | CLI relaxes for PIID search; API always enforces | API cannot show modification history for a contract |

### Moderate (different capabilities or semantics)

| # | Area | Issue | Impact |
|---|------|-------|--------|
| 6 | Opportunity date filter | CLI always filters by posted_date (default 30d); API has no mandatory date filter | API can return all-time data; CLI always scopes to recent |
| 7 | Award agency filter | CLI searches agency_id OR name; API searches name only | API misses agency_id exact matches |
| 8 | Award PIID filter | CLI uses contract_id; API uses solicitation_number | Different fields entirely — API has no PIID search |
| 9 | Prospect CLI no org isolation | CLI has no organization_id filtering | CLI operates as global admin; safe for single-tenant but risky for multi-tenant |
| 10 | Prospect STATUS_CHANGE notes | CLI allows manual creation; API blocks it | CLI can create misleading system notes |

---

## Recommended Approach

After evaluating the four standardization options:

### Decision: Hybrid approach — Views for shared read queries + Accept divergence for admin-only CLI

**Rationale:**

1. **MySQL Views** (for items 1-5, 7-8): Create views that encode the "correct" query logic for entity search, exclusion checks, and award search. Both CLI and API query these views. This ensures filter logic consistency without requiring the API to drop to raw SQL or the CLI to use EF Core.

2. **Raw SQL in API** (for item 8 only): Add a PIID filter to AwardService. This is a missing feature, not a shared-logic issue.

3. **Accept divergence** (for items 6, 9, 10): The CLI is an admin/developer tool with different UX requirements. Mandatory date filtering, no org isolation, and permissive note types are intentional CLI behaviors. Document them clearly.

4. **Stored procedures**: Not recommended. They add deployment complexity, are harder to test, and don't integrate well with EF Core's LINQ-to-SQL pipeline.

### View Definitions

```sql
-- v_entity_search: Encodes correct NAICS/cert/address logic
CREATE OR REPLACE VIEW v_entity_search AS
SELECT
    e.uei_sam, e.legal_business_name, e.dba_name, e.cage_code,
    e.primary_naics, e.registration_status, e.entity_structure_code,
    e.registration_expiration_date, e.last_update_date, e.entity_url,
    e.exclusion_status_flag,
    ea.state_or_province AS pop_state,
    ea.congressional_district
FROM entity e
LEFT JOIN entity_address ea ON e.uei_sam = ea.uei_sam
    AND ea.address_type = 'PHYSICAL';

-- v_active_exclusions: Only active (non-terminated) exclusions
CREATE OR REPLACE VIEW v_active_exclusions AS
SELECT *
FROM sam_exclusion
WHERE termination_date IS NULL
   OR termination_date > CURDATE();

-- v_base_awards: Base awards only (mod 0)
CREATE OR REPLACE VIEW v_base_awards AS
SELECT *
FROM fpds_contract
WHERE modification_number = '0';
```

---

## Task Breakdown

### Phase 42A: Fix Critical Discrepancies

- [x] **42A-1**: Fix API entity NAICS filter to use EXISTS on entity_naics (match CLI behavior)
- [x] **42A-2**: Fix API entity cert filter to check certification_exit_date (match CLI behavior)
- [x] **42A-3**: Fix API entity address type case — stored as PHYSICAL (uppercase), fixed API to match
- [x] **42A-4**: Add PIID filter to AwardService.SearchAsync
- [x] **42A-5**: Add option to AwardService to show all mods when searching by PIID/contract_id

### Phase 42B: Create MySQL Views

- [x] **42B-1**: Create `v_entity_search` view
- [x] **42B-2**: Create `v_active_exclusions` view
- [x] **42B-3**: Create `v_base_awards` view
- [x] **42B-4**: Update CLI entity search to use `v_entity_search`
- [x] **42B-5**: Update CLI exclusion check to offer active-only option (default active)
- [x] **42B-6**: ~~Map EF Core keyless entities to the new views~~ — Skipped. API queries already have correct filters from 42A. Mapping views to EF Core keyless entities adds constraints (no tracking, no Include) without benefit. Views are for CLI standardization; API uses LINQ.

### Phase 42C: Add Missing API Capabilities

- [x] **42C-1**: Add agency_id filter to AwardService (OR with agency_name LIKE)
- [x] **42C-2**: Add `--keyword` and `--department` filters to CLI opportunity search (parity with API)
- [x] **42C-3**: Block manual STATUS_CHANGE notes in CLI prospect manager

### Phase 42D: Documentation & Tests

- [x] **42D-1**: Document accepted divergences (CLI date filter, no org isolation) in this file — see Accepted Divergences table above
- [ ] **42D-2**: Add integration tests verifying CLI and API return same results for common queries (deferred — requires live DB)
- [ ] **42D-3**: Add comments in both CLI and API code referencing this standardization doc (deferred)

---

## Accepted Divergences (No Action Needed)

| Item | Rationale |
|------|-----------|
| CLI opportunity search always filters by posted_date | CLI is a quick-lookup tool; mandatory date filter prevents accidentally scanning millions of rows |
| CLI has no organization_id filtering | CLI is an admin/developer tool for single-tenant local use |
| ~~CLI allows manual STATUS_CHANGE notes~~ | Fixed in 42C-3 — now blocked in CLI too |
| API has richer pagination, sorting, joins | API serves a rich UI; CLI is a simple terminal tool |
| API includes prospect status in opportunity search | Multi-tenant enrichment not applicable to CLI |
| Dashboard: CLI has no pipeline value | CLI dashboard is a simple summary; API serves charts |

---

## Dependencies

- Phase 42A can start immediately (no prerequisites)
- Phase 42B depends on 42A being complete (views encode the corrected logic)
- Phase 42C and 42D can run in parallel with 42B

## Risks

1. **EF Core keyless entity mapping**: Views without a PK require `HasNoKey()` in DbContext. Already done for `v_target_opportunities`, so the pattern is established.
2. **Address type case**: Need to check actual data in `entity_address.address_type` column before fixing. If data is mixed case, a migration may be needed.
3. **NAICS filter performance**: Switching API from `primary_naics` column to `EXISTS` subquery may be slower for large result sets. Benchmark before and after.

## Estimated Effort

| Sub-phase | Tasks | Estimated Hours |
|-----------|-------|-----------------|
| 42A: Critical fixes | 5 tasks | 3-4 hours |
| 42B: MySQL views | 6 tasks | 2-3 hours |
| 42C: Missing features | 3 tasks | 2-3 hours |
| 42D: Docs & tests | 3 tasks | 2-3 hours |
| **Total** | **17 tasks** | **9-13 hours** |
