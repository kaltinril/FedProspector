# Federal Prospector UI

Frontend web application for the Federal Contract Prospecting System.

**Status**: Not started -- implementation begins in Phase 15.

**Stack**: Vite 6 + React 19 + TypeScript + MUI v6 (Material UI)

## Architecture

- **Backend API**: `../api/` (C# ASP.NET Core)
- **Database**: MySQL 8.0+ (read via API, not direct DB access)
- **State management**: TanStack Query for server state, React context for UI state
- **HTTP client**: Axios with typed request/response wrappers
