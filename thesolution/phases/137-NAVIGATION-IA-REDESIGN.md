# Phase 137: Navigation Information Architecture Redesign — 3-Tier (Destinations + Hubs)

**Status:** Not Started (idea captured for review)
**Priority:** Medium — UX/scalability; not blocking.
**Scope:** Frontend (`ui/`) navigation + routing only. No backend, ETL, or schema changes.
**Depends on:** Command palette + collapsible/icon-rail nav + anchor-based nav links (all delivered separately; see "Related / Prerequisite Work").

---

## Goal

Reorganize the left-sidebar navigation from a flat ~34-item sitemap into a **3-tier information architecture** that separates **destinations** (where you start work) from **tools** (things you invoke about a specific opportunity, bid, or company). Consolidate tool-heavy groups into a small number of **hub pages** (one nav item → a page with tabs, the same pattern as the existing Opportunity detail tabs), and move account/utility items off the left rail into the top-right avatar menu.

**Outcome:** ~42 left-rail rows (incl. group headers) → **~11 left-rail rows**. Nothing is removed — depth simply moves one level down, made discoverable via the command palette, hub landing pages, and contextual launchers.

---

## Background / Problem

The left sidebar currently renders **~34 navigable items across 8 groups (~42 rows including group headers)**:

| Group | Items |
|-------|-------|
| MAIN | Dashboard |
| PIPELINE | Recommended, Expiring Contracts, Prospects, Analytics, Calendar, Stale Alerts, Forecast |
| RESEARCH | Opportunities, Awards, Entities, Teaming, Federal Hierarchy, NAICS Browser |
| PRICING INTELLIGENCE | Market Rates, Price-to-Win, Bid Scenarios, Escalation, IGCE Estimator, Sub Benchmarks, SCA Area Rates |
| COMPETITIVE INTEL | Re-compete Candidates, Agency Patterns, Contracting Offices |
| TEAMING | Partner Search, Mentor-Protégé, Gap Analysis |
| ONBOARDING | Certification Alerts, Size Standard, Past Performance, Portfolio Gaps |
| TOOLS | Saved Searches, Data Quality |
| SETTINGS | Profile, Organization |

### Root cause

**Every TOOL is exposed as a global DESTINATION**, so the nav reads like a sitemap rather than a workflow. A tool such as "IGCE Estimator" or "Price-to-Win" is most useful *in the context of a specific opportunity or bid*, not as a cold global link the user must navigate to and then re-enter context.

### Two specific issues called out

1. **"Teaming" is duplicated / ambiguous.** There are two different "Teaming" concepts in the nav:
   - **Research → Teaming** routes to `/subawards/teaming` — this is **subaward-network analysis** (who subcontracts to whom).
   - **TEAMING group** (Partner Search, Mentor-Protégé, Gap Analysis) — this is about **building your own team** to bid.

   These are distinct concepts sharing one label. **Explicit rename in this phase:** the Research → "Teaming" item becomes **"Subaward Network"**.

2. **"Onboarding" is a misnomer.** The ONBOARDING group (Certification Alerts, Size Standard, Past Performance, Portfolio Gaps) contains **permanent eligibility monitors**, not a one-time onboarding flow. It will be **renamed "Company & Eligibility."**

---

## Core Principle

> Separate **DESTINATIONS** (where you start work) from **TOOLS** (things you invoke about a specific opportunity / bid / company).

Tools are most useful **in-context**, not as cold global links. The biggest lever for de-cluttering the nav is **contextual launchers** (e.g. a "Price this" button on an Opportunity) — many tools then don't need prominent global nav at all.

---

## Proposed 3-Tier Model

### Tier 1 — Destinations (flat global nav, ~6 items)

The places you *start* a task. These stay as top-level left-rail items:

- Dashboard
- Recommended
- Prospects
- Opportunities
- Awards
- Entities

### Tier 2 — Hubs (~5 items)

Each hub is **ONE nav item** that opens a **page with tabs** — the same UI pattern already used by the Opportunity detail view (Overview / Document Intel / Qualification & pWin / etc.). The hub's tabs hold what used to be separate nav items.

| Hub (nav item) | Tabs |
|----------------|------|
| **Pipeline** | Board, Forecast, Analytics, Calendar, Stale Alerts, Expiring Contracts |
| **Pricing** | Market Rates, Price-to-Win, Bid Scenarios, Escalation, IGCE Estimator, Sub Benchmarks, SCA Area Rates |
| **Teaming** | Partner Search, Mentor-Protégé, Gap Analysis, **Subaward Network** *(the renamed Research → Teaming item)* |
| **Market Intel** | Agency Patterns, Contracting Offices, Re-compete Candidates, Federal Hierarchy, NAICS Browser |
| **Company & Eligibility** *(renamed from "Onboarding")* | Certification Alerts, Size Standard, Past Performance, Portfolio Gaps |

### Tier 3 — Account / Utility (top-right avatar menu, off the left rail)

Low-frequency, account-level items move out of the left rail into the avatar/user menu in the top bar:

- Profile
- Organization
- Saved Searches
- Data Quality

### Net effect

| | Before | After |
|---|--------|-------|
| Left-rail rows (incl. headers) | ~42 | **~11** |
| Top-level destinations | scattered across 8 groups | 6 flat destinations |
| Tool groups | 8 groups of links | 5 hub pages (tabs) |
| Account/utility | on left rail | top-right avatar menu |

**Nothing is removed.** Depth moves one level down (into hub tabs or the avatar menu). The explicit rename is **Research → "Teaming" becomes "Subaward Network"** (now a tab inside the Teaming hub), plus **"Onboarding" → "Company & Eligibility."**

---

## Discoverability Mechanisms

Consolidation must not bury features. Three mechanisms keep everything findable:

1. **Command palette** (jump-to-page by typing the page name).
   - **NOTE:** This is being added **now, in a separate follow-up** — not part of this phase.
   - Opens with `/` plus a top-bar search box; deliberately **not** a browser-reserved shortcut.
2. **Hub landing pages that advertise their tools** — each hub's default view shows cards with a one-line description of each tool/tab, so a user landing on "Pricing" immediately sees the 7 tools available.
3. **Contextual launchers** — action buttons surfaced from an Opportunity or Prospect, pre-filled with that record's context, e.g.:
   - "Price this" → opens Pricing (Price-to-Win) for the selected opportunity
   - "Build IGCE" → opens Pricing (IGCE Estimator) pre-filled
   - "Find teaming partners" → opens Teaming (Partner Search) scoped to the opportunity's NAICS/agency

   **This is the biggest lever** — once tools launch in-context with pre-filled data, many of them no longer need prominent global nav placement at all.

---

## Related / Prerequisite Work (NOT part of this phase)

These were/are delivered separately and are listed here only as context/prerequisites:

- **Collapsible nav groups** — done.
- **Icon-rail collapse** — pre-existing.
- **Command palette** — being added now in a separate follow-up (see Discoverability #1).
- **Anchor-based nav links** (middle-click / open-in-new-tab) — done.

**This phase is specifically:** the **hub-page consolidation** + **IA reorganization** + **moving Tier-3 items to the avatar menu** (plus the Teaming dedupe/rename and the Onboarding rename).

---

## Suggested Incremental Rollout

Ship in stages to validate the pattern before a big-bang reorg:

1. **Pilot ONE hub first — Pricing** (7 items → 1 "Pricing" page with tabs).
   - Validates the hub-page pattern and the routing approach.
   - **Keep the old routes as redirects to the hub + tab** (e.g. `/pricing/price-to-win` → `/pricing?tab=price-to-win`) so existing deep links / bookmarks keep working.
2. **Apply the hub pattern to the other hubs** (Pipeline, Teaming, Market Intel, Company & Eligibility) once Pricing is validated.
3. **Move Tier-3 items to the avatar menu** (Profile, Organization, Saved Searches, Data Quality).
4. **Finish with the Teaming dedupe/rename** (Research → "Teaming" becomes "Subaward Network" tab inside the Teaming hub).

---

## Deferred / Optional (not committed in this phase)

- **Pinned / Favorites section** — let users pin frequently used tools to the top of the rail.
- **Role-based nav presets** — capture vs. pricing vs. contracts personas, *if* multiple personas actually use the app (see Open Questions).

---

## Reference Mockups

- **`thesolution/reference/nav-redesign-mockup.svg`** — before/after sidebar comparison. *(Present in repo.)*
- **`thesolution/reference/nav-redesign-page-mockup.svg`** — Dashboard destination vs. Pipeline hub-with-tabs page layout. *(Companion mockup — add alongside the sidebar mockup when available; not yet present in repo at time of writing.)*

---

## Open Questions (for the user)

These drive the final Tier 1 / hub split and should be answered before implementation:

1. **Who is the primary daily user, and what are their top ~5 actions?** This drives which items belong in Tier 1 (Destinations).
2. **Single persona vs. multiple personas?** If multiple (capture vs. pricing vs. contracts), do we want **role-based nav presets** (currently deferred)?
3. **Does "Pipeline" include the Prospects board as a tab, or does Prospects stay a separate Tier-1 destination?** (Listed as Tier-1 above, but the Pipeline hub also lists a "Board" tab — confirm whether these are the same thing or two distinct views.)
4. **Which groups truly merit hubs vs. staying flat?** Validate the 5 proposed hubs — some may be better left as flat destinations or merged differently.
5. **Routing / redirect strategy for old deep links** — confirm the approach (old route → hub + `?tab=` redirect) and how long redirects are retained.

---

## Tasks (provisional — pending answers to Open Questions)

- [ ] Confirm Tier 1 / Tier 2 / Tier 3 split with the user (resolve Open Questions).
- [ ] Pilot: build the **Pricing** hub page (tabbed) consolidating the 7 pricing pages; add redirects from old `/pricing/*` routes.
- [ ] Validate pattern + routing with the user before proceeding.
- [ ] Build remaining hubs: Pipeline, Teaming, Market Intel, Company & Eligibility (tabbed pages + redirects).
- [ ] Add hub landing pages with tool-advertising cards (one-line descriptions per tab).
- [ ] Move Tier-3 items (Profile, Organization, Saved Searches, Data Quality) into the top-right avatar menu.
- [ ] Rename Research → "Teaming" to **"Subaward Network"**; relocate it as a tab inside the Teaming hub.
- [ ] Rename "Onboarding" group → **"Company & Eligibility."**
- [ ] Add contextual launchers ("Price this" / "Build IGCE" / "Find teaming partners") from Opportunity / Prospect detail views, pre-filled with context.
- [ ] Update any docs/skills that reference the old nav structure or routes.

---

## Performance Considerations (measured 2026-06-05 against prod)

**Why this matters:** the 3-tier redesign consolidates standalone pages into Tier-2 **hubs with in-page tabs**. The risk is that a hub eagerly loads all its tabs' queries at once — several of which are slow — turning today's one-page-one-query into an N-query fan-out. We measured the real query latency behind every hub tab to ground the design.

### Measured tab latencies (prod, MySQL 8.4.8)
| Hub · Tab | Backing view / query | Measured | Verdict |
|---|---|---|---|
| Teaming · Partner Search + Gap Analysis | `v_partner_capability_match` | **>90 s (timed out at cap)** | 🔴 broken in prod today |
| Teaming · Mentor-Protégé (filtered by org) | `v_mentor_protege_candidate` | 1.0 s | ✅ fine in real use |
| Teaming · Mentor-Protégé (unfiltered "list all") | (worst case) | 53.4 s | ⚠️ avoid unfiltered |
| Market Intel · Agency Patterns | `v_agency_recompete_pattern` | 3.4 s | 🟡 moderate |
| Market Intel · Re-compete Candidates | `v_recompete_candidate` | 2.1 s | 🟡 moderate |
| Market Intel · Contracting Offices | `v_contracting_office_profile` | 0.9 s | ✅ |
| Pricing · IGCE Estimator | `usaspending_award` scan (32,973 rows, NAICS 541512/5yr) | 0.45 s DB | ✅ DB fine; app-memory ⚠️ |
| Teaming · Subaward Network | `sam_subaward` GROUP BY | 0.11 s | ✅ (only 9,550 rows) |
| Company · Portfolio Gaps / Past Performance | views | 0.8 s / 0.1 s | ✅ |

### Findings & root causes
1. **CRITICAL — Partner Search + Gap Analysis are broken in prod today (>90 s).** Both tabs read `v_partner_capability_match`. `EXPLAIN` shows the NAICS filter (`LIKE '%code%'` over a `GROUP_CONCAT`) **cannot push down** — MySQL fully materializes a ~210-billion-row nested-loop estimate and `GROUP_CONCAT`s before applying the filter and `LIMIT`. So even the real filtered/paged query pays the full cost. This is independent of Phase 137.
2. **Mentor-Protégé is fine in real use (1.0 s).** Filtering by the org's protégé UEI pushes into the `protege` CTE; the 53 s only occurs for an unfiltered "list everyone" query. Keep it filtered; never expose an unfiltered list.
3. **Agency Patterns (3.4 s) / Re-compete (2.1 s)** — heavy multi-CTE/window views; acceptable but worth materializing later.
4. **Subaward Network is fast (0.11 s)** — `sam_subaward` is only 9,550 rows; an earlier static estimate of multi-seconds was wrong (corrected by measurement).
5. **IGCE** — DB scan is fine (0.45 s), but the service pulls **32,973 rows unbounded** into app memory for a common NAICS (far more for popular ones). App-memory hygiene issue, not latency.
6. **Structural cause:** most "summary" reads are SQL **VIEWs** (`ToView`) re-executed on every request, not materialized tables. The only real summary table is `usaspending_award_summary`, and no Phase 137 tab uses it.

### Fix suggestions
**Backend (independent of the nav redesign):**
- **Materialize `v_partner_capability_match`** into a daily-refreshed summary table with indexed NAICS filtering (not a `GROUP_CONCAT` substring match), per the CLAUDE.md precompute mandate. Fixes the one broken surface. Optionally do the same for Agency Patterns / Re-compete.
- **Quick wins:** add `.Take(500)` to the IGCE historical-analog pull (`PricingService`), and bound the FPDS branch of Expiring Contracts (`ExpiringContractService`) with `.Take(...)`.

**Frontend (Phase 137 itself):**
- **Lazy-mount the active tab only** — the existing `TabbedDetailPage` and `OrganizationPage` already do this (`{active === tab && <Panel/>}`); reuse the pattern and keep each tab's `useQuery` inside its panel so a hub fires exactly one query, never the slow siblings. Do not regress to `keepMounted`/always-mounted panels.
- **`?tab=` URL state + old-route → `?tab=` redirects** so a hub deep-link loads exactly one tab's data and old bookmarks keep working.
- For the expensive hubs (Teaming, Market Intel): raise `gcTime` and set `refetchOnWindowFocus: false` per-hook; **never eager-prefetch** those tabs.
- Global `QueryClient` defaults are already a good baseline (`staleTime` 5 min / `gcTime` 10 min, `App.tsx`).
