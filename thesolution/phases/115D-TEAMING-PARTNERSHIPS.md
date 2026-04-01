# Phase 115D: Teaming & Partnership Intelligence (Brainstorm Gap Analysis)

**Status:** PLANNED
**Priority:** TBD
**Source:** C:\git\brainstorm\docs\phases\ (phases 45-47)
**Dependencies:** Subaward data (loaded), Entity data (loaded), Exclusions data (loaded), FPDS data (loaded), USASpending data (loaded), Attachment intel (Phase 121+)

---

## Summary

We have a basic teaming search page. The brainstorm designed a full teaming intelligence suite with gap analysis, risk screening, and mentor-protege matching.

---

## Overlap with Existing Features

| Idea | Status | What Exists |
|------|--------|-------------|
| Gap-Based Partner Matchmaker | **NEW** | `SubawardService.GetTeamingPartnersAsync()` searches `sam_subaward` by prime UEI, sub UEI, NAICS, and minimum subaward count. `TeamingPartnerPage.tsx` provides basic search/filter UI. Missing: gap detection, capability matching, compatibility scoring. |
| Toxic Partner Screening | **PARTIAL** | `sam_exclusion` table loaded with debarred/suspended entities. Exclusion status checked in incumbent analysis (`ExpiringContractService`). `fpds_contract.reason_for_modification` has termination-for-cause data. `usaspending_award` has spending data per vendor. Missing: analysis/scoring layer, historical exclusion archive, protest history (needs GAO data), customer concentration analysis, continuous monitoring. |
| Mentor-Protege Matching | **NEW** | Entity certifications loaded (`entity_sba_certification`). Organization certifications tracked. No matching algorithm or mentor-candidate scoring. |
| Interest Flag Workflow | **NEW** | Requires cross-tenant interaction — architecturally novel for our current org-isolation model. Would need new `partner_interest` table and cross-org notification logic. |

---

## Features We Don't Have

### 1. Gap-Based Teaming Partner Matchmaker

Instead of just searching for partners, detect what you're missing and find partners who fill gaps:
- 6-dimension gap detection: NAICS, PSC, certifications, clearance (from attachment intel), past performance (from FPDS/subaward history), geography (from entity_address)
- For a specific opportunity: "You're missing NAICS 541511 experience and a Secret clearance — here are 12 firms that have both and have subbed on similar work"
- Ranked by Partner Compatibility Score (see Phase 115A)
- Score breakdown showing why each partner is a good fit

**Source:** brainstorm phase-45

### 2. Toxic Partner / Due Diligence Screening

Before you team with someone, check 8 risk factors:
1. Current exclusion status (`sam_exclusion` — have this data)
2. Exclusion history (past debarments, even if reinstated — `sam_exclusion.termination_date` tracks this)
3. Terminations for cause (`fpds_contract.reason_for_modification` — have raw data, need analysis)
4. Protest history (would need GAO data — new source)
5. Spending trajectory (`usaspending_award` by `recipient_uei` — have raw data, need trend analysis)
6. Customer concentration (`fpds_contract`/`usaspending_award` by agency — have raw data, need analysis)
7. Certification status (`entity_sba_certification.certification_exit_date` — have this data)
8. Performance signals (any negative indicators — composite of items 1-7)

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
- Feature 2 (toxic partner) has 6 of 8 risk factors covered by data we already load — only GAO protest data requires a new source
- Clearance gap detection (feature 1) depends on attachment intel extraction (Phase 121+), which populates `attachment_intel.clearance_required/level`; `opportunity.security_clearance_required` is reserved/unpopulated from the API
- The interest flag workflow (#4) requires cross-tenant interaction — architecturally different from everything else we have
- Mentor-Protege (#3) is a niche feature but high-value for our target market (WOSB, 8(a))
