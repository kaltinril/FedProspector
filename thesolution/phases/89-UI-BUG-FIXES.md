# Phase 89 — UI Bug Fixes

**Status**: IN PROGRESS
**Started**: 2025-03-10

## Bug Log

### BUG-001: Entity Detail Page — 500 Internal Server Error
- **Page**: `/entities/{uei}` (Entity Detail)
- **Repro**: Navigate to any entity detail page (e.g., `/entities/DNJPS1CVCP17`)
- **Expected**: Entity details load and display
- **Actual**: "Failed to load entity. Could not retrieve entity details. The UEI may be invalid." error displayed
- **Root Cause**: `EntityService.GetDetailAsync()` queries `entity_address.address_line1` but that column does not exist in the DB table. EF Core model is out of sync with the actual MySQL schema.
  - SQL error: `Unknown column 'e.address_line1' in 'field list'`
  - Source: `EntityService.cs:197`
- **Secondary Issue**: The failed query triggers a **DbContext concurrency error** — multiple async operations are being executed on the same DbContext instance simultaneously. This means `GetDetailAsync` is firing multiple queries in parallel (e.g., with `Task.WhenAll`) instead of sequentially, violating EF Core's single-thread-per-context requirement.
- **Severity**: **Critical** — entire entity detail page is broken
- **Fix Required**:
  1. Align the EF Core `EntityAddress` model column names with the actual `entity_address` table schema (check `address_line1` vs actual column name)
  2. Fix the concurrent DbContext usage in `EntityService.GetDetailAsync()` — either await queries sequentially or use separate DbContext instances per parallel query
