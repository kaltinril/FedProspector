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

## Code Review Issues

### 76-7: Daily load scheduler commands broken — wrong CLI format

**Symptom**: `python main.py load daily` fails immediately with `Error: No such command 'load-opportunities'.` (exit code 2, 0 seconds).

**Root Cause**: The CLI was reorganized into command groups (`load`, `search`, `health`) but the `JOBS` dictionary in `scheduler.py` still uses the old flat command format (e.g., `load-opportunities` instead of `load opportunities`). Every job in the dict has this bug — none of the daily load jobs work.

**File**: `fed_prospector/etl/scheduler.py` (JOBS dict, lines ~32-113)

**Fix**: Update all `"command"` entries to use group-based CLI format (e.g., `["python", "main.py", "load", "opportunities", "--key", "2"]`). Verify each mapping against `add_command` registrations in `main.py`.

### 76-8: "API calls used" summary is misleading — shows estimate, not actual

**Symptom**: After a failed daily load (0 jobs ran), summary shows `API calls used: ~35` — implying 35 calls were consumed when zero were actually made.

**Root Cause**: `load_batch.py` computes `total_est` once before jobs run, then prints the same value in both the header ("Est. API calls") and summary ("API calls used"). No actual call tracking exists.

**File**: `fed_prospector/cli/load_batch.py` (lines ~51, ~150)

**Fix**: Only sum estimates for jobs that actually succeeded. Rename label to clarify it's still an estimate (e.g., `Est. API calls used`).

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
