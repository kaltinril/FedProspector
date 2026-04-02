# Federal Contract Prospecting System

## Project Purpose

Python + MySQL system to find WOSB and 8(a) federal contracts to bid on. Replaces prior Salesforce approach.

## Project Organization

| Folder | Purpose |
|--------|---------|
| `fed_prospector/` | **Main Python application** - CLI, API clients, ETL pipeline, DB schema |
| `thesolution/` | Plan documents and implementation roadmap |
| `workdir/` | Data conversion scripts and reference CSV/MD files |
| `api/` | **C# ASP.NET Core Web API** - backend REST API |
| `ui/` | **Frontend web application** - Vite 8 + React 19 + TypeScript + MUI v7 (Phase 70 complete) |
| `OLD_ATTEMPTS/`, `OLD_RESOURCES/` | Archived. Do not modify or reference in new code. |

## Context Management

- **NEVER read large doc/plan files in the main context window.** Delegate to agents.
- **Multi-file edits MUST go to coder agents.** Main context is for orchestration only.
- **Batch doc updates into a single agent call.**
- **Why**: Reading 6+ large markdown files inline causes context compaction.

## Agent Instructions

### When Working on This Project

1. **Read the master plan first**: [thesolution/MASTER-PLAN.md](thesolution/MASTER-PLAN.md)
2. **Update the plan as you work**: Mark tasks done in `thesolution/phases/`. **When adding, completing, or changing phase status, ALWAYS update the phase table in `thesolution/MASTER-PLAN.md` in the same commit.**
3. **Follow the phase order**: Do not skip ahead unless told to.
4. **Record data quality issues**: Document in relevant phase file under "Known Issues".
5. **Never hardcode credentials**: Use `.env` + `python-dotenv`. See `thesolution/credentials.example.yml`.
6. **Prefer bulk extracts over API pagination**: SAM.gov rate limits are harsh.
7. **Test with real data**: `workdir/converted/local database/` has reference CSVs.
8. **Ignore OLD_ATTEMPTS and OLD_RESOURCES**: Relevant data already in `workdir/converted/`.
9. **Keep DDL files and live DB in sync**: When changing SQL schema or view files, always apply changes to the live database in the same step.
10. **Completed phases**: Docs in `thesolution/phases/completed/`. Only read for historical context.
11. **Deferred phases**: Phases 150 (Security Hardening) and 500 (Deferred Items) are intentionally deferred. Do not start without explicit instruction.

### Key Conventions

- **Terminology**: In this project, "Vendor API" = external government data sources (SAM.gov, USASpending.gov, GSA CALC+), called only by Python `load` commands, rate-limited. "App API" = FedProspect's own C# ASP.NET Core backend, consumed by the React UI, queries local DB only.
- **Language**: Python 3.14 for all data gathering, transformation, and loading
- **Database**: MySQL 8.0+ with InnoDB engine, utf8mb4 charset. DB name: `fed_contracts`, user: `fed_app`
- **Config**: `fed_prospector/.env` file with `python-dotenv`, never commit `.env` to git
- **Logging**: Python `logging` module, structured output
- **API Clients**: One class per data source, all inherit from `BaseAPIClient`
- **Vendor API Key Selection**: SAM.gov supports 2 API keys (--key=1 or --key=2 on CLI). Key 2 has 1000/day limit.
- **Change Detection**: SHA-256 record hashing to detect changes between loads
- **Data Quality**: Configurable rules in `etl_data_quality_rule` table, not hardcoded
- **App API**: ASP.NET Core Web API. httpOnly cookie auth, CSRF protection, multi-tenant org isolation.
- **UI**: Vite 8 + React 19 + TypeScript, MUI v7, TanStack Query, Axios (Phase 70 complete)
- **Testing**: Python pytest + C# xUnit (Core, Api, Infrastructure). Run `/run-tests all` or see test paths below.
- **Schema Ownership**: Python DDL owns ETL/data tables. EF Core owns application tables (app_user, prospect, saved_search, organization, etc.). See Phase 10 plan for details.

### Performance & Data Source Decisions

- **Never replace `usaspending_award` queries with `fpds_contract`** for scoring/analytics. `fpds_contract` has only 225K rows vs 28.7M but lacks historical depth. `usaspending_award` is the authoritative source for market competition, vendor history, and award trend analysis. When queries against it are slow, use pre-computed summary tables refreshed during daily load — not table substitution.

### Keeping Skills & Agents Current

When changes affect counts, file paths, or conventions referenced by skills or agents, update those files too:

- **`.claude/skills/`**: Skills embed file paths (`add-endpoint`, `check-health`) and project patterns. When paths change, scan skill SKILL.md files.
- **`.claude/agents/`**: Agents are pattern-based and rarely drift, but review if conventions change significantly.
- **Use `/update-docs`**: After completing work, run to update phase status and conventions in docs.

### Shared Module Dependencies — Check Before Changing

These files are imported by many modules. Changes have wide blast radius — verify downstream consumers still work:

| File | Downstream Impact |
|------|-------------------|
| `db/connection.py` | ALL Python modules |
| `config/settings.py` | 25+ files (API keys, DB creds, URLs) |
| `etl/staging_mixin.py` | 7 loaders (opportunity, awards, exclusions, subaward, usaspending, fedhier, calc) |
| `etl/change_detector.py` | 7 loaders (all using SHA-256 change detection) |
| `etl/load_manager.py` | ALL loaders (load orchestration, etl_load_log) |
| `etl/etl_utils.py` | 8 loaders (date/decimal parsing, hash fetching) |
| `api_clients/base_client.py` | 10 API clients (rate limiting, retries, pagination) |

Individual loaders and `prospect_manager.py` are independent — safe to change in isolation.

### Project File References

| What | Location |
|------|----------|
| Service manager | `fed_prospector.py` / `fed_prospector.bat` — `start\|stop\|restart\|status\|build` `[all\|db\|api\|ui]` |
| Python app + CLI | `fed_prospector/` (`python main.py --help`) |
| Vendor API clients | `fed_prospector/api_clients/` (all inherit `BaseAPIClient`) |
| ETL loaders | `fed_prospector/etl/` |
| C# API | `api/src/FedProspector.Api/Controllers/` |
| C# services | `api/src/FedProspector.Infrastructure/Services/` |
| Tests | `fed_prospector/tests/`, `api/tests/` (Python pytest + C# xUnit) |
| DB schema (DDL) | `fed_prospector/db/schema/` |
| UI application | `ui/` (Phase 70 complete) |
| Master plan | `thesolution/MASTER-PLAN.md` |
| Phase plans | `thesolution/phases/` |
| Tech stack | `thesolution/reference/11-TECH-STACK.md` (all runtime + dependency versions) |
| Reference docs | `thesolution/reference/` (architecture, data quality, API quirks, glossary, vendor API docs) |
| Credentials | `thesolution/credentials.example.yml` |
| Reference CSVs | `workdir/converted/local database/` (NAICS, PSC, SBA, FIPS) |
| Pricing API | `api/src/FedProspector.Api/Controllers/PricingController.cs` (10 endpoints) |
| Pricing service | `api/src/FedProspector.Infrastructure/Services/PricingService.cs` |
| Labor normalizer | `fed_prospector/etl/labor_normalizer.py` (CLI: `normalize labor-categories`) |
| BLS loader | `fed_prospector/etl/bls_loader.py` + `fed_prospector/api_clients/bls_client.py` (CLI: `load bls`) |
| Pricing UI pages | `ui/src/pages/pricing/` (6 pages: heatmap, price-to-win, bid scenario, escalation, IGCE, sub benchmark) |
| Pricing API client | `ui/src/api/pricing.ts` |
| Attachment files | `E:\fedprospector\attachments\` (env var: `ATTACHMENT_DIR`) |
