# Phase 87 — Operational Readiness

## Status: COMPLETE

**Priority**: MEDIUM
**Depends on**: Phase 80 (security fixes should come first)

---

## Context

Review identified missing infrastructure for production deployment: no CI/CD for FedProspect, no backup strategy, undersized connection pool, hardcoded ports, and no request size limits.

After validation against the actual codebase, 6 of 12 original items were skipped as already done, irrelevant, or out of scope for the current deployment model.

---

## Completed Items

### 87-1 — Backup & Disaster Recovery ✅
- Created `fed_prospector/scripts/backup_db.py` — mysqldump + gzip, configurable `--backup-dir` and `--retain-days`
- Created `fed_prospector/scripts/restore_db.py` — restores .sql or .sql.gz with confirmation prompt
- Created `thesolution/reference/backup-and-recovery.md` — DR documentation
- Added `backups/` to .gitignore

### 87-2 — CI/CD Pipeline ✅
- Deleted 5 stale workflow files (from unrelated "Gum" project)
- Created `.github/workflows/ci.yml` with 3 parallel jobs: Python tests, C# build/test, UI build/typecheck
- Uses `.slnx` solution format (not `.sln`)
- Python 3.14 with `allow-prereleases: true`

### 87-4 — Connection Pool Configurable ✅
- Added `DB_POOL_SIZE` env var to `config/settings.py` (default: 10, was hardcoded 5)
- Updated `db/connection.py` to use configured value
- Updated `test_db_pool.py` to match new default

### 87-6 — Service Manager Environment-Aware ✅
- Made ports configurable via env vars: `DB_PORT`, `API_PORT`, `UI_PORT`
- Made `ASPNETCORE_ENVIRONMENT` configurable (was hardcoded to "Development")
- All 17 hardcoded port references replaced with variables

### 87-7 — Request/Response Size Limits ✅
- Added Kestrel `MaxRequestBodySize` = 10MB in Program.cs
- Added `FormOptions.MultipartBodyLengthLimit` = 10MB

### 87-9 — Production Config ✅
- Created `appsettings.Production.json` with Warning-level logging, disabled DetailedErrors
- CORS AllowedOrigins set to null (falls back to localhost; must be overridden for real production)

---

## Skipped Items (with justification)

| Item | Reason |
|------|--------|
| 87-3 Docker/Containerization | Windows-native deployment, no cloud/multi-instance requirement |
| 87-5 Monitoring/Alerting | Already implemented: HealthController, CLI health check, health snapshots |
| 87-8 Graceful Shutdown | MySQL already graceful (mysqladmin shutdown), ASP.NET Core has built-in shutdown, ETL uses transactions |
| 87-10 Requirements Hash Pinning | Local install, versions already pinned, maintenance burden outweighs benefit |
| 87-11 API Versioning | Internal API only, no external consumers, `/api/v1/` prefix already in use |
| 87-12 Distributed Cache | Single-instance deployment, no multi-instance plans |

---

## Verification Checklist

- [x] 87-1: Backup script runs with `--help`, handles mysqldump failures with non-zero exit
- [x] 87-2: CI workflow YAML is valid, targets correct paths and solution files
- [x] 87-4: Pool size reads from `DB_POOL_SIZE` env var, all 11 tests pass
- [x] 87-6: Service manager reads ports from environment, no hardcoded ports remain
- [x] 87-7: API build succeeds with request size limits configured
- [x] 87-9: Production config present with appropriate overrides
