# Phase 14: Testing Strategy — Unit, Integration, Regression & E2E

**Status**: COMPLETE (2026-03-01)
**Dependencies**: Phase 10 (API Foundation) in progress; Python ETL (Phases 1-9) complete
**Deliverable**: 920 tests passing (568 Python + 234 C# Core + 118 C# Api) across 59 test files
**Repository**: `fed_prospector/tests/` (Python), `api/tests/` (C#), `ui/tests/` (future)

---

## Overview

This phase establishes a formal testing strategy across all three layers of the system: the Python ETL pipeline, the C# Web API, and the eventual frontend UI. Testing has been deferred until now (Phase 1 noted "tested via integration") — this phase formalizes what to test, how to test it, and what tooling to use.

**Guiding principles**:
- Every test must be runnable without AI, a live database, or external APIs (except integration tests)
- Tests must run fast enough to include in a pre-commit or CI workflow
- Prefer real data fixtures over excessive mocking
- Test the boundaries: API response parsing, SQL generation, validation rules, auth flows

---

## Test Pyramid

```
         ┌─────────┐
         │  E2E    │   Few — critical user journeys only
         │ (UI)    │
        ─┼─────────┼─
        │Integration│   Moderate — real DB, real API stubs
        │(API+ETL) │
       ─┼──────────┼─
       │  Unit Tests │   Many — fast, isolated, no I/O
       │(all layers)│
       └────────────┘
```

---

## 14.1 Python ETL Test Suite

**Location**: `fed_prospector/tests/`
**Framework**: `pytest` + `pytest-mock` + `pytest-cov`
**Run command**: `pytest fed_prospector/tests/ -v --cov=fed_prospector`

### 14.1.1 Unit Tests (no DB, no network)

#### API Client Tests
- [x] `test_sam_opportunity_client.py` — query parameter construction, pagination logic, response parsing
- [ ] `test_sam_entity_client.py` — search param building, WOSB/8(a) filter construction
- [ ] `test_sam_extract_client.py` — URL construction for monthly/daily extracts, ZIP handling logic
- [x] `test_sam_awards_client.py` — award search params, NAICS/awardee/solicitation filtering
- [x] `test_sam_exclusions_client.py` — UEI/name lookup construction, v4 response parsing
- [x] `test_sam_subaward_client.py` — subcontract search params, response normalization
- [x] `test_sam_fedhier_client.py` — hierarchy traversal, agency search
- [x] `test_usaspending_client.py` — POST body construction, award/transaction response mapping
- [x] `test_calc_client.py` — labor rate query params, pagination
- [x] `test_base_client.py` — retry logic (exponential backoff), rate limit checking, error classification

#### Data Quality Tests
- [x] `test_data_cleaner.py` — all 10+ cleaning rules individually
  - ZIP code parsing (5-digit, 9-digit, international)
  - Date format normalization (various SAM.gov formats)
  - Phone number cleaning
  - DUNS/UEI validation
  - Null/empty string handling
  - Unicode normalization
  - Whitespace trimming
  - Country code mapping
  - State code validation
  - Business type code normalization
- [x] `test_date_utils.py` — date parsing and formatting utilities
- [x] `test_parsing_utils.py` — field parsing and extraction utilities

#### Loader Logic Tests (no DB)
- [x] `test_opportunity_loader_logic.py` — SHA-256 hash computation, change detection logic, field mapping
- [ ] `test_entity_loader_logic.py` — JSON normalization for 1+8 entity tables, hash comparison
- [x] `test_awards_loader_logic.py` — FPDS field mapping, deduplication logic
- [x] `test_usaspending_loader_logic.py` — award/transaction mapping, burn rate calculation formula
- [x] `test_dat_parser.py` — V2 DAT file parsing, field extraction, delimiter handling
- [x] `test_bulk_loader.py` — bulk loading logic, LOAD DATA INFILE construction

#### Utility Tests
- [x] `test_config.py` — .env loading, default values, missing key handling
- [x] `test_db_pool.py` — connection string construction (no actual connections)
- [x] `test_scheduler.py` — job definition validation, schedule parsing, threshold checks
- [x] `test_health_check.py` — health check logic, freshness thresholds
- [x] `test_change_detector.py` — SHA-256 change detection logic

#### Scoring and Business Logic
- [x] `test_prospect_scoring.py` — Go/No-Go scoring (4 criteria, 0-40 scale), edge cases (missing data, boundary values)
- [x] `test_status_flow.py` — prospect status transitions (valid and invalid), STATUS_FLOW enforcement

### 14.1.2 Integration Tests (require MySQL)

**Prereq**: MySQL running, `fed_contracts_test` database (separate from production)
**Run command**: `pytest fed_prospector/tests/integration/ -v --db-test`
**Fixture strategy**: Create/destroy test database per session, seed with minimal reference data

- [ ] `test_build_database.py` — DDL execution creates all 54 tables + 4 views, idempotent rebuild
- [ ] `test_check_schema.py` — schema drift detection catches added/removed columns, missing tables
- [ ] `test_bulk_loader_integration.py` — LOAD DATA INFILE with small fixture files, verify row counts
- [ ] `test_entity_loader_integration.py` — load sample entities, verify change detection on reload
- [ ] `test_opportunity_loader_integration.py` — load + update cycle, verify history records created
- [ ] `test_prospect_manager_integration.py` — full prospect lifecycle: create → assign → score → decide
- [ ] `test_saved_search_integration.py` — save, execute, verify results against seeded data
- [ ] `test_health_check_integration.py` — verify freshness thresholds against known load timestamps
- [ ] `test_db_maintenance_integration.py` — archive, purge staging, ANALYZE runs without error

### 14.1.3 Regression Tests

- [ ] `test_regression_data_quality.py` — replay known-bad records from production (anonymized fixtures) through the cleaner, verify all 18 documented issues are handled
- [ ] `test_regression_api_responses.py` — replay captured API response JSON fixtures through parsers, verify no field mapping regressions
- [ ] `test_regression_hash_stability.py` — verify SHA-256 hash computation is deterministic across Python versions (same input → same hash)

### 14.1.4 Test Fixtures

- [x] Create `fed_prospector/tests/fixtures/` directory — 8 JSON fixture files
- [ ] `api_responses/` — captured JSON responses from each SAM.gov sub-API (sanitized)
- [ ] `dat_files/` — small sample DAT extract files (10-20 records)
- [ ] `csv_files/` — reference data CSVs for test database seeding
- [ ] `bad_records/` — known-bad records that trigger each data quality rule
- [x] Shared `conftest.py` with autouse DB/API mocking

---

## 14.2 C# API Test Suite

**Location**: `api/tests/`
**Framework**: xUnit + Moq + FluentAssertions + WebApplicationFactory
**Run command**: `dotnet test api/` (runs all test projects)
**Existing scaffolding**: `FedProspector.Api.Tests` and `FedProspector.Core.Tests` projects exist (empty)

### 14.2.1 Unit Tests — FedProspector.Core.Tests (234 tests, 25 files)

#### Validator Tests (22 test files)
- [x] `LoginRequestValidatorTests.cs` — valid/invalid usernames, passwords, edge cases
- [x] `PagedRequestValidatorTests.cs` — page size bounds, negative page numbers, max limits
- [x] All Phase 11-13 validator tests (OpportunitySearch, AwardSearch, EntitySearch, SubawardTeamingPartnerSearch, TargetOpportunitySearch, SavedSearch, Prospect, Proposal, Notification, Auth, Admin, etc.)

#### DTO / Mapping Tests
- [x] `MappingProfileTests.cs` — AutoMapper configuration is valid, all mappings resolve
- [x] `PagedResponseTests.cs` — pagination math (total pages, has-next, has-previous)

#### Business Logic Tests (when added in Phase 12)
- [ ] `ProspectScoringTests.cs` — Go/No-Go scoring logic in C# (mirrors Python tests)
- [ ] `StatusFlowTests.cs` — prospect status transitions, invalid transition rejection
- [ ] `BurnRateCalculationTests.cs` — spend analysis calculation

### 14.2.2 Unit Tests — FedProspector.Api.Tests (118 tests, 11 files)

#### Middleware Tests
- [x] `ExceptionHandlerMiddlewareTests.cs` — maps exception types to HTTP status codes, response format
- [x] `SecurityHeadersMiddlewareTests.cs` — security headers added to responses

#### Controller Tests (with mocked services)
- [x] `HealthControllerTests.cs` — returns 200 with expected shape
- [x] `AuthControllerTests.cs` — login success/failure, token format, lockout after N failures
- [x] `OpportunitiesControllerTests.cs` — search params passed to service, pagination applied
- [x] `AwardsControllerTests.cs` — search + burn rate endpoint
- [x] `EntitiesControllerTests.cs` — search + exclusion check
- [ ] `ProspectsControllerTests.cs` — CRUD operations, status flow enforcement
- [ ] `ProposalsControllerTests.cs` — lifecycle transitions, document association
- [x] `DashboardControllerTests.cs` — aggregation queries return expected shape
- [x] `SubawardsControllerTests.cs` — teaming partner search
- [x] `AdminControllerTests.cs` — admin endpoints, user management
- [x] `SavedSearchesControllerTests.cs` — CRUD for saved searches
- [x] `NotificationsControllerTests.cs` — notification list, mark-read

### 14.2.3 Integration Tests (WebApplicationFactory + test DB)

**Strategy**: Use `WebApplicationFactory<Program>` with a test MySQL database (`fed_contracts_test`). Seed minimal data via EF Core migrations + test fixtures.

- [ ] `AuthIntegrationTests.cs` — register → login → access protected endpoint → logout → 401
- [ ] `OpportunitySearchIntegrationTests.cs` — seed opportunities, search by NAICS/set-aside, verify pagination
- [ ] `ProspectLifecycleIntegrationTests.cs` — create prospect → assign → add note → score → change status
- [ ] `ProposalLifecycleIntegrationTests.cs` — create → upload doc → submit → mark awarded
- [ ] `NotificationIntegrationTests.cs` — trigger deadline alert, verify notification created
- [ ] `AdminIntegrationTests.cs` — non-admin gets 403, admin can manage users

### 14.2.4 Regression Tests

- [ ] `ApiRegressionTests.cs` — snapshot-based response testing: call endpoint, compare JSON structure to saved baseline
- [ ] `ValidationRegressionTests.cs` — replay known edge-case inputs, verify correct rejection/acceptance

---

## 14.3 UI Test Suite (Future — after UI framework chosen)

**Location**: `ui/tests/` (TBD)
**Framework**: TBD — likely Vitest (unit) + Playwright (E2E)
**Run command**: TBD

### 14.3.1 Component Unit Tests
- [ ] Search form — filter construction, input validation
- [ ] Results table — pagination controls, sort behavior, empty state
- [ ] Prospect card — status badge, score display, action buttons
- [ ] Login form — validation, error display, submit behavior
- [ ] Dashboard widgets — data formatting, loading states

### 14.3.2 End-to-End Tests (Playwright or Cypress)

**Strategy**: Run against local API + test database. Seed known data before test suite.

- [ ] **Login flow** — valid credentials → dashboard; invalid → error message; lockout after 5 failures
- [ ] **Opportunity search** — enter NAICS filter → results appear → click detail → verify data
- [ ] **Prospect workflow** — search → create prospect from opportunity → assign → add note → score → go/no-go
- [ ] **Proposal workflow** — create proposal from prospect → upload document → submit → track status
- [ ] **Saved search** — create search → verify appears in list → execute → results match
- [ ] **Admin flow** — login as admin → manage users → create user → verify can login
- [ ] **Responsive layout** — verify critical pages render at mobile/tablet/desktop breakpoints

### 14.3.3 Visual Regression (optional)
- [ ] Screenshot comparison for key pages (dashboard, search results, prospect detail)
- [ ] Use Playwright's built-in screenshot comparison or Percy/Chromatic

---

## 14.4 Test Infrastructure

### Automation
- [ ] GitHub Actions workflow: `.github/workflows/test.yml` — SKIPPED (user preference for lean tooling)
  - Python: `pytest` with coverage report (fail below 70% threshold)
  - C#: `dotnet test` with coverage via Coverlet (fail below 70% threshold)
  - UI: `npm test` + `npx playwright test` (when UI exists)
- [ ] Separate scripts for unit tests (fast, no DB) and integration tests (needs MySQL)
- [ ] PR checks: unit tests must pass before merge; integration tests run on `main` branch

### Test Database Management
- [ ] Script: `scripts/setup-test-db.sh` (or `.ps1`) — creates `fed_contracts_test`, runs DDL, seeds reference data
- [ ] Python: pytest fixture or conftest.py that sets up/tears down test DB
- [ ] C#: `TestDatabaseFixture.cs` using `IAsyncLifetime` for xUnit collection fixtures
- [ ] Test DB is disposable — recreated from scratch each CI run

### Test Data Fixtures
- [ ] Shared fixture data (reference tables) usable by both Python and C# tests
- [ ] Anonymized production samples for regression testing
- [ ] Fixture generation script: `scripts/generate-test-fixtures.py` — extract small samples from production DB

### Coverage Reporting
- [ ] Python: `pytest-cov` → HTML + terminal report
- [ ] C#: Coverlet → Cobertura XML → report generator
- [ ] Target: 70% line coverage for unit tests, 50% for integration tests (initial targets, increase over time)

---

## 14.5 Test Conventions

| Convention | Rule |
|-----------|------|
| **Naming** | `test_<what>_<condition>_<expected>` (Python), `<What>_<Condition>_<Expected>` (C#) |
| **One assert per test** | Prefer focused assertions; split compound checks into separate tests |
| **No production DB** | Tests never touch `fed_contracts`; always use `fed_contracts_test` |
| **No live API calls** | Unit tests use fixtures; integration tests use stubs/mocks |
| **Deterministic** | No random data, no time-dependent assertions (freeze time if needed) |
| **Fast** | Unit test suite completes in < 30 seconds; integration in < 5 minutes |
| **Independent** | Tests don't depend on execution order; each test sets up its own state |

---

## Acceptance Criteria

1. [x] `pytest fed_prospector/tests/ -v` runs all Python unit tests — 568 tests pass
2. [ ] `pytest fed_prospector/tests/integration/ -v --db-test` runs integration tests against test DB — deferred (no test DB yet)
3. [x] `dotnet test api/tests/FedProspector.Core.Tests/` — 234 tests pass
4. [x] `dotnet test api/tests/FedProspector.Api.Tests/` — 118 tests pass
5. [ ] CI workflow runs tests on every push/PR — SKIPPED (user preference for lean tooling)
6. [x] Test fixtures exist for SAM.gov API response formats (8 JSON fixture files)
7. [ ] Regression tests cover all 18 documented data quality issues — deferred
8. [x] No test touches the production `fed_contracts` database

---

## Implementation Order

This phase can be worked in parallel with API development (Phases 10-13):

1. **Start immediately**: Python ETL unit tests (14.1.1) — ETL code is complete and stable
2. **Start immediately**: Test fixtures and infrastructure (14.1.4, 14.4)
3. **After Phase 10**: C# Core unit tests (14.2.1) — needs models and validators
4. **After Phase 11**: C# API controller tests (14.2.2) — needs endpoints
5. **After Phase 12**: C# integration tests (14.2.3) — needs CRUD operations
6. **After Phase 13**: Auth and full lifecycle integration tests
7. **After UI exists**: UI component tests (14.3.1) and E2E tests (14.3.2)
8. **Ongoing**: Regression tests added as bugs are found and fixed
