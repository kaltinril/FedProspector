# Phase 76: UI Testing & Bug Fixes

**Status**: In Progress
**Started**: 2026-03-08

## Purpose

Track and fix bugs found during manual UI testing of the FedProspect web application.

## Issues

### 76-1: Dashboard DbContext concurrent access crash ✅ FIXED

**Symptom**: `GET /api/v1/dashboard` returns 400 after login with error:
> A second operation was started on this context instance before a previous operation completed.

**Root Cause**: `DashboardService.GetDashboardAsync()` fires 7 async queries concurrently via `Task.WhenAll`, but EF Core's `DbContext` is not thread-safe. All queries share the same injected `DbContext` instance.

**File**: `api/src/FedProspector.Infrastructure/Services/DashboardService.cs`

**Fix**: Run queries sequentially with individual `await` calls instead of `Task.WhenAll`. DbContext requires single-threaded access.

### 76-2: Root URL (/) shows 404 ✅ FIXED

**Symptom**: Navigating to `localhost:5173` shows the 404 "Page Not Found" page instead of the dashboard.

**Root Cause**: No route defined for `/` in `routes.tsx`. The catch-all `*` route renders `NotFoundPage`.

**File**: `ui/src/routes.tsx`

**Fix**: Added `<Navigate to="/dashboard" replace />` route for `/` so the root URL redirects to the dashboard.

### 76-3: Organizations tab visible to non-system-admins ✅ FIXED

**Symptom**: `POST /api/v1/admin/organizations` returns 403 for org admins. The Organizations tab and its "Create Organization" / "Create Organization Owner" buttons are visible to all admins, but the backend requires `is_system_admin = true`.

**Root Cause**: `isSystemAdmin` was not exposed in the user profile. The UI had no way to distinguish org admins from system admins, so it showed the Organizations tab to everyone with `isAdmin = true`.

**Files**:
- `api/src/FedProspector.Core/DTOs/UserProfileDto.cs` — added `IsSystemAdmin` property
- `api/src/FedProspector.Infrastructure/Services/AuthService.cs` — map `IsSystemAdmin` in profile DTO
- `ui/src/types/auth.ts` — added `isSystemAdmin` to TypeScript DTO
- `ui/src/auth/AuthContext.tsx` — exposed `isSystemAdmin` in auth context
- `ui/src/pages/admin/AdminPage.tsx` — Organizations tab only rendered when `isSystemAdmin` is true

**Fix**: Added `isSystemAdmin` field across the full stack (C# DTO → API response → TS type → AuthContext). Organizations tab is now conditionally rendered based on this flag. Also promoted test user (user_id=1) to `is_system_admin = 1` in the database.

### 76-4: Organizations tab has no list view ✅ FIXED

**Symptom**: Creating an organization succeeds but the Organizations tab shows only a placeholder message — no way to see existing orgs.

**Root Cause**: No `GET /api/v1/admin/organizations` endpoint existed; the UI had no list query.

**Files**:
- `api/src/FedProspector.Core/Interfaces/IOrganizationService.cs` — added `ListOrganizationsAsync()`
- `api/src/FedProspector.Infrastructure/Services/OrganizationService.cs` — implemented list query
- `api/src/FedProspector.Api/Controllers/AdminController.cs` — added `GET organizations` endpoint (system admin only)
- `ui/src/api/admin.ts` — added `listOrganizations()` API call
- `ui/src/queries/useAdmin.ts` — added `useListOrganizations` query hook
- `ui/src/pages/admin/OrganizationsTab.tsx` — replaced placeholder with MUI table (ID, Name, Slug, Tier, Max Users, Active, Created); auto-refreshes after org creation

**Fix**: Added list endpoint + UI table. Organizations tab now shows all orgs in a table with auto-refresh on create.

### 76-5: Create Organization Owner UX is unusable ✅ FIXED

**Symptom**: "Create Organization Owner" dialog requires manually typing a numeric Organization ID. No validation prevents negative numbers. Users have no way to know which ID maps to which org.

**File**: `ui/src/pages/admin/OrganizationsTab.tsx`

**Fix**: Replaced raw number input with a Select dropdown populated from the org list. Added an "Add Owner" action button on each org table row that pre-selects the org and opens the dialog.

### 76-6: Health tab crashes — no /health endpoint ✅ FIXED

**Symptom**: Admin Health tab shows "Something went wrong" error. Console shows `GET /health` returning 503 (Service Unavailable).

**Root Cause**: No health check endpoint existed in the API. The UI was built to call `GET /health` but nobody implemented the backend for it.

**File**: `api/src/FedProspector.Api/Controllers/HealthController.cs` (new)

**Fix**: Added `GET /health` endpoint (AllowAnonymous) that checks database connectivity and ETL freshness. Returns `{ status, database, etlFreshness }` matching the UI's `HealthResponse` type. ETL thresholds: ≤48h = Healthy, ≤7d = Degraded, >7d = Unhealthy.

### 76-7: Daily load scheduler commands broken — wrong CLI format ✅ FIXED

**Symptom**: `python main.py load daily` fails immediately with `Error: No such command 'load-opportunities'.` (exit code 2, 0 seconds).

**Root Cause**: The CLI was reorganized into command groups (`load`, `search`, `health`) but the `JOBS` dictionary in `scheduler.py` still uses the old flat command format (e.g., `load-opportunities` instead of `load opportunities`). Every job in the dict has this bug — none of the daily load jobs work.

**File**: `fed_prospector/etl/scheduler.py` (JOBS dict, lines ~32-113)

**Fix**: Update all `"command"` entries to use group-based CLI format (e.g., `["python", "main.py", "load", "opportunities", "--key", "2"]`). Verify each mapping against `add_command` registrations in `main.py`.

### 76-8: "API calls used" summary is misleading — shows estimate, not actual ✅ FIXED

**Symptom**: After a failed daily load (0 jobs ran), summary shows `API calls used: ~35` — implying 35 calls were consumed when zero were actually made.

**Root Cause**: `load_batch.py` computes `total_est` once before jobs run, then prints the same value in both the header ("Est. API calls") and summary ("API calls used"). No actual call tracking exists.

**File**: `fed_prospector/cli/load_batch.py` (lines ~51, ~150)

**Fix**: Only sum estimates for jobs that actually succeeded. Rename label to clarify it's still an estimate (e.g., `Est. API calls used`).

### 76-9: Daily load freshness skip thresholds too generous + ignores failed runs ✅ FIXED

**Symptom**: `load daily` reports awards as `SKIP (fresh - loaded 57h ago)` and exclusions as `SKIP (fresh - loaded 119h ago)`. 119h (5 days) is not fresh for a daily batch. Summary shows "Skipped: 2, Failed: 0" — hiding stale data.

**Root Cause**: Three sub-bugs:
1. **Thresholds derived from staleness_hours/2**: Awards/exclusions have `staleness_hours=336` (14-day health alarm), so skip threshold = 168h (7 days). Far too generous for daily runs.
2. **Ignores last run status**: `get_job_status()` returns `hours_since_last_run` based on `started_at` regardless of whether that run COMPLETED or FAILED. A failed run 2h ago still counts as "fresh."
3. **Misleading message**: Says "loaded Xh ago" but checks `started_at`, not `completed_at`. And 119h is clearly not "fresh."

**Files**:
- `fed_prospector/cli/load_batch.py` (lines ~84-97 — freshness check logic)
- `fed_prospector/etl/scheduler.py` (JOBS dict — need per-job `daily_freshness_hours`)

**Fix**: Add `daily_freshness_hours` to JOBS dict (e.g., 24h for awards/exclusions). Only skip if last run was COMPLETED and within the freshness window. Improve skip message to show status context.

### 76-10: full_name column too short for SAM.gov contracting officer names ✅ FIXED

**Symptom**: `Error processing aaae5bd96e1a479aaecc1e9a02b6c444: 1406 (22001): Data too long for column 'full_name' at row 1`

**Root Cause**: `contracting_officer.full_name` is VARCHAR(200). Some SAM.gov POC names exceed this (possibly long titles, suffixes, or concatenated names).

**File**: `fed_prospector/db/schema/tables/90_web_api.sql` (line ~43)

**Fix**: ALTER TABLE to VARCHAR(500). Update DDL file to match. The unique index uses a 100-char prefix so it's unaffected.

## Code Review Issues

### 76-R1: Health endpoint leaks internal error details (Medium/Security)

**Problem**: HealthController is `[AllowAnonymous]` but returns raw `ex.Message` from database exceptions in the `Description` field. Can leak hostnames, connection strings, driver versions.

**File**: `api/src/FedProspector.Api/Controllers/HealthController.cs`

**Fix**: Replace `ex.Message` with generic error strings in health check failure descriptions.

### 76-R2: InvalidOperationException returns 500 instead of 400 (Medium)

**Problem**: `OrganizationService` throws `InvalidOperationException` for business rule violations (duplicate slug, existing owner, duplicate email). These likely bubble up as 500 errors instead of 400/409. Users get "Failed to create organization" with no explanation.

**Files**:
- `api/src/FedProspector.Infrastructure/Services/OrganizationService.cs`
- `api/src/FedProspector.Api/Controllers/AdminController.cs`

**Fix**: Catch `InvalidOperationException` in AdminController and return 400/409 with the validation message.

### 76-R3: Repeated system-admin authorization check (Medium/Architecture)

**Problem**: The same 2-line `HasClaim("is_system_admin") + Forbid()` check is copy-pasted 8 times in AdminController. Fragile — new endpoints could miss it.

**Files**:
- `api/src/FedProspector.Api/Controllers/AdminController.cs`
- `api/src/FedProspector.Api/Program.cs` (register policy)

**Fix**: Register a `"SystemAdmin"` authorization policy in Program.cs and use `[Authorize(Policy = "SystemAdmin")]` on the endpoints.

### 76-R4: No AdminGuard on /admin route (Low/UX)

**Problem**: Non-admin users can navigate to `/admin` and see the page shell before backend 403s kick in. Backend is secure but UX is poor.

**File**: `ui/src/routes.tsx`

**Fix**: Wrap the admin route with `AdminGuard` for defense-in-depth.

### 76-R5: Inconsistent query key pattern (Low/Code Quality)

**Problem**: `useListOrganizations` hardcodes `['admin', 'organizations']` instead of using the centralized `queryKeys.admin.*` pattern. Cache invalidation in OrganizationsTab also uses the hardcoded key.

**Files**:
- `ui/src/queries/useAdmin.ts`
- `ui/src/pages/admin/OrganizationsTab.tsx`

**Fix**: Add `organizations` key to `queryKeys.admin` and use it consistently.

### 76-R6: TypeScript DTOs too permissive for required fields (Low/Types)

**Problem**: `CreateOrganizationRequest` and `CreateOwnerRequest` mark required fields as `string | null` in TypeScript when C# requires them non-null. Form guards against it at runtime but types don't enforce it.

**File**: `ui/src/types/api.ts`

**Fix**: Change fields from `string | null` to `string` (required, non-nullable).

## Admin Page Audit Issues

### 76-A1: Temp password never shown after reset (HIGH)

**Problem**: TS `ResetPasswordResponse` is missing `temporaryPassword` field. UI shows the message string instead of the actual generated password. Admin cannot give users their new credentials.

**Files**:
- `ui/src/types/api.ts` — `ResetPasswordResponse` missing `temporaryPassword`
- `ui/src/pages/admin/UserManagementTab.tsx:79` — `setTempPassword(resp.message)` should be `resp.temporaryPassword`
- `api/src/FedProspector.Core/DTOs/Admin/ResetPasswordResponse.cs` — has both `Message` and `TemporaryPassword`

**Fix**: Add `temporaryPassword: string` to TS type, change UI to display `resp.temporaryPassword`.

### 76-A2: Load history pagination completely broken (HIGH)

**Problem**: UI sends `page`/`pageSize` query params but backend expects `limit`/`offset`. Admin always sees only the first 20 records regardless of page navigation.

**Files**:
- `ui/src/api/admin.ts:52` — sends `page` and `pageSize`
- `ui/src/types/api.ts:1095-1101` — `LoadHistoryParams` has `page`/`pageSize`
- `api/src/FedProspector.Api/Controllers/AdminController.cs:44-45` — expects `limit`/`offset`

**Fix**: Either change UI to send `limit`/`offset`, or change backend to accept `page`/`pageSize`. Align the TS `LoadHistoryResponse` type too — it expects `page`, `pageSize`, `totalPages` that the backend never sends.

### 76-A3: Health tab renders ETL data as [object Object] (MEDIUM)

**Problem**: `HealthController` puts nested anonymous objects into the ETL freshness data dictionary. `HealthTab.tsx` renders values with `String(value)` which produces `[object Object]` for nested objects.

**Files**:
- `api/src/FedProspector.Api/Controllers/HealthController.cs:106-112` — nested `new { lastLoad, age, totalLoads }`
- `ui/src/pages/admin/HealthTab.tsx:73-78, 108-113` — `String(value ?? '--')`
- `ui/src/types/api.ts:1113` — `Record<string, string | number | boolean | null>` doesn't account for nested objects

**Fix**: Either flatten the backend response (preferred) or handle nested objects in the UI renderer.

### 76-A4: ETL Status + Load History tabs visible to org admins but 403-blocked (MEDIUM)

**Problem**: These tabs are visible to all admins but the backend endpoints require SystemAdmin policy. Org admins see a loading spinner then a generic error.

**Files**:
- `ui/src/pages/admin/AdminPage.tsx:22-27` — tabs shown to all admins
- `api/src/FedProspector.Api/Controllers/AdminController.cs` — ETL/LoadHistory endpoints are SystemAdmin-only

**Fix**: Hide ETL Status, Load History tabs for non-system-admins (same pattern as Organizations tab).

### 76-A5: Create org/owner 409 error messages swallowed (MEDIUM)

**Problem**: Backend now returns 409 Conflict with specific messages (duplicate slug, existing owner, duplicate email) but UI shows generic "Failed to create organization/owner" regardless.

**Files**:
- `ui/src/pages/admin/OrganizationsTab.tsx:53-54, 70-71` — generic error messages

**Fix**: Extract error message from Axios error response and display it.

### 76-A6: No validation on org create/owner create forms (MEDIUM)

**Problem**: No min/max length validation on name/slug fields. No email format validation. No password minimum length/complexity. Backend also has no validation annotations.

**Files**:
- `ui/src/pages/admin/OrganizationsTab.tsx` — form fields have `required` but no length/format validation
- `api/src/FedProspector.Core/DTOs/Admin/CreateOrganizationRequest.cs` — no data annotations
- `api/src/FedProspector.Core/DTOs/Admin/CreateOwnerRequest.cs` — no data annotations

**Fix**: Add FluentValidation validators on backend. Add matching client-side validation.

### 76-A7: /health endpoint may miss Vite proxy (MEDIUM)

**Problem**: `admin.ts` calls `/health` with raw axios instead of `apiClient`. If Vite dev proxy only forwards `/api/*`, the health call hits the Vite dev server and gets a 404 or HTML page.

**File**: `ui/src/api/admin.ts:57`

**Fix**: Verify Vite proxy config forwards `/health`. Or change backend route to `/api/v1/health` and use `apiClient`.

### 76-A8: 3 backend endpoints have no UI (LOW)

**Problem**: `GET /api/v1/admin/health-snapshots`, `GET /api/v1/admin/api-keys`, `GET /api/v1/admin/jobs` exist in AdminController but no UI tab or component consumes them.

**File**: `api/src/FedProspector.Api/Controllers/AdminController.cs`

**Fix**: Either add UI for these (health trends chart, per-key tracking, job-level view) or document as intentionally API-only.

### 76-A9: Admin can demote themselves to USER role (MEDIUM)

**Problem**: User management allows changing any user's role including the logged-in admin. Backend partially blocks `isAdmin: false` on self but may still apply `role: USER`, creating inconsistent state.

**File**: `ui/src/pages/admin/UserManagementTab.tsx:57-71`

**Fix**: Disable role dropdown for the currently logged-in user, or add backend guard to reject self-demotion entirely.

### 76-A10: Organizations list has no error state (LOW)

**Problem**: If the organizations API call fails, the component renders as if there are zero orgs rather than showing an error.

**File**: `ui/src/pages/admin/OrganizationsTab.tsx:99-158`

**Fix**: Add `isError` check like other admin tabs.

### 76-A11: staleTime missing on useListOrganizations (LOW)

**Problem**: `useListOrganizations` has no `staleTime`, causing refetch on every mount/focus. Other admin hooks use 30s-120s staleTime.

**File**: `ui/src/queries/useAdmin.ts`

**Fix**: Add `staleTime: 60 * 1000` to match other admin queries.
