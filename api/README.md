# FedProspector API

C# ASP.NET Core Web API (.NET 10) backend for the Federal Contract Prospecting System. JWT cookie auth, MySQL via EF Core (Pomelo), multi-tenant org isolation.

## Prerequisites

- **.NET 10 SDK** installed and on PATH
- **MySQL 8.0+** running locally
- **Database `fed_contracts`** with tables created (run Python `python main.py setup build` from `fed_prospector/` first)

## Solution Structure

```
api/
  FedProspector.slnx              # Solution file
  src/
    FedProspector.Api/             # Web API (controllers, middleware, startup)
    FedProspector.Core/            # Domain models, interfaces, DTOs, validators
    FedProspector.Infrastructure/  # EF Core DbContext, service implementations
  tests/
    FedProspector.Api.Tests/
    FedProspector.Core.Tests/
    FedProspector.Infrastructure.Tests/
```

**Controllers**: Auth, Opportunities, Awards, Subawards, Prospects, SavedSearches, Proposals, Dashboard, Entities, Organization, Admin, Notifications, Reference, Health.

## Configuration

Config loads in this order (later files override earlier ones):

| File | Committed | Purpose |
|------|-----------|---------|
| `appsettings.json` | Yes | Base config with placeholders. Connection string set to `SET_VIA_ENVIRONMENT`. |
| `appsettings.Development.json` | Yes | Dev overrides: CORS origins (`localhost:3000`, `localhost:5173`), debug logging, dev-only JWT secret. |
| `appsettings.Local.json` | **No (gitignored)** | Your real DB password and any local overrides. |

### First-time setup

Copy the example file and set your database password:

```bash
cd api/src/FedProspector.Api
cp appsettings.Local.example.json appsettings.Local.json
```

Edit `appsettings.Local.json` and replace `YOUR_PASSWORD` with your `fed_app` MySQL password:

```json
{
  "ConnectionStrings": {
    "DefaultConnection": "Server=localhost;Port=3306;Database=fed_contracts;User=fed_app;Password=YOUR_PASSWORD;SslMode=None;AllowPublicKeyRetrieval=True"
  }
}
```

### Environment variable overrides

Environment variables override all JSON config (standard ASP.NET Core behavior):

```
Jwt__SecretKey=your-production-secret-min-32-chars
ConnectionStrings__DefaultConnection=Server=...;Password=...
```

## Build and Run

```bash
cd api
dotnet restore
dotnet build FedProspector.slnx
dotnet run --project src/FedProspector.Api
```

- API: **http://localhost:5056**
- Swagger UI: **http://localhost:5056/swagger** (Development environment only)

Or use the service manager from the project root:

```bash
./fed_prospector.bat start api
```

## Running Tests

```bash
cd api
dotnet test FedProspector.slnx
```

Three test projects: **Api.Tests**, **Core.Tests**, **Infrastructure.Tests**.

## Common Issues

### "IDX10703: key length is zero"

JWT `SecretKey` is empty. In Development mode, the dev key from `appsettings.Development.json` is used automatically. In Production mode, you **must** set `Jwt__SecretKey` as an environment variable (minimum 32 characters). A runtime guard at startup will throw if the key is missing or too short in non-Development environments.

### "Access denied" or connection failures

The DB password is **not** in any committed config file. Make sure you have created `appsettings.Local.json` with your real password (see Configuration above).

### Cookie auth not working in browser

Auth cookies have the `Secure` flag in production, requiring HTTPS. In development, the Vite dev server proxies API requests to `localhost:5056`. CORS origins are configured in `appsettings.Development.json`.

### CSRF 400 errors on POST/PUT/DELETE

Mutating requests require the `X-XSRF-TOKEN` header. The UI reads the token value from the `XSRF-TOKEN` cookie that the API sets on login.

### 401 on authenticated endpoints

All endpoints require authentication except `/auth/login`, `/auth/register`, and `/auth/refresh`. Make sure you are sending the `access_token` cookie (set automatically by the browser after login).

## Architecture Notes

- **Auth**: httpOnly cookie-based (access_token, refresh_token, XSRF-TOKEN). Not Bearer header auth despite JWT under the hood.
- **Multi-tenant**: Public data (opportunities, awards, entities) is shared. Capture data (prospects, saved searches, proposals) is isolated per organization.
- **Schema ownership**: EF Core migrations own application tables (app_user, organization, prospect, saved_search, etc.). Python DDL owns ETL/data tables (opportunity, award, entity, etc.). Do not create EF migrations for ETL tables.
- **Rate limiting**: Auth endpoints (login, register) are rate-limited to prevent brute force.
- **Logging**: Serilog to console and rolling file (`logs/fedprospector-{date}.log`).
