# Python Architecture Design

## Overview

The Python application is a data pipeline that gathers federal contract data from multiple government APIs, transforms/cleans it, and loads it into MySQL. It runs as CLI scripts and scheduled jobs, not a web application.

## Project Structure

```
fed_prospector/
    config/
        __init__.py
        settings.py              # Environment-based config (DB, API keys)
        logging_config.py        # Structured logging setup
    api_clients/
        __init__.py
        base_client.py           # Abstract base with retry, rate limiting, pagination
        sam_entity_client.py     # SAM Entity Management API v1-4
        sam_extract_client.py    # SAM Bulk Extract downloads (monthly/daily)
        sam_opportunity_client.py # SAM Opportunities API v2
        sam_fedhier_client.py    # SAM Federal Hierarchy API
        sam_awards_client.py     # SAM Contract Awards API
        sam_exclusions_client.py # SAM Exclusions API
        sam_subaward_client.py   # SAM Subaward Reporting API
        fpds_client.py           # FPDS ATOM Feed parser (XML) (DEPRECATED)
        usaspending_client.py    # USASpending API (no auth, no rate limits)
        calc_client.py           # GSA CALC+ API (no auth)
    etl/
        __init__.py
        load_manager.py          # Orchestrates load operations, creates load_log entries
        entity_loader.py         # Entity data transformation and loading
        opportunity_loader.py    # Opportunity transformation and loading
        fedhier_loader.py        # Federal hierarchy loading
        fpds_loader.py           # FPDS award loading (DEPRECATED)
        reference_loader.py      # Load CSV reference tables from workdir
        change_detector.py       # Record hash comparison, field-level diff
        data_cleaner.py          # Data quality rules engine
        dat_parser.py            # V2 pipe-delimited DAT file parser
        bulk_loader.py           # LOAD DATA INFILE bulk loading
        usaspending_loader.py    # USASpending award data loading
        calc_loader.py           # GSA CALC+ labor rate loading
        prospect_manager.py      # Prospect tracking, saved searches, scoring
        subaward_loader.py       # Subaward loading, teaming partner analysis
        scheduler.py             # Job definitions, JobRunner, Windows Task Scheduler
        health_check.py          # Data freshness, API usage, alerts
        db_maintenance.py        # Archive history, purge staging, ANALYZE TABLE
    db/
        __init__.py
        connection.py            # MySQL connection pool (mysql-connector-python)
        schema/
            00_create_database.sql
            tables/
                10_reference.sql
                20_entity.sql
                30_opportunity.sql
                40_federal.sql
                50_etl.sql
                60_prospecting.sql
                70_usaspending.sql
            views/
                10_target_opportunities.sql
                20_competitor_analysis.sql
                30_procurement_intelligence.sql
                40_incumbent_profile.sql
        seed/
            seed_reference_data.py  # Load CSVs from workdir into ref tables
    # Note: Scheduler implemented in etl/scheduler.py (not a separate package)
    utils/
        __init__.py
        hashing.py               # SHA-256 record hashing for change detection
        parsing.py               # Tilde-delimited string parsing, DAT file parsing
        date_utils.py            # YYYYMMDD <-> DATE conversion
        file_utils.py            # ZIP/GZ extraction, file download streaming
    tests/
        __init__.py
        test_api_clients/
        test_etl/
        test_utils/
        conftest.py              # Shared fixtures (test DB, mock API responses)
    cli/                         # CLI command modules (refactored from main.py)
        __init__.py
        database.py              # build-database, load-lookups, status, check-api, seed-quality-rules
        entities.py              # download-extract, load-entities
        opportunities.py         # load-opportunities, search
        prospecting.py           # add-user, list-users, create/update/reassign/list/show prospect, notes, teams, saved searches, dashboard
        calc.py                  # load-calc
        awards.py                # load-awards
        fedhier.py               # load-hierarchy, search-agencies
        exclusions.py            # load-exclusions, check-exclusion, check-prospects
        spending.py              # load-transactions, burn-rate
        health.py                # check-health, run-job, maintain-db, run-all-searches
        subaward.py              # load-subawards, search-subawards, teaming-partners
        schema.py                # check-schema
    main.py                      # CLI entry point (170 lines, delegates to cli/ modules)
    requirements.txt
    requirements-dev.txt
    .env.example
    .gitignore
```

## Implementation Status

| Module | Status | Notes |
|--------|--------|-------|
| `config/settings.py` | Implemented | Phase 1 |
| `config/logging_config.py` | Implemented | Phase 1 |
| `api_clients/base_client.py` | Implemented | Phase 1 - retry, rate limiting, pagination |
| `api_clients/sam_entity_client.py` | Implemented | Phase 2 - v3 API, WOSB/8(a) search |
| `api_clients/sam_extract_client.py` | Implemented | Phase 2 - monthly/daily download, ZIP, JSON streaming |
| `api_clients/sam_opportunity_client.py` | Implemented | Phase 3 - v2 search, 5-call budget, priority set-aside ordering, date range splitting |
| `api_clients/sam_fedhier_client.py` | Implemented | Phase 5D - v1 API, full hierarchy refresh, agency search |
| `api_clients/sam_awards_client.py` | Implemented | Phase 5A - v1 API, search by NAICS/awardee/solicitation |
| `api_clients/sam_exclusions_client.py` | Implemented | Phase 5E - v4 API, check UEI/name, batch entity checks |
| `api_clients/sam_subaward_client.py` | Implemented | Phase 5G - v1 subcontracts API, search by prime/sub/NAICS, teaming analysis |
| `api_clients/fpds_client.py` | Deprecated | FPDS decommissioned Feb 2026, use SAM Contract Awards API |
| `api_clients/usaspending_client.py` | Implemented | Phase 5B - POST-based search, no auth, no rate limits |
| `api_clients/calc_client.py` | Implemented | Phase 5C - GET-based, no auth, no rate limits |
| `etl/load_manager.py` | Implemented | Phase 1 |
| `etl/entity_loader.py` | Implemented | Phase 2 - JSON normalization, 1+8 tables, SHA-256, batch commits |
| `etl/opportunity_loader.py` | Implemented | Phase 3 - SHA-256 change detection, opportunity_history, batch commits |
| `etl/reference_loader.py` | Implemented | Phase 1 + Phase 7 enrichment (hierarchy, categories, flags) |
| `etl/change_detector.py` | Implemented | Phase 2 |
| `etl/data_cleaner.py` | Implemented | Phase 2 - all 10 quality rules + DB-driven rules |
| `etl/dat_parser.py` | Implemented | Phase 2 - V2 pipe-delimited DAT files |
| `etl/bulk_loader.py` | Implemented | Phase 2 - LOAD DATA INFILE |
| `etl/awards_loader.py` | Implemented | Phase 5A - transforms Contract Awards API -> fpds_contract |
| `etl/usaspending_loader.py` | Implemented | Phase 5B/5B-Enhance - SHA-256 change detection, batch upsert, transactions, burn rate |
| `etl/calc_loader.py` | Implemented | Phase 5C - full_refresh with TRUNCATE + reload |
| `etl/prospect_manager.py` | Implemented | Phase 4 - prospect tracking, saved searches, scoring, dashboard |
| `etl/fedhier_loader.py` | Implemented | Phase 5D - hierarchy refresh, agency org normalization |
| `etl/exclusions_loader.py` | Implemented | Phase 5E - exclusion loading, prospect/team member cross-check |
| `etl/fpds_loader.py` | Deprecated | FPDS decommissioned Feb 2026, use awards_loader.py |
| `db/connection.py` | Implemented | Phase 1 |
| `etl/subaward_loader.py` | Implemented | Phase 5G - subaward loading, teaming partner analysis |
| `etl/scheduler.py` | Implemented | Phase 6 - 8 job definitions, JobRunner, Windows Task Scheduler |
| `etl/health_check.py` | Implemented | Phase 6 - data freshness, API usage, alerts, key status |
| `etl/db_maintenance.py` | Implemented | Phase 6 - archive history, purge staging, ANALYZE TABLE |
| `etl/schema_checker.py` | Implemented | Schema drift detection - compares live DB to DDL files |
| `db/schema/tables/*.sql`, `db/schema/views/*.sql` | Implemented | Phase 1 + Phase 5/7/9 - 54 tables + 4 views |
| `main.py` | Implemented | 170 lines, delegates to 12 cli/ modules (39 commands) |
| `cli/*.py` | Implemented | 12 modules: database, entities, opportunities, prospecting, calc, awards, fedhier, exclusions, spending, health, subaward, schema |

## Core Dependencies

```
# requirements.txt
requests>=2.31.0           # HTTP client for REST APIs
mysql-connector-python>=8.2.0  # MySQL driver
python-dotenv>=1.0.0       # .env file loading
lxml>=5.0.0                # XML parsing (FPDS ATOM feeds)
apscheduler>=3.10.0        # Job scheduling
click>=8.1.0               # CLI framework
tqdm>=4.66.0               # Progress bars for bulk loads

# requirements-dev.txt
pytest>=7.4.0
pytest-mock>=3.12.0
responses>=0.24.0          # Mock HTTP responses
```

## Module Designs

### config/settings.py

```python
"""Environment-based configuration. Never hardcode secrets."""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Database
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = int(os.getenv("DB_PORT", "3306"))
DB_NAME = os.getenv("DB_NAME", "fed_contracts")
DB_USER = os.getenv("DB_USER", "fed_app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# SAM.gov API
SAM_API_KEY = os.getenv("SAM_API_KEY", "")
SAM_API_BASE_URL = "https://api.sam.gov"
SAM_DAILY_LIMIT = int(os.getenv("SAM_DAILY_LIMIT", "10"))  # 10 without role, 1000 with

# GSA CALC API (no auth needed)
CALC_API_BASE_URL = "https://api.gsa.gov/acquisition/calc/v3/api"

# USASpending API (no auth needed)
USASPENDING_API_BASE_URL = "https://api.usaspending.gov"

# FPDS ATOM Feed (no auth needed)
FPDS_ATOM_BASE_URL = "https://www.fpds.gov/dbsight/FEEDS/ATOM"

# Paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = Path(os.getenv("DATA_DIR", str(PROJECT_ROOT / "data")))
DOWNLOAD_DIR = DATA_DIR / "downloads"
LOG_DIR = DATA_DIR / "logs"

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
```

### .env.example

```env
# Database
DB_HOST=localhost
DB_PORT=3306
DB_NAME=fed_contracts
DB_USER=fed_app
DB_PASSWORD=changeme

# SAM.gov API (get key at sam.gov, expires every 90 days)
SAM_API_KEY=your_api_key_here
SAM_DAILY_LIMIT=10

# Directories
DATA_DIR=./data
LOG_LEVEL=INFO
```

### api_clients/base_client.py

```python
"""Abstract base class for all API clients.

Features:
- Automatic retry with exponential backoff
- Rate limit tracking via etl_rate_limit table
- Request logging
- Pagination support (generator-based)
"""

class BaseAPIClient:
    def __init__(self, base_url, api_key, source_name, max_daily_requests, db):
        self.base_url = base_url
        self.api_key = api_key
        self.source_name = source_name
        self.max_daily_requests = max_daily_requests
        self.db = db
        self.session = requests.Session()

    def _check_rate_limit(self) -> bool:
        """Query etl_rate_limit for today's count. Return True if under limit."""

    def _increment_rate_counter(self):
        """INSERT ... ON DUPLICATE KEY UPDATE requests_made = requests_made + 1"""

    def _request_with_retry(self, method, url, params=None,
                            max_retries=3, backoff_factor=2) -> requests.Response:
        """Make HTTP request with:
        - Rate limit check before each request
        - Exponential backoff on 429/5xx responses
        - Configurable max retries
        - Timeout (30s default)
        - Logging of all requests/responses
        """

    def paginate(self, endpoint, params, page_key='offset',
                 size_key='limit', total_key='totalRecords'):
        """Generator that yields pages of results.
        Handles pagination math and stops when all records retrieved.
        """
```

### api_clients/sam_entity_client.py

```python
"""SAM.gov Entity Management API v1-4 client.

Two modes:
1. API mode: Paginated queries for targeted lookups (10 records/page max)
2. Extract mode: Bulk download of monthly/daily files (bypasses rate limits)
"""

class SAMEntityClient(BaseAPIClient):
    ENTITY_ENDPOINT = "/entity-information/v1-4/entities"
    DOWNLOAD_ENDPOINT = "/entity-information/v1-4/download-entities"

    def get_entities_by_date(self, update_date, registration_status='A'):
        """Fetch entities updated on a specific date. Generator of pages."""

    def get_entity_by_uei(self, uei_sam):
        """Fetch a single entity by UEI SAM. Returns full JSON record."""

    def search_entities(self, **filters):
        """Search with arbitrary filters: businessTypeCode, sbaBusinessTypeCode,
        naicsCode, stateCode, etc. Generator of pages."""

    def request_bulk_extract(self, format='JSON', date_filter=None):
        """Request async bulk download. Returns token for retrieval."""

    def download_extract(self, token, output_path):
        """Stream download a bulk extract file to disk."""
```

### api_clients/sam_extract_client.py

```python
"""SAM.gov Extracts Download API.

Downloads monthly and daily entity extract files (ZIP -> DAT or JSON).
This is the primary mechanism for building the entity database,
as it bypasses the 10/day rate limit.
"""

class SAMExtractClient(BaseAPIClient):
    EXTRACT_ENDPOINT = "/data-services/v1/extracts"

    def download_monthly_extract(self, year, month, sensitivity='PUBLIC',
                                  charset='UTF-8', version='V2'):
        """Download monthly entity extract.
        Filename format: SAM_PUBLIC_UTF-8_MONTHLY_V2_YYYYMMDD.ZIP
        Note: exact date varies (first Sunday). Try target date, handle 404s.
        """

    def download_daily_extract(self, date, sensitivity='PUBLIC'):
        """Download daily incremental extract (Tue-Sat only)."""

    def parse_dat_file(self, file_path):
        """Parse pipe-delimited DAT file. Applies cleanup:
        1. Fix escaped pipes: |\\| -> ||
        2. Parse NULL markers: || -> None
        3. Split tilde-separated multi-value fields
        Returns: generator of dict records
        """
```

### api_clients/sam_opportunity_client.py

```python
"""SAM.gov Opportunities API v2 client.

Primary source for active contract solicitations.
"""

class SAMOpportunityClient(BaseAPIClient):
    ENDPOINT = "/opportunities/v2/search"

    def search_opportunities(self, posted_from, posted_to,
                              set_aside=None, naics=None,
                              ptype=None, limit=1000):
        """Search opportunities with filters. Generator of pages.

        Args:
            posted_from: MM/dd/yyyy format (required)
            posted_to: MM/dd/yyyy format (required, max 1 year from posted_from)
            set_aside: One of WOSB, EDWOSB, 8A, 8AN, SBA, etc.
            naics: 6-digit NAICS code
            ptype: o=solicitation, k=combined, p=presolicitation, r=sources sought
            limit: Records per page (max 1000)
        """

    def get_opportunity(self, notice_id):
        """Fetch a single opportunity by notice ID."""

    def get_wosb_opportunities(self, posted_from, posted_to, naics=None):
        """Convenience: search for WOSB set-aside opportunities."""

    def get_8a_opportunities(self, posted_from, posted_to, naics=None):
        """Convenience: search for 8(a) set-aside opportunities."""
```

### etl/change_detector.py

```python
"""Change detection using SHA-256 record hashing.

Strategy:
1. When loading data, compute SHA-256 hash of key fields
2. Compare against stored hash in the target table's record_hash column
3. If hash differs: compute field-level diff, log to *_history table, update record
4. If hash matches: skip (record unchanged)
5. If no existing record: insert new
"""

class ChangeDetector:
    def compute_hash(self, record: dict, fields: list) -> str:
        """SHA-256 of pipe-joined sorted field values."""

    def detect_changes(self, new_records, table_name, key_field, hash_field='record_hash'):
        """Compare new records against database.
        Returns: {'inserts': [...], 'updates': [...], 'unchanged': [...]}
        """

    def compute_field_diff(self, old_record, new_record, fields):
        """Return list of (field_name, old_value, new_value) for changed fields.
        Used to populate entity_history / opportunity_history tables.
        """

    def log_changes(self, diffs, entity_key, load_id, history_table):
        """Insert field-level changes into the appropriate history table."""
```

### etl/data_cleaner.py

```python
"""Data quality rules engine.

Applies configurable cleanup rules from etl_data_quality_rule table.
Also includes hardcoded rules for known SAM.gov data issues.

Known issues from prior imports:
1. ZIP codes containing city/state/country (9,294 records)
2. ZIP codes with PO BOX data (27 records)
3. State fields containing dates
4. Foreign province names in state field (> 2 chars)
5. Non-ASCII chars in country names
6. Missing country codes: XKS, XWB, XGZ
7. Multiple CAGE codes comma-separated
8. Retired NAICS codes not in lookup
9. Escaped pipes in DAT files
10. YYYYMMDD dates needing conversion
"""

class DataCleaner:
    def __init__(self, db):
        self.rules = self._load_rules_from_db()

    def clean_record(self, record, source_format='json'):
        """Apply all applicable rules to a record. Returns cleaned record."""

    def clean_zip_code(self, zip_code, city=None, state=None, country=None):
        """Remove city/state/country contamination from ZIP fields."""

    def clean_state_code(self, state_code, country_code=None):
        """Validate state code. Flag non-standard for foreign addresses."""

    def normalize_date(self, date_str):
        """Convert YYYYMMDD or other formats to Python date. Handle bad data."""

    def normalize_country_code(self, three_code):
        """Map 3-letter to standard code. Handle XKS, XWB, XGZ."""

    def split_cage_codes(self, cage_value):
        """Handle comma-separated CAGE codes. Return list."""

    def clean_pipe_escapes(self, raw_line):
        """Fix escaped pipe characters in DAT file lines."""
```

### etl/entity_loader.py

```python
"""Transform and load SAM entity data into normalized tables.

JSON structure -> normalized tables mapping:
    entityRegistration         -> entity (core fields)
    coreData.physicalAddress   -> entity_address (type='PHYSICAL')
    coreData.mailingAddress    -> entity_address (type='MAILING')
    coreData.generalInformation -> entity (structure/type/profit codes)
    coreData.businessTypes.businessTypeList     -> entity_business_type
    coreData.businessTypes.sbaBusinessTypeList  -> entity_sba_certification
    coreData.financialInformation              -> entity (credit_card, debt fields)
    assertions.goodsAndServices.naicsList      -> entity_naics
    assertions.goodsAndServices.pscList        -> entity_psc
    assertions.geographicalAreaServed          -> entity_disaster_response
    pointsOfContact.*                          -> entity_poc (6 types)
"""

class EntityLoader:
    def __init__(self, db, change_detector, data_cleaner):
        pass

    def load_from_json_extract(self, json_file_path, load_id):
        """Load from bulk JSON extract file. Main entry point for monthly loads."""

    def load_from_api_response(self, api_data, load_id):
        """Load from paginated API response. Used for daily incremental."""

    def load_from_dat_file(self, dat_file_path, load_id):
        """Load from pipe-delimited DAT file (fallback). Apply all cleanup."""

    def _normalize_entity(self, raw_json):
        """Extract and flatten entity core fields from nested JSON."""

    def _extract_child_records(self, raw_json, uei_sam):
        """Extract all child table records (NAICS, PSC, business types, etc.)"""

    def _upsert_entity(self, entity_data, load_id):
        """Insert or update entity with change detection and history logging."""

    def _sync_child_records(self, uei_sam, child_table, new_records, key_fields):
        """Sync many-to-many child records: insert new, delete removed."""
```

### etl/reference_loader.py

```python
"""Load reference data from CSV files in workdir into ref_* tables.

Sources:
    ref_naics_code          <- 2-6 digit_2022_Codes.csv + 6-digit_2017_Codes.csv
    ref_sba_size_standard   <- naics_size_standards.csv + Table of Size Standards March 2023
    ref_naics_footnote      <- footnotes.csv
    ref_psc_code            <- PSC April 2022 - PSC for 042022.csv
    ref_country_code        <- country_codes_combined.csv
    ref_state_code          <- GG-Updated-Country-and-State-Lists - States.csv
    ref_fips_county         <- FIPS COUNTY CODES.csv
    ref_business_type       <- OLD_RESOURCES/BusTypes.csv
    ref_set_aside_type      <- set_aside_types.csv (23 entries with categories)
"""

class ReferenceLoader:
    def load_all(self):
        """Load all reference tables from CSV files."""

    def load_naics_codes(self, csv_path):
        """Load NAICS codes. Handle 2-6 digit hierarchy and multiple vintages."""

    def load_size_standards(self, csv_path):
        """Load SBA size standards with footnote references."""

    def load_psc_codes(self, csv_path):
        """Load PSC codes with category hierarchy."""

    def load_country_codes(self, csv_path):
        """Load ISO country codes. Add XKS, XWB, XGZ manually."""

    def load_state_codes(self, csv_path):
        """Load state/territory codes."""

    def load_fips_counties(self, csv_path):
        """Load FIPS county codes."""

    def load_business_types(self, csv_path):
        """Load business type classification codes."""

    def seed_set_aside_types(self):
        """Insert known set-aside type codes (WOSB, 8A, SBA, HUBZone, etc.)"""
```

### scheduler/job_definitions.py

```python
"""Scheduled job definitions.

Recommended schedule:
    SAM Entity Daily Extract:   06:00 AM daily (Tue-Sat)
    SAM Opportunities:          Every 4 hours
    Federal Hierarchy:          Weekly (Sunday 02:00 AM)
    FPDS Awards:                Weekly (Saturday 03:00 AM)
    GSA CALC Rates:             Monthly (1st of month, 04:00 AM)
    USASpending Awards:         Monthly (1st of month, 05:00 AM)
    Exclusions Check:           Weekly (Monday 06:00 AM)
    API Key Expiry Alert:       Daily (check 90-day expiration)
"""

JOBS = [
    {
        'id': 'sam_entity_daily',
        'func': 'etl.load_manager:run_entity_daily',
        'trigger': 'cron',
        'hour': 6,
        'day_of_week': 'tue-sat',
    },
    {
        'id': 'sam_opportunities',
        'func': 'etl.load_manager:run_opportunities',
        'trigger': 'interval',
        'hours': 4,
    },
    # ... etc
]
```

### main.py (CLI)

```python
"""CLI entry point using click.

Commands:
    init-db          Create database schema
    load-reference   Load all reference data from CSVs
    load-entities    Run entity load (full or incremental)
    load-opportunities  Run opportunity load
    load-fedhier     Load federal hierarchy
    load-fpds        Load FPDS historical awards
    load-calc        Load GSA CALC labor rates
    load-usaspending Load USASpending award data
    run-scheduler    Start the job scheduler
    check-status     Show ETL load status and data freshness
    search           Search opportunities by filters
"""

@click.group()
def cli():
    pass

@cli.command()
def init_db():
    """Create all database tables."""

@cli.command()
@click.option('--source', default='all')
def load_reference(source):
    """Load reference data from CSV files."""

@cli.command()
@click.option('--mode', type=click.Choice(['full', 'daily']), default='daily')
@click.option('--date', default=None)
def load_entities(mode, date):
    """Load entity data from SAM.gov."""

@cli.command()
@click.option('--set-aside', default=None)
@click.option('--naics', default=None)
@click.option('--days-back', default=1, type=int)
def load_opportunities(set_aside, naics, days_back):
    """Load opportunities from SAM.gov."""
```

## Key Design Patterns

### 1. Rate Limit Safety
Every API client inherits rate limiting from `BaseAPIClient`. Before each request, the client checks `etl_rate_limit` table. If daily limit reached, raises `RateLimitExceeded` instead of making the request. This prevents accidental API key suspension.

### 2. Bulk Extract Preference
The SAM Entity pipeline defaults to bulk extract downloads (monthly/daily files) rather than paginated API queries. One download = one API call = complete dataset. This is critical when limited to 10 calls/day.

### 3. Idempotent Loads
Every load operation is idempotent. Running the same load twice produces the same result. This is achieved through:
- SHA-256 record hashing (skip unchanged records)
- UPSERT operations (INSERT ... ON DUPLICATE KEY UPDATE)
- Load IDs in `etl_load_log` for tracking and rollback

### 4. Streaming Processing
Large files (55MB+ JSON extracts, monthly DAT files) are processed as streams/generators, not loaded entirely into memory. Each record is processed, transformed, and written to MySQL individually or in small batches.

### 5. Separation of Concerns
- API clients only handle HTTP communication
- Loaders handle data transformation and database writes
- Change detector handles comparison logic
- Data cleaner handles quality rules
- Load manager orchestrates the full pipeline

## Performance Notes

For initial bulk loads of 500K+ entity records, Python should be sufficient. If loading speed becomes a bottleneck, potential optimizations before switching languages:

1. **LOAD DATA INFILE** - MySQL's fastest bulk load mechanism (skip Python INSERT loops)
2. **Batch inserts** - INSERT with 1000+ value tuples per statement
3. **Disable indexes** during load, rebuild after
4. **Connection pooling** - Reuse connections across operations
5. **multiprocessing** - Parallelize independent table loads

If these are insufficient, C# or Go could be evaluated for the loading step specifically, while keeping Python for API communication and orchestration.
