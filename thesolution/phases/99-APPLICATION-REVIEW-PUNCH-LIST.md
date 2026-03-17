# Phase 99: Application Review Punch List

**Status**: PLANNED
**Priority**: Mixed (bugs = high, improvements = medium, tech debt = low)
**Created**: 2026-03-16
**Source**: Automated high-level review + manual validation across all layers

---

## Summary

Full-stack skim review of the FedProspect application. Initial automated review found 109 items; manual code validation removed 13 bogus findings and downgraded 9 overstated ones. **76 validated items remain.**

---

## 1. DATABASE SCHEMA (6 items)

### Consistency

| # | File | Issue |
|---|------|-------|
| DB-1 | Multiple DDL files | FK naming inconsistent: some use 3-letter prefix (`fk_addr_entity`), others long names (`fk_prospect_opp`) |
| DB-2 | `70_usaspending.sql:108` | `usaspending_load_checkpoint` uses `utf8mb4_0900_ai_ci` while all other tables use `utf8mb4_unicode_ci` |
| DB-3 | `20_entity.sql` | `stg_entity_raw` has no FK to `entity`, unlike other staging tables in `80_raw_staging.sql` |

### Tech Debt

| # | File | Issue |
|---|------|-------|
| DB-4 | History tables (`opportunity_history`, `entity_history`, `etl_load_error`, `activity_log`) | No partitioning strategy for high-volume tables. `etl_load_error` grows unbounded |

### Improvements

| # | File | Issue |
|---|------|-------|
| DB-5 | `60_prospecting.sql` | Some FK columns lack explicit indexes (`prospect.organization_id`, `prospect.assigned_to`) |
| DB-6 | `40_federal.sql` | `federal_organization.parent_org_id` has no self-referencing FK (likely intentional for ETL insert-order, but worth documenting) |

#### Removed after validation
- ~~DB-2 (soft-delete conflict)~~: Soft-delete IS the solution — comment in DDL explains it
- ~~DB-8 (quality rules abandoned)~~: `data_cleaner.py` queries `etl_data_quality_rule`; `entity_loader.py` uses it

---

## 2. ETL PIPELINE (15 items)

### Bugs

| # | File | Issue |
|---|------|-------|
| ETL-1 | `api_clients/base_client.py:293-296` | `get()` mutates caller's `params` dict by adding `api_key`. `paginate()` has a copy-fix, but direct `get()` callers are exposed |

### Improvements

| # | File | Issue |
|---|------|-------|
| ETL-2 | Multiple loaders | Broad `except Exception` without logging which record/context failed (data_cleaner:108, calc_loader:105, bulk_loader:202) |
| ETL-3 | All loaders | No retry logic for transient DB failures (deadlocks, connection timeouts). Only `BaseAPIClient` has retries |
| ETL-4 | `etl/load_manager.py` | No DB connection health check before `start_load()` — silent pool exhaustion possible |
| ETL-5 | Multiple loaders | Batch sizes hardcoded as class constants (entity=1000, opportunity=500, awards=500) — not configurable |
| ETL-6 | `etl/batch_upsert.py` | No deadlock retry on `INSERT...ON DUPLICATE KEY` — concurrent loads will crash |
| ETL-7 | `etl/staging_mixin.py:136-149` | Batch insert silently falls back to row-by-row without logging which rows failed |
| ETL-8 | All loaders | If `etl_load_error` insert fails, final error count is wrong |
| ETL-9 | All loaders | No rollback strategy on partial load failure — committed batches can't be unwound |
| ETL-10 | `api_clients/base_client.py:210-215` | Rate counter incremented before response parsing — quota consumed for malformed responses |
| ETL-11 | `api_clients/base_client.py:250-260` | 503 (Service Unavailable) not retried — treated as immediate failure |
| ETL-12 | `api_clients/base_client.py:422-429` | `max_pages` pagination cutoff logged as warning — callers unaware results are incomplete |

### Tech Debt

| # | File | Issue |
|---|------|-------|
| ETL-13 | `db/connection.py:38-47` | Monkey-patches `PooledMySQLConnection` — will break silently on library upgrade |
| ETL-14 | `db/connection.py` | Pool size from `settings.DB_POOL_SIZE` but default and tuning guidance undocumented |
| ETL-15 | All API clients | No request deduplication — retry after network error may cause duplicate inserts |

#### Removed after validation
- ~~ETL-1 (change detector OOM)~~: Documented design choice for single-process CLI; justified in docstring
- ~~ETL-2 (staging returns None)~~: Callers explicitly handle None; documented behavior
- ~~ETL-3 (get_cursor no rollback)~~: Documented as read-only; implicit rollback on connection close
- ~~ETL-4 (rate limit race)~~: Single-process CLI; atomic increment; worst case = 1 extra API call

---

## 3. C# API LAYER (15 items)

### Bugs

| # | File | Issue |
|---|------|-------|
| API-1 | `Middleware/CsrfMiddleware.cs:22-28` | **CSRF bypass on refresh** — `/auth/refresh` is CSRF-exempt but uses cookie auth. Attacker could refresh a session without XSRF token |

### Consistency

| # | File | Issue |
|---|------|-------|
| API-2 | All controllers | Inconsistent null checks on `ResolveOrganizationIdAsync()` / `GetCurrentUserId()` — order and placement varies |
| API-3 | `ProspectService.cs`, `ProposalService.cs` | Mixed exception types for missing resources — `KeyNotFoundException` vs `InvalidOperationException` |
| API-4 | `AwardsController.cs:34,52` | Invalid `years`/`limit`/`offset` silently coerced instead of returning 400 |
| API-5 | Controllers + `Program.cs` | Rate limit policy names are magic strings (`"auth"`, `"search"`, `"write"`) — no constants |

### Improvements

| # | File | Issue |
|---|------|-------|
| API-6 | `EntitiesController.cs:35,42`, `SubawardsController.cs:34` | No length/format validation on `uei` and `primePiid` string params |
| API-7 | `ProspectService.cs:46`, `ProposalService.cs:54` | `CreateAsync()` assumes non-null request — no defensive guard |
| API-8 | All delete services | No FK validation before delete — cryptic DB error instead of user-friendly 400 |
| API-9 | `ProspectService.cs:112-119` | Go/No-Go scoring failure swallowed — prospect created but no activity log for the error |
| API-10 | `SecurityHeadersMiddleware.cs:17-18` | CSP has `unsafe-inline` for styles, no env-specific config for CDN/fonts |
| API-11 | `Program.cs:179-189` | CORS falls back to `localhost:5173` if config missing — safe default but should log a warning in non-dev |

### Tech Debt

| # | File | Issue |
|---|------|-------|
| API-12 | `ProspectService.cs:19-30`, `ProposalService.cs:19-25` | Status flow dictionaries hardcoded as static fields — not database-configurable |
| API-13 | `ForcePasswordChangeMiddleware.cs:25-27` | Allowed paths hardcoded — new auth endpoints must be manually added |

### Test Coverage Gaps

| # | Missing Tests | Impact |
|---|---------------|--------|
| API-14 | `ReferenceController` — no test file | Low (read-only static data) |
| API-15 | 8 services missing tests: `CompanyProfileService`, `ExpiringContractService`, `MarketIntelService`, `OrganizationEntityService`, `PWinService`, `QualificationService`, `RecommendedOpportunityService`, `AutoProspectService` | High (Phase 45+ intelligence features untested) |

#### Removed after validation
- ~~API-1 (entity search no org isolation)~~: Entities are shared SAM.gov reference data — all users should search the same catalog. By design.
- ~~API-3 (DateTime.Now timezone)~~: ETL writes local time; `DateTime.Now` is correct per inline comment
- ~~API-5 (duplicate entity links)~~: `LinkEntityAsync()` checks for existing active/inactive links before creating
- ~~API-11 (pageSize not clamped)~~: `PagedRequest.PageSize` setter clamps 1-100; FluentValidation also enforces
- ~~API-13 (no activity logs)~~: Both `ResetPasswordAsync` and `UpdateUserAsync` call `_activityLogService.LogAsync`
- ~~API-17 (JWT dev-only validation)~~: Standard ASP.NET Core practice; intentional

---

## 4. REACT UI (29 items)

### Bugs

| # | File | Issue |
|---|------|-------|
| UI-1 | `pages/login/LoginPage.tsx:94` | Non-Axios errors assumed to be "network error" without type checking |
| UI-2 | `pages/awards/AwardDetailPage.tsx` | Multiple `useQuery` calls but error state doesn't distinguish which sub-query failed |

### Improvements

| # | File | Issue |
|---|------|-------|
| UI-3 | `api/client.ts` | No `timeout` on axios instance — requests can hang indefinitely |
| UI-4 | `pages/dashboard/DashboardPage.tsx:27` | Only `useDashboard` loading state shown — other queries load without skeletons |
| UI-5 | `pages/prospects/ProspectDetailPage.tsx` | `useRemoveTeamMember` has no error UI — silent failure |
| UI-6 | `auth/AuthContext.tsx:34-48` | `refreshSession` doesn't notify user of network errors — silent failure for transient issues |
| UI-7 | `pages/admin/UserManagementTab.tsx:92` | `navigator.clipboard.writeText` has no error handling |
| UI-8 | `pages/organization/OrgEntitiesTab.tsx:111-116` | No UEI format validation before API call — wasted requests |
| UI-9 | `pages/organization/OrgEntitiesTab.tsx:68-96` | Mutations invalidate query keys but `searchResults` is local state — won't auto-update |
| UI-10 | `pages/organization/OrganizationPage.tsx` | No error boundary per lazy-loaded tab — one tab failure crashes entire page |
| UI-11 | `pages/setup/CompanySetupWizard.tsx:86-88` | No cross-step validation — user can proceed with invalid data |

### Consistency

| # | File | Issue |
|---|------|-------|
| UI-12 | `routes.tsx:59-77` | `NotFoundLayout` checks `isLoading` but shows blank instead of spinner |
| UI-13 | `queries/*` | Stale times vary widely (30s to 10m) with no documented rationale |
| UI-14 | All pages | Mixed error patterns: some use `useSnackbar()`, others local state + `Alert`, others silent |
| UI-15 | `components/shared/TabbedDetailPage.tsx` | Missing `aria-labelledby` / `role="tablist"` attributes |
| UI-16 | `components/shared/DataTable.tsx` | Skeleton/loading patterns inconsistent — `EmptyState` vs `LoadingState` variants |
| UI-17 | `pages/dashboard/DashboardPage.tsx` | Three data sections load independently with no skeleton placeholders |
| UI-18 | `pages/admin/OrganizationsTab.tsx` | No loading skeleton while organizations are fetching |

### Tech Debt

| # | File | Issue |
|---|------|-------|
| UI-19 | `pages/login/RegisterPage.tsx:76-95` | Complex error type guards — should use `axios.isAxiosError()` like LoginPage |
| UI-20 | `pages/profile/ProfilePage.tsx`, `pages/change-password/ChangePasswordPage.tsx` | Password validation regex duplicated across 2 files — extract to shared validator |
| UI-21 | `types/api.ts:73-75` | Both `resourceLinkDetails?: ResourceLinkDto[]` and `resourceLinks?: string | null` exist — redundant |
| UI-22 | `api/client.ts:27-30` | Module-level refresh state (`isRefreshing`, `failedQueue`) — no cross-tab coordination |
| UI-23 | `pages/organization/OrgEntitiesTab.tsx:105-126` | Entity search uses manual `await` instead of `useQuery` — misses caching/retry |
| UI-24 | 4 files: `SavedSearchesPage`, `AwardSearchPage`, `TargetOpportunityPage`, `OpportunitySearchPage` | `SET_ASIDE_OPTIONS` duplicated — extract to shared constants |
| UI-25 | Multiple detail pages | `buildPlaceOfPerformance` helper duplicated — extract to utility |

### Accessibility

| # | File | Issue |
|---|------|-------|
| UI-26 | `components/shared/DataTable.tsx` | `aria-label` prop provided but rarely used by instances |
| UI-27 | `pages/opportunities/QualificationPWinTab.tsx:26-34` | `PWIN_FORMULA` table has no semantic `<table>` element or headers |
| UI-28 | `components/layout/Sidebar.tsx` | No `aria-current="page"` on active nav item |
| UI-29 | `pages/login/LoginPage.tsx` | Form fields missing `autoComplete` attributes (`email`, `current-password`) |

#### Removed after validation
- ~~UI-1 (linkMutation no onError)~~: Error IS displayed via `linkMutation.isError` in JSX — different pattern, not silent
- ~~UI-2 (ChangePasswordPage error handling)~~: Uses `axios.isAxiosError()` correctly with proper fallback
- ~~UI-5 (fragile CSRF parsing)~~: `.slice(1).join('=')` correctly handles `=` in values — standard idiom
- ~~UI-7 (exportOpportunities dead code)~~: Called on line 273 — not dead code
- ~~UI-13 (stale prospect count)~~: Marginal staleness, not a bug — staleTime handles eventual consistency

---

## 5. PYTHON CLI (8 items)

### Improvements

| # | File | Issue |
|---|------|-------|
| CLI-1 | `cli/exclusions.py:56-57` | "No API calls remaining" error doesn't suggest `--key=1` fallback |
| CLI-2 | `cli/subaward.py:67-71` | Error leaks implementation details ("2.7M+ records across 2,700+ pages") |
| CLI-3 | `cli/prospecting.py:150-157` | Inconsistent exit codes — some commands use `sys.exit(1)`, others don't |

### Consistency

| # | File | Issue |
|---|------|-------|
| CLI-4 | `cli/database.py:125-130` | Mixed severity logging — `logger.warning()` for SQL errors vs `logger.error()` + `sys.exit()` elsewhere |
| CLI-5 | `cli/health.py:32-35` | `hc.save_snapshot()` failure only logged as warning, not reported to user |
| CLI-6 | `cli/schedule_setup.py:149-174` | Subprocess failures printed to click but not logged |
| CLI-7 | `cli/load_batch.py:41-140` | `dry_run` flag checked in 6+ places — duplicated logic |

### Tech Debt

| # | File | Issue |
|---|------|-------|
| CLI-8 | `cli/prospecting.py` | CLI commands mixed with business logic — no consistent wrapper/error handling |

#### Removed after validation
- ~~CLI-1 (records_deleted KeyError)~~: `load_delta()` always returns `records_deleted` key
- ~~CLI-2 (SAM_API_KEY_2 not validated)~~: Validation covers both keys with placeholder check
- ~~CLI-3 (string-to-int api_key)~~: Works correctly, Click validates input
- ~~CLI-7 (batch_size not validated)~~: Minor gap, no crash or corruption possible
- ~~CLI-13 (duplicate JOBS)~~: Sequences and definitions are complementary, not duplicated
- ~~CLI-15 (hardcoded NAICS)~~: Configurable via `DEFAULT_AWARDS_NAICS` env var

---

## 6. TEST COVERAGE GAPS (9 items)

### Python Tests

| # | Module | Coverage |
|---|--------|----------|
| TEST-1 | `etl/demand_loader.py` | No tests |
| TEST-2 | `etl/resource_link_resolver.py` | No tests |
| TEST-3 | CLI: `calc`, `fedhier`, `spending`, `exclusions`, `subaward` commands | Not covered in test_cli_load.py |
| TEST-4 | CLI: All 8 admin commands | No test_cli_admin.py |
| TEST-5 | CLI: `update` commands (link-metadata, fetch-descriptions, build-relationships) | No tests |
| TEST-6 | CLI: `demand` process-requests | No tests |

### C# Tests

| # | Module | Coverage |
|---|--------|----------|
| TEST-7 | `ReferenceController` — no test file | Low impact (read-only static data) |
| TEST-8 | 8 intelligence services: CompanyProfileService, ExpiringContractService, MarketIntelService, OrganizationEntityService, PWinService, QualificationService, RecommendedOpportunityService, AutoProspectService | High impact (Phase 45+ features untested) |

### Known Failures

| # | Test | Status |
|---|------|--------|
| TEST-9 | `test_prospect_manager.py::test_all_valid_note_types_accepted[STATUS_CHANGE]` | Pre-existing failure (Phase 94) |

---

## Priority Tiers

### Tier 1 — Security & Real Bugs (4 items)
- **API-1**: CSRF bypass on `/auth/refresh` endpoint
- **ETL-1**: `get()` mutates caller's params dict (direct callers only)
- **UI-1**: LoginPage non-Axios error handling
- **API-11**: CORS should warn in non-dev when falling back to default

### Tier 2 — Reliability & Resilience (11 items)
- **ETL-3/6**: No DB retry logic or deadlock retry
- **ETL-4**: No connection health check before loads
- **ETL-7**: Silent staging batch fallback
- **ETL-11**: 503 not retried
- **UI-3**: No axios timeout
- **UI-10**: No error boundary per org tab
- **API-8**: No FK validation before deletes

### Tier 3 — Consistency & UX (20 items)
- **UI-12-18**: Loading state inconsistencies
- **UI-14**: Mixed error notification patterns
- **API-2-5**: Controller consistency
- **CLI-3-7**: CLI consistency

### Tier 4 — Tech Debt & Test Gaps (21 items)
- **TEST-8**: 8 intelligence services have no tests
- **TEST-3-6**: CLI commands lacking test coverage
- **UI-19-25**: Code duplication
- **ETL-13-15**: Connection pool fragility
- **DB-4**: Table partitioning

---

## Metrics

| Layer | Bugs | Improvements | Consistency | Tech Debt | Total |
|-------|------|-------------|-------------|-----------|-------|
| Database | 0 | 2 | 3 | 1 | **6** |
| ETL/API Clients | 1 | 11 | 0 | 3 | **15** |
| C# API | 1 | 6 | 4 | 2 + 2 test gaps | **15** |
| React UI | 2 | 9 | 7 | 7 + 4 a11y | **29** |
| Python CLI | 0 | 3 | 4 | 1 | **8** |
| Test Gaps | — | — | — | 9 | **9** |
| **Total** | **4** | **31** | **18** | **23** | **76** |

---

## Validation Notes

This document was produced in two passes:
1. **Automated review** (4 parallel agents) — scanned DB, ETL, API, UI, CLI layers. Found 109 items.
2. **Manual validation** (4 parallel agents) — read actual source code to confirm/reject each finding.

**Removed 13 bogus findings** where the code was correct and the reviewer misread it. **Downgraded 9 overstated findings** where the issue was technically true but either by design, documented, or not practically exploitable. Remaining 76 items are validated against source code.
