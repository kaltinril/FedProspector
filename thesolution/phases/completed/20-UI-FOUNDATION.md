# Phase 20: UI Foundation & Layout

**Status**: COMPLETE
**Dependencies**: Phase 14.5 (Multi-Tenancy & Security)
**Deliverable**: React + TypeScript SPA scaffold with auth, routing, layout, API client, and component library
**Repository**: `ui/`

---

## Overview

Scaffold the Vite + React + TypeScript frontend application with MUI (Material UI) component library. Establishes the project structure, cookie-based auth flow, API client layer, shared layout (sidebar nav, top bar), dark/light theme, and company profile setup wizard. This phase produces the shell that all subsequent phases build on, plus the company profile that enables Phase 30's target search and Phase 45's pWin scoring and opportunity recommendations.

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
| Data grid | MUI X Data Grid (MIT free tier) | Server-side sort, pagination — free tier sufficient. **Note: MIT tier does not support server-side filtering via grid column menus. All filtering done via SearchFilters.tsx bar; grid column filter UI disabled.** |
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
├── .env.development          # No VITE_* vars needed — proxy handles API routing
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
│   │   ├── admin.ts          # ETL status, users, org management
│   │   └── organization.ts   # Org profile, NAICS codes, certifications, company setup
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
│   │   └── useAuth.ts        # Hook: login, logout, isOrgAdmin, user
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
│   │   └── charts/                 # Built in Phases 40/60 when consuming pages are developed
│   │       ├── BurnRateChart.tsx   # Line chart for burn rate (Phase 40)
│   │       ├── PipelineChart.tsx   # Funnel/bar for prospect stages (Phase 60)
│   │       └── SpendChart.tsx      # Monthly spend bar chart (Phase 60)
│   ├── hooks/
│   │   ├── useDebounce.ts         # Debounce search inputs
│   │   ├── usePagination.ts       # Page state management
│   │   └── useLocalStorage.ts     # Persist user preferences
│   ├── pages/                     # Built in phases 30-70
│   │   └── login/                 # Each page gets a subdirectory (LoginPage, RegisterPage, etc.)
│   │       ├── LoginPage.tsx
│   │       └── RegisterPage.tsx
│   │   └── setup/
│   │       └── CompanySetupWizard.tsx
│   ├── types/
│   │   ├── api.ts                 # Mirrors C# DTOs
│   │   ├── auth.ts                # Auth types
│   │   ├── common.ts              # PagedResponse, PagedRequest, etc.
│   │   └── organization.ts       # Company profile, NAICS, certifications
│   ├── utils/
│   │   ├── formatters.ts          # Currency, NAICS display
│   │   ├── dateFormatters.ts      # date-fns helpers: formatDate, formatRelative, formatCountdown
│   │   └── constants.ts           # Status enums, set-aside codes, etc.
│   └── theme/
│       └── theme.ts               # MUI theme (dark/light, brand colors)
```

---

## Tasks

### 20.1 Project Scaffolding
- [x] Create Vite + React + TypeScript project in `ui/`
- [x] Install dependencies: MUI, @emotion/react, @emotion/styled, @mui/x-charts, @mui/x-data-grid, React Router, TanStack Query, @tanstack/react-query-devtools, Axios, React Hook Form, Zod, date-fns, react-error-boundary, notistack, @dnd-kit/core, @dnd-kit/sortable
- [x] Configure `vite.config.ts` with path aliases (`@/` -> `src/`)
- [x] Add `tsconfig.json` with strict mode, path aliases (`@/` -> `src/`)
- [x] Update `.gitignore` with `node_modules/`, `ui/dist/`, `ui/.env.local`
- [x] Configure ESLint (`@typescript-eslint`, `eslint-plugin-jsx-a11y`) and Prettier for consistent code formatting
- [x] Enable `React.StrictMode` in `main.tsx`. Note: StrictMode double-invokes effects in development — this is expected and harmless (TanStack Query deduplicates requests).
- [x] ~~**Important**: Exclude `ui/node_modules/` from OneDrive sync~~ **Resolved**: Project moved to `C:\git\fedProspect` (off OneDrive) to avoid sync issues. No exclusion needed.

### 20.2 API Client Layer
- [x] Create Axios instance with base URL `/api/v1` (relative, works with proxy in dev and reverse proxy in prod)
- [x] Set `withCredentials: true` on all Axios requests (browser sends httpOnly cookie automatically)
- [x] Add CSRF interceptor: read XSRF token from non-httpOnly cookie, attach as `X-XSRF-TOKEN` header
- [x] Add 401 interceptor: attempt silent refresh via `POST /auth/refresh`, redirect to login only if refresh fails
  - Use refresh lock pattern: first 401 triggers refresh, concurrent 401s queue behind shared Promise. Prevents multiple competing refresh calls and infinite redirect loops.
- [x] Add 429 interceptor (rate limit toast notification via notistack)
- [x] Create typed API modules matching all endpoints
- [x] Create TypeScript types mirroring every C# DTO
- [x] Create TanStack Query hooks in `src/queries/` with centralized query key factory
- [x] Configure TanStack Query defaults: `staleTime` (2-5min searches, 30s notifications, 60s dashboard), `retry` (2 queries, 1 mutations, 0 auth), `refetchOnWindowFocus` per query type
- [x] Consider generating TypeScript types from the API's OpenAPI/Swagger spec using `openapi-typescript` to prevent manual DTO drift.

#### DTO Sync Strategy

**Recommended**: Use [`openapi-typescript`](https://github.com/openapi-ts/openapi-typescript) to auto-generate TypeScript types from the API's Swagger/OpenAPI spec (`/swagger/v1/swagger.json`). This prevents type drift between C# DTOs and TypeScript interfaces.

```bash
# Generate types from running API
npx openapi-typescript http://localhost:5056/swagger/v1/swagger.json -o src/api/generated-types.ts

# Or from exported JSON file
npx openapi-typescript ../api/swagger.json -o src/api/generated-types.ts
```

Add as an npm script: `"generate-types": "openapi-typescript http://localhost:5056/swagger/v1/swagger.json -o src/api/generated-types.ts"`

**Alternative for MVP**: Manually maintain TypeScript types mirroring C# DTOs. Acceptable if build pipeline complexity is unwanted, but document the drift risk and plan to automate post-MVP.

### 20.3 Authentication
- [x] Create AuthContext -- check session via `GET /auth/me` on app load
- [x] Auth transport configured in 20.2 (withCredentials, CSRF, 401 interceptor)
- [x] Create login page (email + password form)
- [x] Create register page (invite-only, requires invite token)
- [x] Create AuthGuard -- relies on AuthContext session state, redirects unauthenticated users to /login
- [x] Create AdminGuard -- checks `org_role` claim from session, not a separate API call; redirects non-admin users to /dashboard
- [x] Wire up login -> API sets httpOnly cookie -> AuthContext refreshes session -> redirect to dashboard

### 20.4 Layout & Navigation
- [x] Create AppLayout with collapsible sidebar + top bar + content area
- [x] Sidebar navigation links: Dashboard, Opportunities, Awards, Entities, Prospects, Saved Searches, Organization, Admin
- [x] Top bar: notification bell (count badge), user avatar menu (profile, logout), theme toggle
- [x] Breadcrumb component auto-generated from React Router
- [x] Responsive: sidebar collapses to icons on small screens

### 20.5 Theme & Shared Components
- [x] Create MUI theme (professional blue/gray palette, dark mode variant)
- [x] Build shared components: PageHeader, DataTable, SearchFilters, StatusChip, LoadingState, ErrorState, EmptyState
- [x] Build ErrorBoundary wrapper (react-error-boundary) with branded fallback UI
- [x] Build NotificationProvider (notistack) for global toast notifications
- [x] Currency formatter, NAICS display utilities
- [x] date-fns formatters: formatDate, formatRelative, formatCountdown

### 20.6 Service Manager Integration
- [x] Update `fed_prospector.py` UI functions: build_ui (npm run build), start_ui (npm run dev), stop_ui, check_ui
- [x] Verify `fed_prospector.py start all` launches DB + API + UI

### 20.7 Vite Proxy Configuration
- [x] Configure `vite.config.ts` proxy: `/api` -> `http://localhost:5056`, `/health` -> `http://localhost:5056`
- [x] No `VITE_API_URL` in `.env.development` -- proxy handles it, all requests are same-origin
- [x] Axios base URL set to `/api/v1` (relative path, works with Vite proxy in dev and reverse proxy in prod)

### 20.8 Company Profile Wizard

After first login, org owners/admins are guided through a setup wizard to configure their company profile. This data is required by Phase 30 (target opportunity filtering), Phase 45 (pWin scoring, recommended opportunities, qualification checks), and Phase 50 (Go/No-Go scoring enhancement).

#### Backend Changes Required

**Extend Organization entity** with new columns (EF Core migration):

| Column | Type | Purpose |
|--------|------|---------|
| `legal_name` | VARCHAR(300) | Official business name |
| `dba_name` | VARCHAR(300) | Doing-business-as name (nullable) |
| `uei_sam` | VARCHAR(13) | SAM.gov Unique Entity ID — links to `entity` table for past performance lookup |
| `cage_code` | VARCHAR(5) | CAGE code (nullable) |
| `ein` | VARCHAR(10) | Federal tax ID (nullable, encrypted at rest) |
| `address_line1` | VARCHAR(200) | Business address |
| `address_line2` | VARCHAR(200) | (nullable) |
| `city` | VARCHAR(100) | |
| `state_code` | VARCHAR(2) | |
| `zip_code` | VARCHAR(10) | |
| `country_code` | VARCHAR(3) | Default 'USA' |
| `phone` | VARCHAR(20) | Primary phone (nullable) |
| `website` | VARCHAR(500) | Company website (nullable) |
| `employee_count` | INT | Number of employees (for size standard checks) |
| `annual_revenue` | DECIMAL(15,2) | Annual revenue in USD (for size standard checks) |
| `fiscal_year_end_month` | TINYINT | 1-12, default 12 |
| `entity_structure` | VARCHAR(50) | LLC, Corp, Sole Prop, Partnership, JV, etc. |
| `profile_completed` | CHAR(1) | 'Y'/'N' — wizard completed flag |
| `profile_completed_at` | DATETIME | When wizard was completed |

**New junction table: `organization_naics`**

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INT AUTO_INCREMENT | PK |
| `organization_id` | INT | FK to organization |
| `naics_code` | VARCHAR(11) | NAICS code the company competes under |
| `is_primary` | CHAR(1) | 'Y'/'N' — primary NAICS |
| `size_standard_met` | CHAR(1) | 'Y'/'N' — company meets size standard for this NAICS |
| `created_at` | DATETIME | |

**New junction table: `organization_certification`**

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INT AUTO_INCREMENT | PK |
| `organization_id` | INT | FK to organization |
| `certification_type` | VARCHAR(50) | WOSB, EDWOSB, 8A, SDVOSB, HUBZONE, etc. |
| `certifying_agency` | VARCHAR(100) | SBA, VA, etc. |
| `certification_number` | VARCHAR(100) | (nullable) |
| `expiration_date` | DATE | (nullable) |
| `is_active` | CHAR(1) | 'Y'/'N' |
| `created_at` | DATETIME | |

**New junction table: `organization_past_performance`**

| Column | Type | Purpose |
|--------|------|---------|
| `id` | INT AUTO_INCREMENT | PK |
| `organization_id` | INT | FK to organization |
| `contract_number` | VARCHAR(50) | PIID or contract reference |
| `agency_name` | VARCHAR(200) | Contracting agency |
| `description` | TEXT | Brief description of work performed |
| `naics_code` | VARCHAR(11) | NAICS code for this contract |
| `contract_value` | DECIMAL(15,2) | Total contract value |
| `period_start` | DATE | Performance period start |
| `period_end` | DATE | Performance period end |
| `created_at` | DATETIME | |

**New API Endpoints:**

| Method | Endpoint | Purpose |
|--------|----------|---------|
| GET | `/api/v1/org/profile` | Get full company profile (org + NAICS + certs) |
| PUT | `/api/v1/org/profile` | Update company profile (wizard save) |
| GET | `/api/v1/org/naics` | Get org's NAICS codes |
| PUT | `/api/v1/org/naics` | Set org's NAICS codes (bulk replace) |
| GET | `/api/v1/org/certifications` | Get org's certifications |
| PUT | `/api/v1/org/certifications` | Set org's certifications (bulk replace) |
| GET | `/api/v1/org/past-performance` | Get org's past performance records |
| POST | `/api/v1/org/past-performance` | Add past performance record |
| DELETE | `/api/v1/org/past-performance/{id}` | Remove past performance record |
| GET | `/api/v1/reference/naics` | Search NAICS codes (autocomplete) |
| GET | `/api/v1/reference/naics/{code}` | Get NAICS code details + size standard |
| GET | `/api/v1/reference/certifications` | List valid certification types |

#### Wizard UI Flow

**Route**: `/setup` (redirected to after first login if `profile_completed != 'Y'`)

**Step 1: Company Basics**
- Legal name, DBA name (optional)
- SAM.gov UEI (with "Lookup" button — auto-fills from entity table if UEI exists)
- CAGE code (optional)
- Entity structure (dropdown: LLC, Corp, S-Corp, Sole Prop, Partnership, JV)
- Address (street, city, state, ZIP)
- Phone, website

**Step 2: NAICS Codes & Size Standards**
- Autocomplete search for NAICS codes (searches `ref_naics_code` table)
- Add multiple NAICS codes, mark one as primary
- For each NAICS: display the SBA size standard and ask if company meets it (auto-check if revenue/employee data is entered)
- Show revenue and employee count fields here for size standard validation

**Step 3: Certifications**
- Checklist of common certification types: WOSB, EDWOSB, 8(a), SDVOSB, HUBZone, Small Business, Veteran-Owned
- For each selected: certification number (optional), expiration date (optional)
- "We don't have any certifications yet" option (still allows using the system, just won't match set-aside filters)

**Step 4: Past Performance (Optional)**
- "Add a contract" form: contract number, agency, description, NAICS, value, period
- "Skip for now" option — can be filled in later from Organization settings
- Auto-populate suggestion: if UEI was entered in Step 1, show matching contracts from `fpds_contract` table — "We found these contracts associated with your UEI. Select any that represent your past performance."

**Step 5: Review & Save**
- Summary of all entered data
- "Complete Setup" button — sets `profile_completed = 'Y'`
- After completion, redirect to dashboard

#### Tasks

- [x] Create EF Core migration for Organization entity extensions (new columns)
- [x] Create `organization_naics` table + EF Core entity/mapping
- [x] Create `organization_certification` table + EF Core entity/mapping
- [x] Create `organization_past_performance` table + EF Core entity/mapping
- [x] Add `OrgProfileDto`, `UpdateOrgProfileRequest`, `OrgNaicsDto`, `OrgCertificationDto`, `OrgPastPerformanceDto` DTOs
- [x] Add `NaicsSearchDto` and `NaicsDetailDto` DTOs for reference data endpoints
- [x] Implement `/api/v1/org/profile` GET/PUT endpoints in OrganizationController
- [x] Implement `/api/v1/org/naics` GET/PUT endpoints
- [x] Implement `/api/v1/org/certifications` GET/PUT endpoints
- [x] Implement `/api/v1/org/past-performance` GET/POST/DELETE endpoints
- [x] Implement `/api/v1/reference/naics` search endpoint (autocomplete, searches ref_naics_code)
- [x] Implement `/api/v1/reference/naics/{code}` detail endpoint (includes size standard from ref_sba_size_standard)
- [x] Implement `/api/v1/reference/certifications` list endpoint
- [x] Build CompanySetupWizard UI component (5-step stepper using MUI Stepper)
- [x] Build NAICS autocomplete component (debounced search, chip display for selected codes)
- [x] Build certification checklist component
- [x] Build past performance form + auto-populate from FPDS data
- [x] Add redirect logic: after login, if `profile_completed != 'Y'`, redirect to `/setup`
- [x] Add "Company Profile" link in Organization section of sidebar (for editing later)

---

## Verification
- [x] `npm run dev` starts on localhost:5173
- [x] Login page renders, login/register flow works end-to-end against live API
- [x] httpOnly cookie is set by API on login (not visible to JavaScript, visible in browser DevTools)
- [x] CSRF token is read from non-httpOnly cookie and sent as `X-XSRF-TOKEN` header on mutating requests
- [x] Silent token refresh works: expired access token triggers `POST /auth/refresh`, session continues without redirect
- [x] Authenticated routes redirect to login when session is invalid (AuthContext has no user)
- [x] Sidebar navigation works, layout renders correctly
- [x] Organization link visible to org admins in sidebar
- [x] Theme toggle switches dark/light mode
- [x] API calls use `withCredentials: true` (cookie sent automatically, no Bearer header in JS)
- [x] Org context is loaded from session -- user sees only their organization's data
- [x] Company setup wizard renders after first login for new org owners
- [x] NAICS autocomplete searches and returns results from ref_naics_code
- [x] Certifications can be added with type and optional expiration
- [x] Past performance auto-populates from FPDS data when UEI is entered
- [x] Profile completion flag prevents re-showing wizard on subsequent logins
- [x] Company profile is editable from Organization settings after initial setup
