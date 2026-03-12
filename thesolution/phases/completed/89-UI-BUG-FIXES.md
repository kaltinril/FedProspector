# Phase 89 — UI Bug Fixes

## Status: COMPLETE

**Priority**: HIGH
**Depends on**: Phase 88
**Started**: 2025-03-10
**Completed**: 2026-03-11

---

## Completion Summary

Phase 89 fixed 5 bugs discovered during UI testing, plus pre-existing test failures. All bugs were EF Core model mismatches or concurrency issues — no frontend changes required.

| Bug | Severity | Status | Summary |
|-----|----------|--------|---------|
| BUG-001 | Critical | FIXED | Entity detail page 500 error (column name + DbContext concurrency) |
| BUG-002 | High | FIXED | AdminService DbContext concurrency |
| BUG-003 | High | FIXED | MaxLength mismatches on 6 columns |
| BUG-004 | Medium | FIXED | Prospect unique constraint (single vs composite) |
| BUG-005 | High | FIXED | UsaspendingAward missing soft-delete filter |

Pre-existing test fixes: 14 C# tests (AwardServiceTests) + 14 Python tests.

---

## Bug Details

### BUG-001: Entity Detail Page — 500 Internal Server Error (Critical — FIXED)

- **Page**: `/entities/{uei}` (Entity Detail)
- **Symptom**: "Failed to load entity" error on every entity detail page
- **Root Cause A**: EF Core snake_case naming convention produced `address_line1` but MySQL column is `address_line_1`. Same for `AddressLine2`. Affected `EntityAddress.cs` and `EntityPoc.cs` (4 properties total).
- **Fix**: Added explicit `[Column("address_line_1")]` and `[Column("address_line_2")]` attributes.
- **Root Cause B**: `EntityService.GetDetailAsync()` ran 6 async queries via `Task.WhenAll` on a shared DbContext (not thread-safe).
- **Fix**: Replaced with sequential awaits.

### BUG-002: AdminService DbContext Concurrency (High — FIXED)

- `AdminService.GetEtlStatusAsync()` ran 3 async queries via `Task.WhenAll` on shared DbContext.
- **Fix**: Replaced with sequential awaits.

### BUG-003: MaxLength Mismatches (High — FIXED)

EF Core `[MaxLength]` attributes were smaller than actual MySQL column sizes, causing silent truncation or insert failures:

| Model.Property | Old MaxLength | New MaxLength |
|----------------|---------------|---------------|
| `FpdsContract.ContractId` | 50 | 100 |
| `FpdsContract.ModificationNumber` | 10 | 25 |
| `FpdsContract.SolicitationNumber` | 100 | 200 |
| `Opportunity.AwardNumber` | 50 | 200 |
| `UsaspendingAward.TypeOfSetAside` | 50 | 100 |
| `UsaspendingAward.SolicitationIdentifier` | 50 | 100 |

### BUG-004: Prospect Unique Constraint (Medium — FIXED)

- DbContext had single-column unique index on `NoticeId`, but DDL defines composite `(organization_id, notice_id)`.
- **Fix**: Changed to composite index matching the DDL.

### BUG-005: UsaspendingAward Missing Soft-Delete (High — FIXED)

- `UsaspendingAward` model lacked `DeletedAt` property, so soft-deleted rows leaked into queries.
- **Fix**: Added `DeletedAt` property + global query filter `HasQueryFilter(a => a.DeletedAt == null)`.

---

## Pre-existing Test Fixes

### C# Tests
- Fixed `AwardServiceTests.cs` compilation errors (14 tests now pass).

### Python Tests
- Fixed 14 test failures caused by CLI help text drift, method signature changes, and index count drift.

### Remaining Known Pre-existing Failures (Not Phase 89 Scope)
- 2 AuthService test failures
- 1 STATUS_CHANGE test failure (`test_all_valid_note_types_accepted[STATUS_CHANGE]`)

---

## Verification Checklist

- [x] BUG-001: Entity detail page loads without 500 error
- [x] BUG-002: Admin ETL status loads without concurrency error
- [x] BUG-003: MaxLength attributes match MySQL column sizes
- [x] BUG-004: Prospect unique constraint is composite (organization_id, notice_id)
- [x] BUG-005: Soft-deleted UsaspendingAward rows filtered from queries
- [x] AwardServiceTests: 14 tests compile and pass
- [x] Python tests: 14 previously-failing tests now pass
