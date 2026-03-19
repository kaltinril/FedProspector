# Phase 98: API Sorting Fixes

**Status**: PLANNED
**Priority**: High — sorting appears broken to end users on multiple pages

## Problem

API service sort switches only handle a subset of sortable columns. When the UI sends a sort field the API doesn't recognize, the `_ => enriched` fallback silently keeps the default sort order. Users click column headers and nothing changes.

## Scope

### OpportunityService.cs — `SearchAsync()`
- **Default sort**: `ResponseDeadline` ascending (line 91)
- **Handled**: `posteddate`, `title`
- **Missing**: `responsedeadline`, `departmentname`, `naicscode`, `baseandalloptions`, `popstate`, `solicitationnumber`
- Change default sort to `PostedDate` descending (newest first)

### OpportunityService.cs — `GetTargetsAsync()`
- **Default sort**: `DaysUntilDue` ascending (line 371)
- **Handled**: `posteddate`, `title`, `awardamount`
- **Missing**: verify UI columns match; add any missing sort fields

### OpportunityService.cs — `ExportCsvAsync()`
- **Sort**: hardcoded `OrderBy(o => o.ResponseDeadline)` ascending (line 486)
- **Fix**: respect the same sort parameters as `SearchAsync()` so export matches what the user sees

### ProspectService.cs — `SearchAsync()`
- **Handled**: `responsedeadline`, `estimatedvalue`, `gonogoscore`, `createdat`
- **Audit**: verify UI grid columns all map to a handled sort field

### EntityService.cs — `SearchAsync()`
- **Handled**: `name`/`legalbusinessname`, `lastupdatedate`, `registrationexpirationdate`
- **Audit**: verify UI grid columns all map to a handled sort field

### AwardService.cs — `SearchAsync()`
- **Handled**: `datesigned`, `baseandalloptionsvalue`/`value`, `vendorname`, `agencyname`
- **Audit**: verify UI grid columns all map to a handled sort field

## Tasks

- [ ] **OpportunityService `SearchAsync`**: Add missing sort cases, change default to `PostedDate DESC`
- [ ] **OpportunityService `GetTargetsAsync`**: Add missing sort cases
- [ ] **OpportunityService `ExportCsvAsync`**: Pass through sort params instead of hardcoded sort
- [ ] **ProspectService**: Audit UI columns vs sort switch, add any missing
- [ ] **EntityService**: Audit UI columns vs sort switch, add any missing
- [ ] **AwardService**: Audit UI columns vs sort switch, add any missing
- [ ] **Testing**: Verify sort works for each column on each page

## Files

| File | Role |
|------|------|
| `api/src/FedProspector.Infrastructure/Services/OpportunityService.cs` | Main fix target |
| `api/src/FedProspector.Infrastructure/Services/ProspectService.cs` | Audit + fix |
| `api/src/FedProspector.Infrastructure/Services/EntityService.cs` | Audit + fix |
| `api/src/FedProspector.Infrastructure/Services/AwardService.cs` | Audit + fix |
| `ui/src/pages/opportunities/OpportunitySearchPage.tsx` | Reference for column names |
| `ui/src/pages/prospects/ProspectListPage.tsx` | Reference for column names |
| `ui/src/pages/entities/EntitySearchPage.tsx` | Reference for column names |
| `ui/src/pages/awards/AwardSearchPage.tsx` | Reference for column names |

## Notes

- Sort field names from the UI are lowercased before matching (`request.SortBy.ToLowerInvariant()`)
- No centralized sort mapping exists — each service has its own switch
- Consider extracting a shared sort helper if patterns repeat, but don't over-engineer
