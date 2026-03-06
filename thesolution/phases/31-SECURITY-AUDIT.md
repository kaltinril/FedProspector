# Phase 31 -- Security Audit

## Status: COMPLETE (audit) / IN PROGRESS (remediation)

Performed: 2026-03-05
Scope: Full white-hat security review of C# API, Python ETL, React UI

---

## Executive Summary

FedProspect has a mature security architecture for a pre-production app. Cookie auth (HttpOnly, Secure, SameSite=Strict), CSRF double-submit, BCrypt hashing, session revocation, refresh token rotation with reuse detection, and consistent multi-tenant org isolation are all well-implemented. The main gaps are in-memory security state lost on restart, credential exposure in committed config files, and a few authorization edge cases.

## Finding Summary

| Severity | Count | Fix Now | Fix Before Production |
|----------|-------|---------|-----------------------|
| CRITICAL | 1 | -- | 1 |
| HIGH | 3 | 2 | 1 |
| MEDIUM | 6 | 1 | 5 |
| LOW | 5 | 1 | 4 |
| INFO | 4 | -- | -- |
| **Total** | **19** | **4** | **11** |

Items marked "Fix Now" affect current development. Items marked "Fix Before Production" are tracked in Phase 80.

---

## Fix Now (development blockers or functional bugs)

### WHR-004 [HIGH] Admin Can See System-Wide ETL Status

**Location**: `api/src/FedProspector.Api/Controllers/AdminController.cs`

`GetEtlStatus` is accessible to any org admin, but contains system-wide operational data. Should require system-admin claim.

**Fix**: Add `[Authorize(Policy = "SystemAdmin")]` or check `User.HasClaim("is_system_admin", "true")` on `GetEtlStatus`.

---

### WHR-015 [LOW] Admin Password Reset Returns No Temporary Password

**Location**: `api/src/FedProspector.Infrastructure/Services/AdminService.cs:183-208`

`ResetPasswordAsync` generates a temporary password and hashes it, but the response DTO intentionally omits it. The admin is told "provide temporary credentials securely" but has no way to know what they are. Feature is non-functional.

**Fix**: Either return the temporary password in the response (one-time), send it via email, or generate a time-limited reset link instead.

---

### WHR-017 [INFO/BUG] CORS Missing PUT Method

**Location**: `api/src/FedProspector.Api/Program.cs:154`

`.WithMethods("GET", "POST", "DELETE", "PATCH")` is missing `"PUT"`. The `OrganizationController` uses PUT for profile, NAICS, and certifications updates. These will fail with CORS preflight errors in the browser.

**Fix**: Add `"PUT"` to the `.WithMethods()` list.

---

### WHR-010 [MEDIUM] Unbounded In-Memory Dictionaries (DoS)

**Location**: `api/src/FedProspector.Infrastructure/Services/AuthService.cs:31-32`

`_inviteFailedAttempts` grows without bound -- entries added on every failed invite code but never evicted. Attacker can exhaust memory with random invite codes.

**Fix**: Switch to `IMemoryCache` with sliding expiration, or add a max-size eviction policy. Validate invite code format (64 hex chars) before tracking.

---

## Fix Before Production (Phase 80)

These findings are real but carry minimal risk in local single-developer environment. Merged into Phase 80.

### WHR-001 [CRITICAL] API Keys in credentials.yml

**Location**: `thesolution/credentials.yml:16`

Live SAM.gov API key in file. Currently gitignored but exists locally. Verify via `git log` it was never committed to history. If it was, rotate keys and use `git filter-repo` to purge.

*Already tracked in Phase 80.*

### WHR-002 [HIGH] DB Credentials in appsettings.Development.json

**Location**: `api/src/FedProspector.Api/appsettings.Development.json:3`

Connection string with plaintext password committed to git. Move to `dotnet user-secrets` or env vars before any shared deployment.

*Already tracked in Phase 80.*

### WHR-003 [HIGH] In-Memory Brute-Force Tracking Lost on Restart

**Location**: `api/src/FedProspector.Infrastructure/Services/AuthService.cs:28-46`

Four `static ConcurrentDictionary` instances (`_failedLoginTracker`, `_inviteFailedAttempts`, `_registerAttemptTracker`, `_revokedUsers`) are lost on app restart. Brute-force counters reset, revoked sessions may briefly work within the 30-second cache TTL.

**Fix**: Move to Redis or database-backed distributed cache before production.

### WHR-005 [MEDIUM] User Email Logged on Failed Login

**Location**: `api/src/FedProspector.Infrastructure/Services/AuthService.cs:80`

User-supplied email logged verbatim. Potential PII in logs. Log only a prefix or hash.

### WHR-006 [MEDIUM] Password Policy Lacks Common-Password Blocklist

**Location**: `api/src/FedProspector.Core/Validators/RegisterRequestValidator.cs:22-28`

Requires 8+ chars, upper, lower, digit. No special char requirement, no check against common passwords. "Password1" passes.

**Fix**: Add top-10K common password blocklist or integrate HaveIBeenPwned Passwords API (k-anonymity model).

### WHR-007 [MEDIUM] CSRF Token Not Bound to Session

**Location**: `api/src/FedProspector.Api/Middleware/CsrfMiddleware.cs:60-65`

Double-submit token is a random value, not cryptographically tied to the user's session. If an attacker can set cookies on the domain (e.g., subdomain XSS), they can forge both cookie and header. Mitigated by SameSite=Strict.

**Fix**: Bind token via `HMAC-SHA256(session_id, server_secret)`.

### WHR-008 [MEDIUM] Secure Cookies Over HTTP in Dev

**Location**: `api/src/FedProspector.Api/Program.cs:320-323`

All cookies set `Secure=true`. Works on localhost due to browser exemptions. Will fail on HTTP staging environments.

**Fix**: Document HTTPS requirement. Consider `Secure = !isDevelopment` for dev-only.

### WHR-009 [MEDIUM] SQL Table Name Interpolation in Python Bulk Loader

**Location**: `fed_prospector/etl/bulk_loader.py:395,462-468`

f-string table names in SQL (`TRUNCATE TABLE {table_name}`). Currently safe (hardcoded inputs), but dangerous pattern if copied. Quote identifiers with backticks.

### WHR-011 [LOW] HTML Allowed in DisplayName

**Location**: `api/src/FedProspector.Core/Validators/RegisterRequestValidator.cs:29-31`

Display name allows `<script>` tags. React auto-escapes, but if rendered in emails or CSV exports, stored XSS results.

**Fix**: Add `.Matches(@"^[^<>]+$")` to validator.

### WHR-013 [LOW] Registration TOCTOU Race Condition

**Location**: `api/src/FedProspector.Infrastructure/Services/AuthService.cs:258-274`

Email/username uniqueness checked before insert. Concurrent requests could duplicate. DB UNIQUE constraint prevents data corruption but results in 500 instead of friendly error.

**Fix**: Catch `DbUpdateException` with duplicate key and return 400.

### WHR-014 [LOW] ForcePasswordChange JWT Claim Lifetime

**Location**: `api/src/FedProspector.Api/Middleware/ForcePasswordChangeMiddleware.cs:18`

If admin sets force-password-change without revoking sessions, the existing JWT won't enforce it until token expires (30 min). Current admin reset flow already revokes sessions, so this is a defense-in-depth gap only.

---

## Positive Observations

1. **Cookie security**: HttpOnly, Secure, SameSite=Strict on all auth cookies. Path-scoped access and refresh tokens.
2. **Session management**: Server-side session tracking, refresh token rotation, reuse detection that revokes ALL sessions.
3. **Multi-tenant isolation**: Consistent org_id scoping via JWT claims across all controllers.
4. **No raw SQL with user input in C# API**: All queries use EF Core LINQ or parameterized `SqlQueryRaw`.
5. **FluentValidation on all DTOs**: Length limits, format checks, allowed-value restrictions.
6. **Security headers**: X-Content-Type-Options, X-Frame-Options, CSP, Referrer-Policy, Permissions-Policy, HSTS (production).
7. **Rate limiting**: Auth (10/min/IP), global login (100/min), search (60/min/user), write (30/min/user), admin (30/min/user).
8. **Exception handler**: Never leaks stack traces or internal details.
9. **JWT startup guard**: Production rejects weak/default keys.
10. **Invite-only registration**: Prevents open account creation.

---

## Remediation Tracking

| ID | Severity | Description | Status |
|----|----------|-------------|--------|
| WHR-001 | CRITICAL | API keys in credentials.yml | Phase 80 |
| WHR-002 | HIGH | DB creds in appsettings.Development.json | Phase 80 |
| WHR-003 | HIGH | In-memory security state lost on restart | Phase 80 |
| WHR-004 | HIGH | Admin ETL status not system-admin scoped | DONE |
| WHR-005 | MEDIUM | Email logged on failed login | Phase 80 |
| WHR-006 | MEDIUM | No common-password blocklist | Phase 80 |
| WHR-007 | MEDIUM | CSRF token not session-bound | Phase 80 |
| WHR-008 | MEDIUM | Secure cookies over HTTP in dev | Phase 80 |
| WHR-009 | MEDIUM | SQL table name interpolation in Python | Phase 80 |
| WHR-010 | MEDIUM | Unbounded in-memory dictionaries | DONE |
| WHR-011 | LOW | HTML in DisplayName | Phase 80 |
| WHR-012 | LOW | Awards/Entities not org-scoped (public data) | Won't fix |
| WHR-013 | LOW | Registration TOCTOU race | Phase 80 |
| WHR-014 | LOW | ForcePasswordChange JWT lifetime | Phase 80 |
| WHR-015 | LOW | Admin reset returns no temp password | DONE |
| WHR-016 | INFO | Swagger in dev only | No action |
| WHR-017 | INFO | CORS missing PUT method | DONE |
| WHR-018 | INFO | Dev JWT key in source | No action |
| WHR-019 | INFO | AllowedHosts=localhost | Phase 80 |
