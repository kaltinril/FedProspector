# Phase 115C: Advanced Competitive Intelligence (Brainstorm Gap Analysis)

**Status:** IDEA — from brainstorm analysis, not yet prioritized
**Priority:** TBD
**Source:** C:\git\brainstorm\docs\phases\ (phases 38-44, 50)
**Dependencies:** Awards data (loaded), FPDS data (loaded), Entity data (loaded)

---

## Summary

We have basic competitive intelligence (market share, top vendors by NAICS, competitor profiles). The brainstorm designed a much deeper competitive intelligence suite. Several of these are high-value and buildable on existing data.

---

## Overlap with Existing Features

| Idea | Status | What Exists |
|------|--------|-------------|
| Re-compete Early Warning | **PARTIAL** | `ExpiringContractService` finds contracts by completion date (12-month window). `v_expiring_contracts` view joins opportunity+FPDS+USASpending+exclusions. Missing: option exercise analysis, spend pattern modeling, agency behavior prediction. |
| Agency Re-compete Patterns | **NEW** — data ready | All 7 behavioral metrics are computable from existing FPDS data. No aggregation service yet. |
| Competitor Dossier | **PARTIAL** | `EntityDetailPage` has entity overview, competitor analysis tab (`v_competitor_analysis` view), NAICS codes, business types, SBA certs, past performance aggregates. Missing: unified one-click PDF export, head-to-head encounters, teaming network. |
| Enhanced CO Profiles | **PARTIAL** | `contracting_officer` table stores name, email, phone, title, department, office. `opportunity_poc` links officers to opportunities. Missing: award history, set-aside preferences, procurement timelines, retention rates. |
| Agency Buying Patterns | **NEW** — data ready | FPDS/USASpending data exists. `v_set_aside_trend` provides yearly set-aside trends by NAICS. Missing: full agency profile with volume trends, NAICS distribution, seasonal patterns, contract type distribution. |
| Congressional Appropriations | **NEW** — needs Congress.gov API | No government funding/budget data loaded |
| Procurement Wave Forecasting | **NEW** | Composite of re-compete prediction + appropriations + seasonal patterns |
| Social Graph | **NEW** | Data exists in awards + subawards. No graph visualization. |

---

## Features We Don't Have

### 1. Re-compete Early Warning System

Predict upcoming re-competes 12-18 months before solicitation:
- Track all active contracts in user-relevant NAICS codes
- Calculate months remaining on current period of performance
- Account for option years (exercised vs not)
- Tiered action recommendations based on timeline
- Dedicated re-compete tracking board
- Target: >60% prediction accuracy

**How it differs from our expiring contracts:** Our current feature shows contracts approaching expiration. This would be more proactive — predicting re-competes even when options remain, based on spend patterns, option exercise history, and agency behavior.

**Source:** brainstorm phase-39

### 2. Agency Re-compete Pattern Analysis

7 behavioral metrics per contracting office:
- Incumbent retention rate — how often does the incumbent win the re-compete?
- New entrant win rate — how often does a newcomer unseat the incumbent?
- Set-aside shift frequency — how often do they change set-aside type between contracts?
- Solicitation lead time — how far in advance do they post?
- Bridge extension frequency — how often do they extend contracts past PoP?
- Sole-source rate — what % of their awards are sole-source?
- NAICS shift rate — how often do they change NAICS on re-competes?

Hierarchical fallback: if office-level data is sparse, fall back to sub-tier agency, then department.

**Value:** "This office retains incumbents 80% of the time — don't waste resources unless you have a strong angle" vs "This office has 40% new entrant win rate — worth pursuing."

**Source:** brainstorm phase-40

### 3. Competitor Dossier Auto-Generation

One-click competitor profile with 9 sections:
1. Company overview (from SAM.gov entity data)
2. Federal revenue summary (from USASpending)
3. Contract portfolio (active contracts, NAICS mix, agency mix)
4. Top agencies and relationships
5. NAICS coverage map
6. Recent wins and losses
7. Teaming network (who they sub to / who subs to them)
8. Certifications and set-aside eligibility
9. Head-to-head: your competitive encounters

PDF export. Target: sub-3-second generation.

**How it differs from our entity detail page:** Our entity detail has some of this, but spread across tabs. The dossier would be a single, printable, shareable document optimized for capture meetings.

**Source:** brainstorm phase-43

### 4. Contracting Officer Profiles (Enhanced)

Beyond basic name/contact:
- Award history and volume
- Set-aside preferences (% of awards by set-aside type)
- Procurement timelines (average days from posting to award)
- Sole-source frequency
- Incumbent retention rates
- Preferred contract types (FFP vs T&M vs cost-plus)

**Source:** brainstorm phase-50

### 5. Agency Buying Pattern Profiles (Enhanced)

Beyond basic agency info:
- Procurement volume trends (3-year)
- NAICS distribution with shifts over time
- Set-aside utilization trends
- Seasonal patterns (Q4 spending surge, etc.)
- Competition preferences (sealed bid vs negotiated)
- Contract type distribution
- Hierarchical rollup (office → sub-tier → department)

**Source:** brainstorm phase-50

### 6. Congressional Appropriations Leading Indicator

Track funding that drives procurement:
- Congress.gov API integration for appropriations bill tracking
- Budget justification document parsing
- "Procurement Weather Forecast" per NAICS/agency: heating up / stable / cooling down
- Daily monitoring during budget season

**New data source needed:** Congress.gov API (free, no auth)

**Source:** brainstorm phase-41

### 7. Procurement Wave Forecasting Dashboard

18-month procurement forecast fusing multiple signals:
- Re-compete predictions
- Appropriations/budget signals
- Seasonal patterns (federal fiscal year)
- Live SAM.gov opportunity data
- "Hot spots" analysis — NAICS/agency combos with unusually high upcoming activity
- Personalized "Your Market Outlook" summary

**Source:** brainstorm phase-42

### 8. Federal Contracting Social Graph

Interactive force-directed network visualization:
- 4 modes: company-centric, agency-centric, opportunity-centric, path finder
- Nodes: companies, agencies, offices, contracts, contracting officers
- Edges: awarded_to, subcontracts_to, teamed_with
- Up to 500 nodes at 60 FPS
- "Find a path" — show how you're connected to a target agency through teaming/sub relationships

**Source:** brainstorm phase-44

---

## Implementation Notes

- Features 1-5 are buildable entirely on existing data (awards, FPDS, entities, subawards)
- Feature 6 needs Congress.gov API integration
- Feature 7 combines multiple signals (some new, some existing)
- Feature 8 is a visualization challenge — data exists, presentation is the work
- Re-compete early warning (#1) and agency patterns (#2) together are probably the highest-value additions here
