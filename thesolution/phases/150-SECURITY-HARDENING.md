# Phase 150 — Security Hardening

## Status: ACTIVE — Production Is Internet-Exposed

> **This doc was re-audited 2026-06-01** by a multi-angle security review (auth/session,
> injection/IDOR, UI/frontend, infra/deploy/secrets) against the current codebase.
> The previous version (last touched 2026-03-18) assumed *"single-developer, single-machine
> local development… zero practical risk"* and was marked **DEFERRED — Pre-Production Only.**
>
> **That premise is obsolete.** Per [completed/135-PUBLIC-INTERNET-EXPOSURE.md](completed/135-PUBLIC-INTERNET-EXPOSURE.md)
> the app is now **publicly internet-exposed** (port-forwarded HTTPS on 5056, self-signed cert,
> prod box `192.168.0.137`). The trigger condition this phase named — *"before deploying to any
> shared environment"* — **has already occurred.** Several in-code comments
> (`AuthService.cs`, `Program.cs:254`) literally say *"REVISIT … if the API is ever exposed to
> the public internet"* — it is. This phase is now live-fire, not deferred.

---

## How To Use This Doc

Findings are grouped by **what to do with them**, not just severity, so the right work is easy to find:

| Section | Meaning |
|---------|---------|
| 🔴 **A — Critical / Scary** | Real exposure on the public surface. Address now, even if some are also quick. |
| 🟢 **B — Quick Wins** | Low effort, low risk, good hygiene. Knock these out in a batch. |
| 🟡 **C — Verify / Operational** | Not necessarily a code bug — needs the operator to confirm a prod setting or network fact. Some could be Critical *if* the answer is bad. |
| 🔵 **D — Later / Low Bang-for-Buck** | Real but hard, marginal, or only matters under future conditions (scaling, etc.). Deferred **deliberately** — flagged so they aren't forgotten or done prematurely. |
| ✅ **E — Already Done** | Verified fixed in current code since the last version of this doc. Kept for the audit trail. |

Each item carries: **Severity** · **Effort** (Quick win / Moderate / Hard) · **Bang-for-buck** · file:line · a fix · and a **Usability note** — because the goal is *secure **and** usable*, not "unplug it."

**Still excluded deliberately** (local-dev only, gitignored, not deployed): `fed_prospector/.env`,
`thesolution/credentials.yml`, dev `appsettings.Development.json`. These are acceptable as-is —
but see **A3 / C2** about the same DB password having leaked into **git history**.

---

## 🔴 A — Critical / Scary (address now)

### A1 — Application rate limiting is globally DISABLED on a public endpoint
- **Severity: HIGH · Effort: Quick win · Bang-for-buck: HIGH** — *the single most important item in this doc.*
- **File:** `api/src/FedProspector.Api/Program.cs:254-329` — every policy (`auth`, `login_global`, `search`, `write`, `admin`) sets `PermitLimit = int.MaxValue`. Also `AuthService.cs:43` `MaxInviteAttempts = int.MaxValue` and `AuthService.cs:51` `MaxRegisterAttemptsPerMinute = int.MaxValue`. The block comment at `Program.cs:254-261` explicitly defers this *"if the API is ever exposed to the public internet"* — now true.
- **Why it's scary:** Unlimited credential-stuffing / brute-force on `POST /auth/login` and `/register`, and unthrottled scraping of expensive search / pricing / **AI** endpoints (DoS + cost amplification). The only surviving brake is `LoginThrottleService` (in-memory, login-only, 10 fails / 15 min / IP) + DB-backed per-account lockout.
- **Fix:** Re-enable finite limits — the infrastructure is already wired, only the numbers change. Suggested: `auth`/`login_global` 10/min/IP, `write` 60/min/user, `register` 5–10/min/IP. Restore `MaxRegisterAttemptsPerMinute` to a real value.
- **Usability:** Keep `search` **generous** (the old 1000/min was what bounced real users to `/login` with 429s). Tune for anti-abuse, not for throttling the handful of real users. Net usability impact ≈ zero if `search` stays high.

### A2 — Cross-org IDOR: auto-prospect generation trusts a body-supplied `OrganizationId`
- **Severity: Medium-High · Effort: Quick win · Bang-for-buck: High**
- **File:** `api/src/FedProspector.Api/Controllers/ProspectsController.cs:217-225` — `AutoGenerate` does `var orgId = request?.OrganizationId ?? (await ResolveOrganizationIdAsync())`. The `[Authorize(Policy="OrgAdmin")]` check only proves the caller is *an* org admin, not that they admin *that* org. `AutoProspectService.GenerateAutoProspectsAsync(orgId)` does not re-verify ownership.
- **Why it matters:** An admin of Org A can pass Org B's id and trigger prospect generation + notifications **inside another tenant** (cross-tenant write / nuisance / probing). This is the **only** IDOR found — multi-tenant scoping is otherwise consistently enforced (see E).
- **Fix:** Ignore `request.OrganizationId`; always use `ResolveOrganizationIdAsync()`. (If a system-admin override is ever intended, gate the body value behind a `SystemAdmin` policy.)
- **Usability:** None — the UI already calls this for the caller's own org.

### A3 — DB & root passwords (`fed_app_2026`, `root_2026`) live in git history
- **Severity: HIGH · Effort: Moderate · Bang-for-buck: High**
- **Evidence:** `git log -p api/src/FedProspector.Api/appsettings.Development.json` shows `Password=fed_app_2026` in historical commits (removed in Phase 80, commit `b7103d0`). `root_2026` is referenced in `completed/66B-MYSQL-NVME-MIGRATION.md` and `completed/80-CRITICAL-SECURITY-FIXES.md`. **Working tree is clean** — this is history only.
- **Why it matters now:** The same DB now sits behind an internet-exposed app. Anyone who obtains the repo recovers a credential that may still be live. The old doc's "no credentials in git history" final check is **not** satisfied.
- **Fix (do the cheap one):** **Rotate** the `fed_app` and MySQL `root` passwords if not already rotated post-exposure — see **C2**. The external-config architecture makes rotation a one-file edit + restart. A history rewrite (BFG/`git filter-repo`) is *optional* once rotated; rotation is the real fix.
- **Usability:** None — touches only `C:\fedprospector\config\fedprospector.local.json` and dev `appsettings.Local.json`.

### A4 — `axios` HIGH-severity npm advisory in the shipped UI bundle
- **Severity: High · Effort: Quick win · Bang-for-buck: High**
- **Evidence:** `npm audit --omit=dev` in `ui/` flags axios HIGH — incl. GHSA-w9j2-pvgh-6h63 (auth-bypass via prototype pollution in `validateStatus` merge), GHSA-3w6x-2g7m-8v23 (JSON response tampering), GHSA-xx6v-rp6x-q39c (XSRF-token cross-origin leakage). `ui/package.json` pins `"axios": "^1.15.0"`. Axios carries **all** authenticated, credentialed API calls, so the browser-relevant ones (response tampering, XSRF-token leakage) matter directly.
- **Fix:** `npm audit fix` (patch-level bump to 1.15.x+), then re-run `npm audit --omit=dev` to confirm clean. Verify the CSRF interceptor in `ui/src/api/client.ts` still attaches `X-XSRF-TOKEN` after the bump. Add `npm audit --omit=dev` to CI to catch the next one.
- **Usability:** None — patch bump, no API change expected.

---

## 🟢 B — Quick Wins (batch these)

### B1 — `javascript:`/`data:` URI XSS via server-supplied `href` (UI)
- **Severity: Medium · Effort: Quick win · Bang-for-buck: High**
- **Files:** server-sourced URLs rendered straight into `<Link href={…}>` without scheme validation: `ui/src/components/shared/ExternalLink.tsx:13`, `OpportunityDetailPage.tsx:211,471`, `DocumentIntelligenceTab.tsx:966`, `AwardDetailPage.tsx:387`, `EntityDetailPage.tsx:105`, `EntitySearchPage.tsx:82`, `CompetitorDossierPage.tsx:55`, `ProspectDetailPage.tsx:222,782`. React escapes text but **not** `href`; a feed value like `javascript:…` executes on click. Strict CSP (`script-src 'self'`) blocks injected `<script>` but is a gray area for inline `javascript:` handlers.
- **Fix:** Add a `safeUrl()` guard (allow only `http:`/`https:`/`mailto:`) and route every external link through `ExternalLink.tsx`. The project already ships `dompurify` and has an **unused** `ui/src/utils/sanitize.ts` — extend that (see B12) so it earns its place.
- **Usability:** Zero — legitimate links unaffected; only hostile schemes neutralized.

### B2 — Email PII logged on failed login (was M2 / M3)
- **Severity: Low-Medium · Effort: Quick win · Bang-for-buck: Medium**
- **Files:** `AuthService.cs:99` `LogWarning("Login attempt for unknown email: {Email}", email)` and `AuthService.cs:138` `LogAsync(…, new { Email = email })` — the latter persists the full email into the durable `activity_log.details` column for failed attempts (now arriving from the public internet).
- **Fix:** Mask/hash the email (e.g. `ab***@domain`) — admins keep correlation, PII isn't retained.
- **Usability:** None.

### B3 — Vendor API response body logged at ERROR level (was M4)
- **Severity: Low · Effort: Quick win · Bang-for-buck: Low**
- **File:** `fed_prospector/api_clients/base_client.py:267-269` logs `error_text[:2000]` at **ERROR** (the old doc said 500 chars at line 158 — it's now **2000**, and a full-body DEBUG line was added at `:264-266`; the M4 intent of "move to DEBUG" was never applied). Local ETL logs only — not attacker-reachable.
- **Fix:** Keep the DEBUG full-body line; drop the body from the ERROR line (log status + URL path without query string, so the SAM key in the query can't land there either).
- **Usability:** None.

### B4 — Runbook tells operators to set `AllowedHosts="*"`
- **Severity: Medium · Effort: Quick win · Bang-for-buck: Medium**
- **Evidence:** committed `appsettings.json:43` is now safe (`"localhost"`, see E), and the cert script writes explicit SANs — **but** `thesolution/reference/14-PRODUCTION-EXPOSURE.md:111` advises `AllowedHosts="*"` as a fix for HTTP 400 host errors, which re-opens Host-header injection on the public endpoint.
- **Fix:** Remove the wildcard suggestion from the runbook; the correct fix (re-run the cert script with the right `-DnsName`) is already in the same table.
- **Usability:** None — the cert-script path solves the 400 cleanly.

### B5 — CORS silently falls back to `http://localhost:5173` if prod config is unset
- **Severity: Low · Effort: Quick win · Bang-for-buck: Medium**
- **File:** `Program.cs:236-251` — explicit origins + `AllowCredentials()` (correct, no `AllowAnyOrigin`), but if the external config omits `Cors:AllowedOrigins` it logs a warning and **proceeds** with the localhost default.
- **Fix:** In Production, **fail fast** (throw) when `Cors:AllowedOrigins` is unset rather than defaulting. (Single-port deploy is same-origin so this mostly fails closed, but a credentialed localhost origin is undesirable.)
- **Usability:** None for end users; an ops guardrail.

### B6 — Kestrel has no request timeouts / connection caps (DoS surface)
- **Severity: Medium · Effort: Quick win · Bang-for-buck: Medium**
- **File:** `Program.cs:49-53` sets `MaxRequestBodySize = 10 MB` (good) but no `KestrelServerLimits` for `MaxConcurrentConnections`, `RequestHeadersTimeout`, `KeepAliveTimeout`. Defaults leave slowloris / connection-exhaustion partly open on a public port.
- **Fix:** Set `MaxConcurrentConnections`, tighten `RequestHeadersTimeout` (~30s), keep `MinRequestBodyDataRate` on. (A reverse proxy — IIS/nginx/Cloudflare — would add richer controls; see D-cert note.)
- **Usability:** Limits sized for a few users are invisible to legitimate use.

### B7 — Strip `console.*` from the prod bundle
- **Severity: Low · Effort: Quick win · Bang-for-buck: Low**
- **File:** `ui/src/pages/opportunities/OpportunitySearchPage.tsx:316` logs user filter values; likely others. No secrets, but debug noise in the prod console.
- **Fix:** Add Vite `esbuild: { drop: ['console','debugger'] }` (or terser `drop_console`) to the prod build, and remove the stray log.
- **Usability:** None.

### B8 — `X-Api-Version: 1.0` response header (tech fingerprinting)
- **Severity: Low · Effort: Quick win · Bang-for-buck: Low**
- **File:** `api/src/FedProspector.Api/Middleware/SecurityHeadersMiddleware.cs:16`. Minor info disclosure.
- **Fix:** Drop it, or gate to Development.
- **Usability:** None.

### B9 — Unbounded `days` query param on admin analytics
- **Severity: Low · Effort: Quick win · Bang-for-buck: Low**
- **File:** `AdminController.cs:43,57,92` (`days` on load-history / health-snapshots / ai-usage) reaches service queries with no upper clamp (page/pageSize *are* clamped at `AdminService.cs:241`). Admin-gated mild DoS amplification.
- **Fix:** Clamp `days` to a sane max (e.g. 365) in the services.
- **Usability:** None at realistic values.

### B10 — No pre-commit hook for credential patterns (was L2)
- **Severity: Low · Effort: Quick win · Bang-for-buck: Medium**
- **Evidence:** `.git/hooks/` has only samples; no `.pre-commit-config.yaml`. `.gitignore` coverage is solid, but `appsettings.Development.json` is intentionally **tracked** and has leaked a real password before (A3) — exactly what this hook guards.
- **Fix:** Add the hook (snippet below) rejecting staged `SAM-…`, `fed_app_2026`, `root_2026`, etc.
  ```bash
  # .git/hooks/pre-commit
  if git diff --cached | grep -E "SAM-[0-9a-f-]{36}|fed_app_2026|root_2026"; then
      echo "ERROR: Potential credential in staged changes."; exit 1
  fi
  ```
- **Usability:** Zero friction for normal commits.

### B11 — JWT access/refresh lifetimes are hardcoded (was H3 — reframed)
- **Severity: Low · Effort: Moderate · Bang-for-buck: Low**
- **File:** `AuthService.cs:55-56` hardcode `AccessTokenLifetime = 30 min`, `RefreshTokenLifetime = 30 days`. **The old H3 claim is now stale:** there is no `Jwt:ExpirationHours` config being "ignored" — it doesn't exist. So this is simply "lifetimes aren't tunable without a recompile." (Also: the inline comment at `AuthService.cs:155` says "7 days" but the value is 30 — fix the comment.)
- **Fix:** Optionally wire lifetimes through `IOptions<JwtOptions>` so operators can tune without code changes.
- **Usability:** None.

### B12 — Unused `sanitize.ts` / dead DOMPurify dependency
- **Severity: Low (Info) · Effort: Quick win · Bang-for-buck: Medium**
- **File:** `ui/src/utils/sanitize.ts` (`sanitizeHtml()`, **zero call sites**). Not a vuln today (nothing renders raw HTML), but an unused sanitizer is a footgun. **Best move:** repurpose it as the B1 `safeUrl()` chokepoint so `dompurify` earns its keep.
- **Usability:** None.

---

## 🟡 C — Verify / Operational (confirm with the operator)

> These aren't necessarily code bugs — they depend on prod settings / network facts not visible
> from the repo. **C1 could be Critical if the answer is bad.** Resolve these before signing off.

### C1 — Is MySQL `192.168.0.137:3306` reachable from the internet?
- **Severity: Critical *if* exposed, else N/A · Effort: Quick win (verify)**
- Only TCP **5056** is documented as port-forwarded (`open-firewall.ps1`, runbook step 5). Could not determine whether **3306** is also forwarded. If 3306 is internet-reachable, then `SslMode=None` (D3) + the history-leaked `fed_app_2026` (A3) become a **Critical** combo.
- **Action:** Confirm the router has **no** port-forward to 3306 and the Windows firewall blocks inbound 3306 from WAN. Expected answer: LAN-only. Document the result here.

### C2 — Were DB + JWT secrets rotated after going public?
- **Severity: High (governance) · Effort: Quick win (verify) / Moderate (rotate)**
- Ties to A3. No secret-rotation mechanism exists; JWT secret (`.env`), DB password (external config), PFX password (external config) are all static. Confirm a **one-time rotation** of DB + JWT secrets happened post-exposure; if not, do it (cheap via external config).
- **Action:** Verify and record. Rotate if unconfirmed.

### C3 — Confirm prod `AllowedHosts` is the real hostname/IP
- **Severity: Medium · Effort: Quick win (verify)**
- Committed value is `"localhost"` (`appsettings.json:43`); prod must override via `C:\fedprospector\config\fedprospector.local.json` (outside repo, not auditable here). If unset, legit traffic is rejected; if `"*"`, Host-header injection is open.
- **Action:** Confirm the external config sets the explicit public host(s).

---

## 🔵 D — Later / Low Bang-for-Buck (deliberately deferred)

> Real, but hard / marginal / only relevant under future conditions. Flagged so they're not
> forgotten — and not done prematurely either.

### D-cert — Self-signed cert → trusted cert *(recommended; moderate effort, also a usability win)*
- **Severity: Medium · Effort: Moderate · Bang-for-buck: Medium-High**
- `scripts/generate-selfsigned-cert.ps1` issues a self-signed cert. TLS encrypts but **does not authenticate server identity** — users are trained to click through warnings, so a MITM presenting any cert is indistinguishable, and HSTS can't engage on an untrusted cert. *(Not strictly "low BFB" — listed here because it's the moderate-effort item; do it when convenient.)*
- **Fix (usability-preserving options):** (a) Let's Encrypt via DNS-01 if a hostname exists; (b) Cloudflare Tunnel / reverse proxy terminating a trusted cert (also adds DoS controls, see B6); (c) at minimum, distribute the self-signed cert to the few users' trust stores so warnings disappear and HSTS engages.
- **Usability:** A trusted cert **removes** the browser warning — a security *and* usability win.

### D1 — Distributed (Redis) rate limiting (was M5)
- **Severity: Low (now) · Effort: Hard · Bang-for-buck: Low** — only matters under horizontal scaling / multi-node. In-memory trackers (`AuthService.cs:37,46,52`) reset on restart and are per-instance. Fine for the current single node; DB-backed account lockout already survives restarts. **Defer until multi-node.** (Note: A1 is the urgent rate-limit item, not this.)

### D3 — MySQL TLS for the dev→prod LAN hop (was M1)
- **Severity: Medium · Effort: Moderate · Bang-for-buck: Medium** — `SslMode=None` in `appsettings.Development.json:3` and Python `fed_prospector/db/connection.py` (no SSL params). Prod app→DB is loopback (low risk), but the **dev box → prod `192.168.0.137`** path is plaintext creds+data over the LAN. Set `SslMode=Required` for the cross-machine path and add SSL options to the Python connector. (Loopback can stay `None`.) Gated on C1.

### D4 — SAM.gov API key in URL query string (was H4)
- **Severity: Low · Effort: Moderate · Bang-for-buck: Low** — `base_client.py:293-294,324-325` append `?api_key=…`. This is **outbound Vendor-API** traffic from the ETL box, **not** the internet-exposed App API, so exposure doesn't change the risk. Key lands in SAM-side/proxy logs. Check whether SAM supports `X-Api-Key` header auth per endpoint; if not, mark **accepted / won't-fix**.

### D5 — CSP `style-src 'unsafe-inline'`
- **Severity: Low · Effort: Hard · Bang-for-buck: Low** — `SecurityHeadersMiddleware.cs:18`. Required by MUI/Emotion runtime styles. `script-src` is correctly `'self'` (the part that matters for XSS). Removing `unsafe-inline` needs an Emotion nonce setup + visual QA. **Accept for now; document rationale inline.** ⚠️ Do **not** strip it without the nonce work — it will break MUI styling.

### D6 — PFX password stored plaintext in external config
- **Severity: Low · Effort: Moderate · Bang-for-buck: Low** — `generate-selfsigned-cert.ps1:240-244` writes the PFX password into `fedprospector.local.json`. File is outside the repo / never deployed, so local-only. Harden via NTFS ACLs on `C:\fedprospector\config` + `\certs`, or load from the Windows cert store. Don't break the idempotent re-run flow.

### D7 — Pin Kestrel TLS version (`Tls12 | Tls13`)
- **Severity: Low · Effort: Quick win · Bang-for-buck: Low** — no `SslProtocols` pin (`Program.cs:49-53`); relies on Schannel defaults. Modern Windows defaults are fine, so low priority; pin in `ConfigureHttpsDefaults` if the host OS might lag.

### D8 — Logout is CSRF-able
- **Severity: Low · Effort: Moderate · Bang-for-buck: Low** — `/auth/logout` is `[AllowAnonymous]` and CSRF-exempt (`CsrfMiddleware.cs:28`), so an attacker can force a victim's logout (minor DoS). Remove from the exempt list if desired (small UX cost: logout must carry the XSRF header).

### D9 — `ErrorBoundary` surfaces raw `error.message`
- **Severity: Low · Effort: Quick win · Bang-for-buck: Low** — `ui/src/components/shared/ErrorBoundary.tsx:18-19,46`. These are client-side render errors, not server stack traces, so leakage is minimal. Optionally show a generic message + keep the existing "Reload" affordance.

### D10 — Optional: rewrite git history to purge leaked passwords
- **Severity: Low (if rotated) · Effort: Hard · Bang-for-buck: Low** — BFG / `git filter-repo` to scrub `fed_app_2026`/`root_2026` from history. **Only worth it if rotation (A3/C2) is somehow not possible** — rotation makes the historical values dead and is far cheaper.

---

## ✅ E — Already Done (verified fixed in current code)

These were open in the prior doc and are **confirmed resolved** — kept for the audit trail:

- **H1 — `AllowedHosts: "*"`** → now `"localhost"` (`appsettings.json:43`); prod overrides via external config.
- **H2 — JWT placeholder secret + no startup guard** → committed secret is empty; startup guard at `Program.cs:396-402` throws on empty / `CHANGE_ME` / `<32` chars; prod secret comes from `Jwt__SecretKey` env var (in no config file).
- **H5 — `SameSite=Lax` cookies** → now `SameSiteMode.Strict` on all three cookies (`AuthController.cs:268,280,292`), `Secure` env-gated to prod (`:33`).
- **L1 — HANDOFF.md** → no longer exists in the repo (resolved/moot).

**Strong baseline confirmed by the audit (no action needed, do not regress):**

- **SQL injection:** all queries parameterized; the few raw-SQL spots (`InsightsService.cs`, `PricingService.cs`) bind via `MySqlParameter` with clamped numerics; LIKE uses `EscapeLikeWildcards`.
- **Multi-tenant isolation:** consistently org/user-scoped at the service layer (`ProspectService`, `SavedSearchService`); `AdminService` rejects cross-org targets. (One exception → A2.)
- **Mass assignment:** controllers bind to DTOs, not EF entities; `OrgId`/`Role`/`Status` set server-side from claims.
- **AuthZ:** default-deny `FallbackPolicy` + class-level `[Authorize]`; `[AllowAnonymous]` only where appropriate; Swagger gated to Development.
- **Password handling:** bcrypt (`EnhancedHashPassword`), account lockout (5/30min), progressive delay, constant-time dummy-hash path (user-enumeration-safe).
- **Sessions:** refresh-token rotation with **reuse detection** (nukes all sessions on replay); server-side revocation checked per request; no session fixation.
- **CSRF:** double-submit enforced on mutating cookie-auth requests; `/auth/refresh` correctly **not** exempt.
- **Security headers:** real CSP (`script-src 'self'`), HSTS (prod), `X-Frame-Options: DENY` + `frame-ancestors 'none'`, nosniff, Referrer-Policy, Permissions-Policy; `Server` header stripped.
- **Error handling:** `ExceptionHandlerMiddleware` returns generic messages + TraceId only; `DetailedErrors=false` in prod; no dev exception page in prod.
- **Input limits:** 10 MB body cap; pagination clamped 1–100 via FluentValidation.
- **No SSRF**, no path-traversal (no local file-download endpoint; attachments served as DB text + SAM source URLs), no open redirect (hardcoded redirect targets), no source maps in prod, no secrets / `VITE_*` in the bundle, no token in `localStorage`.

---

## Trigger Checklist (reconciled to current state)

Production is **already exposed**, so this is a "close the gaps" list, not a pre-deploy gate:

**Do now (A):**
- [ ] A1 — Re-enable rate limits (keep `search` generous)
- [ ] A2 — `AutoGenerate` ignores body `OrganizationId`
- [ ] A3 — Rotate DB/root passwords leaked in history (see C2)
- [ ] A4 — `npm audit fix` axios; add `npm audit` to CI

**Verify (C):**
- [ ] C1 — Confirm MySQL 3306 is **not** internet-reachable
- [ ] C2 — Confirm DB + JWT secrets rotated post-exposure
- [ ] C3 — Confirm prod `AllowedHosts` set in external config

**Quick wins (B):** B1 safeUrl · B2 email masking · B3 ERROR-body · B4 runbook wildcard · B5 CORS fail-fast · B6 Kestrel limits · B7 console strip · B8 X-Api-Version · B9 `days` clamp · B10 pre-commit hook · B11 configurable JWT lifetimes · B12 sanitize.ts

**Later (D):** D-cert trusted cert · D1 Redis rate limit (scaling) · D3 MySQL TLS · D4 SAM key header · D5 CSP styles · D6 PFX ACLs · D7 TLS pin · D8 logout CSRF · D9 ErrorBoundary · D10 history rewrite

**Done (E):** H1, H2, H5, L1 — verified fixed.
