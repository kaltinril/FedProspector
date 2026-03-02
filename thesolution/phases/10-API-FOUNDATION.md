# Phase 10: C# API Foundation

**Status**: COMPLETE (2026-03-01)
**Dependencies**: Phase 9 (Schema Evolution) complete
**Deliverable**: ASP.NET Core Web API project with MySQL connectivity, auth middleware, Swagger docs, and base architecture
**Repository**: `api/` (monorepo -- same repo as Python ETL)

---

## Overview

Set up the foundational C# ASP.NET Core Web API project that will serve as the backend for the capture management web application. This phase focuses on project scaffolding, database connectivity, authentication infrastructure, and architectural patterns -- no business endpoints yet.

---

## Schema Ownership

**Decision**: Schema ownership is split between Python DDL and C# EF Core Migrations. Both systems share the single `fed_contracts` database.

| Owner | Tables | Rationale |
|-------|--------|-----------|
| **Python DDL** (`fed_prospector/db/schema/`) | ~35 tables (see full list below) | ETL pipeline populates these. Python is source of truth. `check-schema` validates drift. |
| **C# EF Core Migrations** | ~5 existing + future app tables (see full list below) | Application/UI tables. C# is source of truth. EF Core migrations manage changes. |

### Python DDL Tables (35)

- **Entity** (10): `entity`, `entity_address`, `entity_business_type`, `entity_disaster_response`, `entity_history`, `entity_naics`, `entity_poc`, `entity_psc`, `entity_sba_certification`, `stg_entity_raw`
- **Opportunity** (3): `opportunity`, `opportunity_history`, `opportunity_relationship`
- **Federal/Awards** (2): `fpds_contract`, `federal_organization`
- **External sources** (5): `gsa_labor_rate`, `sam_exclusion`, `sam_subaward`, `usaspending_award`, `usaspending_transaction`
- **ETL** (4): `etl_load_log`, `etl_load_error`, `etl_data_quality_rule`, `etl_rate_limit`
- **Reference** (11): `ref_business_type`, `ref_country_code`, `ref_entity_structure`, `ref_fips_county`, `ref_naics_code`, `ref_naics_footnote`, `ref_psc_code`, `ref_sba_size_standard`, `ref_sba_type`, `ref_set_aside_type`, `ref_state_code`

### C# EF Core Tables (5 existing)

- `app_user`, `prospect`, `prospect_note`, `prospect_team_member`, `saved_search`
- Future Phase 10+ tables: `app_session`, `proposal`, `proposal_document`, `proposal_milestone`, `activity_log`, `notification`, `contracting_officer`, `opportunity_poc`

### Rules

1. **Python DDL files remain the source of truth for ETL tables.** `build-database` creates them. `check-schema` validates them.
2. **EF Core maps Python's ETL tables as read-only entities** -- no migrations generated for them. Use `[Table("entity")]` attribute mapping but never create/modify these tables via EF Core.
3. **EF Core migrations own the application tables.** A "baseline" migration captures the existing DDL for the 5 app tables, then EF Core manages them going forward.
4. **Python `build-database` will SKIP the 5 app tables** once EF Core takes ownership (add a skip list or move the DDL to a `legacy/` subfolder).
5. **Both systems share the same `fed_contracts` database.** No separate databases.

---

## Tasks

### 10.1 Project Structure
- [x] Create ASP.NET Core Web API project (.NET 10)
- [x] Solution structure:

```
api/
├── FedProspector.Api.sln
├── src/
│   ├── FedProspector.Api/              # Web API host (Program.cs, controllers, middleware)
│   │   ├── Controllers/
│   │   ├── Middleware/
│   │   ├── Filters/
│   │   └── Program.cs
│   ├── FedProspector.Core/             # Domain models, interfaces, business logic
│   │   ├── Models/
│   │   ├── DTOs/
│   │   ├── Interfaces/
│   │   ├── Services/
│   │   └── Enums/
│   └── FedProspector.Infrastructure/   # Data access, external services
│       ├── Data/
│       ├── Repositories/
│       └── Configuration/
├── tests/
│   ├── FedProspector.Api.Tests/
│   └── FedProspector.Core.Tests/
├── appsettings.json
├── appsettings.Development.json
└── README.md
```

- [x] Create three class library projects: `FedProspector.Api`, `FedProspector.Core`, `FedProspector.Infrastructure`
- [x] Set up project references: Api -> Core + Infrastructure; Infrastructure -> Core
- [x] Add `.gitignore` for .NET, `.editorconfig` for code style

### 10.2 MySQL Database Connection
- [x] Install NuGet packages:
  - `Pomelo.EntityFrameworkCore.MySql` (EF Core MySQL provider)
  - `MySqlConnector` (underlying ADO.NET driver)
- [x] Configure connection string in `appsettings.json`:

```json
{
  "ConnectionStrings": {
    "FedProspectorDb": "Server=localhost;Port=3306;Database=fed_contracts;User=fed_app;Password=<from-env>;SslMode=None"
  }
}
```

- [x] Create `FedProspectorDbContext` with DbSet for each of the 48 production tables (54 tables total: 48 production + 6 staging. EF Core models needed for 48 production tables only; staging tables are managed by the Python ETL pipeline.)
- [x] Map entity models to existing MySQL tables (table names, column names, data types)
- [x] Handle the existing table naming convention (snake_case MySQL -> PascalCase C#)
  > **Snake-case mapping**: Use `UseSnakeCaseNamingConvention()` from the `EFCore.NamingConventions` package to automatically map C# PascalCase properties to MySQL snake_case columns and tables. No manual mapping needed.
- [x] Configure read-only entities for ETL-managed tables (entity, opportunity, fpds_contract, etc.)
- [x] Register DbContext in DI container with Pomelo provider and `ServerVersion.AutoDetect`

#### Entity Model Categories

**Read-Only (Python ETL manages these -- C# should NOT write):**
- All 11 `ref_*` tables
- `entity` + 8 child tables + `entity_history`
- `opportunity` + `opportunity_history` (except new manually-entered columns)
- `fpds_contract`
- `gsa_labor_rate`
- `sam_exclusion`
- `sam_subaward`
- `federal_organization`
- `usaspending_award` + `usaspending_transaction`
- All 4 `etl_*` tables

**Read-Write (C# API manages these):**
- `app_user` (auth columns only -- Python created the user rows)
- `app_session`
- `prospect` + `prospect_note` + `prospect_team_member`
- `proposal` + `proposal_document` + `proposal_milestone`
- `saved_search`
- `activity_log`
- `notification`

### 10.3 Authentication & Authorization
- [x] JWT Bearer token authentication
- [x] Token generation on login (symmetric key from appsettings, 24h expiry)
- [x] Password hashing with BCrypt (`BCrypt.Net-Next` NuGet)
- [x] Auth middleware validates JWT on all protected endpoints
- [x] Role-based authorization: `[Authorize]` attribute, roles: `user`, `admin`
- [x] Account lockout after 5 failed attempts (30 min lockout)
- [x] Session tracking in `app_session` table

#### Token Payload

```json
{
  "sub": "user_id",
  "name": "display_name",
  "role": "user|admin",
  "iat": 1234567890,
  "exp": 1234567890
}
```

### 10.4 Swagger / OpenAPI Documentation
- [x] Install `Swashbuckle.AspNetCore`
- [x] Configure Swagger UI at `/swagger`
- [x] Add XML documentation comments on all controllers/DTOs
- [x] JWT bearer auth in Swagger UI (authorize button)
- [x] Group endpoints by controller/tag (Opportunities, Awards, Entities, Prospects, Proposals, Auth, Admin)

### 10.5 Base Architecture Patterns

#### Repository Pattern
- [x] `IRepository<T>` generic interface (GetById, GetAll, Add, Update, Delete)
- [x] `IReadOnlyRepository<T>` for ETL-managed tables (no write methods)
- [x] Base implementations using EF Core DbContext

#### Pagination Model
- [x] Standard `PagedRequest` DTO: `page` (default 1), `pageSize` (default 25, max 100), `sortBy`, `sortDirection`
- [x] Standard `PagedResponse<T>` DTO: `items[]`, `totalCount`, `page`, `pageSize`, `totalPages`
- [x] Extension method on `IQueryable<T>` for pagination

#### DTOs
- [x] Separate request/response DTOs (never expose entity models directly)
- [x] AutoMapper for entity -> DTO mapping
- [x] Standard error response: `{ "error": "message", "code": "ERROR_CODE", "details": {} }`

#### Base Controller
- [x] `ApiControllerBase` with common helper methods
- [x] Standard HTTP responses: `Ok()`, `Created()`, `NotFound()`, `BadRequest()`, `Unauthorized()`
- [x] Current user extraction from JWT claims

### 10.6 Cross-Cutting Concerns

#### Logging
- [x] Serilog with structured logging (`Serilog.AspNetCore` NuGet)
- [x] Log to console + file (rolling daily)
- [x] Request/response logging middleware (exclude sensitive data)

#### CORS
- [x] Configure CORS for frontend origin (configurable per environment)
- [x] Allow common methods (GET, POST, PATCH, DELETE)
- [x] Allow Authorization header

#### Error Handling
- [x] Global exception handler middleware
- [x] Map exceptions to standard error response DTOs
- [x] Log unhandled exceptions with full stack trace
- [x] Return 500 with generic message in production (no stack trace leak)

#### Health Check
- [x] `/health` endpoint (ASP.NET Core built-in health checks)
- [x] Check MySQL connectivity
- [x] Check ETL data freshness (last load time from `etl_load_log`)

### 10.7 Configuration
- [x] `appsettings.json` -- default config
- [x] `appsettings.Development.json` -- local dev overrides
- [x] Environment variables for secrets (connection string password, JWT key)
- [x] Strongly-typed options pattern (`JwtOptions`, `DatabaseOptions`)

### 10.8 Validation
- [x] Install `FluentValidation` and `FluentValidation.DependencyInjectionExtensions`
- [x] Create base validator classes for common patterns (pagination, IDs, date ranges)
- [x] Register validators in DI via assembly scanning
- [x] Validation errors return 400 with standard error response format

---

## Acceptance Criteria

1. [x] `dotnet build` compiles without errors
2. [x] `dotnet run` starts the API on localhost:5000 (or configured port)
3. [x] Swagger UI accessible at `/swagger` with all endpoint groups
4. [x] MySQL connection established -- `/health` returns OK with DB status
5. [x] JWT auth works: login returns token, protected endpoints reject without token
6. [x] All 48 production table entity models mapped and queryable via EF Core (6 staging tables excluded -- Python ETL only)
7. [x] Pagination model works on a test endpoint
8. [x] Serilog logging visible in console and file
9. [x] CORS allows configured frontend origin

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ORM | Pomelo EF Core for CRUD + raw SQL for complex queries | EF Core for simple CRUD, raw SQL for views and aggregations |
| Auth | JWT Bearer tokens + BCrypt | Stateless, standard, works with any frontend |
| Logging | Serilog | Structured logging, multiple sinks, industry standard |
| Mapping | AutoMapper 13+ | Widely used, convention-based, reduces boilerplate (DI extensions built-in) |
| Validation | FluentValidation 12+ (manual wiring, NOT deprecated AspNetCore package) | Cleaner than DataAnnotations for complex rules |
| MySQL Driver | Pomelo.EntityFrameworkCore.MySql | Best-maintained EF Core MySQL provider, uses MySqlConnector underneath |
| Rate Limiting | Built-in `Microsoft.AspNetCore.RateLimiting` | NOT the deprecated AspNetCoreRateLimit package |
| API Versioning | `/api/v1/` prefix on all endpoints | URL-based versioning for simplicity |
| Boolean Convention | `CHAR(1) 'Y'/'N'` in MySQL (not BOOLEAN or ENUM) | Matches existing Python ETL schema convention |
| Target Framework | .NET 10 LTS | Long-term support release |

---

## NuGet Packages Summary

| Package | Purpose |
|---------|---------|
| `Pomelo.EntityFrameworkCore.MySql` | EF Core provider for MySQL |
| `MySqlConnector` | ADO.NET driver (Pomelo dependency) |
| `Swashbuckle.AspNetCore` | Swagger / OpenAPI UI and generation |
| `BCrypt.Net-Next` | Password hashing |
| `Serilog.AspNetCore` | Structured logging |
| `Serilog.Sinks.File` | File logging sink |
| `AutoMapper` (13.0+) | Object mapping (DI extensions built-in) |
| `FluentValidation` (12.x) | Request validation |
| `FluentValidation.DependencyInjectionExtensions` (12.x) | DI registration for validators (requires manual pipeline wiring) |
| `EFCore.NamingConventions` | Snake-case naming convention for EF Core |
| `Microsoft.AspNetCore.Authentication.JwtBearer` | JWT auth middleware |
