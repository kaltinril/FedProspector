# Phase 44: USASpending-First Loading Strategy

**Status**: COMPLETE (44A + 44C implemented; 44B + 44D moved to Phase 500 backlog)
**Depends on**: Phase 43 (On-Demand Award Loading)

## Context

Phase 43 introduced on-demand award loading — when a user views an unloaded award, USASpending data is fetched first (no rate limit), then SAM.gov FPDS data is queued (rate-limited). This raised a broader question: **should the entire ETL pipeline adopt a "load free sources first, enrich with rate-limited sources second" strategy?**

## The Idea

1. Load ALL data from unlimited-rate sources first (USASpending.gov, GSA CALC+)
2. Enrich/overwrite with rate-limited SAM.gov data as budget allows
3. Apply this pattern to ALL data types, not just awards

## Current Data Source Inventory

### Unlimited Rate Sources (no API key required)

| Source | Data | Records | Current Use |
|--------|------|---------|-------------|
| USASpending.gov API | Federal awards (all types), transactions | Millions (FY2008+) | Filtered loading by keyword/NAICS |
| USASpending.gov Bulk CSV | Same, downloadable per fiscal year | Millions | Not yet used |
| GSA CALC+ | Labor ceiling rates | ~230K | Full bulk load (already done) |

### Rate-Limited Sources (SAM.gov, 10/day free or 1000/day key 2)

| Source | Data | Records | Current Use |
|--------|------|---------|-------------|
| SAM Entity Extract | Full entity dataset (ZIP download) | ~576K | Monthly bulk (1 API call) |
| SAM Entity API | Individual entity lookup | ~576K | On-demand lookups |
| SAM Opportunities API | Active solicitations | ~100K+ | Daily filtered loads |
| SAM Awards API | FPDS contract data | ~1M+ | Filtered by NAICS/set-aside |
| SAM Subaward API | Subcontract reporting | ~2.7M+ | Monthly analysis |
| SAM Exclusions API | Debarred entities | ~167K | Spot checks only |
| SAM Federal Hierarchy API | Agency structure | ~600 | Weekly refresh |

## Analysis: What Overlaps?

### Awards: USASpending vs SAM Awards (FPDS)

**High overlap** — both contain federal contract award data.

| Aspect | USASpending.gov | SAM.gov Awards (FPDS) |
|--------|-----------------|----------------------|
| Rate limit | None | 10-1000/day (shared pool) |
| History depth | FY2008+ (18 years) | 2018+ (~6 years) |
| Award types | Contracts, grants, loans, IDVs | Contracts only |
| Transaction history | Yes (per-modification) | No |
| Set-aside detail | Type of set-aside (text) | Set-aside code (more precise) |
| Contract classification | Basic (type, pricing) | Deep (extent competed, # offers, pricing type) |
| Place of performance | State, country, zip | State, country, zip, congressional district |
| Vendor detail | Recipient name, UEI | Vendor name, UEI, DUNS |
| Freshness | Weekly updates | More current for recent awards |
| Bulk download | CSV per fiscal year | No bulk option |

**Bottom line**: USASpending covers ~80% of what users need for award analysis. SAM.gov FPDS adds: extent competed, number of offers, contract pricing type, IDV PIID, and contracting office detail.

### Entities: No real overlap

USASpending has recipient name/UEI only. SAM Entity Extract is the sole source for business type, SBA certifications, NAICS codes, addresses, POCs, etc. **No shortcut here** — SAM Extract is already efficient (1 API call = 576K entities).

### Subawards: No overlap

Only SAM.gov Subaward API has this data. USASpending has a subaward endpoint but it's not currently integrated.

### Opportunities: No overlap

Only SAM.gov Opportunities API has active solicitations.

## Proposed Strategy: Tiered Loading

### Tier 1: Unlimited Sources (run anytime, no budget concern)

| Action | Source | Target Table | Frequency | Records |
|--------|--------|-------------|-----------|---------|
| Bulk download all awards | USASpending CSV | `usaspending_award` | Monthly full + weekly incremental | Millions |
| Load all transactions | USASpending API | `usaspending_transaction` | On-demand per award | Per award |
| Load all labor rates | GSA CALC+ | `gsa_labor_rate` | Monthly | ~230K |

**New capability**: USASpending bulk CSV download. The API client already has `request_bulk_download()` — download CSV for each fiscal year and LOAD DATA INFILE into MySQL.

### Tier 2: Efficient Rate-Limited Sources (low call count, high value)

| Action | Source | Target Table | Frequency | API Calls |
|--------|--------|-------------|-----------|-----------|
| Entity extract download | SAM Extract | `entity` + 7 child tables | Monthly full + daily incremental | 1-2 calls |
| Federal hierarchy refresh | SAM FedHier | `federal_organization` | Weekly | ~7 calls |
| Active opportunities | SAM Opportunities | `opportunity` | Daily | 5-50 calls |

### Tier 3: Expensive Rate-Limited Sources (use budget carefully)

| Action | Source | Target Table | Frequency | API Calls |
|--------|--------|-------------|-----------|-----------|
| FPDS enrichment for key awards | SAM Awards | `fpds_contract` | Queued via demand_loader | Variable |
| Subaward analysis | SAM Subaward | `sam_subaward` | Monthly or on-demand | Variable |
| Exclusion spot checks | SAM Exclusions | `sam_exclusion` | On-demand per entity | 1 per check |

### Tier 4: On-Demand (Phase 43 pattern)

| Action | Source | Target Table | Trigger |
|--------|--------|-------------|---------|
| Single award detail | USASpending + SAM Awards | Both tables | User views award |
| Single entity detail | SAM Entity API | `entity` tables | User views entity |

## What Changes vs Current Approach

### Current: SAM.gov-first, USASpending supplementary
- Load awards filtered by NAICS from SAM.gov Awards → `fpds_contract`
- Load matching USASpending data → `usaspending_award` + `usaspending_transaction`
- Rate limit is the bottleneck

### Proposed: USASpending-first, SAM.gov enrichment
- Bulk load USASpending CSV for all fiscal years → `usaspending_award` (millions of records)
- Load transactions on-demand (no rate limit)
- Enrich with SAM.gov FPDS only for awards users actually view (Phase 43 demand pattern)
- Result: Complete historical picture with zero SAM.gov API calls, FPDS detail added incrementally

## Is This a Good Idea?

### Advantages

1. **Vastly more data with zero API budget**: Millions of awards vs thousands currently
2. **Historical depth**: 18 years of data for trend analysis
3. **No rate limit anxiety**: USASpending and CALC+ have no limits
4. **Better UX**: Users always have some data; FPDS enriches over time
5. **Budget preservation**: Save SAM.gov calls for opportunities and entities (which have no alternative source)
6. **Aligns with Phase 43**: On-demand enrichment pattern already works

### Risks and Concerns

1. **Data volume**: Millions of USASpending records = significant DB storage and query time
   - Mitigation: Index well, partition by fiscal year, or only load relevant NAICS codes
2. **Data staleness**: USASpending updates weekly, SAM.gov may be more current
   - Mitigation: On-demand FPDS enrichment catches up for viewed awards
3. **Schema mismatch**: `usaspending_award` and `fpds_contract` have different schemas
   - Current: They're already separate tables, queried independently
   - This doesn't change — it just means `usaspending_award` has more rows
4. **Initial load time**: Bulk CSV for 18 fiscal years could be large
   - Mitigation: Start with recent 5 years, backfill gradually
5. **Not all data types benefit**: Entities, opportunities, subawards still need SAM.gov
   - True, but awards are the biggest rate-limit consumer. Freeing up those calls helps everything.

### Verdict: Good idea, with scoping

**Do it for awards — the ROI is clear.** USASpending covers the majority of award analysis needs. FPDS enrichment adds detail for specific contracts users care about.

**Don't force it on other data types** — entities already have the Extract workaround (1 call), opportunities have no alternative, subawards are SAM-only.

## Implementation Plan (if approved)

### Phase 44A: USASpending Bulk CSV Loading
1. Add CLI command: `python main.py load usaspending-bulk --years-back 5`
2. Use `USASpendingClient.request_bulk_download()` to get CSV download link
3. Download CSV, parse, and load via LOAD DATA INFILE
4. Add fiscal year filter to avoid re-loading old data
5. Schema: reuse existing `usaspending_award` table

### Phase 44B: Auto-FPDS Enrichment
1. Extend demand_loader to process FPDS requests in batches (not just single awards)
2. Add a priority queue: awards viewed by users get enriched first
3. Background nightly job: enrich remaining awards within daily rate budget
4. Add `fpds_enriched_at` timestamp to `usaspending_award` to track enrichment status

### Phase 44C: UI Adjustments
1. Award search should query BOTH tables (union or fallback)
2. Award list shows all awards (USASpending), detail shows enriched FPDS when available
3. Partial data banner (from Phase 43) already handles this

### Phase 44D: Rate Budget Reallocation
1. With awards no longer consuming SAM.gov calls, reallocate budget:
   - Opportunities: 500 calls/day (was ~200)
   - Entity updates: 200 calls/day (daily delta)
   - Subaward analysis: 200 calls/day (monthly)
   - On-demand FPDS: 100 calls/day (demand_loader)
2. Update rate budget configuration

## Estimated Effort

| Sub-phase | Effort | Dependencies |
|-----------|--------|-------------|
| 44A: Bulk CSV loading | 2-3 days | USASpending bulk download endpoint |
| 44B: Auto-enrichment | 1 day | Phase 43 demand_loader |
| 44C: UI adjustments | 1-2 days | Phase 44A data available |
| 44D: Budget reallocation | 0.5 days | Config only |

## Decisions Made

1. **Scope**: Recent 5 fiscal years (FY2021-2025), backfill older years later
2. **Trigger**: CLI command (`python main.py load usaspending-bulk`), on-demand
3. **Award search**: Fallback strategy — search fpds_contract first, supplement with usaspending_award if few results
4. **44B deferred**: On-demand FPDS loading (Phase 43) is sufficient for now; auto-enrichment deferred
5. **44D deferred**: Rate budget reallocation is config-only, do later

## Implementation Status

### 44A: USASpending Bulk CSV Loading — COMPLETE
- Schema: `fiscal_year` and `fpds_enriched_at` columns added to `usaspending_award`
- Client: `poll_bulk_download()` and `download_bulk_file()` added to `USASpendingClient`
- Loader: New `usaspending_bulk_loader.py` — CSV → TSV → LOAD DATA INFILE with temp table upsert
- CLI: `python main.py load usaspending-bulk [--years-back 5] [--fiscal-year YYYY] [--skip-download]`

### 44B: Auto-FPDS Enrichment — MOVED TO PHASE 500A
- See [500-DEFERRED-ITEMS.md](500-DEFERRED-ITEMS.md)

### 44C: UI + API Adjustments — COMPLETE
- C# AwardService: Fallback search queries `usaspending_award` when FPDS results are below page size
- DTO: `DataSource` field added ("fpds" or "usaspending")
- UI: "Data" column with Full/Partial chip badge in award search grid

### 44D: Rate Budget Reallocation — MOVED TO PHASE 500B
- See [500-DEFERRED-ITEMS.md](500-DEFERRED-ITEMS.md)
