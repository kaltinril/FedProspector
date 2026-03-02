# Phase 15: UI Foundation & Layout

**Status**: NOT STARTED
**Dependencies**: Phase 10 (API), Phase 13 (Auth), Phase 14 (Testing)
**Deliverable**: React + TypeScript SPA scaffold with auth, routing, layout, API client, and component library
**Repository**: `ui/`

---

## Overview

Scaffold the Vite + React + TypeScript frontend application with MUI (Material UI) component library. Establishes the project structure, auth flow (JWT), API client layer, shared layout (sidebar nav, top bar), and dark/light theme. This phase produces no feature pages — just the shell that all subsequent phases build on.

## Tech Stack

| Layer | Choice | Why |
|-------|--------|-----|
| Build tool | Vite 6 | Fast dev server, instant HMR, simple config |
| Framework | React 19 + TypeScript | Most ecosystem support, strong typing |
| Component library | MUI v6 (Material UI) | Best data grid, enterprise-ready, themeable |
| Routing | React Router v7 | Standard, supports auth guards |
| State management | TanStack Query v5 | Server-state caching, auto-refetch, pagination built-in |
| HTTP client | Axios | Interceptors for JWT, error handling |
| Forms | React Hook Form + Zod | Lightweight validation, TypeScript-native schemas |
| Charts | Recharts | Simple, composable, MUI-compatible |
| Data grid | MUI X Data Grid | Sorting, filtering, pagination, export — enterprise-grade |
| Icons | MUI Icons (Material Symbols) | Consistent with MUI theme |

## Project Structure

```
ui/
├── index.html
├── package.json
├── tsconfig.json
├── vite.config.ts
├── .env.development          # VITE_API_URL=http://localhost:5056
├── .env.production           # VITE_API_URL=/api
├── src/
│   ├── main.tsx              # App entry point
│   ├── App.tsx               # Router + providers
│   ├── api/
│   │   ├── client.ts         # Axios instance + interceptors
│   │   ├── auth.ts           # login, register, logout, profile
│   │   ├── opportunities.ts  # search, detail, targets
│   │   ├── awards.ts         # search, detail, burn-rate
│   │   ├── entities.ts       # search, detail, competitor, exclusion
│   │   ├── subawards.ts      # teaming partners
│   │   ├── prospects.ts      # CRUD, notes, team, scoring
│   │   ├── proposals.ts      # CRUD, milestones, documents
│   │   ├── dashboard.ts      # dashboard aggregate
│   │   ├── savedSearches.ts  # CRUD, run
│   │   ├── notifications.ts  # list, mark read
│   │   └── admin.ts          # ETL status, users
│   ├── auth/
│   │   ├── AuthContext.tsx    # JWT token state, user info
│   │   ├── AuthGuard.tsx     # Route protection (redirect to login)
│   │   ├── AdminGuard.tsx    # Admin-only route protection
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
│   │   │   └── CurrencyDisplay.tsx # Formatted dollar amounts
│   │   └── charts/
│   │       ├── BurnRateChart.tsx   # Line chart for burn rate
│   │       ├── PipelineChart.tsx   # Funnel/bar for prospect stages
│   │       └── SpendChart.tsx      # Monthly spend bar chart
│   ├── hooks/
│   │   ├── useDebounce.ts         # Debounce search inputs
│   │   ├── usePagination.ts       # Page state management
│   │   └── useLocalStorage.ts     # Persist user preferences
│   ├── pages/                     # Built in phases 16-20
│   │   └── login/
│   │       ├── LoginPage.tsx
│   │       └── RegisterPage.tsx
│   ├── types/
│   │   ├── api.ts                 # Mirrors C# DTOs
│   │   ├── auth.ts                # Auth types
│   │   └── common.ts              # PagedResponse, PagedRequest, etc.
│   ├── utils/
│   │   ├── formatters.ts          # Currency, date, NAICS display
│   │   └── constants.ts           # Status enums, set-aside codes, etc.
│   └── theme/
│       └── theme.ts               # MUI theme (dark/light, brand colors)
```

---

## Tasks

### 15.1 Project Scaffolding
- [ ] Create Vite + React + TypeScript project in `ui/`
- [ ] Install dependencies: MUI, React Router, TanStack Query, Axios, React Hook Form, Zod, Recharts
- [ ] Configure `vite.config.ts` with API proxy (dev → localhost:5056)
- [ ] Create `.env.development` and `.env.production`
- [ ] Add `tsconfig.json` with strict mode, path aliases (`@/` → `src/`)
- [ ] Update `.gitignore` with `node_modules/`, `ui/dist/`, `ui/.env.local`

### 15.2 API Client Layer
- [ ] Create Axios instance with base URL from env
- [ ] Add JWT token interceptor (attach Bearer header from localStorage)
- [ ] Add 401 interceptor (redirect to login on expired token)
- [ ] Add 429 interceptor (rate limit toast notification)
- [ ] Create typed API modules matching all 31 endpoints
- [ ] Create TypeScript types mirroring every C# DTO

### 15.3 Authentication
- [ ] Create AuthContext with JWT token management (localStorage)
- [ ] Create login page (email + password form)
- [ ] Create register page
- [ ] Create AuthGuard (redirect unauthenticated users to /login)
- [ ] Create AdminGuard (redirect non-admin users to /dashboard)
- [ ] Wire up login → store token → redirect to dashboard

### 15.4 Layout & Navigation
- [ ] Create AppLayout with collapsible sidebar + top bar + content area
- [ ] Sidebar navigation links (Dashboard, Opportunities, Awards, Entities, Prospects, Proposals, Saved Searches, Admin)
- [ ] Top bar: notification bell (count badge), user avatar menu (profile, logout), theme toggle
- [ ] Breadcrumb component auto-generated from React Router
- [ ] Responsive: sidebar collapses to icons on small screens

### 15.5 Theme & Shared Components
- [ ] Create MUI theme (professional blue/gray palette, dark mode variant)
- [ ] Build shared components: PageHeader, DataTable, SearchFilters, StatusChip, LoadingState, ErrorState, EmptyState
- [ ] Currency formatter, date formatter, NAICS display utilities

### 15.6 Service Manager Integration
- [ ] Update `fed_prospector.py` UI functions: build_ui (npm run build), start_ui (npm run dev), stop_ui, check_ui
- [ ] Verify `fed_prospector.py start all` launches DB + API + UI

---

## Verification
- [ ] `npm run dev` starts on localhost:5173
- [ ] Login page renders, login/register flow works end-to-end against live API
- [ ] Authenticated routes redirect to login when no token
- [ ] Sidebar navigation works, layout renders correctly
- [ ] Theme toggle switches dark/light mode
- [ ] API calls attach JWT token automatically
