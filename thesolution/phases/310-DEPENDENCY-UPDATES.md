# Phase 310: Dependency Updates & Package Maintenance

**Status:** PLANNED
**Priority:** HIGH for security fixes (axios CRITICAL, vite HIGH), MEDIUM for version bumps
**Dependencies:** None

---

## Summary

Security audit found 2 UI vulnerabilities (axios CRITICAL SSRF, vite HIGH path traversal). EF Core is a major version behind the .NET 10 runtime. Multiple packages have minor/patch updates available. npm major version update is NOT urgent (npm 11 ships with Node 24, not Node 22).

---

## Security Fixes — Do First

### axios 1.13.6 → 1.15.0 (CRITICAL)
- **GHSA-3p68-rc4w-qgx5**: NO_PROXY Hostname Normalization Bypass leads to SSRF
- Pinned exact in package.json — needs manual version bump
- Fix: Change `"axios": "1.13.6"` to `"axios": "1.15.0"` in `ui/package.json`

### vite 8.0.1 → 8.0.8 (HIGH — 3 advisories)
- Path Traversal in Optimized Deps `.map` Handling
- `server.fs.deny` bypassed with queries
- Arbitrary File Read via Vite Dev Server WebSocket
- Within semver range — fixable with `npm audit fix`

### cryptography 46.0.6 → 46.0.7 (Python, patch)
- Security-critical package, patch updates often address CVEs
- Fix: `pip install cryptography==46.0.7`

---

## UI Dependencies (ui/package.json)

### Immediate (security + patch)
| Package | Current | Target | Type | Notes |
|---------|---------|--------|------|-------|
| axios | 1.13.6 | 1.15.0 | **CRITICAL security** | SSRF vuln, pinned exact — manual bump |
| vite | ^8.0.1 | 8.0.8 | **HIGH security** | 3 advisories, `npm audit fix` |
| react | ^19.2.0 | 19.2.5 | Patch | |
| react-dom | ^19.2.0 | 19.2.5 | Patch | |
| react-hook-form | ^7.71.2 | 7.72.1 | Patch | |
| react-router-dom | ^7.13.1 | 7.14.0 | Minor | |
| @tanstack/react-query | ^5.91.2 | 5.97.0 | Minor | |
| typescript-eslint | ^8.57.1 | 8.58.1 | Patch | |

### Major version bumps (evaluate separately)
| Package | Current | Latest | Notes |
|---------|---------|--------|-------|
| @mui/material | ^7.3.9 | **9.0.0** | MUI v7 → v9 — full migration needed |
| @mui/icons-material | ^7.3.9 | **9.0.0** | Must match @mui/material |
| @mui/x-data-grid | ^8.27.5 | **9.0.1** | Grid API may have breaking changes |
| @mui/x-charts | ^8.27.5 | **9.0.1** | Chart API may change |
| typescript | ~5.9.3 | **6.0.2** | First TS 6.x — compiler changes likely |
| eslint | 9.39.4 | **10.2.0** | Config format may change |
| @eslint/js | 9.39.4 | **10.0.1** | Must match eslint |

### Not urgent
| Package | Current | Latest | Notes |
|---------|---------|--------|-------|
| npm | 10.9.4 | 11.12.1 | Ships with Node 24, not Node 22. No urgency. |
| @types/node | ^22.0.0 | 25.5.2 | Type defs only — safe but unnecessary on Node 22 |

---

## .NET Dependencies (api/)

### EF Core alignment (major bump)
| Package | Current | Latest | Notes |
|---------|---------|--------|-------|
| Microsoft.EntityFrameworkCore.Design | 9.0.7 | **10.0.5** | App targets net10.0 — EF Core should match |
| EFCore.NamingConventions | 9.0.0 | **10.0.1** | Must match EF Core version |
| Microsoft.EntityFrameworkCore.InMemory | 9.0.7 | **10.0.5** | Test project |
| Microsoft.EntityFrameworkCore.Relational | 9.0.7 | **10.0.5** | Test project |

### Minor/patch
| Package | Current | Latest | Notes |
|---------|---------|--------|-------|
| Microsoft.OpenApi | 3.4.0 | 3.5.1 | Minor |
| Swashbuckle.AspNetCore | 10.1.5 | 10.1.7 | Patch |
| Microsoft.NET.Test.Sdk | 18.3.0 | 18.4.0 | Minor |

**No known vulnerabilities** in any .NET package.

---

## Python Dependencies (fed_prospector/requirements.txt)

| Package | Current | Latest | Type | Notes |
|---------|---------|--------|------|-------|
| cryptography | 46.0.6 | 46.0.7 | **Security patch** | Update first |
| anthropic | 0.86.0 | 0.93.0 | Minor (7 behind) | SDK changes possible |
| requests | 2.32.5 | 2.33.1 | Minor | HTTP library |
| click | 8.3.1 | 8.3.2 | Patch | CLI framework |
| lxml | 6.0.2 | 6.0.3 | Patch | |
| pytest | 9.0.2 | 9.0.3 | Patch | |
| rapidfuzz | 3.14.3 | 3.14.5 | Patch | |
| pillow | 12.1.1 | 12.2.0 | Minor | |
| pydantic_core | 2.41.5 | 2.45.0 | Minor | Pulled by anthropic |
| pip | 25.3 | 26.0.1 | Major | Review release notes |
| tzdata | 2025.3 | 2026.1 | Data update | Timezone definitions |

**No dependency conflicts.** mysql-connector-python already at latest.

---

## Build Order

1. **Security fixes** — axios, vite, cryptography (do immediately)
2. **Python patch/minor updates** — low risk, `pip install -r requirements.txt`
3. **.NET EF Core 9 → 10** — aligns ORM with runtime, test with `dotnet build` + integration
4. **.NET minor/patch** — OpenApi, Swashbuckle, Test.Sdk
5. **UI patch/minor** — react, react-router, TanStack, etc.
6. **MUI v9 migration** — largest effort, separate sub-phase if needed
7. **TypeScript 6** — evaluate breaking changes before upgrading
8. **ESLint 10** — evaluate config format changes
9. **Update tech stack docs** — `thesolution/reference/11-TECH-STACK.md`

---

## Risks

- **axios bump** changes semver pin — verify SSRF protection code in attachment_downloader.py still works (it validates Content-Type and URL prefixes)
- **EF Core 9 → 10** may have breaking changes in query translation or migration format
- **Pomelo.EntityFrameworkCore.MySql** must stay compatible with chosen EF Core version — check their compatibility matrix
- **MUI v9** is a full major release — likely needs component API changes, theme updates. Scope as separate sub-phase.
- **TypeScript 6** — first major release, stricter checks likely. May surface new type errors.

---

## Testing

1. `npm audit` — zero high/critical after security fixes
2. `npm run build && tsc -b` — UI builds clean
3. `dotnet build` — all C# projects build
4. `dotnet test` — C# tests pass
5. `python -m pytest` — Python tests pass
6. `pip check` — no dependency conflicts
7. Manual smoke test of key pages after MUI/EF Core updates
