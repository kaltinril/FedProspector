# Federal Contract Prospecting System - Master Plan

## Mission

Build a B2B SaaS platform that helps companies discover, evaluate, and win federal contracts — with a focus on WOSB (Women-Owned Small Business) and 8(a) set-aside opportunities.

The platform gathers data from 10+ government APIs, normalizes it into a MySQL database, and provides a web application with powerful search, competitive intelligence, and pipeline management. Companies subscribe to give their teams the best intel for finding and winning contracts.

## Background

This project targets federal contract prospecting as a paid SaaS product. The initial customer is a women-owned small business (MSOne LLC), with the architecture designed to support multiple subscribing companies from day one.

A previous Salesforce CRM approach hit CPU/transaction limits when processing 1M+ entity records and required expensive licensing. This project replaces Salesforce with:
- A Python ETL pipeline gathering data from 10+ federal government APIs
- A MySQL database with 57 tables normalizing opportunities, awards, entities, and competitive intelligence
- A C# ASP.NET Core Web API with multi-tenant organization isolation
- A React web application for search, analysis, and capture management
- Per-organization data isolation so each subscribing company's prospects, proposals, and searches are private

## Project Organization

```
fedProspect/
├── fed_prospector/    Main Python application (CLI, API clients, ETL, DB schema)
├── api/               C# ASP.NET Core Web API (Phase 10+)
├── ui/                Frontend web application (future)
├── thesolution/       Current plan documents (this folder)
├── workdir/           Data conversion scripts and reference CSV/MD files
├── OLD_ATTEMPTS/      Archived: legacy Salesforce/Apex code, prior DB schema attempts
├── OLD_RESOURCES/     Archived: original DOCX/XLSX/PDF/PNG/OpenAPI source files
├── .claude/           Claude Code configuration
└── .github/           GitHub configuration
```

> **Note**: `OLD_ATTEMPTS/` and `OLD_RESOURCES/` are archived reference material from the prior Salesforce-based approach. All relevant data has been converted into `workdir/converted/`. New code should not depend on files in these archived folders.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | MySQL 8.0+ (local) | Replaces Salesforce. No licensing cost. Full SQL capability. |
| Data Gathering | Python 3.14 | Rich ecosystem for REST/SOAP/CSV/JSON. requests, lxml, openpyxl. |
| Bulk Loads | DAT + LOAD DATA INFILE preferred | Fastest MySQL loading path. JSON streaming used for incremental/API loads. |
| Change Detection | SHA-256 record hashing | Compare one hash instead of 100+ fields. Log field-level diffs only when hash differs. |
| Rate Limit Strategy | Bulk extracts first, Vendor API for incremental | Monthly extract = 1 Vendor API call for all entities. Daily Vendor API = targeted updates only. |
| Credentials | `.env` + python-dotenv | Never hardcode. Prior work had keys visible in SQL definition files. |
| Web API | ASP.NET Core (.NET 10) | Type-safe, high-perf backend. EF Core for MySQL. Separate from Python ETL. |
| Frontend | Vite + React 19 + TypeScript + MUI v6 | Modern stack, enterprise component library, fast dev server. |
| Multi-Tenancy | Shared public data + org-isolated capture data | Government data is shared; prospects/proposals are private per company. |

## Phase Roadmap

### Phase 1: Foundation
**Status**: [x] COMPLETE (2026-02-22)
**File**: [01-FOUNDATION.md](phases/01-FOUNDATION.md)

- ~~Set up MySQL database~~ 54 tables + 4 views
- ~~Load reference data from CSVs~~ ~13,001 rows across 11 tables (originally 12,988 in Phase 1; Phase 7 added ref_sba_type + ref_entity_structure)
- ~~Python project scaffolding~~ config, logging, DB pool, CLI
- ~~Base API client~~ rate limit via DB, exponential backoff
- ~~CLI entry point~~ `python main.py` (52 commands across 15 `cli/` modules)
- **Deliverable**: DONE

### Phase 2: Entity Data Pipeline (Proof of Concept - 1 Source)
**Status**: [x] COMPLETE (2026-02-22) - 865K entities loaded
**File**: [02-ENTITY-PIPELINE.md](phases/02-ENTITY-PIPELINE.md)

- ~~Build SAM.gov Entity API client~~ `sam_entity_client.py` (v3 API, WOSB/8(a) search)
- ~~Build SAM.gov Extract client~~ `sam_extract_client.py` (monthly/daily download, ZIP, JSON streaming via ijson)
- ~~Implement data cleaner~~ `data_cleaner.py` (all 10 quality rules + DB-driven rules)
- ~~Implement entity loader~~ `entity_loader.py` (JSON normalization, 1+8 tables, SHA-256 change detection, batch commits)
- ~~Implement DAT parser + bulk loader~~ `dat_parser.py` + `bulk_loader.py` (V2 DAT files, LOAD DATA INFILE)
- ~~CLI commands~~ `download-extract`, `load-entities`, `seed-quality-rules`
- ~~Download monthly extract and execute initial bulk load~~ 865,232 entities in ~4.5 min
- **Deliverable**: DONE

### Phase 3: Opportunities Pipeline (Proof of Concept - Load First Data)
**Status**: [x] COMPLETE (2026-02-28) - 12,209 opportunities loaded (2-year historical), polling via Phase 6
**File**: [03-OPPORTUNITIES-PIPELINE.md](phases/03-OPPORTUNITIES-PIPELINE.md)

- ~~Build SAM.gov Opportunities API client~~ `sam_opportunity_client.py` (v2 search, 5-call budget, priority set-aside ordering)
- ~~Implement opportunity loader with change tracking~~ `opportunity_loader.py` (SHA-256 hashing, opportunity_history)
- ~~Create CLI commands~~ `load-opportunities` (--max-calls, --historical) + `search` (local DB query)
- ~~Initial + historical load~~ 12,209 opportunities across 12 SB set-aside types (2-year range, Mar 2024 - Feb 2026)
- ~~Set up scheduled polling~~ Phase 6 `run-job opportunities` + Windows Task Scheduler (every 4 hours)
- **Note**: SAM.gov API key 2 confirmed at 1000/day tier (enables full historical loads)
- **Deliverable**: DONE

### Phase 4: Sales/Prospecting Pipeline
**Status**: [x] COMPLETE (2026-02-22)
**File**: [04-SALES-PROSPECTING.md](phases/04-SALES-PROSPECTING.md)

- ~~Build prospect tracking tables and workflow~~ `ProspectManager` class + 13 CLI commands
- ~~Implement saved search/filter system~~ `save-search`, `run-search`, `list-searches` with dynamic SQL
- ~~Build go/no-go scoring framework~~ 4-criterion scoring (0-40 scale): set-aside, time, NAICS match, value
- ~~Create prospect notes and activity logging~~ Auto-logged status changes, assignments; manual notes
- ~~Pipeline dashboard~~ `dashboard` command with status counts, due this week, workload, win/loss stats
- **Deliverable**: DONE

### Phase 5: Extended Data Sources (Remaining Phases Build-Out)
**Status**: [x] COMPLETE (2026-02-28) - All iterations complete (5A-5E, 5G); 5F deprecated
**File**: [05-EXTENDED-SOURCES.md](phases/05-EXTENDED-SOURCES.md)

- ~~SAM.gov Contract Awards API~~ `sam_awards_client.py` + `awards_loader.py` (v1 API, search by NAICS/awardee/solicitation, loads to `fpds_contract`)
- ~~USASpending.gov API~~ `usaspending_client.py` + `usaspending_loader.py` (POST-based search, SHA-256 change detection, incumbent search working)
- ~~USASpending Transaction History (5B-Enhance)~~ `usaspending_transaction` table, `load_transactions()`, `calculate_burn_rate()` for spend analysis
- ~~FPDS ATOM Feed~~ DEPRECATED (Feb 2026) — replaced by SAM.gov Contract Awards API (5A)
- ~~GSA CALC+ API~~ `calc_client.py` + `calc_loader.py` (full_refresh, ~122K labor rates loaded)
- ~~SAM.gov Federal Hierarchy API~~ `sam_fedhier_client.py` + `fedhier_loader.py` (v1 API, full hierarchy refresh, agency search)
- ~~SAM.gov Exclusions API~~ `sam_exclusions_client.py` + `exclusions_loader.py` (v4 API, check UEI/name, prospect team member cross-check, loads to `sam_exclusion`)
- ~~SAM.gov Subaward Reporting API~~ `sam_subaward_client.py` + `subaward_loader.py` (v1 subcontracts API, teaming partner analysis, loads to `sam_subaward`)
- **Key capability**: Incumbent analysis -- USASpending, FPDS, and Contract Awards data combine to identify previous contract winners, their pricing, and period of performance end dates. This enables predicting rebids before they post and crafting competitive proposals. See [01-RESEARCH-AND-DATA-SOURCES.md](reference/01-RESEARCH-AND-DATA-SOURCES.md) "Incumbent & Competitive Intelligence Strategy" section.
- **CLI refactored**: `main.py` (1752 -> 170 lines) with 52 commands split into 15 `cli/` modules (database, entities, opportunities, prospecting, calc, awards, fedhier, exclusions, spending, health, subaward, schema, admin, setup, schedule)
- **New CLI commands**: `load-awards`, `load-hierarchy`, `search-agencies`, `load-exclusions`, `check-exclusion`, `check-prospects`, `load-transactions`, `burn-rate`, `load-subawards`, `search-subawards`, `teaming-partners`
- **Deliverable**: DONE

### Phase 6: Automation and Monitoring
**Status**: [x] COMPLETE (2026-02-28)
**File**: [06-AUTOMATION.md](phases/06-AUTOMATION.md)

- ~~Job scheduler~~ `etl/scheduler.py` with 8 job definitions, `JobRunner` class, Windows Task Scheduler integration
- ~~Health check dashboard~~ `etl/health_check.py` + `check-health` CLI command (data freshness, API usage, alerts)
- ~~Data staleness detection~~ Threshold-based staleness per source (6h opportunities, 48h entities, 14d hierarchy/awards/exclusions, 45d CALC+/USASpending)
- ~~API key management~~ Configuration checks, daily limit monitoring
- ~~Database maintenance~~ `etl/db_maintenance.py` + `maintain-db` CLI (archive history, purge staging, ANALYZE TABLE)
- ~~Job runner CLI~~ `run-job` command to manually trigger any scheduled job
- ~~Saved search automation~~ `run-all-searches` command to execute all active saved searches
- **CLI**: 4 new commands in `cli/health.py` (check-health, run-job, maintain-db, run-all-searches)
- **Deliverable**: DONE

### Phase 7: Reference Data Enrichment
**Status**: [x] COMPLETE (2026-02-28)
**File**: [07-REFERENCE-ENRICHMENT.md](phases/07-REFERENCE-ENRICHMENT.md)

- ~~Enrich `ref_business_type`~~ categories (11 groups), socioeconomic flags, small business flags
- ~~Load `ref_entity_structure`~~ 8 codes from entity data discovery
- ~~Merge SAM.gov territory codes~~ `ref_country_code` with `is_iso_standard` flag (21 SAM-only territories)
- ~~Add NAICS hierarchy metadata~~ `code_level`, `level_name`, `parent_code` (Sector→National Industry)
- ~~Expand `ref_set_aside_type`~~ 23 entries from CSV with categories (was 14 hardcoded)
- ~~New `ref_sba_type` lookup table~~ 5 SBA certification codes (A6, A9, A0, JT, XX)
- ~~Update views~~ enriched JOINs for human-readable output (business types, NAICS sectors, SBA certs)
- ~~FPDS.gov deprecation~~ documented in Phase 5F, SAM.gov Contract Awards API URL in settings.py
- **Deliverable**: DONE

### Phase 8: Web/API Readiness (Gap Analysis)
**Status**: [x] COMPLETE
**Document**: [08-WEB-API-READINESS.md](phases/08-WEB-API-READINESS.md)

**Architecture Decision**: Python stays as ETL/data gathering only. C# API backend will query MySQL directly. Frontend TBD.

**Scope**:
- [x] Gap analysis complete — schema audit, missing tables, missing columns documented
- [x] Add 14 new tables — completed in Phase 9
- [x] Add ~15 new columns across 4 existing tables — completed in Phase 9
- [x] Build C# API backend — 57 endpoints across 14 controllers (Phases 10-14.5)
- [x] Replicate prospect status flow, Go/No-Go scoring in C# (Phase 12)

**Impact**: Current 57 tables + 4 views (schema changes completed in Phase 9, expanded in Phase 14.5, +1 table in Phase 14.6).

### Phase 9: Schema Evolution
**Status**: [x] COMPLETE (2026-03-01)
**Document**: [09-SCHEMA-EVOLUTION.md](phases/09-SCHEMA-EVOLUTION.md)

**Scope**:
- [x] Add 14 new tables (8 production: app_session, proposal, proposal_document, proposal_milestone, activity_log, notification, contracting_officer, opportunity_poc; plus 6 raw staging: `stg_*_raw`)
- [x] ALTER 4 existing tables with ~15 new columns (app_user, opportunity, prospect, prospect_team_member)
- [x] Update `build-database` CLI to include new schema file
- [x] Result: 54 tables + 4 views (verified with `check-schema --verbose`: 54 OK, 0 DRIFT, 0 MISSING; expanded to 56 tables in Phase 14.5)
- **Existing data preserved**: 832K entities, 13K opportunities, 2.1K contracts, 110K labor rates

### Phase 10: C# API Foundation
**Status**: [x] COMPLETE (2026-03-01)
**Document**: [10-API-FOUNDATION.md](phases/10-API-FOUNDATION.md)
**Repository**: `api/` folder (monorepo -- same repo as Python ETL)

**Schema ownership splits**: Python DDL owns ETL/data tables (~35), EF Core owns application tables (~5 existing + future). Both share the `fed_contracts` database. See [10-API-FOUNDATION.md](phases/10-API-FOUNDATION.md) "Schema Ownership" section for full details.

**Scope**:
- [x] ASP.NET Core Web API project (.NET 10)
- [x] MySQL connectivity via Pomelo EF Core + entity models for 56 tables (50 production + 6 staging). EF Core models needed for 50 production tables only; staging tables are managed by the Python ETL pipeline. (Phase 14.5 added `organization` and `organization_invite`.)
- [x] JWT authentication middleware + BCrypt password hashing
- [x] Swagger/OpenAPI documentation
- [x] Repository pattern, pagination, DTOs, base controller
- [x] Serilog logging, CORS, error handling, health check

### Phase 11: Read-Only Query Endpoints
**Status**: [x] COMPLETE (2026-03-01)
**Document**: [11-READ-ENDPOINTS.md](phases/11-READ-ENDPOINTS.md)

**Scope**:
- [x] 17 endpoints across 7 controllers (14 GET, 2 POST, 1 DELETE)
- [x] OpportunitiesController: search + detail + WOSB/8(a) targets
- [x] AwardsController: search + detail + burn-rate calculation
- [x] EntitiesController: search + detail + competitor profile + exclusion check
- [x] SubawardsController: teaming partners
- [x] DashboardController + AdminController (ETL status)
- [x] SavedSearchesController: list, create, run, delete

### Phase 12: Capture Management API (CRUD)
**Status**: [x] COMPLETE (2026-03-01)
**Document**: [12-CAPTURE-MANAGEMENT-API.md](phases/12-CAPTURE-MANAGEMENT-API.md)

**Scope**:
- [x] 14 endpoints (11 write + 3 read) across 2 controllers for prospects, proposals, notes, team members
- [x] Prospect status flow validation (replicate Python STATUS_FLOW)
- [x] Go/No-Go scoring (4 criteria, 0-40 scale)
- [x] Proposal lifecycle (DRAFT → SUBMITTED → AWARDED/NOT_AWARDED)
- [x] Activity logging on all write operations

### Phase 13: Auth, Notifications & Production Readiness
**Status**: [x] COMPLETE (2026-03-01)
**Document**: [13-AUTH-AND-PRODUCTION.md](phases/13-AUTH-AND-PRODUCTION.md)

**Scope**:
- [x] Auth endpoints: register, login, logout, change-password, profile (GET + PATCH)
- [x] Notification system: list, mark-read, mark-all-read + notification generation service
- [x] Admin user management: list users, update user, reset password
- [x] Production hardening: rate limiting (4 policies), security headers, enhanced error handling
- [x] Enhanced health check with per-source ETL freshness
- [x] Swagger/OpenAPI documentation improvements

### Phase 14: Testing Strategy — Unit, Integration, Regression & E2E
**Status**: [x] COMPLETE (2026-03-01)
**Document**: [14-TESTING.md](phases/14-TESTING.md)

**Scope**:
- [x] Python ETL test suite: 568 tests across 23 test files (8 API client, 3 data quality, 11 loader/business/utility + conftest.py + 8 JSON fixtures)
- [x] C# Core.Tests: 237 tests across 25+ test files (22 validator, 1 mapping, 1 DTO, 1 paged response + Phase 14.5 additions)
- [x] C# Api.Tests: 223 tests across 11+ test files (2 middleware, 9 controller + Phase 14.5 additions)
- [x] **Total: 1,028 tests, all passing** — pytest + xUnit + Moq + FluentAssertions
- [ ] UI test suite (future): deferred until UI exists
- [ ] CI/CD: GitHub Actions skipped (user preference for lean tooling)
- [ ] Integration tests against test DB: deferred (unit tests with mocking cover current needs)

### Phase 14.5: Multi-Tenancy & Security Hardening
**Status**: [x] COMPLETE (2026-03-02)
**Document**: [14.5-MULTI-TENANCY-SECURITY.md](phases/14.5-MULTI-TENANCY-SECURITY.md)
**Dependencies**: Phase 13 (Auth), Phase 14 (Testing)

**Scope**:
> **BLOCKER**: Must complete before Phase 15. Multi-tenancy changes affect auth flow, JWT claims, cookie handling, and all capture endpoint signatures. The UI cannot be built against the pre-14.5 API.

- [x] Organization-scoped data isolation: `organization` table, `organization_invite` table, `app_user` modifications (`org_role`, `organization_id`)
- [x] httpOnly cookie auth replacing localStorage, token refresh endpoint, `OnTokenValidated` session check
- [x] Invite-only registration flow
- [x] Org management endpoints: GET/PATCH `/org`, GET/POST/DELETE `/org/invites`, GET `/org/members`
- [x] Multi-tenant query scoping on all capture endpoints
- [x] Missing endpoints: PATCH `saved-searches`, POST `milestones`, GET `proposals`, POST `auth/refresh`, GET `notifications/unread-count`, GET `opportunities/export`
- [x] Security hardening: CSP, Swagger restriction, CORS tightening, generic error messages, `ClockSkew=Zero`
- **Result**: 57 endpoints across 14 controllers, 14 services, 57 tables + 4 views, 1,028 tests passing

### Phase 14.7: CLI Command Hierarchy
**Status**: [x] COMPLETE (2026-03-02)
**Document**: [14.7-CLI-HIERARCHY.md](phases/14.7-CLI-HIERARCHY.md)
**Dependencies**: Phase 14.6 (Admin Operability — all 52 commands must exist before renaming)

Restructured 52 flat commands into 7 discoverable groups. Commands now follow `python main.py GROUP COMMAND` pattern. The 7 groups are: `setup`, `load`, `search`, `prospect`, `analyze`, `admin`, `health`. See [phases/14.7-CLI-HIERARCHY.md](phases/14.7-CLI-HIERARCHY.md).

### Phase 14.6: Admin Operability & CLI Hardening
**Status**: [x] COMPLETE (2026-03-02)
**Document**: [14.6-ADMIN-OPERABILITY.md](phases/14.6-ADMIN-OPERABILITY.md)
**Dependencies**: Phase 14.5 (Multi-Tenancy), Phase 6 (Automation)

**Scope**:
> **BLOCKER FOR UI PHASES**: Ensures an admin can stand up, operate, and troubleshoot the system without AI assistance or raw SQL.

- [x] Entity auto-load wrapper: `refresh-entities` command (download + load in one step)
- [x] First-time setup wizard: `verify-setup` command (checks all prerequisites with pass/fail)
- [x] Schedule installer: `setup-schedule` command (auto-creates Windows/Linux scheduled tasks)
- [x] Log rotation: RotatingFileHandler (50 MB per file, 10 backups)
- [x] Admin CLI commands: `create-org`, `list-orgs`, `invite-user`, `list-org-members`, `disable-user`, `enable-user`, `reset-password` (7 new commands in `cli/admin.py`)
- [x] Job/load history: `load-history` command with source/days/status filters
- [x] Service manager hardening: pre-flight port/binary checks, diagnostic messages
- [x] API key expiration tracking: warns at <14 days, errors at <3 days
- [x] Health check persistence: `etl_health_snapshot` table (1 new table, total: 57 tables + 4 views)
- [x] Auto-seed quality rules in `build-database`
- **Result**: 52 CLI commands across 15 modules, 12 new commands, 1 new table

### Phase 14.9: Raw Staging for All ETL Loaders
**Status**: [x] COMPLETE (2026-03-03)
**Document**: [14.9-RAW-STAGING.md](phases/14.9-RAW-STAGING.md)

All 7 ETL loaders now write raw API JSON to staging tables before normalization. A second `autocommit=True` connection ensures staging rows persist even when normalization raises an error. `db_maintenance.purge_staging` extended to cover all 7 tables (`stg_entity_raw`, `stg_opportunity_raw`, `stg_fpds_award_raw`, `stg_usaspending_raw`, `stg_exclusion_raw`, `stg_subaward_raw`, `stg_fedhier_raw`).

### Phase 14.10: ETL Loader DRY Refactor
**Status**: [x] COMPLETE (2026-03-03)
**Document**: [14.10-ETL-REFACTOR-DRY.md](phases/14.10-ETL-REFACTOR-DRY.md)

| 14.10 | ETL Loader DRY Refactor | COMPLETE | StagingMixin, etl_utils.py (parse_date/parse_decimal/fetch_existing_hashes/escape_tsv_value), get_cursor context manager; ~560 lines removed across 8 loaders |

### Phase 15: UI Foundation & Layout
**Status**: [ ] NOT STARTED
**File**: [phases/15-UI-FOUNDATION.md](phases/15-UI-FOUNDATION.md)
**Dependencies**: Phase 14 (Testing), Phase 14.5 (Multi-Tenancy & Security)

- Vite + React 19 + TypeScript scaffold
- MUI v6 component library, TanStack Query, Axios
- JWT auth flow (login/register, token management, route guards)
- App layout: collapsible sidebar, top bar, breadcrumbs, dark/light theme
- Typed API client layer (all 57 API endpoints from Phases 10-14.5)
- Shared components: DataTable, SearchFilters, StatusChip, etc.
- Service manager integration (fed_prospector.py UI commands)

### Phase 16: Search & Discovery
**Status**: [ ] NOT STARTED
**File**: [phases/16-SEARCH-DISCOVERY.md](phases/16-SEARCH-DISCOVERY.md)

- Opportunity search with NAICS, set-aside, keyword, deadline filters
- Target opportunity search (pre-filtered relevance)
- Award search with vendor, NAICS, agency, value range filters
- Entity search with SBA certification, business type filters
- Teaming partner search from subaward data
- Shared filter bar, URL state sync, CSV export
- MUI X Data Grid with server-side pagination and sorting

### Phase 17: Detail Views & Competitive Intelligence
**Status**: [ ] NOT STARTED
**File**: [phases/17-DETAIL-INTELLIGENCE.md](phases/17-DETAIL-INTELLIGENCE.md)

- Opportunity detail: overview, qualification checklist, CONUS/OCONUS, clearance
- History & incumbent intel: new vs re-compete, incumbent profile, burn rate, bid count
- Award detail: contract facts, financials, burn rate chart, transaction history
- Entity detail: company profile, competitor analysis, exclusion check
- Cross-linking between opportunities ↔ awards ↔ entities

### Phase 18: Capture Management & Pipeline
**Status**: [ ] NOT STARTED
**File**: [phases/18-CAPTURE-MANAGEMENT.md](phases/18-CAPTURE-MANAGEMENT.md)

- Prospect pipeline: Kanban view (drag-and-drop) + list view
- Prospect detail: Go/No-Go scoring, status transitions, priority
- Notes & team collaboration (add notes, manage team members)
- Proposal management: milestones, documents, status tracking
- Create prospect flow from opportunity search/detail

### Phase 19: Dashboard, Saved Searches & Notifications
**Status**: [ ] NOT STARTED
**File**: [phases/19-DASHBOARD-NOTIFICATIONS.md](phases/19-DASHBOARD-NOTIFICATIONS.md)

- Executive dashboard: pipeline funnel, due this week, workload, win/loss metrics
- Saved search management: create, run, enable notifications
- Notification center: feed with mark-as-read, filtering
- Top bar notification bell with unread count

### Phase 20: Admin, Profile & Production Polish
**Status**: [ ] NOT STARTED
**File**: [phases/20-ADMIN-POLISH.md](phases/20-ADMIN-POLISH.md)

- Admin panel: ETL status monitoring, user management
- User profile: edit, change password
- Error handling: 404 page, error boundaries, session expired flow
- Responsive design: mobile, tablet, desktop
- Performance: code splitting, bundle optimization
- Accessibility: keyboard nav, ARIA, WCAG AA

## Success Criteria

### Data & ETL
1. Can find all active WOSB/8(a) opportunities matching target NAICS codes within seconds
2. Daily refresh of opportunities runs automatically via scheduler
3. Entity data for 500K+ contractors available for competitive analysis
4. Change history shows what changed and when for entities and opportunities
5. Data quality issues are caught and cleaned automatically during load
6. API rate limits are never exceeded

### SaaS Product
7. Multiple companies can use the system simultaneously with complete data isolation
8. Company admins can invite team members and manage roles (owner/admin/member)
9. Invite-only registration prevents unauthorized access to company data
10. Paying customers get competitive intelligence (incumbent analysis, burn rate, market share by NAICS) unavailable on free government sites
11. Sub-second search across 100K+ opportunities with advanced filtering (NAICS, set-aside, contract type, re-compete status, clearance)
12. Team members can claim, track, and manage prospects through a Kanban pipeline
13. Secure authentication with httpOnly cookies, token refresh, and CSRF protection

## Supporting Documents

| Document | Purpose |
|----------|---------|
| [01-RESEARCH-AND-DATA-SOURCES.md](reference/01-RESEARCH-AND-DATA-SOURCES.md) | All federal data sources with APIs, limits, and priority ranking |
| [02-DATABASE-SCHEMA.md](reference/02-DATABASE-SCHEMA.md) | Complete MySQL DDL for all tables, views, and indexes |
| [03-PYTHON-ARCHITECTURE.md](reference/03-PYTHON-ARCHITECTURE.md) | Python module design, patterns, and class structure |
| [04-DATA-OVERLAP-AND-LIMITS.md](reference/04-DATA-OVERLAP-AND-LIMITS.md) | Data redundancy map and rate limit strategy |
| [05-LEGAL-CONSIDERATIONS.md](reference/05-LEGAL-CONSIDERATIONS.md) | Terms of use, PII, D&B restrictions |
| [QUICKSTART.md](QUICKSTART.md) | Environment setup guide (MySQL, Python, SAM.gov API key) |
| [credentials.yml](credentials.yml) | All local dev passwords (MySQL root, fed_app, SAM.gov API key) |
| [06-GLOSSARY.md](reference/06-GLOSSARY.md) | Federal contracting terminology definitions |
| [14.5-MULTI-TENANCY-SECURITY.md](phases/14.5-MULTI-TENANCY-SECURITY.md) | Multi-tenant architecture, auth hardening, org isolation |
| [15-UI-FOUNDATION.md](phases/15-UI-FOUNDATION.md) | React + TypeScript UI scaffold and shared components |
| [16-SEARCH-DISCOVERY.md](phases/16-SEARCH-DISCOVERY.md) | Opportunity, award, entity, and teaming partner search |
| [17-DETAIL-INTELLIGENCE.md](phases/17-DETAIL-INTELLIGENCE.md) | Detail views and competitive intelligence features |
| [18-CAPTURE-MANAGEMENT.md](phases/18-CAPTURE-MANAGEMENT.md) | Prospect pipeline Kanban and proposal management |
| [19-DASHBOARD-NOTIFICATIONS.md](phases/19-DASHBOARD-NOTIFICATIONS.md) | Executive dashboard, saved searches, notification system |
| [20-ADMIN-POLISH.md](phases/20-ADMIN-POLISH.md) | Admin panel, profile, responsive design, accessibility |
