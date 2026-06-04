# Phase 133: Linked Entity Aggregation Fixes + Sister Subsidiary + SBA Affiliation Size Roll-Up

**Status:** COMPLETE (2026-06-03)
**Priority:** Medium — bug fixes for three linked-entity views and one broken page, plus one new relationship type.
**Dependencies:** Phase 115D (Teaming & Partnerships — `organization_entity`), Phase 115F (Onboarding & Past Performance — the three views below). **Task 6 (affiliation size roll-up) additionally depends on Phase 129 Task 3** — the size-eligibility engine (`CheckSizeEligibilityAsync`) it extends.

---

## Verification — 2026-06-01

Multi-agent verification across DB, C# API, and UI confirms **no Phase 133 work has been implemented**. `PLANNED` status is accurate. Findings:

- **Tasks 2/3/4 (views) — NOT IMPLEMENTED.** `115f_onboarding_past_performance.sql` contains zero references to `organization_entity` or `entity_naics`; no later migration redefines these views. `SHOW CREATE VIEW` on **prod** (`192.168.0.137`) confirms all three (`v_portfolio_gap_analysis`, `v_certification_expiration_alert`, `v_sba_size_standard_monitor`) are still org-only. No drift between file and prod. (Dev DB on `127.0.0.1:3306` was not listening at verification time, so dev was not directly confirmed — file/prod agree, so dev is almost certainly the same.)
- **Task 1 — NOT IMPLEMENTED.** `OrganizationEntityService.cs` `ValidRelationships` = `{ SELF, JV_PARTNER, TEAMING }` only. `OrgEntitiesTab.tsx` `RELATIONSHIP_OPTIONS` = same three; the per-relationship switch (lines ~153-164) is a **color** switch (no icons) with no `SISTER_SUBSIDIARY` branch. `SISTER_SUBSIDIARY` appears nowhere except this doc.
- **Task 5 — NOT FIXED / premise needs re-check.** `TeamingController` `GET /api/v1/teaming/mentor-protege` and `TeamingService.GetMentorProtegeCandidatesAsync` are unchanged since Phase 129 (no error-handling or query fix). `MentorProtegePage.tsx` still renders the generic `ErrorState` "Failed to load mentor-protege pairs" and has **no dedicated empty state** (falls through to an empty `DataTable`). **Key data point:** the backing view `v_mentor_protege_candidate` exists on prod and runs, but `SELECT *` returns **~5.49M rows** — a likely cartesian blow-up and a strong candidate for the real cause of the load error (timeout/perf), to investigate during implementation.
- **Task 6 — NOT IMPLEMENTED.** No `CheckSizeEligibilityWithAffiliatesAsync`, no `AffiliationSizeService`, no affiliated result DTO, no endpoint, no UI (`flippedToOtherThanSmall` etc. found nowhere in `ui/src`). The additive baseline — Phase 129 `CompanyProfileService.CheckSizeEligibilityAsync(int orgId, string naicsCode)` — is present and intact.
- **Pre-existing bug found (Task 4):** `v_sba_size_standard_monitor` compares `size_type = 'R'` (CASE + WHERE, plus the comment at ~line 145), but the loaded reference data is `'M'` / `'E'` (513 / 483 rows in the source CSV `workdir/converted/local database/data_to_import/naics_size_standards.csv`); the revenue branch therefore never matches and revenue-based size monitoring is currently non-functional (all revenue-based NAICS silently dropped). **CONFIRMED ON PROD (2026-06-01):** live data is `'M'`=500 / `'E'`=478 (no `'R'`); the live view did compare `'R'`. **FIXED & APPLIED TO PROD (2026-06-01):** the `'R'`→`'M'` correction is committed in the standalone idempotent hotfix migration `fed_prospector/db/schema/migrations/133a_fix_size_standard_monitor_size_type.sql` and the 115f source (`115f_onboarding_past_performance.sql`), and **applied to prod** (live view def now has 0 `'R'` / 3 `'M'` tokens; verified functionally — old `'R'` logic returned NULL for revenue NAICS, new `'M'` logic computes correctly; no data modified). The view returns 0 rows today only because no org has `annual_revenue`/`employee_count` entered yet (0 of 3 orgs), not because of the bug. **DEV PENDING:** local MySQL (`127.0.0.1:3306`) was not running at apply time — apply `133a` to dev when it is up so dev does not drift behind prod (CLAUDE.md rule 9).
- **Title reconciled:** filename, H1, and the MASTER-PLAN row now all use the canonical name "Linked Entity Aggregation Fixes + Sister Subsidiary + SBA Affiliation Size Roll-Up" (file renamed from `133-MENTOR-PROTEGE-AND-SUBSIDIARY-LINKING.md` on 2026-06-01).

### Design decisions — 2026-06-01

Open questions on Task 6 resolved with the product owner; folded into the tasks below:

1. **`size_type` is `'M'` / `'E'`, not `'R'`.** Source CSV + reference doc `13-NAICS-SIZE-STANDARDS.md` use `'M'` = receipts (in $millions) and `'E'` = employees. The existing `v_sba_size_standard_monitor` erroneously compares `'R'`, so its revenue branch is dead (pre-existing bug). Task 4 corrects `'R'`→`'M'` in the view; all roll-up math in Task 6 uses `'M'`/`'E'`.
2. **Affiliate financials are entered manually via the UI**, not sourced from SAM.gov `entity_*` tables (those carry no revenue/headcount, and affiliates are external UEIs with no `organization` row). Two new nullable columns on `organization_entity` (`affiliate_annual_revenue`, `affiliate_employee_count`) hold owner-entered figures. The org's own figures stay on `organization.annual_revenue` / `organization.employee_count`.
3. **The org is always the hub (its `SELF` link); there is no upward "parent" link.** The included affiliation set is active rows with relationship in { `SELF`, `SISTER_SUBSIDIARY`, `JV_PARTNER` }; `TEAMING` is excluded. Upward parent-company linking is out of scope (see Deferred).
4. **Aggregation is combined/sum, not largest-single-entity** — per 13 CFR 121.103(a)(6) and 121.104(d)(1), size = the org's receipts/employees PLUS each included affiliate's, compared as a combined total to the NAICS threshold. The only "size off one party" case is an SBA-approved mentor-protégé JV (mentor's size excluded, 13 CFR 125.9(d)(1)(iii) & (d)(4); 121.103(b)(6)), which is **now in scope** for Task 6 via a per-link `mpa_approved` flag on the `JV_PARTNER` link (not a new relationship type) — driven by the owner's real situation of one approved-MPA JV (mentor excluded) and one regular JV (counted). Only the broader mentor-protégé past-performance inheritance modeling (§ 125.9(d), distinct from this size exclusion) stays deferred.

---

## Completion — 2026-06-03

All 6 tasks are implemented across DB / C# / UI and live on **prod**.

- **Task 1 — `SISTER_SUBSIDIARY` relationship type.** Added to `ValidRelationships` in `OrganizationEntityService.cs` and to `RELATIONSHIP_OPTIONS` + the relationship-color switch in `OrgEntitiesTab.tsx`. (No DB migration — `relationship` is free-form `VARCHAR`.)
- **Tasks 2/3/4 — onboarding views aggregate linked entities.** `v_portfolio_gap_analysis`, `v_certification_expiration_alert`, and `v_sba_size_standard_monitor` now aggregate across linked entities (migration `133b_linked_entity_view_aggregation.sql`); **applied & verified on PROD**. `v_portfolio_gap_analysis` now returns rows it previously missed; all three views reference `organization_entity`; the size view retains the `size_type` `'R'`→`'M'` fix from `133a`.
- **Task 5 — Mentor-Protégé page fixed.** Root cause was a cartesian blow-up in the backing view: the cardinality fix (`133c_fix_mentor_protege_candidate_cardinality.sql`) dropped `v_mentor_protege_candidate` from ~5.49M to ~309K rows on **prod**. Backend hardened (no unbounded count; the 400-on-mount is fixed) and the UI now renders a clean empty state.
- **Task 6 — SBA affiliation size roll-up (13 CFR 121.103).** Four new `organization_entity` columns — `affiliate_annual_revenue`, `affiliate_employee_count`, `mpa_approved`, `mpa_effective_date` — added via migration `133d_affiliation_size_rollup_columns.sql` (**applied & verified on prod**) and EF migration `AddAffiliationSizeRollupColumns`. Service surface: `CheckSizeEligibilityWithAffiliatesAsync` + `AffiliatedSizeEligibilityResultDto` + endpoint `GET /api/v1/org/size-eligibility/{naicsCode}`. UI adds the affiliate-financial inputs, the JV approved-MPA flag, and a standalone-vs-affiliated display with a `flippedToOtherThanSmall` callout.

**Verification level:** C# builds (0 errors), **959 automated tests pass** (Core 345 / Infra 330 / Api 284), UI builds, and **all DB migrations applied & verified on PROD**. Manual UI click-through is recommended as a final check.

**Known follow-ups (not blockers):**
- The EF model snapshot is materially stale vs. the actual models (pre-existing; per CLAUDE.md the prod-apply mechanism is raw SQL, not EF migrate).
- The mentor-protégé view at ~309K rows could be tightened further.

---

## Context

`organization_entity` links an org to one or more SAM UEIs (sister subsidiary, JV partner, teaming partner, etc.) but three of the onboarding/size-standard views built in Phase 115F don't actually aggregate data across those linked entities — they only look at the org's own row. We also need one additional relationship type (`SISTER_SUBSIDIARY`) to model common-parent subsidiaries. A related page (Mentor-Protégé) errors on load.

The org is the hub (its `SELF` link); affiliates are only linked downward/sideways (`SISTER_SUBSIDIARY`, `JV_PARTNER`). Upward parent-company linking is out of scope — see **Deferred**.

The SBA-approved mentor-protégé **size exclusion** is in scope for Task 6 via a per-link `mpa_approved` flag on a `JV_PARTNER` link (mentor's size not counted; see Task 6). Broader mentor-protégé modeling — dedicated `MENTOR`/`PROTEGE` relationship types, past-performance inheritance under § 125.9(d), tribal exemption, per-link aggregation overrides — stays deferred (see **Deferred** below).

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
- **File:** `ui/src/pages/organization/OrgEntitiesTab.tsx` — add `{ value: 'SISTER_SUBSIDIARY', label: 'Sister subsidiary' }` to the `RELATIONSHIP_OPTIONS` const (lines ~43–47) and add a matching `case 'SISTER_SUBSIDIARY':` branch returning a chip color to the `relationshipColor` switch (lines ~153–164). The relationship chip is rendered from `relationshipColor(link.relationship)` (~line 369); there are no per-relationship icons or labels to add.
- **No DB migration needed** — `organization_entity.relationship` is a free-form `VARCHAR` with no CHECK constraint.

### Task 2 — Fix `v_portfolio_gap_analysis` to aggregate linked entities

- **File:** `fed_prospector/db/schema/migrations/115f_onboarding_past_performance.sql` (view at ~line 263).
- **Change:** NAICS source unions `organization_naics` with `entity_naics` (keyed by `uei_sam`, `naics_code`) joined through `organization_entity` (where `is_active = 'Y'`). Past-performance counts union the org's `organization_past_performance` rows with awards from linked UEIs via `usaspending_award` joined `organization_entity.uei_sam = usaspending_award.recipient_uei`, grouped by `usaspending_award.naics_code`, filtered to `usaspending_award.deleted_at IS NULL`. **Do not substitute `fpds_contract`** (CLAUDE.md performance rule). All active linked relationships count; per-link overrides are deferred.
- Apply to live DB in same commit (CLAUDE.md rule 9).

### Task 3 — Fix `v_certification_expiration_alert` to include linked entities' certs

- **File:** same migration file, view at ~lines 101–138.
- **Change:** the SAM.gov section currently joins `entity_sba_certification esc INNER JOIN organization o ON o.uei_sam = esc.uei_sam`. Replace with a UNION (or IN-list) that also includes any `uei_sam` from `organization_entity` where `organization_id = o.organization_id` and `is_active = 'Y'`.
- Apply to live DB.

### Task 4 — Fix `v_sba_size_standard_monitor` to use aggregated NAICS

- **File:** same migration file, view at ~lines 148–173.
- **Change:** source NAICS from the same aggregated set used in Task 2 (org's own `organization_naics` UNION linked entities' `entity_naics` via active `organization_entity` rows), not just `organization_naics` on the org.
- **The pre-existing `size_type` bug is already STAGED — fold it into this view rebuild.** The view's CASE and WHERE clauses compared `size_type = 'R'`, but the loaded reference data uses `'M'` (receipts/$millions) and `'E'` (employees) — so the revenue branch never matched and every revenue-based NAICS was silently dropped (revenue-based size monitoring is currently non-functional). The `'R'`→`'M'` correction (CASE expression, WHERE clause, and the comment) is **already staged (2026-06-01)** in the standalone idempotent hotfix migration `fed_prospector/db/schema/migrations/133a_fix_size_standard_monitor_size_type.sql` and in the 115f source. So **Task 4's remaining work is only the linked-entity NAICS aggregation** (sourcing NAICS from the aggregated set above) layered on top of the already-corrected `'M'`/`'E'` view — when you redefine the view here, start from the corrected definition, not the old `'R'` one.
- Apply to live DB (CLAUDE.md rule 9 — both dev and prod). Note: the `133a` hotfix was **applied to prod 2026-06-01** (dev pending — local MySQL was down); whoever lands Task 4 supersedes it with the aggregated view, so build the aggregated view from the corrected `'M'`/`'E'` definition and apply the final aggregated definition to both DBs (back up first per the Phase 134 runbook).

### Task 5 — Diagnose and fix Mentor-Protégé page error

- **UI:** `ui/src/pages/teaming/MentorProtegePage.tsx` (shows "Failed to load mentor-protege pairs").
- **API:** `TeamingController` → `ITeamingService.GetMentorProtegeCandidatesAsync()` → `v_mentor_protege_candidate` (defined in `fed_prospector/db/schema/migrations/115d_teaming_partnerships.sql`).
- **Leading hypothesis:** verification found that `v_mentor_protege_candidate` runs on prod but `SELECT *` returns **~5.49M rows** — a likely cartesian/over-broad join blow-up that would make the endpoint time out or exhaust memory rather than return a clean result. **Investigate the view's join cardinality first.**
- **Steps:** (1) run `SELECT COUNT(*) FROM v_mentor_protege_candidate` against live DB and inspect the view definition (`115d_teaming_partnerships.sql`, view at ~line 207) for a missing/over-broad join condition causing the ~5.49M-row blow-up; if the row count is the cause, constrain the join (and/or add pagination/limits) so the candidate set is bounded; (2) call `GET /api/v1/teaming/mentor-protege` and capture the response to confirm whether it errors, times out, or returns empty; (3) if the view still errors after the cardinality fix, fix the view; (4) if the endpoint returns empty successfully but the UI renders an error, fix the frontend to render a clean empty state instead. (Deeper root-cause analysis of the join can happen at implementation time; the ~5.49M-row lead is the starting point.)

### Task 6 — SBA Affiliation Size Roll-Up (13 CFR 121.103)

> **Why this lives here:** Phase 129's size-eligibility engine
> (`CompanyProfileService.CheckSizeEligibilityAsync(int orgId, string naicsCode)`, plus a batch
> overload `CheckSizeEligibilityAsync(int orgId, IEnumerable<string> naicsCodes)`) determines whether
> an org is "small" using **only that single org's** `organization.annual_revenue` and
> `organization.employee_count`. Under **13 CFR 121.103**, a firm's size must **include the receipts
> and employees of its affiliates** (here: sister subsidiaries and joint-venture relationships, except
> that an SBA-approved mentor-protégé JV excludes the mentor's size via the per-link `mpa_approved`
> flag). The current number can therefore be **too favorable** (understated
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
`SELF` (the org's own SAM UEI), `SISTER_SUBSIDIARY` (common-parent subsidiaries, Task 1), and
`JV_PARTNER`. The org is the hub (its `SELF` link, the protégé in any MPA relationship) and **always
counts**; there is **no upward "parent" link** — upward parent-company linking is out of scope (see
Known Issues / Deferred). `TEAMING` is a **non-affiliate** relationship by default (teaming alone does
not create affiliation under 121.103) and must be **excluded** from the roll-up.

**Approved-MPA exclusion (per-link).** A `JV_PARTNER` link that is flagged as an SBA-approved
mentor-protégé agreement (`mpa_approved = 'Y'`, see schema below) is **excluded** from the size
roll-up — the **mentor's size is not counted**; the JV qualifies as small for any procurement for which
the protégé/org alone qualifies as small (13 CFR 125.9(d)(1)(iii) & (d)(4); an approved MPA does not by
itself create affiliation, 121.103(b)(6)). An **unflagged** `JV_PARTNER` (`mpa_approved = 'N'`) is a
regular JV and is still **included** (counted). The flag is **per-link** because an org can hold both an
approved mentor-protégé JV (mentor excluded) and an ordinary JV (counted) at the same time. The org
itself (`SELF`, the protégé) always counts regardless. **Simplification:** we exclude only the flagged
mentor partner's standalone size; finer JV proportionate-share math (counting just the org's share of
the JV's own receipts/headcount) stays deferred (see Known Issues).

**Aggregation is combined/sum, not largest single entity.** Per **13 CFR 121.103(a)(6)** and
**121.104(d)(1)**, a firm's size = the **sum** of its own receipts/employees **plus** each included
affiliate's, compared as a combined total to the NAICS threshold — it is **not** the largest single
entity. The one case where size is effectively based off a single party is an **SBA-approved
mentor-protégé joint venture**, where the mentor's size is excluded (13 CFR 125.9(d)(1)(iii) & (d)(4);
121.103(b)(6)) — that MPA-JV exclusion is **in scope for this task** via the per-link `mpa_approved`
flag (see the approved-MPA exclusion above and the schema below).

**Do not reuse the "effective NAICS" linked-UEI helper for this roll-up.** The existing effective-NAICS
helper (Phase 91/104) intentionally includes `TEAMING` and `partner_uei` for past-performance / pWin
purposes; the size roll-up needs a **different** inclusion set (`TEAMING` excluded). The two
relationship purposes — pWin effective-NAICS vs. size affiliation — intentionally do not align, so build
the roll-up's included set independently rather than calling that helper.

**Where affiliate receipts/headcount come from — manual UI entry.** SAM.gov `entity_*` tables carry
**no** revenue or employee data, and affiliates are external UEIs with no `organization` row, so the
roll-up cannot source affiliate financials from them. Instead, the org admin **enters them manually**
on the entity-link form. Add two new nullable columns to `organization_entity`:
`affiliate_annual_revenue DECIMAL(18,2) NULL` and `affiliate_employee_count INT NULL`, populated via the
OrgEntitiesTab link/edit form (`ui/src/pages/organization/OrgEntitiesTab.tsx`) and the link API
(`OrganizationController` `/api/v1/org/entities`, `OrganizationEntityService`, `LinkEntityRequest` DTO
in `OrganizationEntityDto.cs`). The org's **own** figures continue to come from
`organization.annual_revenue` / `organization.employee_count` (the `SELF` row / hub org).

**Approved-MPA flag columns.** In addition, add two more columns to `organization_entity` to carry the
per-link approved-mentor-protégé flag (drives the exclusion above): `mpa_approved CHAR(1) NOT NULL
DEFAULT 'N'` (`'Y'`/`'N'`, matching the existing `is_active` convention on this table) and
`mpa_effective_date DATE NULL`. These are populated on the same link/edit form (only meaningful when
`relationship = 'JV_PARTNER'`).

`organization_entity` is **EF Core-owned**, so these four new columns need an **EF migration AND** the
SQL DDL (`fed_prospector/db/schema/tables/90_web_api.sql`, table at ~line 196) kept in sync, applied to
**both** dev and prod (CLAUDE.md rule 9).

If an included affiliate has no entered receipts/headcount for the value needed by the applicable
`size_type`, count it as a **gap** (do not silently treat missing affiliate data as zero — that
re-introduces the understatement bug). Surface it in `missingAffiliateData[]` so the user knows the
roll-up is incomplete. Until the owner enters these numbers, affiliates correctly show as
missing-data gaps rather than zero. **Owner will populate these figures via the UI as the data is
gathered; the feature ships with the input fields, and the roll-up treats not-yet-entered affiliates as
gaps.**

**Aggregation math (per 121.103):**
- **Revenue-based standards (`size_type = 'M'`)** — sum the org's `organization.annual_revenue` plus
  every included affiliate's `organization_entity.affiliate_annual_revenue`; compare the **combined**
  receipts against the NAICS threshold (the threshold is in $millions for `'M'`).
- **Employee-based standards (`size_type = 'E'`)** — sum the org's `organization.employee_count` plus
  every included affiliate's `organization_entity.affiliate_employee_count`; compare the **combined**
  headcount against the threshold.
- Affiliation is determined **as a whole** (the combined enterprise is small or it is not); it is not
  pro-rated by ownership percentage in this default rule. Ownership-percentage / per-link override
  refinement is deferred (see Known Issues and the Task-spanning "Per-link aggregation override UI"
  deferred item).

**Service surface.** Extend the Phase 129 eligibility engine rather than forking it:
- Add an affiliation-aware path that returns the standalone result **and** the rolled-up result, e.g.
  `CheckSizeEligibilityWithAffiliatesAsync(int orgId, string naicsCode)` returning a result that
  includes: `standaloneEligible`, `affiliatedEligible`, `combinedRevenue` / `combinedEmployees`,
  `threshold`, `sizeType`, `affiliateCount`, `includedAffiliates[]` (uei + relationship + contributed
  amount), `excludedAffiliates[]` (uei + relationship + exclusion reason, e.g. `APPROVED_MPA` for a
  flagged mentor-protégé JV or `TEAMING` for a teaming partner — so the UI can show **why** a partner
  wasn't counted), `missingAffiliateData[]` (uei list with no receipts/headcount), and a
  `flippedToOtherThanSmall` boolean (true when standalone says small but the roll-up says
  other-than-small — the dangerous case).
- The standalone `CheckSizeEligibilityAsync` from Phase 129 stays intact for callers that want the
  org-only number; the affiliation path is additive.

**View / UI wiring.** `v_sba_size_standard_monitor` (fixed in Task 4 to aggregate linked NAICS) should
also reflect the affiliated size verdict where it reports eligibility, so the monitor and any
"approaching outsized" alert use the combined number. Where the UI shows the size verdict (NAICS step /
size monitor), display **both** the standalone and affiliated determinations when they differ, with a
clear callout when `flippedToOtherThanSmall` is true.

- **Files (anticipated):**
  - `api/src/FedProspector.Infrastructure/Services/CompanyProfileService.cs` — affiliation-aware
    eligibility method (or a dedicated `AffiliationSizeService`).
  - `api/src/FedProspector.Core/DTOs/` — new affiliated-eligibility result DTO.
  - **New `organization_entity` columns** (`affiliate_annual_revenue`, `affiliate_employee_count`,
    `mpa_approved`, `mpa_effective_date`), kept in sync across **EF migration** (entity model +
    migration), the SQL DDL `fed_prospector/db/schema/tables/90_web_api.sql`, and applied to **both dev
    and prod** (CLAUDE.md rule 9). Plus the link API to accept/persist them:
    `api/src/FedProspector.Core/DTOs/Organizations/OrganizationEntityDto.cs` (`LinkEntityRequest` +
    `OrganizationEntityDto`), `OrganizationEntityService`, `OrganizationController` `/api/v1/org/entities`.
  - `ui/src/pages/organization/OrgEntitiesTab.tsx` — input fields for the two manual figures on the
    link/edit form, plus (when `relationship = 'JV_PARTNER'`) an "SBA-approved mentor-protégé agreement"
    checkbox and optional effective date that persist to `mpa_approved` / `mpa_effective_date`.
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
8. (Task 6) `TEAMING` links are **excluded** from the roll-up; `SELF`, `SISTER_SUBSIDIARY`, and
   `JV_PARTNER` are **included** by default.
9. (Task 6) When the standalone determination is "small" but the rolled-up determination is
   "other-than-small," the result flags `flippedToOtherThanSmall = true` and the UI surfaces it where
   the size verdict is shown.
10. (Task 6) Included affiliates with no manually-entered receipts/headcount (the value needed for the
    applicable `size_type` is NULL on the `organization_entity` link row) are reported as
    `missingAffiliateData` (a gap), **not** silently treated as zero.
11. (Task 6) The Phase 129 standalone `CheckSizeEligibilityAsync` path is unchanged; the affiliation
    path is additive.
12. (Task 6) A `JV_PARTNER` link flagged as an approved mentor-protégé agreement (`mpa_approved = 'Y'`)
    is **excluded** from the size roll-up (the mentor's size is **not** counted; the JV is small if the
    protégé/org alone is small — 13 CFR 125.9(d)(1)(iii) & (d)(4)), while an **unflagged** `JV_PARTNER`
    (`mpa_approved = 'N'`) is **included** — verifiable with the owner's two JVs (one approved-MPA, one
    regular: the approved-MPA mentor is reported in `excludedAffiliates[]` with reason `APPROVED_MPA`,
    the regular JV partner is counted in `includedAffiliates[]`).

---

## Known Issues / Deferred

- **Dedicated `MENTOR` / `PROTEGE` relationship types + past-performance INHERITANCE** — the broader
  mentor-protégé modeling stays deferred: dedicated `MENTOR`/`PROTEGE` relationship types (rather than the
  per-link `mpa_approved` flag on `JV_PARTNER` that Task 6 now adds) and **past-performance inheritance**
  under § 125.9(d) (a protégé claiming the mentor's past performance / experience) are **distinct from the
  size-eligibility exclusion** and remain out of scope. Only the size-standard exclusion (mentor's size not
  counted) is being pulled into Task 6 via the `mpa_approved` flag; the past-perf-inheritance modeling is
  not.
- **Tribal entity attribute + auto-suggest sisters** — a `tribal_ownership_type` attribute on entities plus a "find sister companies under the same tribal parent" suggestion flow.
- **Per-link aggregation override UI** — flipping the default "this link counts for past-perf / NAICS / size / certs" per-link, with a reason note. The fixes above use a single default (all active links count for all view purposes).
- **Grouped relationship picker with plain-English tooltips** — regrouping the dropdown into "Under common ownership", "Mentor-Protégé", "Partnership" sections with one-line tooltips per option.
- **Proposal-time disclosure badges** — chips on past-perf rows that surface which linked entity the row came from.
- **(Task 6) Mentor-protégé affiliation exclusion — NOW IN SCOPE** via the per-link `mpa_approved` flag
  (see Task 6). An approved SBA mentor-protégé agreement exempts the JV from affiliation for size purposes
  (the JV is small if the protégé/org alone is small — 13 CFR 125.9(d)(1)(iii) & (d)(4); an approved MPA
  does not by itself create affiliation, 121.103(b)(6)). This is implemented as a per-link
  `mpa_approved = 'Y'` flag on a `JV_PARTNER` link, not a new relationship type — so it does **not** pull
  in the broader mentor-protégé modeling (dedicated `MENTOR`/`PROTEGE` types and past-performance
  inheritance under § 125.9(d)), which stays deferred (see the item above).
- **(Task 6) Ownership-percentage / pro-rated aggregation** — 121.103 aggregates affiliated entities as
  a whole (no pro-rating); finer rules (e.g. minority-interest / negative-control nuances, the SBA
  "totality of circumstances" test) are out of scope for the default rule and would layer onto the
  per-link override UI deferred above.
- **(Task 6) Calculation-window precision** — receipts should be a 5-year average (13 CFR 121.104(c)(1))
  and employees a 24-month average (13 CFR 121.106) per affiliate, and inter-affiliate transactions
  should be excluded from receipts (13 CFR 121.104(a)). The roll-up uses whatever averaged figures the
  owner enters per affiliate / the org profile already provides; computing those windows from raw period
  data and netting inter-affiliate receipts is out of scope here.
- **(Task 6) Upward "parent company" linking** — the org is modeled as the hub (its `SELF` link) and
  affiliates are linked downward/sideways only (`SISTER_SUBSIDIARY`, `JV_PARTNER`); there is no `PARENT`
  relationship type or upward link. Modeling a parent that owns the hub org is out of scope.
