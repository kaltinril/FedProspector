# Phase 102: Dependency Updates -- Stable/LTS Versions

## Goal

Update all packages across Python, C# (.NET), and Node.js/React to the highest stable/LTS versions available. No beta, RC, preview, or early-access releases. Fix any breaking changes introduced by the upgrades.

## Constraints

- **Stable releases only** -- no pre-release, beta, RC, or preview versions
- **LTS-track preferred** -- when a package offers LTS vs Current, prefer LTS
- **.NET**: Stay on the current target framework unless an LTS version is available (check if .NET 10 is LTS or if we should target .NET 9 LTS)
- **Node.js**: Already on 22.x (LTS). No change needed unless a newer LTS is available.
- **Python**: Already on 3.14.x. No change unless stability requires it.
- **Test after each major upgrade** -- don't batch all upgrades without testing

## Current Package Inventory

### C# / .NET (NuGet)

Target framework: `net10.0` (all projects)

| Package | Old Version | New Version | Project |
|---------|-------------|-------------|---------|
| AutoMapper | 16.0.0 | **16.1.1** | Core |
| BCrypt.Net-Next | 4.1.0 | 4.1.0 (latest) | Infrastructure |
| coverlet.collector | 6.0.4 | **8.0.1** | Api.Tests, Core.Tests |
| EFCore.NamingConventions | 9.0.0 | 9.0.0 (blocked) | Infrastructure |
| FluentAssertions | 8.8.0 | **8.9.0** | Api.Tests, Core.Tests |
| FluentValidation | 12.1.1 | 12.1.1 (latest) | Core |
| FluentValidation.DependencyInjectionExtensions | 12.1.1 | 12.1.1 (latest) | Api |
| Microsoft.AspNetCore.Authentication.JwtBearer | 10.0.3 | **10.0.5** | Api, Infrastructure |
| Microsoft.AspNetCore.Mvc.Testing | 10.0.3 | **10.0.5** | Api.Tests |
| Microsoft.EntityFrameworkCore.Design | 9.0.7 | 9.0.7 (blocked) | Api |
| Microsoft.EntityFrameworkCore.InMemory | 9.0.7 | 9.0.7 (blocked) | Api.Tests |
| Microsoft.EntityFrameworkCore.Relational | 9.0.7 | 9.0.7 (blocked) | Api.Tests |
| Microsoft.Extensions.Logging.Abstractions | 10.0.3 | **10.0.5** | Core.Tests |
| Microsoft.NET.Test.Sdk | 17.14.1 | **18.3.0** | Api.Tests, Core.Tests |
| Microsoft.OpenApi | 2.4.1 | **3.4.0** | Api |
| Moq | 4.20.72 | 4.20.72 (latest) | Api.Tests, Core.Tests |
| Pomelo.EntityFrameworkCore.MySql | 9.0.0 | 9.0.0 (blocked) | Infrastructure |
| Serilog.AspNetCore | 10.0.0 | 10.0.0 (latest) | Api |
| Serilog.Sinks.File | 7.0.0 | 7.0.0 (latest) | Api |
| Swashbuckle.AspNetCore | 10.1.4 | **10.1.5** | Api |
| xunit | 2.9.3 | 2.9.3 (latest) | Api.Tests, Core.Tests |
| xunit.runner.visualstudio | 3.1.4 | **3.1.5** | Api.Tests, Core.Tests |

**NOT upgraded (blocked):** EF Core stack (Design 9.0.7, InMemory 9.0.7, Relational 9.0.7, NamingConventions 9.0.0) -- Pomelo.EntityFrameworkCore.MySql has no 10.x release yet. All other packages were already at latest.

### Node.js / React (npm)

| Package | Old Version | New Version | Type |
|---------|-------------|-------------|------|
| @dnd-kit/core | ^6.3.1 | ^6.3.1 (latest) | dep |
| @dnd-kit/sortable | ^10.0.0 | ^10.0.0 (latest) | dep |
| @emotion/react | ^11.14.0 | ^11.14.0 (latest) | dep |
| @emotion/styled | ^11.14.1 | ^11.14.1 (latest) | dep |
| @hookform/resolvers | ^5.2.2 | ^5.2.2 (latest) | dep |
| @mui/icons-material | ^7.3.9 | ^7.3.9 (latest) | dep |
| @mui/material | ^7.3.9 | ^7.3.9 (latest) | dep |
| @mui/x-charts | ^8.27.4 | **^8.27.5** | dep |
| @mui/x-data-grid | ^8.27.4 | **^8.27.5** | dep |
| @tanstack/react-query | ^5.90.21 | **^5.91.2** | dep |
| @tanstack/react-query-devtools | ^5.91.3 | ^5.91.3 (latest) | dep |
| axios | ^1.13.6 | ^1.13.6 (latest) | dep |
| date-fns | ^4.1.0 | ^4.1.0 (latest) | dep |
| dompurify | ^3.3.2 | **^3.3.3** | dep |
| notistack | ^3.0.2 | ^3.0.2 (latest) | dep |
| react | ^19.2.0 | ^19.2.0 (latest) | dep |
| react-dom | ^19.2.0 | ^19.2.0 (latest) | dep |
| react-error-boundary | ^6.1.1 | ^6.1.1 (latest) | dep |
| react-hook-form | ^7.71.2 | ^7.71.2 (latest) | dep |
| react-router-dom | ^7.13.1 | ^7.13.1 (latest) | dep |
| zod | ^4.3.6 | ^4.3.6 (latest) | dep |
| @eslint/js | ^9.39.1 | **^9.39.4** | devDep |
| @types/node | ^22.0.0 | ^22.0.0 (latest for Node 22) | devDep |
| @types/react | ^19.2.7 | **^19.2.14** | devDep |
| @types/react-dom | ^19.2.3 | ^19.2.3 (latest) | devDep |
| @vitejs/plugin-react | ^5.1.4 | **^6.0.1** | devDep |
| eslint | ^9.39.3 | **^9.39.4** | devDep |
| eslint-plugin-jsx-a11y | ^6.10.2 | ^6.10.2 (latest) | devDep |
| eslint-plugin-react-hooks | ^7.0.1 | ^7.0.1 (latest) | devDep |
| eslint-plugin-react-refresh | ^0.4.24 | **^0.5.2** | devDep |
| globals | ^16.5.0 | **^17.4.0** | devDep |
| prettier | ^3.8.1 | ^3.8.1 (latest) | devDep |
| typescript | ~5.9.3 | ~5.9.3 (latest) | devDep |
| typescript-eslint | ^8.48.0 | **^8.57.1** | devDep |
| rollup-plugin-visualizer | ^5.14.0 | **^7.0.1** | devDep |
| vite | ^7.3.1 | **^8.0.1** | devDep |

**Removed:** @types/dompurify (deprecated), @typescript-eslint/eslint-plugin (redundant), @typescript-eslint/parser (redundant)

**NOT upgraded:** eslint 10 (plugins don't support it yet), @types/node 25 (project runs Node 22)

**Breaking change fixed:** vite.config.ts `manualChunks` changed from object to function syntax for Vite 8/Rolldown.

### Python (pip)

| Package | Old Version | New Version |
|---------|-------------|-------------|
| requests | 2.32.5 | 2.32.5 (latest) |
| mysql-connector-python | 9.6.0 | 9.6.0 (latest) |
| python-dotenv | 1.2.1 | **1.2.2** |
| lxml | 6.0.2 | 6.0.2 (latest) |
| apscheduler | 3.11.2 | 3.11.2 (latest) |
| click | 8.3.1 | 8.3.1 (latest) |
| tqdm | 4.67.3 | 4.67.3 (latest) |
| ijson | 3.4.0.post0 | **3.5.0** |
| bcrypt | 5.0.0 | 5.0.0 (latest) |
| certifi | 2026.1.4 | **2026.2.25** (transitive) |
| charset-normalizer | 3.4.4 | **3.4.6** (transitive) |

All other Python packages already at latest stable.

## Tasks

| # | Task | Status |
|---|------|--------|
| 102-1 | Audit C# NuGet packages for available stable updates | DONE |
| 102-2 | Update NuGet packages and fix breaking changes | DONE |
| 102-3 | Audit npm packages for available stable updates | DONE |
| 102-4 | Update npm packages and fix breaking changes | DONE |
| 102-5 | Audit Python packages for available stable updates | DONE |
| 102-6 | Update Python packages and fix breaking changes | DONE |
| 102-7 | Run full test suite (C# + Python) and verify builds | DONE |
| 102-8 | Manual smoke test of UI and API | DONE |

### 102-1: Audit C# NuGet Packages

Run `dotnet list package --outdated` for each project. Document which packages have stable updates available. Flag any major version bumps that may have breaking changes (especially AutoMapper 16.x which has a known vulnerability).

### 102-2: Update NuGet Packages

Update packages one major-version-bump at a time. Run `dotnet build` and `dotnet test` after each update. Fix any breaking API changes.

Priority: AutoMapper (has known CVE), then other packages by severity.

### 102-3: Audit npm Packages

Run `npm outdated` in the `ui/` directory. Document which packages have stable updates. Pay attention to:
- React and react-dom (currently on 19.x)
- MUI v7 packages
- TanStack Query v5
- Vite 7
- TypeScript

### 102-4: Update npm Packages

Update packages. Run `npm run build` and check for TypeScript errors after each update.

### 102-5: Audit Python Packages

Check current Python packages against PyPI for stable updates.

### 102-6: Update Python Packages

Update packages. Run `pytest` after updates.

### 102-7: Full Test Suite

Run all tests:
- `cd api && dotnet test`
- `cd fed_prospector && pytest`
- `cd ui && npm run build`

### 102-8: Manual Smoke Test

Start all services and verify basic functionality works end-to-end.

## Results

### Test Results

- **C#:** 577 passed, 0 failed
- **Python:** 632 passed, 1 failed (pre-existing STATUS_CHANGE test in test_prospect_manager.py, not from upgrades)
- **npm:** `tsc --noEmit` clean, `npm run build` success, `npm audit` 0 vulnerabilities

### Key Outcomes

- **AutoMapper CVE fixed** -- upgraded 16.0.0 to 16.1.1, eliminating GHSA-rvv3-g6hj-g44x build warning
- **Vite 8 with Rolldown bundler** -- build time dropped from ~33s to <1s; required `manualChunks` syntax change from object to function
- **EF Core blocked at 9.x** -- Pomelo.EntityFrameworkCore.MySql has no 10.x release; EF Core stack stays at 9.0.7/9.0.0 until Pomelo ships a compatible version
- **Removed 3 redundant npm packages** -- @types/dompurify (deprecated), @typescript-eslint/eslint-plugin and @typescript-eslint/parser (subsumed by typescript-eslint)
- **No breaking changes** beyond the Vite 8 manualChunks syntax fix

## Known Issue Driving This Phase

AutoMapper 16.0.0 has CVE GHSA-rvv3-g6hj-g44x (high severity). This shows as a build warning on every build. **Resolved** by upgrading to 16.1.1.
