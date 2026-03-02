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
- Staleness: green (< 24h), yellow (24-48h), red (> 48h)
- API usage: SAM.gov daily quota consumed vs. limit (progress bar)
- Recent errors table: timestamp, source, error message, severity
- Alerts section: active warnings (stale data, rate limits, etc.)

**User Management Tab:**
- System admin sees all users across all orgs. Org admin sees only their org's members.
- User table: username, email, role, active status, last login, created date
- Inline actions: toggle active, change role (user/admin), reset password
- Reset password → display temporary password modal
- Cannot deactivate yourself (handled by API)

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
- 409 Conflict handling (concurrent edit detection — "This record was modified. Reload and try again?")
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
- [ ] Verify initial load < 500KB gzipped

### 20.7 Accessibility
- [ ] Keyboard navigation for all interactive elements
- [ ] ARIA labels on icon buttons and status indicators
- [ ] Color contrast meets WCAG AA
- [ ] Screen reader testing on key flows (search, detail, pipeline)

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
- [ ] `npm run build` produces production bundle < 500KB gzipped
