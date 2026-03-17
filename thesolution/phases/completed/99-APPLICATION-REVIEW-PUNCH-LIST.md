# Phase 99: Application Review Punch List

**Status**: COMPLETE
**Created**: 2026-03-16
**Source**: Automated high-level review + manual validation across all layers

---

## Summary

Full-stack skim review of the FedProspect application. Initial automated review found 109 items; manual code validation removed 13 bogus findings and downgraded 9 overstated ones, leaving 76 validated items.

**Final disposition:**
- **15 fixed** during Phase 99
- **9 moved** to Phase 500 (test coverage gaps + hardcoded paths audit)
- **52 closed** as WILL NOT ADD (cosmetic, polish, low-risk, or working-as-designed)

---

## Completed (15 items)

- ~~API-1~~: CSRF bypass on `/auth/refresh` endpoint
- ~~ETL-1~~: `get()` mutates caller's params dict
- ~~ETL-6~~: No deadlock retry in `batch_upsert.py`
- ~~ETL-11~~: 503 not retried (verified already handled)
- ~~API-11~~: CORS fallback should warn in non-dev
- ~~UI-1~~: LoginPage non-Axios error handling
- ~~UI-3~~: No axios timeout
- ~~UI-10~~: No error boundary per org tab
- ~~UI-19~~: RegisterPage complex error type guards
- ~~UI-20~~: Password validation duplicated (extracted to shared util)
- ~~UI-24~~: SET_ASIDE_OPTIONS duplicated (extracted to shared constants)
- ~~UI-25~~: buildPlaceOfPerformance duplicated (extracted to shared util)
- ~~UI-28~~: Sidebar missing `aria-current="page"`
- ~~UI-29~~: Form fields missing `autoComplete` attributes
- ~~ProposalDetailPage~~: 4 silent mutations got error/success snackbars

## Moved to Phase 500 (9 items → 500N)

- API-15: 8 intelligence services missing tests
- TEST-1 through TEST-6: Python test coverage gaps (demand_loader, resource_link_resolver, CLI commands)
- TEST-9: Pre-existing test failure (STATUS_CHANGE)
- CROSS-1: Audit for hardcoded absolute paths

## WILL NOT ADD (52 items)

Closed without action. These are cosmetic consistency fixes, UX polish, a11y nits, and low-risk tech debt that don't affect correctness, security, or user experience in any meaningful way.

**DB**: Collation inconsistency, table partitioning, FK naming, staging FKs, FK indexes, self-referencing FKs
**ETL**: Broad exception handling, connection health check, configurable batch sizes, staging batch fallback logging, error count accuracy, partial load rollback, rate counter timing, pagination cutoff, connection pool monkey-patch, pool size docs, request deduplication
**API**: Inconsistent null checks, mixed exception types, silent param coercion, rate limit magic strings, UEI/PIID validation, null request guards, Go/No-Go activity log, CSP unsafe-inline, status flow hardcoded, ForcePasswordChange paths, ReferenceController tests, FK validation before delete
**UI**: AwardDetailPage error distinction, dashboard loading skeletons, removeTeamMember error UI, refreshSession network errors, clipboard error handling, UEI format validation, searchResults local state, wizard cross-step validation, NotFoundLayout spinner, stale time documentation, mixed error patterns, TabbedDetailPage aria, DataTable skeleton/aria consistency, redundant resourceLinks types, cross-tab refresh coordination, OrgEntitiesTab useQuery, PWIN_FORMULA semantic table
**CLI**: All 8 items (error messages, exit codes, logging severity, health snapshot reporting, subprocess logging, dry-run flag duplication, late imports, business logic separation)
