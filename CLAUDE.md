# Federal Contract Prospecting System

## Project Purpose

Build a Python + MySQL system to gather, store, and analyze federal contract opportunity data. The primary goal is to efficiently find WOSB (Women-Owned Small Business) and 8(a) program contracts to bid on.

This replaces a previous Salesforce-based approach. All data gathering uses Python. All data storage uses a local MySQL database.

## Project Organization

| Folder | Purpose |
|--------|---------|
| `fed_prospector/` | **Main Python application** - CLI, API clients, ETL pipeline, DB schema |
| `thesolution/` | Plan documents and implementation roadmap |
| `workdir/` | Data conversion scripts and reference CSV/MD files |
| `api/` | **C# ASP.NET Core Web API** - backend REST API (Phase 10+) |
| `ui/` | **Frontend web application** - TBD framework (future) |
| `OLD_ATTEMPTS/` | Legacy Salesforce/Apex code and prior database schema attempts (archived) |
| `OLD_RESOURCES/` | Original source files (DOCX, XLSX, PDF, PNG, OpenAPI specs) from prior work (archived) |

## Context Management

- **NEVER read large doc/plan files in the main context window.** Delegate to agents instead.
- **Multi-file edits (especially doc updates) MUST go to coder agents.** The main context is for orchestration only: decide what to do, launch agents, review results, commit.
- **Batch doc updates into a single agent call.** Give it the list of files + what changed (e.g., "update table count from 38 to 39 in all docs") and let it handle all reads/edits outside the main window.
- **Why**: Reading 6+ large markdown files inline causes context compaction, which loses conversation history and wastes the user's time.

## Agent Instructions

### When Working on This Project

1. **Always read the master plan first**: See [thesolution/00-MASTER-PLAN.md](thesolution/00-MASTER-PLAN.md) for current status and phase overview.
2. **Update the plan as you work**: When you complete a task, mark it done in the relevant phase file (thesolution/04-18). When you discover new requirements or issues, add them.
3. **Follow the phase order**: Phases build on each other. Do not skip ahead unless explicitly told to.
4. **Record data quality issues**: Any unexpected data formats, bad values, or API behavior must be documented in the relevant phase file under a "Known Issues" section.
5. **Never hardcode credentials**: All API keys, database passwords, and sensitive config go in `.env` files. Use `python-dotenv` to load them. Passwords are stored in `thesolution/credentials.yml` for easy reference.
6. **Prefer bulk extracts over API pagination**: SAM.gov rate limits are harsh (10/day without a role). Use monthly/daily extract downloads when available instead of paginated API calls.
7. **Test with real data**: The `workdir/converted/local database/` folder has real CSV reference data.
8. **Ignore OLD_ATTEMPTS and OLD_RESOURCES**: These contain archived prior work. Do not modify or reference files from these folders in new code. The relevant data has already been converted into `workdir/converted/`.

### Key Conventions

- **Language**: Python 3.14 for all data gathering, transformation, and loading
- **Database**: MySQL 8.0+ with InnoDB engine, utf8mb4 charset
- **Config**: `.env` file with `python-dotenv`, never commit `.env` to git
- **Logging**: Python `logging` module, structured output
- **API Clients**: One class per data source, all inherit from `BaseAPIClient`
- **API Key Selection**: SAM.gov supports 2 API keys (--key=1 or --key=2 on CLI). Key 2 has 1000/day limit.
- **Change Detection**: SHA-256 record hashing to detect changes between loads
- **Data Quality**: Configurable rules in `etl_data_quality_rule` table, not hardcoded

### Known Data Quality Issues (from prior SAM.gov imports)

These were discovered during the first import attempt and must be handled in the data cleaner:

1. ZIP codes containing city/state/country names (9,294 records in first import)
2. ZIP codes containing PO BOX data (27 records)
3. State fields containing dates (e.g., "05/03/1963")
4. Foreign addresses with province names > 2 chars in state field
5. Non-ASCII characters in country names (Reunion, Cote d'Ivoire)
6. Missing 3-letter country codes: XKS (Kosovo), XWB (West Bank), XGZ (Gaza)
7. CAGE codes with multiple values separated by comma+space
8. NAICS codes from retired vintages not in current lookup tables
9. Escaped pipe characters in DAT extract files (`|\|` must become `||`)
10. Dates in YYYYMMDD format needing conversion to DATE type
11. SBA type entries in DAT file concatenate code+date (e.g., "A620291223" = code "A6" + date "20291223")
12. Duplicate NAICS entries for some entities (same code, different flags) - 7 occurrences in monthly extract
13. SAM.gov Opportunities API returns `fullParentPathName` (dot-separated) instead of separate department/subTier/office fields
14. Opportunity `description` field is a URL, not text content (requires separate authenticated fetch)
15. SAM.gov Opportunities API rejects date ranges of exactly 365 days (error: "Date range must be null year(s) apart") — use 364-day max chunks
16. SAM.gov Opportunities API rejects Feb 29 as start date — historical load skips leap day
17. Opportunity `pop_state` field can contain ISO 3166-2 subdivision codes > 2 chars (e.g., IN-MH for India-Maharashtra) — column widened to VARCHAR(6)
18. SAM.gov Contract Awards API dates are in MM/DD/YYYY format (not ISO 8601) — awards_loader converts during load

### Project File References

| What | Location |
|------|----------|
| Python application | `fed_prospector/` (CLI: `python main.py --help`, 38 commands in 11 `cli/` modules) |
| Plan documents | `thesolution/` |
| Credentials (DB, API keys) | `thesolution/credentials.yml` |
| Quick start / environment setup | `thesolution/QUICKSTART.md` |
| Original Salesforce SOW (legacy) | `workdir/converted/SalesForce Customizations SOW_MS1.md` |
| SAM Entity API structure | `workdir/converted/entity_api_relationship.md` |
| Entity field mapping (154 fields) | `workdir/converted/local database/entity compare between formats.csv` |
| API rate limits & endpoints | `workdir/converted/salesforce to samgov api.csv` |
| NAICS codes (2022) | `workdir/converted/local database/data_to_import/2-6 digit_2022_Codes.csv` |
| SBA size standards | `workdir/converted/local database/data_to_import/naics_size_standards.csv` |
| PSC codes | `workdir/converted/local database/PSC April 2022 - PSC for 042022.csv` |
| Country codes | `workdir/converted/country_codes_combined.csv` |
| State codes | `workdir/converted/GG-Updated-Country-and-State-Lists - States.csv` |
| FIPS county codes | `workdir/converted/local database/FIPS COUNTY CODES.csv` |
| Proposed MySQL architecture | `workdir/converted/proposed mysql solution.md` |
| SAM Entity import doc (legacy) | `workdir/converted/PBDC - Import Entity API to SF.md` |
| Business type codes | `OLD_RESOURCES/BusTypes.csv` |
| OpenAPI specs (archived) | `OLD_RESOURCES/openapi_entityManagement.json`, `OLD_RESOURCES/samgov_complete.json` |
| DAT file parser (V2 pipe-delimited) | `fed_prospector/etl/dat_parser.py` |
| Bulk loader (LOAD DATA INFILE) | `fed_prospector/etl/bulk_loader.py` |
| SAM Opportunity API client | `fed_prospector/api_clients/sam_opportunity_client.py` |
| Opportunity loader | `fed_prospector/etl/opportunity_loader.py` |
| Prospect pipeline manager | `fed_prospector/etl/prospect_manager.py` |
| USASpending API client | `fed_prospector/api_clients/usaspending_client.py` |
| GSA CALC+ API client | `fed_prospector/api_clients/calc_client.py` |
| USASpending loader | `fed_prospector/etl/usaspending_loader.py` |
| GSA CALC+ loader | `fed_prospector/etl/calc_loader.py` |
| USASpending table DDL (2 tables) | `fed_prospector/db/schema/08_usaspending_tables.sql` |
| SAM Contract Awards API client | `fed_prospector/api_clients/sam_awards_client.py` |
| Awards loader (-> fpds_contract) | `fed_prospector/etl/awards_loader.py` |
| SAM Federal Hierarchy API client | `fed_prospector/api_clients/sam_fedhier_client.py` |
| Federal Hierarchy loader | `fed_prospector/etl/fedhier_loader.py` |
| SAM Exclusions API client | `fed_prospector/api_clients/sam_exclusions_client.py` |
| Exclusions loader | `fed_prospector/etl/exclusions_loader.py` |
| SAM Subaward API client | `fed_prospector/api_clients/sam_subaward_client.py` |
| Subaward loader | `fed_prospector/etl/subaward_loader.py` |
| Job scheduler definitions | `fed_prospector/etl/scheduler.py` |
| Health check dashboard | `fed_prospector/etl/health_check.py` |
| Database maintenance | `fed_prospector/etl/db_maintenance.py` |
| CLI modules (refactored from main.py) | `fed_prospector/cli/` (database, entities, opportunities, prospecting, calc, awards, fedhier, exclusions, spending, health, subaward) |
| Prior import progress notes (archived) | `OLD_ATTEMPTS/local database/progress story.txt` |
| SAM Contract Awards API research | `workdir/converted/sam-contract-awards-api.md` |
| USASpending Transactions API research | `workdir/converted/usaspending-transactions-api.md` |
| Phase 8 Web/API Readiness gap analysis | `thesolution/13-PHASE8-WEB-API-READINESS.md` |
| Phase 9 Schema Evolution plan | `thesolution/14-PHASE9-SCHEMA-EVOLUTION.md` |
| Phase 10 C# API Foundation plan | `thesolution/15-PHASE10-API-FOUNDATION.md` |
| Phase 11 Read Endpoints plan | `thesolution/16-PHASE11-READ-ENDPOINTS.md` |
| Phase 12 Capture Management API plan | `thesolution/17-PHASE12-CAPTURE-MANAGEMENT-API.md` |
| Phase 13 Auth & Production plan | `thesolution/18-PHASE13-AUTH-AND-PRODUCTION.md` |
