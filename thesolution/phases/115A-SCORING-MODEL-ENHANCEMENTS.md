# Phase 115A: Scoring Model Enhancements (Brainstorm Gap Analysis)

**Status:** IN PROGRESS
**Priority:** TBD
**Source:** C:\git\brainstorm\docs\phases\ (phases 24-30, metrics-framework)
**Dependencies:** Existing pWin infrastructure (Phase 45). OQS Strategic Alignment factor would require a new "growth targets" data model (new tables + UI). IVS nightly batch would require a scheduled job infrastructure.

---

## Existing Scoring Models

We currently have 3 scoring models in production. GoNoGo and qScore work adequately for their purpose. pWin needs a ground-up rethink.

### GoNoGo Score (Prospect Qualification)

- **Files**: `GoNoGoScoringService.cs`, `prospect_manager.py`
- **Output**: 0-40 raw, displayed as percentage
- **Factors** (4, unweighted, additive):
  1. **Set-Aside Favorability** (0-10): WOSB/EDWOSB→10, 8A→8, SBA/HZC/SDVOSB→5, None→0
  2. **Time Remaining** (0-10): >30d→10, 15-30d→7, 7-14d→4, <7d→1, past→0
  3. **NAICS Match** (0 or 10): binary — org entity with WOSB business type matches opp NAICS
  4. **Award Value** (0-10): ≥$1M→10, ≥$500K→8, ≥$100K→6, ≥$50K→4, <$50K→2
- **Used for**: Quick qualification decision when creating/reviewing prospects

### pWin (Probability of Win)

- **File**: `PWinService.cs`
- **Output**: 0-100
- **Factors** (7, weighted):
  1. **Set-Aside Match** (weight 0.20): org has required cert→100, related cert→50, none→0
  2. **NAICS Experience** (weight 0.20): ≥5 past perf records→100, ≥3→75, ≥1→50, 0→10
  3. **Competition Level** (weight 0.15): ≤3 vendors in NAICS→100, 4-6→70, 7-10→40, >10→20
  4. **Incumbent Advantage** (weight 0.15): org is incumbent→100, no incumbent→70, other→30
  5. **Teaming Strength** (weight 0.10): ≥3 partners→100, 1-2→60, 0→30
  6. **Time to Respond** (weight 0.10): ≥31d→100, 15-30d→70, 7-14d→40, <7d→10
  7. **Contract Value Fit** (weight 0.10): within 2x avg→100, within 5x→60, >5x→30
- **Categories**: ≥70 High, 40-69 Medium, 15-39 Low, <15 VeryLow
- **Known issues**: Current model is not accurate or effective. Factors use crude thresholds and don't account for agency-specific patterns, proposal quality, past performance relevance, or competitive dynamics. The NAICS experience factor treats all past performance equally regardless of relevance. Competition level uses a simple vendor count rather than analyzing actual competitive positioning. Incumbent advantage is binary (you are or aren't) rather than considering vulnerability signals. This phase aims to replace or significantly enhance pWin.

### qScore (Opportunity Quality / Recommendation Score)

- **File**: `RecommendedOpportunityService.cs`
- **Output**: 0-100 (normalized from 60-point raw)
- **Factors** (4, unweighted, additive):
  1. **Set-Aside Match** (0-20): org has cert→20, related cert→10, filtered out if missing required
  2. **NAICS Match** (0-20): primary NAICS→20, secondary→15
  3. **Time Remaining** (0-10): ≥30d→10, 14-29d→7, 7-13d→4, <7d→1
  4. **Contract Value** (0-10): >$1M→10, >$500K→8, >$100K→6, >$50K→4, ≤$50K→2
- **Used for**: Recommendation engine, computed on-demand (not stored on prospects)

---

## Summary

The brainstorm project designed several scoring models beyond our current GoNoGo, pWin, and qScore. These would give users richer decision-making tools. The UX review from the brainstorm flagged "score proliferation" as a risk — 9 distinct 0-100 scores is confusing. Recommendation: keep pWin as the headline metric, add only the most impactful new scores, and present others as supporting detail.

---

## Overlap with Existing Features

| Idea | Status | What Exists |
|------|--------|-------------|
| Opportunity Quality Score (OQS) | **ENHANCEMENT** | Extends existing qScore from 4 unweighted factors to 7 weighted factors; would replace `RecommendedOpportunityService` scoring |
| Pursuit Priority Score | **NEW** | Combines pWin + OQS into a single pipeline sort metric; no equivalent exists today |
| Incumbent Vulnerability Score (IVS) | **PARTIAL** | `MarketIntelService.GetIncumbentAnalysisAsync()` returns `VulnerabilitySignals` (string list) + burn rate + percent spent. No formal 0-100 scored model. |
| Competitor Strength Index (CSI) | **NEW** | Market share exists (top 10 vendors by $ in `MarketIntelService.GetMarketShareAsync()`), but no per-competitor scoring model |
| Partner Compatibility Score (PCS) | **NEW** | pWin has a "teaming strength" factor but it's just a subaward partner count, not quality/fit scoring |
| Open Door Score | **NEW** | No prime engagement scoring. `sam_subaward` data is used for teaming partner search and pWin teaming strength (partner count), but no prime-level engagement quality scoring. |

---

## Proposed Scores

### 1. Opportunity Quality Score (OQS) — "Should I Want This?" [ENHANCEMENT of existing qScore]

Enhances the existing qScore (see above) from 4 unweighted factors to a 7-factor weighted model measuring opportunity desirability independent of win probability. Would replace `RecommendedOpportunityService`'s current scoring logic:
- Profile Match Strength (0.20) — how well the opp matches your NAICS/PSC/certs
- Estimated Value Alignment (0.15) — is the contract size in your sweet spot?
- Competition Level (0.10) — fewer competitors = better opportunity
- Timeline Feasibility (0.15) — do you have time to respond?
- Strategic Alignment (0.15) — does this advance your growth goals? *(requires new user-defined growth targets — no such data structure exists yet)*
- Reuse Potential (0.10) — can you reuse existing proposals/past performance? *(requires proposal tracking — not in scope; past performance records exist via `organization_past_performance`)*
- Growth Potential (0.15) — is this a foothold into a new agency/NAICS?

**Key insight:** Creates a 2D decision matrix — OQS ("should I want this?") vs pWin ("can I win this?"). High OQS + High pWin = must pursue. Low OQS + High pWin = easy win but not strategic. High OQS + Low pWin = invest in capture. Low both = skip.

**Source:** brainstorm phase-29

### 2. Pursuit Priority Score [NEW — combines existing pWin + proposed OQS]

Combined metric: `(pWin × 0.6) + (OQS × 0.4)` as default pipeline sort order. Low-confidence scores discounted by 15%. Depends on both an enhanced pWin and the OQS enhancement above.

**Value:** Single number for "what should I work on next?" — replaces manual prioritization.

**Source:** brainstorm metrics-framework

### 3. Incumbent Vulnerability Score (IVS) — Formal 6-Factor Model [NEW — formalizes existing signals]

`MarketIntelService.GetIncumbentAnalysisAsync()` already returns vulnerability signals as a string list, burn rate, and percent spent, but has no formal scored model. This would replace those ad-hoc signals with a scored 0-100 model:
- Contract Age (0.15) — older contracts more vulnerable
- Option Exercise History (0.25) — non-exercised options = major signal *(must be inferred from FPDS modification records; no explicit option-exercise column exists)*
- Spend Anomalies (0.15) — declining spend suggests dissatisfaction
- Certification Risk (0.15) — incumbent losing small biz status
- Agency Re-compete Pattern (0.15) — does this agency typically re-compete or sole-source?
- Number of Offers on Original (0.15) — more original bidders = more likely re-compete

Computed nightly for all active contracts in user-relevant NAICS codes. Trend tracking over time.

**Source:** brainstorm phase-26

### 4. Competitor Strength Index (CSI) [NEW]

5-factor model per competitor:
- Federal Revenue (0.25)
- Win Rate (0.20) *(NOT computable — we only have FPDS wins, not unsuccessful bids/offers)*
- Agency Penetration (0.20) — how many offices they've won at
- Team Stability (0.15) — do they keep the same subs?
- Certification Portfolio (0.20) — breadth of set-aside eligibility

Has both a general-purpose variant and a context-specific variant (scored against a specific opportunity).

**Source:** brainstorm phase-30

### 5. Partner Compatibility Score (PCS) [NEW]

6-factor model for teaming partner evaluation:
- Capability Complement (0.25) — do they fill your gaps?
- Agency Track Record (0.25) — have they won at this agency?
- Past Teaming History (0.15) — have you worked together before?
- Size Compatibility (0.15) — won't you exceed size standards together?
- Certification Complement (0.10) — do their certs add eligibility?
- Clean Record (0.10) — no exclusions, no terminations for cause

**Source:** brainstorm phase-45, metrics-framework

### 6. Open Door Score [NEW]

Rates prime contractors on how much they actually engage small business subs:
- Small business sub spend %
- Sub diversity count
- Average subaward size
- Sub retention rate
- NAICS breadth of sub work
- Year-over-year trend

**Value:** Helps small businesses find primes who are actually good teaming partners, not just checking boxes.

**Source:** brainstorm phase-47

---

## UX Recommendations (from brainstorm UX review)

- **Don't show all scores at once.** pWin is the headline. OQS and Pursuit Priority could be secondary. Others (CSI, PCS, IVS, Open Door) are contextual — show them only where relevant.
- **2D scatter plot** of pWin vs OQS would be a powerful pipeline visualization.
- **Confidence indicators** — every score should show High/Medium/Low confidence based on data completeness, so users don't over-trust scores built on thin data.

---

## Implementation Notes

- **Existing models**: GoNoGo and qScore work adequately for their purposes. pWin specifically needs a ground-up rethink — it is not accurate, not effective, and uses crude thresholds that don't reflect real-world win probability. Any work in this phase should start with pWin.
- Most scoring factors use data we already have (awards, entities, subawards, NAICS, set-asides). Exceptions: CSI Win Rate (no bid data, only wins), OQS Strategic Alignment (needs new user-defined goals), OQS Reuse Potential (needs proposal tracking or scoping down to past performance only)
- The brainstorm designed a pluggable factor engine with configurable weights — our current pWin implementation could be extended or replaced entirely
- pWin calibration/backtesting (AUC-ROC target >0.70, Bayesian weight optimization) was a separate brainstorm phase — worth considering once we have enough historical win/loss data

## Implementation Progress

### Completed
- [x] Enhanced pWin — continuous scoring curves, confidence levels, past performance relevance, vulnerability-aware incumbent factor
- [x] Enhanced OQS — 7-factor weighted model replacing 4-factor qScore (profile match, value alignment, competition, timeline, reuse, growth, re-compete advantage)
- [x] IVS Service — 6-factor incumbent vulnerability model (contract age, option exercise, spend anomalies, cert risk, agency patterns, offers)
- [x] CSI Service — 5-factor competitor strength model (federal revenue, agency penetration, certs, team stability, NAICS concentration)
- [x] PCS Service — 6-factor partner compatibility model (capability complement, agency track record, teaming history, size compatibility, cert complement, clean record)
- [x] Open Door Service — 6-factor prime engagement scoring (small biz sub spend, diversity, avg subaward size, retention, NAICS breadth, YoY trend)
- [x] Pursuit Priority Score — combined pWin×0.6 + OQS×0.4 with confidence discount
- [x] API endpoints for all new scores
- [x] DI registration for all new services

### Remaining
- [ ] UI components for new scores (IVS, CSI, PCS, Open Door displays)
- [ ] Pursuit Priority as default pipeline sort
- [ ] 2D scatter plot visualization (pWin vs OQS)
- [ ] Unit tests for new scoring services
- [ ] Integration tests
- [ ] Python CLI parity (if needed)
