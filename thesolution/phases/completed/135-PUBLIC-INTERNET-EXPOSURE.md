# Phase 135 — Public Internet Exposure: Single-Port HTTPS + Unauthenticated Hardening

**Status: COMPLETE** (2 pending TODOs, see below)

Expose FedProspect to the public internet as one C# process serving both the API and the
React UI over HTTPS on a single port, hardened against unauthenticated attackers.

> Full operator reference (architecture, config layering, go-live runbook, troubleshooting,
> security hardening): **`thesolution/reference/14-PRODUCTION-EXPOSURE.md`**. This phase doc
> is a concise pointer; the reference doc is the source of truth.

## What shipped

### Single-port HTTPS (Option B)

- One C# process (`api/src/FedProspector.Api/`) serves the prebuilt React UI as static
  files (`UseStaticFiles` + `MapFallbackToFile("index.html").AllowAnonymous()`) **and** the
  API on one port. No separate UI server in prod; Vite (5173) is dev-only.
- Ports: **5056** = API+UI (HTTPS in Production, HTTP in Development); **5055** =
  HTTP→HTTPS redirect (Production).
- UI build output → API `wwwroot`; `deploy.ps1` runs `npm run build` before copying, so
  prod needs no node_modules / UI rebuild.

### Config layering & deploy safety

- `Program.cs` config order (last wins): `appsettings.json` →
  `appsettings.{Environment}.json` → env vars → in-repo `appsettings.Local.json`
  (gitignored dev secrets) → external prod config.
- External prod config `C:\fedprospector\config\fedprospector.local.json` (override via
  `FEDPROSPECTOR_CONFIG`) lives outside the repo so deploy can't overwrite it; holds
  ConnectionStrings/Cors/AllowedHosts/Kestrel cert. Example: `scripts/fedprospector.local.example.json`.
- JWT secret is NOT in any config file — from `Jwt__SecretKey` env var (set by
  `fed_prospector.py` from `fed_prospector/.env`).
- `deploy.ps1` excludes `appsettings.Local.json` (`/XF`).

### Scripts

- `scripts/generate-selfsigned-cert.ps1` — SSL provisioner: self-signed RSA-2048 5-yr cert
  → `C:\fedprospector\certs\fedprospector.pfx`; writes/merges external config; idempotent.
- `scripts/open-firewall.ps1` — self-elevating; opens inbound TCP 5056; idempotent.

### Service manager

- `fed_prospector.py` auto-detects Production by presence of the external config file (not
  just `ASPNETCORE_ENVIRONMENT`); `start` skips Vite in Production; health probe tries
  HTTPS then HTTP.

### Unauthenticated-surface hardening

Threat model: only unauthenticated attackers matter (3 trusted users have logins).

- Per-IP failed-login throttle (10 / 15-min → 15-min block; cleared on success) —
  `LoginThrottleService`.
- Constant-time login (dummy bcrypt on unknown/inactive/locked).
- Default-deny `FallbackPolicy` (auth required unless `[AllowAnonymous]`).
- JWT-secret startup guard in ALL environments.
- Anonymous `/health` trimmed to `{status, db}`.
- HTTPS via self-signed cert (browser "not trusted" warning expected; full-strength encryption).

## Pending TODOs

1. `build` still auto-launches the API after building — owner wants `build` to JUST build.
2. `deploy.ps1` builds only the UI; it should also `dotnet build` the API.
