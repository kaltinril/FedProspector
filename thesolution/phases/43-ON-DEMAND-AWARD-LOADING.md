# Phase 43: On-Demand Award Loading

**Status**: COMPLETE
**Depends on**: Phase 42 (CLI/API standardization)

## Context

When a user navigates to `/awards/{contractId}` and the award isn't in the local database, they see an error page. Awards are loaded filtered via CLI (`load awards --naics ...`), so not all awards exist locally. We need a tiered approach: graceful UI state, quick USASpending fetch, and queued FPDS enrichment.

## Design Decisions

- **API response**: Return 200 with `dataStatus` field (`full`, `partial`, `not_loaded`) instead of 404. Works naturally with TanStack Query.
- **Loading trigger**: Queue table (`data_load_request`). C# inserts row, Python ETL polls and processes. Reuses existing API clients and loader patterns.
- **UI feedback**: Poll `GET /api/v1/awards/{contractId}/load-status` every 4 seconds while loading. Invalidate cache on completion.

## New Table: `data_load_request`

```sql
CREATE TABLE IF NOT EXISTS data_load_request (
    request_id       INT AUTO_INCREMENT PRIMARY KEY,
    request_type     VARCHAR(30) NOT NULL,        -- 'USASPENDING_AWARD', 'FPDS_AWARD'
    lookup_key       VARCHAR(200) NOT NULL,        -- contract PIID
    lookup_key_type  VARCHAR(20) NOT NULL DEFAULT 'PIID',
    status           VARCHAR(20) NOT NULL DEFAULT 'PENDING',  -- PENDING, PROCESSING, COMPLETED, FAILED
    requested_by     INT,                           -- app_user.user_id (nullable)
    requested_at     DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
    started_at       DATETIME,
    completed_at     DATETIME,
    load_id          INT,                           -- FK to etl_load_log
    error_message    TEXT,
    result_summary   JSON,
    INDEX idx_dlr_status (status),
    INDEX idx_dlr_lookup (lookup_key, request_type),
    INDEX idx_dlr_requested (requested_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

## New C# API Endpoints

| Method | Path | Purpose |
|--------|------|---------|
| GET | `/api/v1/awards/{contractId}` | **Modified** — returns `AwardDetailResponse` with `dataStatus` instead of 404 |
| POST | `/api/v1/awards/{contractId}/load` | Request on-demand load (body: `{ tier: "usaspending" \| "fpds" }`) |
| GET | `/api/v1/awards/{contractId}/load-status` | Poll load request status |

## Data Flow

```
User visits /awards/W911NF25C0001
  -> C# API: fpds_contract not found, usaspending_award not found
  -> Returns { dataStatus: "not_loaded" }
  -> UI shows "not loaded" state with Load button + USASpending.gov link

User clicks "Load This Award"
  -> POST /api/v1/awards/.../load { tier: "usaspending" }
  -> Inserts data_load_request (USASPENDING_AWARD, PENDING)
  -> UI starts polling /load-status

Python DemandLoader (background):
  -> Picks up request, sets PROCESSING
  -> USASpendingClient.search_awards(keyword=piid)
  -> Loads usaspending_award + usaspending_transaction
  -> Sets COMPLETED, auto-queues FPDS_AWARD request

UI polling detects COMPLETED:
  -> Refetches detail -> { dataStatus: "partial", detail: {...financials...} }
  -> Shows data with banner "Full FPDS details loading..."

Later, DemandLoader processes FPDS request:
  -> Checks SAM.gov rate budget
  -> SAMAwardsClient.search_awards(piid=...) -> loads fpds_contract
  -> dataStatus becomes "full"
```

## Implementation Sequence

### Phase A: Foundation (Tier 1 -- graceful UI)
1. Create `data_load_request` table DDL
2. Add EF Core model + DbSet
3. Create `AwardDetailResponse` + `LoadRequestStatusDto` DTOs
4. Modify `AwardService.GetDetailAsync` -> return tiered response
5. Add `RequestLoadAsync` + `GetLoadStatusAsync` to service
6. Add controller endpoints (`/load`, `/load-status`)
7. Update `AwardDetailPage.tsx` -- handle not_loaded state, Load button, external links
8. Add API client functions for load/status

### Phase B: Quick Load (Tier 2 -- USASpending)
1. Create `fed_prospector/etl/demand_loader.py`
2. Implement USASPENDING_AWARD processing (extract from cli/spending.py pattern)
3. Create `fed_prospector/cli/demand.py` -- `process-requests` command + `--watch`
4. Register in main.py
5. Add UI polling hook
6. End-to-end test

### Phase C: FPDS Enrichment (Tier 3)
1. Add FPDS_AWARD processing to DemandLoader
2. Rate budget checking (reserve portion of SAM.gov daily quota)
3. Auto-queue FPDS after USASpending completion
4. Add scheduler entry

### Phase D: Polish
1. Request deduplication
2. Timeout handling (PROCESSING -> FAILED after 10 min)
3. UI polish: partial data display, progress indicators, error/retry

## Files to Create (6)

| File | Purpose |
|------|---------|
| `fed_prospector/db/schema/tables/55_data_load_request.sql` | Queue table DDL |
| `fed_prospector/etl/demand_loader.py` | On-demand loading logic |
| `fed_prospector/cli/demand.py` | `process-requests` CLI command |
| `api/src/FedProspector.Core/Models/DataLoadRequest.cs` | EF Core model |
| `api/src/FedProspector.Core/DTOs/Awards/AwardDetailResponse.cs` | Response wrapper DTO |
| `api/src/FedProspector.Core/DTOs/Awards/LoadRequestStatusDto.cs` | Load status DTO |

## Files to Modify (10)

| File | Change |
|------|--------|
| `api/.../Controllers/AwardsController.cs` | Add /load, /load-status endpoints; change GetDetail return |
| `api/.../Services/AwardService.cs` | Tiered response logic, load request methods |
| `api/.../Interfaces/IAwardService.cs` | New method signatures |
| `api/.../Data/FedProspectorDbContext.cs` | Add DbSet<DataLoadRequest> |
| `ui/src/pages/awards/AwardDetailPage.tsx` | Handle not_loaded/partial states |
| `ui/src/api/awards.ts` | Add load/status API functions |
| `ui/src/types/api.ts` | Add new types |
| `fed_prospector/main.py` | Register process-requests command |
| `fed_prospector/etl/scheduler.py` | Add demand_loader job |
| `fed_prospector/etl/usaspending_loader.py` | Extract single-award load helper |

## Key Reuse Points

- `cli/spending.py` burn-rate `--load-if-missing` -- already does USASpending search->load flow
- `USASpendingClient` -- `search_awards()`, `get_award()`, `get_all_transactions()` (no rate limits)
- `SAMAwardsClient` -- `search_awards(piid=...)` for FPDS data
- `StagingMixin` + `ChangeDetector` -- existing staging/upsert patterns

## Verification

1. Navigate to `/awards/NONEXISTENT123` -> "not loaded" state with Load button
2. Click Load -> polling indicator appears
3. Run `python main.py process-requests` -> processes USASpending request
4. Page auto-refreshes -> partial financial data shown
5. Run `process-requests` again -> processes FPDS request (if rate budget allows)
6. Page shows full data
7. Existing awards still show `dataStatus: "full"` (no regression)
