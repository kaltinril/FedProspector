# Phase 115M: FPDS Contract Data Enrichment

**Status:** PLANNED
**Priority:** MEDIUM -- enriches existing data with fields already available in the API
**Dependencies:** None (existing FPDS loader + table)

---

## Summary

An audit of our SAM.gov API specifications revealed that the Contract Awards API returns many fields we don't currently load into `fpds_contract`. These fields are available for free in data we already download -- we just ignore them during ETL. This phase adds the most impactful missing fields.

### Agency/Org Coding Systems Context

Federal organizations have THREE different identifier schemes, all stored in our `federal_organization` table:

| Scheme | Example | Description | Where Used |
|--------|---------|-------------|------------|
| **CGAC** | `012` | Common Government-wide Accounting Classification. 3-digit Treasury department code. | Opportunity `fullParentPathCode` first segment |
| **Agency Code** | `12K3` | FPDS-level agency/sub-tier identifier. | `fpds_contract.agency_id` |
| **FPDS Office Code** | `127SWF` | Contracting office identifier. | `fpds_contract.contracting_office_id`, opportunity `contracting_office_id` |

All three map to the same org hierarchy in `federal_organization`. Cross-table agency matching (Phase 115L) needs to account for all three code types when joining across data sources.

---

## Feature 1: Competition & Procurement Strategy Fields

New columns on `fpds_contract`:

| Column | API Field | Type | Why Valuable |
|--------|-----------|------|-------------|
| `source_selection_code` | `sourceSelectionProcess.code` | VARCHAR(10) | How the winner was chosen -- lowest price technically acceptable (LPTA) vs best value tradeoff. Directly shapes bid strategy. |
| `solicitation_procedures_code` | `solicitationProcedures.code` | VARCHAR(10) | Simplified acquisition, sealed bid, negotiated, sole source. Determines proposal complexity. |
| `contract_bundling_code` | `contractBundling.code` | VARCHAR(10) | Whether contract was bundled. High relevance for WOSB/8(a) -- bundled contracts are harder for small businesses. |
| `subcontract_plan_code` | `subcontractPlan.code` | VARCHAR(10) | Whether subcontracting plan required. Indicates teaming/subcontracting opportunities. |
| `performance_based_flag` | `performanceBasedServiceContract.code` | VARCHAR(5) | Whether contract is performance-based. Affects proposal writing and pricing approach. |
| `multiyear_contract_flag` | `multiyearContract.code` | VARCHAR(5) | Whether contract spans multiple fiscal years. Affects pricing and commitment risk. |
| `consolidated_contract_flag` | `consolidatedContract.code` | VARCHAR(5) | Whether contract was consolidated. Another bundling signal for small business strategy. |

---

## Feature 2: Contract Value Fields

| Column | API Field | Type | Why Valuable |
|--------|-----------|------|-------------|
| `ultimate_contract_value` | `ultimateContractValue` | DECIMAL(15,2) | Total ceiling value including all options -- more complete than `base_and_all_options` for some records. |
| `total_ultimate_contract_value` | `totalUltimateContractValue` | DECIMAL(15,2) | Aggregate across all modifications. True total commitment. |

---

## Feature 3: Funding Organization Fields

| Column | API Field | Type | Why Valuable |
|--------|-----------|------|-------------|
| `funding_office_code` | `fundingOffice.code` | VARCHAR(20) | Identifies the office funding the work (vs contracting office). Different org may fund vs contract. |
| `funding_office_name` | `fundingOffice.name` | VARCHAR(200) | Human-readable funding office name. |
| `contracting_department_code` | `contractingDepartment.code` | VARCHAR(10) | Department-level code from FPDS data. Helps Phase 115L agency normalization -- this is the CGAC-equivalent that's already in the API response. |
| `contracting_department_name` | `contractingDepartment.name` | VARCHAR(200) | Department name from FPDS (canonical format). |

---

## Feature 4: Awardee Socioeconomic Flags

The FPDS API returns detailed socioeconomic classification of the awardee. Rather than adding 15+ boolean columns, store as a JSON column:

| Column | Type | Contents |
|--------|------|----------|
| `awardee_socioeconomic` | JSON | Object with boolean flags: `sba8a`, `wosb`, `edwosb`, `sdvosb`, `hubzone`, `veteranOwned`, `smallBusiness`, `smallDisadvantagedBusiness` |

Example queries:

```sql
-- Find contracts won by WOSB firms
SELECT * FROM fpds_contract WHERE JSON_EXTRACT(awardee_socioeconomic, '$.wosb') = true;

-- Find 8(a) set-aside wins
SELECT * FROM fpds_contract WHERE JSON_EXTRACT(awardee_socioeconomic, '$.sba8a') = true AND set_aside_type LIKE '%8(a)%';
```

MySQL 8.x supports JSON indexing via generated columns if query performance becomes an issue.

**These flags are arguably the highest-value addition for the project's core mission of finding WOSB and 8(a) contracts to bid on.** Knowing which past awardees were WOSB/8(a) certified directly feeds set-aside analysis and competitive positioning.

---

## Feature 5: Additional Procurement Intelligence

Lower priority but still useful:

| Column | API Field | Type | Why |
|--------|-----------|------|-----|
| `reason_not_awarded_sb` | `reasonNotAwardedToSmallBusiness` | VARCHAR(200) | Explains why small biz didn't win. Post-mortem intelligence. |
| `cost_or_pricing_data_code` | `costOrPricingData.code` | VARCHAR(10) | Whether cost/pricing data was required. Indicates procurement rigor. |
| `contract_financing_code` | `contractFinancing.code` | VARCHAR(10) | How contract is financed (advance payments, progress payments, etc.). |
| `major_program_code` | `majorProgramCode` | VARCHAR(50) | Program identification for tracking specific programs across contracts. |

---

## Implementation

### DDL Migration

Single migration file with ALTER TABLE statements adding all new columns:

```sql
ALTER TABLE fpds_contract
    ADD COLUMN source_selection_code VARCHAR(10) DEFAULT NULL,
    ADD COLUMN solicitation_procedures_code VARCHAR(10) DEFAULT NULL,
    ADD COLUMN contract_bundling_code VARCHAR(10) DEFAULT NULL,
    ADD COLUMN subcontract_plan_code VARCHAR(10) DEFAULT NULL,
    ADD COLUMN performance_based_flag VARCHAR(5) DEFAULT NULL,
    ADD COLUMN multiyear_contract_flag VARCHAR(5) DEFAULT NULL,
    ADD COLUMN consolidated_contract_flag VARCHAR(5) DEFAULT NULL,
    ADD COLUMN ultimate_contract_value DECIMAL(15,2) DEFAULT NULL,
    ADD COLUMN total_ultimate_contract_value DECIMAL(15,2) DEFAULT NULL,
    ADD COLUMN funding_office_code VARCHAR(20) DEFAULT NULL,
    ADD COLUMN funding_office_name VARCHAR(200) DEFAULT NULL,
    ADD COLUMN contracting_department_code VARCHAR(10) DEFAULT NULL,
    ADD COLUMN contracting_department_name VARCHAR(200) DEFAULT NULL,
    ADD COLUMN awardee_socioeconomic JSON DEFAULT NULL,
    -- Feature 5 (lower priority)
    ADD COLUMN reason_not_awarded_sb VARCHAR(200) DEFAULT NULL,
    ADD COLUMN cost_or_pricing_data_code VARCHAR(10) DEFAULT NULL,
    ADD COLUMN contract_financing_code VARCHAR(10) DEFAULT NULL,
    ADD COLUMN major_program_code VARCHAR(50) DEFAULT NULL;
```

### ETL Changes

Modify `fpds_loader.py` to extract these additional fields from the API response during load. These are all in the same API response we already download -- just need to add column mappings.

### Backfill Strategy

Re-run a full FPDS load to populate new columns on existing 225K records. Or if we store raw JSON from FPDS loads, parse from stored data.

---

## Build Order

1. DDL migration (add columns)
2. Update `fpds_loader.py` column mappings
3. Full refresh load to backfill
4. Update C# entities (add properties with `[Column]` attributes)
5. Update relevant C# services to use new fields (PricingService, MarketIntelService)
6. Add UI display for socioeconomic flags and competition strategy data

---

## Entity Management API (Future Phase)

The SAM.gov Entity Management API provides vendor registration data (SAM registrations) that we don't load at all. This is a larger effort deserving its own phase but would enable:

- Competitor profiling (what NAICS/PSC codes competitors register for)
- Certification verification (cross-check 8(a)/WOSB/HUBZone status)
- Security clearance filtering
- Geographic market analysis

Recommend deferring to a separate phase (115N or similar).
