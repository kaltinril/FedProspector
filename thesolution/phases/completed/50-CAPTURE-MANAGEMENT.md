# Phase 50: Capture Management & Pipeline

**Status**: COMPLETE
**Dependencies**: Phase 40 (Detail Views), Phase 14.5 (Multi-Tenancy)
**Deliverable**: Prospect pipeline (Kanban + list), proposal tracking, team collaboration, Go/No-Go scoring
**Repository**: `ui/src/pages/`

---

## Overview

Build the capture management workflow — once a user finds an opportunity, they track it as a "prospect" and move it through a pipeline: NEW → REVIEWING → PURSUING → BID_SUBMITTED → WON/LOST. DECLINED and NO_BID are terminal statuses — shown as a collapsible 'Archived' section below the Kanban board, or as a filter toggle.

**Data scoping:** All prospect/proposal data is scoped to the user's organization. Users only see their company's pipeline.

#### Prospect Status State Machine

Valid transitions (enforced by `ProspectStatusValidator` in C# and `STATUS_FLOW` dict in Python):

```
NEW ──────────→ REVIEWING
  └──────────→ DECLINED (terminal)

REVIEWING ────→ PURSUING
  └──────────→ DECLINED (terminal)

PURSUING ─────→ BID_SUBMITTED
  └──────────→ DECLINED (terminal)

BID_SUBMITTED → WON (terminal)
  └──────────→ LOST (terminal)
```

| From | Valid Targets | Notes |
|------|--------------|-------|
| NEW | REVIEWING, DECLINED | Initial triage |
| REVIEWING | PURSUING, DECLINED | Go/No-Go evaluation |
| PURSUING | BID_SUBMITTED, DECLINED | Active pursuit → submission |
| BID_SUBMITTED | WON, LOST | Awaiting award decision |
| DECLINED | (none) | Terminal — cannot reopen |
| WON | (none) | Terminal — contract awarded |
| LOST | (none) | Terminal — not selected |

**UI enforcement**: Kanban drag-and-drop validates target column against this table. Invalid drops show error toast and snap card back to original column. The status chip dropdown on prospect detail also only shows valid next statuses.

This is where the tool goes beyond search (what GovWin does) into active bid management (what a CRM does). Users manage their pipeline, assign team members, write internal notes, create proposals, and track milestones.

**User workflow this enables:**
> "I found a good medical staffing opportunity. Track it, assign it to Sarah, score it for go/no-go, then manage the proposal through submission."

---

## Pages

### Prospect Pipeline (`/prospects`)

**Two views (toggle):**

**Kanban View (default):**
- Columns: NEW → REVIEWING → PURSUING → BID_SUBMITTED → WON / LOST
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
- Go/No-Go score gauge (0-40) (4 criteria x 0-10 each = 40 max)
- Assigned user + capture manager
- Reassign action (dropdown or button) — users can reassign without going to list view
- Deadline countdown

**Tab 1: Overview**
- Linked opportunity summary card (key facts)
- Score breakdown panel:
  - Named criteria (`SetAside`, `TimeRemaining`, `NaicsMatch`, `AwardValue`), each with `Score` (0-10), `Max`, and `Detail` (explanation text). No explicit weight field — all criteria weighted equally.
  - Overall score with visual gauge (0-40)
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

### 50.1 Prospect Pipeline — Kanban View
- [x] Build Kanban board with drag-and-drop (use `@dnd-kit/core` + `@dnd-kit/sortable` ONLY — `react-beautiful-dnd` is deprecated and incompatible with React 19)
- [x] Pipeline columns: NEW, REVIEWING, PURSUING, BID_SUBMITTED, WON, LOST (plus DECLINED and NO_BID as terminal/archived statuses)
- [x] Prospect cards: title, deadline, value, assignee, priority, score
- [x] Drag card between columns → calls `PATCH /prospects/{id}/status`
- [x] Color coding: red deadline (< 7 days), priority flags
- [x] Filter bar: my prospects, due this week, by NAICS
- [x] Empty state for new users with zero prospects: "Start by searching for opportunities and tracking them as prospects." with a link to /opportunities
- [x] Optimistic update: card moves immediately, reverts on API failure with error toast
- [x] Invalid status transitions: validate drop target against allowed transitions before calling API. Show toast if invalid (e.g., NEW -> WON is not allowed)
- [x] Loading state: brief dimming of dragged card during API call

### 50.2 Prospect Pipeline — List View
- [x] Build data grid list view (toggle from Kanban)
- [x] All prospect fields as columns
- [x] Server-side pagination and sorting
- [x] Bulk status update and reassignment
- [x] Quick filter chips (status, priority, assigned user)

### 50.3 Create Prospect Flow

#### Prospect Creation Defaults

When creating a prospect from the "Track as Prospect" button on an opportunity:

| Field | Default | Required? |
|-------|---------|-----------|
| Opportunity | Pre-filled from source opportunity | Yes (auto) |
| Assignee | Current logged-in user | No (defaults to self) |
| Priority | MEDIUM | No (defaults to MEDIUM) |
| Status | NEW | Yes (auto, not user-editable) |
| Notes | Empty | No |

**Design rationale**: Minimize friction. Users should be able to track an opportunity with a single click. All fields except the opportunity link are optional with sensible defaults. Users can edit assignee, priority, and add notes after creation from the prospect detail page.

- [x] "Track as Prospect" from opportunity detail/search
- [x] Create prospect form (assignee, priority, initial notes)
- [x] Wire to `POST /api/v1/prospects`
- [x] Duplicate prospect protection: if user tries to create a prospect for a NoticeId that already has a prospect in their org, show a message linking to the existing prospect
- [x] Redirect to new prospect detail

### 50.4 Prospect Detail Page
- [x] Build tabbed detail page
- [x] Status transition dropdown (valid transitions only)
- [x] Go/No-Go score gauge and criteria breakdown
- [x] "Recalculate Score" button
- [x] Wire to `GET /api/v1/prospects/{id}`

### 50.5 Notes & Team Collaboration
- [x] Notes feed component (chronological, add new)
- [x] Wire to `POST /api/v1/prospects/{id}/notes`
- [x] Team member list: company name, UEI, role, proposed hourly rate, commitment %
- [x] Add team member: entity search by UEI or company name (not user search)
- [x] `AddTeamMemberRequest` has `UeiSam`, `Role`, `ProposedHourlyRate`, `CommitmentPct`, `Notes`
- [x] `ProspectTeamMemberDto` returns `UeiSam`, `EntityName`, `Role`, `ProposedHourlyRate`, `CommitmentPct`
- [x] Remove team member with confirmation dialog
- [x] Wire to `POST/DELETE /api/v1/prospects/{id}/team-members`

### 50.6 Proposal Management
- [x] Create proposal form (from prospect detail)
- [x] Edit Proposal form for proposal-level fields (status, estimated value, win probability, lessons learned)
- [x] Proposal detail page with milestone tracker
- [x] Create Milestone flow (Phase 14.5 adds the POST endpoint)
- [x] Milestone status update (inline toggle) — milestone display includes `AssignedTo` field
- [x] Document registry (metadata display) — includes `FileSizeBytes`
  - **MVP**: Document metadata registry — displays document title, type, uploaded date, and uploader name. Documents are tracked but not stored in the application.

  > **Competitive Gap**: Without document upload, teams must manage RFP responses, compliance docs, and past performance examples in external tools (Box, Dropbox, SharePoint). This fragments the capture workflow. **Document upload (S3 or local storage) is a high-priority addition for Phase 70 or early post-MVP.** Include: file upload, download, version tracking, and per-document access within the prospect/proposal context.
- [x] Wire to proposal API endpoints
- [x] Breadcrumb: Dashboard > Prospects > [Name] > Proposal #[X]

---

## Verification
- [x] Kanban board loads prospects in correct columns
- [x] Drag-and-drop updates status via API
- [x] Empty Kanban state displays onboarding message for new users
- [x] Invalid drag-and-drop transitions are blocked with toast message
- [x] Create prospect from opportunity search → appears in pipeline
- [x] Duplicate prospect for same NoticeId is prevented with link to existing
- [x] Go/No-Go score displays correctly with criteria breakdown
- [x] Notes and team member CRUD works
- [x] Team members display as companies (entity names with UEI) not users
- [x] Reassign works from detail page (not just list view)
- [x] Proposal milestones can be created and updated
