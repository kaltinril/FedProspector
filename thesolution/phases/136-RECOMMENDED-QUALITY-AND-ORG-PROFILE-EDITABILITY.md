# Phase 136 — Recommended Opportunity Quality & Org Profile Editability

**Status:** In Progress — Units A, B, C, D, F, G implemented, merged to `main`, and verified (API build 0 errors/0 warnings + 1016 tests pass; UI `tsc -b` + Vite build clean). The Associated-NAICS → Recommended candidate-selection wiring + labeled scoring tier (Open Question #4, conservative default) are complete. Migration `fed_prospector/db/schema/migrations/136_organization_associated_naics.sql` **APPLIED to prod (192.168.0.137) on 2026-06-04** (table verified). **PENDING:** apply the same migration to **dev (127.0.0.1)** when its local server is up; and **deploy code + rebuilt UI to prod via `deploy.ps1`** (the new features are not live until deployed). **Unit E** (automatic NAICS-hierarchy relatedness) remains **deferred (P3)**.
**Priority:** High — the Recommended Opportunities list is the product's primary daily surface, and it is currently showing junk while burying the opportunities the user cares about.
**Dependencies:** Phase 100 (Recommended Dedup & Filtering), Phase 101 (Org Set-Aside Eligibility), Phase 110 (Attachment Intelligence — clearance extraction), Phase 115F (Onboarding & Past Performance), Phase 129 (NAICS/SBA Size Standards) — all COMPLETE.

---

## Problem

The org **MSOne** (`org_id = 3`, a WOSB/8(a) with thin federal prime history) reports that the **Recommended Opportunities** list shows junk and buries the opportunities she actually cares about. Investigation against live code and the prod DB found that the Recommended list is ranked by the **OQS score** and capped at **top-N**, with several distinct root causes:

1. **No way to fix the org profile outside the onboarding wizard.** The Organization page only edits the org *name*. There is no UI to set the **full org profile** (legal name, DBA, UEI, CAGE, EIN, entity structure, address, phone, website, fiscal year end, annual revenue, employee count), NAICS codes, or certifications after onboarding. Crucially, `org_id = 3` has `annual_revenue = NULL`, so the pWin **Size Eligibility** factor returns "undeterminable" — a self-inflicted scoring gap with no user-facing remedy. The user wants to edit the **entire** org profile easily on the Organization page, see the org's **own NAICS codes** (full list, primary flagged), and maintain a manually-curated list of **"associated" NAICS** beyond the registered/linked-entity codes that participates in matching/recommendations.

2. **Set-aside / sources-sought / RFI-style market-research notices are scored and ranked like biddable solicitations.** A "Sources Sought" notice has no meaningful win probability, yet it competes for the same top-N slots as real solicitations and is ranked by an OQS score that does not apply to it.

3. **Opportunities that require a security clearance the org cannot meet are mixed into the list** with no way to hide them, even though clearance intel has already been extracted from attachments for analyzed opportunities.

4. **The OQS/pWin scores are dragged down by factors that have no real data.** For a thin-history org, factors like Reuse Potential, Growth Potential, Re-compete Advantage, and Value Alignment default to a neutral/low score and are summed at full weight into the total. This pulls otherwise-strong opportunities (good Profile Match, low Competition, good Timeline) down the ranking and below the top-N cutoff, so they get buried.

5. **Linked-entity (affiliate) financials can only be set once, at link time.** The per-affiliate `affiliate_annual_revenue` / `affiliate_employee_count` (used by the Phase 133 affiliation size roll-up) can only be supplied through the link upsert; there is no way to correct or update them later, and the entities list shows only a NAICS **count** per linked entity rather than each entity's primary NAICS. The user wants to edit each linked entity's employees/revenue **anytime** (not just at link creation) and to see each linked entity's primary NAICS in the list.

This phase implements the fixes the user chose, scoped as concrete units with exact hook points.

---

## Background: How the Recommended Engine Works Today (verified)

**Service:** `api/src/FedProspector.Infrastructure/Services/RecommendedOpportunityService.cs`

- **Candidate query** (lines 86–90): filters `naicsCodes.Contains(o.NaicsCode)` (**exact NAICS match**), `o.Active != "N"`, `!OpportunityFilters.NonBiddableTypes.Contains(o.Type)`, and deadline not past.
- **Dedup** by solicitation (lines 131–135) — keeps latest notice per solicitation (Phase 100).
- **Intel batch-load** for re-compete data (lines 138–151): already batch-loads `OpportunityAttachmentSummaries` grouped by `NoticeId`. **This is the load to extend for clearance** (Unit B).
- **Set-aside cert HARD filter** (lines 177–182): skips opps requiring a cert the org lacks. **This is correct — leave it.**
- **7-factor OQS** built at lines 222–231; `oqScore = Math.Round(factors.Sum(f => f.WeightedScore), 1)` at **line 233**; `realDataCount` / `confidence` at lines 234–235; **top-N cap** at lines 280–284.
- **Duplicate OQS model** in `CalculateOqScoreAsync` (factors at 430–439, sum at **line 441**, realDataCount/confidence at 442–443). **Both code paths must change together** for any scoring change.
- **Factor scoring methods** at lines 599–752; `BuildFactor` at lines 761–772 — already records `HadRealData` per factor.

**pWin engine:** `api/src/FedProspector.Infrastructure/Services/PWinService.cs` — `totalScore = Math.Round(factors.Sum(f => f.WeightedScore), 1)` at **line 221**; per-factor `HadRealData` exists; `realDataCount` / `dataCompletenessPercent` / `confidence` at lines 231–233. The same renormalization (Unit D) applies here.

**Non-biddable types:** `api/src/FedProspector.Core/Constants/OpportunityFilters.cs` = `["Award Notice", "Justification", "Sale of Surplus Property", "Consolidate/(Substantially) Bundle"]`.

### Actual notice `type` values in prod (`opportunity.type`, varchar)

| Type | Count | Role in this phase |
|------|-------|--------------------|
| Combined Synopsis/Solicitation | 50,250 | Biddable solicitation |
| Solicitation | 24,342 | Biddable solicitation |
| Award Notice | 23,442 | Non-biddable (already excluded) |
| Sources Sought | 10,060 | **Market research / RFI-style** (Unit C) |
| Presolicitation | 8,651 | Maybe market research — **open question** (Unit C) |
| Special Notice | 6,007 | **Market research / RFI-style** (Unit C) |
| Justification | 1,626 | Non-biddable (already excluded) |
| (small others) | — | — |

"RFI"-style market-research notices in this dataset are **"Sources Sought"** and **"Special Notice"**. **Presolicitation is a maybe** — see Open Questions.

### Clearance intel storage (verified)

Table `opportunity_attachment_summary` (DDL: `fed_prospector/db/schema/tables/36_attachment.sql`) has:
- `clearance_required` `CHAR(1)` (Y/N)
- `clearance_level` `VARCHAR(50)`
- `clearance_scope` `VARCHAR(50)`
- `clearance_details` `TEXT`
- `overall_confidence` `ENUM('high','medium','low') NOT NULL`

C# entity `OpportunityAttachmentSummary` exposes `ClearanceRequired` and `OverallConfidence` (already used in `AttachmentIntelService`). Clearance is stored **per attachment**, so it must be aggregated per `notice_id`.

**Aggregation rule:** treat a notice as **"high-confidence clearance required"** if **ANY** of its attachment summaries has `clearance_required = 'Y'` **AND** `overall_confidence = 'high'`.

> **Important caveat (document in UI and code):** Only opportunities that have been **document-analyzed** have this signal. Un-analyzed opportunities **cannot** be flagged and will not be filtered by clearance. The filter is best-effort, not exhaustive.

### Org profile editability (verified)

- **Backend already supports partial edits of the FULL profile.** `CompanyProfileService.UpdateProfileAsync` (`api/src/FedProspector.Infrastructure/Services/CompanyProfileService.cs:35`) is null-coalescing — it only writes non-null fields, so partial updates are safe. It **already covers every profile field the user wants editable** (verified lines 43–60): `Name`, `LegalName`, `DbaName`, `UeiSam`, `CageCode`, `Ein`, `AddressLine1/2`, `City`, `StateCode`, `ZipCode`, `CountryCode`, `Phone`, `Website`, `EmployeeCount`, `AnnualRevenue`, `FiscalYearEndMonth`, `EntityStructure`. `SetNaicsAsync` does a **full replace** of org NAICS; `SetCertificationsAsync` is similar (and Phase 101 made it only touch `MANUAL`-source rows). Endpoints: `PUT /api/v1/org/profile`, `GET`/`PUT /api/v1/org/naics`, `PUT /api/v1/org/certifications`. **So Unit A can cover the full profile with no backend change.**
- **UI gap.** `ui/src/pages/organization/OrgSettingsTab.tsx` only edits the org **name** (and shows slug / maxUsers / subscriptionTier / createdAt). There is **no** UI to edit any of the other profile fields, NAICS codes, or certifications outside the onboarding wizard (`ui/src/pages/setup/`, with NAICS fields in `NaicsCodesStep.tsx`). Org NAICS currently appears only as a **count** on the Entity Linking tab — there is **no list view** of the org's own NAICS codes.
- **Existing admin gate** already present in `OrgSettingsTab.tsx` (line 26): `canEdit = user?.role === 'owner' || user?.role === 'admin' || user?.isOrgAdmin === true`. Reuse this for all editing added by this phase.
- **Consequence of missing revenue:** `org_id = 3` has `annual_revenue = NULL`, so the pWin **Size Eligibility** factor (`PWinService.ScoreSizeEligibilityAsync`, ~lines 1032–1061 → `CompanyProfileService.CheckSizeEligibilityAsync`) returns "undeterminable". **Entering revenue fixes it** with no code change to the scorer.

### Linked-entity (affiliate) data editability (verified)

- **Storage.** Linked entities live in `organization_entity` (entity `api/src/FedProspector.Core/Models/OrganizationEntity.cs`): columns include `affiliate_annual_revenue` (`decimal?` `AffiliateAnnualRevenue`, line 42), `affiliate_employee_count` (`int?` `AffiliateEmployeeCount`, line 45), `relationship`, `is_active`, `partner_uei`, `mpa_approved`, `mpa_effective_date`, `notes`. Each linked entity's NAICS (with `is_primary`) live in `entity_naics` (`EntityNaics.IsPrimary` is a `CHAR(1)` Y/N string, `api/src/FedProspector.Core/Models/EntityNaics.cs:20`).
- **CRITICAL gap — affiliate financials are write-once-at-link-time.** `affiliate_annual_revenue` / `affiliate_employee_count` are ONLY settable through the link upsert `POST /api/v1/org/entities` (`OrganizationController` `[HttpPost("entities")]` at line 293 → `OrganizationEntityService.LinkEntityAsync`, which sets them on an existing/reactivated link at lines 95–96 and on a new link at lines 133–134). **There is NO dedicated per-entity edit endpoint.** Existing entity endpoints are: `POST entities` (link/upsert, 293), `DELETE entities/{linkId}` (321), `POST entities/refresh-self` (342), `POST entities/resync-certs` (363), `GET entities/aggregate-naics` (377), `GET size-eligibility/{naicsCode}` (394, affiliation-aware roll-up). To make affiliate revenue/employees editable **anytime** (decoupled from the link action), Unit F **adds** a dedicated `PUT /api/v1/org/entities/{linkId}` (owner/admin gated). **No schema change** — the columns already exist.
- **Entities DTO.** `api/src/FedProspector.Core/DTOs/Organizations/OrganizationEntityDto.cs` already returns `AffiliateAnnualRevenue`/`AffiliateEmployeeCount` (lines 15–16; second DTO block 38–39) and a `NaicsCount` (line 26, populated in `OrganizationEntityService` at lines 47 and 469). It does **not** currently carry each entity's **primary NAICS** — Unit F adds a `primaryNaics` field (sourced from `entity_naics` where `is_primary = 'Y'`).
- **UI gap.** `ui/src/pages/organization/OrgEntitiesTab.tsx` renders only the NAICS **count** per linked entity (`link.naicsCount`, ~lines 396–397) and the only per-row action is deactivate (delete). There is no inline edit of affiliate revenue/employees and no display of the entity's primary NAICS.

### Associated NAICS (verified: does NOT exist today)

- There is **no table, column, or code** for a manually-curated "associated NAICS" list anywhere in the codebase. It is genuinely new and needs a **new table** (`organization_associated_naics`) plus CRUD endpoints and a UI editor (Unit G).
- **Recommended candidate selection uses ONLY the org's registered NAICS.** `RecommendedOpportunityService.GetRecommendedAsync` candidate query filters `naicsCodes.Contains(o.NaicsCode!)` at **line 87**. Associated NAICS must **expand that set** so opportunities in associated codes also surface. (Contrast with the broader `entities/aggregate-naics` endpoint, which already unions org + linked-entity + manual NAICS for *display*; associated NAICS is a distinct, user-prioritized list that should feed *matching/scoring*.)

---

## Units

| Unit | Title | Priority | Schema change? |
|------|-------|----------|----------------|
| A | Full org-profile editability + own-NAICS list on the Organization page | **P1** | No |
| B | Recommended: high-confidence clearance filter (hidden by default + toggle) | **P1** | No |
| C | Recommended: separate ungated "Market Research" section | **P1** | No |
| D | Score renormalization over present factors only | **P2** | No |
| E | NAICS-hierarchy relatedness for past performance (automatic layer) | **P3 — OPTIONAL / DEFERRED** | Yes (Unit E only) |
| F | Linked-entity data editing (primary NAICS shown + revenue/employees editable anytime) | **P1** | No (adds an endpoint only) |
| G | Associated NAICS (manual, user-prioritized list that feeds matching/scoring) | **P1** | Yes (new table) |

---

### Unit A — Full Org-Profile Editability + Own-NAICS List on the Organization Page (P1)

**Goal:** Give owner/admin a way to view and **easily edit the FULL org profile** — not just business size — without re-running the onboarding wizard, plus a visible list of the org's **own** NAICS codes with the primary flagged. This directly unblocks the Size Eligibility factor for `org_id = 3` (and any other org with NULL revenue) and satisfies user requirements #1 and #2.

**What to build** — add editable sections to `OrgSettingsTab.tsx` (or split the Organization page into sub-tabs) for owner/admin only (reuse the existing `canEdit` gate at `OrgSettingsTab.tsx:26`). All of this saves via endpoints that **already exist** — no backend change:

1. **Full org profile (requirement #1):** make the **entire** profile editable, covering every field `UpdateProfileAsync` already accepts (verified `CompanyProfileService.cs:43–60`): **legal name, DBA, UEI, CAGE, EIN, entity structure**, **address** (line1/line2, city, state, zip, country), **phone, website**, **fiscal year-end month**, **annual revenue**, **employee count** (and the display name). Save via `PUT /api/v1/org/profile` (partial, null-coalescing update — safe to send only changed fields). Keep it **easy**: a single clearly-labeled, grouped form (Identity / Address / Business Size) rather than burying revenue under a sub-feature.
2. **Own-NAICS list + editor (requirement #2):** show the **full list** of the org's own NAICS codes (closes the "only a count" gap) with the **primary clearly flagged**, plus add/remove and the ability to mark **exactly one** as primary. **Reuse the wizard's `NaicsCodesStep.tsx` logic/validation** (single-primary rule, valid 6-digit codes, dedup). Save via `PUT /api/v1/org/naics` (full replace — matches `SetNaicsAsync`). (Note this is the org's *own* registered NAICS; linked-entity NAICS are Unit F and the manual associated list is Unit G.)
3. **Certifications editor:** add/remove certifications. Save via `PUT /api/v1/org/certifications`. Respect Phase 101's `source` semantics — only `MANUAL`-source certs are user-editable; `SAM_ENTITY`-synced certs render read-only.

**No schema changes.** All endpoints already exist and already cover all required fields.

**Files to touch:**
- `ui/src/pages/organization/OrgSettingsTab.tsx` (add full-profile + NAICS-list + certs editable sections, or split into sub-tabs)
- `ui/src/pages/setup/NaicsCodesStep.tsx` (extract reusable NAICS list/editor logic — do not duplicate validation)
- `ui/src/queries/useOrganization.ts` (or the relevant query-hook module — add mutations for profile/NAICS/certs if not already present)
- `ui/src/api/*` org client + `ui/src/types/api.ts` (confirm `PUT /org/profile` exposes all fields above, and that `PUT /org/naics`/`PUT /org/certifications` methods exist; add if missing)
- No backend changes expected; verify `UpdateOrgProfileRequest`, NAICS, and certification DTOs expose the needed fields.

**Acceptance:**
- An owner/admin can view and edit the **full** org profile (identity, address, contact, business size) on the Organization page and save it via `PUT /api/v1/org/profile`.
- The org's **own** NAICS codes are shown as a full list with exactly one primary flagged, and are editable (add/remove/set-primary).
- Certifications are editable (MANUAL-source only; synced certs read-only).
- After entering `annual_revenue` for `org_id = 3`, the pWin **Size Eligibility** factor computes a real value (no longer "undeterminable") with no scorer code change.
- Non-admins see all of the above read-only.

---

### Unit B — Recommended: High-Confidence Clearance Filter, Hidden by Default + Toggle (P1)

**Goal:** Stop burying biddable opportunities under ones that require a security clearance the org cannot meet, while keeping them reachable on demand. **Critically: clearance-required opportunities must NEVER count toward the top-N (top 50), even when the toggle is ON.** The user's top 50 is always 50 biddable, non-clearance-required opportunities; clearance-required notices are at most an *additive* extra group, never a substitute for a top-N slot.

**What to build:**

1. **Aggregate clearance per notice** from `opportunity_attachment_summary` using the rule: a notice is **clearance-required (high confidence)** if **ANY** of its attachment summaries has `clearance_required = 'Y'` AND `overall_confidence = 'high'`. **Extend the existing batch-load** at `RecommendedOpportunityService.cs` lines 138–151 (which already groups `OpportunityAttachmentSummaries` by `NoticeId`) to also surface this flag — **do not add a separate query.**
2. **The top-N ranking cap is ALWAYS computed over the clearance-EXCLUDED candidate set.** Filter the clearance-required-high-confidence notices out of the scored candidate list **BEFORE** the `OrderByDescending(s => s.Score).Take(limit)` top-N cap (the cap at `RecommendedOpportunityService.GetRecommendedAsync`, lines ~280–284). This holds **regardless of the toggle state** — the toggle never widens the pool the top-N is drawn from. The top 50 are always the 50 best **non-clearance-required** opportunities.
3. **Default behavior (toggle OFF):** clearance-required notices are hidden entirely — not in the top-N, not shown anywhere.
4. **Toggle ON (`includeClearanceRequired = true`):** the high-confidence clearance-required notices are returned as a **SEPARATE / appended group**, visually distinct from the top-N (e.g. its own section/heading or clearly-grouped rows, each with a "Clearance required" badge). This group is **purely additive**: it does **NOT** consume, displace, or push out any of the top-N non-clearance slots. The two sets **never compete for the same slots** — the top-N is selected/capped from the clearance-excluded set, and the clearance group is selected/capped **separately**. (If the clearance group itself needs a bound, cap it with its own independent limit; it does not draw from the top-N `limit`.)
5. **Add the `includeClearanceRequired` toggle/param** (service method signature on `GetRecommendedAsync` + endpoint query param). When true, populate the separate clearance group in addition to the unchanged top-N; when false (default), omit it.
6. **Surface a "Clearance required" badge** on the clearance-group cards/rows (with the detected `clearance_level`/`clearance_scope` if available, for context).
7. **Apply the same clearance exclusion in both OQS code paths** if `CalculateOqScoreAsync` participates in the listing path; at minimum the listing/candidate path that feeds the top-N cap must exclude clearance-required notices from the ranked set.

> **Implementation note:** In `RecommendedOpportunityService.GetRecommendedAsync`, partition the scored candidates by the aggregated clearance flag **before** the top-N cap at lines ~280–284. Run `OrderByDescending(s => s.Score).Take(limit)` over **only the non-clearance-required** partition to produce the top-N. The clearance-required partition is selected/capped on its own (only when `includeClearanceRequired` is true) so the two paths never share or contend for the `limit` slots.

> **Caveat to document in code + UI (unchanged):** only document-analyzed opportunities can be flagged. Un-analyzed opportunities are never excluded by this filter and never appear in the clearance group (we cannot know their clearance requirement).

**No schema changes.**

**Files to touch:**
- `api/src/FedProspector.Infrastructure/Services/RecommendedOpportunityService.cs` (extend intel batch-load lines 138–151; add exclusion + `includeClearanceRequired` param; populate clearance fields on the DTO)
- `api/src/FedProspector.Api/Controllers/` Recommended controller (add `includeClearanceRequired` query param)
- `api/src/FedProspector.Core/DTOs/...RecommendedOpportunityDto` (add `ClearanceRequired` bool + optional `ClearanceLevel`/`ClearanceScope`)
- `ui/src/pages/recommendations/RecommendedOpportunitiesPage.tsx` (toggle control + "Clearance required" badge)
- `ui/src/api/*` and `ui/src/types/api.ts` (wire the new param + DTO fields)

**Acceptance:**
- **The top-N (top 50) is ALWAYS 50 biddable, non-clearance-required opportunities** — the clearance-required-high-confidence set is filtered out before the `OrderByDescending/Take(limit)` cap, so it never occupies, displaces, or pushes out a top-N slot, **in either toggle state**.
- By default (toggle OFF), Recommended hides notices flagged clearance-required-high-confidence entirely (not shown anywhere).
- With the toggle ON, those notices appear as a **separate, appended group** (visually distinct, each marked with a "Clearance required" badge) that is purely **additive** — the top-N non-clearance list is byte-for-byte identical to the toggle-OFF top-N; only the extra clearance group is added.
- Flipping the toggle never changes which opportunities are in the top-N, nor their order; it only shows/hides the separate clearance group.
- Un-analyzed opportunities are unaffected by the toggle and never appear in the clearance group (documented behavior).

---

### Unit C — Recommended: Separate Ungated "Market Research" Section (P1)

**Goal:** Stop scoring/ranking RFI-style market-research notices like biddable solicitations, and stop them from consuming top-N slots. Give them their own home where win probability is irrelevant.

**What to build:**

1. A dedicated **Market Research** list/section showing **ALL** notices of type **"Sources Sought"** and **"Special Notice"** that match the org's NAICS + cert profile.
2. This section is **NOT score-ranked** and **NOT capped at top-N** — use a much higher cap or proper pagination. Win probability/OQS is not shown for these (or is clearly marked N/A).
3. Likely a **new service method + endpoint** (e.g., `GetMarketResearchAsync`) and a **UI section or tab** on the Recommended page. Reuse the existing candidate-matching predicates (NAICS exact match, set-aside cert hard filter, active, deadline) but **without** the OQS scoring/top-N machinery.

> See Open Questions re: whether to also include **"Presolicitation"** in this section.

**No schema changes.**

**Files to touch:**
- `api/src/FedProspector.Infrastructure/Services/RecommendedOpportunityService.cs` (new `GetMarketResearchAsync` method, or a sibling service) — reuse NAICS/cert/active/deadline predicates; sort by `posted_date`/deadline, not score; paginate
- `api/src/FedProspector.Api/Controllers/` Recommended controller (new endpoint, e.g. `GET /recommended/market-research`)
- `api/src/FedProspector.Core/DTOs/...` (lightweight market-research DTO — no OQS fields required)
- `ui/src/pages/recommendations/RecommendedOpportunitiesPage.tsx` (new section/tab with pagination)
- `ui/src/api/*` + `ui/src/types/api.ts`

**Acceptance:**
- A separate Market Research section lists Sources Sought + Special Notice matching the org profile, paginated/uncapped, with no misleading win score.
- The main score-ranked Recommended list no longer competes with these notices for top-N slots.

---

### Unit D — Score Renormalization Over Present Factors Only (P2)

**Goal:** Stop thin-history orgs from being penalized by factors that have no real data. Rank by the factors that actually have signal.

**What to change** — in **BOTH** code paths in `RecommendedOpportunityService` (OQS at **line 233** and the duplicate at **line 441**) **and** `PWinService` (totalScore at **line 221**):

1. Compute the weighted score over **ONLY** factors where `HadRealData == true`, **dividing by the sum of those factors' weights** (renormalize so present factors sum to 1.0). i.e. `score = Σ(weightedScore where HadRealData) / Σ(weight where HadRealData)`, scaled to the same 0–100 range.
2. **Zero-real-data behavior:** when **no** factor has real data, return a **null score / "insufficient data"** indicator rather than a misleading number. Define and document this explicitly (the DTO must be able to represent "no score"). Such items should sort last / be visually flagged, not ranked as if scored.
3. **Keep showing** the confidence / data-completeness indicator (`realDataCount`, `confidence`, `dataCompletenessPercent`) so users can see how much of the score is backed by real data.

> **App-wide impact note:** This changes **displayed** OQS and pWin scores everywhere they appear (Recommended list, dashboard widget, Qualification & pWin tab, lazy-loaded grid scores from Phase 104B). Call this out in the PR/testing. Per CLAUDE.md, `RecommendedOpportunityService` and `PWinService` both feed multiple consumers — verify the grid/dashboard render correctly with a possibly-null score.

**No schema changes.**

**Files to touch:**
- `api/src/FedProspector.Infrastructure/Services/RecommendedOpportunityService.cs` (lines 233 and 441 — both OQS computations; null-score handling in both `RecommendedOpportunityDto` returns)
- `api/src/FedProspector.Infrastructure/Services/PWinService.cs` (line 221; null-score handling; `WinProbability` write at ~line 238 must tolerate null)
- DTOs that carry the score (`RecommendedOpportunityDto`, pWin DTO) — allow nullable score + an "insufficient data" flag
- UI score renderers (Recommended grid, dashboard "Top Recommendations" widget, `QualificationPWinTab.tsx`, lazy grid score cell) — render the null/insufficient-data state gracefully

**Acceptance:**
- For a thin-history org, ranking is driven by factors with real data (Profile Match, Competition Level, Timeline Feasibility) and **not** dragged down by defaulted Reuse/Growth/Re-compete/Value factors.
- An opportunity with zero real-data factors shows "insufficient data," not a numeric score, and does not outrank genuinely-scored items.
- Confidence/data-completeness indicators still display.

---

### Unit E — NAICS-Hierarchy Relatedness for Past Performance (P3 — OPTIONAL / DEFERRED)

> **The user deprioritized this. Do not start it as part of the P1/P2 work. It is documented here so the hook points and approach are captured for later.**

> **Relationship to Unit G (associated NAICS):** Unit E is the **automatic, hierarchy-derived** relatedness layer (same subsector/industry-group codes get partial, labeled credit). Unit G is the **manual, user-prioritized** associated-NAICS list. They are **complementary**, not duplicates: Unit G (P1) lets the user explicitly declare codes they consider relevant and have them feed matching now; Unit E (P3/optional) would later add automatic partial credit for hierarchy-adjacent codes. Build Unit G regardless of whether Unit E is ever undertaken.

**Goal:** Give **partial** past-performance / NAICS-experience credit for work in *related* NAICS codes (same industry group/subsector), instead of only crediting **exact** NAICS matches. Exact match always remains **full** credit; related matches are **partial** and **always labeled** as such.

**NAICS hierarchy is real and verified:** `ref_naics_code` has `parent_code`, `code_level` (1–5), `level_name`. Chain example: `54 → 541 → 5416 → 54161 → 541611 / 541612 / 541618`. An existing hierarchy API already uses `parent_code` (`ReferenceController` `naics/sectors|children|ancestors` via `CompanyProfileService`).

**Approach (follow existing precompute precedent — do NOT scan 28M rows per request):**

1. New precomputed table **`ref_naics_related`** (`anchor_naics`, `related_naics`, `weight`, `source`), seeded from `ref_naics_code` hierarchy tiers:
   - exact = **1.0**
   - same 5-digit ≈ **0.7**
   - same 4-digit ≈ **0.5**
   - same 3-digit ≈ **0.25**
2. Optional per-org summary **`org_naics_footprint`** (org's NAICS presence rolled up for fast lookup).
3. Refresh both via a **CLI command wired into the daily load**, mirroring the `usaspending_award_summary` precedent (`fed_prospector/db/schema/tables/usaspending_award_summary.sql`, refreshed during daily load). Migrations must be **manual + idempotent + applied to BOTH dev and prod** (CLAUDE.md). **No unnecessary FKs** (project convention).

**Exact-match hook points to convert to partial credit (always labeled; exact stays full):**
- `QualificationService.CheckPastPerformanceAsync` — lines **254** and **262** (currently `NaicsCode == naicsCode`)
- `PWinService.ScoreNaicsExperienceCachedAsync` — lines **293** and **301** (currently `NaicsCode == naicsCode`)
- The Profile Match factor in `RecommendedOpportunityService` (`ScoreProfileMatch`, in the factor methods at lines 599–752)
- The SQL view `v_past_performance_relevance` in `fed_prospector/db/schema/migrations/115f_onboarding_past_performance.sql` (~lines 254, 278)

**Data-source fix to bundle here (known issue, see below):** when touching past-performance matching, switch the authoritative vendor-history read from `fpds_contract` (~225K rows, sparse) to `usaspending_award` (28.7M rows) per CLAUDE.md — via a precomputed summary, not a per-request scan.

**Files to touch (when undertaken):**
- `fed_prospector/db/schema/tables/ref_naics_related.sql` (new), optional `org_naics_footprint.sql` (new)
- `fed_prospector/db/schema/migrations/<NNN>_naics_relatedness.sql` (new — manual, idempotent, dev + prod)
- New CLI command (e.g., `refresh naics-relatedness`) + wire into `job daily`
- `api/src/FedProspector.Infrastructure/Services/QualificationService.cs`, `PWinService.cs`, `RecommendedOpportunityService.cs`
- `fed_prospector/db/schema/migrations/115f_onboarding_past_performance.sql` (view update)

**Acceptance (when undertaken):** related-NAICS past performance contributes partial, clearly-labeled credit; exact match still scores full; precompute refresh runs in the daily load; no 28M-row per-request scans.

---

### Unit F — Linked-Entity Data Editing: Primary NAICS Shown + Revenue/Employees Editable Anytime (P1)

**Goal:** Satisfy user requirements #3 and #5 — show each linked entity's **primary NAICS** in the entities list (today it shows only a count), and make each linked entity's **employees and revenue editable at ANY time**, not only when the link is created.

**What to build:**

1. **Show each linked entity's primary NAICS (requirement #3).** In `OrgEntitiesTab.tsx`, replace/augment the NAICS **count** column (`link.naicsCount`, ~lines 396–397) so each row also shows the entity's **primary NAICS** (the `entity_naics` row where `is_primary = 'Y'`). Ideally make it **expandable to all of that entity's NAICS**. Add a `primaryNaics` field to the entities DTO (`OrganizationEntityDto.cs`) and populate it in `OrganizationEntityService` (alongside where `NaicsCount` is set, lines 47 and 469) by selecting the `is_primary = 'Y'` code (string Y/N per `EntityNaics.IsPrimary`).
2. **Edit affiliate employees + revenue anytime (requirement #5).** Add a **dedicated** `PUT /api/v1/org/entities/{linkId}` endpoint that updates `affiliate_annual_revenue` and `affiliate_employee_count` (and, while we're there, the editable link fields `relationship`, `mpa_approved`, `mpa_effective_date`, `notes`, `partner_uei`) on an existing link, **owner/admin gated** (`[Authorize(Policy = "OrgAdmin")]`, matching the other entity mutations). **Explicitly:** this MUST be usable at any time after the link exists — it is decoupled from the link/upsert action, so financials are no longer write-once. **No schema change** — `OrganizationEntity` already has `AffiliateAnnualRevenue`/`AffiliateEmployeeCount` (lines 42/45) and the rest of these columns. Wire a small per-row inline edit (or an "Edit" dialog) in `OrgEntitiesTab.tsx`.
3. Editing affiliate revenue/employees here feeds the Phase 133 affiliation **size roll-up** (`CompanyProfileService.CheckSizeEligibilityWithAffiliatesAsync` reads `AffiliateAnnualRevenue`/`AffiliateEmployeeCount` at lines 531–532 / 625–626), so corrected values immediately improve the affiliation-aware size verdict — with no scorer change.

> **Why a new endpoint rather than reusing `POST /api/v1/org/entities`:** the upsert path is keyed to the link/reactivate action and re-runs cert/NAICS sync; using it just to fix a revenue number is awkward and surprising. A clean `PUT .../entities/{linkId}` makes "edit this affiliate's data" a first-class, anytime operation.

**No schema changes** (adds an endpoint only; columns already exist).

**Files to touch:**
- `api/src/FedProspector.Api/Controllers/OrganizationController.cs` (add `PUT entities/{linkId}`, `[Authorize(Policy = "OrgAdmin")]`)
- `api/src/FedProspector.Infrastructure/Services/OrganizationEntityService.cs` (add an update method; populate `primaryNaics` on the DTO at the spots where `NaicsCount` is set — lines 47 and 469)
- `api/src/FedProspector.Core/DTOs/Organizations/OrganizationEntityDto.cs` (add `PrimaryNaics`; add/confirm an update-request DTO with the editable fields)
- `ui/src/pages/organization/OrgEntitiesTab.tsx` (show primary NAICS — ideally expandable to all; inline/dialog edit of revenue/employees + link fields)
- `ui/src/api/*` + `ui/src/types/api.ts` (wire the new `PUT entities/{linkId}` and the `primaryNaics` field)

**Acceptance:**
- The entities list shows each linked entity's **primary NAICS** (not just a count); ideally the row expands to all of that entity's NAICS.
- An owner/admin can edit any linked entity's **revenue and employee count at any time** (post-link, not only at creation) via `PUT /api/v1/org/entities/{linkId}`, and the affiliation size roll-up reflects the new values.
- Non-admins see the entity data read-only.

---

### Unit G — Associated NAICS: Manual, User-Prioritized List That Feeds Matching/Scoring (P1)

**Goal:** Satisfy user requirement #4 — a manually-curated list of **"associated" NAICS** codes the org declares relevant **beyond** their registered NAICS and **beyond** linked-entity NAICS, that **"gets included in things"** (recommendations/matching). This is genuinely new — no table or code exists today.

**What to build:**

1. **New table `organization_associated_naics`** — columns: `organization_id` (int), `naics_code` (the 6-digit code), optional `note` (varchar/text), `created_at` (datetime). Keep it simple; a unique key on `(organization_id, naics_code)` to prevent dupes. **No unnecessary FKs** (project convention) — `organization_id` references the org logically without a hard FK. Migration must be **manual, idempotent, and applied to BOTH dev (`127.0.0.1`) and prod (`192.168.0.137`)** per CLAUDE.md (DDL file + a hand-applied `migrations/<NNN>_associated_naics.sql`; this is a new ETL/reference-style table, so Python DDL ownership applies).
2. **CRUD endpoints** under `/api/v1/org/associated-naics` (owner/admin gated for writes): `GET` to list, and either `PUT` (full-replace, mirroring the org-NAICS `SetNaicsAsync` pattern) or `POST`/`DELETE` for add/remove. Pick the full-replace `PUT` for consistency with the rest of the org-NAICS editing UX unless add/remove is clearly simpler.
3. **Editor on the Organization page** — a section (next to the own-NAICS list from Unit A) to add/remove associated codes with an optional note. Validate 6-digit codes / dedup, and **disallow codes already in the org's own registered NAICS** (or just de-dup against them when building match sets) so the two lists stay meaningfully distinct.
4. **"Included in things" — wire associated NAICS into matching/scoring:**
   - **Recommended candidate selection:** expand the NAICS set used at `RecommendedOpportunityService.GetRecommendedAsync` **line 87** (`naicsCodes.Contains(o.NaicsCode!)`) so opportunities whose `NaicsCode` is in **(registered ∪ associated)** also surface as candidates.
   - **Other org-NAICS-driven matching/search** where appropriate (e.g., anywhere the org's NAICS set is used to find/flag relevant opportunities) should likewise consider the associated set. Audit call sites that build the org NAICS list.
   - **In scoring (Profile Match / pWin):** associated NAICS should be a **clearly-LABELED, distinct tier** — an opportunity matched via an *associated* code (rather than a *registered* code) must be transparently marked as such in the UI, not silently treated as a full registered match. Do **not** let associated matches masquerade as registered ones. (How heavily they should count is an Open Question below.)
5. **Relationship to Unit E:** this manual list (Unit G, P1) is the user-prioritized layer; Unit E (P3/optional) is the automatic hierarchy-derived layer. They are complementary and can coexist — associated (manual) and related (hierarchy) can each be their own labeled tier.

**Schema change: YES** — one new table (manual, idempotent, dev + prod).

**Files to touch:**
- `fed_prospector/db/schema/tables/<NN>_organization_associated_naics.sql` (new DDL)
- `fed_prospector/db/schema/migrations/<NNN>_associated_naics.sql` (new — manual, idempotent, dev + prod)
- EF Core model + DbContext for the new table if it is read via EF in the API (`api/src/FedProspector.Core/Models/`, `api/src/FedProspector.Infrastructure/Data/`); use `[Column]` attributes for any digit-letter names per project convention
- `api/src/FedProspector.Api/Controllers/OrganizationController.cs` (associated-NAICS CRUD endpoints, OrgAdmin-gated writes)
- `api/src/FedProspector.Infrastructure/Services/` (associated-NAICS read/write; merge associated codes into the org NAICS set used by `RecommendedOpportunityService` line 87 and other match sites)
- `api/src/FedProspector.Core/DTOs/...` (associated-NAICS DTO; add a "matched via associated NAICS" label/tier to the Recommended/pWin DTOs)
- `ui/src/pages/organization/OrgSettingsTab.tsx` (associated-NAICS editor)
- `ui/src/pages/recommendations/RecommendedOpportunitiesPage.tsx` + score/qualification views (show the associated-tier label)
- `ui/src/api/*` + `ui/src/types/api.ts`

**Acceptance:**
- An owner/admin can add/remove associated NAICS codes (with optional notes) on the Organization page; the list persists in `organization_associated_naics` (dev + prod).
- Opportunities whose NAICS is in the associated list (but not the registered list) **now surface** in Recommended candidate selection (line 87 set expanded).
- Where an opportunity is matched via an associated code, the UI **labels** it as an associated-tier match, distinct from registered-NAICS matches.
- Associated and registered lists are kept distinct (no silent merging that hides which list drove a match).

---

## Cross-Cutting Notes

- **Migrations:** Units **A, B, C, D, and F need NO schema changes** — all the columns and entity properties already exist (Unit F **adds an endpoint only**; the affiliate revenue/employee/NAICS columns are already present). **Unit G adds one new table** (`organization_associated_naics`) and **Unit E** adds tables; both sets of migrations must be **manual, idempotent, and applied to BOTH dev (`127.0.0.1`) and prod (`192.168.0.137`)** per CLAUDE.md, with **no unnecessary FKs**.
- **Keep the set-aside cert hard-filter as-is** (`RecommendedOpportunityService.cs` lines 177–182) — it is correct; this phase does not touch it.
- **Both OQS code paths change together** for Unit D (lines 233 and 441). Forgetting one yields inconsistent scores between the list path and the single-score path.
- **Score change has app-wide blast radius** (Unit D): Recommended list, dashboard widget, Qualification & pWin tab, and Phase 104B lazy grid scores all read these services.
- **Clearance filter is best-effort** (Unit B): only analyzed opps carry the signal — say so in the UI.
- **Clearance never competes for top-N slots** (Unit B): the top-N (top 50) is always computed over the clearance-excluded set; with the toggle ON, clearance-required notices are an *additive* separate group, not a replacement for any top-N slot.

## Files-to-Touch Summary

| Unit | Backend | Frontend | DDL/Migration |
|------|---------|----------|---------------|
| A | (none — verify full-profile/NAICS/cert DTOs) | `OrgSettingsTab.tsx`, `NaicsCodesStep.tsx` (extract), org query/api modules | none |
| B | `RecommendedOpportunityService.cs` (138–151), Recommended controller, `RecommendedOpportunityDto` | `RecommendedOpportunitiesPage.tsx`, `api.ts` | none |
| C | `RecommendedOpportunityService.cs` (new method), Recommended controller, new DTO | `RecommendedOpportunitiesPage.tsx`, `api.ts` | none |
| D | `RecommendedOpportunityService.cs` (233, 441), `PWinService.cs` (221), score DTOs | score renderers (grid, dashboard, pWin tab) | none |
| E | `QualificationService.cs` (254, 262), `PWinService.cs` (293, 301), `RecommendedOpportunityService.cs` (599–752), CLI | (optional surfacing of partial-credit labels) | `ref_naics_related`, `org_naics_footprint`, view update — manual/idempotent/dev+prod |
| F | `OrganizationController.cs` (new `PUT entities/{linkId}`), `OrganizationEntityService.cs` (update method; `primaryNaics` at 47/469), `OrganizationEntityDto.cs` | `OrgEntitiesTab.tsx` (show primary NAICS; edit revenue/employees), `api.ts` | none (endpoint only) |
| G | new DDL/model/DbContext, `OrganizationController.cs` (associated-NAICS CRUD), service (merge into match set; `RecommendedOpportunityService.cs` line 87), DTOs (associated-tier label) | `OrgSettingsTab.tsx` (editor), `RecommendedOpportunitiesPage.tsx`/score views (tier label), `api.ts` | `organization_associated_naics` — manual/idempotent/dev+prod, no FK |

---

## Open Questions

1. **Presolicitation in Market Research (Unit C)?** Sources Sought + Special Notice are clearly market-research. **Presolicitation (8,651 rows)** is ambiguous — it can precede a real solicitation. Include it in the Market Research section, leave it in the score-ranked list, or show it in both? **Needs a decision before building Unit C.**
2. **Clearance toggle default (Unit B):** confirmed = **hidden by default**, with an opt-in toggle. (Recorded for the record; no further input needed unless changed.)
3. **Scope of the clearance filter:** should the high-confidence clearance filter also apply to the **main Opportunities search** (`/opportunities`), or **only** to Recommended? This phase scopes it to Recommended; extending to search is a follow-up if desired.
4. **Associated-NAICS scoring weight (Unit G):** how heavily should an **associated** NAICS match count in scoring relative to a **registered** NAICS match — **full weight** (treat associated as equivalent for ranking, just labeled), or a **reduced/labeled** weight (surfaces the opportunity but scores the match lower so registered matches still rank ahead)? Either way it must be a transparently labeled tier. **Needs a decision before wiring Unit G into scoring** (candidate *selection* expansion at line 87 is independent of this and can proceed regardless).

---

## Known Issues (record per CLAUDE.md)

- **Past-performance / NAICS-experience scoring reads `fpds_contract` (~225K rows, sparse) and manual `organization_past_performance`, NOT the authoritative `usaspending_award` (28.7M rows).** CLAUDE.md mandates `usaspending_award` as the authoritative vendor-history source and forbids substituting `fpds_contract` for analytics. Fix this when touching past-performance matching (bundled into Unit E), via a precomputed summary refreshed during the daily load — never a per-request 28M-row scan.
- **Clearance signal coverage is partial:** only document-analyzed opportunities have `opportunity_attachment_summary` rows, so Unit B's filter cannot flag un-analyzed opportunities. This is a coverage limitation, not a bug; surface it in the UI.

## Scope Boundaries

**In scope:** Full org-profile editability (identity/address/contact/business size), own-NAICS list+editor, certifications (Unit A); high-confidence clearance hide-by-default + toggle on Recommended (Unit B); a separate ungated Market Research section (Unit C); score renormalization over present factors in OQS + pWin (Unit D); linked-entity primary-NAICS display + anytime editing of affiliate revenue/employees via a new `PUT /entities/{linkId}` (Unit F); manual associated-NAICS list with a new table, CRUD, and merge into Recommended candidate selection + labeled scoring tier (Unit G).

**Out of scope (this phase):** NAICS-relatedness *automatic* partial credit and the `fpds_contract → usaspending_award` data-source fix (captured as **Unit E**, deferred — distinct from the manual associated-NAICS list in Unit G); extending the clearance filter to the main Opportunities search (open question 3); any change to the set-aside cert hard-filter; ETL/loader changes (beyond the new `organization_associated_naics` DDL/migration for Unit G).
