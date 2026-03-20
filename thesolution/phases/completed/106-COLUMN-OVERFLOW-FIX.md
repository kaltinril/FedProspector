# Phase 106: Column Overflow Fix

## Status: COMPLETE

## Problem

SAM.gov opportunity loads fail with:
```
1406 (22001): Data too long for column 'phone' at row 1
```

The `contracting_officer.phone` column is `VARCHAR(50)`, which can be exceeded by phone numbers with extensions, country codes, or embedded notes from SAM.gov. The same risk exists for `fax` and potentially other string columns.

The error-enrichment code in `opportunity_loader.py` misreports `len=0, value=None` because it looks up the column value in the opportunity dict rather than the POC dict where phone/fax live.

## Root Cause

- `contracting_officer.phone` and `fax` are `VARCHAR(50)` — too narrow for some SAM.gov data
- No defensive truncation before INSERT

## Fix

### 1. Widen columns (DDL + live DB)
```sql
ALTER TABLE contracting_officer MODIFY COLUMN phone VARCHAR(100);
ALTER TABLE contracting_officer MODIFY COLUMN fax VARCHAR(100);
```

### 2. Add defensive truncation in loader
In `opportunity_loader.py`, truncate phone/fax/email to their column limits before upsert so oversized data degrades gracefully instead of erroring.

### 3. Fix error enrichment
The row-by-row fallback error handler should look up the failing column value from the correct dict (POC data, not opportunity data) for contracting_officer inserts.

## Files Changed

| File | Change |
|------|--------|
| `fed_prospector/db/schema/tables/90_web_api.sql` | Widen phone/fax to VARCHAR(100) |
| `fed_prospector/etl/opportunity_loader.py` | Add truncation + fix error enrichment |
| Live DB `fed_contracts` | ALTER TABLE |

## Testing

- Re-run the load that failed (offset 16000 batch)
- Verify no more 1406 errors
