# Quick Start Guide

Get your local environment ready for the Federal Contract Prospecting System.

---

## Your Environment (validated 2026-03-01)

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

> **Credentials**: All passwords stored in [credentials.yml](credentials.yml) (not committed to git).

---

## Step 1: MySQL Fresh Install

MySQL 8.4.8 LTS installed from ZIP extract at `D:\mysql\` (standalone, no Windows service).

### Start the Server

Open a terminal (stays open while server runs):

```bash
D:\mysql\bin\mysqld.exe --basedir=D:\mysql --datadir=D:\mysql\data --console --secure-file-priv=""
```

You should see `ready for connections` on port 3306.

### First-Time Setup (already done)

```sql
-- In a second terminal: D:\mysql\bin\mysql.exe -u root --skip-password
ALTER USER 'root'@'localhost' IDENTIFIED BY '<your_root_password>';
CREATE DATABASE fed_contracts CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER 'fed_app'@'localhost' IDENTIFIED BY '<your_app_password>';
GRANT ALL PRIVILEGES ON fed_contracts.* TO 'fed_app'@'localhost';
GRANT FILE ON *.* TO 'fed_app'@'localhost';
FLUSH PRIVILEGES;
```

### (Optional) Register as Windows Service

```bash
# Run as Administrator
D:\mysql\bin\mysqld.exe --install MySQL84 --defaults-file=D:\mysql\my.ini
net start MySQL84
```

---

## Step 2: Python Virtual Environment

```bash
cd fed_prospector
python -m venv .venv
source .venv/Scripts/activate   # Git Bash
# or: .venv\Scripts\activate.bat  # CMD
```

### Create .env File

Create `fed_prospector/.env` with credentials from [credentials.yml](credentials.yml):

```env
DB_HOST=localhost
DB_PORT=3306
DB_NAME=fed_contracts
DB_USER=fed_app
DB_PASSWORD=<your_app_password>
SAM_API_KEY=your_actual_api_key_here
SAM_DAILY_LIMIT=10
DATA_DIR=./data
LOG_LEVEL=INFO
```

---

## Step 3: SAM.gov API Key

1. Go to https://sam.gov, log in
2. Navigate to profile, request a **Public API Key**
3. Save it in [credentials.yml](credentials.yml) under `sam_gov.api_key`

> Default: 10 calls/day. With an entity role: 1,000/day. See below for upgrade steps.

### Upgrading to 1,000 Calls/Day

| Account Type | Daily Limit | Who Can Get It |
|-------------|-------------|----------------|
| Personal (no role) | 10/day | Anyone with a SAM.gov account |
| Personal (with role) | 1,000/day | Registered entities in SAM.gov |
| System account | 10,000/day | Federal government agencies only |

**Steps:**
1. Your business must be registered as an entity in SAM.gov (UEI required)
2. Log in → Account Details → Request Role → "Data Entry" role
3. Or: Have entity admin (Workspace → Entity → Users → Assign Roles) grant you Entity Administrator
4. Wait 1-2 weeks for approval. API key automatically upgrades.
5. Update `.env`: `SAM_DAILY_LIMIT=1000`

> API keys expire every 90 days — set a calendar reminder.

---

## Step 4: Verify Everything

```bash
# Test MySQL connection
D:\mysql\bin\mysql.exe -u fed_app -p<your_app_password> -e "USE fed_contracts; SELECT 'OK';"

# Build database and load reference data
cd fed_prospector
source .venv/Scripts/activate
python main.py setup verify          # Check all prerequisites
python main.py setup build           # Create all tables + views
python main.py setup seed-lookups    # Load reference tables from CSVs
python main.py health status         # Show table counts, API status
python main.py setup test-api        # Test SAM.gov API key (uses 1 call)
```

---

## Step 5: C# API (Phases 10-14)

**Prerequisites**: [.NET 10 SDK](https://dotnet.microsoft.com/download)

```bash
cd api
dotnet restore
dotnet build FedProspector.Api.slnx
dotnet run --project src/FedProspector.Api
```

API starts at `https://localhost:5001`. Swagger UI at `/swagger` (dev only).

Connection string in `api/src/FedProspector.Api/appsettings.Development.json`.

---

## Running Tests

```bash
# Python
cd fed_prospector && source .venv/Scripts/activate
python -m pytest fed_prospector/tests/ -v

# C# (all three test projects)
dotnet test api/tests/FedProspector.Core.Tests/
dotnet test api/tests/FedProspector.Api.Tests/
dotnet test api/tests/FedProspector.Infrastructure.Tests/
```

---

## CLI Overview

54 commands in 7 groups. Run `python main.py --help` for all groups, or `python main.py GROUP --help` for sub-commands.

See individual phase docs in `thesolution/phases/` for command details per phase.

---

## Troubleshooting

### MySQL won't start
- Check for existing instance: `netstat -an | findstr 3306`
- Check error log: `D:\mysql\data\rack7.err`

### "mysql" command not found
- Use full path `D:\mysql\bin\mysql.exe` or add `D:\mysql\bin` to PATH

### SAM.gov API returns 403
- Key may be expired (90-day cycle). Regenerate at sam.gov.

### "Access denied" connecting to MySQL
- Verify user exists: `SHOW GRANTS FOR 'fed_app'@'localhost';`
- Ensure `.env` password matches `credentials.yml`

---

## What's Next

See [MASTER-PLAN.md](MASTER-PLAN.md) for the phase roadmap. Next up: Phase 45 (Opportunity Intelligence).
