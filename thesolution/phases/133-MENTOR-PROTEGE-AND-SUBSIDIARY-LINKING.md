# Phase 133: Linked Entity Aggregation Fixes + Sister Subsidiary

**Status:** PLANNED
**Priority:** Medium — bug fixes for three linked-entity views and one broken page, plus one new relationship type.
**Dependencies:** Phase 115D (Teaming & Partnerships — `organization_entity`), Phase 115F (Onboarding & Past Performance — the three views below). **Task 6 (affiliation size roll-up) additionally depends on Phase 129 Task 3** — the size-eligibility engine (`CheckSizeEligibility`) it extends.

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

### Task 6 — SBA Affiliation Size Roll-Up (13 CFR 121.103)

> **Why this lives here:** Phase 129's size-eligibility engine (`CheckSizeEligibilityAsync` /
> `CheckSizeEligibility(int orgId, string naicsCode)` in `CompanyProfileService`) determines whether
> an org is "small" using **only that single org's** `organization.annual_revenue` and
> `organization.employee_count`. Under **13 CFR 121.103**, a firm's size must **include the receipts
> and employees of its affiliates** (parent, sister subsidiaries, and certain joint-venture /
> mentor-protégé relationships). The current number can therefore be **too favorable** (understated
> size) for any org that has affiliates — a False Claims Act / decertification risk identical to the
> "outsized" problem Phase 129 Task 4 already warns about. Phase 129 explicitly lists "Affiliate
> analysis" as **out of scope** (it owns single-org math). This phase is where affiliation roll-up
> belongs because it **establishes the linked-entity relationships the roll-up aggregates over**
> (`organization_entity` + the new `SISTER_SUBSIDIARY` type from Task 1, plus the JV / common-parent
> shapes already modeled). Implement this task **after Phase 129 Task 3 ships** and **after Tasks 1–4
> of this phase** are in place.

**Description.** Add an affiliation-aware size determination that aggregates the receipts/headcount of
an org's affiliates into the size comparison, and feed the aggregated totals into the existing
eligibility engine so the "small / other-than-small" verdict reflects the **combined** entity, not the
standalone org.

**What counts as an affiliate (for this task's default rule).** Aggregate over all `organization_entity`
rows for the org where `is_active = 'Y'` and `relationship` is one of the affiliation-bearing types:
`SELF` (the org's own SAM UEI), `SISTER_SUBSIDIARY` (common-parent subsidiaries, Task 1), `JV_PARTNER`,
and any parent relationship represented in `organization_entity`. `TEAMING` is a **non-affiliate**
relationship by default (teaming alone does not create affiliation under 121.103) and must be
**excluded** from the roll-up. Mentor-protégé pairs that qualify for the SBA exclusion from affiliation
(13 CFR 125.9(b)(3)) are **deferred** — see Known Issues.

**Where affiliate receipts/headcount come from.** For each linked UEI, source annual receipts and
employee count from the SAM.gov entity data already loaded for that UEI (the `entity_*` tables
populated by the entity loader; same UEIs surfaced in Tasks 2–4). If a linked UEI has no
receipts/headcount on file, count it as a **gap** (do not silently treat missing affiliate data as
zero — that re-introduces the understatement bug). Surface the gap in the result so the user knows the
roll-up is incomplete.

**Aggregation math (per 121.103):**
- **Revenue-based standards (`size_type = 'M'`)** — sum the org's `annual_revenue` plus every included
  affiliate's average annual receipts; compare the **combined** receipts against the NAICS threshold.
- **Employee-based standards (`size_type = 'E'`)** — sum the org's `employee_count` plus every included
  affiliate's average employee count; compare the **combined** headcount against the threshold.
- Affiliation is determined **as a whole** (the combined enterprise is small or it is not); it is not
  pro-rated by ownership percentage in this default rule. Ownership-percentage / per-link override
  refinement is deferred (see Known Issues and the Task-spanning "Per-link aggregation override UI"
  deferred item).

**Service surface.** Extend the Phase 129 eligibility engine rather than forking it:
- Add an affiliation-aware path that returns the standalone result **and** the rolled-up result, e.g.
  `CheckSizeEligibilityWithAffiliatesAsync(int orgId, string naicsCode)` returning a result that
  includes: `standaloneEligible`, `affiliatedEligible`, `combinedRevenue` / `combinedEmployees`,
  `threshold`, `sizeType`, `affiliateCount`, `includedAffiliates[]` (uei + relationship + contributed
  amount), `missingAffiliateData[]` (uei list with no receipts/headcount), and a
  `flippedToOtherThanSmall` boolean (true when standalone says small but the roll-up says
  other-than-small — the dangerous case).
- The standalone `CheckSizeEligibility` from Phase 129 stays intact for callers that want the org-only
  number; the affiliation path is additive.

**View / UI wiring.** `v_sba_size_standard_monitor` (fixed in Task 4 to aggregate linked NAICS) should
also reflect the affiliated size verdict where it reports eligibility, so the monitor and any
"approaching outsized" alert use the combined number. Where the UI shows the size verdict (NAICS step /
size monitor), display **both** the standalone and affiliated determinations when they differ, with a
clear callout when `flippedToOtherThanSmall` is true.

- **Files (anticipated):**
  - `api/src/FedProspector.Infrastructure/Services/CompanyProfileService.cs` — affiliation-aware
    eligibility method (or a dedicated `AffiliationSizeService`).
  - `api/src/FedProspector.Core/DTOs/` — new affiliated-eligibility result DTO.
  - `fed_prospector/db/schema/migrations/115f_onboarding_past_performance.sql` —
    `v_sba_size_standard_monitor` adjustment if the verdict is computed in the view (apply to live DB
    in the same commit, CLAUDE.md rule 9).
  - UI: the NAICS / size-monitor surfaces that render the eligibility verdict.

---

## Acceptance Criteria

1. User can link a UEI as `SISTER_SUBSIDIARY` via the Entity Linking picker and it persists.
2. `v_portfolio_gap_analysis` returns non-zero `past_performance_count` for a NAICS code where a linked entity has awards, even when the org's own `organization_past_performance` is empty for that NAICS.
3. `v_certification_expiration_alert` surfaces SBA certs attached to linked UEIs, not just the org's own `uei_sam`.
4. `v_sba_size_standard_monitor` includes NAICS registered on linked entities.
5. Mentor-Protégé page loads without error; empty result set renders a clean empty state.
6. All three view changes applied to live DB in the same commit as the DDL edit.
7. (Task 6) For an org with at least one affiliate (e.g. a `SISTER_SUBSIDIARY` link), the
   affiliation-aware eligibility call returns a **combined** receipts/headcount total that equals the
   org's own value plus every included affiliate's value, compared against the correct NAICS threshold
   by `size_type`.
8. (Task 6) `TEAMING` links are **excluded** from the roll-up; `SELF`, `SISTER_SUBSIDIARY`,
   `JV_PARTNER`, and parent links are **included**.
9. (Task 6) When the standalone determination is "small" but the rolled-up determination is
   "other-than-small," the result flags `flippedToOtherThanSmall = true` and the UI surfaces it where
   the size verdict is shown.
10. (Task 6) Linked UEIs with no receipts/headcount on file are reported as `missingAffiliateData`
    (a gap), **not** silently treated as zero.
11. (Task 6) The Phase 129 standalone `CheckSizeEligibility` path is unchanged; the affiliation path is
    additive.

---

## Known Issues / Deferred

- **`MENTOR` / `PROTEGE` relationship types** — requires MPA data model, `mpa_effective_date`, and aggregation rules that distinguish past-perf inheritance (§ 125.9(d)) from size-standard eligibility. Not in scope here.
- **Tribal entity attribute + auto-suggest sisters** — a `tribal_ownership_type` attribute on entities plus a "find sister companies under the same tribal parent" suggestion flow.
- **Per-link aggregation override UI** — flipping the default "this link counts for past-perf / NAICS / size / certs" per-link, with a reason note. The fixes above use a single default (all active links count for all view purposes).
- **Grouped relationship picker with plain-English tooltips** — regrouping the dropdown into "Under common ownership", "Mentor-Protégé", "Partnership" sections with one-line tooltips per option.
- **Proposal-time disclosure badges** — chips on past-perf rows that surface which linked entity the row came from.
- **(Task 6) Mentor-protégé affiliation exclusion (13 CFR 125.9(b)(3))** — an approved SBA
  mentor-protégé agreement exempts the pair from affiliation for size purposes. Modeling that exclusion
  requires the MPA data model that is itself deferred (see the `MENTOR` / `PROTEGE` item above). Until
  then, the roll-up applies the conservative default for any MP relationship that is represented as an
  affiliation-bearing link.
- **(Task 6) Ownership-percentage / pro-rated aggregation** — 121.103 aggregates affiliated entities as
  a whole (no pro-rating); finer rules (e.g. minority-interest / negative-control nuances, the SBA
  "totality of circumstances" test) are out of scope for the default rule and would layer onto the
  per-link override UI deferred above.
- **(Task 6) Calculation-window precision** — receipts should be a 5-year average and employees a
  24-month average per affiliate. The roll-up uses whatever averaged figures SAM.gov / the org profile
  already provide; computing those windows from raw period data is out of scope here.
