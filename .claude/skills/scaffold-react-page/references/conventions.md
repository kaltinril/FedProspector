# React UI Conventions

## Tech Stack

| Layer | Choice |
|-------|--------|
| Build | Vite 8 |
| Framework | React 19 + TypeScript |
| Components | MUI v9 (Material UI) |
| Routing | React Router v7 |
| Server State | TanStack Query v5 |
| HTTP | Axios |
| Forms | React Hook Form + Zod |

## Project Structure

```
ui/src/
├── api/           — One module per domain (auth.ts, opportunities.ts)
├── queries/       — TanStack Query hooks per entity + queryKeys.ts
├── auth/          — AuthContext.tsx, AuthGuard.tsx
├── components/
│   ├── layout/    — AppLayout, Sidebar
│   └── shared/    — DataTable, SearchFilters
├── pages/         — Feature/Page.tsx per route
├── types/         — api.ts (mirrors C# DTOs), common.ts
├── utils/         — formatters.ts, dateFormatters.ts
├── theme/         — theme.ts (MUI theme)
```

## Auth Pattern

- httpOnly cookie set by C# API (POST /auth/login)
- Axios withCredentials: true (auto-sends cookie)
- CSRF: read XSRF-TOKEN cookie, send as X-XSRF-TOKEN header
- AuthContext: checks GET /auth/me on app load
- useAuth() hook: { user, isLoading, login, logout, isAdmin }
- AuthGuard: redirects to /login if not authenticated

## API Client Pattern

- Axios instance at api/client.ts with baseURL '/api/v1'
- Request interceptor adds CSRF token
- Response interceptor handles 401 → silent refresh with lock pattern
- All API functions return `.then(r => r.data)` (unwrap Axios response)

## Query Pattern

- Centralized queryKeys in queries/queryKeys.ts
- Keys are arrays: ['entity', 'action', params]
- staleTime varies: 30s (notifications), 60s (dashboard), 5min (searches)
- retry: 2 for most queries

## Component Patterns

- MUI X Data Grid MIT for tables (NO server-side column filtering — use SearchFilters bar)
- SearchFilters bar above data grid for all filtering
- Loading: MUI Skeleton or CircularProgress
- Error: react-error-boundary with fallback UI
- Toast: notistack for success/error notifications
- Dark/light mode via MUI theme toggle
