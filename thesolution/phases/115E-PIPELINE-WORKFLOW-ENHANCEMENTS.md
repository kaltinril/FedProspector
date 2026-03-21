# Phase 115E: Pipeline & Workflow Enhancements (Brainstorm Gap Analysis)

**Status:** IDEA — from brainstorm analysis, not yet prioritized
**Priority:** TBD
**Source:** C:\git\brainstorm\docs\phases\ (phases 20-22, 48-49, 51)
**Dependencies:** Existing prospect pipeline (Phase 40+)

---

## Summary

Our pipeline works (Kanban + list view, 6 statuses, drag-and-drop). The brainstorm designed a more feature-rich pipeline with analytics, automation, and proposal support. Some of these are genuinely useful additions.

## Overlap with Existing Features

| Idea | Status | What Exists |
|------|--------|-------------|
| Calendar/Gantt views | **NEW** | `ProspectPipelinePage` has Kanban (6 status columns) + list view. No calendar or Gantt. |
| Reverse Timeline Generator | **NEW** | `proposal_milestone` table tracks due dates per proposal, but no auto-generation from response deadline. |
| Pipeline Analytics | **PARTIAL** | Dashboard shows pipeline value, status chart, due-this-week, workload by assignee. `prospect.outcome` and `prospect.outcome_date` track win/loss. Missing: funnel visualization, stage conversion rates, revenue forecasting, win/loss reason analysis. |
| Morning Brief Email | **NEW** | `NotificationService` handles in-app notifications only (4 types: new_match, deadline_approaching, status_changed, score_recalculated). No email backend, no scheduled digests. |
| Webhooks | **NEW** | No webhook infrastructure. Notifications are in-app only. |
| Calendar Integration | **NEW** | No external calendar sync. `proposal_milestone.due_date` exists but no iCal/Outlook/Google export. |
| Sources-Sought Drafter | **NEW** | Phase 110 attachment intelligence will extract text from solicitation docs. No response drafting. |
| Proposal Reuse KB | **NEW** | `proposal_document` table stores files. No content extraction, no templates, no semantic search. Explicitly out of scope in Phase 110. |

---

## Pipeline Enhancements We Don't Have

### 1. Additional Pipeline Views

We have Kanban and list. The brainstorm also designed:
- **Calendar view** — plot opportunities by response deadline
- **Timeline/Gantt view** — visualize overlapping capture efforts

**Source:** brainstorm phase-20

### 2. Reverse Timeline Generator

Given a response deadline, auto-generate working-backward milestones:
- "Response due March 15 → Color review by March 8 → Draft complete by March 1 → Capture plan by Feb 15 → Go/No-Go by Feb 1"
- Configurable per stage
- Could integrate with calendar exports

**Value:** Saves BD professionals from manually calculating backward from every deadline.

**Source:** brainstorm phase-21

### 3. Pipeline Analytics Dashboard

- **Funnel analysis** — stage-to-stage conversion rates, drop-off counts, average time to convert
- **Revenue forecasting** — weighted projections by expected award month, scenario analysis (optimistic/baseline/pessimistic)
- **Win/loss analysis** — reasons for losses, feeding back into pWin calibration
- **Activity metrics** — cards created/moved/closed per week, team workload trends
- **Multi-format export** — CSV, Excel, PDF summary reports

We have basic pipeline value on the dashboard, but not this level of analytics.

**Source:** brainstorm phase-22

### 4. Morning Brief Daily Email Digest

Single daily email aggregating:
- Action items for today (deadlines, tasks)
- New opportunities matching saved searches
- Pipeline deadline reminders
- Market intelligence highlights
- "Add to Pipeline" one-click links

Mobile-optimized HTML email.

**How it differs from our notifications:** We have in-app notifications. This is a push email that arrives before you open the app — designed for the user persona who checks email first thing.

**Source:** brainstorm phase-15, phase-51

### 5. Webhook Delivery for Saved Search Results

Allow power users to pipe new opportunity matches to external systems (Slack, Teams, CRM, custom tools) via webhooks.

**Source:** brainstorm phase-15

### 6. Calendar Integration

Push pipeline deadlines and response dates to Google Calendar / Outlook. Could also accept calendar events (e.g., "Industry Day" entries auto-linked to opportunities).

**Source:** brainstorm phase-51

---

## Proposal Support Features (New Category)

### 7. Sources-Sought Auto-Response Drafter

When a sources-sought or RFI matches your profile:
- Auto-detect matching notices
- Parse requirements from the notice
- Assemble draft capability statement from profile + past performance + templates
- Side-by-side review interface (notice requirements on left, your draft on right)
- PDF export

**Value:** Sources-sought responses are time-sensitive and repetitive. Automating the draft saves hours.

**Source:** brainstorm phase-48

### 8. Proposal Reuse Knowledge Base

Upload past proposals (PDF/DOCX/PPTX):
- Auto-extract sections with structure preservation
- Vector embeddings for semantic search
- When working on a new opportunity, auto-surface relevant past proposal sections
- Per-tenant encryption (proposals are sensitive)

**Note:** We explicitly scoped this OUT in Phase 110. But it's worth tracking as a future capability. The brainstorm called this "the highest-value feature for repeat bidders."

**Source:** brainstorm phase-49

---

## Implementation Notes

- Morning Brief email (#4) is probably the highest-impact item here — it's a retention/engagement driver
- Pipeline analytics (#3) builds on existing data, just needs UI
- Reverse timeline (#2) is a relatively simple feature with high perceived value
- Proposal reuse KB (#8) is complex (needs vector search) but was called out as extremely high-value
