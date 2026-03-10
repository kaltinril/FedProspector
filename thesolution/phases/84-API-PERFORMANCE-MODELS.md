# Phase 84: App API Performance & Model Completeness

**Status**: PLANNED
**Priority**: HIGH
**Depends on**: Phase 81 (for schema fixes that affect models)

## Overview
Review identified N+1 query problems, missing EF Core model properties, missing navigation properties, unbounded queries, and exception handling gaps in the C# ASP.NET Core API. These affect performance at scale and data accessibility.

## Issues

### CRITICAL

#### 84-1: N+1 Query — AwardService.SearchAsync PSC Subquery
- **File**: `api/src/FedProspector.Infrastructure/Services/AwardService.cs` lines 115-119
- **Issue**: Per-row subquery for PSC description: `_context.RefPscCodes.Where(p => p.PscCode == x.Contract.PscCode)...FirstOrDefault()`. With 20 results per page, fires 20 additional queries.
- **Fix**: Batch-load PSC descriptions before projection. Or add navigation property `FpdsContract.RefPscCode` with `Include()`.

#### 84-2: N+1 Query — EntityService.SearchAsync PopState Subquery
- **File**: `api/src/FedProspector.Infrastructure/Services/EntityService.cs` lines 77-96
- **Issue**: Per-row subquery to EntityAddresses for PopState: `_context.EntityAddresses.Where(a => a.UeiSam == e.UeiSam && a.AddressType == "PHYSICAL")...FirstOrDefault()`. At scale (50+ entities), 50+ additional queries.
- **Fix**: Use grouped JOIN in the main query or add navigation property with Include.

#### 84-3: N+1 Query — EntityService.GetDetailAsync PSC Descriptions
- **File**: `api/src/FedProspector.Infrastructure/Services/EntityService.cs` lines 146-157
- **Issue**: Per-PSC-code subquery for description. Entity with 5-20 PSC codes fires 5-20 additional queries.
- **Fix**: Single JOIN to RefPscCodes. Or batch-load descriptions for all PSC codes at once.

#### 84-4: Missing Navigation Properties (8+ models)
- **Files**: Multiple models in `api/src/FedProspector.Core/Models/`
- **Missing**:
  - `Proposal` -> `Prospect` (has FK ProspectId but no navigation)
  - `ProspectNote` -> `Prospect`, `AppUser` (has FKs but no navigation)
  - `ProspectTeamMember` -> `Prospect`, `AppUser` (has FKs but no navigation)
  - `OpportunityPoc` -> `Opportunity`, `ContractingOfficer` (has FKs but no navigation)
  - `SavedSearch` -> `AppUser` (has UserId but no navigation)
  - `ActivityLog` -> `AppUser` (has UserId but no navigation)
  - `OrganizationInvite` -> `AppUser` (has InvitedBy but no navigation)
- **Impact**: Services must use manual JOINs instead of Include(). N+1 risk in detail endpoints.
- **Fix**: Add `[ForeignKey("...")]` navigation properties to all child models. Update DbContext OnModelCreating if needed.

### HIGH

#### 84-5: Missing Model Properties — Schema Drift
- **Files**:
  - `Entity.cs` missing `EftIndicator` (DDL: `20_entity.sql:52` has `eft_indicator VARCHAR(10)`)
  - `FpdsContract.cs` missing `FundingSubtierCode`, `FundingSubtierName` (DDL: `40_federal.sql:43-44`)
- **Issue**: ETL-loaded data inaccessible via API. Data silently dropped on EF Core reads.
- **Fix**: Add properties with `[Column("...")]` attributes.

#### 84-6: Prospect Missing AssignedToUser/CaptureManagerUser Navigation
- **File**: `api/src/FedProspector.Core/Models/Prospect.cs` lines 20-22, 75-77
- **Issue**: FKs `AssignedTo` and `CaptureManagerId` exist but no navigation properties. DashboardService (line 85) does manual JOINs.
- **Fix**: Add `public AppUser? AssignedToUser { get; set; }` and `public AppUser? CaptureManagerUser { get; set; }`.

#### 84-7: Unbounded Query in OpportunityService.GetDetailAsync
- **File**: `api/src/FedProspector.Infrastructure/Services/OpportunityService.cs` lines 147-200
- **Issue**: Multiple multi-table joins without explicit limits in composition. At scale, complex JOIN chains cause performance degradation.
- **Fix**: Profile query execution plan. Consider denormalized views or limit related entity counts.

#### 84-8: CSV Export No Size Limit
- **File**: `api/src/FedProspector.Api/Controllers/OpportunitiesController.cs` lines 82-91
- **Issue**: `ExportCsv` has no PageSize limit. Could export unbounded result sets causing OOM.
- **Fix**: Enforce hard limit (e.g., 5000 rows max). Return 400 if exceeded.

### MEDIUM

#### 84-9: Inadequate Exception Handler Mapping
- **File**: `api/src/FedProspector.Api/Middleware/ExceptionHandlerMiddleware.cs` lines 25-32
- **Issue**: Only handles 4 exception types. All others map to 500. ValidationException, business rule violations all return 500.
- **Fix**: Add mappings: `ValidationException -> 400`, `ArgumentException -> 400`, `TimeoutException -> 504`.

#### 84-10: Inconsistent Pagination Limits
- **Files**: Multiple controllers
- **Issue**: Page size validated differently: some allow 50, some 100, some have no upper limit.
- **Fix**: Define `MAX_PAGE_SIZE = 100` constant. Apply consistently across all search endpoints via base validator.

#### 84-11: Incomplete AutoMapper Configuration
- **File**: `api/src/FedProspector.Core/Mapping/MappingProfile.cs`
- **Issue**: Only 7 mappings defined. 20+ services manually project DTOs in LINQ. Maintenance burden; inconsistent DTO construction.
- **Fix**: Consolidate all model-> DTO mappings. Use `IMapper.ProjectTo<T>()` in queries where possible.

#### 84-12: Unvalidated Enum-Like String Fields
- **Files**: ProspectService, AwardService, etc.
- **Issue**: Status, Priority, OrgRole, NoteType stored as strings. No validation that values match allowed set.
- **Fix**: Create C# enums. Validate in FluentValidation rules. Consider DB CHECK constraints.

#### 84-13: Session Validation Race Condition
- **File**: `api/src/FedProspector.Api/Program.cs` lines 70-108
- **Issue**: `OnTokenValidated` queries AppSessions synchronously. No locking. Concurrent requests with same token validate simultaneously before revocation persists.
- **Fix**: Add DB-level unique constraint on TokenHash. Cache session validity with short TTL (30s).

#### 84-14: Session Validation DB Query Per Request
- **File**: `api/src/FedProspector.Api/Program.cs` lines 71-107
- **Issue**: Every authenticated request queries DB to validate session. High DB load for active users.
- **Fix**: Cache revocation status in memory cache with 30-60s TTL. Fallback to DB on cache miss.

#### 84-15: Missing Multi-Tenancy Assertions
- **File**: `api/src/FedProspector.Api/Controllers/OpportunitiesController.cs` lines 36-44
- **Issue**: organizationId is optional when passed to service. No assertion that search respects org isolation.
- **Fix**: Add guard: `if (organizationId == null) return Unauthorized()`. Or enforce in service layer consistently.

### LOW

#### 84-16: Health Check Uses Raw SQL
- **File**: `api/src/FedProspector.Api/Controllers/HealthController.cs` lines 74-76
- **Issue**: Hardcoded SQL instead of EF Core query. Inconsistent with rest of codebase.
- **Fix**: Replace with EF Core LINQ query.

#### 84-17: Missing Cascade Deletes on Prospect Children
- **File**: `api/src/FedProspector.Infrastructure/Data/FedProspectorDbContext.cs` lines 252-256
- **Issue**: Prospect has Restrict delete for org. No cascade for ProspectNote, ProspectTeamMember, Proposal.
- **Fix**: Add cascade deletes in OnModelCreating.

#### 84-18: No Graceful Shutdown Handling
- **File**: `api/src/FedProspector.Api/Program.cs` line 350
- **Issue**: `app.Run()` with no cancellation token. Long-running requests may be terminated during deployment.
- **Fix**: Add cancellation token support. Implement shutdown handler.

## Verification
1. All C# tests pass: `dotnet test api/tests/ --verbosity normal`
2. Run SQL profiler during entity search — verify single query (no N+1)
3. Run SQL profiler during award search — verify single query
4. Verify all new navigation properties work with Include()
5. Test CSV export with limit exceeded — verify 400 response
6. Test session caching — verify DB query reduction
