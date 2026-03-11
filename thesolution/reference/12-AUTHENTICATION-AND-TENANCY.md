# Authentication and Multi-Tenancy Reference

Quick reference for FedProspect's auth system and organization isolation model.

## Authentication Flow

**Login** (`POST /api/v1/auth/login`):
1. User submits email + password.
2. Server verifies password (bcrypt EnhancedHash), checks lockout/active status.
3. On success: generates JWT access token (30 min) + refresh token (7 days), creates `app_session` row with SHA-256 hashes of both tokens.
4. Sets three cookies: `access_token` (httpOnly, Secure, SameSite=Strict, path `/api`), `refresh_token` (httpOnly, Secure, SameSite=Strict, path `/api/v1/auth`), `XSRF-TOKEN` (readable by JS, for CSRF double-submit).
5. Response body returns `userId`, `userName`, `expiresAt` (no tokens in body).

**Token Refresh** (`POST /api/v1/auth/refresh`):
- Reads `refresh_token` cookie, finds matching session by hash.
- Rotates: old session revoked, new access + refresh tokens issued.
- Reuse detection: if a rotated refresh token is reused, ALL user sessions are revoked.

**Logout** (`POST /api/v1/auth/logout`):
- Revokes session in DB, clears all three cookies.

**Session Validation** (every authenticated request):
- `OnTokenValidated` JWT event extracts token, computes SHA-256 hash, calls `ValidateSessionAsync`.
- 30-second in-memory cache per session to reduce DB hits.
- In-memory revocation set provides instant invalidation (password change, admin deactivation).

**Registration** (`POST /api/v1/auth/register`):
- Invite-only. Requires a valid 64-char hex invite code matching the registrant's email.
- Creates user in the invite's organization with the invite's role.
- Auto-logs in on success (sets cookies).

## JWT Claims

| Claim | Value |
|-------|-------|
| `sub` | User ID (int) |
| `email` | User email |
| `name` | Display name |
| `role` | `admin` if IsOrgAdmin=Y, else `user` |
| `org_id` | Organization ID |
| `org_role` | `owner`, `admin`, or `member` |
| `is_system_admin` | `true` or `false` |
| `force_password_change` | `true` or `false` |
| `jti` | Unique token ID (GUID) |

## CSRF Protection

- **Middleware**: `CsrfMiddleware` runs on all POST/PUT/PATCH/DELETE requests.
- **Mechanism**: Double-submit cookie. JS reads `XSRF-TOKEN` cookie, sends it as `X-XSRF-TOKEN` header.
- **Exempt paths**: `/api/v1/auth/login`, `/api/v1/auth/register`, `/api/v1/auth/refresh` (no token exists yet).
- **Skipped for**: Bearer token auth (non-browser clients).

## Brute-Force Protections

| Protection | Threshold | Window |
|------------|-----------|--------|
| Account lockout | 5 failed logins | 30-minute lockout |
| Progressive delay | 3+ failures/email | 2-second delay per attempt (10-min window) |
| Registration rate limit | 3 attempts/IP | 1 minute |
| Invite code lockout | 5 failed attempts | Permanent until restart |
| Login global rate limit | 100 total/all IPs | 1 minute |

## Multi-Tenancy Model

Every user belongs to exactly one organization (`app_user.organization_id`). The `org_id` JWT claim is set at login and used by controllers to scope all queries.

**Organization Roles** (in `app_user.org_role`):

| Role | Capabilities |
|------|-------------|
| `owner` | Full org management, invite users, manage members, delete org |
| `admin` | Same as owner (both satisfy `OrgAdmin` policy) |
| `member` | Standard access, no org management |

**System Admin** (`app_user.is_system_admin`): Cross-org access to ETL status, system health, user management. Separate from org roles.

**Org Isolation Pattern**: Controllers call `GetCurrentOrganizationId()` or `ResolveOrganizationIdAsync()` from `ApiControllerBase`, then pass `orgId` to service methods which filter all queries by it. There is no global middleware for org filtering -- each service method applies it explicitly.

## Authorization Policies

| Policy | Requirement | Used By |
|--------|------------|---------|
| `OrgAdmin` | `org_role` is `owner` or `admin` | Org management endpoints |
| `SystemAdmin` | `is_system_admin` = `true` | ETL status, system admin endpoints |
| `AdminAccess` | OrgAdmin OR SystemAdmin | Admin controller (base policy) |

## Rate Limiting Policies

| Policy | Limit | Partition Key |
|--------|-------|--------------|
| `auth` | 10/min | IP address |
| `login_global` | 100/min | Global (all IPs) |
| `search` | 60/min | User ID (or IP) |
| `write` | 30/min | User ID (or IP) |
| `admin` | 30/min | User ID (or IP) |

## Key Tables

| Table | Purpose |
|-------|---------|
| `app_user` | User accounts. Links to org via `organization_id`. Stores password hash, lockout state, roles. |
| `organization` | Tenant. Has company profile fields, subscription tier, max users. |
| `app_session` | Active sessions. Stores access + refresh token hashes, expiry, revocation timestamp. |
| `organization_invite` | Pending invitations. 64-char hex code, email, role, expiry. |
| `activity_log` | Audit trail. Scoped to `organization_id`. Tracks login, logout, CRUD actions. |

## Key Files

| File | Purpose |
|------|---------|
| `api/src/FedProspector.Api/Controllers/AuthController.cs` | Login, logout, register, refresh, profile endpoints |
| `api/src/FedProspector.Infrastructure/Services/AuthService.cs` | Auth logic: password verify, JWT generation, session management |
| `api/src/FedProspector.Api/Middleware/CsrfMiddleware.cs` | CSRF double-submit validation |
| `api/src/FedProspector.Api/Middleware/ForcePasswordChangeMiddleware.cs` | Blocks non-auth requests if password change required |
| `api/src/FedProspector.Api/Middleware/SecurityHeadersMiddleware.cs` | Security response headers |
| `api/src/FedProspector.Api/Controllers/ApiControllerBase.cs` | `GetCurrentUserId()`, `GetCurrentOrganizationId()`, `ResolveOrganizationIdAsync()` |
| `api/src/FedProspector.Api/Controllers/OrganizationController.cs` | Org profile, members, invites, certs, NAICS management |
| `api/src/FedProspector.Api/Program.cs` | JWT config, authorization policies, rate limiting setup |
| `api/src/FedProspector.Core/Models/AppUser.cs` | User entity with org linkage and role fields |
| `api/src/FedProspector.Core/Models/Organization.cs` | Organization entity with company profile |
| `ui/src/auth/AuthContext.tsx` | Frontend auth state, login/logout/refresh calls |
