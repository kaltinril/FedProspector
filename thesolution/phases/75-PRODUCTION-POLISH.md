# Phase 75: Production Polish

**Status**: NOT STARTED
**Dependencies**: Phase 70 (Admin & Organization Management) -- COMPLETE
**Split from**: Old Phase 70 (see [19-UI-PHASE-REVIEW.md](completed/19-UI-PHASE-REVIEW.md) for rationale)

---

## Already Implemented (verified in codebase)

The following items from the original Phase 75 scope are already built and working. They do NOT need any further work unless defects are found during testing.

### Error Handling -- DONE
- **404 page**: `ui/src/pages/errors/NotFoundPage.tsx` -- renders on catch-all `*` route, with "Go to Dashboard" and "Go Back" buttons
- **Error boundaries**: `ui/src/components/shared/ErrorBoundary.tsx` using `react-error-boundary` -- wraps every authenticated route in `ui/src/routes.tsx` via `AuthenticatedLayout`
- **Session expired flow**: `ui/src/api/client.ts` 401 interceptor attempts token refresh, then redirects to `/login?expired=true`; `LoginPage.tsx` shows "Your session has expired" warning alert

### Code Splitting & Bundle Optimization -- DONE
- **React.lazy per route**: All 17+ page imports in `ui/src/routes.tsx` use `lazy()` with `Suspense` fallback in `App.tsx`
- **Vendor chunk splitting**: `ui/vite.config.ts` defines `manualChunks` for react, mui, query, charts, datagrid
- **Bundle analysis**: `rollup-plugin-visualizer` configured, available via `npm run analyze`

### Loading & Empty States -- DONE
- **LoadingState**: `ui/src/components/shared/LoadingState.tsx` with `skeleton`, `spinner`, and `overlay` variants
- **EmptyState**: `ui/src/components/shared/EmptyState.tsx` with customizable title, message, icon, and action slot
- **Toast notifications**: `notistack` SnackbarProvider in `ui/src/components/shared/NotificationProvider.tsx`; `ApiErrorListener` dispatches toasts for rate-limit (429) and conflict (409) responses

### Responsive Sidebar -- DONE
- **Mobile drawer**: `ui/src/components/layout/Sidebar.tsx` renders a temporary `Drawer` on `xs`-`sm` (hamburger menu), permanent on `md`+
- **Hamburger toggle**: `ui/src/components/layout/TopBar.tsx` has a `MenuIcon` button visible only on mobile (`display: { md: 'none' }`)
- **Collapsible desktop sidebar**: Toggle between 240px and 64px widths, persisted in localStorage

### Accessibility Foundations -- DONE
- **Skip to main content**: Link in `ui/src/components/layout/AppLayout.tsx` that becomes visible on focus
- **Focus management on route changes**: `AppLayout.tsx` moves focus to `#main-content` via `useEffect` on `location.pathname`
- **ARIA attributes**: Extensive `aria-label`, `aria-controls`, `aria-haspopup`, `aria-expanded` on menus, buttons, data tables (DataTable defaults `aria-label` to "Data table")
- **jsx-a11y ESLint plugin**: Configured in `ui/eslint.config.js` with `flatConfigs.recommended` rules
- **Dark/light mode**: `ui/src/theme/ThemeContext.tsx` with localStorage persistence, toggle in TopBar
- **Offline detection**: `ui/src/components/shared/OfflineBanner.tsx` shows fixed warning banner when browser goes offline

---

## Remaining Work

### 75.1 Responsive Data Tables
**Owner**: ui-developer
**Effort**: ~1 day

The `DataTable` component (`ui/src/components/shared/DataTable.tsx`) wraps MUI `DataGrid` with `overflowX: auto`, but does not hide or reformat columns for narrow viewports.

**Tasks**:
1. Audit all pages that use `DataTable` or `DataGrid` directly -- identify which columns are essential vs secondary
2. Add responsive column visibility using MUI DataGrid's column visibility model or custom breakpoint logic
3. For search pages (`OpportunitySearchPage`, `AwardSearchPage`, `EntitySearchPage`), define mobile-friendly column sets that hide less important columns (e.g., agency, dates) below `md` breakpoint
4. Test that horizontal scroll still works as fallback when columns cannot be hidden

**Files to modify**:
- `ui/src/components/shared/DataTable.tsx` (optional: add responsive column helper)
- `ui/src/pages/opportunities/OpportunitySearchPage.tsx`
- `ui/src/pages/awards/AwardSearchPage.tsx`
- `ui/src/pages/entities/EntitySearchPage.tsx`
- `ui/src/pages/awards/ExpiringContractsPage.tsx`
- `ui/src/pages/subawards/TeamingPartnerPage.tsx`
- `ui/src/pages/admin/LoadHistoryTab.tsx`

### 75.2 Responsive Page Layouts
**Owner**: ui-developer
**Effort**: ~1 day

Detail pages and dashboards need breakpoint-specific layout adjustments.

**Tasks**:
1. Audit `DashboardPage.tsx` grid layout -- ensure cards stack vertically on mobile instead of wrapping awkwardly
2. Review detail pages (`OpportunityDetailPage`, `AwardDetailPage`, `EntityDetailPage`, `ProspectDetailPage`) -- tab panels should use full width on mobile; side-by-side panels (if any) should stack
3. Review `ProspectPipelinePage` (Kanban) -- columns should scroll horizontally on narrow screens or stack with a column selector
4. Verify `SearchFilters` component collapses or becomes a toggle-able panel on mobile
5. Test login and register pages on narrow viewports (already use responsive `px` values -- may just need verification)

**Files to audit**:
- `ui/src/pages/dashboard/DashboardPage.tsx`
- `ui/src/pages/opportunities/OpportunityDetailPage.tsx`
- `ui/src/pages/awards/AwardDetailPage.tsx`
- `ui/src/pages/entities/EntityDetailPage.tsx`
- `ui/src/pages/prospects/ProspectPipelinePage.tsx`
- `ui/src/pages/prospects/ProspectDetailPage.tsx`
- `ui/src/components/shared/SearchFilters.tsx`

### 75.3 Accessibility Audit & Fixes
**Owner**: qa (audit) + ui-developer (fixes)
**Effort**: ~1.5 days

Foundations are solid (skip link, focus management, ARIA, jsx-a11y lint). This task covers manual testing and edge case fixes.

**Tasks**:
1. **Keyboard navigation audit**: Tab through every page end-to-end. Verify all interactive elements (buttons, links, menus, modals, data grid rows) are reachable and operable via keyboard alone. Pay special attention to:
   - Kanban drag-and-drop on ProspectPipelinePage (uses @dnd-kit -- verify keyboard support)
   - Modal dialogs (ConfirmDialog, SaveSearchModal) -- verify focus trap
   - Notification popover in TopBar -- verify Escape closes it
2. **Color contrast verification**: Run automated contrast checker (e.g., axe DevTools) against both light and dark themes. Known risk areas:
   - `text.secondary` colors (`#546E7A` light, `#B0BEC5` dark) against their backgrounds
   - Status chips / badges with colored backgrounds
   - Disabled button text
3. **Screen reader testing**: Test key flows with NVDA or VoiceOver:
   - Login flow
   - Search and navigate to an opportunity
   - Open tabs on detail pages
   - Read notification popover
4. **Fix issues found**: Create sub-tasks as needed for specific fixes

### 75.4 Bundle Size Baseline & Optimization
**Owner**: ui-developer
**Effort**: ~0.5 days

Bundle analysis tooling is in place (`npm run analyze`). This task establishes a baseline and optimizes if needed.

**Tasks**:
1. Run `npm run analyze` and record the current bundle sizes (total, per-chunk) in this document
2. Identify any chunks over 200 KB gzipped that could be further split
3. Check if `@mui/icons-material` tree-shaking is working (the codebase uses named imports like `import DashboardOutlined from '@mui/icons-material/DashboardOutlined'` which should tree-shake correctly)
4. Verify `date-fns` is tree-shaken (only specific functions imported, not the whole package)
5. Consider lazy-loading `@mui/x-charts` and `@mui/x-data-grid` vendor chunks only on pages that use them (currently they are separate chunks but loaded eagerly when the chunk is referenced)
6. Document target sizes and add a CI check if desired

### 75.5 Browser Compatibility Testing
**Owner**: qa
**Effort**: ~0.5 days

**Tasks**:
1. Test the full application in Chrome (latest), Firefox (latest), and Edge (latest)
2. Verify: login, search, detail pages, prospect pipeline drag-and-drop, admin panel, notifications
3. Check for CSS flexbox/grid rendering differences
4. Verify dark mode toggle works across browsers
5. Document any browser-specific issues and fix or defer

### 75.6 Page Transitions (Optional / Low Priority)
**Owner**: ui-developer
**Effort**: ~0.5 days

**Tasks**:
1. Add subtle fade transition on route changes (using React Router's `useNavigation` state or a lightweight animation library)
2. Keep transitions fast (150-200ms max) to avoid feeling sluggish
3. Ensure transitions do not interfere with accessibility (respect `prefers-reduced-motion` media query)

**Note**: This is cosmetic polish. Deprioritize if other tasks take longer than estimated.

---

## Out of Scope

These items are handled elsewhere or intentionally excluded:

- **Security hardening** -- Phase 80 (deferred until production deployment)
- **Image optimization** -- No user-uploaded images in the app; icons are from MUI Icons (SVG). No work needed.
- **Dark mode implementation** -- Already complete (ThemeContext + toggle in TopBar)
- **Lazy loading for heavy components** -- Already implemented via React.lazy route splitting and vendor chunk separation

---

## Dependencies & Risks

| Risk | Impact | Mitigation |
|------|--------|------------|
| Kanban drag-and-drop keyboard support may be limited in @dnd-kit | Accessibility gap for keyboard-only users | Test first; if @dnd-kit lacks keyboard support, add manual "Move to column" dropdown as alternative |
| Color contrast fixes may require theme palette changes | Visual appearance changes across the app | Get contrast ratios first, then decide if palette tweaks or component-level overrides are better |
| Responsive DataGrid column hiding may require per-page configuration | More work than a single shared solution | Start with the highest-traffic pages (opportunities, awards) and use a consistent pattern |
| Browser testing may uncover CSS issues | Unplanned fix work | Budget 0.5 days of fix time within the browser testing task |

---

## Success Criteria

1. All pages render correctly and are usable at 360px, 768px, 1024px, and 1440px viewport widths
2. Every interactive element is reachable and operable via keyboard alone
3. No WCAG AA color contrast violations in either theme
4. Bundle sizes documented; no single chunk exceeds 300 KB gzipped without justification
5. Application works without visual or functional regressions in Chrome, Firefox, and Edge
6. Zero console errors or warnings during normal usage flows

---

## Estimated Total Effort

| Task | Effort |
|------|--------|
| 75.1 Responsive Data Tables | ~1 day |
| 75.2 Responsive Page Layouts | ~1 day |
| 75.3 Accessibility Audit & Fixes | ~1.5 days |
| 75.4 Bundle Size Baseline | ~0.5 days |
| 75.5 Browser Compatibility Testing | ~0.5 days |
| 75.6 Page Transitions (optional) | ~0.5 days |
| **Total** | **~5 days** (4 days without optional 75.6) |
