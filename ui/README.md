# FedProspect UI

Frontend web application for the Federal Contract Prospecting System.

**Stack**: Vite 6 + React 19 + TypeScript + MUI v6

## Quick Start

```bash
# From project root:
python fed_prospector.py start all    # Starts DB + API + UI

# Or just UI:
cd ui && npm run dev                  # http://localhost:5173
```

## Architecture

- **API proxy**: Vite proxies `/api` to `http://localhost:5056` (C# backend)
- **Auth**: httpOnly cookie-based, CSRF protection, silent refresh
- **State**: TanStack Query v5 for server state, React Context for UI state
- **HTTP**: Axios with typed wrappers in `src/api/`
- **Components**: MUI v6 with dark/light theme support
