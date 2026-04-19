# Phase 310: Dependency Updates & Package Maintenance

**Status:** IN PROGRESS — PRs 1–6 done, PR 7 deferred (ecosystem), PRs 8–9 deferred (separate session), PR 10 in progress
**Priority:** HIGH (6 open security advisories across UI + Python)
**Dependencies:** None
**Validated against live state:** 2026-04-18
**Strategy:** Go latest stable on every package, unless the latest has a known vulnerability or a hard compatibility blocker.

---

## Summary

Live audit found 6 open security advisories:
- **UI:** 4 (axios ×2, vite, dompurify) — all fixable in-range
- **Python:** 2 on `anthropic 0.86.0` (race condition, insecure file perms) — patched in 0.87.0+; target 0.96.0 (latest)
- **C#:** 0 known

**One hard blocker to going latest everywhere:** `Pomelo.EntityFrameworkCore.MySql` has no 10.x release on nuget.org (latest stable 9.0.0 as of 2026-04-18), so `Microsoft.EntityFrameworkCore.*` must stay on 9.x to remain Pomelo-compatible.

**Execution strategy — order matters:** Land every other upgrade first (security + patch/minor across UI, Python, .NET, plus ESLint 10). Validate the codebase is stable. Then tackle **MUI v7→v9** (biggest migration). Then **TypeScript 5.9→6.0** last, once everything else is proven stable.

Rationale for the ordering:
- **MUI v9 was released 2026-04-07** (11 days ago as of 2026-04-18). Doing it last gives v9 a few more weeks of real-world bug-fix releases before we adopt.
- **TypeScript 6 stricter type checks** could surface errors in MUI v9 migration code if the two were bundled together. Sequencing them separately makes debugging clearer: if `tsc` breaks after TS 6 bump, we know it's the compiler, not the library.
- Core `@mui/material` skipped v8 (went v5 → v6 → v7 → v9) to harmonize version numbers with `@mui/x-*` packages — so this is actually a **1-major jump** (v7→v9), not 2.

---

## Compatibility Gates (verified 2026-04-18)

| Package | Latest stable | Advisories at latest | Decision |
|---|---|---|---|
| axios | 1.15.0 | 0 | Go latest |
| vite | 8.0.8 | 0 | Go latest (within ^8 range) |
| dompurify | 3.4.0 | 0 | Go latest |
| @mui/material | 9.0.0 | 0 | Go latest (v7 → v9; MUI skipped v8 → actually a 1-major jump). **Ship after all other PRs.** v9 released 2026-04-07. |
| typescript | 6.0.3 | 0 | Go latest |
| eslint | 10.2.1 | 0 (only old ReDoS < 4.18.2) | Go latest |
| coverlet.collector | 10.0.0 | 0 | Go latest |
| Pomelo.EntityFrameworkCore.MySql | **9.0.0** | 0 | **Stay on 9.x** — no 10.x exists |
| Microsoft.EntityFrameworkCore.* | 9.0.7 → **9.0.x patch only** | 0 | Stay on 9.x to match Pomelo |
| @types/node | 25.6.2 | 0 | Recommend staying on 22.x to match Node runtime (compat, not security) |
| npm | 11.12.1 | 0 | Go latest (installs on Node 22) |
| anthropic (Python) | 0.96.0 | 0 | Go latest — **fixes 2 medium CVEs in 0.86.0** |
| All other Python packages | latest patch/minor | 0 | Go latest |

---

## Security Fixes — Must Land First

### UI (4 advisories open)

| Package | Current | Target | Severity | Advisory |
|---------|---------|--------|----------|----------|
| axios | 1.13.6 (pinned) | 1.15.0 | Moderate | GHSA-3p68-rc4w-qgx5 (SSRF via NO_PROXY bypass) |
| axios | 1.13.6 (pinned) | 1.15.0 | Moderate | GHSA-fvcv-3m26-pcqx (Cloud Metadata Exfiltration via Header Injection) |
| vite | ^8.0.1 (8.0.1 installed) | 8.0.8 | High | GHSA-p9ff-h696-f583 (Arbitrary File Read via Dev Server WS), GHSA-v2wj-q39q-566r (fs.deny bypass), GHSA-4w7w-66w2-5vf9 (Path Traversal in .map) |
| dompurify | ^3.3.3 | 3.4.0 | Moderate | GHSA-39q2-94rc-95cp (ADD_TAGS bypasses FORBID_TAGS) — our `ui/src/utils/sanitize.ts` uses ALLOWED_TAGS (allowlist), so not exploited, but patch anyway |
| follow-redirects | 1.15.9 (transitive) | 1.15.11 | Moderate | GHSA-r4q5-vmmm-2653 — resolves automatically with axios update |

### Python (2 advisories open)

| Package | Current | Target | Severity | Advisory |
|---------|---------|--------|----------|----------|
| anthropic | 0.86.0 | 0.96.0 | Medium | GHSA-w828-4qhx-vxx3 (Memory Tool path validation race → sandbox escape) — patched in 0.87.0 |
| anthropic | 0.86.0 | 0.96.0 | Medium | GHSA-q5f5-3gjm-7mfm (Insecure default file permissions in local FS Memory Tool) — patched in 0.87.0 |

Both affect the Claude SDK's Memory Tool. Confirm with `grep -r "beta.memory\|memory_tool" fed_prospector/` whether we use the Memory Tool; if not, exposure is academic, but still patch.

### C# — no known vulnerabilities
`dotnet list package --vulnerable` returns nothing.

---

## UI — Full Update List (go latest on all)

| Package | Current | Target | Category | Notes |
|---------|---------|--------|----------|-------|
| axios | 1.13.6 (pinned) | **1.15.0** | Security | Unpins to ^1.15.0 |
| vite | ^8.0.1 | **8.0.8** | Security | `npm audit fix` |
| dompurify | ^3.3.3 | **3.4.0** | Security | |
| react | ^19.2.0 | **19.2.5** | Patch | |
| react-dom | ^19.2.0 | **19.2.5** | Patch | |
| react-hook-form | ^7.71.2 | **7.72.1** | Patch | |
| react-router-dom | ^7.13.1 | **7.14.1** | Minor | |
| @tanstack/react-query | ^5.91.2 | **5.99.1** | Minor | |
| @tanstack/react-query-devtools | ^5.91.3 | **5.99.1** | Minor | |
| @mui/material | ^7.3.9 | **9.0.0** | Major (1 version — MUI skipped v8 for core) | Migration needed — see MUI v9 migration guide. Land in **PR 8**, after other PRs have stabilized. |
| @mui/icons-material | ^7.3.9 | **9.0.0** | Major | Must match @mui/material |
| @mui/x-charts | ^8.27.5 | **9.0.2** | Major | Align with MUI v9 |
| @mui/x-data-grid | ^8.27.5 | **9.0.2** | Major | Align with MUI v9 |
| typescript | ~5.9.3 | **6.0.3** | Major | First TS 6.x — run `tsc --noEmit` before committing. Land in **PR 9** (dead last), after MUI v9 has stabilized. |
| eslint | ^9.39.3 | **10.2.1** | Major | Flat config already in use |
| @eslint/js | ^9.39.1 | **10.0.1** | Major | Match eslint |
| eslint-plugin-react-hooks | ^7.0.1 | **7.1.1** | Minor | Verify peer-dep range allows ESLint 10 |
| typescript-eslint | ^8.57.1 | **8.58.2** (PR 5) → bump again in PR 9 | Patch now, then bump to a TS 6-supporting version when PR 9 lands |
| prettier | ^3.8.1 | **3.8.3** | Patch | |
| globals | ^17.4.0 | **17.5.0** | Patch | |
| @types/node | ^22.0.0 | **^22.19.17** (stay on 22) | Compat | Match Node 22 runtime; going to 25 adds APIs we can't use |

### Environment
- **npm 10.9.4 → 11.12.1** — works on Node 22; `npm install -g npm@latest`

---

## .NET — Full Update List (go latest except EF Core)

### Cannot go latest — Pomelo blocker
EF Core must stay on the 9.x line until `Pomelo.EntityFrameworkCore.MySql` ships a 10.x release.

| Package | Current | Target | Projects |
|---------|---------|--------|----------|
| Microsoft.EntityFrameworkCore.Design | 9.0.7 | **9.0.7 (stay)** — bump to any 9.0.x patch if released | FedProspector.Api |
| Microsoft.EntityFrameworkCore.InMemory | 9.0.7 | **9.0.7 (stay)** | Api.Tests, Infrastructure.Tests |
| Microsoft.EntityFrameworkCore.Relational | 9.0.7 | **9.0.7 (stay)** | Api.Tests |
| EFCore.NamingConventions | 9.0.0 | **9.0.0 (stay)** | Infrastructure |
| Pomelo.EntityFrameworkCore.MySql | 9.0.0 | **9.0.0 (latest)** | Infrastructure |

**Watch:** when Pomelo 10.x ships, open sub-phase **310D** to bump EF Core 9 → 10 + Pomelo 9 → 10 together.

### Everything else — go latest

| Package | Current | Target | Projects |
|---------|---------|--------|----------|
| Microsoft.AspNetCore.Authentication.JwtBearer | 10.0.5 | **10.0.6** | Api, Infrastructure |
| Microsoft.AspNetCore.Mvc.Testing | 10.0.5 | **10.0.6** | Api.Tests |
| Microsoft.Extensions.Logging.Abstractions | 10.0.5 | **10.0.6** | Core.Tests, Infrastructure.Tests |
| Microsoft.OpenApi | 3.4.0 | **3.5.2** | Api |
| Swashbuckle.AspNetCore | 10.1.5 | **10.1.7** | Api |
| Microsoft.NET.Test.Sdk | 18.3.0 | **18.4.0** | All 3 test projects |
| coverlet.collector | 8.0.1 | **10.0.0** (major) | All 3 test projects — verify coverage output still parses in CI |

---

## Python — Full Update List (go latest on all)

### Direct deps in `fed_prospector/requirements.txt`

| Package | Current | Target | Category |
|---------|---------|--------|----------|
| anthropic | 0.86.0 | **0.96.0** | **Security (2 CVEs)** |
| requests | 2.32.5 | **2.33.1** | Minor |
| lxml | 6.0.2 | **6.1.0** | Minor |
| click | 8.3.1 | **8.3.2** | Patch |
| rapidfuzz | 3.14.3 | **3.14.5** | Patch |
| pytest | 9.0.2 | **9.0.3** | Patch |

### Transitive deps (auto-update with direct bumps)

pdfminer.six 20251230 → 20260107, pydantic 2.12.5 → 2.13.2, pydantic_core 2.41.5 → 2.46.2, anyio 4.12.1 → 4.13.0, charset-normalizer 3.4.6 → 3.4.7, docstring_parser 0.17.0 → 0.18.0, jiter 0.13.0 → 0.14.0, pillow 12.1.1 → 12.2.0, pypdfium2 5.6.0 → 5.7.0, Pygments 2.19.2 → 2.20.0, cryptography 46.0.6 → 46.0.7, packaging 26.0 → 26.1

### Environment

| Tool | Current | Target | Action |
|------|---------|--------|--------|
| pip | 25.3 | **26.0.1** | `python -m pip install --upgrade pip` |
| tzdata | 2025.3 | **2026.1** | Annual timezone refresh |

---

## Execution Order (isolated PRs to limit blast radius)

Each PR is standalone — if one breaks, it can be reverted without blocking the others.

**Ordering principle:** security first → low-risk drop-ins → ESLint 10 → MUI v9 → TypeScript 6 last. MUI v9 and TypeScript 6 are the two biggest migrations; doing them sequentially (not bundled) makes debugging clearer, and TypeScript 6 goes dead last so we don't compound stricter type-check errors on top of a just-landed UI library migration.

**All target versions verified as stable `latest` dist-tag releases (2026-04-18)** — no betas, alphas, RCs, or canary builds. Runtimes targeted are LTS tracks (Node 22 LTS "Jod", .NET 10 LTS, MySQL 8.4 LTS, Python 3.14). Only caveat: the Python `anthropic` SDK is at 0.96.0 because the SDK itself is still pre-1.0 (not available as 1.x); each 0.x release is a production release, not a prerelease in the SemVer sense.

### PR 1 — UI security (ships first)
1. Edit `ui/package.json`: `"axios": "1.13.6"` → `"axios": "^1.15.0"`
2. `cd ui && npm audit fix` (resolves vite, dompurify, follow-redirects)
3. `npm audit` must report 0 vulns
4. `npm run build && tsc -b && npm run lint`
5. Smoke test: login, attachment download, dashboard list, one detail page

### PR 2 — Python security + minor/patch bundle
1. Update `fed_prospector/requirements.txt`: anthropic 0.96.0, requests 2.33.1, lxml 6.1.0, click 8.3.2, rapidfuzz 3.14.5, pytest 9.0.3
2. `pip install -r requirements.txt --upgrade && pip check`
3. Review anthropic 0.86 → 0.96 CHANGELOG for call-site breaking changes; grep `fed_prospector/` for `anthropic.`, `Anthropic(`, `.messages.create`, `.beta.`
4. `python -m pytest`
5. `python -m pip install --upgrade pip`
6. Smoke test: `python main.py load opportunity --limit 5`, one Anthropic-backed analyzer call, one PDF extraction

### PR 3 — .NET minor/patch (EF Core stays on 9.x)
1. Update JwtBearer, Mvc.Testing, Logging.Abstractions, OpenApi, Swashbuckle, Test.Sdk versions across all 6 csproj files
2. `dotnet restore && dotnet build && dotnet test`
3. Smoke test: auth flow, `/api/prospects`, saved search CRUD

### PR 4 — coverlet.collector 8 → 10 (major)
1. Bump in all 3 test csproj files
2. `dotnet test` — current CI doesn't collect coverage, but confirm tests still run
3. If a future CI step adds `--collect:"XPlat Code Coverage"`, verify output format at that time

### PR 5 — UI patch/minor non-security (non-MUI, non-TS)
1. Bump: react, react-dom, react-router-dom, @tanstack/react-query, @tanstack/react-query-devtools, react-hook-form, prettier, globals, eslint-plugin-react-hooks, typescript-eslint (stay on 8.x that supports TS 5.9 and TS 6), MUI v7 patch (7.3.9 → 7.3.10), MUI X v8 patch (8.27.5 → 8.28.2)
2. `npm run build && tsc -b && npm run lint`
3. Smoke test UI key pages

### PR 6 — npm CLI bump
1. `npm install -g npm@11.12.1`
2. `npm ci` in `ui/` — verify lockfile format still resolves
3. Regenerate lockfile if needed

### PR 7 — ESLint 9 → 10 — **DEFERRED**

**Status:** Deferred (2026-04-18) until the ESLint 10 ecosystem catches up.

**Blocker:** `eslint-plugin-jsx-a11y@6.10.2` (latest on npm) declares peer `eslint ^3 || ... || ^9` — does not accept ESLint 10. It is the de-facto JSX accessibility linter with no real replacement; removing it would drop a11y linting coverage. `typescript-eslint@8.58.2` and `eslint-plugin-react-hooks@7.1.1` already support ESLint 10; jsx-a11y is the sole holdout. Tracking issue: jsx-a11y #1075 (filed 2026-02-09, no progress as of 2026-04-18).

**No security pressure:** ESLint 9.x has zero open advisories. Only old ReDoS < 4.18.2 is flagged on npm audit, and we're far past that.

**Resume conditions:** (a) jsx-a11y ships a release with `eslint ^10` in peer range, OR (b) a viable replacement emerges. When either happens, reopen this PR with the original plan:

1. Bump eslint 9.39.4 → 10.x latest, @eslint/js 9.39.4 → 10.x latest
2. Keep typescript-eslint on a version that still supports TS 5.x (so this PR doesn't force TS 6 yet)
3. `npm run lint` — fix any violations from 3 new `recommended` rules (`no-unassigned-vars`, `no-useless-assignment`, `preserve-caught-error`)
4. `npm run build`

### PR 8 — MUI v7 → v9 (largest effort; do AFTER everything above has shipped and stabilized)
Only start this PR after PRs 1–6 have merged (PR 7 is deferred; see above), run in prod for at least a few days, and the codebase is proven stable. Gives MUI v9 time to accumulate post-GA bug-fix patches (watch for 9.0.x or 9.1 release before starting).

1. Read MUI migration guides v7→v9 (MUI skipped v8 for core, so one guide — but @mui/x-* went v8→v9 on its own guide)
2. Run MUI codemods: `npx @mui/codemod@latest v9.0.0/preset-safe ui/src` (commit alone — reversible baseline)
3. Bump @mui/material, @mui/icons-material, @mui/x-charts, @mui/x-data-grid to v9 targets
4. Manually audit DataGrid column defs (37 files) — see Code Impact Analysis section below
5. Manually audit Charts (8 files) — responsive sizing, tooltip/legend slots
6. `npm run build && tsc -b && npm run lint`
7. Smoke test every page — grid behavior, chart rendering, theme, breakpoints
8. Screenshot-diff critical pages (dashboard, pipeline, pricing pages, prospect detail) before/after
9. Fix any visual regressions

### PR 9 — TypeScript 5.9 → 6.0 (ships LAST)
Done after MUI v9 so stricter type-check errors are clearly attributable to TS 6 and not compounded with a fresh UI library migration.

1. Bump typescript 5.9.3 → 6.0.3
2. Bump typescript-eslint 8.57.x → whatever version officially supports TS 6 (verify peer-dep range at time of PR)
3. `tsc --noEmit` — fix new type errors surfaced by stricter TS 6 checks (expect the `as any` cast in `ui/src/pages/opportunities/DocumentIntelligenceTab.tsx` to need a real type)
4. `npm run lint` — fix any new linting issues from newer typescript-eslint
5. `npm run build`
6. Smoke test UI

### PR 10 — Docs
Update [../reference/11-TECH-STACK.md](../reference/11-TECH-STACK.md) with the new versions. Mark Phase 310 COMPLETE in [../MASTER-PLAN.md](../MASTER-PLAN.md) and move this file to `phases/completed/`.

### Future — Sub-phase 310D (not part of Phase 310 delivery)
When `Pomelo.EntityFrameworkCore.MySql` 10.x ships, bundle EF Core 9 → 10 + Pomelo 9 → 10 together in a new sub-phase.

---

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| axios 1.13 → 1.15 breaks interceptors / adapter API | Smoke test axios.create flows; grep `axios.create(` and `adapter:` |
| anthropic 0.86 → 0.96 breaks call sites | Review SDK CHANGELOG; search call sites in `fed_prospector/` |
| MUI v7 → v9 visual regressions | Screenshot diff critical pages before/after; MUI codemods do most renames |
| TypeScript 6 stricter checks fail type-check | Run `tsc --noEmit` in isolation before committing |
| typescript-eslint peer range excludes TS 6 | Gate check in PR 8; split if needed |
| coverlet 10 changes coverage format | Gate on CI coverage parser; easy revert |
| npm 11 lockfile format incompatibility | Regenerate lockfile; low risk |
| Pomelo 10 never ships → stuck on EF Core 9 | Not blocking — 9.x is fully supported. Watch release notes. |

---

## Code Impact Analysis (validated 2026-04-18 via 4 exploration agents)

### Summary — risk per upgrade bundle

| Bundle | Risk | Effort | Code changes |
|--------|------|--------|--------------|
| UI security (axios, vite, dompurify) | Low | < 1 hour | None — drop-in |
| UI patch/minor (React, router, TanStack, RHF, prettier, etc.) | Low | < 1 hour | None |
| Python all | Low | < 30 minutes | 1 line (requirements.txt) |
| .NET all (excluding EF Core) | Low | < 1 hour | None — csproj bumps only |
| TypeScript 5.9 → 6.0 | Medium | 1–2 hours | Run `tsc`; audit `as any` casts |
| ESLint 9 → 10 | Low | 1 hour | Fix new `recommended` rule violations |
| coverlet.collector 8 → 10 | Low | < 15 minutes | None — CI doesn't consume coverage |
| **MUI v7 → v9** | **Medium–High** | **16–24 hours** | **~58 files, ~800 modifications** |

---

### Python: anthropic 0.86 → 0.96

- Single call site: [fed_prospector/etl/attachment_ai_analyzer.py](../../fed_prospector/etl/attachment_ai_analyzer.py) (~1,277 lines)
- Zero breaking changes across 0.87 → 0.96 changelog
- **Memory Tool NOT used** — grep for `beta.memory`, `memory_tool`, `memory=`, `local_filesystem` returned nothing. CVEs (GHSA-w828-4qhx-vxx3, GHSA-q5f5-3gjm-7mfm) don't apply to us in practice
- Stable APIs we rely on (all unchanged): `Anthropic(api_key=...)`, `client.messages.create()`, `response.content[0].text`, `response.usage.cache_read_input_tokens`, `response.usage.cache_creation_input_tokens`
- Deprecation: `claude-sonnet-4-6` marked deprecated in v0.95 (still functional; generates warnings). Model IDs referenced at lines 26–27; consider migration to `claude-sonnet-4-7` in a future phase
- **Required change:** `anthropic==0.86.0` → `anthropic==0.96.0` in `requirements.txt`
- **No exception class handling to update** — code uses generic `except Exception` blocks

### UI: axios, vite, dompurify, React, router, TanStack Query, RHF

- **Zero code changes required** for any of these bumps
- axios usage grep'd — no `axios.create({ adapter })` or custom interceptors that could break
- vite 8.0.1 → 8.0.8: patch security only, config unchanged
- dompurify: [ui/src/utils/sanitize.ts](../../ui/src/utils/sanitize.ts) uses `ALLOWED_TAGS` allowlist — unaffected by `ADD_TAGS` bypass bug
- TanStack Query 5.91 → 5.99: all minor, our code already on v5 idioms (`gcTime`, not `cacheTime`)
- React Router 7.13 → 7.14.1: patch within v7; no deprecations hit

### UI: TypeScript 5.9 → 6.0.3

- **`tsconfig` already v6-safe:** `moduleResolution: "bundler"`, no `moduleResolution: "classic"`, `strict: true` already on
- **One `as any` cast to audit:** [ui/src/pages/opportunities/DocumentIntelligenceTab.tsx](../../ui/src/pages/opportunities/DocumentIntelligenceTab.tsx) — `methodIntel[fieldKey]`. TS 6's stricter inference may reject this; replace with a proper discriminated union or index type
- **Process:** bump → `tsc --noEmit` → fix errors one file at a time → commit

### UI: ESLint 9 → 10.2.1

- **Flat config already in use** — `ui/eslint.config.js` is the only config file; no `.eslintrc*` legacy config
- **Peer-dep compatibility verified** — `typescript-eslint@8.58.2` officially supports TS 6 ✓; `eslint-plugin-react-hooks@7.1.1` supports ESLint 10 ✓
- **Expect new violations from 3 new `recommended` rules**:
  - `no-unassigned-vars`
  - `no-useless-assignment`
  - `preserve-caught-error` (may affect `catch (e)` blocks that don't re-throw)
- **Process:** bump → `npm run lint` → fix violations file-by-file → commit

### UI: MUI v7 → v9 (biggest ticket)

Dedicated sub-phase recommended — two separate PRs.

**Scope estimate:** ~58 files touched, ~800 modifications, 16–24 hours of careful work.

**Already v8-stable (no change needed):**
- Grid uses the `size={{ xs, sm }}` API throughout (`ui/src/pages/setup/CompanyBasicsStep.tsx` and ~13 others)
- [ui/src/components/shared/DataTable.tsx](../../ui/src/components/shared/DataTable.tsx) already uses `slots` API (not `components`/`componentsProps`)
- Theme definition at [ui/src/theme/theme.ts](../../ui/src/theme/theme.ts) uses stable `createTheme` and component overrides
- [ui/src/theme/ThemeContext.tsx](../../ui/src/theme/ThemeContext.tsx) uses stable `ThemeProvider` + `CssBaseline`

**Auto-fixable via `npx @mui/codemod@latest v9.0.0/preset-safe ui/src`:**
- ~50 files with icon imports (~70 icon usages)
- `components` / `componentsProps` → `slots` / `slotProps` in ~12 files (setup wizard, dialogs, pipeline)
- Common button/textfield variant prop renames

**Manual audit required — DataGrid (37 files):**
- All files importing `GridColDef`, `GridPaginationModel`, `GridSortModel` from `@mui/x-data-grid`
- Hot spots: [ui/src/components/shared/DataTable.tsx](../../ui/src/components/shared/DataTable.tsx), [ui/src/pages/prospects/ProspectPipelinePage.tsx](../../ui/src/pages/prospects/ProspectPipelinePage.tsx), [ui/src/pages/admin/UserManagementTab.tsx](../../ui/src/pages/admin/UserManagementTab.tsx), [ui/src/pages/saved-searches/SavedSearchesPage.tsx](../../ui/src/pages/saved-searches/SavedSearchesPage.tsx), all `ui/src/pages/opportunities/*Tab.tsx`
- Check: `valueGetter`/`valueSetter` signature, `hide: true` migration to `columnVisibilityModel`, `actions` column type renderers, server-mode pagination params
- Confirmed: all DataGrid usage is **community edition** (no Pro features like aggregation, Excel export, row pinning)
- [ui/src/hooks/useResponsiveColumns.ts](../../ui/src/hooks/useResponsiveColumns.ts) — verify `GridColumnVisibilityModel` API stability

**Manual audit required — Charts (8 files):**
- [ui/src/components/shared/BurnRateChart.tsx](../../ui/src/components/shared/BurnRateChart.tsx), [ui/src/components/shared/MarketShareChart.tsx](../../ui/src/components/shared/MarketShareChart.tsx), [ui/src/components/shared/SetAsideTrendChart.tsx](../../ui/src/components/shared/SetAsideTrendChart.tsx)
- [ui/src/pages/dashboard/DashboardPage.tsx](../../ui/src/pages/dashboard/DashboardPage.tsx), [ui/src/pages/pricing/BidScenarioPage.tsx](../../ui/src/pages/pricing/BidScenarioPage.tsx), [ui/src/pages/pipeline/RevenueForecastPage.tsx](../../ui/src/pages/pipeline/RevenueForecastPage.tsx), [ui/src/pages/pricing/EscalationPage.tsx](../../ui/src/pages/pricing/EscalationPage.tsx), [ui/src/pages/pricing/SubBenchmarkPage.tsx](../../ui/src/pages/pricing/SubBenchmarkPage.tsx)
- Check: responsive sizing (v9 no longer auto-sizes width — may need explicit `width` or sized container), `valueFormatter` signatures, tooltip/legend slot APIs

**Icon verification (~50 files, low risk after codemod):**
- [ui/src/components/layout/Sidebar.tsx](../../ui/src/components/layout/Sidebar.tsx) — 40+ icon imports
- [ui/src/components/layout/TopBar.tsx](../../ui/src/components/layout/TopBar.tsx) — 7 icons
- Dialogs & forms — ~15 icons scattered

**Suggested split:**
- **Sub-phase 310A-1:** codemod-only commit (safe, non-functional; one PR)
- **Sub-phase 310A-2:** DataGrid + Charts manual audit + screenshot-diff QA (one PR, requires ~1 week testing)

### .NET: coverlet.collector 8 → 10, JwtBearer/OpenApi/Swashbuckle patches

- **Zero code changes required across all .NET bumps**
- coverlet v8 → v10 (v9 skipped by maintainer): no `coverlet.runsettings`, no `coverlet.json`, no `--collect:"XPlat Code Coverage"` in CI. [.github/workflows/ci.yml](../../.github/workflows/ci.yml) runs plain `dotnet test` — coverage is not consumed anywhere. Safe drop-in
- JwtBearer custom events at [api/src/FedProspector.Api/Program.cs](../../api/src/FedProspector.Api/Program.cs):59–131 (`OnMessageReceived` cookie fallback, `OnTokenValidated` session cache) — all use stable APIs
- Microsoft.OpenApi 3.4 → 3.5: no custom `DocumentFilter`/`OperationFilter`/`SchemaFilter` in codebase — Swagger setup in `Program.cs:309–345` is vanilla Swashbuckle
- `packages.lock.json` is in source control (6 files) — will regenerate on `dotnet restore`; expect lockfile diffs in the PR
- No `Directory.Packages.props` (Central Package Management) — versions edited in each csproj directly
- `api/global.json` pins SDK `10.0.201` with `rollForward: "latestPatch"` — no conflicts

---

## Unused / Removable Dependencies (validated 2026-04-18)

Not security-related, but surfaced during the upgrade audit. Address in Phase 310 or a separate cleanup phase.

### UI — candidates for removal

| Package | Status | Recommendation |
|---------|--------|----------------|
| `@emotion/react`, `@emotion/styled` | No direct imports in `ui/src/**` — only referenced in `vite.config.ts` for chunk splitting. Also peer-deps of `@mui/material` | **Verify before removing** — MUI requires Emotion as peer; explicit pins may be intentional. If pins removed, npm will auto-resolve via MUI's peer range. Retain if the team wants explicit version control. |
| `@tanstack/react-query-devtools` | No direct imports in `ui/src/**` | **Verify** — often conditionally loaded in dev builds. If no devtools panel is wired up, safe to remove. Check if anyone on the team relies on it locally before removing. |

**Everything else in `ui/package.json` is used** — `@dnd-kit/core` + `@dnd-kit/sortable` in pipeline drag-drop, `notistack` for snackbars (20+ files), `react-error-boundary`, `zod`, `date-fns`, `@hookform/resolvers`, all build tools.

### Python — all declared deps are used

20 packages in `requirements.txt`, all actively imported (confirming import-name mismatches like `python-dotenv` → `dotenv`, `pymupdf` → `fitz`, `python-docx` → `docx`, `python-pptx` → `pptx`, `mysql-connector-python` → `mysql.connector`). Nothing to remove.

### .NET — all declared packages are used

- `Microsoft.EntityFrameworkCore.Design` appears unused in code but is **correctly declared** — it's a design-time-only tool for `dotnet ef migrations` CLI. Keep it.
- `EFCore.NamingConventions` is confirmed used via `.UseSnakeCaseNamingConvention()` in `InfrastructureServiceExtensions.cs`
- All test packages (coverlet, xunit runner, Mvc.Testing, InMemory) are used by the test runner even without explicit code references. Keep all.

### No duplicate-responsibility packages found

No two packages doing the same job across any of the three manifests.

---

## Verification

Per-PR:
- **UI:** `npm audit` → 0; `npm run build`; `tsc -b`; `npm run lint`; manual smoke
- **.NET:** `dotnet build`; `dotnet test`; manual smoke of auth + `/api/prospects`
- **Python:** `pip check`; `python -m pytest`; dry-run `python main.py load opportunity --limit 5`

End-state check after all PRs ship:
- `cd ui && npm audit` = 0 vulnerabilities
- `cd ui && npm outdated` = empty (except `@types/node` held to 22.x by choice, and any EF Core row if present)
- `pip list --outdated` = empty
- `cd api && dotnet list package --outdated` = only EF Core / Pomelo rows (held at 9.x until Pomelo ships 10)
- `cd api && dotnet list package --vulnerable` = empty
- Tech stack doc in [../reference/11-TECH-STACK.md](../reference/11-TECH-STACK.md) reflects new versions

---

## Progress Log

- **2026-04-18 — PR 1 (UI security) landed.** axios 1.13.6 (pinned) → ^1.15.0, vite 8.0.1 → 8.0.8, dompurify 3.3.3 → 3.4.0. `npm audit` UI = 0 vulns.
- **2026-04-18 — PR 2 (Python security + patch/minor) landed.** anthropic 0.86.0 → 0.96.0 (fixes GHSA-w828-4qhx-vxx3 and GHSA-q5f5-3gjm-7mfm), requests 2.32.5 → 2.33.1, lxml 6.0.2 → 6.1.0, click 8.3.1 → 8.3.2, rapidfuzz 3.14.3 → 3.14.5, pytest 9.0.2 → 9.0.3.
- **2026-04-18 — PR 3 (.NET minor/patch) landed.** JwtBearer / Mvc.Testing / Logging.Abstractions 10.0.5 → 10.0.6, Microsoft.OpenApi 3.4.0 → 3.5.2, Swashbuckle.AspNetCore 10.1.5 → 10.1.7, Microsoft.NET.Test.Sdk 18.3.0 → 18.4.0. EF Core family held at 9.x (Pomelo has no 10.x).
- **2026-04-18 — PR 4 (coverlet.collector 8 → 10) landed.** Bumped across all 3 test csproj files.
- **2026-04-18 — PR 5 (UI patch/minor non-security) landed.** react / react-dom 19.2.0 → 19.2.5, react-router-dom 7.13.1 → 7.14.1, @tanstack/react-query + devtools 5.91.x → 5.99.1, react-hook-form 7.71.2 → 7.72.1, prettier 3.8.1 → 3.8.3, globals 17.4.0 → 17.5.0, eslint-plugin-react-hooks 7.0.1 → 7.1.1, typescript-eslint 8.57.1 → 8.58.2, @mui/material + icons-material 7.3.9 → 7.3.10 (patch only; v9 deferred), @mui/x-charts + x-data-grid 8.27.5 → 8.28.2 (patch only; v9 deferred).
- **2026-04-18 — PR 6 (npm CLI bump) landed.** npm 10.9.4 → 11.12.1 on local machine.
- **2026-04-18 — PR 7 (ESLint 9 → 10) deferred.** Blocked on `eslint-plugin-jsx-a11y` ecosystem support for ESLint 10. No security pressure (ESLint 9.x has 0 open advisories). Resume when jsx-a11y ships a release with `eslint ^10` in peer range.
- **2026-04-18 — PR 8 (MUI v7 → v9) deferred to separate session.** Requires 16–24h of focused DataGrid + Charts audit; out of scope for this session.
- **2026-04-18 — PR 9 (TypeScript 5.9 → 6.0) deferred to separate session.** Sequencing rule: TS 6 ships after MUI v9 stabilizes.
- **2026-04-18 — PR 10 (Docs) in progress.** Tech stack doc and this phase file updated to reflect PRs 1–6. Phase NOT marked COMPLETE — three PRs outstanding.
- **2026-04-18 — Bonus cleanup (landed alongside PRs 1–6):**
  - Fixed compile error in `api/tests/FedProspector.Infrastructure.Tests/Services/ProspectServiceTests.cs` (missing `IPipelineService` mock).
  - Fixed 3 stale `AuthServiceTests` cases (invite code hex pattern, role rename, error text).
  - Added `FedProspector.Infrastructure.Tests` to `api/FedProspector.slnx` — previously omitted by oversight. CI now runs its 319 tests.
