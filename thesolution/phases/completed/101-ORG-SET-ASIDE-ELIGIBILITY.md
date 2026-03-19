# Phase 101: Organization Set-Aside Eligibility (from SAM.gov Entity Data)

**Status:** COMPLETE
**Priority:** High — affects qualification, pWin, recommendations, and target filtering
**Dependencies:** Phase 91 (Entity Linking) — COMPLETE

---

## Goal

Fix the existing SELF entity sync so that `organization_certification` is correctly populated from SAM.gov entity data. The scoring services (Qualification, pWin, Recommendations) already read from `organization_certification` — they just get bad data today. Fix the source, not the consumers.

Additionally: display set-aside eligibility read-only on the org profile, and fix the hardcoded qualification stub on the opportunity Overview tab.

---

## Root Cause

`PopulateFromSelfEntityAsync()` in `OrganizationEntityService.cs` (line 269-293) has two bugs:

### Bug 1: Wrong `CertificationType` values

Line 284 writes: `CertificationType = ec.SbaTypeDesc ?? ec.SbaTypeCode ?? "SBA"`

This produces values like `"SBA Certified 8(a) Program Participant"`. But the scoring services expect `"8(a)"`, `"WOSB"`, `"EDWOSB"`, etc. The qualification check never matches because the strings don't align.

### Bug 2: `entity_business_type` is completely ignored

The sync only copies `entity_sba_certification`. But WOSB/EDWOSB eligibility comes from **business type codes** in `entity_business_type` (8W, 8E, 8C, 8D). These are never synced to `organization_certification` at all.

**Result:** Even after linking a SELF entity and refreshing, the org has wrong/missing certs, and every downstream consumer (qualification, pWin, recommendations) produces incorrect results.

---

## Mapping: Entity Data → CertificationType Values

The scoring services use these `CertificationType` values (from `SetAsideToCertMap` in QualificationService, PWinService, RecommendedOpportunityService):

### From `entity_business_type`

| Entity `business_type_code` | Description | → `CertificationType` |
|------------------------------|-------------|----------------------|
| 8W | Woman Owned Small Business | `WOSB` |
| 8E | Economically Disadvantaged WOSB | `EDWOSB` |
| 8C | JV Women Owned Small Business | `WOSB` |
| 8D | JV Economically Disadvantaged WOSB | `EDWOSB` |
| QF | Service-Disabled Veteran-Owned | `SDVOSB` |
| A5 | Veteran-Owned Small Business | `VOSB` |

Note: 8E/8D entities are eligible for both EDWOSB and WOSB set-asides. The scoring services already handle this — `PWinService.SetAsideCertMap["WOSB"]` includes `["WOSB", "EDWOSB"]`.

### From `entity_sba_certification` (active only: `exit_date IS NULL OR exit_date > TODAY`)

| Entity `sba_type_code` | Description | → `CertificationType` |
|--------------------------|-------------|----------------------|
| A4 | 8(a) Program Participant | `8(a)` |
| A6 | 8(a) Joint Venture | `8(a)` |
| XX | HUBZone Certified | `HUBZone` |

### General rule

Any entity with any small-business-related business type or active SBA cert also gets `SDB` cert type. The scoring services map SBA/SBP set-aside codes to `"SDB"` (not "Small Business").

---

## Implementation Plan

### Task 1: Fix `PopulateFromSelfEntityAsync()` — the core fix

**File:** `api/src/FedProspector.Infrastructure/Services/OrganizationEntityService.cs`

**Change:** Replace lines 269-293 to sync certs from **all active linked entities** (SELF + JV_PARTNER + TEAMING), not just SELF. This matches how `GetAggregateNaicsAsync()` already unions NAICS from all linked entities.

1. Get all active linked UEIs for the org (same as `GetLinkedUeisAsync()`)
2. Query `entity_business_type` for all linked UEIs
3. Query `entity_sba_certification` for all linked UEIs (active certs only: `exit_date IS NULL OR exit_date > TODAY`)
4. Map both to `OrganizationCertification` records using the correct `CertificationType` values (see mapping table above)
5. Deduplicate across all entities (e.g., if SELF and JV partner both have WOSB, only one row)
6. Delete `source = 'SAM_ENTITY'` rows and insert the mapped ones

**Trigger:** This sync must run on ANY entity link or delink (SELF, JV_PARTNER, or TEAMING), not just SELF. Extract the cert-sync logic into its own method (e.g., `SyncEntityCertsAsync(orgId)`) called from `LinkEntityAsync`, `DeactivateLinkAsync`, and `RefreshFromSelfEntityAsync`.

**What this fixes immediately (no other code changes needed):**
- `QualificationService.CheckSetAsideMatch()` — will find matching certs
- `PWinService.ScoreSetAsideMatch()` — will score 100 instead of 0
- `RecommendedOpportunityService` — will include cert-restricted opportunities
- Dashboard recommendations — will show results
- All downstream consumers that read `organization_certification`

**For SBA certs with expiration dates:** Set `ExpirationDate` from `certification_exit_date` and `IsActive` based on whether exit date is null or in the future.

### Task 2: Fix Overview tab qualification stub

**File:** `ui/src/pages/opportunities/OpportunityDetailPage.tsx` (lines ~270-293)

The Overview tab has a hardcoded `QualificationChecklist` that always shows "Unknown" / "Requires organization profile". The real qualification check works on the Qualification & pWin tab.

**Fix:** Replace the stub with a live summary calling `GET /opportunities/{noticeId}/qualification` — show overall status chip (Qualified/Partially/Not Qualified) with pass/fail counts, with a link to the Qualification & pWin tab for full details. Or simply remove it since the dedicated tab exists.

### Task 3: UI — Read-only set-aside display on org profile

**Location:** Section within Entity Linking tab on OrganizationPage, or a new "Eligibility" tab.

**States:**

1. **No SELF entity linked:**
   - Message: "Link your SAM.gov entity to see your set-aside eligibility."
   - If manual certs exist from wizard, show them.

2. **SELF entity linked:**
   - Read-only list of cert types synced from entity, grouped by category
   - Show `last_loaded_at` timestamp for data freshness
   - Refresh button (calls existing `POST /org/entities/refresh-self`)

3. **SELF entity linked, no certs found:**
   - Message: "Your SAM.gov entity has no set-aside certifications on record."

**No new endpoint needed** — the existing `GET /org/certifications` already returns `organization_certification` data. After Task 1 fixes the sync, this endpoint returns the correct data. Just need a UI component that displays it as read-only when source is entity.

### Task 4: Setup wizard behavior when SELF entity exists

**Current:** Step 3 (Certifications) always shows manual checkboxes.

**Change:** If org already has a SELF entity linked, show read-only summary of synced certs instead of editable checkboxes. If no SELF entity, keep existing behavior unchanged.

### Task 5: Add `source` column to `organization_certification` (PREREQUISITE for Task 1)

Add a `source` column (`VARCHAR(20) NOT NULL DEFAULT 'MANUAL'`, values: `MANUAL`, `SAM_ENTITY`). Backfill all existing rows as `MANUAL`. This is **required** before Task 1 — without it, the sync cannot selectively delete entity-synced rows vs manual rows.

Also update `OrgCertificationDto` to include the `source` field so the UI can render differently.

Also update `SetCertificationsAsync` in `CompanyProfileService` to only delete/replace rows where `source = 'MANUAL'`, leaving `SAM_ENTITY` rows untouched. This prevents the `PUT /org/certifications` endpoint from wiping entity-synced certs.

---

## Bug Fix: Overview Tab Qualification Placeholder

**File:** `ui/src/pages/opportunities/OpportunityDetailPage.tsx` (lines ~270-293)

The Overview tab contains a **hardcoded stub** `QualificationChecklist` that always shows "Unknown" / "Requires organization profile" for all 6 items. It has a caption saying "Automated matching against your organization profile is coming soon." This was written before the real `QualificationService` existed.

The **real** qualification check already works on the Qualification & pWin tab (`QualificationPWinTab.tsx`), which calls `GET /opportunities/{noticeId}/qualification`.

**Fix:** Replace the stub with a live summary calling the same endpoint, or remove the section entirely since the dedicated tab exists.

---

## Known Degraded-Data Scenarios (All Fixed by Task 1)

| Location | Current Behavior | Root Cause | Fixed By |
|----------|-----------------|------------|----------|
| Overview tab Qualification Checklist | Shows "Requires organization profile" always | Hardcoded stub | Task 2 |
| Qualification tab — Set-Aside Match | "Org lacks required SDB certification" | Wrong cert types in `organization_certification` | Task 1 |
| pWin — Set-Aside Match factor (20%) | Scores 0 when cert missing | Same | Task 1 |
| Recommended Opps | Skips opps requiring certs | Same | Task 1 |
| Dashboard — Top Recommendations | "Link your SAM.gov entity" | Empty results from bad certs | Task 1 |

---

## DRY Note: Duplicated Mappings

The cert-to-set-aside mapping is duplicated in three C# services:
- `RecommendedOpportunityService` (lines 17-31)
- `QualificationService` (lines 17-31)
- `PWinService` (lines 18-32)

`etl_utils.get_tracked_set_asides()` (line 149) has a similar mapping but serves a different purpose — it controls what data the ETL pipeline loads. Out of scope.

Consolidating the C# duplicates into a shared `SetAsideMapping` class in `FedProspector.Core` is a nice cleanup but **not required** for correctness — Task 1 fixes the data, and the existing service mappings work fine once the data is right. Can be done as a follow-up refactor.

---

## Out of Scope

- **Dynamic `target_opportunities` view** — currently hardcodes set-aside list; making it org-specific is a separate effort
- **JV cert eligibility rules** — SBA has specific rules about which JV structures qualify for which set-asides (mentor-protege, size limits, etc.). We aggregate certs from all linked entities but don't enforce SBA JV approval rules. That's a future enhancement.
- **Cert expiration alerts** — notifying when SBA cert approaches exit date
- **ETL set-aside filtering** — `etl_utils.get_tracked_set_asides()` controls data ingestion, not display
- **Consolidating DRY mapping** — nice-to-have refactor, not blocking

---

## Risks & Considerations

| Risk | Mitigation |
|------|------------|
| Entity data staleness (monthly refresh) | Show `last_loaded_at` timestamp; refresh button triggers `refresh-self` |
| SBA cert expired but entity not yet updated | Check `certification_exit_date > TODAY` in sync logic |
| Orgs without SAM.gov registration | Fallback to manual wizard certs (unchanged behavior) |
| HUBZone code "XX" may not be correct | Verify from real entity data before implementing |
| SELF entity with zero certs wipes manual wizard certs | Task 5 (`source` column) makes sync only delete `SAM_ENTITY` rows, preserving `MANUAL` ones |
| Manual API edits could overwrite entity-synced certs | Task 4 makes wizard read-only; `source` column lets us protect entity rows from `PUT /org/certifications` |

---

## Testing Checklist

- [ ] Link SELF entity → org certs populated with correct `CertificationType` values
- [ ] Entity with business type 8W → org gets `WOSB` cert
- [ ] Entity with business type 8E → org gets `EDWOSB` cert
- [ ] Entity with SBA cert A4 (active) → org gets `8(a)` cert
- [ ] Entity with SBA cert A4 (expired) → org does NOT get `8(a)` cert
- [ ] Refresh SELF entity → org certs re-synced correctly
- [ ] Qualification check now shows "Pass" for set-aside when cert exists
- [ ] pWin set-aside factor scores 100 instead of 0
- [ ] Recommendations include cert-restricted opportunities
- [ ] Overview tab shows live qualification summary (not "Requires organization profile")
- [ ] Org profile shows read-only certs when SELF entity linked
- [ ] Setup wizard Step 3 is read-only when SELF entity linked
- [ ] Org without SELF entity → manual certs still work as before
- [ ] JV partner with 8(a) cert → org gets `8(a)` cert in addition to SELF certs
- [ ] Delink JV partner → re-sync removes that partner's certs, keeps SELF + other partners
- [ ] Link new JV partner → re-sync adds that partner's certs

---

## Task Summary

| # | Task | Layer | Complexity | Depends On |
|---|------|-------|------------|------------|
| 1 | Add `source` column to `organization_certification` (`MANUAL` or `SAM_ENTITY`), backfill existing as `MANUAL`, update DTO, guard `SetCertificationsAsync` to only touch `MANUAL` rows | Backend | Low | — |
| 2 | Fix cert sync: extract `SyncEntityCertsAsync(orgId)` — maps business types + SBA certs from ALL linked entities to correct `CertificationType` values, only deletes `SAM_ENTITY` rows | Backend | Medium | Task 1 |
| 3 | Trigger cert sync on any entity link/delink (SELF, JV, TEAMING). On SELF delink, also clear `UeiSam` and entity-populated profile fields. | Backend | Low | Task 2 |
| 4 | One-time migration: re-sync all orgs with existing linked entities | Backend | Low | Task 2 |
| 5 | Fix Overview tab: replace hardcoded qualification stub with live summary or remove | Frontend | Low | — |
| 6 | Read-only set-aside eligibility display on org profile | Frontend | Medium | Task 2 |
| 7 | Setup wizard Step 3 read-only when SELF entity linked | Frontend | Low | Task 2 |
| 8 | Update `CertificationCount` in entity link DTO to include business-type-derived certs, not just SBA certs | Backend | Low | — |
