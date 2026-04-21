# Phase 133: Linked Entity Aggregation Fixes + Sister Subsidiary

**Status:** PLANNED
**Priority:** Medium — bug fixes for three linked-entity views and one broken page, plus one new relationship type.
**Dependencies:** Phase 115D (Teaming & Partnerships — `organization_entity`), Phase 115F (Onboarding & Past Performance — the three views below).

---

## Context

`organization_entity` links an org to one or more SAM UEIs (parent, JV partner, teaming partner, etc.) but three of the onboarding/size-standard views built in Phase 115F don't actually aggregate data across those linked entities — they only look at the org's own row. We also need one additional relationship type (`SISTER_SUBSIDIARY`) to model common-parent subsidiaries. A related page (Mentor-Protégé) errors on load.

Broader mentor-protégé modeling (MPA, tribal exemption, per-link aggregation overrides) is deferred — see **Deferred** below.

---

## Problem

1. **Portfolio Gap Analysis** (`v_portfolio_gap_analysis`) reports "No Experience" for NAICS codes where a linked entity has awards, because the view only reads the org's own `organization_naics` and `organization_past_performance`.
2. **Certification Expiration Alert** (`v_certification_expiration_alert`) only joins `entity_sba_certification` via the org's own `uei_sam`, missing certs on linked UEIs.
3. **SBA Size Standard Monitor** (`v_sba_size_standard_monitor`) only joins `organization_naics` on the org, missing NAICS registered on linked entities.
4. **Entity Linking** picker has no "Sister company" option — a common shape for subsidiaries sharing a parent.
5. **Mentor-Protégé page** (`/teaming/mentor-protege`) fails with "Failed to load mentor-protege pairs" on load.

---

## Scope

### Task 1 — Add `SISTER_SUBSIDIARY` relationship type

- **File:** `api/src/FedProspector.Infrastructure/Services/OrganizationEntityService.cs` — add `"SISTER_SUBSIDIARY"` to the `ValidRelationships` HashSet (currently `SELF`, `JV_PARTNER`, `TEAMING`).
- **File:** `ui/src/pages/organization/OrgEntitiesTab.tsx` — add `{ value: 'SISTER_SUBSIDIARY', label: 'Sister subsidiary' }` to the relationship options list and a matching branch in the label/icon switch near lines 155–159.
- **No DB migration needed** — `organization_entity.relationship` is a free-form `VARCHAR` with no CHECK constraint.

### Task 2 — Fix `v_portfolio_gap_analysis` to aggregate linked entities

- **File:** `fed_prospector/db/schema/migrations/115f_onboarding_past_performance.sql` (view at ~line 263).
- **Change:** NAICS source unions `organization_naics` with `entity_naics_codes` joined through `organization_entity` (where `is_active = 'Y'`). Past-performance counts union the org's `organization_past_performance` rows with awards from linked UEIs (via `usaspending_award` or equivalent, grouped by NAICS). All active linked relationships count; per-link overrides are deferred.
- Apply to live DB in same commit (CLAUDE.md rule 9).

### Task 3 — Fix `v_certification_expiration_alert` to include linked entities' certs

- **File:** same migration file, view at ~lines 101–138.
- **Change:** the SAM.gov section currently joins `entity_sba_certification esc INNER JOIN organization o ON o.uei_sam = esc.uei_sam`. Replace with a UNION (or IN-list) that also includes any `uei_sam` from `organization_entity` where `organization_id = o.organization_id` and `is_active = 'Y'`.
- Apply to live DB.

### Task 4 — Fix `v_sba_size_standard_monitor` to use aggregated NAICS

- **File:** same migration file, view at ~lines 148–173.
- **Change:** source NAICS from the same aggregated set used in Task 2 (org's own `organization_naics` UNION linked entities' `entity_naics_codes` via active `organization_entity` rows), not just `organization_naics` on the org.
- Apply to live DB.

### Task 5 — Diagnose and fix Mentor-Protégé page error

- **UI:** `ui/src/pages/teaming/MentorProtegePage.tsx` (shows "Failed to load mentor-protege pairs").
- **API:** `TeamingController` → `ITeamingService.GetMentorProtegeCandidatesAsync()` → `v_mentor_protege_candidate` (defined in `fed_prospector/db/schema/migrations/115d_teaming_partnerships.sql`).
- **Steps:** (1) call `GET /api/v1/teaming/mentor-protege` and capture response; (2) run `SELECT * FROM v_mentor_protege_candidate LIMIT 10` against live DB; (3) if the view errors, fix the view; (4) if the endpoint returns empty successfully but the UI renders an error, fix the frontend to render a clean empty state instead.

---

## Acceptance Criteria

1. User can link a UEI as `SISTER_SUBSIDIARY` via the Entity Linking picker and it persists.
2. `v_portfolio_gap_analysis` returns non-zero `past_performance_count` for a NAICS code where a linked entity has awards, even when the org's own `organization_past_performance` is empty for that NAICS.
3. `v_certification_expiration_alert` surfaces SBA certs attached to linked UEIs, not just the org's own `uei_sam`.
4. `v_sba_size_standard_monitor` includes NAICS registered on linked entities.
5. Mentor-Protégé page loads without error; empty result set renders a clean empty state.
6. All three view changes applied to live DB in the same commit as the DDL edit.

---

## Known Issues / Deferred

- **`MENTOR` / `PROTEGE` relationship types** — requires MPA data model, `mpa_effective_date`, and aggregation rules that distinguish past-perf inheritance (§ 125.9(d)) from size-standard eligibility. Not in scope here.
- **Tribal entity attribute + auto-suggest sisters** — a `tribal_ownership_type` attribute on entities plus a "find sister companies under the same tribal parent" suggestion flow.
- **Per-link aggregation override UI** — flipping the default "this link counts for past-perf / NAICS / size / certs" per-link, with a reason note. The fixes above use a single default (all active links count for all view purposes).
- **Grouped relationship picker with plain-English tooltips** — regrouping the dropdown into "Under common ownership", "Mentor-Protégé", "Partnership" sections with one-line tooltips per option.
- **Proposal-time disclosure badges** — chips on past-perf rows that surface which linked entity the row came from.
