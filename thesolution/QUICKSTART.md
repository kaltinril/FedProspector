# Quick Start Guide

Get your local environment ready for the Federal Contract Prospecting System.

---

## Your Environment (validated 2026-02-22)

| Component | Status | Details |
|-----------|--------|---------|
| Windows 11 Pro | Ready | Build 10.0.26200 |
| Python 3.14.3 | Ready | `C:\Users\jerem\AppData\Local\Python\pythoncore-3.14-64\python.exe` |
| pip 25.3 | Ready | Bundled with Python 3.14 (`python -m pip`) |
| Git 2.51.2 | Ready | `C:\Program Files\Git\cmd\git.exe` |
| MySQL 8.4.8 LTS | Ready | Standalone ZIP extract at `D:\mysql\` (no installer, no service) |
| MySQL Workbench 8.0.46 | Ready | `C:\Program Files\MySQL\MySQL Workbench 8.0 CE\` |
| `fed_contracts` database | Ready | Created 2026-02-22, utf8mb4 charset |
| `fed_app` user | Ready | Full privileges on `fed_contracts` |
| SAM.gov API key | Ready | Free tier (10 calls/day), stored in `samgov.yml` and `credentials.yml` |
| Reference CSV files | Ready | All 10 files present in `workdir/converted/` |

> **Python note**: Python 3.10 has been uninstalled. `python` resolves to 3.14.3 via the Windows App Execution Alias. Use `python -m pip` for pip commands.

> **Credentials**: All passwords stored in [credentials.yml](credentials.yml) (not committed to git). Replace `<your_root_password>` and `<your_app_password>` placeholders throughout this doc with your actual values from that file.

---

## Prerequisites Checklist

- [x] Windows 10/11
- [x] Python 3.14.3 installed
- [x] pip 25.3 installed
- [x] Git 2.51.2 installed
- [x] MySQL 8.4.8 LTS installed (standalone at `D:\mysql\`)
- [x] MySQL Workbench 8.0.46 installed
- [x] Reference data CSV files in place
- [x] MySQL data directory initialized
- [x] MySQL server running
- [x] `fed_contracts` database created
- [x] `fed_app` database user created with grants
- [x] SAM.gov API key obtained (stored in `samgov.yml` and `credentials.yml`)
- [x] Python virtual environment created (`fed_prospector/.venv/`)
- [x] `.env` file configured (`fed_prospector/.env`)
- [x] All dependencies installed (Phase 1 complete)

---

## Step 1: MySQL Fresh Install (DONE)

MySQL 8.4.8 LTS was installed from a ZIP extract at `D:\mysql\`. This is a standalone installation with no Windows service.

### 1a. Initialize Data Directory

This was run once to create a fresh data directory with a passwordless root user:

```bash
D:\mysql\bin\mysqld.exe --initialize-insecure --basedir=D:\mysql --datadir=D:\mysql\data
```

### 1b. Start the Server

MySQL is started manually. Open a **separate** terminal window (it stays open while the server runs):

```bash
D:\mysql\bin\mysqld.exe --basedir=D:\mysql --datadir=D:\mysql\data --console --secure-file-priv=""
```

You should see output ending with `ready for connections` on port 3306. Leave this terminal open.

### 1c. Set Root Password, Create Database and App User

In a **second** terminal, connect with the passwordless root and set everything up:

```bash
D:\mysql\bin\mysql.exe -u root --skip-password
```

```sql
ALTER USER 'root'@'localhost' IDENTIFIED BY '<your_root_password>';
CREATE DATABASE fed_contracts CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'fed_app'@'localhost' IDENTIFIED BY '<your_app_password>';
GRANT ALL PRIVILEGES ON fed_contracts.* TO 'fed_app'@'localhost';
GRANT FILE ON *.* TO 'fed_app'@'localhost';
FLUSH PRIVILEGES;
```

### 1d. Verify

```bash
-- Root login with new password
D:\mysql\bin\mysql.exe -u root -p<your_root_password> -e "SELECT VERSION(); SHOW DATABASES;"

-- App user login
D:\mysql\bin\mysql.exe -u fed_app -p<your_app_password> -e "USE fed_contracts; SELECT 'OK' AS status;"
```

### (Optional) Register MySQL as a Windows Service

If you'd rather have MySQL start automatically with Windows instead of running it manually each time:

```bash
# Run as Administrator
D:\mysql\bin\mysqld.exe --install MySQL84 --defaults-file=D:\mysql\my.ini
net start MySQL84
```

Then you can add `D:\mysql\bin` to your system PATH so `mysql` works from anywhere.

---

## Step 2: Python - Already Installed (DONE)

Python 3.14.3 is installed. Python 3.10 was uninstalled.

```
Python:  C:\Users\jerem\AppData\Local\Python\pythoncore-3.14-64\python.exe
pip:     python -m pip (25.3)
```

No action needed.

---

## Step 3: Get a SAM.gov API Key

You need a free API key to access SAM.gov data. Without a role assignment, you get 10 API calls/day (the system is designed around this limit using bulk extracts).

If you already have a key from the prior attempt, check if it's still valid (they expire every 90 days). If expired or lost:

1. Go to https://sam.gov
2. Log in (use your business login if you have one)
3. Navigate to your profile and request a **Public API Key**
4. The key will be emailed to you or shown on screen
5. Save it in [credentials.yml](credentials.yml) under `sam_gov.api_key`

> **Note**: If you have a Federal role or Entity Administrator role on SAM.gov, you may be able to request up to 1,000 calls/day. Update `SAM_DAILY_LIMIT` accordingly. See the [Upgrading SAM.gov API Rate Limits](#upgrading-samgov-api-rate-limits-10day---1000day) section below.

---

## Upgrading SAM.gov API Rate Limits (10/day -> 1,000/day)

### Current Situation

- **Default (no role)**: 10 API calls/day across ALL SAM.gov APIs (Entity, Opportunities, Federal Hierarchy, Exclusions, etc.)
- **With entity role**: 1,000 API calls/day
- **Federal system account**: 10,000 API calls/day (federal agencies only)

### Rate Limit Tiers

| Account Type | Daily Limit | Who Can Get It |
|-------------|-------------|----------------|
| Personal API key (no role) | 10/day | Anyone with a SAM.gov account |
| Personal API key (with role) | 1,000/day | Registered entities in SAM.gov |
| System account API key | 10,000/day | Federal government agencies only |

### How to Upgrade from 10 to 1,000 Calls/Day

Your business must be **registered as an entity in SAM.gov** (which it should already be if you're bidding on federal contracts). Then you request a role assignment.

**Step-by-step process:**

1. **Verify entity registration**: Log into SAM.gov. Your business should already have a Unique Entity ID (UEI). If not, register at https://sam.gov/content/entity-registration (takes up to 10 business days for initial registration).

2. **Request a role**:
   - Log into SAM.gov
   - Go to your **Account Details** page (click your name in the top right -> Account Details)
   - Look for the **"Request Role"** or **"Manage Roles"** section
   - Request the **"Data Entry"** role (or equivalent API access role)
   - Provide a business justification - be specific: e.g., *"Building internal tool to monitor WOSB/8(a) contract opportunities by NAICS code for bid/no-bid decisions"*

2.1. **Detailed steps**
    1.	Have your wife log into https://sam.gov
    2.	Click her name (top-right) → Workspace
    3.	Click your entity (MSOne LLC)
    4.	Click the Users tab
    5.	Click Assign Roles
    6.	Enter your email address (the email tied to your SAM.gov account)
    7.	Select Entity Administrator role
    8.	Click Submit
    9.	Check your email and click the SAM.gov link to accept the role
    10.	Log into SAM.gov and verify under Workspace → MSOne LLC → Users that your role is assigned
    After this, your API limit will increase to 1,000 calls/day automatically.



3. **Wait for approval**: Role approval typically takes **1-2 weeks** after entity registration is complete. Total timeline from scratch: ~2-3 weeks.

4. **Verify upgrade**: After role approval, your existing API key automatically gets the higher limit. Run `python main.py check-api` to verify. You can also check your daily usage with `python main.py status`.

5. **Update config**: Once approved, update your `.env` file:
   ```
   SAM_DAILY_LIMIT=1000
   ```

### Tips

- Your API key **expires every 90 days** - set a calendar reminder to regenerate it on your SAM.gov Account Details page
- The 1,000/day limit is **shared across all SAM.gov APIs** (Entity, Opportunities, Federal Hierarchy, etc.)
- You can have both a personal API key and a system account API key if needed
- If you need more than 1,000/day, rate limit exception requests are handled case-by-case with business justification
- Contact SAM.gov support at https://www.fsd.gov for issues with role assignment

### Why This Matters

With 10 calls/day, our daily opportunity refresh uses 4-5 calls (one per priority set-aside type), leaving only 5-6 for everything else. With 1,000/day, we can query all 12 set-aside types multiple times per day, run entity lookups, and use other SAM.gov APIs freely.

---

## Step 4: Set Up the Python Project

From the project root (`pbdc/`), create the Python project directory and virtual environment:

```bash
# Create the project directory (from pbdc/ root)
mkdir fed_prospector
cd fed_prospector

# Create virtual environment
python -m venv .venv

# Activate it (Windows - Git Bash)
source .venv/Scripts/activate

# Activate it (Windows - PowerShell)
.venv\Scripts\Activate.ps1

# Activate it (Windows - CMD)
.venv\Scripts\activate.bat
```

### Create the .env File

Create `fed_prospector/.env` with credentials from [credentials.yml](credentials.yml):

```env
# Database (MySQL at D:\mysql)
DB_HOST=localhost
DB_PORT=3306
DB_NAME=fed_contracts
DB_USER=fed_app
DB_PASSWORD=<your_app_password>

# SAM.gov API (expires every 90 days)
SAM_API_KEY=your_actual_api_key_here
SAM_DAILY_LIMIT=10

# Directories
DATA_DIR=./data
LOG_LEVEL=INFO
```

---

## Step 5: Verify Everything Works

### Test MySQL Connection

```bash
D:\mysql\bin\mysql.exe -u fed_app -p<your_app_password> -e "USE fed_contracts; SELECT 'Connection OK' AS status;"
```

### Test Python + MySQL Driver

```bash
python -m pip install mysql-connector-python python-dotenv
```

```python
# Quick test script - run with: python test_connection.py
import os
from dotenv import load_dotenv
import mysql.connector

load_dotenv()

conn = mysql.connector.connect(
    host=os.getenv("DB_HOST", "localhost"),
    port=int(os.getenv("DB_PORT", "3306")),
    database=os.getenv("DB_NAME", "fed_contracts"),
    user=os.getenv("DB_USER", "fed_app"),
    password=os.getenv("DB_PASSWORD", ""),
)
print(f"Connected to MySQL {conn.get_server_info()}")
print(f"Database: {conn.database}")
conn.close()
print("Success! Environment is ready.")
```

### Test SAM.gov API Key

```python
# Quick test - run with: python test_sam_api.py
import os
import requests
from dotenv import load_dotenv

load_dotenv()

api_key = os.getenv("SAM_API_KEY")
if not api_key or api_key == "your_api_key_here":
    print("ERROR: Set your SAM_API_KEY in .env first")
    exit(1)

resp = requests.get(
    "https://api.sam.gov/opportunities/v2/search",
    params={
        "api_key": api_key,
        "postedFrom": "01/01/2025",
        "postedTo": "01/31/2025",
        "limit": 1,
    },
)
print(f"Status: {resp.status_code}")
if resp.status_code == 200:
    data = resp.json()
    print(f"Total opportunities found: {data.get('totalRecords', 'unknown')}")
    print("SAM.gov API key is working!")
else:
    print(f"Error: {resp.text[:200]}")
```

> **Warning**: Each test call counts against your daily limit (10/day without a role). Only run this once to verify.

---

## Step 6: Verify Reference Data Files

The CSV files needed for reference table loading are already in place. All 10 confirmed present:

| File | Location | Status |
|------|----------|--------|
| NAICS 2022 codes | `workdir/converted/local database/data_to_import/2-6 digit_2022_Codes.csv` | Present |
| NAICS 2017 codes | `workdir/converted/local database/data_to_import/6-digit_2017_Codes.csv` | Present |
| SBA size standards | `workdir/converted/local database/data_to_import/naics_size_standards.csv` | Present |
| NAICS footnotes | `workdir/converted/local database/data_to_import/footnotes.csv` | Present |
| Set-aside types | `workdir/converted/local database/data_to_import/set_aside_types.csv` | Present |
| PSC codes | `workdir/converted/local database/PSC April 2022 - PSC for 042022.csv` | Present |
| Country codes | `workdir/converted/country_codes_combined.csv` | Present |
| SAM.gov countries | `workdir/converted/GG-Updated-Country-and-State-Lists - Countries.csv` | Present |
| State codes | `workdir/converted/GG-Updated-Country-and-State-Lists - States.csv` | Present |
| FIPS county codes | `workdir/converted/local database/FIPS COUNTY CODES.csv` | Present |
| Business types | `OLD_RESOURCES/BusTypes.csv` | Present |

No action needed.

---

## What's Next

**Phase 1 is COMPLETE** (2026-02-22). The system is now self-service:

```bash
cd fed_prospector
source .venv/Scripts/activate        # Git Bash
# or: .venv\Scripts\activate.bat     # CMD

python main.py build-database        # Create/rebuild all 39 tables + 2 views
python main.py load-lookups          # Load all 11 reference tables from CSVs
python main.py status                # Show table counts, API status, recent loads
python main.py check-api             # Test SAM.gov API key (uses 1 call)
python main.py build-database --drop-first  # Nuclear option: drop and rebuild everything
```

**Phase 2** (Entity Data Pipeline) is COMPLETE. 865,232 entities loaded. Run the pipeline:

```bash
# Phase 2 commands:
python main.py seed-quality-rules       # Seed 10 data quality rules into DB
python main.py download-extract --type=monthly --year=2026 --month=2  # Download monthly extract (1 API call)

# Load from DAT file (V2 pipe-delimited, preferred - uses LOAD DATA INFILE, ~4.5 min for 865K entities):
python main.py load-entities --mode=full --file=data/downloads/SAM_PUBLIC_MONTHLY_V2_20260215.dat

# Load from JSON file (streaming parser, slower):
python main.py load-entities --mode=full --file=data/downloads/entities.json

# Daily incremental:
python main.py download-extract --type=daily --date=2026-02-21  # Download daily extract
python main.py load-entities --mode=daily --file=data/downloads/daily.json    # Load daily incremental
```

> **Note**: LOAD DATA INFILE requires MySQL to be started with `--secure-file-priv=""` and the `fed_app` user to have FILE privilege (`GRANT FILE ON *.* TO 'fed_app'@'localhost';`). Both are already configured in Steps 1b and 1c above.

See [05-PHASE2-ENTITY-PIPELINE.md](05-PHASE2-ENTITY-PIPELINE.md) for full details.

**Phase 3** (Opportunities Pipeline) is COMPLETE. 12,209 opportunities loaded (2-year historical), auto-polling via Phase 6. Run the pipeline:

```bash
# Phase 3 commands:
python main.py load-opportunities                          # Load WOSB/8(a) opps (last 7 days, 5 calls max)
python main.py load-opportunities --set-aside=WOSB --days-back=30  # Specific set-aside
python main.py load-opportunities --historical --max-calls=10      # 2-year historical (needs 1K/day limit)
python main.py search --open-only --days=30                # Search local DB for open opportunities
python main.py search --set-aside=WOSB --naics=541511      # Filtered search
```

See [06-PHASE3-OPPORTUNITIES-PIPELINE.md](06-PHASE3-OPPORTUNITIES-PIPELINE.md) for full details.

**Phase 4** (Sales/Prospecting Pipeline) is COMPLETE. 12 CLI commands for prospect management:

```bash
# Phase 4: Prospect Management
python main.py add-user --username jdoe --name "Jane Doe" --email jane@example.com
python main.py list-users
python main.py create-prospect --notice-id ABC123 --assign-to jdoe --priority HIGH
python main.py update-prospect --id 1 --status REVIEWING --user jdoe --notes "Looks good"
python main.py list-prospects --open-only
python main.py show-prospect --id 1
python main.py save-search --name "WOSB IT" --user jdoe --set-asides WOSB,EDWOSB --open-only
python main.py run-search --name "WOSB IT"
python main.py dashboard
```

See [07-PHASE4-SALES-PROSPECTING.md](07-PHASE4-SALES-PROSPECTING.md) for full details.

**Phase 5** (Extended Data Sources) is COMPLETE. All iterations (5A-5E, 5G) done, 5F deprecated:

```bash
# Phase 5: Extended Data Sources
python main.py load-calc                    # Load ~52K GSA labor rates (no API key needed)
python main.py load-awards --naics=541511 --key=2   # Load contract awards from SAM.gov API
python main.py load-hierarchy --key=2       # Load federal org hierarchy from SAM.gov
python main.py search-agencies --name="Army"  # Search federal organizations
python main.py load-exclusions --key=2      # Load exclusion records from SAM.gov
python main.py check-exclusion --uei=ABC123 --key=2   # Check entity for exclusions
python main.py check-prospects              # Check prospect team members against exclusions
python main.py load-transactions --award-id CONT_AWD_...  # Load transaction history for an award
python main.py burn-rate --award-id CONT_AWD_...          # Calculate spend velocity for an award
python main.py load-subawards --naics=541511 --key=2   # Load subaward data from SAM.gov
python main.py search-subawards --prime-uei=ABC123     # Search local subaward data
python main.py teaming-partners --naics=541511         # Find teaming partners from subawards
```

**Phase 6** (Automation and Monitoring) is COMPLETE. Job scheduler, health checks, and DB maintenance:

```bash
# Phase 6: Automation & Health
python main.py check-health             # Comprehensive health check (freshness, API, alerts)
python main.py check-health --json      # Machine-readable JSON output
python main.py run-job opportunities    # Manually trigger any scheduled job
python main.py run-job --list           # List all jobs with last-run status
python main.py maintain-db              # Run database maintenance (cleanup old history)
python main.py maintain-db --dry-run    # Preview what would be cleaned up
python main.py maintain-db --analyze    # Run ANALYZE TABLE on all tables
python main.py maintain-db --sizes      # Show table sizes (data + index)
python main.py run-all-searches         # Execute all active saved searches
```

See [09-PHASE6-AUTOMATION.md](09-PHASE6-AUTOMATION.md) for Windows Task Scheduler setup.

**Phase 7** (Reference Data Enrichment) is COMPLETE. 11 reference tables with enriched metadata:

```bash
python main.py load-lookups                 # Reload all 11 enriched reference tables
python main.py load-lookups --table=sba_type  # Load a specific reference table
python main.py status                       # Show updated row counts for all tables
```

> **Note**: CLI has 38 commands across 11 modules in `cli/`. Run `python main.py --help` for the full list.

See [08-PHASE5-EXTENDED-SOURCES.md](08-PHASE5-EXTENDED-SOURCES.md) for full details.

---

## Phases 8-13: Web API & Frontend (PLANNING)

Phases 1-7 (Python CLI + MySQL ETL pipeline) are complete. Phases 8-13 build a **C# ASP.NET Core Web API** and a **frontend UI** on top of the existing `fed_contracts` database, turning the CLI-based system into a full web application.

| Phase | Name | Summary | Plan Document |
|-------|------|---------|---------------|
| 8 | Web/API Readiness | Gap analysis identifying what the existing schema needs before web consumption | [13-PHASE8-WEB-API-READINESS.md](13-PHASE8-WEB-API-READINESS.md) |
| 9 | Schema Evolution | 14 new tables (8 production + 6 staging) + column additions (39 to 53 tables) for user auth, notifications, capture management, and API response preservation | [14-PHASE9-SCHEMA-EVOLUTION.md](14-PHASE9-SCHEMA-EVOLUTION.md) |
| 10 | API Foundation | ASP.NET Core 8+ project scaffolding, Entity Framework Core, JWT authentication | [15-PHASE10-API-FOUNDATION.md](15-PHASE10-API-FOUNDATION.md) |
| 11 | Read Endpoints | 11 GET endpoints for opportunities, awards, entities, and dashboard views | [16-PHASE11-READ-ENDPOINTS.md](16-PHASE11-READ-ENDPOINTS.md) |
| 12 | Capture Management API | 10 CRUD endpoints for prospects, proposals, notes, and workflow | [17-PHASE12-CAPTURE-MANAGEMENT-API.md](17-PHASE12-CAPTURE-MANAGEMENT-API.md) |
| 13 | Auth & Production | Authentication hardening, notifications, rate limiting, Docker deployment | [18-PHASE13-AUTH-AND-PRODUCTION.md](18-PHASE13-AUTH-AND-PRODUCTION.md) |

The `api/` folder contains the C# ASP.NET Core Web API project. The `ui/` folder will contain the frontend application (framework TBD).

---

## Troubleshooting

### MySQL won't start
- Make sure no other instance is already running: `netstat -an | findstr 3306`
- Check `D:\mysql\data\rack7.err` for error details
- If data directory is corrupted, reinitialize: `D:\mysql\bin\mysqld.exe --initialize-insecure --basedir=D:\mysql --datadir=D:\mysql\data` (this wipes existing data)

### "mysql" command not found
- MySQL is not on your PATH. Use the full path: `D:\mysql\bin\mysql.exe`
- Or add `D:\mysql\bin` to your system PATH

### Python can't find mysql-connector-python
- Make sure your virtual environment is activated (you should see `(.venv)` in your prompt)
- Run `python -m pip install mysql-connector-python` inside the activated venv

### SAM.gov API returns 403
- API key may be expired (90-day cycle). Log into sam.gov and regenerate
- Check that you're passing the key as `api_key` query parameter, not a header

### "Access denied" connecting to MySQL
- Verify the `fed_app` user was created: `D:\mysql\bin\mysql.exe -u root -p<your_root_password> -e "SELECT USER, HOST FROM mysql.user;"`
- Verify grants: `D:\mysql\bin\mysql.exe -u root -p<your_root_password> -e "SHOW GRANTS FOR 'fed_app'@'localhost';"`
- Make sure the password in `.env` matches `credentials.yml`
