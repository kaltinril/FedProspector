# Federal Contract Data Sources - Complete Inventory

## Overview

This document catalogs all identified federal government data sources for contract prospecting. Sources are ranked by priority for WOSB/8(a) contract discovery.

---

## Tier 1 - Essential (Implement First)

### 1. SAM.gov Entity/Exclusions Extracts Download API

**Purpose**: Bulk download of ALL registered federal contractor entities. This is the foundation of the entity database.

| Field | Detail |
|-------|--------|
| URL | `https://api.sam.gov/data-services/v1/extracts` |
| Auth | API key via `api_key` query param |
| Rate Limit | 10/day (no role), 1,000/day (with role) |
| Data Format | ZIP containing pipe-delimited DAT file or JSON |
| Update Frequency | Monthly (full), Daily (incremental) |

**File Types**:
- Monthly: `SAM_PUBLIC_MONTHLY_V2_YYYYMMDD.ZIP` (first Sunday of each month)
- Daily: `SAM_PUBLIC_DAILY_V2_YYYYMMDD.ZIP` (Tuesday-Saturday)
- UTF-8 variants available

**Why Essential**: One API call downloads ALL active entities (~576K active out of ~1.3M total). Bypasses the harsh 10/day rate limit entirely. Contains UEI SAM, CAGE codes, legal business names, NAICS codes, PSC codes, business types, SBA certifications (including WOSB/8(a) status), and all points of contact.

**Known Issues**:
- Filename varies by month (not always the same day). Strategy: try target date, handle 404s by trying adjacent dates
- DAT files are pipe-delimited with escaped pipes (`|\|`) requiring cleanup
- JSON extract preferred for Python processing (preserves nested structure)

**WOSB/8(a) Relevant Fields**: `sbaBusinessTypeList` with `sbaBusinessTypeCode`, `certificationEntryDate`, `certificationExitDate`

---

### 2. SAM.gov Get Opportunities Public API (v2)

**Purpose**: Active contract solicitations, RFPs, RFQs, pre-solicitation notices. THE source for finding contracts to bid on.

| Field | Detail |
|-------|--------|
| URL | `https://api.sam.gov/opportunities/v2/search` |
| Auth | API key via `api_key` query param |
| Rate Limit | 10/day (no role), 1,000/day (with role) |
| Data Format | JSON |
| Update Frequency | Active notices daily, archived weekly |
| Max per page | 1,000 records |

**Key Parameters**:
- `typeOfSetAside` - Filter by set-aside code (one value per request)
- `postedFrom` / `postedTo` - Date range (mandatory, max 1 year, `MM/dd/yyyy`)
- `ncode` - NAICS code filter (max 6 digits)
- `ptype` - Procurement type: `o` (solicitation), `k` (combined synopsis/solicitation), `p` (presolicitation), `r` (sources sought)
- `limit` - Max 1,000 records per page
- `offset` - Pagination offset

**WOSB/8(a) Set-Aside Codes**:

| Code | Description |
|------|-------------|
| `WOSB` | Women-Owned Small Business Program Set-Aside |
| `WOSBSS` | WOSB Program Sole Source |
| `EDWOSB` | Economically Disadvantaged WOSB Set-Aside |
| `EDWOSBSS` | EDWOSB Program Sole Source |
| `8A` | 8(a) Set-Aside |
| `8AN` | 8(a) Sole Source |
| `SBA` | Total Small Business Set-Aside |
| `SBP` | Partial Small Business Set-Aside |
| `HZC` | HUBZone Set-Aside |
| `HZS` | HUBZone Sole Source |
| `SDVOSBC` | Service-Disabled Veteran-Owned SB Set-Aside |
| `SDVOSBS` | SDVOSB Sole Source |

**Response includes**: `noticeId`, `title`, `solicitationNumber`, `postedDate`, `typeOfSetAside`, `naicsCode`, `classificationCode` (PSC), `award` (amount/date/awardee UEI), `pointOfContact`, `description`, `placeOfPerformance`, `resourceLinks`

---

### 3. USASpending.gov API (v2)

**Purpose**: Comprehensive U.S. government spending data. Best for aggregate analysis and historical trends.

| Field | Detail |
|-------|--------|
| URL | `https://api.usaspending.gov/` |
| Auth | None required |
| Rate Limit | **No documented rate limits** |
| Data Format | JSON (API), CSV (bulk downloads) |
| Update Frequency | Regular (sourced from FPDS and agency systems) |

**Key Endpoints**:
- `/api/v2/search/spending_by_award/` - Award search with business category filtering
- `/api/v2/awards/{award_id}/` - Individual award details
- `/api/v2/recipient/duns/{recipient_id}/` - Recipient details by UEI
- `/api/v2/bulk_download/awards/` - Bulk CSV download
- `/api/v2/search/spending_by_category/` - Aggregated spending by various dimensions
- `/api/v2/references/naics/` - NAICS hierarchy

**Bulk Download**: Available at `https://www.usaspending.gov/download_center/award_data_archive` with FY2008-present data.

**Why Essential**: No rate limits makes this ideal for bulk historical analysis. Answer questions like: which agencies spend the most on WOSB/8(a) contracts, what NAICS codes, what dollar ranges, who are the top awardees (competitors).

---

### 4. SAM.gov Entity Management API (v1-4)

**Purpose**: Real-time lookup of individual contractor registrations. Use for targeted queries, not bulk loads.

| Field | Detail |
|-------|--------|
| URL | `https://api.sam.gov/entity-information/v1-4/entities` |
| Auth | API key (personal) or Basic Auth + x-api-key (system account) |
| Rate Limit | 10/day (personal, no role), 1,000/day (personal, with role), 10,000/day (federal system) |
| Data Format | JSON or CSV |
| Keys expire | Every 90 days |

**Data Sensitivity Levels**:

| Level | Content | Access |
|-------|---------|--------|
| Public | Name, UEI, addresses, business types, NAICS | Any API key |
| FOUO (CUI) | Hierarchy, security clearance, contact emails/phones | Federal System Account |
| Sensitive (CUI) | Banking, SSN/TIN/EIN | Federal System Account + POST only |

**Key WOSB/8(a) Parameters**:
- `businessTypeCode` - e.g., `8W` (WOSB), `A2` (Woman Owned), `8E` (EDWOSB), `8C` (JV WOSB), `8D` (JV EDWOSB)
- `sbaBusinessTypeCode` - e.g., `A6` (SBA Certified 8(a) Participant)
- Response `sbaBusinessTypeList` includes `certificationEntryDate` and `certificationExitDate`

**Strategy**: Use the Extracts API (Source 1) for bulk data. Reserve this API for targeted lookups of specific entities by UEI when fresh data is needed.

---

### 5. SAM.gov Federal Hierarchy Public API

**Purpose**: Federal agency organizational structure (Department -> Sub-tier -> Office)

| Field | Detail |
|-------|--------|
| URL | `https://api.sam.gov/prod/federalorganizations/v1/orgs` |
| Auth | API key via `api_key` query param |
| Rate Limit | 10/day (no role), hierarchical and paginated |
| Data Format | JSON |

**Why Essential**: Maps which offices within agencies issue WOSB/8(a) contracts. Enables agency-level targeting.

---

## Tier 2 - High Value (Implement Second)

### 6. SAM.gov Contract Awards API (v1)

**Purpose**: Historical contract award data (modernized replacement for FPDS on SAM.gov)

| Field | Detail |
|-------|--------|
| URL | `https://api.sam.gov/contract-awards/v1/search` |
| Auth | API key |
| Rate Limit | Same tier structure as other SAM.gov APIs |
| Data Format | JSON (max 100/page, 400K total sync; 1M extract) |

**80+ filter parameters** including: `awardeeBusinessTypeName`, `coBusSizeDeterminationName`, `naicsCode`, `productOrServiceCode`, `awardeeUniqueEntityId`, `dollarsObligated`, `dateSigned`

**WOSB/8(a) fields**: Small Business status, Minority-Owned, WOSB certifications, 8(a) participation, HUBZone status

**Why High Value**: Shows who won what, for how much, under which set-aside. Essential for competitive intelligence.

---

### 7. GSA CALC+ Quick Rate API (v3)

**Purpose**: Awarded labor ceiling rates on GSA professional services schedules

| Field | Detail |
|-------|--------|
| URL | `https://api.gsa.gov/acquisition/calc/v3/api/ceilingrates/` |
| Auth | None required |
| Rate Limit | None documented |
| Data Format | JSON (or CSV via `&export=y`) |
| Records | ~51,863 total, refreshed nightly |

**Key Filters**: `business_size:s` (small business), `price_range:MIN,MAX`, `security_clearance`, `education_level`

**Why High Value**: Free pricing intelligence for proposal development. Know the ceiling rates before bidding.

---

### 8. SAM.gov Exclusions API (v4)

**Purpose**: Debarred/suspended entities

| Field | Detail |
|-------|--------|
| URL | `https://api.sam.gov/entity-information/v4/exclusions` |
| Auth | API key |
| Rate Limit | Same tier structure |
| Data Format | JSON |

**Why High Value**: Due diligence. Verify teaming partners are not excluded before pursuing a bid.

---

### 9. FPDS-NG ATOM Feed

**Purpose**: The authoritative historical record of all federal contract actions (since 2004)

| Field | Detail |
|-------|--------|
| URL | `https://www.fpds.gov/dbsight/FEEDS/ATOM?FEEDNAME=DETAIL&q=` |
| Auth | None required for ATOM feed |
| Rate Limit | 10 records/thread, 10 threads/search (100/search). No daily limit. |
| Data Format | XML (ATOM feed) |

**Query Syntax Example**:
```
https://www.fpds.gov/dbsight/FEEDS/ATOM?FEEDNAME=DETAIL&q=LAST_MOD_DATE:[2024/01/01,2024/12/31]+AGENCY_CODE:"3600"
```

**Small Business ATOM Fields**: Type of Set Aside, `genericBoolean03` (SBA-Certified WOSB), `genericBoolean04` (EDWOSB)

**Status**: FPDS is being migrated into SAM.gov. The Contract Awards API (Source 6) is the modernized replacement, but FPDS has deeper history.

---

## Tier 3 - Valuable Supplements (Implement Third)

### 10. SAM.gov Acquisition Subaward Reporting API

**Purpose**: Published federal subcontract data

| Field | Detail |
|-------|--------|
| URL | `https://api.sam.gov/prod/contract/v1/subcontracts/search` |
| Auth | API key |
| Rate Limit | Same tier structure |
| Data Format | JSON, max 1,000/page |

**Why Valuable**: Shows which large primes subcontract to WOSB/8(a) firms. Identifies potential teaming partners.

---

### 11. SAM.gov PSC (Product Service Codes) Public API

**Purpose**: Product and service classification codes reference data

| Field | Detail |
|-------|--------|
| URL | Documented at open.gsa.gov |
| Auth | API key |
| Data Format | JSON |

**Why Valuable**: Reference data for decoding PSC codes in opportunities and awards.

---

### 12. Acquisition Gateway - Forecast of Contracting Opportunities (FCO)

**Purpose**: Agency procurement forecasts -- upcoming opportunities BEFORE they are posted

| Field | Detail |
|-------|--------|
| URL | `https://acquisitiongateway.gov/forecast` |
| Auth | Varies by agency |
| API | No single unified API. Some agencies publish as spreadsheets/PDFs. |

**Why Valuable**: Earliest possible intelligence. See WOSB opportunities 6-12 months before SAM.gov posting. Competitive advantage. But requires per-agency approach.

---

## Tier 4 - Nice-to-Have

### 13. Regulations.gov API (v4)
- Federal rulemaking documents. Monitor WOSB/8(a) program rule changes.
- URL: `https://api.regulations.gov/v4/`
- Auth: API key via `X-Api-Key` header (free at api.data.gov)

### 14. Federal Register API (v1)
- Published federal rules and notices.
- URL: `https://www.federalregister.gov/api/v1/`
- Auth: None
- No rate limits documented

### 15. SAM.gov Assistance Listings API
- Federal grants and assistance programs (formerly CFDA).
- Lower priority for contract prospecting, but useful for pursuing grants alongside contracts.

### 16. SBIR.gov
- Small Business Innovation Research opportunities.
- No documented API. Congressional authorization expired Sept 2025.

### 17. SBA Dynamic Small Business Search (DSBS)
- Directory of small businesses. Same data available via SAM.gov Entity API.
- No public API. Use SAM.gov Entity Management API instead.

### 18. SBA SubNet
- Subcontracting opportunities from large businesses.
- No API, posting currently disabled. Use SAM.gov Subaward API instead.

### 19. eSRS (Electronic Subcontracting Reporting System)
- Prime contractor subcontracting plan reporting.
- Being decommissioned February 2026. Use SAM.gov Subaward API instead.

---

## Incumbent & Competitive Intelligence Strategy

Finding the **incumbent** -- the company that previously won a contract being rebid -- is one of the highest-value activities in federal prospecting. Knowing who won before, for how much, and under what terms directly informs bid/no-bid decisions, pricing strategy, and teaming approach.

Three of the data sources already cataloged above are the primary tools for incumbent research. This section consolidates their incumbent-specific capabilities and explains the overall strategy.

### USASpending.gov for Incumbent Research (Source 3)

USASpending.gov is the best starting point for incumbent analysis because it has **no rate limits** and covers all federal spending from FY2008 to present.

**Key endpoints for incumbent research**:

| Endpoint | Purpose |
|----------|---------|
| `/api/v2/search/spending_by_award/` | Search by NAICS, PSC, agency, or award type to find who won similar contracts |
| `/api/v2/awards/{award_id}/` | Full award details including recipient UEI, name, amounts, period of performance |
| `/api/v2/recipient/duns/{recipient_id}/` | Recipient profile with complete award history across all agencies |

**Bulk CSV downloads**: Available at `https://www.usaspending.gov/download_center/award_data_archive` (FY2008-present). Download entire fiscal years of award data for offline analysis.

**Incumbent use case**: Search by solicitation number or NAICS + agency to find who won the previous contract, the award amount, period of performance, and whether it was competitive or sole-source.

**Key fields for incumbent analysis**: `recipient_name`, `recipient_uei`, `award_amount`, `period_of_performance_start_date`, `period_of_performance_current_end_date`, `type_of_set_aside`, `naics_code`

---

### FPDS ATOM Feed for Incumbent Research (Source 9)

FPDS is the authoritative record of all federal contract actions and is the best tool for tracing a contract's full lifecycle from initial award through every modification and option year.

**Rate limits**: 100 records per search (10 records/thread x 10 threads), **no daily limit**. Unlimited searches.

**Feed URL**: `https://www.fpds.gov/dbsight/FEEDS/ATOM?FEEDNAME=DETAIL&q=`

**Incumbent use case**: Search by contract number or solicitation number to find all modifications, option years exercised, and total obligated amount over the contract lifecycle. This reveals the true total value of a contract (not just the initial award) and shows how many option years were exercised.

**Key fields for incumbent analysis**: `vendorName`, `vendorDUNSNumber`, `dollarObligated`, `signedDate`, `contractActionType`, `typeOfSetAside`

---

### SAM.gov Contract Awards API for Incumbent Research (Source 6)

The SAM.gov Contract Awards API is the modernized replacement for FPDS queries, with structured JSON responses and 80+ filter parameters.

**Capabilities**: Supports async extract mode for larger result sets (up to 1M records).

**Key filters for incumbent research**: `awardeeUniqueEntityId`, `naicsCode`, `dollarsObligated`, `productOrServiceCode`, `dateSigned`, `coBusSizeDeterminationName`

**Incumbent use case**: Search by agency + NAICS to find recent award patterns, identify repeat winners, and analyze pricing trends. Filter by `coBusSizeDeterminationName` to see whether contracts were awarded to small or large businesses.

**Key fields for incumbent analysis**: `awardeeBusinessName`, `awardeeUniqueEntityId`, `totalDollarsObligated`, `dateSigned`, `periodOfPerformance`, `coBusSizeDeterminationName`

---

### Incumbent Analysis Workflow

When a new opportunity appears on SAM.gov, the following workflow uses these three sources to build a complete picture of the incumbent:

1. **Find the previous award**: Search USASpending or FPDS by the solicitation number from the new opportunity. If the solicitation number is new, search by NAICS code + contracting agency + place of performance to find likely predecessor contracts.

2. **Understand the incumbent's pricing**: Compare the incumbent's award amount to understand ceiling rates. Cross-reference with GSA CALC+ (Source 7) for labor rate benchmarks. This informs whether to compete on price or value.

3. **Assess the competitive landscape**: Check if the incumbent is a small business (the contract may be a set-aside renewal) or a large business (the agency may be creating a new set-aside, which is an advantage for WOSB bidders). Look at the `type_of_set_aside` field on the previous award.

4. **Predict upcoming rebids**: Search USASpending for contracts with `period_of_performance_current_end_date` values 6-12 months in the future. These contracts will likely be rebid BEFORE they appear on SAM.gov, giving early preparation time.

5. **Cross-reference with our entity data**: Look up the incumbent's UEI in our `entity` table to see their certifications, NAICS codes, business size, and SBA status. This reveals whether they still qualify for set-asides and what their competitive position is.

---

## Commercial Sources (Paid)

### 20. GovWin IQ (Deltek)
- Pre-RFP intelligence, competitor analysis, pipeline tracking
- Cost: $5,000 - $119,000/year
- Goal: replicate as much as possible from free government APIs before considering

### 21. Bloomberg Government (BGOV)
- Federal contract intelligence and analytics
- Paid subscription

---

## Summary: Implementation Order

| Order | Source | Type | Rate Limit | Priority |
|-------|--------|------|------------|----------|
| 1 | SAM.gov Extracts | Bulk DL | 10-1K/day | Entity foundation |
| 2 | SAM.gov Opportunities | REST | 10-1K/day | Active contracts |
| 3 | USASpending.gov | REST | Unlimited | Spending analysis |
| 4 | SAM.gov Federal Hierarchy | REST | 10-1K/day | Agency mapping |
| 5 | SAM.gov Contract Awards | REST | 10-1K/day | Award history |
| 6 | GSA CALC+ | REST | Unlimited | Pricing intel |
| 7 | SAM.gov Exclusions | REST | 10-1K/day | Due diligence |
| 8 | FPDS ATOM Feed | XML | Unlimited | Deep history |
| 9 | SAM.gov Subaward | REST | 10-1K/day | Sub intel |
| 10 | Acquisition Gateway FCO | Manual | N/A | Forecasts |
