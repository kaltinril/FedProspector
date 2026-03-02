# Phase 20: Admin, Profile & Production Polish

**Status**: NOT STARTED
**Dependencies**: Phase 19 (Dashboard & Notifications)
**Deliverable**: Admin panel, user profile, responsive design, performance optimization, error handling
**Repository**: `ui/src/pages/`

---

## Overview

Final phase — build the admin panel (user management, ETL monitoring), user profile management, and production polish (responsive design, performance, accessibility, error boundaries).

---

## Pages

### Admin Panel (`/admin` — admin role required)

**ETL Status Tab:**
- Source status table: source name, last load time, staleness indicator, records loaded
- Staleness: green (< 24h), yellow (24-48h), red (> 48h)
- API usage: SAM.gov daily quota consumed vs. limit (progress bar)
- Recent errors table: timestamp, source, error message, severity
- Alerts section: active warnings (stale data, rate limits, etc.)

**User Management Tab:**
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
- Rate limit handling (429 → toast with retry-after info)
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
- [ ] Rate limit toast with backoff info
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
- [ ] Bundle size analysis (vite-plugin-visualizer)
- [ ] Verify initial load < 500KB gzipped

### 20.7 Accessibility
- [ ] Keyboard navigation for all interactive elements
- [ ] ARIA labels on icon buttons and status indicators
- [ ] Color contrast meets WCAG AA
- [ ] Screen reader testing on key flows (search, detail, pipeline)

---

## Verification
- [ ] Admin panel accessible only to admin users
- [ ] ETL status shows real source data from API
- [ ] User management CRUD works (create, toggle, reset password)
- [ ] Profile edit and password change work
- [ ] 404 page renders for invalid routes
- [ ] Error toasts appear on API failures
- [ ] Session expired redirects to login
- [ ] Responsive design works at all breakpoints
- [ ] Lighthouse score > 80 on performance
- [ ] `npm run build` produces production bundle < 500KB gzipped
