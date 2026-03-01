# Federal Contract Prospecting System - Master Plan

## Mission

Build a complete system that gathers federal contract opportunity data from government APIs, loads it into a local MySQL database, and enables fast discovery, evaluation, and pursuit of WOSB (Women-Owned Small Business) and 8(a) program contracts.

## Background

This project targets federal contract prospecting for a women-owned small business. A previous Salesforce CRM approach hit Salesforce CPU/transaction limits when processing 1M+ entity records and required expensive licensing.

This project replaces Salesforce with a local MySQL database and Python-based data pipeline that:
- Gathers data from 10+ federal government APIs and data sources
- Loads and normalizes the data into a relational schema
- Tracks changes between data loads
- Enables fast filtering for WOSB/8(a) set-aside contracts by NAICS code
- Supports prospecting workflow (assign, track, score, decide on contracts)

## Project Organization

```
pbdc/
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
| Rate Limit Strategy | Bulk extracts first, API for incremental | Monthly extract = 1 API call for all entities. Daily API = targeted updates only. |
| Credentials | `.env` + python-dotenv | Never hardcode. Prior work had keys visible in SQL definition files. |

## Phase Roadmap

### Phase 1: Foundation
**Status**: [x] COMPLETE (2026-02-22)
**File**: [01-FOUNDATION.md](phases/01-FOUNDATION.md)

- ~~Set up MySQL database~~ 40 tables + 4 views
- ~~Load reference data from CSVs~~ ~13,001 rows across 11 tables (originally 12,988 in Phase 1; Phase 7 added ref_sba_type + ref_entity_structure)
- ~~Python project scaffolding~~ config, logging, DB pool, CLI
- ~~Base API client~~ rate limit via DB, exponential backoff
- ~~CLI entry point~~ `python main.py` (39 commands across 12 `cli/` modules)
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
- **CLI refactored**: `main.py` (1752 -> 170 lines) with 39 commands split into 12 `cli/` modules (database, entities, opportunities, prospecting, calc, awards, fedhier, exclusions, spending, health, subaward, schema)
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
**Status**: PLANNING
**Document**: [08-WEB-API-READINESS.md](phases/08-WEB-API-READINESS.md)

**Architecture Decision**: Python stays as ETL/data gathering only. C# API backend will query MySQL directly. Frontend TBD.

**Scope**:
- [x] Gap analysis complete — schema audit, missing tables, missing columns documented
- [ ] Add 14 new tables (8 production: app_session, proposal, proposal_document, proposal_milestone, activity_log, notification, contracting_officer, opportunity_poc; plus 6 raw staging: `stg_*_raw` tables for API response preservation)
- [ ] Add ~15 new columns across 4 existing tables (app_user, opportunity, prospect, prospect_team_member)
- [ ] Build C# API backend (21 endpoints documented)
- [ ] Replicate prospect status flow, Go/No-Go scoring, burn rate logic in C#

**Impact**: Current 40 tables + 4 views → 54 tables + 4 views (Tier 1 MVP). Plus 6 raw staging tables (`stg_*_raw`) for API response preservation.

### Phase 9: Schema Evolution
**Status**: PLANNING
**Document**: [09-SCHEMA-EVOLUTION.md](phases/09-SCHEMA-EVOLUTION.md)

**Scope**:
- [ ] Add 14 new tables (8 production: app_session, proposal, proposal_document, proposal_milestone, activity_log, notification, contracting_officer, opportunity_poc; plus 6 raw staging: `stg_*_raw`)
- [ ] ALTER 4 existing tables with ~15 new columns (app_user, opportunity, prospect, prospect_team_member)
- [ ] Update `build-database` CLI to include new schema file
- [ ] Result: 40 → 54 tables + 4 views

### Phase 10: C# API Foundation
**Status**: PLANNING
**Document**: [10-API-FOUNDATION.md](phases/10-API-FOUNDATION.md)
**Repository**: `api/` folder (monorepo -- same repo as Python ETL)

**Schema ownership splits**: Python DDL owns ETL/data tables (~35), EF Core owns application tables (~5 existing + future). Both share the `fed_contracts` database. See [10-API-FOUNDATION.md](phases/10-API-FOUNDATION.md) "Schema Ownership" section for full details.

**Scope**:
- [ ] ASP.NET Core Web API project (.NET 10)
- [ ] MySQL connectivity via Pomelo EF Core + entity models for 54 tables total (48 production + 6 staging). EF Core models needed for 48 production tables only; staging tables are managed by the Python ETL pipeline.
- [ ] JWT authentication middleware + BCrypt password hashing
- [ ] Swagger/OpenAPI documentation
- [ ] Repository pattern, pagination, DTOs, base controller
- [ ] Serilog logging, CORS, error handling, health check

### Phase 11: Read-Only Query Endpoints
**Status**: PLANNING
**Document**: [11-READ-ENDPOINTS.md](phases/11-READ-ENDPOINTS.md)

**Scope**:
- [ ] 11 GET endpoints across 6 controllers
- [ ] OpportunitiesController: search + detail + WOSB/8(a) targets
- [ ] AwardsController: search + detail + burn-rate calculation
- [ ] EntitiesController: search + detail + competitor profile + exclusion check
- [ ] SubawardsController: teaming partners
- [ ] DashboardController + AdminController (ETL status)

### Phase 12: Capture Management API (CRUD)
**Status**: PLANNING
**Document**: [12-CAPTURE-MANAGEMENT-API.md](phases/12-CAPTURE-MANAGEMENT-API.md)

**Scope**:
- [ ] 10 write endpoints for prospects, proposals, notes, team members
- [ ] Prospect status flow validation (replicate Python STATUS_FLOW)
- [ ] Go/No-Go scoring (4 criteria, 0-40 scale)
- [ ] Proposal lifecycle (DRAFT → SUBMITTED → AWARDED/NOT_AWARDED)
- [ ] Activity logging on all write operations

### Phase 13: Auth, Notifications & Production Readiness
**Status**: PLANNING
**Document**: [13-AUTH-AND-PRODUCTION.md](phases/13-AUTH-AND-PRODUCTION.md)

**Scope**:
- [ ] Auth endpoints: register, login, logout, change-password, profile
- [ ] Notification system: deadline alerts, status change alerts, saved search results
- [ ] Admin user management
- [ ] Production hardening: rate limiting, input validation, security headers
- [ ] Docker containerization + CI/CD pipeline skeleton
- [ ] API documentation (Swagger + Postman collection)

## Success Criteria

1. Can find all active WOSB/8(a) opportunities matching target NAICS codes within seconds
2. Daily refresh of opportunities runs automatically
3. Entity data for 500K+ contractors available for competitive analysis
4. Change history shows what changed and when for entities and opportunities
5. Team members can claim, track, and manage prospects through the pipeline
6. API rate limits are never exceeded
7. Data quality issues are caught and cleaned automatically during load

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
