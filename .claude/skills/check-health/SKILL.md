---
name: check-health
description: "Run a development environment health check or diagnose operational issues. Use for env setup verification, build/connection problems, failed loads, stale data, schema drift, or ETL errors. Trigger when the user asks 'is MySQL running', 'why won't it build', 'is my environment broken', 'why did the load fail', 'is my data stale', 'check schema drift', 'what loads ran today', 'catch up missed loads', or any variation. Usage: /check-health [full|quick|loads|freshness|schema|catchup]"
argument-hint: "[full|quick|loads|freshness|schema|catchup]"
disable-model-invocation: true
---

# Environment Health Check

**First**: Read `fed_prospector/.env` to get the `DB_PASSWORD` value. MySQL user is `fed_app`, database is `fed_contracts`. `mysql` is on PATH — no need to use a full path.

Verify all development dependencies are working. Default mode is `quick`.

## Quick Check

Run these in parallel:

1. **MySQL**: `mysql -u fed_app -p"$DB_PASSWORD" -e "SELECT 1" fed_contracts`
2. **Python**: Check venv exists at `fed_prospector/.venv/` and run `python --version`
3. **C# SDK**: `dotnet --version`
4. **Git**: `git status`

## Full Check

All quick checks, plus:

5. **C# build**: `dotnet build api/FedProspector.slnx`
6. **Python imports**: `fed_prospector/.venv/Scripts/python.exe -c "import fed_prospector"`
7. **MySQL table count**: `mysql -u fed_app -p"$DB_PASSWORD" -e "SELECT COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema='fed_contracts'" fed_contracts`
8. **.env file**: Check `fed_prospector/.env` exists

## Output Format

Present a checklist:
```
[PASS] MySQL connectivity
[PASS] Python 3.14.3
[FAIL] C# build - error details...
```

## Common Fixes

| Problem | Fix |
|---------|-----|
| MySQL not running | `E:/mysql/bin/mysqld.exe --basedir=E:/mysql --datadir=E:/mysql/data --console --secure-file-priv=""` |
| Python packages missing | Activate venv, then `pip install -r requirements.txt` |
| C# build fails | `dotnet restore api/FedProspector.slnx` |
| .env missing | Copy from `thesolution/credentials.example.yml` template |

## Operational Diagnostics

Use these when the argument is `loads`, `freshness`, `schema`, or `catchup`.

### Load History (`loads`)
```bash
python fed_prospector/main.py health load-history
```
Options: `--source SAM_OPPORTUNITY`, `--days 7`, `--status FAILED`, `--limit 20`

### Data Freshness (`freshness`)
```bash
python fed_prospector/main.py health check
```
Shows freshness per source with alerts (OK/WARN/STALE/NEVER). Add `--json` for machine-readable output.

### Schema Drift (`schema`)
```bash
python fed_prospector/main.py health check-schema
```
Options: `--table <name>` (single table), `--verbose` (show all checked), `--fix` (generate ALTER statements)

### Catchup Missed Loads (`catchup`)
```bash
python fed_prospector/main.py health catchup --dry-run
```
Shows what would run. Remove `--dry-run` to execute. Add `--include-all` for unsafe/long-running jobs.

### Run Individual Job
```bash
python fed_prospector/main.py health run-job --list     # see available jobs
python fed_prospector/main.py health run-job <job_name> # run one
```

## Common Error Patterns

| Pattern | Fix |
|---------|-----|
| Rate limit exceeded | Wait 24h or use `--key 2` (1000/day tier) |
| Connection timeout | Check MySQL is running (`/dev-stack status`) |
| Load stuck in RUNNING | Likely crashed mid-load — re-run the loader |
| Schema drift after DDL change | `health check-schema --fix`, apply the ALTER output |
| Stale data alerts | `health catchup` to recover missed loads |
| SAM.gov API quirks | See `thesolution/reference/09-SAM-API-QUIRKS.md` |
| Data quality issues | See `thesolution/reference/08-DATA-QUALITY-ISSUES.md` |
