# Phase 45: Opportunity Intelligence & Re-compete Targeting

**Status**: NOT STARTED
**Dependencies**: Phase 40 (Detail Views & Competitive Intelligence)
**Blocked By**: None (Phase 40 builds the detail page shells; this phase makes them smart)

## Purpose

Transform FedProspect from a search tool into an intelligence platform. Users should open the app and immediately see the best opportunities for their company — scored, ranked, and analyzed. When they click one, they get a complete picture: who the incumbent is, what the contract costs, whether their team can win it, and what the probability of winning is.

This phase also adds proactive re-compete targeting: surfacing contracts that are expiring soon — before the solicitation hits SAM.gov — so users can get ahead of the competition.

## What the User Sees

### 1. Dashboard: Top 10 Recommended Opportunities

The dashboard (Phase 60's landing page) gets a prominent "Top Opportunities For You" section — the first thing users see when they log in.

**How it works:**
- System queries opportunities matching the user's org profile (NAICS codes, certifications, set-aside eligibility from Phase 20's company profile wizard)
- Ranks by a composite relevance score (see Scoring Model below)
- Displays top 10 as cards with summary info

**Each opportunity card shows:**
- Title (truncated) + Notice ID
- Agency / Sub-agency
- Set-aside type badge (WOSB, 8(a), SDVOSB, etc.)
- NAICS code + description
- Estimated value range or award ceiling
- Response deadline + days remaining (color-coded: green >30d, yellow 14-30d, red <14d)
- Contract type (FFP, T&M, Cost-Plus, IDIQ, etc.)
- Place of performance (state/city or OCONUS indicator)
- pWin badge (percentage, color-coded)
- Re-compete indicator (if applicable, with incumbent name)
- "Quick Add to Pipeline" button

**Cards are clickable** — opening the Opportunity Intelligence Panel (see below).

**Refresh behavior:**
- Auto-refreshes daily via backend job
- "Refresh Now" button for on-demand recalculation
- Shows "Last updated: X hours ago" timestamp

### 2. Dashboard: Contracts Expiring Soon (Re-compete Targets)

A second dashboard section: "Contracts Expiring Soon — Displacement Opportunities"

**How it works:**
- Queries `fpds_contract` for contracts in the user's NAICS codes with `ultimate_completion_date` within the next 6-12 months
- Filters to set-aside types matching user's certifications (WOSB, 8(a))
- Cross-references: has a solicitation already been posted on SAM.gov for this re-compete?
- Ranks by proximity to expiration + contract value + incumbent vulnerability signals

**Each expiring contract card shows:**
- Contract title / description
- PIID (contract number)
- Incumbent name + UEI
- NAICS code
- Current contract value (base + all options)
- Performance period end date + months remaining
- Monthly burn rate + percent spent
- Incumbent health indicators:
  - Registration status (active/expired/expiring)
  - Exclusion status (debarred/suspended = major opportunity)
  - Burn rate health (on track / overspending / underspending)
- Re-solicitation status: "Not Yet Posted" / "Pre-Solicitation Posted" / "Solicitation Active" (linked to SAM.gov opportunity if found)
- "Track This Re-compete" button → creates a prospect in NEW status

### 3. Opportunity Intelligence Panel

When a user clicks any opportunity (from dashboard, search results, or anywhere in the app), a full-width slide-out panel or detail page opens with deep analysis organized into tabs:

#### Tab 1: Overview & Summary
- **The Ask**: Plain-language summary of what the government needs (from opportunity description, parsed and summarized)
- Contract type (FFP, T&M, Cost-Plus, IDIQ, BPA, etc.)
- Estimated value / award ceiling
- Set-aside type + eligibility check against user's profile (pass/fail badges)
- NAICS code + size standard + user's company size compliance (pass/fail)
- Place of performance + CONUS/OCONUS
- Response deadline with countdown
- Solicitation number, notice type, archive type
- Points of contact (name, email, phone)
- Link to full solicitation on SAM.gov

#### Tab 2: Qualification & Readiness Assessment
This tab answers: "Can we bid on this? Should we?"

**Certification & Eligibility Checks** (auto-evaluated against company profile):
- [ ] Set-aside match (WOSB/8(a)/SDVOSB/HUBZone — does our cert match?)
- [ ] NAICS code match (is this one of our registered NAICS codes?)
- [ ] Size standard compliance (revenue/employees under the threshold?)
- [ ] Security clearance required? (flag if description mentions clearance keywords: TS, Secret, Top Secret, SCI, Public Trust)
- [ ] Place of performance feasible? (OCONUS flag, state match)
- [ ] Registration active in SAM.gov?

**Staffing & Capability Assessment** (manual + data-assisted):
- Do we need to hire? (flag if job categories in description don't match known capabilities)
- Teaming partner needed? (show existing JV/teaming relationships from subaward data)
- Suggested teaming partners (entities with WOSB/8(a) certs + this NAICS code + past performance in this agency)
- Past performance match: list user's org's prior contracts in this NAICS code (from `fpds_contract` where `vendor_uei` = user's org UEI)

**Go/No-Go Score**: Display the existing 4-factor score (set-aside, time, NAICS, value) with breakdown + gauge chart

#### Tab 3: Competitive Intelligence
- **Incumbent Analysis** (if re-compete):
  - Incumbent name, UEI, company profile link
  - Incumbent's current contract details (value, period, burn rate)
  - Incumbent's win rate in this NAICS
  - Incumbent's exclusion/debarment status
  - Incumbent's SAM.gov registration status (expired = vulnerability)
  - Incumbent's other active contracts (spread thin?)
- **Market Landscape**:
  - Top 10 vendors by award value in this NAICS code (bar chart)
  - Market share percentages
  - Number of historical bidders on similar opportunities
  - Average award value in this NAICS
- **Competitor Profiles** (expandable cards for top 5 competitors):
  - Company name, size, certifications
  - Win rate, average contract size
  - Recent awards in this NAICS
  - Known teaming relationships (from subaward data)

#### Tab 4: Financials & pWin
- **pWin Score**: Large, prominent display (percentage + color gauge)
  - Factor breakdown (see pWin Model below)
  - "What would improve our chances?" actionable suggestions
- **Financial Analysis**:
  - Estimated contract value range
  - Historical award values for similar NAICS/set-aside combinations (min, avg, median, max)
  - Burn rate of incumbent's current contract (if re-compete)
  - Suggested bid range based on historical data
- **ROI Estimate** (if user fills in proposal cost estimate):
  - Estimated proposal cost vs. contract value
  - Break-even probability threshold
  - Gross margin estimate at expected win rate

#### Tab 5: Action & Tracking
- "Add to Pipeline" → creates prospect with all data pre-populated
- "Save for Later" → bookmarks without creating prospect
- "Share with Team" → internal notification to org members
- Notes field for quick capture thoughts
- Activity log (who viewed, when, what actions taken)

## pWin (Probability of Win) Model

### Calculation

Weighted composite score, 0-100%:

| Factor | Weight | Source | Scoring |
|--------|--------|--------|---------|
| Set-aside match | 20% | Company profile vs. opportunity | Exact cert match = 100%, related cert = 50%, no cert = 0% |
| NAICS experience | 20% | `fpds_contract` where vendor = user's org | 5+ prior contracts = 100%, 3-4 = 75%, 1-2 = 50%, 0 = 10% |
| Competition level | 15% | Historical bidder count for NAICS/agency | 1-3 bidders avg = 100%, 4-6 = 70%, 7-10 = 40%, 10+ = 20% |
| Incumbent advantage | 15% | Is this a re-compete? Are we the incumbent? | We are incumbent = 100%, no incumbent = 70%, competitor is incumbent = 30% |
| Teaming strength | 10% | Teaming partners' combined NAICS experience | Strong team (3+ partners with NAICS exp) = 100%, moderate = 60%, solo = 30% |
| Time to respond | 10% | Days until deadline | 30+ days = 100%, 14-30 = 70%, 7-14 = 40%, <7 = 10% |
| Contract value fit | 10% | Estimated value vs. company's avg contract size | Within 2x = 100%, 2-5x = 60%, 5x+ = 30% |

**Formula**: `pWin = Σ (factor_score × weight)`

### pWin Categories
- **High** (70-100%): Strong match, pursue aggressively
- **Medium** (40-69%): Good fit, evaluate further
- **Low** (15-39%): Weak fit, consider teaming or pass
- **Very Low** (0-14%): Likely pass, significant gaps

### Actionable Suggestions
Based on the lowest-scoring factors, the system suggests improvements:
- Low NAICS experience → "Consider teaming with [Entity X] who has 12 contracts in this NAICS"
- Low teaming strength → "Find teaming partners: [link to teaming partner search pre-filtered]"
- Incumbent advantage against us → "Incumbent [Company] has won 3 consecutive re-competes. Consider differentiation strategy."
- Low competition data → "No historical bid data available. Contact the contracting officer for industry day information."

## New Backend Endpoints Required

### Priority 1 — Must Have for Dashboard

```
GET /api/v1/opportunities/recommended
  Query: ?limit=10
  Auth: Org-scoped (uses org's NAICS codes and certifications)
  Returns: OpportunityRecommendationDto[] (opportunity summary + relevance score + pWin)
  Logic: Match org profile → score → rank → return top N

GET /api/v1/contracts/expiring
  Query: ?monthsAhead=12&naicsCode={code}&setAside={type}&limit=20
  Auth: Org-scoped
  Returns: ExpiringContractDto[] (contract summary + incumbent info + burn rate + vulnerability signals + re-solicitation status)
  Logic: Query fpds_contract by completion date range → join incumbent data → check SAM.gov for posted re-solicitations

POST /api/v1/prospects/{id}/calculate-pwin
  Auth: Org-scoped
  Returns: PWinResultDto (score, factor breakdown, suggestions)
  Logic: Run pWin model (7 weighted factors) → persist to prospect.win_probability → return breakdown
```

### Priority 2 — For Intelligence Panel

```
GET /api/v1/opportunities/{noticeId}/intelligence
  Returns: OpportunityIntelligenceDto (combined data from opportunity + fpds_contract + usaspending + entity views)
  Logic: Expose ProcurementIntelligenceView + competitor analysis + market share data

GET /api/v1/opportunities/{noticeId}/qualification-check
  Auth: Org-scoped
  Returns: QualificationCheckDto (checklist of pass/fail items against org profile)
  Logic: Compare opportunity requirements to org's NAICS codes, certifications, size standards

GET /api/v1/awards/market-share
  Query: ?naicsCode={code}&years=3&limit=10
  Returns: MarketShareDto (top vendors by award value, market percentages)
  Logic: Aggregate fpds_contract by vendor for given NAICS, compute shares

GET /api/v1/opportunities/{noticeId}/incumbent-analysis
  Returns: IncumbentAnalysisDto (incumbent profile + contract health + vulnerability signals)
  Logic: Look up incumbent from opportunity → fetch their contracts, burn rate, registration status, exclusion status
```

### Priority 3 — For pWin Suggestions

```
GET /api/v1/opportunities/{noticeId}/teaming-suggestions
  Query: ?limit=5
  Auth: Org-scoped
  Returns: TeamingSuggestionDto[] (entities with matching NAICS + certs + past performance, not already teaming partners)
  Logic: Find entities with WOSB/8(a) certs + this NAICS + prior contracts with this agency

GET /api/v1/opportunities/{noticeId}/historical-bids
  Returns: HistoricalBidDataDto (average bidder count, avg award value, historical trend for this NAICS/agency combination)
  Logic: Aggregate fpds_contract by NAICS + contracting agency → compute averages
```

## Database Changes

### New Tables
None required — all data exists in current schema. New endpoints query existing tables and views.

### New Views (optional, for performance)

```sql
-- v_recommended_opportunities: Pre-joined opportunity + org profile match
-- Could be materialized or computed on-demand depending on performance

-- v_expiring_contracts: fpds_contract filtered by completion date range
-- with incumbent profile data joined
CREATE OR REPLACE VIEW v_expiring_contracts AS
SELECT
    fc.piid,
    fc.description_of_requirement,
    fc.naics_code,
    fc.type_of_set_aside,
    fc.vendor_uei,
    fc.vendor_name,
    fc.base_and_all_options_value,
    fc.ultimate_completion_date,
    fc.date_signed,
    -- Incumbent health signals
    e.registration_status,
    e.registration_expiration_date,
    ex.exclusion_type IS NOT NULL AS is_excluded,
    -- Burn rate
    TIMESTAMPDIFF(MONTH, fc.date_signed, fc.ultimate_completion_date) AS total_months,
    fc.dollars_obligated / NULLIF(TIMESTAMPDIFF(MONTH, fc.date_signed, NOW()), 0) AS monthly_burn_rate,
    fc.dollars_obligated / NULLIF(fc.base_and_all_options_value, 0) * 100 AS percent_spent,
    -- Re-solicitation check
    o.notice_id AS resolicitation_notice_id,
    o.response_deadline AS resolicitation_deadline
FROM fpds_contract fc
LEFT JOIN entity e ON e.uei = fc.vendor_uei
LEFT JOIN sam_exclusion ex ON ex.entity_uei = fc.vendor_uei AND ex.termination_date IS NULL
LEFT JOIN opportunity o ON o.solicitation_number = fc.solicitation_id AND o.archive_type != 'archived'
WHERE fc.ultimate_completion_date BETWEEN NOW() AND DATE_ADD(NOW(), INTERVAL 12 MONTH);
```

## UI Components

### New Components
- `OpportunityRecommendationCard` — summary card for dashboard top 10
- `ExpiringContractCard` — summary card for re-compete targets
- `OpportunityIntelligencePanel` — slide-out or full-page detail with 5 tabs
- `PWinGauge` — circular gauge chart showing pWin percentage with color coding
- `QualificationChecklist` — pass/fail badge list for certification/eligibility checks
- `MarketShareChart` — horizontal bar chart of top vendors by NAICS
- `IncumbentHealthCard` — incumbent status with vulnerability indicators
- `TeamingSuggestionList` — recommended teaming partners with relevance scores
- `CompetitorProfileCard` — expandable card for competitor details

### Modified Components (from other phases)
- `DashboardPage` (Phase 60) — add "Top Opportunities" and "Expiring Contracts" sections above pipeline metrics
- `OpportunityDetailPage` (Phase 40) — replace basic tabs with full Intelligence Panel tabs
- `ProspectCreateForm` (Phase 50) — pre-populate from intelligence data when creating from recommendation

## Acceptance Criteria

1. User logs in and sees top 10 recommended opportunities personalized to their org's NAICS codes and certifications
2. Each recommended opportunity shows summary info: value, deadline, set-aside, contract type, pWin, and re-compete status
3. Clicking an opportunity opens the Intelligence Panel with 5 tabs of deep analysis
4. Qualification tab shows automated pass/fail checks against org profile
5. Competitive Intelligence tab shows incumbent analysis with vulnerability signals
6. pWin is automatically calculated with 7-factor breakdown and actionable suggestions
7. "Contracts Expiring Soon" section shows displacement opportunities with incumbent health indicators
8. User can create a prospect directly from any recommendation or expiring contract with pre-populated data
9. Dashboard refreshes recommendations daily; manual refresh available
10. All endpoints are org-scoped (multi-tenant isolation maintained)

## Deferred to Post-MVP

- AI-generated opportunity summaries (LLM parsing of full solicitation PDFs)
- Email alerts for new high-pWin opportunities
- Custom pWin model weights per organization
- Competitive win/loss history tracking (requires manual bid outcome entry)
- Integration with GovWin IQ or other paid intelligence sources
- Predictive re-solicitation timing (ML model for "when will this be re-competed?")
