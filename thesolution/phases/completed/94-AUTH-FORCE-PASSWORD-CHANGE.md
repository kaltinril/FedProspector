# Phase 94: Auth — Force Password Change UI Flow

## Status: PLANNED

## Problem
After login, users with `force_password_change = 'Y'` in the DB get 403 Forbidden on ALL API calls. The `ForcePasswordChangeMiddleware` correctly blocks endpoints, but the UI has no handling — it shows a generic "Something went wrong" error wall instead of redirecting to a password change screen.

Additionally, auth cookies were set with `Secure=true` unconditionally, which breaks local dev (HTTP). This is already fixed in uncommitted changes.

## Root Cause
1. **Cookie Secure flag** (fixed, uncommitted): `AuthController.SetAuthCookies()` hardcoded `Secure = true`. Browsers discard Secure cookies over HTTP.
2. **No UI force-password-change flow**: `ForcePasswordChangeMiddleware` returns `403 {"error": "Password change required"}` but the UI doesn't detect or handle this response. No redirect, no prompt.
3. **Login/me responses don't include forcePasswordChange**: The UI has no proactive way to know password change is required.

## Tasks

### Task 1: Immediate — Clear DB flag for dev user
```sql
UPDATE app_user SET force_password_change = 'N' WHERE email = 'jeremy.swartwood@msoneservices.com';
```

### Task 2: Backend — Include forcePasswordChange in responses
- **`AuthController.cs`** login response: Add `forcePasswordChange` field
- **`UserProfileDto.cs`**: Add `ForcePasswordChange` property (if not present)
- **`AuthService.cs`**: Map `ForcePasswordChange` from `AppUser` into profile DTO

### Task 3: UI — Add force-password-change 403 interceptor
- **`ui/src/api/client.ts`**: In the response interceptor, detect `403` with `error === "Password change required"` and redirect to `/change-password`
- **Fix latent bug**: `.split('=')[1]` → `.split('=').slice(1).join('=')` for cookie parsing (line 17)

### Task 4: UI — Create ChangePasswordPage
- **`ui/src/pages/change-password/ChangePasswordPage.tsx`**: Dedicated page for forced password changes
- Extract/reuse the change-password form from `ui/src/pages/profile/ProfilePage.tsx` (lines 184-243)
- Show a banner explaining why the user must change their password
- After success: redirect to `/login` (backend revokes all sessions)

### Task 5: UI — Wire up routing and auth context
- **`ui/src/routes.tsx`**: Add `/change-password` as an authenticated route
- **`ui/src/auth/AuthContext.tsx`**: Expose `forcePasswordChange` from `/auth/me` response so components can check proactively

### Task 6: Rebuild, restart, verify
- `fed_prospector.bat build` — verify build succeeds
- `fed_prospector.bat restart api`
- Existing tests pass (Python + C#)

## Files to Modify

| File | Change |
|------|--------|
| `api/src/FedProspector.Api/Controllers/AuthController.cs` | Already fixed (Secure flag). Add forcePasswordChange to login response |
| `api/tests/.../AuthControllerTests.cs` | Already fixed (constructor sig) |
| `api/src/FedProspector.Core/DTOs/UserProfileDto.cs` | Add ForcePasswordChange field |
| `api/src/FedProspector.Infrastructure/Services/AuthService.cs` | Map flag in profile DTO |
| `ui/src/api/client.ts` | Add force-password-change 403 interceptor, fix cookie parsing |
| `ui/src/auth/AuthContext.tsx` | Handle forcePasswordChange from /auth/me |
| `ui/src/routes.tsx` | Add /change-password route |
| `ui/src/pages/change-password/ChangePasswordPage.tsx` | New dedicated change-password page |

## Existing Code to Reuse
- `ui/src/pages/profile/ProfilePage.tsx` lines 184-243 — working change-password form
- `ui/src/api/auth.ts` — `changePassword()` API method
- `ui/src/utils/apiErrorHandler.ts` — custom event pattern for error dispatch

## Known Issues (QA Review Findings)

### HIGH — Must fix before phase ships

| # | Issue | File(s) | Detail |
|---|-------|---------|--------|
| H1 | **Login always navigates to /dashboard, ignoring forcePasswordChange** | `LoginPage.tsx:81` | After `await login()`, code unconditionally calls `navigate('/dashboard')` before re-render. User hits dashboard briefly, then AuthGuard redirects to `/change-password` — visible flash. Worse, dashboard API calls fire and get 403'd, triggering the 403 interceptor race with React Router. **Fix:** Remove imperative `navigate('/dashboard')` and let the `<Navigate>` components (lines 66-72) handle routing on re-render. |
| H2 | **ChangePasswordPage has no `isLoading` guard — redirects to /login on refresh** | `ChangePasswordPage.tsx:26-32` | Page checks `isAuthenticated` without checking `isLoading`. On full page refresh, `user` is null until `/auth/me` completes, so the page immediately redirects to `/login`. AuthGuard handles this with a spinner; this page doesn't. **Fix:** Add `if (isLoading) return <CircularProgress />` before the auth check. |
| H3 | **TanStack Query cache is never cleared on logout** | `AuthContext.tsx:59-64`, `App.tsx` | `logout()` sets `user = null` but never calls `queryClient.clear()`. Cached data (notifications, prospects, org data) persists. If a different user logs in on the same tab, they see the previous user's data until queries refetch (up to 5min staleTime). **Fix:** Pass `queryClient` into AuthProvider or use `useQueryClient()` and call `.clear()` in `logout`. |
| H4 | **`refreshFailCount` never resets on re-login — breaks next session** | `client.ts:31-33, 86-91` | Module-level counter increments on refresh failure, only resets on *successful refresh*. After 3 failures → redirect to login. On re-login in same tab, counter stays at 3; next 401 skips refresh entirely and force-redirects to `/login?expired=true`. **Fix:** Export a `resetRefreshFailCount()` from `client.ts`, call it from `AuthContext.login`. |
| H5 | **Logout endpoint requires valid JWT + CSRF — fails after token expiry** | `AuthController.cs:65`, `CsrfMiddleware.cs` | Logout has `[Authorize]` and is not CSRF-exempt. After 30min (access token + XSRF cookie expire), logout POST gets 401/403. Client-side cleanup happens in `finally`, but server session is never revoked. Refresh token (7-day lifetime) may persist in browser. **Fix:** Add `/auth/logout` to CSRF exempt paths; consider `[AllowAnonymous]` with optional token parsing. |

### MEDIUM — Should fix in this phase

| # | Issue | File(s) | Detail |
|---|-------|---------|--------|
| M1 | **Password validation mismatch between frontend and backend** | `ChangePasswordPage.tsx:37`, `ProfilePage.tsx:70-76`, `ChangePasswordRequestValidator.cs:13-19` | Frontend only checks `length >= 8`. Backend requires uppercase + lowercase + digit. User can submit `abcdefgh`, button enables, server rejects with confusing error. **Fix:** Add matching rules to frontend validation in both pages; show requirements in helper text. |
| M2 | **Login form rejects short passwords — blocks legacy users** | `LoginPage.tsx:22` | Zod schema enforces `min(8)` on login. Users with pre-existing short passwords can't even submit the form. **Fix:** Remove min-length from the *login* schema (only enforce on registration/change). |
| M3 | **Login response DTO mismatch — `success` field missing** | `AuthController.cs:57`, `auth.ts` | Backend returns anonymous object `{ UserId, UserName, ExpiresAt, ForcePasswordChange }`. Frontend `AuthResult` type expects `success: boolean`. Currently harmless (login flow ignores response), but misleading types will cause bugs if anyone checks `result.success`. **Fix:** Either add `success = true` to backend response or fix the frontend type. |
| M4 | **GetProfile/UpdateProfile throw unhandled exceptions → 500s** | `AuthController.cs:185-212` | Both call service methods that throw `KeyNotFoundException` / `InvalidOperationException` without try/catch. Returns 500 instead of 404/400. `ChangePassword` (line 164-177) handles these correctly. **Fix:** Add matching try/catch blocks. |
| M5 | **Session expired + error alerts show simultaneously** | `LoginPage.tsx:122-132` | `sessionExpired` state is set from URL param and never cleared. User sees "session expired" warning, then submits bad creds and sees both alerts. **Fix:** Add `setSessionExpired(false)` in `onSubmit` alongside `setError(null)`. |
| M6 | **ProfilePage error handling doesn't extract server error messages** | `ProfilePage.tsx:87-90` | Uses `err.message` (generic Axios string like "Request failed with status code 400") instead of extracting `err.response.data.message`. `ChangePasswordPage` does this correctly. **Fix:** Match the pattern from ChangePasswordPage. |
| M7 | **Email lookup case-sensitivity inconsistency** | `AuthService.cs:78 vs 279` | `LoginAsync` queries `u.Email == email` (raw input). `RegisterAsync` uses `.ToLower()` comparison. If collation is case-sensitive, "User@Test.com" registered user can't login with "user@test.com". **Fix:** Use `.ToLower()` consistently, or use `normalizedEmail` for the DB query too. |
| M8 | **Race condition: in-flight API calls during logout trigger refresh loop** | `client.ts:84-117`, `AuthContext.tsx:59-64` | Logout clears cookies. Pending API calls get 401, trigger refresh attempts, which fail and increment `refreshFailCount` (connects to H4). **Fix:** Add `isLoggingOut` flag in `client.ts` to suppress 401 interceptor during logout. |

### LOW — Address when convenient

| # | Issue | File(s) | Detail |
|---|-------|---------|--------|
| L1 | **Inconsistent error response field names** | `AuthController.cs:168-176` | Success uses `{ message }`, errors use `{ message }` or `{ error }` inconsistently across endpoints. |
| L2 | **`clearSession()` exposed publicly — misuse risk** | `AuthContext.tsx:16, 67-69` | Clears local state without server logout. Any component could call it instead of `logout()`, leaving server session active. Rename or remove from public interface. |
| L3 | **Double navigation on logout from ChangePasswordPage** | `ChangePasswordPage.tsx:63-69` | `handleLogout` calls `navigate('/login')` but setting `user=null` also triggers `<Navigate to="/login">`. Harmless but redundant. |
| L4 | **No Suspense boundary for lazy-loaded public routes** | `routes.tsx:83-85` | `/login`, `/register`, `/change-password` use `lazy()` but no `<Suspense>` fallback visible. React will throw if chunk isn't loaded. |
| L5 | **`_failedLoginTracker` grows unboundedly** | `AuthService.cs:29` | No eviction policy. Brute-force with many emails = unbounded memory growth. Invite tracker `.Clear()` resets everyone. |
| L6 | **Registration rate limit bypassed when `RemoteIpAddress` is null** | `AuthService.cs:590` | Returns `true` (allow) when IP is null. Behind certain proxies, IP can be null. |
| L7 | **No test coverage for forcePasswordChange in login response** | `AuthControllerTests.cs` | No tests verify `ForcePasswordChange` field in login/register/refresh responses or the redirect flow. |
| L8 | **JWT `force_password_change` claim not immediately enforced** | `AuthService.cs:640` | Claim baked into JWT at login/refresh. If admin sets flag on active user, not enforced until token refresh (up to 30min). |
| L9 | **No user feedback on logout failure** | `TopBar.tsx:97-101` | If logout API fails, client clears state silently. User thinks they're fully logged out but server session persists. |

## Verification
1. Login with `force_password_change='N'` → dashboard loads normally
2. Login with `force_password_change='Y'` → redirected to /change-password page
3. Change password on that page → redirected to login, flag cleared in DB
4. Login again → dashboard loads normally
5. Build succeeds, existing tests pass
