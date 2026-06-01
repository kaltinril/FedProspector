# Production Internet Exposure — Single-Port HTTPS

How FedProspect is exposed to the public internet: one C# process serves both the
API and the React UI over HTTPS on a single port, hardened against unauthenticated
attackers. Threat model: only **unauthenticated** attackers matter — the 3 trusted
users all have logins.

## Architecture — Single-Port HTTPS (Option B)

- The C# API (`api/src/FedProspector.Api/`) serves the **prebuilt React UI as static
  files** (`UseStaticFiles` + `MapFallbackToFile("index.html").AllowAnonymous()`) **and**
  the API, on **one port**. There is NO separate UI server in production. Vite (port 5173)
  is dev-only.
- **Ports**:
  - **5056** — API + UI. HTTPS in Production, plain HTTP in Development.
  - **5055** — HTTP→HTTPS redirect endpoint (Production only, from `appsettings.Production.json`).
  - **5173** — Vite dev server (development only).
- UI build output goes to the API's `wwwroot` (`ui/vite.config.ts` `build.outDir`).
  `deploy.ps1` runs `npm run build` before copying, so prod gets the prebuilt SPA.
  **Prod does NOT need `node_modules` or a UI rebuild.**

## Config Layering

`Program.cs` loads configuration in this order (**last wins**):

1. Committed `appsettings.json`
2. `appsettings.{Environment}.json`
3. Environment variables
4. In-repo `appsettings.Local.json` — DEV machine secrets, **gitignored**
5. **External prod config file** — highest precedence

### External prod config file

- Path: `C:\fedprospector\config\fedprospector.local.json` (override via the
  `FEDPROSPECTOR_CONFIG` env var).
- Lives **OUTSIDE the repo** so `deploy.ps1` can never overwrite it.
- Holds prod's `ConnectionStrings`, `Cors`, `AllowedHosts`, and the `Kestrel` HTTPS
  endpoint + self-signed cert path/password.
- Example shape: `scripts/fedprospector.local.example.json`.

### Secrets that are NOT in config files

- **JWT secret** comes from the `Jwt__SecretKey` **environment variable** (set by
  `fed_prospector.py` `_api_env()` from `fed_prospector/.env`). It is in no config file.

### Deploy safety

- `deploy.ps1` excludes `appsettings.Local.json` from robocopy (`/XF`). Per-machine
  secrets stay on each box and are never shipped. The external config file is never
  touched by deploy.

## Scripts

### `scripts/generate-selfsigned-cert.ps1` — the SSL provisioner

Run on the **PROD server** (elevated when using `-OpenFirewall`). With NO args it uses
baked-in defaults: SAN + `AllowedHosts` cover external IP `206.162.3.86`, internal
`192.168.0.137`, `localhost`, and `127.0.0.1`. It:

1. Generates (or reuses) a self-signed RSA-2048, 5-year cert into
   `C:\fedprospector\certs\fedprospector.pfx`.
2. Writes/merges the external config file (Kestrel cert + `AllowedHosts`; on first run
   migrates `ConnectionStrings`/`Cors` from the in-repo `appsettings.Local.json`).

Idempotent. After a public-IP change, re-run with:

```powershell
.\scripts\generate-selfsigned-cert.ps1 -DnsName <new-ip>,192.168.0.137,localhost,127.0.0.1 -Force
```

`-DnsName` entries are validated. PowerShell switches use a **SINGLE dash** — a mistyped
double-dash like `--Force` is rejected/ignored (see Troubleshooting).

### `scripts/open-firewall.ps1`

Self-elevating (UAC); opens inbound TCP **5056**; idempotent; uses the same firewall rule
name as the cert script's `-OpenFirewall`.

## Service Manager (`fed_prospector.py` / `.bat`)

- **Auto-detects Production by the PRESENCE of the external config file** (not just the
  `ASPNETCORE_ENVIRONMENT` env var) — robust against a stale terminal where `setx` hasn't
  taken effect yet.
- In Production it launches the API as Production (HTTPS; Kestrel config drives binding),
  and `start` does **NOT** launch Vite (the API serves the built UI).
- The health probe tries **HTTPS then HTTP** so `build`/`start`/`status` detect the API
  regardless of scheme.

### Known pending TODOs

- `build` still auto-launches the API after building — owner wants `build` to JUST build.
- `deploy.ps1` currently builds only the UI; it should also `dotnet build` the API.

## Go-Live Runbook (prod)

1. **From dev**: `.\deploy.ps1` — ships code + prebuilt UI; leaves prod's external config
   and `appsettings.Local.json` untouched.
2. **On prod**: `fed_prospector.bat build api` — compile the C#. *(TODO: deploy will do
   this later.)*
3. **On prod, elevated**: `.\scripts\generate-selfsigned-cert.ps1` then
   `.\scripts\open-firewall.ps1`.
4. `setx ASPNETCORE_ENVIRONMENT Production` (once; takes effect in a new terminal) —
   though file-based detection now also covers this.
5. Port-forward the router's public port → prod TCP **5056**.
6. `fed_prospector.bat start`, then browse `https://<host-or-ip>:5056`.

## Troubleshooting

| Symptom | Cause / Fix |
|---------|-------------|
| HTTP 400 "request hostname is invalid" | `AllowedHosts` doesn't include the host you used. Re-run the cert script (no `-DnsName`, single-dash `-Force`) so `AllowedHosts` gets the full list, or set `AllowedHosts="*"`. |
| `ERR_CONNECTION_TIMED_OUT` from another machine | Windows Firewall (run `open-firewall.ps1`) and/or missing router port-forward. |
| "Waiting for API to respond" on build/start | API is on a different scheme/port than the probe expected. Fixed by file-based Production detection + dual-scheme (HTTPS-then-HTTP) probe. |
| `--Force` (double dash) ignored | PowerShell parses `--Force` as a positional value, NOT the switch. Use single-dash `-Force`. |
| Browser "not trusted" / cert warning | Expected with a self-signed cert. Encryption is full-strength; click through once per device. |

## Unauthenticated-Surface Security Hardening

Threat model: only unauthenticated attackers matter (3 trusted users get logins).
Implemented:

- **Per-IP failed-login throttle** — 10 failures / 15-min window → 15-min block;
  failures only, cleared on success (`LoginThrottleService`).
- **Constant-time login** — dummy bcrypt comparison on unknown/inactive/locked accounts
  so timing doesn't leak account existence.
- **Default-deny authorization** — global `FallbackPolicy` requires auth on every endpoint
  unless explicitly `[AllowAnonymous]`.
- **JWT-secret startup guard** — enforced in ALL environments.
- **Trimmed anonymous `/health`** — returns only `{status, db}`.
- **HTTPS** — self-signed cert; the browser "not trusted" warning is expected (full-strength
  encryption; click through once per device).
