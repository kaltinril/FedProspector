# Phase 115I: Pre-computed Scoring Summaries

**Status:** COMPLETE  
**Priority:** HIGH  
**Dependencies:** Phase 115A (Scoring Model Enhancements)

---

## Problem

The Phase 115A scoring models (OQS, CSI, IVS) need market competition data from `usaspending_award` (28.7M rows). Real-time GROUP BY + COUNT(DISTINCT) queries across this table take 8-25+ seconds depending on the number of NAICS codes. The date filter (last 5 years) only eliminates ~28% of rows and provides negligible performance benefit.

Phase 115A shipped with a split-query workaround (individual per-NAICS ref lookups instead of IN range scans), reducing the worst case from 25s to ~8s. This phase replaces that with pre-computed summary tables for sub-millisecond lookups.

## Solution

Pre-compute market competition summaries during the daily USASpending load. The OQS and other scoring services query the summary table instead of aggregating 28.7M rows on every request.

## Summary Table Design

### `competition_summary`

| Column | Type | Description |
|--------|------|-------------|
| naics_code | VARCHAR(11) | NAICS code |
| agency_name | VARCHAR(255) | Awarding agency name |
| vendor_count | INT | Distinct vendor UEIs with awards |
| contract_count | INT | Total contract count |
| total_value | DECIMAL(18,2) | Total dollars obligated |
| computed_at | DATETIME | When this row was last refreshed |

**Primary key:** (naics_code, agency_name)  
**Expected size:** ~14,559 rows (based on current data)  
**Compute time:** ~71 seconds for full rebuild

### Source Query

```sql
INSERT INTO competition_summary (naics_code, agency_name, vendor_count, contract_count, total_value, computed_at)
SELECT 
    naics_code,
    awarding_agency_name,
    COUNT(DISTINCT recipient_uei),
    COUNT(*),
    SUM(total_obligation),
    NOW()
FROM usaspending_award
WHERE naics_code IS NOT NULL
  AND awarding_agency_name IS NOT NULL
  AND recipient_uei IS NOT NULL
GROUP BY naics_code, awarding_agency_name
ON DUPLICATE KEY UPDATE
    vendor_count = VALUES(vendor_count),
    contract_count = VALUES(contract_count),
    total_value = VALUES(total_value),
    computed_at = NOW();
```

## Tasks

- [x] Created DDL for `usaspending_award_summary` table (`fed_prospector/db/schema/tables/usaspending_award_summary.sql`)
- [x] Added `refresh_usaspending_award_summary()` function in `fed_prospector/etl/etl_utils.py`
- [x] Wired refresh into `usaspending_bulk_loader.py` (called after each load)
- [x] Wired refresh into `usaspending_loader.py` (called after each load)
- [x] Created EF Core model `UsaspendingAwardSummary` (`api/src/FedProspector.Core/Models/UsaspendingAwardSummary.cs`)
- [x] Registered in `FedProspectorDbContext` with composite key
- [x] Updated `RecommendedOpportunityService.GetRecommendedAsync` to query summary table instead of 28.7M-row usaspending_award
- [x] Updated `RecommendedOpportunityService.CalculateOqScoreAsync` to query summary table
- [x] Table populated with 16,665 rows

## Design Decisions

- **No date dimension**: The 5-year date filter only eliminates 28% of rows — not worth the complexity. The summary covers all historical data.
- **Full rebuild on each load**: With only ~14K rows, a full TRUNCATE + INSERT is simpler and faster than incremental updates.
- **Schema ownership**: Python DDL owns this table (ETL/data table, not application table).
