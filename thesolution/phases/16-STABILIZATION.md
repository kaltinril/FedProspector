# Phase 16 — Stabilization

## Status: COMPLETE (2026-03-04)

---

## Context

FedProspect: ~54K lines, 57 tables, 59 endpoints, 54 CLI commands across Python + C#. Before starting UI phases (20-70), we needed better agent context and missing test safety nets. Agents working on this project see the root CLAUDE.md but lacked domain-specific context about dependencies and data quality rules, leading to changes in one area breaking another.

---

## Deliverables

### 16.1 — CLAUDE.md Reference Links + Dependency Map
- [x] Added "Critical Reference Docs" section with links to SAM API quirks, data quality issues, data architecture, vendor API docs, master plan
- [x] Added "Shared Module Dependencies" table showing blast radius of shared modules (connection.py, settings.py, staging_mixin.py, change_detector.py, load_manager.py, etl_utils.py, base_client.py)

### 16.2 — `/validate` Skill
- [x] Created `.claude/skills/validate/SKILL.md`
- [x] Runs all Python + C# tests in forked context, reports pass/fail summary
- [x] `disable-model-invocation: true`, `context: fork`

### 16.3 — C# Service Layer Tests (155 new tests)
13 of 14 services were untested (only GoNoGoScoringService had tests). Created test files in `api/tests/FedProspector.Infrastructure.Tests/Services/`:

| Service | Tests | Notes |
|---------|-------|-------|
| AuthServiceTests | 42 | JWT, password hashing, claims, lockout, session mgmt |
| SavedSearchServiceTests | 29 | CRUD, dynamic filter parsing, soft delete |
| ProposalServiceTests | 18 | Lifecycle state machine, milestones, documents |
| ProspectServiceTests | 14 | CRUD, status transitions, org isolation |
| AwardServiceTests | 10 | Search, filters, vendor profile |
| OpportunityServiceTests | 9 | 4 passing, 5 skipped (EF.Functions.DateDiffDay InMemory limitation) |
| OrganizationServiceTests | 8 | Invite flow, member management |
| EntityServiceTests | 6 | Search, detail, competitor analysis |
| AdminServiceTests | 5 | User management, ETL status |
| NotificationServiceTests | 5 | CRUD, mark-read |
| DashboardServiceTests | 3 | Aggregation queries |
| SubawardServiceTests | 3 | Construction + defaults (raw SQL can't run InMemory) |
| ActivityLogServiceTests | 3 | Logging queries |

### 16.4 — Python Business Logic + CLI Tests (276 new tests)

| Test File | Tests | Coverage |
|-----------|-------|----------|
| test_schema_checker.py | 99 | DDL parsing, type normalization, column/index/FK comparison, drift detection |
| test_prospect_manager.py | 71 | All public methods: user CRUD, prospect CRUD, status flow, notes, team, saved searches, dashboard |
| test_cli_prospect.py | 30 | create, search, detail, status, notes, team, saved-search, dashboard |
| test_cli_health.py | 18 | check-health, show-status with various flags |
| test_cli_load.py | 18 | load-entities, load-opportunities, load-awards arg parsing + loader wiring |
| test_cli_database.py | 13 | build-database, check-schema |
| test_reference_loader.py | 27 (updated) | Updated fixture for specific exception types |

CLI test pattern: patch at source module (not CLI module) due to Click's lazy imports in command bodies.

### 16.5 — Code Quality Fixes

- [x] **22 bare `except Exception:` replaced** with specific types (`OSError`, `ValueError`, `KeyError`, `mysql.connector.Error`) in `reference_loader.py` (12) and `prospect_manager.py` (10)
- [x] **Deadlock retry decorator** created at `fed_prospector/utils/db_retry.py` — catches MySQL error 1213, max 3 retries with linear backoff
- [x] **11 silent error suppressions fixed** in `reference_loader.py` — added `logger.warning()` calls before `continue` statements that previously swallowed errors silently
- [x] **Subaward loader** — documented that composite key fix resolved silent skip issue
- [x] **Autocommit dual-mode documented** in `fed_prospector/db/connection.py` — comprehensive docstring explaining raw connection vs pooled connection autocommit behavior and PooledMySQLConnection patch

---

## Verification

- Python: 1,016 passed
- C# Core: 316 passed
- C# Api: 238 passed
- C# Infrastructure: 176 passed, 5 skipped
- **Total: 1,746 tests (1,741 passed, 5 skipped, 0 failed)**
- CLAUDE.md has reference doc links and shared module dependency map
- 1 remaining `except Exception:` in reference_loader.py line 759 is acceptable (rollback + re-raise pattern)
