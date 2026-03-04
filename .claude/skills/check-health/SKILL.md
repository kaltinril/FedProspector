---
name: check-health
description: "Run a development environment health check: MySQL, Python, C# build, git status. Usage: /check-health [full|quick]"
argument-hint: "[full|quick]"
disable-model-invocation: true
---

# Environment Health Check

Verify all development dependencies are working. Default mode is `quick`.

## Quick Check

Run these in parallel:

1. **MySQL**: `D:/mysql/bin/mysql.exe -u fed_app -pfed_app_2026 -e "SELECT 1" fed_contracts`
2. **Python**: Check venv exists at `c:/git/fedProspect/fed_prospector/.venv/` and run `python --version`
3. **C# SDK**: `dotnet --version`
4. **Git**: `git -C c:/git/fedProspect status`

## Full Check

All quick checks, plus:

5. **C# build**: `dotnet build c:/git/fedProspect/api/FedProspector.slnx`
6. **Python imports**: `c:/git/fedProspect/fed_prospector/.venv/Scripts/python.exe -c "import fed_prospector"`
7. **MySQL table count**: `D:/mysql/bin/mysql.exe -u fed_app -pfed_app_2026 -e "SELECT COUNT(*) AS table_count FROM information_schema.tables WHERE table_schema='fed_contracts'" fed_contracts`
8. **.env file**: Check `c:/git/fedProspect/fed_prospector/.env` exists

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
| MySQL not running | `D:\mysql\bin\mysqld.exe --basedir=D:\mysql --datadir=D:\mysql\data --console --secure-file-priv=""` |
| Python packages missing | Activate venv, then `pip install -r requirements.txt` |
| C# build fails | `dotnet restore c:/git/fedProspect/api/FedProspector.slnx` |
| .env missing | Copy from `thesolution/credentials.yml` template |
