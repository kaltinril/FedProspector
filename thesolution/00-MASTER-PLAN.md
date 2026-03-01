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
**File**: [04-PHASE1-FOUNDATION.md](04-PHASE1-FOUNDATION.md)

- ~~Set up MySQL database~~ 36 tables + 2 views
- ~~Load reference data from CSVs~~ 12,988 rows across 9 tables
- ~~Python project scaffolding~~ config, logging, DB pool, CLI
- ~~Base API client~~ rate limit via DB, exponential backoff
- ~~CLI entry point~~ `python main.py` (26 commands across 7 `cli/` modules)
- **Deliverable**: DONE

### Phase 2: Entity Data Pipeline (Proof of Concept - 1 Source)
**Status**: [x] COMPLETE (2026-02-22) - 865K entities loaded
**File**: [05-PHASE2-ENTITY-PIPELINE.md](05-PHASE2-ENTITY-PIPELINE.md)

- ~~Build SAM.gov Entity API client~~ `sam_entity_client.py` (v3 API, WOSB/8(a) search)
- ~~Build SAM.gov Extract client~~ `sam_extract_client.py` (monthly/daily download, ZIP, JSON streaming via ijson)
- ~~Implement data cleaner~~ `data_cleaner.py` (all 10 quality rules + DB-driven rules)
- ~~Implement entity loader~~ `entity_loader.py` (JSON normalization, 1+8 tables, SHA-256 change detection, batch commits)
- ~~Implement DAT parser + bulk loader~~ `dat_parser.py` + `bulk_loader.py` (V2 DAT files, LOAD DATA INFILE)
- ~~CLI commands~~ `download-extract`, `load-entities`, `seed-quality-rules`
- ~~Download monthly extract and execute initial bulk load~~ 865,232 entities in ~4.5 min
- **Deliverable**: DONE

### Phase 3: Opportunities Pipeline (Proof of Concept - Load First Data)
**Status**: [~] IN PROGRESS (2026-02-28) - 12,209 opportunities loaded (2-year historical), polling pending
**File**: [06-PHASE3-OPPORTUNITIES-PIPELINE.md](06-PHASE3-OPPORTUNITIES-PIPELINE.md)

- ~~Build SAM.gov Opportunities API client~~ `sam_opportunity_client.py` (v2 search, 5-call budget, priority set-aside ordering)
- ~~Implement opportunity loader with change tracking~~ `opportunity_loader.py` (SHA-256 hashing, opportunity_history)
- ~~Create CLI commands~~ `load-opportunities` (--max-calls, --historical) + `search` (local DB query)
- ~~Initial + historical load~~ 12,209 opportunities across 12 SB set-aside types (2-year range, Mar 2024 - Feb 2026)
- [ ] Set up scheduled polling (Phase 6)
- **Note**: SAM.gov API key 2 confirmed at 1000/day tier (enables full historical loads)
- **Deliverable**: IN PROGRESS - Historical opportunities loaded, search working, scheduled polling pending (Phase 6)

### Phase 4: Sales/Prospecting Pipeline
**Status**: [x] COMPLETE (2026-02-22)
**File**: [07-PHASE4-SALES-PROSPECTING.md](07-PHASE4-SALES-PROSPECTING.md)

- ~~Build prospect tracking tables and workflow~~ `ProspectManager` class + 12 CLI commands
- ~~Implement saved search/filter system~~ `save-search`, `run-search`, `list-searches` with dynamic SQL
- ~~Build go/no-go scoring framework~~ 4-criterion scoring (0-40 scale): set-aside, time, NAICS match, value
- ~~Create prospect notes and activity logging~~ Auto-logged status changes, assignments; manual notes
- ~~Pipeline dashboard~~ `dashboard` command with status counts, due this week, workload, win/loss stats
- **Deliverable**: DONE

### Phase 5: Extended Data Sources (Remaining Phases Build-Out)
**Status**: [~] IN PROGRESS (2026-02-28) - 5A, 5B, 5B-Enhance, 5C complete
**File**: [08-PHASE5-EXTENDED-SOURCES.md](08-PHASE5-EXTENDED-SOURCES.md)

- ~~SAM.gov Contract Awards API~~ `sam_awards_client.py` + `awards_loader.py` (v1 API, search by NAICS/awardee/solicitation, loads to `fpds_contract`)
- ~~USASpending.gov API~~ `usaspending_client.py` + `usaspending_loader.py` (POST-based search, SHA-256 change detection, incumbent search working)
- ~~USASpending Transaction History (5B-Enhance)~~ `usaspending_transaction` table, `load_transactions()`, `calculate_burn_rate()` for spend analysis
- [ ] FPDS ATOM Feed (deep historical procurement data)
- ~~GSA CALC+ API~~ `calc_client.py` + `calc_loader.py` (full_refresh, ~52K labor rates loaded)
- [ ] SAM.gov Federal Hierarchy API (agency org structure)
- [ ] SAM.gov Exclusions API (due diligence)
- [ ] SAM.gov Subaward Reporting API (subcontracting intelligence)
- **Key capability**: Incumbent analysis -- USASpending, FPDS, and Contract Awards data combine to identify previous contract winners, their pricing, and period of performance end dates. This enables predicting rebids before they post and crafting competitive proposals. See [01-RESEARCH-AND-DATA-SOURCES.md](01-RESEARCH-AND-DATA-SOURCES.md) "Incumbent & Competitive Intelligence Strategy" section.
- **CLI refactored**: `main.py` (1752 -> 126 lines) with 26 commands split into `cli/` modules (database, entities, opportunities, prospecting, calc, awards, spending)
- **New CLI commands**: `load-awards`, `load-transactions`, `burn-rate`
- **Deliverable**: IN PROGRESS - 5A (Contract Awards), 5B (USASpending), 5B-Enhance (Transactions), 5C (GSA CALC+) complete; 5D/5E/5F/5G pending

### Phase 6: Automation and Monitoring
**Status**: [ ] Not Started
**File**: [09-PHASE6-AUTOMATION.md](09-PHASE6-AUTOMATION.md)

- Fully automated daily/weekly/monthly refresh schedule
- Error alerting and monitoring
- API key expiration reminders (90-day cycle)
- Data staleness detection
- Operational documentation and runbooks
- **Deliverable**: Hands-off daily operation with alerts for issues

### Phase 7: Reference Data Enrichment
**Status**: [ ] Not Started
**File**: [12-PHASE7-REFERENCE-ENRICHMENT.md](12-PHASE7-REFERENCE-ENRICHMENT.md)

- Enrich `ref_business_type` with categories and socioeconomic flags
- Load `ref_entity_structure` (currently empty -- 8 codes discovered from entity data)
- Merge SAM.gov territory codes into `ref_country_code` with ISO standard flags
- Add NAICS hierarchy metadata (Sector/Subsector/Industry Group/Industry/National Industry)
- Expand `ref_set_aside_type` from 14 hardcoded to comprehensive CSV-driven load
- New `ref_sba_type` lookup table for SBA certification codes
- Update views with enriched JOINs for human-readable output
- FPDS.gov deprecation: update Phase 5F docs, add SAM.gov Contract Awards API URL
- **Deliverable**: All reference tables enriched, repeatable via `load-lookups`, views show human-readable data

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
| [01-RESEARCH-AND-DATA-SOURCES.md](01-RESEARCH-AND-DATA-SOURCES.md) | All federal data sources with APIs, limits, and priority ranking |
| [02-DATABASE-SCHEMA.md](02-DATABASE-SCHEMA.md) | Complete MySQL DDL for all tables, views, and indexes |
| [03-PYTHON-ARCHITECTURE.md](03-PYTHON-ARCHITECTURE.md) | Python module design, patterns, and class structure |
| [10-DATA-OVERLAP-AND-LIMITS.md](10-DATA-OVERLAP-AND-LIMITS.md) | Data redundancy map and rate limit strategy |
| [11-LEGAL-CONSIDERATIONS.md](11-LEGAL-CONSIDERATIONS.md) | Terms of use, PII, D&B restrictions |
| [QUICKSTART.md](QUICKSTART.md) | Environment setup guide (MySQL, Python, SAM.gov API key) |
| [credentials.yml](credentials.yml) | All local dev passwords (MySQL root, fed_app, SAM.gov API key) |
