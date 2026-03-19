# Phase 150 — Security Hardening

## Status: DEFERRED — Pre-Production Only

---

## Context

This phase is intentionally deferred. The project is currently single-developer, single-machine local development. The security issues documented here are real but carry zero practical risk in that environment.

**Do not implement this phase until the system is being prepared for staging or production deployment.**

The following items are excluded from this phase and left as-is deliberately:
- `.env` file with API keys — local dev only, gitignored, acceptable for now
- `thesolution/credentials.yml` — local reference doc, gitignored, acceptable for now
- `appsettings.Development.json` with DB password — local dev config, not deployed

---

## Items to Address Before Production

### HIGH — Fix Before Any Shared Deployment

**H1 — `AllowedHosts: "*"` in production appsettings**
File: `api/src/FedProspector.Api/appsettings.json:41`
Set `AllowedHosts` to the explicit production domain(s). Wildcard allows Host header injection attacks.
```json
"AllowedHosts": "app.fedprospect.com;www.fedprospect.com"
```

**H2 — JWT Placeholder Secret Must Be Replaced**
File: `api/src/FedProspector.Api/appsettings.json`
The JWT secret `"CHANGE_THIS_TO_A_SECURE_KEY_AT_LEAST_32_CHARS_LONG"` is a known-public string. Anyone who knows this (or finds it in source control history) can forge valid JWTs. Add a startup assertion that fails fast if the placeholder is in use:
```csharp
var jwtSecret = builder.Configuration["Jwt:SecretKey"];
if (string.IsNullOrEmpty(jwtSecret) || jwtSecret.StartsWith("CHANGE_THIS"))
    throw new InvalidOperationException("JWT SecretKey must be set to a secure value before startup.");
```

**H3 — JWT Access Token Lifetime Config Is Ignored**
File: `api/src/FedProspector.Infrastructure/Services/AuthService.cs:39`
`AccessTokenLifetime = TimeSpan.FromMinutes(30)` is hardcoded. `appsettings.json` has `ExpirationHours: 24` which is never read. Wire the config value to the service via `IOptions<JwtOptions>` so operators can tune token lifetime without code changes.

**H4 — SAM.gov API Key in URL Query Parameters**
File: `fed_prospector/api_clients/base_client.py:183-185`
The API key is appended as `?api_key=SAM-...` in every request URL. URL query parameters appear in server access logs, proxy logs, and browser history. Check whether SAM.gov supports key-in-header authentication (e.g., `X-Api-Key` header) and switch to that if available.

**H5 — `SameSite=Lax` on Auth Cookies**
File: `api/src/FedProspector.Api/Controllers/AuthController.cs:212-216`
`SameSite=Lax` allows the `access_token` cookie to be sent on top-level cross-site GET navigations. Change to `SameSite=Strict` to prevent any cross-site cookie transmission:
```csharp
SameSite = SameSiteMode.Strict
```

---

### MEDIUM — Operational Security Improvements

**M1 — Enable MySQL TLS for Production Connections**
Files: `api/src/FedProspector.Api/appsettings.Development.json`, Python DB connection
The development MySQL connection string uses `SslMode=None`. Production should use `SslMode=Required`. The Python connection module should also be updated to pass SSL options from config.

**M2 — Email Address Not Logged on Failed Login**
File: `api/src/FedProspector.Infrastructure/Services/AuthService.cs:81`
`LogWarning("Login attempt for unknown email: {Email}", email)` logs the full email address. Replace with a hashed or masked version to protect PII in logs:
```csharp
var maskedEmail = email.Length > 3 ? email[..2] + "***" + email[email.IndexOf('@')..] : "***";
_logger.LogWarning("Login attempt for unknown email: {Email}", maskedEmail);
```

**M3 — Activity Log Stores Full Email Address**
File: `api/src/FedProspector.Infrastructure/Services/AuthService.cs:117`
`LogAsync(null, "LOGIN_FAILED", "USER", null, new { Email = email })` stores the full email in the `activity_log.details` JSON column — a durable PII record for every failed login, including non-existent accounts. Replace with a hashed identifier for correlation without PII retention.

**M4 — API Response Body Logged at ERROR Level**
File: `fed_prospector/api_clients/base_client.py:158`
`self.logger.error("Request failed: %d %s", response.status_code, response.text[:500])` logs up to 500 chars of API response bodies at ERROR level. Move to DEBUG level for production to avoid PII or sensitive data from error responses appearing in production logs.

**M5 — Distributed Rate Limiting for Auth Endpoints**
File: `api/src/FedProspector.Infrastructure/Services/AuthService.cs:28-36`
In-memory rate limiting (`_failedLoginTracker`, `_inviteFailedAttempts`, `_registerAttemptTracker`) resets on every app restart and is per-instance in multi-node deployments. Replace with Redis-backed distributed rate limiting before any horizontal scaling or container-based deployment.

---

### LOW — Pre-Launch Polish

**L1 — HANDOFF.md Should Be Gitignored or Removed**
File: `HANDOFF.md` (currently untracked)
This file is used for AI session handoffs and may contain architecture details not intended for long-term commit history. Either add it to `.gitignore` or clean up its content before committing.

**L2 — Pre-Commit Hook for Credential Pattern Detection**
Add a pre-commit hook that rejects commits containing patterns like `SAM-`, `fed_app_2026`, or `root_2026`. Even with `.gitignore` covering credential files, a developer could accidentally run `git add` in a way that bypasses the ignore rules.

```bash
# .git/hooks/pre-commit (or configure via pre-commit framework)
if git diff --cached | grep -E "SAM-[0-9a-f-]{36}|fed_app_2026|root_2026"; then
    echo "ERROR: Potential credential in staged changes. Review before committing."
    exit 1
fi
```

---

## Trigger Checklist

Before deploying to any shared environment (staging, cloud, team access), verify all items above are addressed:

- [ ] H1: `AllowedHosts` set to explicit domain
- [ ] H2: JWT secret replaced and startup assertion added
- [ ] H3: JWT expiry wired to config
- [ ] H4: SAM.gov API key delivery method reviewed (URL vs header)
- [ ] H5: `SameSite=Strict` on auth cookies
- [ ] M1: MySQL TLS enabled
- [ ] M2: Email masking in failed login log
- [ ] M3: Activity log email hashing
- [ ] M4: API response body at DEBUG not ERROR
- [ ] M5: Distributed rate limiting in place

Also re-verify: API keys rotated (Phase 14.x review found them in local files), DB password removed from `appsettings.Development.json`, no credentials in git history (`git log -p | grep -E "SAM-|fed_app"`).
