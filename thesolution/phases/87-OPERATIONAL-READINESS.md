# Phase 87 — Operational Readiness

## Status: PLANNED

**Priority**: MEDIUM
**Depends on**: Phase 80 (security fixes should come first)

---

## Context

Review identified missing infrastructure for production deployment: no CI/CD for FedProspect, no containerization, no backup strategy, undersized connection pool, no monitoring, and no graceful shutdown.

---

## Items to Address

### CRITICAL

**87-1 — No Backup & Disaster Recovery Strategy**
No documented backup procedures, DR plan, or restore mechanisms. No RTO/RPO defined. Implement:
1. Automated MySQL backups (mysqldump or xtrabackup)
2. Daily full + hourly incremental schedule
3. Monthly restore test procedure
4. Document RTO/RPO targets
5. Store backups on separate drive from data (not E:\mysql)

---

### HIGH

**87-2 — CI/CD Pipeline Does Not Test FedProspect**
Files: `.github/workflows/build-and-test.yaml`, `build-and-release.yml`
Workflows reference "Gum.sln" — not FedProspector. No automated testing on PRs. Create new workflows:
- `python-tests.yml` — run pytest on PR
- `csharp-tests.yml` — run dotnet test on PR
- `ui-build.yml` — run npm build + typecheck on PR

**87-3 — No Docker/Containerization**
No Dockerfile, docker-compose.yml. Inconsistent environments, difficult deployment. Create Dockerfiles for API and UI. Docker-compose for local dev (MySQL + API + UI).

**87-4 — Connection Pool Undersized**
File: `fed_prospector/db/connection.py:57`
`pool_size=5` too small for concurrent ETL loaders + API requests. Increase to 10-20. Make configurable via `DB_POOL_SIZE` env var.

**87-5 — No Monitoring/Alerting Infrastructure**
No centralized health monitoring, alerting, or metrics export. Implement health check dashboard. Export Prometheus metrics from API. Set up alerts for: DB connectivity, disk space, ETL failures, API error rate.

**87-6 — Service Manager Not Environment-Aware**
File: `fed_prospector.py`
Hardcodes local paths, ports. No dev/staging/prod config. Use environment variable for environment type. Externalize all ports, paths, URLs.

---

### MEDIUM

**87-7 — No Request/Response Size Limits**
No MaxContentLength configured in ASP.NET. Potential DoS via large payloads. Configure `FormOptions.MultipartBodyLengthLimit` and Kestrel `MaxRequestBodySize`.

**87-8 — No Graceful Shutdown**
Files: `fed_prospector.py`, `api/Program.cs`
Services killed without draining in-flight requests. Data corruption possible. Implement graceful shutdown with drain period. Add CancellationToken support.

**87-9 — Missing Environment-Specific Config Files**
Only `appsettings.json` and `appsettings.Development.json`. No Staging/Production. Add `appsettings.Staging.json`, `appsettings.Production.json` with appropriate values.

**87-10 — Python Requirements Lacks Hash Pinning**
File: `fed_prospector/requirements.txt`
Versions specified but no hash pinning. Transitive dependencies unpinned. Use `pip-compile` to generate `requirements.lock` with hashes.

---

### LOW

**87-11 — No API Versioning Strategy**
Single API version. No deprecation policy. Implement URL-based versioning (`/api/v1/` prefix already in place — formalize).

**87-12 — Memory Cache Not Distributed**
File: `api/Program.cs:34`
`AddMemoryCache()` not suitable for multi-instance deployment. Use Redis if multi-instance planned. Document single-instance limitation.

---

## Verification Checklist

- [ ] 87-1: Run backup script, restore to test DB, verify data integrity
- [ ] 87-2: Push PR branch, verify all test workflows trigger and pass
- [ ] 87-3: `docker-compose up` starts MySQL + API + UI successfully
- [ ] 87-4: Run 10 concurrent loaders — verify no connection exhaustion
- [ ] 87-5: Health check dashboard accessible, alerts configured
- [ ] 87-6: Service manager reads ports/paths from environment
- [ ] 87-8: Send SIGTERM during active load — verify clean exit
- [ ] 87-9: Staging and Production appsettings files present
- [ ] 87-10: `requirements.lock` generated with hashes
