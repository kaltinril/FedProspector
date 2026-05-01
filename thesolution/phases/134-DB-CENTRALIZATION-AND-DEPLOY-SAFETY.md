# Phase 134 — DB Centralization and Deploy Safety

**Status**: IN PROGRESS
**Priority**: HIGH (blocks granting non-developer users access to prod)
**Depends on**: None

---

## Background / Problem

This is a single-developer, single-org, two-machine setup.

- **Dev box**: `c:\git\fedProspect` on Windows. MySQL data lives on `E:\` (HP SSD EX950 NVMe, ~3.5 GB/s).
- **Prod box**: `192.168.0.137`. Single drive (C:). MySQL data dir at `C:\mysql\data`, attachments at `C:\fedprospector\attachments`. Drive: Samsung 970 EVO Plus 1TB NVMe (~3.5 GB/s read, ~3.3 GB/s write — essentially the same class as dev).
- **Current deploy script**: [deploy.ps1](../../deploy.ps1). It does three parallel robocopies: `C:\git\fedProspect → \\prod\gitshare`, `E:\mysql → \\prod\mysql`, and `E:\fedprospector\attachments → \\prod\attachments`. This means **every deploy file-level overwrites prod's entire MySQL data directory**, destroying any user changes (tracking flags, hidden opportunities, prospect notes, saved searches, organization_entity links, proposals, etc.).
- Today, only the developer's wife uses prod, lightly (testing). But she's about to grant access to an employee, and real user data will accumulate fast. **Must fix before that point.**
- Daily ETL load originally ran from dev (`python ./fed_prospector/main.py job daily`). Uses server-side `LOAD DATA INFILE` (no `LOCAL` keyword) — see [bulk_loader.py:440](../../fed_prospector/etl/bulk_loader.py). Files must be on the MySQL server's filesystem. As of cutover, daily load runs on prod instead.

### User-data tables (irreplaceable, must never be clobbered)

From [60_prospecting.sql](../../fed_prospector/db/schema/tables/60_prospecting.sql) and [90_web_api.sql](../../fed_prospector/db/schema/tables/90_web_api.sql):

- `organization`, `app_user`, `app_session`, `organization_invite`
- `prospect`, `prospect_note`, `prospect_team_member`
- `saved_search`
- `proposal`, `proposal_document`, `proposal_milestone`
- `activity_log`, `notification`
- `organization_certification`, `organization_naics`, `organization_past_performance`
- `organization_entity` (companies linked to an org)
- `contracting_officer`, `opportunity_poc` (mixed — partly user-curated)
- File attachments on disk (env: `ATTACHMENT_DIR` — `E:\fedprospector\attachments` on dev, `C:\fedprospector\attachments` on prod)

### ETL-loaded tables (reproducible, less critical)

`opportunity`, `entity`, `usaspending_award`, `fpds_contract`, `sca_*`, `bls_*`, `etl_*`, `ref_*`, etc. Theoretically rebuildable from APIs but practically painful (28M rows in `usaspending_award`, harsh SAM.gov rate limits).

---

## Options Considered

### Option 1 — Prod owns the DB; dev connects to it remotely (CHOSEN)

- Bind prod's MySQL to LAN. Grant `fed_app@192.168.0.%`. Dev's `.env` points `DB_HOST=192.168.0.137`.
- Daily ETL runs **on prod** manually via `python ./fed_prospector/main.py job daily` (user RDPs in or runs locally — no Task Scheduler). `LOAD DATA INFILE` stays server-side, files local to MySQL, zero code changes.
- Deploy ships **code only** — strip MySQL + attachments robocopy jobs from `deploy.ps1`.
- Schema migrations target prod via the same connection.
- **Why chosen**: Eliminates the data-loss bug by construction (deploy can't touch the DB if it never copies the DB). Simple. Matches the actual ownership: prod owns user state, dev owns code. Prod's NVMe is in the same perf class as dev's so no measurable load slowdown. ETL code is unchanged because `LOAD DATA INFILE` stays local to MySQL.

### Option 2 — Selective deploy (file-level allowlist) — REJECTED

- Keep current robocopy approach but exclude user tables from the MySQL data dir copy.
- **Why rejected**: InnoDB shared tablespaces make file-level table exclusion unreliable — many tables share `ibdata1` and indexes. You can't safely robocopy "just some tables." Even if it worked, you'd maintain a brittle allowlist forever, and any new user table you forget to add gets clobbered. File-level copies of running InnoDB are inherently unsafe (current script already has to delete redo logs on the target as a workaround).

### Option 3 — Selective data deploy via mysqldump (allowlist of ETL tables) — REJECTED FOR NOW

- Daily load runs on dev's local MySQL. After load, mysqldump only the ETL-loaded tables → restore on prod. User tables on prod never touched.
- **Why rejected**: More moving parts than option 1 (allowlist maintenance, dump/restore window, transactional consistency during the swap). Was considered as a fallback if prod's storage turned out to be much slower than dev's. Hardware check confirmed prod is in the same NVMe perf class, so option 1 wins on simplicity.
- **Keep documented as a fallback** in case future prod hardware ever changes (e.g., prod moves to a slower disk or VM).

### Option 4 — MySQL replication (primary/replica) — REJECTED

- 4a: Prod = primary, dev = replica. Replicas are read-only — fine for a warm backup but doesn't change the deploy story; option 1 is still required underneath. Adds operational sharp edges (binlogs, GTID gaps, replicas falling behind).
- 4b: Dev = primary, prod = replica. Doesn't work — wife's writes happen on prod, but a replica is read-only. Her actions would fail.
- 4c: Bidirectional / dual-primary. Conflict resolution nightmare for a one-person ops setup. Don't.
- 4d: InnoDB Cluster / Group Replication. Needs 3+ nodes, overkill.
- **Why rejected**: Replication is a layer *on top of* "prod is canonical," not a substitute. For a single-org workload, manual NAS backups are enough; we don't need near-zero-RPO. Can revisit if scale grows.

### Option 5 — Bidirectional sync of just user tables — REJECTED

- Some kind of merge logic to push prod's user-table changes back to dev periodically.
- **Why rejected**: Asymmetric sync logic, conflict resolution, and merge code are far more complex than just having one source of truth. We don't need dev to have current user data — dev is for development, not analysis of live user behavior.

---

## Chosen Architecture (Option 1) — Detailed

- **Prod (`192.168.0.137`)**: hosts MySQL, hosts attachments, runs daily ETL manually (user RDPs in or runs locally), runs the C# API and UI for end-users.
- **Dev**: runs the editor, runs `python ./fed_prospector/main.py` ad-hoc against prod's MySQL over LAN, runs the C# API and UI in Debug mode against prod's MySQL for development.
- **Deploy** = `robocopy C:\git\fedProspect → \\prod\gitshare` only. No DB touched.
- **Backups** = `robocopy` of prod's MySQL data dir to NAS at `\\diskstation\home\fedprospector\mysql`, run manually as needed (before risky operations, or on a personal cadence).
- **Schema migrations** = run from dev via `python ./fed_prospector/main.py`, targeting prod through the connection string.

---

## Implementation Steps

### Task 1 — Run [setup-prod.ps1](../../setup-prod.ps1) on prod (one-time)

The script is idempotent and ships in the repo (deployed via the gitshare push). RDP into prod, open elevated PowerShell, run it.

> **Note**: `setup-prod.ps1` and `backup.ps1` were authored after the seed deploy and are currently **untracked** in git on dev. They must be committed and pushed to prod (via a final old-style deploy or by copying them to `C:\git\fedProspect\` on prod) before Task 1 / Task 5 can be run on the prod box.

- [ ] On prod, RDP in and run: `powershell -ExecutionPolicy Bypass -File C:\git\fedProspect\setup-prod.ps1`
- [ ] Script handles: `my.ini` bind-address edit, firewall rule (TCP 3306 from dev box only — default `192.168.0.250`), pause for manual MySQL restart, GRANT for `fed_app@<dev-ip>` with same password as `fed_app@localhost`.
- [ ] If dev's DHCP lease ever shifts to a different IP, re-run `setup-prod.ps1 -DevIp <new-ip>` to update both the firewall rule and the MySQL grant.
- [ ] From dev, verify: `mysql -h 192.168.0.137 -u fed_app -p fed_contracts -e "SELECT COUNT(*) FROM opportunity;"`

### Task 2 — Python + repo on prod — DONE

Already in place: Python 3.14, repo at `C:\git\fedProspect`, venv, `.env`, attachments dir. The application currently runs on prod and the daily load is run from prod manually. No work for this task.

### Task 3 — Switch dev to point at prod (manual by user, with agent help on config files)

- [ ] Edit `fed_prospector/.env` on dev: change `DB_HOST=localhost` → `DB_HOST=192.168.0.137`.
- [ ] Edit `api/src/FedProspector.Api/appsettings.Local.json` on dev: update connection string to point at `192.168.0.137`. Verify pool settings (`MaxPoolSize=50;MinPoolSize=5`) and consider adding `ConnectionLifetime=300;ConnectionReset=true` to handle LAN connection resets — see Gotcha 1.
- [ ] Stop dev's local MySQL service (or leave it running for offline backup — see Future / Deferred below).
- [ ] Smoke-test: run dev's UI against prod's DB. Verify reads + writes work.

### Task 4 — Strip DB/attachments from [deploy.ps1](../../deploy.ps1) (agent: coder)

Goal: deploy ships **only** the project source tree to `\\prod\gitshare\fedProspect`. No MySQL data, no attachments, no post-copy MySQL fixes.

Specific edits (line numbers refer to the current [deploy.ps1](../../deploy.ps1) — verify before editing in case of drift):

- [ ] **Top of script — `net use` setup**: in the `foreach ($share in @("gitshare", "mysql", "attachments"))` cleanup loop, drop `"mysql"` and `"attachments"`. Likewise remove the two `net use \\$target\mysql ...` and `net use \\$target\attachments ...` authentication lines.
- [ ] **Parallel jobs — MySQL**: delete the entire `Start-Job -Name "MySQL"` block (currently the second of three jobs).
- [ ] **Parallel jobs — Attachments**: delete the entire `Start-Job -Name "Attachments"` block (currently the third of three jobs). Result: only the `Project` (gitshare) job remains.
- [ ] **Error-path cleanup**: in the `if ($hasErrors)` branch, drop the `net use \\$target\mysql /delete` and `net use \\$target\attachments /delete` lines.
- [ ] **Post-copy fixes — Fix 1 (`my.ini` path rewrite)**: delete entirely. Prod manages its own `my.ini`.
- [ ] **Post-copy fixes — Fix 2 (InnoDB redo log clear)**: delete entirely. Only relevant when copying a hot MySQL data dir, which we no longer do.
- [ ] **Post-copy fixes — Fix 3 (`.env` path rewrite)**: delete entirely. The new approach is to NOT overwrite prod's `.env` in the first place (see next bullet) rather than overwrite-then-rewrite.
- [ ] **Project robocopy — exclude `.env`**: in the `Start-Job -Name "Project"` block, add `/XF ".env"` to the robocopy args. Without this, dev's `fed_prospector/.env` (with `DB_HOST=192.168.0.137`) would overwrite prod's (which needs `DB_HOST=localhost`). Add any other host-specific files to the same `/XF` list as they come up.
- [ ] **Post-copy fixes — Fix 4 (appsettings pool limits)**: keep — still applies to the C# API code that just got copied. Already idempotent.
- [ ] **Bottom of script — disconnect**: drop the `net use \\$target\mysql /delete` and `net use \\$target\attachments /delete` lines.
- [ ] **"Done!" message**: remove `"Start MySQL on target with: ..."`. Replace with something like `"Done! Restart the C# API on prod to pick up the new code."` (or whatever fits the actual prod restart workflow).
- [ ] **Test**: run the new minimal `deploy.ps1` against prod. Verify it pushes only the gitshare and prod's MySQL data + user records are untouched.

### Task 5 — Backups via robocopy of MySQL data dir to NAS (manual)

Simpler than mysqldump: stop MySQL, robocopy the on-disk InnoDB tablespace files to the NAS, restart MySQL. Workflow assumes MySQL is **stopped** during the copy — guarantees a consistent snapshot, no hot-copy hazard.

- [ ] [backup.ps1](../../backup.ps1):
  - `robocopy C:\mysql\data \\diskstation\home\fedprospector\mysql /MIR /MT:8 /R:1 /W:1`
  - Also copies `my.ini` so the NAS snapshot is self-contained for restore.
- [ ] User workflow: shut MySQL down, run `backup.ps1`, start MySQL back up.
- [ ] Test restore once: copy NAS contents back to a dev location, point a MySQL instance at it, verify it starts and table counts match.

---

## Cutover Plan

A final old-style deploy seeded prod with today's ETL data, and the first daily ETL run on prod completed successfully. The cutover order is:

1. ✅ Final old-style deploy completed. Daily ETL load executed successfully on prod.
2. Task 1 on prod: run `setup-prod.ps1`. (Task 2 already done.)
3. Task 3 on dev (point dev at prod).
4. Verify dev still works for development.
5. Task 4: strip `deploy.ps1`. Test the new minimal deploy.
6. Task 5: `backup.ps1` (robocopy to NAS) — run once, verify it lands on the NAS.
7. Wife grants the employee access. Real user data starts flowing.

---

## Gotchas / Risks

1. **C# EF Core connection pooling — only matters when debugging from dev**: On prod, the C# API and MySQL are on the same box (localhost), so pool/timeout behavior is unchanged. The concern is only when you run the API in Debug mode on **dev** pointing at prod's MySQL — that's the LAN connection where idle connections might be killed by network/timeout. If you hit "connection lifetime" errors during local debug, add `ConnectionLifetime=300;ConnectionReset=true` to the `appsettings.Local.json` connection string.

2. **Dev's `.env` would overwrite prod's during deploy**: Both machines have a `fed_prospector/.env` at the same path, but they need different values (dev: `DB_HOST=192.168.0.137`, prod: `DB_HOST=localhost`). The gitshare robocopy compares timestamps and would clobber prod's. Fix: add `/XF ".env"` to the robocopy exclusion list in `deploy.ps1` (handled in Task 4). Same applies to any other host-specific config files.

3. **Schema migrations now run against a DB real users are using**: Take a backup (`backup.ps1`) before any migration. Avoid breaking changes during business hours once the employee is active.

---

## Success Criteria

- [ ] `deploy.ps1` no longer touches MySQL or attachments
- [ ] Wife or her employee can mark a prospect as tracking, deploy fires, and the tracking flag is still there afterward
- [ ] Daily load runs successfully on prod when manually triggered, producing the same data quality as previous dev-side runs
- [ ] Dev can run the UI in dev mode against prod's DB and CRUD through it
- [ ] `backup.ps1` lands a full copy of `C:\mysql\data` on the NAS at `\\diskstation\home\fedprospector\mysql`, and a test restore has been validated at least once
- [ ] Cannot connect to prod's MySQL from outside the LAN (firewall verified)

---

## Known Issues

- **Pebble missing from prod's venv on first run**: had to manually `pip install -r requirements.txt` on prod after the seed deploy. Cause unknown (incomplete prior install? requirements drift?). Daily load now succeeds. If the venv ever gets recreated, re-run `pip install -r requirements.txt`.
- **`8a` vs `8A` set-aside case mismatch in daily batch**: [fed_prospector/cli/load_batch.py:77](../../fed_prospector/cli/load_batch.py) passed `"8a"` lowercase; [awards.py](../../fed_prospector/cli/awards.py) `VALID_SET_ASIDE_CODES` is uppercase `"8A"` and validation is case-sensitive — caused the awards loader to fail loudly during the first prod-side daily run. Fix applied in working tree (one-line: `"8a"` → `"8A"` at line 77); not yet committed as of this writing. Surfaced because daily ran end-to-end on the new machine for the first time.

---

## Future / Deferred

- Read-only local mirror on dev for offline analytics.
- Optional: prod → dev MySQL replication for near-zero-RPO backup (only if manual NAS backups prove insufficient). See Option 4 above.
- Optional: schedule `backup.ps1` if manual cadence becomes unreliable.
- Optional: move backups to a true offsite location (cloud bucket, etc.) once the business grows — NAS is on-LAN, not strictly offsite.
- Selective data deploy via mysqldump allowlist (Option 3) remains documented as a fallback if prod hardware ever changes (e.g., slower disk, VM with constrained I/O).
