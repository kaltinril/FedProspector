# Federal Prospector API

C# ASP.NET Core Web API backend for the Federal Contract Prospecting System.

**Status**: Phase 10 (PLANNING)

See [thesolution/15-PHASE10-API-FOUNDATION.md](../thesolution/15-PHASE10-API-FOUNDATION.md) for the implementation plan.

## Architecture

- **Framework**: ASP.NET Core Web API (.NET 8+)
- **Database**: MySQL 8.0+ (shared with Python ETL in `fed_prospector/`)
- **ORM**: Pomelo Entity Framework Core
- **Auth**: JWT Bearer tokens + BCrypt password hashing
- **Docs**: Swagger/OpenAPI at `/swagger`
