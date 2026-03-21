# Phase 115D: Teaming & Partnership Intelligence (Brainstorm Gap Analysis)

**Status:** IDEA — from brainstorm analysis, not yet prioritized
**Priority:** TBD
**Source:** C:\git\brainstorm\docs\phases\ (phases 45-47)
**Dependencies:** Subaward data (loaded), Entity data (loaded), Exclusions data (loaded)

---

## Summary

We have a basic teaming search page. The brainstorm designed a full teaming intelligence suite with gap analysis, risk screening, and mentor-protege matching.

---

## Overlap with Existing Features

| Idea | Status | What Exists |
|------|--------|-------------|
| Gap-Based Partner Matchmaker | **NEW** | `SubawardService.GetTeamingPartnersAsync()` searches `sam_subaward` by prime UEI, sub UEI, NAICS, and minimum subaward count. `TeamingPartnerPage.tsx` provides basic search/filter UI. Missing: gap detection, capability matching, compatibility scoring. |
| Toxic Partner Screening | **PARTIAL** | `sam_exclusion` table loaded with debarred/suspended entities. Exclusion status checked in incumbent analysis (`ExpiringContractService`). Missing: historical exclusion archive, FPDS termination-for-cause analysis, protest history (needs GAO data), spending trajectory, customer concentration, continuous monitoring. |
| Mentor-Protege Matching | **NEW** | Entity certifications loaded (`entity_sba_certification`). Organization certifications tracked. No matching algorithm or mentor-candidate scoring. |
| Interest Flag Workflow | **NEW** | Requires cross-tenant interaction — architecturally novel for our current org-isolation model. Would need new `partner_interest` table and cross-org notification logic. |

---

## Features We Don't Have

### 1. Gap-Based Teaming Partner Matchmaker

Instead of just searching for partners, detect what you're missing and find partners who fill gaps:
- 6-dimension gap detection: NAICS, PSC, certifications, clearance, past performance, geography
- For a specific opportunity: "You're missing NAICS 541511 experience and a Secret clearance — here are 12 firms that have both and have subbed on similar work"
- Ranked by Partner Compatibility Score (see Phase 115A)
- Score breakdown showing why each partner is a good fit

**Source:** brainstorm phase-45

### 2. Toxic Partner / Due Diligence Screening

Before you team with someone, check 8 risk factors:
1. Current exclusion status (we already have this data)
2. Exclusion history (past debarments, even if reinstated)
3. Terminations for cause (from FPDS data)
4. Protest history (would need GAO data — new source)
5. Spending trajectory (declining revenue = financial risk)
6. Customer concentration (>60% from one agency = risk)
7. Certification status (expiring soon?)
8. Performance signals (any negative indicators)

Output: traffic light indicator (green/yellow/red) + one-page PDF due diligence report.
Continuous monitoring: weekly re-checks of all teaming partners with alerts on changes.

**Source:** brainstorm phase-46

### 3. Mentor-Protege Opportunity Identifier

Match eligible 8(a)/WOSB/HUBZone/SDVOSB firms with potential mentor firms:
- Based on complementary capabilities
- Existing prime-sub relationships (from subaward data)
- Shared agency experience
- Size standard compatibility

**Value:** Helps small businesses find mentors proactively, and helps larger firms find protege candidates.

**Source:** brainstorm phase-47

### 4. Interest Flag Workflow

When you find a potential teaming partner, express interest:
- "Flag interest" button on partner profiles
- If both parties flag each other, notify both (like a matching system)
- Requires multi-tenant awareness (can't see other orgs' flags, only mutual matches)

**Source:** brainstorm phase-45

---

## New Data Sources Potentially Needed

| Source | Purpose | Notes |
|--------|---------|-------|
| GAO Bid Protest Decisions | Protest history for due diligence | Web scraping needed |

---

## Implementation Notes

- Features 1 and 2 are high-value and mostly buildable on existing data
- The interest flag workflow (#4) requires cross-tenant interaction — architecturally different from everything else we have
- Mentor-Protege (#3) is a niche feature but high-value for our target market (WOSB, 8(a))
