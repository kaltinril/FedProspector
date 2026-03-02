# Phase 18: Capture Management & Pipeline

**Status**: NOT STARTED
**Dependencies**: Phase 17 (Detail Views), Phase 14.5 (Multi-Tenancy)
**Deliverable**: Prospect pipeline (Kanban + list), proposal tracking, team collaboration, Go/No-Go scoring
**Repository**: `ui/src/pages/`

---

## Overview

Build the capture management workflow — once a user finds an opportunity, they track it as a "prospect" and move it through a pipeline: LEAD → QUALIFIED → PURSUING → SUBMITTED → WON/LOST.

**Data scoping:** All prospect/proposal data is scoped to the user's organization. Users only see their company's pipeline.

This is where the tool goes beyond search (what GovWin does) into active bid management (what a CRM does). Users manage their pipeline, assign team members, write internal notes, create proposals, and track milestones.

**User workflow this enables:**
> "I found a good medical staffing opportunity. Track it, assign it to Sarah, score it for go/no-go, then manage the proposal through submission."

---

## Pages

### Prospect Pipeline (`/prospects`)

**Two views (toggle):**

**Kanban View (default):**
- Columns: LEAD → QUALIFIED → PURSUING → SUBMITTED → WON / LOST
- Cards show: opportunity title, deadline countdown, estimated value, assigned user avatar, priority flag, go/no-go score
- Drag-and-drop to move between stages
- Click card → Prospect Detail

**List View:**
- Full data grid with all prospect fields
- Sortable by deadline, value, score, status, priority
- Bulk actions (reassign, update status)
- Filter by: status, priority, assigned user, NAICS, set-aside

**Actions:**
- "New Prospect" button (from scratch or from opportunity)
- Quick filters: "My Prospects", "Due This Week", "High Priority"

### Prospect Detail (`/prospects/:id`)

**Header:**
- Opportunity title (linked)
- Status chip (with transition dropdown)
- Priority flag (LOW / MEDIUM / HIGH / CRITICAL)
- Go/No-Go score gauge (0-100)
- Assigned user + capture manager
- Reassign action (dropdown or button) — users can reassign without going to list view
- Deadline countdown

**Tab 1: Overview**
- Linked opportunity summary card (key facts)
- Score breakdown panel:
  - Individual criteria scores (set-aside match, NAICS experience, clearance, value fit, etc.)
  - Each criterion: name, score, weight, rationale
  - Overall weighted score with visual gauge
  - "Recalculate Score" button
- Win probability + estimated gross margin
- Bid submitted date, outcome, outcome notes (if completed)

**Tab 2: Notes**
- Chronological note feed (newest first)
- Add note form (rich text area + submit)
- Notes show: author, timestamp, content
- Sticky/pinned notes at top

**Tab 3: Team (Teaming Partners)**
- Team member list: company name, UEI, role, proposed hourly rate, commitment %
- Add team member: entity search by UEI or company name (not user search — team members are teaming partner companies, not internal users)
- Remove team member with confirmation dialog
- Capture manager designation

**Tab 4: Proposal**
- If no proposal: "Create Proposal" CTA
- If proposal exists:
  - Proposal status, submission deadline
  - Milestone checklist (with completion tracking)
  - Document list (attached files metadata)
  - Link to full proposal detail

**Tab 5: Intelligence**
- Embedded opportunity intel (re-compete status, incumbent info, burn rate)
- Same content as Opportunity Detail "History" tab — no need to navigate away

### Proposal Detail (`/proposals/:id`)

**Header:**
- Proposal number, status
- Linked prospect/opportunity
- Submission deadline countdown
- Estimated value, win probability

**Sections:**
- Edit Proposal form: status, estimated value, win probability, lessons learned
- Milestone tracker (visual timeline)
  - Each milestone: name, due date, status, completion date, assigned to (`AssignedTo` field)
  - "Create Milestone" flow (Phase 14.5 adds the POST endpoint)
  - Update milestone inline
- Document registry (metadata only — name, type, uploaded date, uploaded by, file size in bytes (`FileSizeBytes`))
- Lessons learned (text field, updated after outcome)

**Breadcrumb:** Dashboard > Prospects > [Name] > Proposal #[X]

**Note:** Proposals are accessed through prospect detail only — there is no top-level "Proposals" sidebar item.

---

## Tasks

### 18.1 Prospect Pipeline — Kanban View
- [ ] Build Kanban board with drag-and-drop (use `@dnd-kit/core` + `@dnd-kit/sortable` ONLY — `react-beautiful-dnd` is deprecated and incompatible with React 19)
- [ ] Pipeline columns: LEAD, QUALIFIED, PURSUING, SUBMITTED, WON, LOST
- [ ] Prospect cards: title, deadline, value, assignee, priority, score
- [ ] Drag card between columns → calls `PATCH /prospects/{id}/status`
- [ ] Color coding: red deadline (< 7 days), priority flags
- [ ] Filter bar: my prospects, due this week, by NAICS
- [ ] Empty state for new users with zero prospects: "Start by searching for opportunities and tracking them as prospects." with a link to /opportunities
- [ ] Optimistic update: card moves immediately, reverts on API failure with error toast
- [ ] Invalid status transitions: validate drop target against allowed transitions before calling API. Show toast if invalid (e.g., LEAD -> WON is not allowed)
- [ ] Loading state: brief dimming of dragged card during API call

### 18.2 Prospect Pipeline — List View
- [ ] Build data grid list view (toggle from Kanban)
- [ ] All prospect fields as columns
- [ ] Server-side pagination and sorting
- [ ] Bulk status update and reassignment
- [ ] Quick filter chips (status, priority, assigned user)

### 18.3 Create Prospect Flow
- [ ] "Track as Prospect" from opportunity detail/search
- [ ] Create prospect form (assignee, priority, initial notes)
- [ ] Wire to `POST /api/v1/prospects`
- [ ] Duplicate prospect protection: if user tries to create a prospect for a NoticeId that already has a prospect in their org, show a message linking to the existing prospect
- [ ] Redirect to new prospect detail

### 18.4 Prospect Detail Page
- [ ] Build tabbed detail page
- [ ] Status transition dropdown (valid transitions only)
- [ ] Go/No-Go score gauge and criteria breakdown
- [ ] "Recalculate Score" button
- [ ] Wire to `GET /api/v1/prospects/{id}`

### 18.5 Notes & Team Collaboration
- [ ] Notes feed component (chronological, add new)
- [ ] Wire to `POST /api/v1/prospects/{id}/notes`
- [ ] Team member list: company name, UEI, role, proposed hourly rate, commitment %
- [ ] Add team member: entity search by UEI or company name (not user search)
- [ ] `AddTeamMemberRequest` has `UeiSam`, `Role`, `ProposedHourlyRate`, `CommitmentPct`
- [ ] `ProspectTeamMemberDto` returns `UeiSam`, `EntityName`, `Role`, `ProposedHourlyRate`, `CommitmentPct`
- [ ] Remove team member with confirmation dialog
- [ ] Wire to `POST/DELETE /api/v1/prospects/{id}/team-members`

### 18.6 Proposal Management
- [ ] Create proposal form (from prospect detail)
- [ ] Edit Proposal form for proposal-level fields (status, estimated value, win probability, lessons learned)
- [ ] Proposal detail page with milestone tracker
- [ ] Create Milestone flow (Phase 14.5 adds the POST endpoint)
- [ ] Milestone status update (inline toggle) — milestone display includes `AssignedTo` field
- [ ] Document registry (metadata display) — includes `FileSizeBytes`
- [ ] Wire to proposal API endpoints
- [ ] Breadcrumb: Dashboard > Prospects > [Name] > Proposal #[X]

---

## Verification
- [ ] Kanban board loads prospects in correct columns
- [ ] Drag-and-drop updates status via API
- [ ] Empty Kanban state displays onboarding message for new users
- [ ] Invalid drag-and-drop transitions are blocked with toast message
- [ ] Create prospect from opportunity search → appears in pipeline
- [ ] Duplicate prospect for same NoticeId is prevented with link to existing
- [ ] Go/No-Go score displays correctly with criteria breakdown
- [ ] Notes and team member CRUD works
- [ ] Team members display as companies (entity names with UEI) not users
- [ ] Reassign works from detail page (not just list view)
- [ ] Proposal milestones can be created and updated
