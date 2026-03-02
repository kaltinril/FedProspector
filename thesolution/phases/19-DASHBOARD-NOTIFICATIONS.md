# Phase 19: Dashboard, Saved Searches & Notifications

**Status**: NOT STARTED
**Dependencies**: Phase 18 (Capture Management)
**Deliverable**: Executive dashboard, saved search management with alerts, notification center
**Repository**: `ui/src/pages/`

---

## Overview

Build the "home base" experience — the dashboard users see when they log in, the saved searches that automate discovery, and the notification system that surfaces new opportunities and deadlines.

**Data scoping:** Dashboard data is scoped to the user's organization.

**User workflow this enables:**
> "I log in every morning, see my pipeline at a glance, check if any new NAICS 621111 opportunities appeared overnight, and review deadlines for the week."

---

## Pages

### Dashboard (`/dashboard` — default landing page)

**Layout: Card-based grid**

**Row 1: Key Metrics (4 stat cards)**
- Total open prospects — `TotalOpenProspects` field from API
- Due this week — computed client-side as `dueThisWeek.length` (count, red if overdue)
- Win rate — computed as `WON / (WON + LOST)` from `winLossMetrics`; handle division-by-zero (show "N/A")
- Pipeline value — sum of estimated values from prospects (may need API addition or client-side computation from pipeline data)

**Row 2: Pipeline Overview**
- Prospect status bar chart (NEW → REVIEWING → PURSUING → BID_SUBMITTED)
- Click a stage → navigate to pipeline filtered by that status

**Row 3: Two-column layout**
- **Left: Due This Week** (table of opportunities with deadlines in next 7 days)
  - Title, deadline (countdown), assigned user, status, priority (`Priority`), set-aside code (`SetAsideCode`)
  - Click → prospect detail
- **Right: Workload by Assignee** (horizontal bar chart)
  - Team members and their prospect counts
  - Helps managers balance workload

**Row 4: Recent Activity**
- Win/loss metrics (simple bar chart: WON vs LOST count)
- Recent saved search results (last 5 searches with new result counts)
  - Click → run saved search

### Saved Searches (`/saved-searches`)

**List View:**
- Table of saved searches: name, description, last run date, new results count, notification enabled toggle
- Actions per row: Run, Edit (uses `PATCH /api/v1/saved-searches/{id}`), Delete
- "New Saved Search" button

**Create/Edit Saved Search Dialog:**
- Search name
- Description
- Filter criteria (matches `SavedSearchFilterCriteria` DTO):
  - `SetAsideCodes` (list), `NaicsCodes` (list), `States` (list)
  - `MinAwardAmount`, `MaxAwardAmount`
  - `OpenOnly` (boolean), `Types` (list), `DaysBack` (number)
- Enable notifications toggle
- Save → `POST /api/v1/saved-searches` (create) or `PATCH /api/v1/saved-searches/{id}` (edit)

**Run Results:**
- Click "Run" → modal/page shows matching opportunities
- New results since last run highlighted
- "Track as Prospect" action on results

### Notification Center (`/notifications`)

**Layout: Feed-style list**
- Notification cards: icon, title, message, timestamp, read/unread status
- Types:
  - New opportunity matching saved search
  - Prospect deadline approaching
  - Prospect status changed
  - Score recalculated
- Click notification → navigate to relevant entity. Routing is based on `EntityType` + `EntityId` (e.g., `EntityType: "opportunity"` + `EntityId: "ABC123"` navigates to `/opportunities/ABC123`)
- **Canonical `EntityType` values** for notification routing: `opportunity` → `/opportunities/{EntityId}`, `award` → `/awards/{EntityId}`, `entity` → `/entities/{EntityId}`, `prospect` → `/prospects/{EntityId}`, `proposal` → `/prospects/{ProspectId}/proposals/{EntityId}`. Values are lowercase, matching route segments.
- "Mark all as read" button
- Filter: unread only, by type
- **Canonical `NotificationType` values** (defined as constants in Phase 14.5): `new_match`, `deadline_approaching`, `status_changed`, `score_recalculated`. UI uses these for icon selection and type filtering.
- Empty state: "You're all caught up!" message when zero notifications

**Top Bar Integration:**
- Bell icon in top bar with unread count badge
- Dropdown shows last 5 notifications
- "View all" link → notification center page

### Notification Mechanism

#### MVP: Polling-Based Notifications

**Top bar bell widget polling**:
- `GET /api/v1/notifications/unread-count` polled every **60 seconds** via TanStack Query `refetchInterval`
- Lightweight endpoint returns `{ unreadCount: number }` only
- Badge updates without full notification list fetch
- Full notification list fetched only when user opens notification dropdown/page

**Saved search automation**:
- Backend job (extends Phase 6 scheduler) runs each saved search with `notifications_enabled = true`
- **Default interval**: Every 4 hours (matches opportunity ETL refresh cycle)
- Job compares current results against `last_run_result_count` — if new matches found, creates `new_match` notification
- "New results" determined by: opportunities with `posted_date` > saved search's `last_run_at`

**Notification creation triggers**:
| Trigger | NotificationType | EntityType | When |
|---------|-----------------|------------|------|
| Saved search finds new matches | `new_match` | `opportunity` | Scheduler job |
| Opportunity deadline within 7 days | `deadline_approaching` | `prospect` | Scheduler job (daily) |
| Prospect status changed by teammate | `status_changed` | `prospect` | On status update API call |
| Go/No-Go score recalculated | `score_recalculated` | `prospect` | On score recalc API call |

#### Future: Real-Time Push (Post-MVP)

- **SignalR WebSocket** for instant notifications without polling
- Reduces server load from N users * 1 request/minute to persistent connections
- Implement when user base exceeds ~50 concurrent users

#### Future: Email Digests (Post-MVP)

- Daily/weekly email summary of new matching opportunities
- Requires email infrastructure (SendGrid/SES) — see Phase 14.5 Known Gap

### Dashboard Metric Definitions

| Metric | Calculation | Edge Cases |
|--------|------------|------------|
| **Total Open Prospects** | Count of prospects WHERE status NOT IN ('WON', 'LOST', 'DECLINED') AND organization_id = user's org | Zero = "No active prospects" |
| **Due This Week** | Count of prospects WHERE linked opportunity's `response_deadline` BETWEEN today AND today + 7 days AND status NOT IN terminal states | Zero = "No upcoming deadlines" |
| **Win Rate** | WON / (WON + LOST) for the organization. Excludes DECLINED (voluntary withdrawal ≠ loss). | Zero denominator = show "N/A" (no completed bids yet) |
| **Pipeline Value** | SUM of `opportunity.base_and_all_options` for all non-terminal prospects in the org. Computed server-side by `DashboardService`. | Null opportunity values excluded from sum. Show "$0" if all values null. |
| **Workload by Assignee** | Count of non-terminal prospects grouped by `assigned_to` user | Unassigned prospects grouped under "Unassigned" |

**"Won" timing**: A prospect is marked WON when the user manually transitions it after receiving the contract award notification. This is a manual action, not auto-detected from FPDS data (auto-detection is a future enhancement).

---

## Tasks

### 19.1 Dashboard Page
- [ ] Build card-based dashboard layout
- [ ] Key metrics stat cards (open prospects, due this week, win rate, pipeline value)
- [ ] Pipeline stage bar chart (@mui/x-charts horizontal bar chart) — @mui/x-charts does not support funnel charts; horizontal stacked bar effectively shows stage progression
- [ ] Due this week table (sortable by deadline)
- [ ] Workload by assignee bar chart
- [ ] Win/loss metrics chart
- [ ] Recent saved searches with result counts
- [ ] Wire to `GET /api/v1/dashboard`
- [ ] Auto-refresh via TanStack Query `refetchInterval: 300000` (5 minutes) with `refetchIntervalInBackground: false`. Pauses when browser tab is not visible.

### 19.2 Saved Search Management
- [ ] Saved search list page
- [ ] Create saved search dialog with filter builder
- [ ] Reuse filter components from opportunity search
- [ ] Run saved search → display results
- [ ] Notification enabled toggle
- [ ] Delete saved search with confirmation
- [ ] Wire to saved search API endpoints

### 19.3 Notification Center
- [ ] Notification feed page (paginated)
- [ ] Notification card component (icon, title, message, timestamp)
- [ ] Click → navigate to relevant entity
- [ ] Mark as read (individual + all)
- [ ] Filter by unread/type
- [ ] Wire to notification API endpoints

### 19.4 Top Bar Notification Widget
- [ ] Bell icon with unread count badge
- [ ] Dropdown with last 5 notifications
- [ ] "View all" link to notification center
- [ ] Poll for new notifications (or use SignalR later)

---

## Verification
- [ ] Dashboard loads with real data from API
- [ ] Dashboard stat card computations are correct (win rate handles zero division, pipeline value sums correctly)
- [ ] Pipeline chart clickable → navigates to filtered pipeline
- [ ] Saved search create/run/delete flow works end-to-end
- [ ] Saved search filter criteria matches API DTO (`SetAsideCodes`, `NaicsCodes`, `States`, etc.)
- [ ] Notifications display and mark-as-read works
- [ ] Notification empty state shows "You're all caught up!" message
- [ ] Notification bell shows correct unread count
- [ ] Notification click routes to correct entity based on `EntityType` + `EntityId`
- [ ] Due this week shows correct opportunities
