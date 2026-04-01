# Phase 115H: Ignore Opportunity & Pipeline Visibility Fixes

**Status:** PLANNED
**Priority:** HIGH
**Dependencies:** Prospect Pipeline (Phase 50), Dashboard (Phase 70)

---

## Summary

Two related pipeline usability issues:

1. **Ignore Opportunity** — Users who review an opportunity and decide it's not viable need a way to hide it so it doesn't clutter their views. This applies to opportunities on the search/browse pages (not yet added to the pipeline as a prospect). Must be a toggle so ignored opportunities can be un-ignored.

2. **Done Prospects Not Visible** — Prospects moved to terminal statuses (DECLINED, NO_BID, WON, LOST) may not be visible in the Kanban view even when the user selects those statuses. Investigation and fix needed.

---

## Feature 1: Ignore Opportunity

### Problem

When browsing opportunities (Opportunities page, Recommended page, Expiring Contracts), users repeatedly see the same opportunities they've already evaluated and rejected. There's no way to dismiss them without adding them to the prospect pipeline and declining them — which pollutes the pipeline with noise.

### Requirements

- [ ] Add "Ignore" action to opportunity cards/rows across all opportunity-facing pages
- [ ] Ignored opportunities are hidden by default from all opportunity lists
- [ ] Toggle control (e.g., "Show ignored" checkbox/switch) to reveal ignored opportunities
- [ ] Ignored opportunities are visually distinct when shown (e.g., muted/greyed out)
- [ ] "Un-ignore" action available when viewing ignored opportunities
- [ ] Ignore state is per-user (not org-wide — different team members may want to evaluate the same opportunity)
- [ ] Ignore state persists across sessions

### Affected Pages

- **Opportunities** search/browse page
- **Recommended Opportunities** page
- **Expiring Contracts** page
- Any future page that lists opportunities

### Design Notes

**Database:**
- New table: `opportunity_ignore` (or similar)
  - `user_id` (FK to app_user)
  - `notice_id` (the SAM.gov opportunity identifier)
  - `ignored_at` (timestamp)
  - Optional: `reason` (text, for user's own notes — "too large", "wrong agency", etc.)
- EF Core owned (application table, not ETL)

**API:**
- `POST /api/opportunities/{noticeId}/ignore` — mark as ignored
- `DELETE /api/opportunities/{noticeId}/ignore` — un-ignore
- `GET /api/opportunities` and related endpoints gain `excludeIgnored=true` (default) query param

**UI:**
- Ignore button/icon on opportunity cards and list rows
- Global or per-page toggle: "Show ignored opportunities"
- Visual treatment for ignored items when shown

---

## Feature 2: Done Prospect Visibility Bug

### Problem

Prospects moved to terminal statuses can't be seen even when selecting those statuses in the Kanban view filter.

### Known Issues Found in Code

1. **NO_BID missing from Kanban columns** — `ProspectPipelinePage.tsx` line 66 defines `KANBAN_STATUSES` as `['NEW', 'REVIEWING', 'PURSUING', 'BID_SUBMITTED', 'WON', 'LOST']`. The `NO_BID` status is absent. Prospects with NO_BID status fall through to the NEW column via fallback logic (line 424-425), which is incorrect and confusing.

2. **NO_BID missing from status filter dropdown** — The status filter dropdown does not include NO_BID as an option, so users cannot filter to see NO_BID prospects.

3. **DECLINED column exists but isn't in KANBAN_STATUSES** — DECLINED is handled as a separate "Archived" bucket but may not display correctly depending on view mode and filter state.

### Tasks

- [ ] Investigate: Reproduce the exact scenario where Done prospects disappear
- [ ] Fix: Add NO_BID to KANBAN_STATUSES and the status filter dropdown
- [ ] Fix: Ensure all terminal statuses (WON, LOST, DECLINED, NO_BID) are visible when explicitly selected in the filter
- [ ] Fix: Kanban view should show terminal status columns when those statuses are selected
- [ ] Test: Verify status filter works correctly for every status value
- [ ] Consider: Should terminal statuses be hidden by default on Kanban with a "Show completed/archived" toggle?

---

## Implementation Order

1. Bug fixes first (Feature 2) — quick wins, improves existing functionality
2. Database + API for ignore feature
3. UI integration across opportunity pages

---

## Out of Scope

- Bulk ignore (select multiple opportunities to ignore at once) — defer to future enhancement
- Ignore reasons as structured data / analytics — keep it simple, optional free-text at most
- Auto-ignore rules (e.g., "ignore all from agency X") — separate feature if needed later
