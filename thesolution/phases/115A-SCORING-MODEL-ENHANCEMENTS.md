# Phase 115A: Scoring Model Enhancements (Brainstorm Gap Analysis)

**Status:** IDEA — from brainstorm analysis, not yet prioritized
**Priority:** TBD
**Source:** C:\git\brainstorm\docs\phases\ (phases 24-30, metrics-framework)
**Dependencies:** Existing pWin infrastructure (Phase 45). OQS Strategic Alignment factor would require a new "growth targets" data model (new tables + UI). IVS nightly batch would require a scheduled job infrastructure.

---

## Summary

The brainstorm project designed several scoring models beyond our current pWin and qScore. These would give users richer decision-making tools. The UX review from the brainstorm flagged "score proliferation" as a risk — 9 distinct 0-100 scores is confusing. Recommendation: keep pWin as the headline metric, add only the most impactful new scores, and present others as supporting detail.

---

## Overlap with Existing Features

| Idea | Status | What Exists |
|------|--------|-------------|
| Opportunity Quality Score (OQS) | **NEW** | Nothing measures opportunity desirability independent of org fit |
| Pursuit Priority Score | **NEW** | `RecommendedOpportunityService` has a basic 4-factor qScore (set-aside + NAICS + time + value, normalized to 0-100), but not a unified pWin+OQS composite |
| Incumbent Vulnerability Score (IVS) | **PARTIAL** | `MarketIntelService.GetIncumbentAnalysisAsync()` returns `VulnerabilitySignals` (string list) + burn rate + percent spent. No formal 0-100 scored model. |
| Competitor Strength Index (CSI) | **NEW** | Market share exists (top 10 vendors by $ in `MarketIntelService.GetMarketShareAsync()`), but no per-competitor scoring model |
| Partner Compatibility Score (PCS) | **NEW** | pWin has a "teaming strength" factor but it's just a subaward partner count, not quality/fit scoring |
| Open Door Score | **NEW** | No prime engagement scoring. `sam_subaward` data is used for teaming partner search and pWin teaming strength (partner count), but no prime-level engagement quality scoring. |

---

## New Scores We Don't Have

### 1. Opportunity Quality Score (OQS) — "Should I Want This?"

A 7-factor model measuring opportunity desirability independent of win probability:
- Profile Match Strength (0.20) — how well the opp matches your NAICS/PSC/certs
- Estimated Value Alignment (0.15) — is the contract size in your sweet spot?
- Competition Level (0.10) — fewer competitors = better opportunity
- Timeline Feasibility (0.15) — do you have time to respond?
- Strategic Alignment (0.15) — does this advance your growth goals? *(requires new user-defined growth targets — no such data structure exists yet)*
- Reuse Potential (0.10) — can you reuse existing proposals/past performance? *(requires proposal tracking — not in scope; past performance records exist via `organization_past_performance`)*
- Growth Potential (0.15) — is this a foothold into a new agency/NAICS?

**Key insight:** Creates a 2D decision matrix — OQS ("should I want this?") vs pWin ("can I win this?"). High OQS + High pWin = must pursue. Low OQS + High pWin = easy win but not strategic. High OQS + Low pWin = invest in capture. Low both = skip.

**Source:** brainstorm phase-29

### 2. Pursuit Priority Score

Combined metric: `(pWin × 0.6) + (OQS × 0.4)` as default pipeline sort order. Low-confidence scores discounted by 15%.

**Value:** Single number for "what should I work on next?" — replaces manual prioritization.

**Source:** brainstorm metrics-framework

### 3. Incumbent Vulnerability Score (IVS) — Formal 6-Factor Model

We have vulnerability signals, but the brainstorm designed a formal scored model:
- Contract Age (0.15) — older contracts more vulnerable
- Option Exercise History (0.25) — non-exercised options = major signal *(must be inferred from FPDS modification records; no explicit option-exercise column exists)*
- Spend Anomalies (0.15) — declining spend suggests dissatisfaction
- Certification Risk (0.15) — incumbent losing small biz status
- Agency Re-compete Pattern (0.15) — does this agency typically re-compete or sole-source?
- Number of Offers on Original (0.15) — more original bidders = more likely re-compete

Computed nightly for all active contracts in user-relevant NAICS codes. Trend tracking over time.

**Source:** brainstorm phase-26

### 4. Competitor Strength Index (CSI)

5-factor model per competitor:
- Federal Revenue (0.25)
- Win Rate (0.20) *(NOT computable — we only have FPDS wins, not unsuccessful bids/offers)*
- Agency Penetration (0.20) — how many offices they've won at
- Team Stability (0.15) — do they keep the same subs?
- Certification Portfolio (0.20) — breadth of set-aside eligibility

Has both a general-purpose variant and a context-specific variant (scored against a specific opportunity).

**Source:** brainstorm phase-30

### 5. Partner Compatibility Score (PCS)

6-factor model for teaming partner evaluation:
- Capability Complement (0.25) — do they fill your gaps?
- Agency Track Record (0.25) — have they won at this agency?
- Past Teaming History (0.15) — have you worked together before?
- Size Compatibility (0.15) — won't you exceed size standards together?
- Certification Complement (0.10) — do their certs add eligibility?
- Clean Record (0.10) — no exclusions, no terminations for cause

**Source:** brainstorm phase-45, metrics-framework

### 6. Open Door Score

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

- Most scoring factors use data we already have (awards, entities, subawards, NAICS, set-asides). Exceptions: CSI Win Rate (no bid data, only wins), OQS Strategic Alignment (needs new user-defined goals), OQS Reuse Potential (needs proposal tracking or scoping down to past performance only)
- The brainstorm designed a pluggable factor engine with configurable weights — our current pWin implementation could be extended
- pWin calibration/backtesting (AUC-ROC target >0.70, Bayesian weight optimization) was a separate brainstorm phase — worth considering once we have enough historical win/loss data
