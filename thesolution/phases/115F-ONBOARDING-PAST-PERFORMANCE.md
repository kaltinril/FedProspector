# Phase 115F: Onboarding & Past Performance Portfolio (Brainstorm Gap Analysis)

**Status:** PLANNED
**Priority:** TBD
**Source:** C:\git\brainstorm\docs\phases\ (phases 17-19)
**Dependencies:** Entity data (loaded), FPDS contract data (loaded), USASpending data (loaded), Org profile + wizard (Phase 70+), `ref_sba_size_standard` (loaded). New schema needed: `organization_psc` table for PSC auto-import.

---

## Summary

We have basic org setup (NAICS, certs, entity linking). The brainstorm designed a much richer onboarding flow and a full past performance portfolio management system.

---

## Overlap with Existing Features

| Idea | Status | What Exists |
|------|--------|-------------|
| UEI Auto-Import | **PARTIAL** | `organization.uei_sam` links org to SAM.gov. `organization_entity` table links to multiple UEIs (SELF, JV, TEAMING). `CompanySetupWizard` has 5 steps (Basics, NAICS, Certifications, Past Performance, Review). But import is manual — no auto-populate from SAM.gov entity data. |
| Profile Completeness Score | **PARTIAL** | `organization.profile_completed` Y/N flag exists. Wizard guides through steps. Missing: percentage score, specific recommendations. Note: no `organization_psc` table exists yet — PSC-based recommendations would need that table first. |
| Certification Lifecycle Alerts | **PARTIAL** | `organization_certification.expiration_date` stored. `entity_sba_certification` loaded. `NotificationService` exists. Missing: background job checking expirations, no 90/60/30-day alert generation. |
| SBA Size Standard Monitoring | **PARTIAL** | `ref_sba_size_standard` table loaded. `organization_naics.size_standard_met` Y/N flag. Missing: actual comparison of org revenue against NAICS threshold, no alerts at 80% of limit. |
| Enrichable Past Performance | **EXISTS** | Full CRUD in `organization_past_performance` (contract_number, agency_name, description, naics_code, contract_value, period_start/end) via `PastPerformanceStep.tsx`. |
| Relevance Matching | **NEW** | No matching of past performance records against incoming opportunities. |
| Portfolio Gap Analysis | **NEW** | No analysis of NAICS/agency coverage gaps vs market opportunity volume. |
| Citation Exports | **NEW** | No formatted export (SF 330, Section L/M narrative). |

---

## Onboarding Enhancements

### 1. UEI-Based Profile Auto-Import

Enter your UEI, and the system auto-populates:
- Company name, address, business type from SAM.gov Entity API
- NAICS codes from `entity_naics` (PSC codes from `entity_psc` exist but no `organization_psc` table to import into — would need schema addition)
- Certifications from `entity_sba_certification`
- Past performance from FPDS contracts (`fpds_contract.vendor_uei`) and/or USASpending awards (`usaspending_award.recipient_uei`)
- Auto-generated saved searches from imported NAICS codes (new logic — `saved_search` table exists but no auto-creation path today)

Fallback paths: CAGE code lookup, name search, manual entry.

**How it differs from our org setup:** We have entity linking, but the user still manually enters NAICS codes, certs, etc. This would auto-populate from SAM.gov entity tables. Requires: API endpoint to read entity data by UEI and map to org tables, plus `organization_psc` table creation for PSC import.

**Value:** "UEI to first matches in under 10 minutes" — the brainstorm set this as a target.

**Source:** brainstorm phase-17

### 2. Profile Completeness Score

Visual indicator showing how complete the org profile is:
- Percentage bar with specific recommendations ("Add PSC codes to improve matching")
- Guides users to fill in the fields that will improve their results most

**Source:** brainstorm phase-17

### 3. Certification Lifecycle Tracking

Beyond just listing certs:
- Alerts at 90/60/30 days before certification expiration
- 8(a) graduation date calculation (entry date + 9 years)
- Renewal reminders
- SAM.gov change detection — alert when government data diverges from stored profile

**Source:** brainstorm phase-18

### 4. SBA Size Standard Monitoring

Track revenue against NAICS size standards:
- Warn at 80% of threshold ("You're at $22M against a $28M size standard for NAICS 541511")
- Critical for maintaining small business eligibility

**Source:** brainstorm phase-18

---

## Past Performance Portfolio

### 5. User-Enrichable Past Performance Records

We have FPDS/USASpending award data in the database, but it is not auto-imported into `organization_past_performance` — users enter records manually via the wizard. The brainstorm adds user-editable fields beyond what we store today:
- Narrative descriptions of what was delivered
- Key personnel involved
- Specific deliverables and outcomes
- Customer satisfaction notes
- Teaming partners on the contract
- Internal rating
- Relevance tags (custom labels)

**Source:** brainstorm phase-19

### 6. Past Performance Relevance Matching

For any opportunity, auto-rank your past performance entries by relevance:
- NAICS code match
- Agency/office match
- Keyword similarity
- Dollar value similarity
- Recency

"Here are your 5 most relevant past performances for this opportunity" — instant capture meeting prep.

**Source:** brainstorm phase-19

### 7. Portfolio Gap Analysis

Show NAICS codes and agencies where you have:
- High opportunity volume but NO past performance → "You could win more if you built experience here"
- Past performance but LOW opportunity volume → "Your experience here isn't in demand right now"

**Source:** brainstorm phase-19

### 8. Formatted Citation Exports

Generate past performance citations in standard formats:
- SF 330 format (for A&E contracts)
- Section L/M narrative format
- Configurable templates
- One-click PDF/Word export

**Value:** Every proposal requires past performance citations. Auto-formatting saves hours per proposal.

**Source:** brainstorm phase-19

---

## Implementation Notes

- UEI auto-import (#1) would dramatically improve onboarding — we already have all the data, just need to wire it up
- Certification lifecycle (#3) and SBA size monitoring (#4) are high-value for our WOSB/8(a) target market
- Past performance relevance matching (#6) pairs well with the OQS score (Phase 115A) — together they answer "is this a good fit AND can I prove it?"
- Citation exports (#8) are a strong differentiator — competitors don't offer this

## Missing Ideas / Gaps Not Covered

- **SAM.gov Registration Expiration Monitoring**: Entity registrations expire annually. `entity.registration_expiration_date` exists — alerting on upcoming SAM.gov expiration is low-hanging fruit and critical for eligibility.
- **Subcontract History**: `sam_subaward` table has `sub_uei` data. Past performance could include subcontract work, not just prime contracts.
- **organization_psc table**: Multiple features here assume org-level PSC storage, but no such table exists today. Should be created before PSC-related features.
- **Competitor Past Performance Comparison**: We have incumbent/competitor views (`v_competitor_analysis`, `v_incumbent_profile`). Could show "your past performance vs incumbent's" for a given recompete.
