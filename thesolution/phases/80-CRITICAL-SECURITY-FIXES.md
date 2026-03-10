# Phase 80 — Critical Security Fixes

## Status: PLANNED

**Priority**: IMMEDIATE — must be completed before any shared/production deployment
**Depends on**: None
**Overlaps**: Phase 100 (Security Hardening) — Phase 80 covers the subset of security issues that are critical and should not be deferred.

---

## Overview

Comprehensive project review identified hardcoded credentials, authentication vulnerabilities, and cookie security issues that represent immediate security risks. These items were found across multiple layers (Python service manager, C# API configuration, React UI auth flow).

---

## Issues

### CRITICAL

**80-1 — Hardcoded Database Root Password in Service Manager**
File: `fed_prospector.py` line 36
Issue: `MYSQL_ROOT_PASS = "root_2026"` is hardcoded in the repository.
OWASP: A02:2021 – Cryptographic Failures
Fix: Move to `.env` file; reference via `os.getenv('MYSQL_ROOT_PASS')`. Add to `.env.example` with placeholder.

**80-2 — Plaintext JWT Secret in appsettings.json**
File: `api/src/FedProspector.Api/appsettings.json` line 6
Issue: JWT secret hardcoded as `"CHANGE_ME_TO_A_SECURE_KEY_AT_LEAST_32_CHARS_LONG"`. Runtime guard exists in Program.cs:301-305 but the value is committed to Git.
OWASP: A02:2021, A07:2021
Fix: Remove from appsettings.json entirely; require environment variable `JWT_SECRET`. Keep runtime guard as defense-in-depth.

**80-3 — Plaintext Database Password in Development Config**
File: `api/src/FedProspector.Api/appsettings.Development.json` line 3
Issue: Database password hardcoded as `"fed_app_2026"` in development config committed to Git.
OWASP: A02:2021
Fix: Use environment variables for connection string components. Provide `.env.local` template (gitignored).

**80-4 — credentials.yml Contains Real-Format Credentials in VCS**
File: `thesolution/credentials.yml`
Issue: Contains SAM.gov API key (UUID format), MySQL root password, app password — all plaintext, in git history. Header says "NOT for production" but file is not gitignored.
Fix:
1. Rename to `credentials.example.yml` with masked values (e.g., `SAM-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx`)
2. Add `thesolution/credentials.yml` to `.gitignore`
3. Update CLAUDE.md reference from `credentials.yml` to `credentials.example.yml`

---

### HIGH

**80-5 — Auth Refresh Loop Vulnerability**
File: `ui/src/api/client.ts` lines 68-90
Issue: If `/auth/refresh` endpoint continuously returns 401, the code redirects to login repeatedly without breaking the cycle. Could cause infinite redirect loop.
Fix: Add max retry counter (e.g., 3 attempts) before redirecting to login. Reset counter on successful auth.

**80-6 — Session Refresh Race Condition (Multi-Tab)**
File: `ui/src/api/client.ts` lines 25-40
Issue: Global `isRefreshing` and `failedQueue` use module-level state that can be corrupted if multiple 401s occur across browser tabs/windows.
Fix: Use sessionStorage or BroadcastChannel API to coordinate refresh across tabs. Implement per-request lock pattern.

**80-7 — Refresh Token Cookie Path Too Restrictive**
File: `api/src/FedProspector.Api/Controllers/AuthController.cs` lines 231-237
Issue: `refresh_token` cookie set with `Path = "/api/v1/auth/refresh"`. If path changes or other endpoints need the token, cookie won't be sent.
Fix: Change to `Path = "/api/v1/auth"` or `/api` for broader but still scoped access.

**80-8 — Inconsistent Cookie Paths (Access vs XSRF)**
File: `api/src/FedProspector.Api/Controllers/AuthController.cs` lines 219-237
Issue: `access_token` path = `/api`, `refresh_token` path = `/api/v1/auth/refresh`, `XSRF-TOKEN` path = `/`. Three different scopes create confusion and potential cookie loss.
Fix: Standardize: access_token → `/api`, refresh_token → `/api`, XSRF-TOKEN → `/` (needs to be readable by JS).

---

### MEDIUM

**80-9 — CSRF Token Missing Error Not Handled**
File: `ui/src/api/client.ts` lines 13-22
Issue: If XSRF-TOKEN cookie is not found, requests proceed without the token header. No warning or fallback.
Fix: Log warning when CSRF token not found. Consider retry strategy or user notification.

**80-10 — Missing AllowAnonymous on Market Share Endpoint**
File: `api/src/FedProspector.Api/Controllers/AwardsController.cs` line 34
Issue: `GetMarketShare` endpoint marked `[AllowAnonymous]` but queries data that should be organization-scoped.
Fix: Remove `[AllowAnonymous]` and add `[Authorize]`. Pass organization ID from auth context.

---

## Verification

1. `grep -r "root_2026\|fed_app_2026\|CHANGE_ME" --include="*.py" --include="*.json" --include="*.yml"` returns zero matches (excluding .example files)
2. `credentials.yml` is in `.gitignore`
3. Auth refresh loop test: rapidly expire token, verify max 3 retries then redirect
4. Cookie paths consistent across all Set-Cookie headers
5. Market share endpoint returns 401 for unauthenticated requests

---

## Relationship to Phase 100

Phase 100 (Security Hardening) covers MEDIUM/LOW items like MySQL TLS, email masking in logs, distributed rate limiting. Phase 80 covers the CRITICAL/HIGH items that should be fixed first regardless of deployment timeline.
