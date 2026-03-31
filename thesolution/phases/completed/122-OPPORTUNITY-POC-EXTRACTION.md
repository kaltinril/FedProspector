# Phase 122: Opportunity Point of Contact Extraction

**Status:** COMPLETE
**Priority:** High -- contact data exists in raw JSON but is never extracted to the opportunity table
**Dependencies:** None

---

## Summary

The SAM.gov Opportunity API returns `pointOfContact` data (name, email, phone, fax, title) for each opportunity. This data is stored in `stg_opportunity_raw.raw_json` and the `opportunity_loader` already extracts it to the `contracting_officer` and `opportunity_poc` tables. However, the C# API and UI never expose this data to users.

## Implementation

### Tasks

- [x] **C# API**: Add `PointOfContactDto` to `OpportunityDetailDto`, query POC data via join in `GetDetailAsync`
- [x] **EF Core Model**: Add `Officer` navigation property to `OpportunityPoc`
- [x] **UI Types**: Add `PointOfContactDto` interface and `pointsOfContact` field to `OpportunityDetail`
- [x] **UI Display**: Add Points of Contact section to Overview tab with name, email, phone, fax, title, type
- [x] **Backfill CLI**: Add `python main.py backfill pocs` command to extract POC from `stg_opportunity_raw.raw_json` for opportunities missing POC records
- [x] **Build verification**: C# API builds, 612 tests pass, Python CLI --help works

### Files Changed

| File | Change |
|------|--------|
| `api/src/FedProspector.Core/Models/OpportunityPoc.cs` | Added `Officer` navigation property to `ContractingOfficer` |
| `api/src/FedProspector.Core/DTOs/Opportunities/OpportunityDetailDto.cs` | Added `PointsOfContact` list and `PointOfContactDto` class |
| `api/src/FedProspector.Infrastructure/Services/OpportunityService.cs` | Query POC data via join and include in response |
| `ui/src/types/api.ts` | Added `PointOfContactDto` interface, `pointsOfContact` to `OpportunityDetail` |
| `ui/src/pages/opportunities/OpportunityDetailPage.tsx` | Added POC display section in Overview tab |
| `fed_prospector/cli/backfill.py` | Added `backfill_pocs` command |
| `fed_prospector/main.py` | Registered `backfill pocs` command |

### Backfill Command

```bash
# Backfill POCs for all opportunities missing them
python main.py backfill pocs

# Backfill a single opportunity
python main.py backfill pocs --notice-id abc123

# Preview without writing
python main.py backfill pocs --dry-run

# Re-extract even for opportunities that already have POCs
python main.py backfill pocs --force
```

## Discovery

Sample raw JSON from `stg_opportunity_raw`:
```json
{
  "pointOfContact": [
    {
      "type": "primary",
      "fullName": "RACHEL M. OPPERMAN, N722.23, PHONE (215)697-2560",
      "email": "RACHEL.M.OPPERMAN.CIV@US.NAVY.MIL",
      "phone": null,
      "fax": null,
      "title": null
    }
  ]
}
```

Note: phone numbers are sometimes embedded in `fullName` rather than in the `phone` field.

## Known Issues

- Phone numbers embedded in fullName are not parsed out (deferred to Phase 200 contact normalization)
- The `contracting_officer` dedup key is `(full_name, email)` which may not catch all duplicates (deferred to 500E)

## Deferred to Phase 500

- `ContractingOfficer.cs` MaxLength attributes don't match DB schema (FullName 200 vs DB 500, Phone/Fax 50 vs DB 100) — pre-existing, not a regression
- No unit tests for POC join query or DTO mapping
