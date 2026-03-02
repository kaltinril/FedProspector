# Phase 15: UI Foundation & Layout

**Status**: NOT STARTED
**Dependencies**: Phase 14.5 (Multi-Tenancy & Security)
**Deliverable**: React + TypeScript SPA scaffold with auth, routing, layout, API client, and component library
**Repository**: `ui/`

---

## Overview

Scaffold the Vite + React + TypeScript frontend application with MUI (Material UI) component library. Establishes the project structure, cookie-based auth flow, API client layer, shared layout (sidebar nav, top bar), and dark/light theme. This phase produces no feature pages — just the shell that all subsequent phases build on.

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Build tool | Vite 6 | Fast dev server, instant HMR, simple config |
| Framework | React 19 + TypeScript | Most ecosystem support, strong typing |
| Component library | MUI v6 (Material UI) | Best data grid, enterprise-ready, themeable |
| Routing | React Router v7 | Standard, supports auth guards |
| State management | TanStack Query v5 | Server-state caching, auto-refetch, pagination built-in |
| HTTP client | Axios | Interceptors for auth, error handling |
| Forms | React Hook Form + Zod | Lightweight validation, TypeScript-native schemas |
| Charts | @mui/x-charts | Theme-consistent, part of MUI ecosystem, no extra design work |
| Data grid | MUI X Data Grid (MIT free tier) | Server-side sort, filter, pagination — free tier sufficient |
| Icons | MUI Icons (Material Symbols) | Consistent with MUI theme |
| Date library | date-fns | Tree-shakeable, lightweight date formatting and countdowns |
| Error boundary | react-error-boundary | Catches React render crashes, prevents white-screen |
| Toast notifications | notistack | MUI-compatible snackbar stacking |

## Project Structure

```
ui/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── .env.production           # Production-specific overrides (if any)
├── src/
│   ├── main.tsx              # App entry point
│   ├── App.tsx               # Router + providers
│   ├── routes.tsx            # Centralized route definitions
│   ├── api/
│   │   ├── client.ts         # Axios instance + interceptors (withCredentials, CSRF, refresh)
│   │   ├── auth.ts           # login, register, logout, me, refresh
│   │   ├── opportunities.ts  # search, detail, targets
│   │   ├── awards.ts         # search, detail, burn-rate
│   │   ├── entities.ts       # search, detail, competitor, exclusion
│   │   ├── subawards.ts      # teaming partners
│   │   ├── prospects.ts      # CRUD, notes, team, scoring
│   │   ├── proposals.ts      # CRUD, milestones, documents
│   │   ├── dashboard.ts      # dashboard aggregate
│   │   ├── savedSearches.ts  # CRUD, run
│   │   ├── notifications.ts  # list, mark read
│   │   └── admin.ts          # ETL status, users, org management
│   ├── queries/
│   │   ├── queryKeys.ts        # Cache key factory (all query keys in one place)
│   │   ├── useOpportunities.ts # TanStack Query hooks for opportunities
│   │   ├── useAwards.ts
│   │   ├── useEntities.ts
│   │   ├── useProspects.ts
│   │   ├── useProposals.ts
│   │   ├── useDashboard.ts
│   │   ├── useSavedSearches.ts
│   │   ├── useNotifications.ts
│   │   └── useAdmin.ts
│   ├── auth/
│   │   ├── AuthContext.tsx    # Session state via GET /auth/me, user info
│   │   ├── AuthGuard.tsx     # Route protection — relies on AuthContext session state
│   │   ├── AdminGuard.tsx    # Admin-only — checks org_role claim from session, not a separate API call
│   │   └── useAuth.ts        # Hook: login, logout, isAdmin, user
│   ├── components/
│   │   ├── layout/
│   │   │   ├── AppLayout.tsx       # Sidebar + top bar + content area
│   │   │   ├── Sidebar.tsx         # Nav links, collapse toggle
│   │   │   ├── TopBar.tsx          # Breadcrumb, notifications bell, user menu
│   │   │   └── Breadcrumb.tsx      # Auto breadcrumbs from route
│   │   ├── shared/
│   │   │   ├── PageHeader.tsx      # Title + action buttons
│   │   │   ├── SearchFilters.tsx   # Reusable filter bar (chips, selects, date pickers)
│   │   │   ├── DataTable.tsx       # Thin wrapper around MUI X Data Grid
│   │   │   ├── StatusChip.tsx      # Color-coded status badges
│   │   │   ├── LoadingState.tsx    # Skeleton / spinner
│   │   │   ├── ErrorState.tsx      # Error display with retry
│   │   │   ├── EmptyState.tsx      # "No results" with illustration
│   │   │   ├── ConfirmDialog.tsx   # Reusable confirmation modal
│   │   │   ├── CurrencyDisplay.tsx # Formatted dollar amounts
│   │   │   ├── ErrorBoundary.tsx   # react-error-boundary wrapper with fallback UI
│   │   │   └── NotificationProvider.tsx # notistack provider for global toast notifications
│   │   └── charts/
│   │       ├── BurnRateChart.tsx   # Line chart for burn rate
│   │       ├── PipelineChart.tsx   # Funnel/bar for prospect stages
│   │       └── SpendChart.tsx      # Monthly spend bar chart
│   ├── hooks/
│   │   ├── useDebounce.ts         # Debounce search inputs
│   │   ├── usePagination.ts       # Page state management
│   │   └── useLocalStorage.ts     # Persist user preferences
│   ├── pages/                     # Built in phases 16-20
│   │   └── login/                 # Each page gets a subdirectory (LoginPage, RegisterPage, etc.)
│   │       ├── LoginPage.tsx
│   │       └── RegisterPage.tsx
│   ├── types/
│   │   ├── api.ts                 # Mirrors C# DTOs
│   │   ├── auth.ts                # Auth types
│   │   └── common.ts              # PagedResponse, PagedRequest, etc.
│   ├── utils/
│   │   ├── formatters.ts          # Currency, NAICS display
│   │   ├── dateFormatters.ts      # date-fns helpers: formatDate, formatRelative, formatCountdown
│   │   └── constants.ts           # Status enums, set-aside codes, etc.
│   └── theme/
│       └── theme.ts               # MUI theme (dark/light, brand colors)
```

---

## Tasks

### 15.1 Project Scaffolding
- [ ] Create Vite + React + TypeScript project in `ui/`
- [ ] Install dependencies: MUI, @mui/x-charts, @mui/x-data-grid, React Router, TanStack Query, Axios, React Hook Form, Zod, date-fns, react-error-boundary, notistack
- [ ] Configure `vite.config.ts` with path aliases (`@/` -> `src/`)
- [ ] Add `tsconfig.json` with strict mode, path aliases (`@/` -> `src/`)
- [ ] Update `.gitignore` with `node_modules/`, `ui/dist/`, `ui/.env.local`

### 15.2 API Client Layer
- [ ] Create Axios instance with base URL `/api/v1` (relative, works with proxy in dev and reverse proxy in prod)
- [ ] Set `withCredentials: true` on all Axios requests (browser sends httpOnly cookie automatically)
- [ ] Add CSRF interceptor: read XSRF token from non-httpOnly cookie, attach as `X-XSRF-TOKEN` header
- [ ] Add 401 interceptor: attempt silent refresh via `POST /auth/refresh`, redirect to login only if refresh fails
- [ ] Add 429 interceptor (rate limit toast notification via notistack)
- [ ] Create typed API modules matching all endpoints
- [ ] Create TypeScript types mirroring every C# DTO
- [ ] Create TanStack Query hooks in `src/queries/` with centralized query key factory

### 15.3 Authentication
- [ ] Create AuthContext -- check session via `GET /auth/me` on app load
- [ ] Axios: `withCredentials: true` on all requests (browser sends cookie automatically)
- [ ] CSRF: Read XSRF token from non-httpOnly cookie, attach as `X-XSRF-TOKEN` header
- [ ] 401 interceptor: attempt silent refresh via `POST /auth/refresh`, redirect to login only if refresh fails
- [ ] Create login page (email + password form)
- [ ] Create register page (invite-only, requires invite token)
- [ ] Create AuthGuard -- relies on AuthContext session state, redirects unauthenticated users to /login
- [ ] Create AdminGuard -- checks `org_role` claim from session, not a separate API call; redirects non-admin users to /dashboard
- [ ] Wire up login -> API sets httpOnly cookie -> AuthContext refreshes session -> redirect to dashboard

### 15.4 Layout & Navigation
- [ ] Create AppLayout with collapsible sidebar + top bar + content area
- [ ] Sidebar navigation links: Dashboard, Opportunities, Awards, Entities, Prospects, Saved Searches, Organization, Admin
- [ ] Top bar: notification bell (count badge), user avatar menu (profile, logout), theme toggle
- [ ] Breadcrumb component auto-generated from React Router
- [ ] Responsive: sidebar collapses to icons on small screens

### 15.5 Theme & Shared Components
- [ ] Create MUI theme (professional blue/gray palette, dark mode variant)
- [ ] Build shared components: PageHeader, DataTable, SearchFilters, StatusChip, LoadingState, ErrorState, EmptyState
- [ ] Build ErrorBoundary wrapper (react-error-boundary) with branded fallback UI
- [ ] Build NotificationProvider (notistack) for global toast notifications
- [ ] Currency formatter, NAICS display utilities
- [ ] date-fns formatters: formatDate, formatRelative, formatCountdown

### 15.6 Service Manager Integration
- [ ] Update `fed_prospector.py` UI functions: build_ui (npm run build), start_ui (npm run dev), stop_ui, check_ui
- [ ] Verify `fed_prospector.py start all` launches DB + API + UI

### 15.7 Vite Proxy Configuration
- [ ] Configure `vite.config.ts` proxy: `/api` -> `http://localhost:5056`, `/health` -> `http://localhost:5056`
- [ ] No `VITE_API_URL` in `.env.development` -- proxy handles it, all requests are same-origin
- [ ] Axios base URL set to `/api/v1` (relative path, works with Vite proxy in dev and reverse proxy in prod)

---

## Verification
- [ ] `npm run dev` starts on localhost:5173
- [ ] Login page renders, login/register flow works end-to-end against live API
- [ ] httpOnly cookie is set by API on login (not visible to JavaScript, visible in browser DevTools)
- [ ] CSRF token is read from non-httpOnly cookie and sent as `X-XSRF-TOKEN` header on mutating requests
- [ ] Silent token refresh works: expired access token triggers `POST /auth/refresh`, session continues without redirect
- [ ] Authenticated routes redirect to login when session is invalid (AuthContext has no user)
- [ ] Sidebar navigation works, layout renders correctly
- [ ] Organization link visible to org admins in sidebar
- [ ] Theme toggle switches dark/light mode
- [ ] API calls use `withCredentials: true` (cookie sent automatically, no Bearer header in JS)
- [ ] Org context is loaded from session -- user sees only their organization's data
