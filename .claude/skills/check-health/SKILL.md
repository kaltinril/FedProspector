---
name: check-health
description: "Run a development environment health check: MySQL, Python, C# build, git status. Use when verifying the dev environment works, diagnosing build or connection issues, or after setup. Usage: /check-health [full|quick]"
argument-hint: "[full|quick]"
disable-model-invocation: true
---

# Environment Health Check

**First**: Read `thesolution/credentials.yml` to get `MYSQL_USER`, `MYSQL_PASSWORD`, and the MySQL install path (`MYSQL_DIR`, default `D:/mysql`). Use these values in all commands below — never hardcode credentials or paths.

Verify all development dependencies are working. Default mode is `quick`.

## Quick Check

Run these in parallel:

1. **MySQL**: `$MYSQL_DIR/bin/mysql.exe -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -e "SELECT 1" fed_contracts`
2. **Python**: Check venv exists at `fed_prospector/.venv/` and run `python --version`
3. **C# SDK**: `dotnet --version`
4. **Git**: `git status`

## Full Check

All quick checks, plus:

5. **C# build**: `dotnet build api/FedProspector.slnx`
6. **Python imports**: `fed_prospector/.venv/Scripts/python.exe -c "import fed_prospector"`
7. **MySQL table count**: `$MYSQL_DIR/bin/mysql.exe -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -e "SELECT COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema='fed_contracts'" fed_contracts`
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
| MySQL not running | `$MYSQL_DIR/bin/mysqld.exe --basedir=$MYSQL_DIR --datadir=$MYSQL_DIR/data --console --secure-file-priv=""` |
| Python packages missing | Activate venv, then `pip install -r requirements.txt` |
| C# build fails | `dotnet restore api/FedProspector.slnx` |
| .env missing | Copy from `thesolution/credentials.yml` template |
