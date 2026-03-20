# Phase 104: JV Past Performance & Entity Award Loading

**Status:** COMPLETE
**Priority:** High — directly affects qualification pass/fail and pWin scoring
**Dependencies:** Phase 91 (Entity Linking), Phase 101 (Cert Sync)

---

## Goal

Make past performance checks and pWin scoring include award history from all linked entities (SELF + JV partners). Also solve the JV member discovery problem and enable entity-specific award loading.

---

## Current State

### What works today

- `QualificationService.CheckPastPerformanceAsync()` checks `organization_past_performance` (manual entries) and `fpds_contract` (loaded FPDS awards) filtered by `vendor_uei = org.UeiSam`
- `PWinService.ScoreNaicsExperienceAsync()` uses `GetLinkedUeisAsync()` to check awards across all linked entity UEIs — **already aggregates for pWin**
- Awards can be loaded by UEI via `python main.py load awards --awardee-uei <UEI>`
- `fpds_contract.vendor_uei` links awards to entities
- `usaspending_award.recipient_uei` links USASpending awards to entities
- `usaspending_award.recipient_parent_uei` tracks parent company relationships

### What's broken / missing

1. **QualificationService only checks SELF UEI** — does not use `GetLinkedUeisAsync()` like PWinService does. A JV partner's awards don't help you pass the qualification check.

2. **Awards are not loaded for linked entities** — the system only loads awards by NAICS and set-aside codes. There's no automatic loading of awards for SELF/JV/TEAMING entity UEIs. If a JV partner's awards haven't been loaded by coincidence (matching NAICS), they won't appear.

3. **No JV member discovery** — SAM.gov Entity API does **not** return parent/child or JV member relationships. You can identify that an entity IS a JV (via business type codes 8C, 8D), but you can't programmatically find who the JV's member companies are. The only link is the entity structure code — which doesn't help.

4. **No entity-triggered award loading** — when you link an entity, there's no automatic process to ensure that entity's awards are in the database.

---

## JV Member Discovery Problem

A JV is two (or more) companies that form a new third entity. In SAM.gov:
- The JV entity has its own UEI (e.g., `AGS MSONE JV LLC`)
- The JV entity may have business type codes 8C (JV WOSB) or 8D (JV EDWOSB)
- The JV entity's registration does NOT list its member companies' UEIs

**How to find JV members:**

### Option A: USASpending parent_uei field
`usaspending_award.recipient_parent_uei` tracks the parent company for award recipients. If the JV won awards, the parent UEI might point to one of the member companies. But this is inconsistent — JVs often report themselves as the parent.

### Option B: Manual entry (recommended for now)
When linking a JV entity, the user also specifies the other member company's UEI. This could be a field on the entity link: "Other JV member UEI." The user knows who their JV partner is — they formed the JV.

**Proposed data model addition:**
```sql
ALTER TABLE organization_entity ADD COLUMN partner_uei VARCHAR(12) NULL;
```

When `relationship = 'JV_PARTNER'`, `partner_uei` stores the UEI of the other company in the JV (not the JV entity itself, but the other member). This gives us:
- `uei_sam` = the JV entity's UEI (already stored)
- `partner_uei` = the other member company's UEI (new field)

With SELF UEI + JV UEI + partner UEI, we have all three entities involved in a JV arrangement.

### Option C: Entity relationship table (future)
A more general `entity_relationship` table tracking parent/child/JV/subsidiary links between entities. Overkill for now.

---

## Award Loading Strategy

### Current: Awards loaded by NAICS/set-aside
Awards are loaded via `python main.py load awards --naics 541511 --set-aside WOSB`. This catches awards in your NAICS codes but misses:
- Awards your JV partner won in different NAICS codes
- Awards from the JV entity itself
- Awards from the partner's other entity

### Proposed: Entity-triggered award loading

When an entity is linked to an org, automatically queue loading of that entity's awards:

1. **On entity link:** Check if `fpds_contract` has recent awards for that UEI. If not (or stale), trigger award loading.
2. **CLI command:** `python main.py load awards --entity-ueis <UEI1>,<UEI2>,<UEI3>` — loads awards for specific UEIs.
3. **Batch on link:** When linking a JV entity, load awards for: JV UEI + partner UEI (if provided).

### SAM Awards API supports this
`SAMAwardsClient.search_by_awardee(uei)` already exists — just needs to be called when entities are linked.

---

## Implementation Plan

### Task 1: Fix QualificationService to use linked UEIs

**File:** `api/src/FedProspector.Infrastructure/Services/QualificationService.cs`

`CheckPastPerformanceAsync()` currently only checks `org.UeiSam`. Change to use `GetLinkedUeisAsync()` (same pattern as `PWinService.ScoreNaicsExperienceAsync()`).

```csharp
// Current (line ~250):
.Where(c => c.VendorUei == org.UeiSam && c.NaicsCode == naics)

// Fixed:
var linkedUeis = await _orgEntityService.GetLinkedUeisAsync(orgId);
if (!string.IsNullOrEmpty(org.UeiSam) && !linkedUeis.Contains(org.UeiSam))
    linkedUeis.Add(org.UeiSam);
// ...
.Where(c => linkedUeis.Contains(c.VendorUei) && c.NaicsCode == naics)
```

This immediately makes qualification checks pass when JV partner awards exist in `fpds_contract`.

### Task 2: Add `partner_uei` to `organization_entity`

**Schema:** Add `partner_uei VARCHAR(12) NULL` to `organization_entity` table in DDL.
**C# Model:** Add `PartnerUei` property to `OrganizationEntity`.
**DTO:** Add `partnerUei` to `OrganizationEntityDto` and `LinkEntityRequest`.
**UI:** When linking with relationship = JV_PARTNER, show an optional "Other JV member UEI" field.

### Task 3: Include partner UEIs in linked UEI aggregation

**File:** `OrganizationEntityService.GetLinkedUeisAsync()`

Currently returns `uei_sam` from active links. Extend to also include `partner_uei` values (when not null). This means the aggregate UEI list includes: SELF UEI + each JV entity UEI + each JV's partner company UEI.

This flows through to everywhere that calls `GetLinkedUeisAsync()`: pWin scoring, NAICS aggregation, and now qualification checks.

### Task 4: Entity-triggered award loading (CLI)

Add a CLI command:
```bash
python main.py load awards --for-org
```

This command:
1. Queries `organization_entity` for all active linked UEIs (+ partner UEIs)
2. For each UEI, checks if `fpds_contract` has recent awards (last 5 years)
3. If not, calls `SAMAwardsClient.search_by_awardee(uei)` to load them
4. Reports: "Loaded X awards for Y entities"

Also add `--awardee-uei` support for ad-hoc loading of a specific entity's awards (already exists in the API client, just wire up the CLI).

### Task 5: Auto-load awards on entity link (optional)

When `LinkEntityAsync` fires and an entity is linked, queue a background job or log a `data_load_request` to load awards for that entity's UEI (and partner UEI if JV). The actual loading happens via the ETL pipeline, not inline in the API request.

This is optional — the CLI command from Task 4 can be run manually or on a schedule.

### Task 6: UI — Show award source in past performance

On the Qualification tab, when past performance shows pass/fail, indicate which entity the awards came from:
- "3 contracts found via MSONE LLC (SELF)"
- "2 contracts found via AGS MSONE JV LLC (JV Partner)"

This helps the user understand why they pass or fail.

---

## Out of Scope

- Automated JV member discovery from SAM.gov (not possible via API)
- Loading USASpending awards by entity (only FPDS for now — USASpending is slower and less granular)
- Entity relationship graph / visualization
- Subaward data aggregation from JV partners

---

## Risks & Considerations

| Risk | Mitigation |
|------|------------|
| SAM Awards API rate limits (10/day free tier) | Use key 2 (1000/day) for entity award loading; batch efficiently |
| `partner_uei` may not always be known | Make it optional; user can add later; system works without it |
| Large result sets for active entities | Limit to last 5 fiscal years; use date_from parameter |
| QualificationService now passes more easily | Correct behavior — JV past performance should count |
| JV entity might have no awards itself | The value is in loading the partner company's awards too |

---

## Testing Checklist

- [x] QualificationService uses all linked UEIs for past performance check
- [x] JV partner's awards cause past performance to pass
- [x] `partner_uei` field stored and returned in entity link DTO
- [x] UI shows "Other JV member UEI" field when linking JV
- [x] `GetLinkedUeisAsync` returns SELF + JV + partner UEIs
- [x] CLI `load awards --for-org` loads awards for all linked UEIs
- [x] Award source entity shown on qualification tab

---

## Task Summary

| # | Task | Layer | Complexity | Depends On |
|---|------|-------|------------|------------|
| 1 | Fix QualificationService to use linked UEIs for past performance | Backend | Low | — |
| 2 | Add `partner_uei` to `organization_entity` (schema, model, DTO, UI) | Full stack | Medium | — |
| 3 | Include partner UEIs in `GetLinkedUeisAsync()` aggregation | Backend | Low | Task 2 |
| 4 | CLI command: `load awards --for-org` — load awards for all linked entity UEIs | Python | Medium | — |
| 5 | (Optional) Auto-queue award loading on entity link | Backend + Python | Medium | Task 4 |
| 6 | UI: Show award source entity on qualification/pWin tabs | Frontend | Low | Task 1 |
