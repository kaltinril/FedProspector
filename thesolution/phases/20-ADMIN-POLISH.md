# Phase 20: Admin, Profile & Production Polish

**Status**: NOT STARTED
**Dependencies**: Phase 19 (Dashboard & Notifications)
**Deliverable**: Admin panel, user profile, responsive design, performance optimization, error handling
**Repository**: `ui/src/pages/`

---

## Overview

Final phase — build the admin panel (user management, ETL monitoring), user profile management, and production polish (responsive design, performance, accessibility, error boundaries).

**Two admin levels:** System admin has platform-wide visibility (all orgs, all users, ETL status). Org admin has company-level visibility (own org's members, settings, invites).

---

## Pages

### Admin Panel (`/admin` — admin role required)

**Health Tab:**
- Display data from `/health` endpoint — system health indicator with database connectivity, ETL freshness, uptime
- Can also be shown as a small indicator in the top bar for admins

**ETL Status Tab:**
- Source status table: source name, last load time, staleness indicator, records loaded
- API usage: SAM.gov daily quota consumed vs. limit (progress bar)
- Recent errors table: timestamp, source, error message, severity
- Alerts section: active warnings (stale data, rate limits, etc.)

#### ETL Staleness Thresholds (from Phase 6 `health_check.py`)

| Data Source | Green (Fresh) | Yellow (Stale) | Red (Critical) |
|------------|---------------|----------------|----------------|
| Opportunities | < 6 hours | 6-12 hours | > 12 hours |
| Entities | < 48 hours | 48-96 hours | > 96 hours |
| Federal Hierarchy | < 14 days | 14-28 days | > 28 days |
| Contract Awards | < 14 days | 14-28 days | > 28 days |
| Exclusions | < 14 days | 14-28 days | > 28 days |
| Subawards | < 14 days | 14-28 days | > 28 days |
| CALC+ Labor Rates | < 45 days | 45-90 days | > 90 days |
| USASpending | < 45 days | 45-90 days | > 90 days |

These thresholds are sourced from Phase 6 (`etl/health_check.py`). The ETL Status tab displays a color-coded table using these values, with last refresh timestamp and row count for each source.

**User Management Tab:**
- System admin sees all users across all orgs. Org admin sees only their org's members.
- User table: username, email, role, active status, last login, created date
- Inline actions: toggle active, change role (user/admin), reset password
- Reset password → display temporary password modal. After reset, `force_password_change` flag is set (added in Phase 14.5). Temp password only usable for password change, not normal app access.
- Cannot deactivate yourself (handled by API)

### Organization Admin Panel (Org Admin / Owner Role)

Accessible to users with `org_role` = `admin` or `owner`. Manages the subscribing company's team.

#### Org Settings Page
- View organization name, slug, member count, seat limit, subscription tier
- Edit organization name (org admin+)
- View created date

#### Member Management
- Table: display name, email, org role (owner/admin/member), status (active/inactive), last login
- Inline actions: change role (owner can promote/demote), toggle active status
- "Invite Member" button → modal with email + role selection → calls `POST /api/v1/org/invites`
- Cannot deactivate yourself or demote yourself below current role

#### Pending Invites
- Table: email, role, invited by, sent date, expires date, status
- Actions: revoke invite (DELETE /api/v1/org/invites/{id}), resend (future — requires email infra)

#### Activity Log (Org-Scoped)
- Table: timestamp, user, action, entity type, entity name/ID
- Filterable by user, action type, date range
- Data source: `activity_log` table scoped by `organization_id`
- Shows: prospect created/updated, status changes, proposals created, searches saved, team changes
- **Purpose**: Compliance visibility for federal contractors — auditable record of who did what

### System Admin Panel (System Admin Role)

Accessible to users with system `is_admin = true`. Manages the platform across all organizations.

#### Organization Management
- Table: org name, slug, member count, seat limit, subscription tier, is_active, created date
- Actions: create organization (`POST /api/v1/admin/organizations`), toggle active, edit seat limit
- "Create Organization" button → modal with name, slug, subscription tier, seat limit
- "Create Owner" button on each org → modal with email, display name, password → calls `POST /api/v1/admin/organizations/{id}/owner`

#### Cross-Org User Management
- Existing user list (from Phase 13) enhanced with organization name column
- Filter by organization
- Actions: toggle active, force password reset, view user's org

### User Profile (`/profile`)
- Display name, email, username (read-only)
- Edit display name and email
- Change password form (current + new + confirm)
- Account info: created date, role, last login

### Error & Edge Case Handling
- 404 page ("Page not found" with navigation)
- Global error boundary (catches React render errors)
- API error toasts (snackbar notifications for failed requests)
- Session expired handling (401 → redirect to login with "session expired" message)
- Rate limit handling (429 → toast with retry-after info; differentiate by policy type: auth vs search vs write)
- 409 Conflict handling (concurrent edit detection — "This record was modified. Reload and try again?"). Server-side: compare `UpdatedAt` timestamp in PATCH requests. If the record's `UpdatedAt` differs from what the client sent, return 409.
- DOMPurify for any rich text/HTML rendering (notes, descriptions) to prevent stored XSS
- External URLs (entity URLs from SAM.gov) rendered with `rel="noopener noreferrer"` and `target="_blank"`
- Offline detection (banner when network is down)

---

## Tasks

### 20.1 Admin — ETL Status
- [ ] Build ETL status page (admin-only route)
- [ ] Source status table with staleness coloring
- [ ] API usage progress bars
- [ ] Recent errors table
- [ ] Active alerts display
- [ ] Wire to `GET /api/v1/admin/etl-status`

### 20.2 Admin — User Management
- [ ] User management table
- [ ] Toggle active status
- [ ] Change role (dropdown)
- [ ] Reset password action → modal with temp password
- [ ] Wire to admin user API endpoints

### 20.3 User Profile
- [ ] Profile page with user info
- [ ] Edit display name / email form
- [ ] Change password form with validation
- [ ] Wire to auth profile endpoints

### 20.4 Error Handling & Edge Cases
- [ ] Global error boundary component
- [ ] 404 Not Found page
- [ ] API error snackbar (MUI Snackbar + Alert)
- [ ] Session expired redirect flow
- [ ] Rate limit toast with backoff info (differentiate by policy type: auth vs search vs write)
- [ ] 409 Conflict handling — "This record was modified. Reload and try again?" dialog
- [ ] DOMPurify for any rich text/HTML rendering (notes, descriptions) to prevent stored XSS
- [ ] External URLs (entity URLs from SAM.gov) rendered with `rel="noopener noreferrer"` and `target="_blank"`
- [ ] Offline detection banner

### 20.5 Responsive Design
- [ ] Sidebar collapses on tablets (< 1024px)
- [ ] Sidebar hidden on mobile (< 768px) — hamburger menu
- [ ] Data grids scroll horizontally on small screens
- [ ] Dashboard cards stack vertically on mobile
- [ ] Detail pages single-column on mobile
- [ ] Test on common breakpoints (1440, 1024, 768, 375)

### 20.6 Performance
- [ ] Route-based code splitting (React.lazy + Suspense)
- [ ] TanStack Query cache configuration (staleTime, gcTime per query type)
- [ ] Image/asset optimization (if any)
- [ ] Verify MUI bundle size — use tree shaking, only import used components
- [ ] Bundle size analysis (vite-plugin-visualizer)
- [ ] Verify initial route bundle < 500KB gzipped (measure after Phase 15 for baseline; MUI + Data Grid + Charts baseline is ~300-350KB). Total app size may exceed 500KB with code splitting.

### 20.7 Accessibility
- [ ] Keyboard navigation for all interactive elements
- [ ] ARIA labels on icon buttons and status indicators
- [ ] Color contrast meets WCAG AA
- [ ] Screen reader testing on key flows (search, detail, pipeline)
- [ ] Install `eslint-plugin-jsx-a11y` for automated accessibility linting (configured in Phase 15)

### 20.8 Organization Admin Features
- [ ] Org settings page (name, member list)
- [ ] Invite members flow (email + role)
- [ ] Remove members with confirmation
- [ ] View pending invites
- [ ] These are the org admin's view — separate from system admin

---

## Verification
- [ ] Admin panel accessible only to admin users
- [ ] `/health` data displayed in admin panel (Health tab)
- [ ] ETL status shows real source data from API
- [ ] User management CRUD works (create, toggle, reset password)
- [ ] Org admin can manage members (invite, remove, view pending)
- [ ] System admin sees all orgs; org admin sees only own org
- [ ] Profile edit and password change work
- [ ] 404 page renders for invalid routes
- [ ] Error toasts appear on API failures
- [ ] 409 conflict dialog works on concurrent edit
- [ ] DOMPurify sanitizes rendered HTML in notes/descriptions
- [ ] External links have `noopener noreferrer`
- [ ] Session expired redirects to login
- [ ] Responsive design works at all breakpoints
- [ ] Lighthouse score > 80 on performance
- [ ] `npm run build` produces initial route bundle < 500KB gzipped (total app may exceed with code splitting)
