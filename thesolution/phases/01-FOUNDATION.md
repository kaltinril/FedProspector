# Phase 1: Foundation

**Status**: COMPLETE (2026-02-22)
**Dependencies**: None (first phase)
**Deliverable**: Working MySQL database with reference tables populated; Python project skeleton that connects to DB

---

## Tasks

### 1.1 MySQL Database Setup -- DONE (2026-02-22)
- [x] Install/verify MySQL 8.0+ is running locally (MySQL 8.4.8 LTS at D:\mysql)
- [x] Create database `fed_contracts` with utf8mb4 charset
- [x] Create application user `fed_app` with appropriate grants
- [x] Execute all DDL from [02-DATABASE-SCHEMA.md](../reference/02-DATABASE-SCHEMA.md):
  - [x] Reference tables (`ref_*` - 10 tables, schema doc said 9 but ref_entity_structure was a 10th)
  - [x] Entity tables (10 tables)
  - [x] Opportunity tables (2 tables)
  - [x] Federal data tables (3 tables)
  - [x] ETL tables (4 tables)
  - [x] Prospecting tables (5 tables, schema doc said 4 but saved_search was a 5th)
  - [x] Views (2 views)
- [x] Verify all tables created successfully (35 tables + 2 views confirmed at Phase 1; now 40 tables + 4 views after all phases)
- [x] Verify foreign key relationships are correct (15 FKs confirmed)

> **Note**: Schema doc summary said 32 tables but actual DDL defines 35. Originally 34 from Phase 1; usaspending_award added in Phase 5B. The ref_entity_structure (10th reference table) and saved_search (5th prospecting table) were listed in the DDL but not in the count summary. All are created. **Current total (all phases complete)**: 40 tables + 4 views. Phase 5 added sam_exclusion, sam_subaward, usaspending_transaction; Phase 7 added ref_sba_type; opportunity_relationship table and v_procurement_intelligence/v_incumbent_profile views added later.

### 1.2 Python Project Scaffolding -- DONE (2026-02-22)
- [x] Create project directory structure per [03-PYTHON-ARCHITECTURE.md](../reference/03-PYTHON-ARCHITECTURE.md)
- [x] Create `requirements.txt` with core dependencies
- [x] Create `.env.example` template
- [x] Create `.gitignore` (include .env, __pycache__, data/downloads/*)
- [x] Set up virtual environment (`.venv/` in fed_prospector/)
- [x] Install dependencies (all 7 packages + transitive deps installed)
- [x] Implement `config/settings.py` with dotenv loading
- [x] Implement `config/logging_config.py`
- [x] Implement `db/connection.py` with connection pooling
- [x] Verify Python can connect to MySQL (`python main.py status` works)

### 1.3 Load Reference Data -- DONE (2026-02-22)
- [x] `ref_naics_code` - 2,264 rows (2,125 from 2022 + 139 unique from 2017)
- [x] `ref_sba_size_standard` - 978 rows (18 skipped due to exception NAICS codes like `115310e1`)
- [x] `ref_naics_footnote` - 29 rows
- [x] `ref_psc_code` - 6,062 rows (parent_psc_code widened to VARCHAR(200) for category names)
- [x] `ref_country_code` - 252 rows (includes XKS, XWB, XGZ added automatically)
- [x] `ref_state_code` - 71 rows
- [x] `ref_fips_county` - 3,243 rows (state carried forward from group headers)
- [x] `ref_business_type` - 75 rows
- [x] `ref_set_aside_type` - 14 rows (hardcoded seed data)
- [x] Total: 12,988 rows across 9 tables (now 11 tables / ~13,001 rows after Phase 7 added ref_sba_type and ref_entity_structure)

> **Known Issue**: SBA size standards CSV has 18 "exception" NAICS codes (e.g., `115310e1`, `541330e2`) that don't match standard NAICS codes. These represent alternate size standards for specific subsectors. Skipped with warnings for now - could be handled by stripping the suffix and storing as a secondary record.

### 1.4 Base API Client -- DONE (2026-02-22)
- [x] Implement `api_clients/base_client.py`:
  - [x] Rate limit checking via `etl_rate_limit` table
  - [x] Rate limit incrementing (INSERT ON DUPLICATE KEY UPDATE)
  - [x] Retry with exponential backoff (429/5xx/connection/timeout)
  - [x] Request/response logging
  - [x] Pagination generator
- [x] Implement `etl/load_manager.py` (start_load, complete_load, fail_load, log_record_error)
- [ ] Write unit tests for base client retry logic (deferred - tested via integration)

### 1.5 ETL Infrastructure -- DONE (2026-02-22)
- [x] Implement `utils/hashing.py` (SHA-256 record hashing)
- [x] Implement `utils/date_utils.py` (YYYYMMDD, YYYY-MM-DD, MM/dd/yyyy conversion)
- [x] Implement `utils/parsing.py` (pipe-delimited, tilde-delimited, pipe escape fixing)
- [x] Implement `etl/change_detector.py` (classify_records, compute_field_diff, log_changes)
- [ ] Write unit tests for utilities (deferred - tested via integration)

### 1.6 CLI Entry Point -- DONE (2026-02-22)
- [x] Implement `main.py` with click:
  - [x] `build-database` command (with --drop-first for rebuild)
  - [x] `load-lookups` command (with --table for individual tables)
  - [x] `status` command (connection, row counts, API limits, recent loads)
  - [x] `check-api` command (test SAM.gov API key)
- [x] Verify CLI works end-to-end: `python main.py build-database && python main.py load-lookups`

---

## Self-Service Commands

The system is fully runnable without AI:

```bash
cd fed_prospector
source .venv/Scripts/activate        # Git Bash
# or: .venv\Scripts\activate.bat     # CMD

python main.py build-database        # Create/rebuild all 40 tables + 4 views
python main.py load-lookups          # Load all 11 reference tables from CSVs
python main.py load-lookups --table naics   # Load just one table
python main.py status                # Show everything: tables, counts, API status
python main.py check-api             # Test SAM.gov API key (uses 1 call)
python main.py build-database --drop-first  # Nuclear option: drop and rebuild
```

---

## Acceptance Criteria

1. [x] MySQL database has all 35 tables and 2 views created (now 40 tables + 4 views after later phases)
2. [x] All 9 reference tables are populated with correct row counts (12,988 total; now 11 tables / ~13,001 rows after Phase 7)
3. [x] Python project runs `main.py status` and shows database connection + table stats
4. [x] `.env.example` exists with all required config keys documented
5. [x] No hardcoded credentials anywhere in code
6. [x] Base API client implements retry and rate limiting (unit tests deferred)

---

## Files Created

```
fed_prospector/
    .env                          # Actual config (git-ignored)
    .env.example                  # Template
    .gitignore
    requirements.txt
    main.py                       # CLI entry point
    config/__init__.py
    config/settings.py            # Environment config
    config/logging_config.py      # Structured logging
    api_clients/__init__.py
    api_clients/base_client.py    # Rate limiting, retry, pagination
    etl/__init__.py
    etl/load_manager.py           # Load log tracking
    etl/change_detector.py        # SHA-256 change detection
    etl/reference_loader.py       # CSV -> MySQL reference loader
    db/__init__.py
    db/connection.py              # Connection pool
    db/schema/00_create_database.sql
    db/schema/01_reference_tables.sql
    db/schema/02_entity_tables.sql
    db/schema/03_opportunity_tables.sql
    db/schema/04_federal_tables.sql
    db/schema/05_etl_tables.sql
    db/schema/06_prospecting_tables.sql
    db/schema/07_views.sql
    utils/__init__.py
    utils/hashing.py              # SHA-256 record hashing
    utils/date_utils.py           # Date format conversion
    utils/parsing.py              # Pipe/tilde parsing
    tests/__init__.py
    tests/conftest.py             # Pytest fixtures (stub)
    data/downloads/.gitkeep
    data/logs/.gitkeep
```

---

## Known Issues Encountered and Resolved

- **NAICS CSV header has extra spaces**: `2022 NAICS US   Code` (3 spaces) - handled in loader
- **PSC parent_psc_code too long**: Data has category names up to 80 chars, column was VARCHAR(50) - widened to VARCHAR(200)
- **SBA exception codes**: 18 rows with codes like `115310e1` not in NAICS table - skipped with warning
- **FIPS state column sparse**: State only on first county of each group - loader carries forward last state
- **Country footnote markers**: `[b]` in country names - stripped with regex
- BusTypes.csv in OLD_RESOURCES/, not workdir/ - handled via settings.OLD_RESOURCES path
