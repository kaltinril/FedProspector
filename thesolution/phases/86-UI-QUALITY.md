# Phase 86 — UI Quality & Resilience

## Status: PLANNED

**Priority**: MEDIUM
**Depends on**: Phase 85 (contract alignment affects UI error handling)

---

## Context

Review of the React UI identified authentication flow vulnerabilities, type safety gaps, missing cache invalidation, and error boundary gaps that affect reliability and developer experience.

---

## Items to Address

### HIGH

**86-1 — AdminGuard Missing isSystemAdmin Check**
File: `ui/src/auth/AdminGuard.tsx:10`
Only checks `isAdmin`. System admin users without `isAdmin=true` are blocked from /admin routes. Fix:
```typescript
if (!isAdmin && !isSystemAdmin) return <Navigate to="/" />;
```

**86-2 — Missing Query Invalidation on Mutations**
Files: Multiple mutation hooks in `ui/src/queries/`
When mutations succeed (create prospect, save search, etc.), related queries are not invalidated. UI shows stale data until manual refresh. Add `queryClient.invalidateQueries({ queryKey: [...] })` in all mutation `onSuccess` callbacks.

**86-3 — Unhandled Error Type in LoginPage**
File: `ui/src/pages/login/LoginPage.tsx:74-93`
Complex type assertions on error object: `(err as { response: {...} }).response`. If error structure differs, throws instead of showing user-friendly message. Use `axios.isAxiosError(err)` type guard.

**86-4 — Untyped Error in Admin Mutation Handlers**
File: `ui/src/pages/admin/OrganizationsTab.tsx:54,72`
`onError: (error: any) => {` defeats TypeScript safety. Type as `AxiosError<{ error?: string }>`.

**86-5 — 404 Route Requires Authentication**
File: `ui/src/routes.tsx:228-234`
NotFoundPage wrapped in AuthenticatedLayout. Unauthenticated users see login page instead of 404. Add public 404 route outside auth guard.

---

### MEDIUM

**86-6 — DataTable Uses `any` Type**
File: `ui/src/components/shared/DataTable.tsx:14-15`
`type AnyRow = any` defeats column type checking. No IDE autocomplete for column accessors. Use generic type parameter:
```typescript
function DataTable<T extends Record<string, unknown>>()
```

**86-7 — AuthContext Silent Failure on Network Error**
File: `ui/src/auth/AuthContext.tsx:28-39`
`refreshSession()` catches all errors, sets user to null. Temporary network failure forces re-login. Retry with exponential backoff. Distinguish auth failure from network error.

**86-8 — SearchFilters Date Range Type Assertion**
File: `ui/src/components/shared/SearchFilters.tsx:47-52`
`const range = val as { start?: string; end?: string }` — unsafe assertion without validation. Add runtime validation or use discriminated union type.

**86-9 — SaveSearchModal Unsafe `as never` Cast**
File: `ui/src/components/shared/SaveSearchModal.tsx:43`
`filterCriteria: filterCriteria as never` defeats type safety completely. Properly type filterCriteria to match API contract.

**86-10 — useLocalStorage No Error Handling on Parse**
File: `ui/src/hooks/useLocalStorage.ts:4-10`
`JSON.parse()` without try-catch. Malformed localStorage data crashes app on startup. Wrap in try-catch; reset to initialValue on parse error.

**86-11 — OfflineBanner Uses Unreliable navigator.onLine**
File: `ui/src/components/shared/OfflineBanner.tsx:7`
`navigator.onLine` unreliable for all browsers/connections (VPN, metered). Combine with periodic health check fetch.

**86-12 — Query Key Params Object Identity**
File: `ui/src/queries/queryKeys.ts`
Query keys include params objects by reference. Same query with different object instances creates separate cache entries. Spread specific param properties into key array instead of passing whole object.

---

### LOW

**86-13 — No Global Error Boundary at Root**
File: `ui/src/App.tsx`
ErrorBoundary only on authenticated routes. If outer providers crash, no fallback UI. Wrap entire App in ErrorBoundary at root level.

**86-14 — OfflineBanner zIndex Conflict**
File: `ui/src/components/shared/OfflineBanner.tsx:30`
`zIndex: 1400` may conflict with MUI Snackbar (1300) or dialogs. Use MUI theme zIndex scale.

**86-15 — Hardcoded Set-Aside Colors**
File: `ui/src/pages/opportunities/OpportunitySearchPage.tsx:33-44`
Color mapping hardcoded in component instead of centralized config. Move to `utils/constants.ts`.

---

## Verification Checklist

- [ ] 86-1: Test admin route with systemAdmin user (not isAdmin) — verify access
- [ ] 86-2: Create prospect — verify list updates immediately (no stale data)
- [ ] 86-3: Trigger login error — verify friendly message shown
- [ ] 86-4: No `any` types in mutation error handlers
- [ ] 86-5: Test 404 route while logged out — verify 404 shown (not login redirect)
- [ ] 86-6: DataTable has generic type parameter
- [ ] 86-10: Clear localStorage, set malformed value — verify no crash on load
- [ ] 86-13: Root-level ErrorBoundary present in App.tsx
- [ ] TypeScript build clean: `cd ui && npm run build`
