# Federal Contract Prospecting System

## Project Purpose

Python + MySQL system to find WOSB and 8(a) federal contracts to bid on. Replaces prior Salesforce approach.

## Project Organization

| Folder | Purpose |
|--------|---------|
| `fed_prospector/` | **Main Python application** - CLI, API clients, ETL pipeline, DB schema |
| `thesolution/` | Plan documents and implementation roadmap |
| `workdir/` | Data conversion scripts and reference CSV/MD files |
| `api/` | **C# ASP.NET Core Web API** - backend REST API, 57 endpoints across 13 controllers (Phases 10-14.5) |
| `ui/` | **Frontend web application** - TBD framework (future) |
| `OLD_ATTEMPTS/`, `OLD_RESOURCES/` | Archived. Do not modify or reference in new code. |

## Context Management

- **NEVER read large doc/plan files in the main context window.** Delegate to agents.
- **Multi-file edits MUST go to coder agents.** Main context is for orchestration only.
- **Batch doc updates into a single agent call.**
- **Why**: Reading 6+ large markdown files inline causes context compaction.

## Agent Instructions

### When Working on This Project

1. **Read the master plan first**: [thesolution/MASTER-PLAN.md](thesolution/MASTER-PLAN.md)
2. **Update the plan as you work**: Mark tasks done in `thesolution/phases/`.
3. **Follow the phase order**: Do not skip ahead unless told to.
4. **Record data quality issues**: Document in relevant phase file under "Known Issues".
5. **Never hardcode credentials**: Use `.env` + `python-dotenv`. See `thesolution/credentials.yml`.
6. **Prefer bulk extracts over API pagination**: SAM.gov rate limits are harsh.
7. **Test with real data**: `workdir/converted/local database/` has reference CSVs.
8. **Ignore OLD_ATTEMPTS and OLD_RESOURCES**: Relevant data already in `workdir/converted/`.

### Key Conventions

- **Terminology**: In this project, "Vendor API" = external government data sources (SAM.gov, USASpending.gov, GSA CALC+), called only by Python `load` commands, rate-limited. "App API" = FedProspect's own C# ASP.NET Core backend (57 endpoints), consumed by the React UI, queries local DB only.
- **Language**: Python 3.14 for all data gathering, transformation, and loading
- **Database**: MySQL 8.0+ with InnoDB engine, utf8mb4 charset
- **Config**: `.env` file with `python-dotenv`, never commit `.env` to git
- **Logging**: Python `logging` module, structured output
- **API Clients**: One class per data source, all inherit from `BaseAPIClient`
- **Vendor API Key Selection**: SAM.gov supports 2 API keys (--key=1 or --key=2 on CLI). Key 2 has 1000/day limit.
- **Change Detection**: SHA-256 record hashing to detect changes between loads
- **Data Quality**: Configurable rules in `etl_data_quality_rule` table, not hardcoded
- **App API**: ASP.NET Core Web API with 57 endpoints across 13 controllers + auth + health (Phases 10-14.5 complete). httpOnly cookie auth, CSRF protection, multi-tenant org isolation.
- **UI**: Vite + React 19 + TypeScript, MUI v6, TanStack Query, Axios (Phases 15-20)
- **Testing**: 1,259 tests total (738 Python pytest + 263 C# Core xUnit + 235 C# Api xUnit + 23 C# Infrastructure xUnit), all passing
- **Schema Ownership**: Python DDL owns ETL/data tables (~35 tables) + 14 new tables from Phase 9. EF Core owns application tables (app_user, prospect, saved_search, organization, organization_invite, etc.) starting Phase 10. 57 tables + 4 views total. See Phase 10 plan for details.

### Known Data Quality Issues

See `thesolution/reference/08-DATA-QUALITY-ISSUES.md` for 18 known issues handled by ETL cleaners (ZIP parsing, date formats, SAM.gov API quirks, etc.)

### Data Linking

See `thesolution/reference/07-DATA-ARCHITECTURE.md` for entity/opportunity/contract linking chains and field mappings.

### Project File References

| What | Location |
|------|----------|
| Python application | `fed_prospector/` (CLI: `python main.py --help`, 54 commands in 7 groups: setup, load, search, prospect, analyze, admin, health) |
| CLI modules | `fed_prospector/cli/` (database, entities, opportunities, prospecting, calc, awards, fedhier, exclusions, spending, health, subaward, schema, admin, setup, schedule) |
| Vendor API clients | `fed_prospector/api_clients/` (sam_opportunity, sam_awards, sam_exclusions, sam_subaward, sam_fedhier, usaspending, calc) |
| ETL loaders | `fed_prospector/etl/` (bulk_loader, dat_parser, opportunity_loader, awards_loader, usaspending_loader, calc_loader, fedhier_loader, exclusions_loader, subaward_loader, prospect_manager, scheduler, health_check, db_maintenance) |
| API controllers | `api/src/FedProspector.Api/Controllers/` (13 controllers: Auth, Health, Opportunities, Awards, Entities, Subawards, Dashboard, Admin, SavedSearches, Prospects, Proposals, Notifications, Organization) |
| API services | `api/src/FedProspector.Infrastructure/Services/` (14 services: Auth, Opportunity, Award, Entity, Subaward, Dashboard, Admin, SavedSearch, Prospect, Proposal, ActivityLog, GoNoGoScoring, Notification, Organization) |
| Python tests | `fed_prospector/tests/` (34 test files, 8 JSON fixtures in `fixtures/`, shared `conftest.py`) |
| C# Core tests | `api/tests/FedProspector.Core.Tests/` (263 tests, 34 test files: 25 validator, 1 mapping, 1 DTO, 1 paged response + Phase 14.5 additions) |
| C# Api tests | `api/tests/FedProspector.Api.Tests/` (235 tests, 22 test files: 2 middleware, 9 controller + Phase 14.5 additions) |
| C# Infrastructure tests | `api/tests/FedProspector.Infrastructure.Tests/` (23 tests: GoNoGoScoringService) |
| DB schema (DDL) | `fed_prospector/db/schema/` |
| Master plan | `thesolution/MASTER-PLAN.md` |
| UI application | `ui/` (Vite + React 19 + TypeScript, MUI v6, TanStack Query — Phases 15-20) |
| Phase plans | `thesolution/phases/` (01 through 20) |
| Reference docs | `thesolution/reference/` (01 through 09) |
| Credentials (DB, API keys) | `thesolution/credentials.yml` |
| Quick start | `thesolution/QUICKSTART.md` |
| SAM.gov API specs | `thesolution/sam_gov_api/` (8 YAML/YML OpenAPI specs) |
| Reference data CSVs | `workdir/converted/local database/` (NAICS, PSC, SBA size standards, FIPS, entity field mapping) |
| Reference docs (legacy) | `workdir/converted/` (country_codes, state_codes, entity_api_relationship, proposed mysql solution) |
| Data architecture | `thesolution/reference/07-DATA-ARCHITECTURE.md` |
| Data quality issues | `thesolution/reference/08-DATA-QUALITY-ISSUES.md` |
| SAM.gov API quirks | `thesolution/reference/09-SAM-API-QUIRKS.md` |
| Glossary | `thesolution/reference/06-GLOSSARY.md` |
