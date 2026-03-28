# Phase 300: Comprehensive Project Review & Technical Debt Registry

**Status:** IN REVIEW
**Review date:** 2026-03-28 (Round 1) / 2026-03-28 (Round 2)
**Verification date:** 2026-03-28 — findings cross-checked against live codebase; 6 items reclassified or dismissed
**Scope:** Full codebase audit — App API, DB/ETL, UI, Docs, Phase Docs
**Priority:** High — captures untracked issues found during full project review
**Architecture note:** Single-user / single-org application. Multi-tenancy exists in code but is not a commercial deployment concern. All org-isolation findings are DEFERRED.

## Motivation

Two rounds of cross-layer audit using parallel code review agents covering all major subsystems. Round 1 surveyed every layer for issues not already tracked by Phase 120/150/200. Round 2 focused specifically on **usability, data accuracy, efficiency, and usefulness** for actual BD/capture workflows. This document is a living technical debt registry — findings that are not addressed here should be promoted to sub-phases.

---

## Deferred Findings (Single-Org — Not Worth Fixing)

These were flagged in Round 1 but are moot for single-user deployment:

| # | Finding | Reason Deferred |
|---|---------|----------------|
| D1 | `SubawardsController` has no org isolation | Single org — isolation irrelevant |
| D2 | `AdminController.GetUsers` fails for system admins with no `org_id` claim | Only one admin; no system-admin role needed |
| D3 | CORS falls back to `localhost:5173` silently in production | Single-user local deployment |
| D4 | In-memory registration rate limiter (`ConcurrentDictionary`) | Not a multi-user attack surface |
| D5 | EF Core `Migrations/` folder empty — schema non-reproducible | DB is always local; not reproducing from scratch |

---

## Verified Non-Issues (dismissed after code verification, 2026-03-28)

| # | Original Finding | Verdict | Explanation |
|---|-----------------|---------|-------------|
| DA-H4 | Opportunity hash doesn't include `active` field | **BOGUS** | The `active` field IS in `_OPPORTUNITY_HASH_FIELDS` at line 32 of `opportunity_loader.py`. Hash correctly detects active/inactive transitions. Original finding was factually wrong. |
| H2 | No integration/service-layer tests for `ProposalService`, `OpportunityService`, `AuthService` | **ALREADY FIXED** | Tests exist at `api/tests/FedProspector.Infrastructure.Tests/Services/ProposalServiceTests.cs`, `OpportunityServiceTests.cs`, and `AuthServiceTests.cs`. Finding was stale. |
| DA-M3 | No data freshness indicator in UI — `last_loaded_at` not exposed via API | **ALREADY FIXED** | The `/health` endpoint exposes ETL freshness data per source via `CheckEtlFreshnessAsync()` in `HealthController.cs`. Data freshness is available in the UI health check. |
| M8 | `ai_usage_log.cost_usd` is `DECIMAL(10,6)` vs other monetary columns at `DECIMAL(15,2)` | **NOT INCONSISTENT** | `DECIMAL(10,6)` is intentionally correct for AI API costs which are fractions of a cent per call (e.g., $0.000375 per request). This is a different domain than contract dollar amounts and requires sub-cent precision. Not a bug or inconsistency. |

---

## Round 1 Findings — Code Quality & Infrastructure

*Issues not tracked by Phase 120/150/200 and applicable to single-org deployment.*

### CRITICAL

| # | Layer | Issue | File(s) |
|---|-------|-------|---------|
| C1 | App API | `ProposalService.AddDocumentAsync` stores `""` as `FilePath` — proposals tracked in DB but file bytes are never written to disk | `api/src/FedProspector.Infrastructure/Services/ProposalService.cs` |

**Recommended fix — C1:** Requires infrastructure decision (local disk path vs. S3/Azure Blob). Add `IFileStorageService` abstraction before proposals feature is used.

### HIGH

| # | Layer | Issue | File(s) |
|---|-------|-------|---------|
| H1 | App API | Missing `GET /api/v1/proposals/{id}` endpoint — standard CRUD gap | `api/src/FedProspector.Api/Controllers/ProposalsController.cs` |
| H3 | DB/ETL | No retry logic for transient MySQL errors (errno 2006, 2013) — all DB calls fail immediately on connection drops | `fed_prospector/db/connection.py` |

**Recommended fix — H1:** Add `[HttpGet("{id:int}")]` action calling `ProposalService.GetByIdAsync(id, organizationId)`.

**Recommended fix — H3:** Wrap `get_connection()` with exponential backoff retry for errno 2006/2013 (max 3 attempts, 1s/2s/4s delays).

### MEDIUM

| # | Layer | Issue | File(s) |
|---|-------|-------|---------|
| M1 | App API | Three inconsistent error response formats: `ApiError()`, `{error:...}`, `{message:...}` | Multiple controllers |
| M2 | App API | Missing `DELETE /api/v1/proposals/{id}` and `DELETE /api/v1/proposals/{id}/milestones/{milestoneId}` | `ProposalsController.cs` |
| M3 | App API | No pagination validation — `Page < 1` causes negative `.Skip()`, `PageSize = 0` returns empty | Multiple services |
| M4 | App API | Hardcoded `"Y"`/`"N"` string flags throughout all services — typo-prone, no constants | All service files |
| M5 | App API | `ForcePasswordChangeMiddleware` uses fragile exact-string path matching — breaks silently on route renames | `api/src/FedProspector.Api/Middleware/ForcePasswordChangeMiddleware.cs` |
| M6 | App API | `AuthController.Login` returns anonymous object, not a typed `LoginResponseDto` | `api/src/FedProspector.Api/Controllers/AuthController.cs:57` |
| M7 | DB/ETL | No migration version control table — no audit trail for which SQL migrations have run | `fed_prospector/db/schema/migrations/` |
| M9 | DB/ETL | Set-aside codes hardcoded in `v_target_opportunities` view — not driven by org profile | `fed_prospector/db/schema/views/10_target_opportunities.sql:45` |
| M10 | DB/ETL | `etl_data_quality_rule` DB framework underutilized — `_apply_db_rule()` completeness unverified | `fed_prospector/etl/data_cleaner.py:163-200` |
| M11 | UI | `requestAnalysis()` builds URL via string interpolation instead of `params` object — inconsistent with all other API calls | `ui/src/api/opportunities.ts:~99` |
| M12 | UI | `SET_ASIDE_COLORS` maps `"8(A)"` and `"8A"` separately — case normalization missing | `ui/src/utils/constants.ts:60-71` |

### LOW / TECH DEBT

| # | Layer | Issue | File(s) |
|---|-------|-------|---------|
| L1 | App API | Several controllers return anonymous objects for success messages instead of typed DTOs | Multiple controllers |
| L2 | DB/ETL | `datetime.now()` used everywhere — timezone-naive, no documented UTC strategy | ETL loaders, `load_manager.py` |
| L3 | DB/ETL | Batch sizes hardcoded per loader class — not config-driven | `entity_loader.py`, `opportunity_loader.py`, `usaspending_bulk_loader.py` |
| L4 | DB/ETL | Logger inconsistency — some loaders use module-level `logger`, others use `self.logger` | `awards_loader.py:22 vs 97`, `entity_loader.py:84` |
| L5 | DB/ETL | No checkpoint resumption for entity/opportunity/awards loaders — only USASpending supports this | Multiple loaders |
| L6 | DB/ETL | No data archiving strategy for soft-deleted `usaspending_award` rows — unbounded growth over time | Schema design gap |
| L7 | Docs | `thesolution/reference/04-DATA-OVERLAP-AND-LIMITS.md` is stale — record counts outdated | `thesolution/reference/04-DATA-OVERLAP-AND-LIMITS.md` |
| L8 | Docs | `thesolution/reference/08-DATA-QUALITY-ISSUES.md` is minimal — no remediation tracking | `thesolution/reference/08-DATA-QUALITY-ISSUES.md` |
| L9 | Docs | No ETL troubleshooting guide exists for ops | Gap |

---

## Round 2 Findings — Usability, Data Accuracy, Efficiency, Usefulness

### DATA ACCURACY

#### Critical

| # | Issue | File(s) |
|---|-------|---------|
| DA-C1 | **Incumbent data always NULL in opportunity table** — `incumbent_uei`/`incumbent_name` never populated by opportunity_loader (columns reserved, not in API response). pWin falls back to FPDS solicitation_number lookup, which frequently returns wrong or outdated contractor. The 15% weight for incumbent advantage in pWin is often garbage. | `fed_prospector/db/schema/tables/30_opportunity.sql:29-30`; `api/src/FedProspector.Infrastructure/Services/PWinService.cs:324-346` |
| DA-C2 | **Set-aside cert mapping inconsistent between services** — `PWinService` maps `"SBA"` → `["8(a)", "WOSB", "EDWOSB", "HUBZone", "SDVOSB"]`; `QualificationService` maps `"SBA"` → `["SDB"]` only. Users see different eligibility results on the same screen. `"SBP"` is missing from QualificationService entirely (KeyNotFoundException risk). | `api/src/FedProspector.Infrastructure/Services/PWinService.cs:18-32`; `api/src/FedProspector.Infrastructure/Services/QualificationService.cs:18-32` |

**Fix DA-C1:** Document this limitation prominently. Remove the FPDS solicitation_number fallback or add a confidence flag so users know the incumbent guess is unreliable. Consider letting the user manually set the incumbent.

**Fix DA-C2:** Extract set-aside → certification mapping into a single shared constant/class. Both services import from it. Add `"SBP"` mapping.

#### High

| # | Issue | File(s) |
|---|-------|---------|
| DA-H1 | **Response deadline timezone mismatch** — loader converts SAM.gov ISO 8601 deadlines to UTC correctly, but view `DATEDIFF(o.response_deadline, NOW())` uses DB server local time (may not be UTC). Opportunities can appear or disappear from "open" lists at wrong times. | `fed_prospector/db/schema/views/10_target_opportunities.sql:16`; `fed_prospector/etl/opportunity_loader.py` |
| DA-H3 | **AI-extracted fields have no enum validation** — `clearance_required`, `eval_method`, `vehicle_type` go straight to DB. If Claude returns `"MAYBE"` instead of a valid enum, it's stored as-is. No validation, no rejection, no warning to user. | `fed_prospector/etl/attachment_ai_analyzer.py:436-451` |

**Fix DA-H1:** Use `UTC_TIMESTAMP()` instead of `NOW()` in views. Verify loader stores deadlines in UTC consistently.

**Fix DA-H3:** Add an enum validation step in `attachment_ai_analyzer.py` before DB write. Log and blank-out fields with invalid values.

#### Medium

| # | Issue | File(s) |
|---|-------|---------|
| DA-M1 | **Dedup loses amendment history for empty solicitation numbers** — `v_opportunity_latest` partitions on `COALESCE(NULLIF(solicitation_number,''), notice_id)`. Two copies of same opp with blank solicitation_number both appear; amendments where solicitation_number changes aren't correlated. | `fed_prospector/db/schema/views/05_opportunity_latest.sql:12-14` |
| DA-M4 | **FPDS data has 1-3 month reporting lag** — pWin uses `DateSigned >= threeYearsAgo` on FPDS contracts. Recent wins by org aren't counted in their NAICS experience score. New contract wins show up in the system months after signing. | `api/src/FedProspector.Infrastructure/Services/PWinService.cs:236-240` |

#### Low / Future Enhancements

| # | Issue | File(s) |
|---|-------|---------|
| DA-H2 | **pWin could evaluate additional real-world factors** — no check for GSA Schedule requirement, no location-vs-POP match, no OCI restrictions, no org-specific historical win rate against specific competitors. Nice-to-have enhancement; current model already evaluates 7 weighted factors (set-aside match 0.20, NAICS experience 0.20, competition level 0.15, incumbent advantage 0.15, teaming strength 0.10, time to respond 0.10, contract value fit 0.10) which is reasonably comprehensive. | `api/src/FedProspector.Infrastructure/Services/PWinService.cs` |
| DA-M2 | **Qualification NAICS check returns "Warning" only when opportunity has no NAICS code** — returns "Fail" (not "Warning") when the org lacks the NAICS, which is the correct behavior. The "Warning" for missing-NAICS-on-opportunity is also reasonable since the check cannot be evaluated. Behavior is actually correct; original description was inaccurate. | `api/src/FedProspector.Infrastructure/Services/QualificationService.cs:314-343` |

**DA-H2 note:** Consider adding more factors in a future iteration, but current 7-factor model is adequate for initial BD workflows. Document known limitations in pWin tooltip.

**DA-M2 note:** No code change needed. Original finding mischaracterized the behavior.

---

### USABILITY

#### Critical

| # | Issue | File(s) |
|---|-------|---------|
| UX-C1 | **"Save Search" button on Opportunity Search page is a placeholder** — shows `'Save Search will be available soon'` toast and does nothing. The `SaveSearchModal` component exists and works on the Saved Searches page, but isn't wired to the search form. | `ui/src/pages/opportunities/OpportunitySearchPage.tsx:278-282` |

**Fix UX-C1:** Wire `SaveSearchModal` to the existing button with the current filter state. This is a low-effort, high-value fix.

#### High

| # | Issue | File(s) |
|---|-------|---------|
| UX-H1 | **No pWin or qualification status in search results** — users must click into every opportunity detail to see fit. With 50-200 results per search, this is a major bottleneck for prospecting workflows. | `ui/src/pages/opportunities/OpportunitySearchPage.tsx` (results columns) |
| UX-H2 | **No multi-certification filter** — can't search "WOSB OR HUBZone" in one query. Users with multiple certifications must run multiple searches. | `ui/src/pages/opportunities/OpportunitySearchPage.tsx` (filter sidebar) |
| UX-H3 | **No confirmation dialogs for destructive pipeline actions** — declining a prospect, marking WON/LOST, or removing from pipeline has no "are you sure?" prompt. Single-click closes opportunities. | Prospect detail/pipeline pages |

**Fix UX-H1:** Add `qScore` and a pass/fail badge to the search results table columns. Use batch pWin endpoint to load scores for visible rows.

**Fix UX-H2:** Change set-aside filter from single-select to multi-select checkbox group.

**Fix UX-H3:** Wrap `LOST`, `DECLINED`, `WON` status transitions in `ConfirmDialog` calls (component exists at `ui/src/components/common/ConfirmDialog.tsx`).

#### Medium

| # | Issue | File(s) |
|---|-------|---------|
| UX-M1 | **Prospect pipeline cards lack pWin/qualification at-a-glance** — users can't prioritize work from the Kanban view without opening every card | `ui/src/pages/prospects/ProspectPipelinePage.tsx` |
| UX-M2 | **Dashboard shows only 5 recommendations, uncustomizable** — no filter, no refresh button, qScore shown without explanation | `ui/src/pages/dashboard/DashboardPage.tsx:272-327` |
| UX-M3 | **Teaming partner search is a raw entity database lookup** — no filters for certification, geography, past performance, or capacity | `ui/src/pages/subawards/TeamingPartnerPage.tsx` |
| UX-M4 | **Sidebar navigation terminology unclear to new users** — "Awards" (implies winners not contract listings), "Targets" (unclear distinction from Opportunities) | `ui/src/components/layout/Sidebar.tsx` |
| UX-M5 | **Activity Log tab in Organization settings is a stub "coming soon" page** | `ui/src/pages/organization/OrgActivityLogTab.tsx` |
| UX-M6 | **pWin/go-no-go score has no explanation** — users see a number (e.g., 65) with no context of what it means, what's "good", or what factors drove it | OpportunityDetailPage, ProspectDetailPage |

---

### EFFICIENCY

#### Medium

| # | Issue | File(s) |
|---|-------|---------|
| EF-M1 | **OpportunityService dedup uses inline `Max()` subquery per row** — executes a correlated subquery for every row in the filtered set. Should use `v_opportunity_latest` view or a window function. | `api/src/FedProspector.Infrastructure/Services/OpportunityService.cs:72-77` |
| EF-M2 | **Detail page likely triggers multiple sequential API calls** — incumbent, competitive landscape, and set-aside shift are separate endpoints that React may call one-by-one. Page load can be 1-2s slower than necessary. | `api/src/FedProspector.Api/Controllers/OpportunitiesController.cs:131,141,150` |

#### Low

| # | Issue | File(s) |
|---|-------|---------|
| EF-L1 | **PWinService batch runs sequentially** — `CalculateBatchAsync()` loops `CalculateAsync()` one at a time instead of using `Task.WhenAll()` with a semaphore | `api/src/FedProspector.Infrastructure/Services/PWinService.cs:135-161` |
| EF-L2 | **`RecommendedOpportunityService` pulls all matching opportunities before filtering** — for orgs with 10 NAICS codes, may pull 10K-50K rows to memory before scoring | `api/src/FedProspector.Infrastructure/Services/RecommendedOpportunityService.cs:83-119` |
| EF-L3 | **Batch pWin saves changes after each record** — should accumulate 20-30 updates then call `SaveChangesAsync()` once | `api/src/FedProspector.Infrastructure/Services/PWinService.cs:114-118` |

---

### MISSING HIGH-VALUE FEATURES (Usefulness)

These features don't exist but would meaningfully improve BD outcomes:

| # | Feature | Impact | Effort | Data Available? |
|---|---------|--------|--------|----------------|
| MF-1 | **Deadline alerts / email notifications** — auto-remind when prospect deadline is 14/7/3 days away | ⭐⭐⭐⭐⭐ | 2-3 days | ✅ Yes |
| MF-2 | **"Similar Contracts" search** — from any opportunity, find others with same NAICS/agency/set-aside/value range | ⭐⭐⭐⭐⭐ | 1-2 days | ✅ Yes |
| MF-3 | **Win rate analytics** — win/loss rate broken down by NAICS, agency, set-aside type; "which markets are we winning in?" | ⭐⭐⭐⭐⭐ | 1-2 days | ✅ Yes (prospect table has outcome) |
| MF-4 | **Lost deal root cause tracking** — when marking LOST, capture reason (price/technical/schedule/strategy) and competitor name | ⭐⭐⭐⭐ | 2-3 days | ✅ Add columns to prospect |
| MF-5 | **Set-aside trend visualization** — is WOSB spend growing or declining in my NAICS? Year-over-year comparison | ⭐⭐⭐⭐ | 1-2 days | ✅ Yes (`v_set_aside_trend` view exists) |
| MF-6 | **NAICS market analysis** — total federal spend by NAICS, top contractors, WOSB %, average award value | ⭐⭐⭐⭐ | 2-3 days | ✅ Yes (FPDS + USASpending data) |
| MF-7 | **Teaming partner finder with intelligence** — search by NAICS + past performance + geography + small-business cert, not just entity name | ⭐⭐⭐⭐ | 3-5 days | ✅ Partial (subaward data exists) |
| MF-8 | **Past performance scorecard** — org's own record: on-time delivery, quality, reference contacts for proposals | ⭐⭐⭐ | 2-3 days | ⚠️ Partial (FPDS data, needs manual input too) |

**MF-3 SQL sketch (win rate by segment):**
```sql
SELECT o.naics_code, o.set_aside_code, o.department_name,
  COUNT(*) AS bids,
  SUM(CASE WHEN p.status = 'WON' THEN 1 ELSE 0 END) AS wins,
  ROUND(100.0 * SUM(CASE WHEN p.status = 'WON' THEN 1 ELSE 0 END) / COUNT(*), 1) AS win_rate
FROM prospect p
JOIN opportunity o ON p.notice_id = o.notice_id
WHERE p.status IN ('WON', 'LOST')
GROUP BY o.naics_code, o.set_aside_code, o.department_name
ORDER BY win_rate DESC;
```

**MF-5 note:** `v_set_aside_trend` view already exists in `fed_prospector/db/schema/views/65_set_aside_trend.sql` — only the UI widget is missing.

---

## Already-Tracked Issues (confirmed still high priority)

| Finding | Tracked In |
|---------|-----------|
| MySQL 8.0.20+ `VALUES()` deprecation in `batch_upsert.py` (CRITICAL) | Phase 120 |
| USASpending bulk loader bugs U1–U5 (checkpoint, FY sentinel, resume stats, O(n²) dedup, null hash) | Phase 120 |
| `AllowedHosts: *` wildcard in production config | Phase 150 |
| JWT secret / token lifetime hardcoded | Phase 150 |
| MySQL `SslMode=None` in production | Phase 150 |
| SAM API key in query parameter | Phase 150 |
| Cookie `SameSite=Lax` | Phase 150 |
| Database schema normalization | Phase 200 |

---

## Relationship to Other Planned Phases

- **Phase 113 (Federal Hierarchy Browser):** UX-H1 (pWin in search results) and DA-C2 (set-aside mapping) should be fixed first — both affect how users evaluate results Phase 113 will surface.
- **Phase 124 (Attachment Hash Dedup):** Fix DA-H3 (AI field validation) in same pass as attachment pipeline work.

---

## Recommended Sub-Phases

| Sub-Phase | Cluster | Findings | Estimated Effort |
|-----------|---------|----------|-----------------|
| 300.1 | **Data Accuracy Fixes** | DA-C2, DA-H1, DA-H3 | 2-3 days |
| 300.2 | **Usability Quick Wins** | UX-C1, UX-H3, M11, M12 | 1-2 days |
| 300.3 | **High-Value Missing Features** | MF-1 (deadline alerts), MF-2 (similar contracts), MF-3 (win rate analytics) | 4-6 days |
| 300.4 | **pWin & Qualification Accuracy** | DA-C1 (document limitation) | 1 day |
| 300.5 | **Efficiency Fixes** | EF-M1, EF-M2, EF-L1, EF-L3 | 1-2 days |
| 300.6 | **BD Analytics & Intelligence** | MF-4 (lost deal tracking), MF-5 (set-aside trends), MF-6 (NAICS market analysis) | 4-5 days |
| 300.7 | **API Cleanup** | H1, M1, M2, M3, M4, M5, M6, H3 | 3-4 days |

---

## Out of Scope

- Phase 150 items (security hardening) — deferred until production deployment
- Phase 600 items (insane optimizations) — intentionally deferred
- Phase 200 items (DB normalization) — tracked separately
- Phase 120 ETL bugs — tracked separately
- File storage for proposals (C1) — needs infrastructure decision first
- Multi-org/multi-tenant improvements — single-org deployment, not needed
