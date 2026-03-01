# Phase 10: C# API Foundation

**Status**: PLANNING
**Dependencies**: Phase 9 (Schema Evolution) complete
**Deliverable**: ASP.NET Core Web API project with MySQL connectivity, auth middleware, Swagger docs, and base architecture
**Repository**: `api/` (monorepo -- same repo as Python ETL)

---

## Overview

Set up the foundational C# ASP.NET Core Web API project that will serve as the backend for the capture management web application. This phase focuses on project scaffolding, database connectivity, authentication infrastructure, and architectural patterns -- no business endpoints yet.

---

## Tasks

### 10.1 Project Structure
- [ ] Create ASP.NET Core Web API project (.NET 10)
- [ ] Solution structure:

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
├── Dockerfile
└── README.md
```

- [ ] Create three class library projects: `FedProspector.Api`, `FedProspector.Core`, `FedProspector.Infrastructure`
- [ ] Set up project references: Api -> Core + Infrastructure; Infrastructure -> Core
- [ ] Add `.gitignore` for .NET, `.editorconfig` for code style

### 10.2 MySQL Database Connection
- [ ] Install NuGet packages:
  - `Pomelo.EntityFrameworkCore.MySql` (EF Core MySQL provider)
  - `MySqlConnector` (underlying ADO.NET driver)
- [ ] Configure connection string in `appsettings.json`:

```json
{
  "ConnectionStrings": {
    "FedProspectorDb": "Server=localhost;Port=3306;Database=fed_contracts;User=fed_app;Password=<from-env>;SslMode=None"
  }
}
```

- [ ] Create `FedProspectorDbContext` with DbSet for each of the 45 tables
- [ ] Map entity models to existing MySQL tables (table names, column names, data types)
- [ ] Handle the existing table naming convention (snake_case MySQL -> PascalCase C#)
  > **Snake-case mapping**: Use `UseSnakeCaseNamingConvention()` from the `EFCore.NamingConventions` package to automatically map C# PascalCase properties to MySQL snake_case columns and tables. No manual mapping needed.
- [ ] Configure read-only entities for ETL-managed tables (entity, opportunity, fpds_contract, etc.)
- [ ] Register DbContext in DI container with Pomelo provider and `ServerVersion.AutoDetect`

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
- [ ] JWT Bearer token authentication
- [ ] Token generation on login (symmetric key from appsettings, 24h expiry)
- [ ] Password hashing with BCrypt (`BCrypt.Net-Next` NuGet)
- [ ] Auth middleware validates JWT on all protected endpoints
- [ ] Role-based authorization: `[Authorize]` attribute, roles: `user`, `admin`
- [ ] Account lockout after 5 failed attempts (30 min lockout)
- [ ] Session tracking in `app_session` table

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
- [ ] Install `Swashbuckle.AspNetCore`
- [ ] Configure Swagger UI at `/swagger`
- [ ] Add XML documentation comments on all controllers/DTOs
- [ ] JWT bearer auth in Swagger UI (authorize button)
- [ ] Group endpoints by controller/tag (Opportunities, Awards, Entities, Prospects, Proposals, Auth, Admin)

### 10.5 Base Architecture Patterns

#### Repository Pattern
- [ ] `IRepository<T>` generic interface (GetById, GetAll, Add, Update, Delete)
- [ ] `IReadOnlyRepository<T>` for ETL-managed tables (no write methods)
- [ ] Base implementations using EF Core DbContext

#### Pagination Model
- [ ] Standard `PagedRequest` DTO: `page` (default 1), `pageSize` (default 25, max 100), `sortBy`, `sortDirection`
- [ ] Standard `PagedResponse<T>` DTO: `items[]`, `totalCount`, `page`, `pageSize`, `totalPages`
- [ ] Extension method on `IQueryable<T>` for pagination

#### DTOs
- [ ] Separate request/response DTOs (never expose entity models directly)
- [ ] AutoMapper for entity -> DTO mapping
- [ ] Standard error response: `{ "error": "message", "code": "ERROR_CODE", "details": {} }`

#### Base Controller
- [ ] `ApiControllerBase` with common helper methods
- [ ] Standard HTTP responses: `Ok()`, `Created()`, `NotFound()`, `BadRequest()`, `Unauthorized()`
- [ ] Current user extraction from JWT claims

### 10.6 Cross-Cutting Concerns

#### Logging
- [ ] Serilog with structured logging (`Serilog.AspNetCore` NuGet)
- [ ] Log to console + file (rolling daily)
- [ ] Request/response logging middleware (exclude sensitive data)

#### CORS
- [ ] Configure CORS for frontend origin (configurable per environment)
- [ ] Allow common methods (GET, POST, PATCH, DELETE)
- [ ] Allow Authorization header

#### Error Handling
- [ ] Global exception handler middleware
- [ ] Map exceptions to standard error response DTOs
- [ ] Log unhandled exceptions with full stack trace
- [ ] Return 500 with generic message in production (no stack trace leak)

#### Health Check
- [ ] `/health` endpoint (ASP.NET Core built-in health checks)
- [ ] Check MySQL connectivity
- [ ] Check ETL data freshness (last load time from `etl_load_log`)

### 10.7 Configuration
- [ ] `appsettings.json` -- default config
- [ ] `appsettings.Development.json` -- local dev overrides
- [ ] Environment variables for secrets (connection string password, JWT key)
- [ ] Strongly-typed options pattern (`JwtOptions`, `DatabaseOptions`)

### 10.8 Validation
- [ ] Install `FluentValidation` and `FluentValidation.DependencyInjectionExtensions`
- [ ] Create base validator classes for common patterns (pagination, IDs, date ranges)
- [ ] Register validators in DI via assembly scanning
- [ ] Validation errors return 400 with standard error response format

---

## Acceptance Criteria

1. [ ] `dotnet build` compiles without errors
2. [ ] `dotnet run` starts the API on localhost:5000 (or configured port)
3. [ ] Swagger UI accessible at `/swagger` with all endpoint groups
4. [ ] MySQL connection established -- `/health` returns OK with DB status
5. [ ] JWT auth works: login returns token, protected endpoints reject without token
6. [ ] All 45 table entity models mapped and queryable via EF Core
7. [ ] Pagination model works on a test endpoint
8. [ ] Serilog logging visible in console and file
9. [ ] CORS allows configured frontend origin

---

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| ORM | Pomelo EF Core for CRUD + raw SQL for complex queries | EF Core for simple CRUD, raw SQL for views and aggregations |
| Auth | JWT Bearer tokens + BCrypt | Stateless, standard, works with any frontend |
| Logging | Serilog | Structured logging, multiple sinks, industry standard |
| Mapping | AutoMapper | Widely used, convention-based, reduces boilerplate |
| Validation | FluentValidation | Cleaner than DataAnnotations for complex rules |
| MySQL Driver | Pomelo.EntityFrameworkCore.MySql | Best-maintained EF Core MySQL provider, uses MySqlConnector underneath |

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
