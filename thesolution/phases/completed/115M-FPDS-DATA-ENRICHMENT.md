# Phase 115M: FPDS Contract Data Enrichment

**Status:** COMPLETE (code complete 2026-04-13; backfill load pending)
**Priority:** HIGH -- feeds directly into pricing accuracy and core WOSB/8(a) mission
**Dependencies:** Phase 115L (fh_org_id resolution -- DONE)

---

## Summary

The SAM.gov Contract Awards API returns fields we currently throw away during ETL. This phase adds the three that genuinely improve end-user outcomes, plus wires one existing field into PricingService where it belongs.

**Scope**: 3 new columns + 1 JSON blob + 1 existing-field activation. That's it.

**Design principle**: Every field must have a named consumer that produces a better result for the user. Fields that would only be "displayed" or "could inform" a service are deferred. Our scoring services (PWin, GoNoGo, IVS, OpenDoor) are outcome-based models -- injecting process metadata flags into them adds noise, not signal.

---

## Feature 1: Awardee Socioeconomic Flags (CRITICAL)

| Column | Type | Contents |
|--------|------|----------|
| `awardee_socioeconomic` | JSON | `{sba8a, wosb, edwosb, sdvosb, hubzone, veteranOwned, smallBusiness, smallDisadvantagedBusiness}` |

**Why**: The API returns 9+ certification fields (`sbaCertified8aProgramParticipant`, `sbaCertifiedWomenOwnedSmallBusiness`, `sbaCertifiedEconomicallyDisadvantagedWomenOwnedSmallBusiness`, `sbaCertifiedHubZoneFirm`, etc.) that we completely ignore. For a system whose entire purpose is finding WOSB/8(a) contracts to bid on, this is the single highest-value addition.

Today we can only see that a contract WAS set aside (via `set_aside_type`), but not whether the awardee actually held the certification. These are different things -- many awards go to vendors who aren't certified in the set-aside category.

**Consumers**:
- `CompetitorStrengthService` -- certification portfolio scoring (weight 0.20). Currently infers certification from SAM entity data, which only shows *current* status. FPDS socioeconomic flags give point-in-time certification status at award time.
- `v_set_aside_trend` -- answer "how many WOSB-certified firms actually won WOSB set-asides?" vs non-certified firms winning set-aside contracts.
- `v_competitor_analysis` -- add socioeconomic profile from historical awards per competitor.
- `CompetitorDossierPage.tsx` -- display certification history from award records.
- `MarketIntelService` -- market share analysis segmented by business type.

MySQL 8.x generated columns for high-frequency queries:

```sql
ALTER TABLE fpds_contract
    ADD COLUMN is_wosb_awardee BOOLEAN GENERATED ALWAYS AS (JSON_EXTRACT(awardee_socioeconomic, '$.wosb') = CAST('true' AS JSON)) STORED,
    ADD COLUMN is_8a_awardee BOOLEAN GENERATED ALWAYS AS (JSON_EXTRACT(awardee_socioeconomic, '$.sba8a') = CAST('true' AS JSON)) STORED,
    ADD INDEX idx_fpds_wosb (is_wosb_awardee),
    ADD INDEX idx_fpds_8a (is_8a_awardee);
```

---

## Feature 2: Source Selection Code (HIGH)

| Column | API Field | Type |
|--------|-----------|------|
| `source_selection_code` | `sourceSelectionProcess.code` | VARCHAR(10) |

**Why**: LPTA (Lowest Price Technically Acceptable) and Best Value are fundamentally different pricing regimes. In LPTA, the lowest technically-acceptable price wins -- you need P10-P25 comparables. In Best Value, technical factors matter -- P50 is appropriate. Our Price-to-Win engine currently mixes both in the same comparable set, producing a meaningless average.

**Consumer**:
- `PricingService.EstimatePriceToWinAsync()` (line ~156) -- filter comparable awards by source selection method, then adjust target percentile. This is the primary consumer and the reason to add the field.
- `v_price_to_win_comparable` (86_v_price_to_win.sql) -- add as filter column so the view supports segmentation.

**Why not PWinService or GoNoGo?** These are outcome-based models. PWin's Competition Level factor already uses vendor counts per NAICS. Source selection method is procurement process metadata -- it doesn't tell you how many competitors exist or how strong they are. Adding it would dilute existing signals.

---

## Feature 3: Contract Bundling Code (MEDIUM)

| Column | API Field | Type |
|--------|-----------|------|
| `contract_bundling_code` | `contractBundling.code` | VARCHAR(10) |

**Why**: Bundled contracts consolidate multiple smaller requirements into one large contract, making them harder for small businesses to win. This is directly relevant to the WOSB/8(a) mission -- capture managers need to see bundling patterns when evaluating agencies and NAICS codes.

**Consumers**:
- `v_procurement_intelligence` -- add bundling indicator to the procurement profile so users see it on the Opportunity Detail page alongside other contract characteristics.
- Agency pattern analytics -- "what % of this agency's contracts in this NAICS are bundled?" is actionable intelligence for Go/No-Go decisions made by humans, not by the scoring formula.

**Why not scoring services?** Bundling is a per-contract fact about the predecessor award, not a predictive signal about the current opportunity. GoNoGo's 0-40 scale is 4 orthogonal factors (set-aside, time, NAICS, value) and adding a 5th would either dilute each factor or break the scale. Users can factor bundling into their manual assessment using the displayed data.

---

## Feature 4: Activate type_of_contract_pricing in PricingService

This field is ALREADY in `fpds_contract` and loaded by the ETL, but PricingService ignores it.

- **Field**: `type_of_contract_pricing` (VARCHAR(10)) -- FFP, T&M, Cost-Plus, etc.
- **Service**: `PricingService.EstimatePriceToWinAsync()` (line ~156) -- FFP and T&M contracts have fundamentally different pricing dynamics. Comparing FFP awards against T&M awards is apples-to-oranges. Filter comparable awards by contract pricing type.
- **View**: Update `v_price_to_win_comparable` to include `type_of_contract_pricing` as a filter column (it's already in the underlying table).

No DDL or ETL changes needed -- just service and view updates.

---

## Deferred to Phase 500

Fields from the original 115M spec or the first rewrite that don't earn their place:

| Field | Reason Deferred |
|-------|----------------|
| `solicitation_procedures_code` | "Sealed bid vs negotiated" is procurement trivia. No service consumes it for a better result. |
| `subcontract_plan_code` | Plan required != plan executed. OpenDoorService already scores actual subaward behavior, which is the real signal. |
| `performance_based_flag` | "Different proposal structure" is vague. No formula change, no user-facing improvement. |
| `multiyear_contract_flag` | IVS already detects multiyear contracts from modification history with more granularity than a boolean flag. |
| `consolidated_contract_flag` | Redundant with bundling. One signal is enough. |
| `ultimate_contract_value` / `total_ultimate_contract_value` | Likely duplicates `base_and_all_options`. Unverified distinction. |
| `funding_office_code/name` | Already have funding_agency + funding_subtier. Marginal. |
| `contracting_department_code/name` | Already have agency_id + fh_org_id from 115L. Redundant. |
| `reason_not_awarded_sb` | Interesting post-mortem data but no consumer. |
| `cost_or_pricing_data_code` | No consumer. Speculative. |
| `contract_financing_code` | No consumer. Speculative. |
| `major_program_code` | No consumer. Speculative. |

### Existing unused fields NOT being activated

These fields are already in `fpds_contract` and remain display-only. Forcing them into scoring models would add noise:

| Field | Why Not |
|-------|---------|
| `extent_competed` | PWin already measures competition via vendor counts per NAICS. This is a per-contract categorical flag, not a market signal. |
| `type_of_contract` | Displayed in DTOs. No scoring or pricing formula benefits from this beyond what `type_of_contract_pricing` already provides. |
| `psc_code` | Narrowing Price-to-Win comparables by PSC on top of NAICS would reduce sample size below useful thresholds for most codes. |
| `pop_state` | Geo-adjusting IGCE labor rates sounds good in theory but requires a separate regional cost index dataset we don't have. |
| `far1102_exception_code` | Niche procurement edge case. Not actionable for end users. |
| `co_bus_size_determination` | Never referenced. No consumer. |

---

## Implementation

### DDL Migration

```sql
ALTER TABLE fpds_contract
    ADD COLUMN source_selection_code VARCHAR(10) DEFAULT NULL,
    ADD COLUMN contract_bundling_code VARCHAR(10) DEFAULT NULL,
    ADD COLUMN awardee_socioeconomic JSON DEFAULT NULL;

-- Generated columns for high-frequency JSON queries
ALTER TABLE fpds_contract
    ADD COLUMN is_wosb_awardee BOOLEAN GENERATED ALWAYS AS (JSON_EXTRACT(awardee_socioeconomic, '$.wosb') = CAST('true' AS JSON)) STORED,
    ADD COLUMN is_8a_awardee BOOLEAN GENERATED ALWAYS AS (JSON_EXTRACT(awardee_socioeconomic, '$.sba8a') = CAST('true' AS JSON)) STORED,
    ADD INDEX idx_fpds_wosb (is_wosb_awardee),
    ADD INDEX idx_fpds_8a (is_8a_awardee);
```

### ETL Changes (awards_loader.py)

Add to `_normalize_award()` (after line ~530):
- `sourceSelectionProcess.code` --> `source_selection_code`
- `contractBundling.code` --> `contract_bundling_code`
- Socioeconomic flags from `awardeeData.certifications` + `awardeeData.socioEconomicData` --> `awardee_socioeconomic` JSON

Add new fields to `_AWARD_HASH_FIELDS` and `_UPSERT_COLS`.

### C# Entity Changes (FpdsContract.cs)

Add properties with `[Column("snake_case")]` attributes:

```csharp
[Column("source_selection_code")]
public string? SourceSelectionCode { get; set; }

[Column("contract_bundling_code")]
public string? ContractBundlingCode { get; set; }

[Column("awardee_socioeconomic", TypeName = "json")]
public string? AwardeeSocioeconomic { get; set; }
```

### View Updates

| View | Change |
|------|--------|
| `v_price_to_win_comparable` | Add `source_selection_code`, `type_of_contract_pricing` as filter columns |
| `v_procurement_intelligence` | Add `source_selection_code`, `contract_bundling_code` |
| `v_competitor_analysis` | Add socioeconomic aggregation from `awardee_socioeconomic` |
| `v_set_aside_trend` | Add awardee certification breakdown using generated columns |

### Service Updates

| Service | Method | Change |
|---------|--------|--------|
| `PricingService` | `EstimatePriceToWinAsync` | Filter by `source_selection_code`; adjust target percentile (LPTA=P20, BV=P50) |
| `PricingService` | `EstimatePriceToWinAsync` | Filter by `type_of_contract_pricing` (existing field, newly consumed) |
| `CompetitorStrengthService` | certification scoring | Use `awardee_socioeconomic` for point-in-time cert status |

### Backfill

Re-run full FPDS load (`python main.py load awards --full-refresh`) to populate new columns on existing 225K records.

---

## Build Order

1. **DDL migration** -- add 3 columns + 2 generated columns + 2 indexes
2. **ETL changes** -- update `_normalize_award()`, `_UPSERT_COLS`, `_AWARD_HASH_FIELDS`
3. **Full refresh load** -- backfill 225K records
4. **C# entity** -- add 3 properties with `[Column]` attributes
5. **View updates** -- update 4 views
6. **Service updates** -- wire `source_selection_code` + `type_of_contract_pricing` into PricingService, `awardee_socioeconomic` into CompetitorStrengthService
7. **UI updates** -- display socioeconomic flags on CompetitorDossierPage, bundling on procurement intelligence

---

## Agency/Org Coding Systems Context

Federal organizations have THREE different identifier schemes, all stored in our `federal_organization` table:

| Scheme | Example | Description | Where Used |
|--------|---------|-------------|------------|
| **CGAC** | `012` | Common Government-wide Accounting Classification. 3-digit Treasury department code. | Opportunity `fullParentPathCode` first segment |
| **Agency Code** | `12K3` | FPDS-level agency/sub-tier identifier. | `fpds_contract.agency_id` |
| **FPDS Office Code** | `127SWF` | Contracting office identifier. | `fpds_contract.contracting_office_id`, opportunity `contracting_office_id` |

All three map to the same org hierarchy in `federal_organization`. Cross-table agency matching (Phase 115L -- DONE) accounts for all three code types.

---

## Entity Management API (Future Phase 115N)

The SAM.gov Entity Management API provides vendor registration data that we do not load at all. This is a larger effort deserving its own phase but would enable:

- Competitor profiling (what NAICS/PSC codes competitors register for)
- Certification verification (cross-check 8(a)/WOSB/HUBZone status)
- Security clearance filtering
- Geographic market analysis
