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

| Package | Current Version | Project |
|---------|----------------|---------|
| AutoMapper | 16.0.0 | Core |
| BCrypt.Net-Next | 4.1.0 | Infrastructure |
| coverlet.collector | 6.0.4 | Api.Tests, Core.Tests |
| EFCore.NamingConventions | 9.0.0 | Infrastructure |
| FluentAssertions | 8.8.0 | Api.Tests, Core.Tests |
| FluentValidation | 12.1.1 | Core |
| FluentValidation.DependencyInjectionExtensions | 12.1.1 | Api |
| Microsoft.AspNetCore.Authentication.JwtBearer | 10.0.3 | Api, Infrastructure |
| Microsoft.AspNetCore.Mvc.Testing | 10.0.3 | Api.Tests |
| Microsoft.EntityFrameworkCore.Design | 9.0.7 | Api |
| Microsoft.EntityFrameworkCore.InMemory | 9.0.7 | Api.Tests |
| Microsoft.EntityFrameworkCore.Relational | 9.0.7 | Api.Tests |
| Microsoft.Extensions.Logging.Abstractions | 10.0.3 | Core.Tests |
| Microsoft.NET.Test.Sdk | 17.14.1 | Api.Tests, Core.Tests |
| Microsoft.OpenApi | 2.4.1 | Api |
| Moq | 4.20.72 | Api.Tests, Core.Tests |
| Pomelo.EntityFrameworkCore.MySql | 9.0.0 | Infrastructure |
| Serilog.AspNetCore | 10.0.0 | Api |
| Serilog.Sinks.File | 7.0.0 | Api |
| Swashbuckle.AspNetCore | 10.1.4 | Api |
| xunit | 2.9.3 | Api.Tests, Core.Tests |
| xunit.runner.visualstudio | 3.1.4 | Api.Tests, Core.Tests |

### Node.js / React (npm)

| Package | Current Version | Type |
|---------|----------------|------|
| @dnd-kit/core | ^6.3.1 | dep |
| @dnd-kit/sortable | ^10.0.0 | dep |
| @emotion/react | ^11.14.0 | dep |
| @emotion/styled | ^11.14.1 | dep |
| @hookform/resolvers | ^5.2.2 | dep |
| @mui/icons-material | ^7.3.9 | dep |
| @mui/material | ^7.3.9 | dep |
| @mui/x-charts | ^8.27.4 | dep |
| @mui/x-data-grid | ^8.27.4 | dep |
| @tanstack/react-query | ^5.90.21 | dep |
| @tanstack/react-query-devtools | ^5.91.3 | dep |
| axios | ^1.13.6 | dep |
| date-fns | ^4.1.0 | dep |
| dompurify | ^3.3.2 | dep |
| notistack | ^3.0.2 | dep |
| react | ^19.2.0 | dep |
| react-dom | ^19.2.0 | dep |
| react-error-boundary | ^6.1.1 | dep |
| react-hook-form | ^7.71.2 | dep |
| react-router-dom | ^7.13.1 | dep |
| zod | ^4.3.6 | dep |
| @eslint/js | ^9.39.1 | devDep |
| @types/dompurify | ^3.0.5 | devDep |
| @types/node | ^22.0.0 | devDep |
| @types/react | ^19.2.7 | devDep |
| @types/react-dom | ^19.2.3 | devDep |
| @typescript-eslint/eslint-plugin | ^8.56.1 | devDep |
| @typescript-eslint/parser | ^8.56.1 | devDep |
| @vitejs/plugin-react | ^5.1.4 | devDep |
| eslint | ^9.39.3 | devDep |
| eslint-plugin-jsx-a11y | ^6.10.2 | devDep |
| eslint-plugin-react-hooks | ^7.0.1 | devDep |
| eslint-plugin-react-refresh | ^0.4.24 | devDep |
| globals | ^16.5.0 | devDep |
| prettier | ^3.8.1 | devDep |
| typescript | ~5.9.3 | devDep |
| typescript-eslint | ^8.48.0 | devDep |
| rollup-plugin-visualizer | ^5.14.0 | devDep |
| vite | ^7.3.1 | devDep |

### Python (pip)

| Package | Current Version |
|---------|----------------|
| requests | 2.32.5 |
| mysql-connector-python | 9.6.0 |
| python-dotenv | 1.2.1 |
| lxml | 6.0.2 |
| apscheduler | 3.11.2 |
| click | 8.3.1 |
| tqdm | 4.67.3 |
| ijson | 3.4.0.post0 |
| bcrypt | 5.0.0 |

## Tasks

| # | Task | Status |
|---|------|--------|
| 102-1 | Audit C# NuGet packages for available stable updates | TODO |
| 102-2 | Update NuGet packages and fix breaking changes | TODO |
| 102-3 | Audit npm packages for available stable updates | TODO |
| 102-4 | Update npm packages and fix breaking changes | TODO |
| 102-5 | Audit Python packages for available stable updates | TODO |
| 102-6 | Update Python packages and fix breaking changes | TODO |
| 102-7 | Run full test suite (C# + Python) and verify builds | TODO |
| 102-8 | Manual smoke test of UI and API | TODO |

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

## Known Issue Driving This Phase

AutoMapper 16.0.0 has CVE GHSA-rvv3-g6hj-g44x (high severity). This shows as a build warning on every build.
