# Phase 19: Dashboard, Saved Searches & Notifications

**Status**: NOT STARTED
**Dependencies**: Phase 18 (Capture Management)
**Deliverable**: Executive dashboard, saved search management with alerts, notification center
**Repository**: `ui/src/pages/`

---

## Overview

Build the "home base" experience — the dashboard users see when they log in, the saved searches that automate discovery, and the notification system that surfaces new opportunities and deadlines.

**User workflow this enables:**
> "I log in every morning, see my pipeline at a glance, check if any new NAICS 621111 opportunities appeared overnight, and review deadlines for the week."

---

## Pages

### Dashboard (`/dashboard` — default landing page)

**Layout: Card-based grid**

**Row 1: Key Metrics (4 stat cards)**
- Total open prospects (count)
- Due this week (count, red if overdue)
- Win rate (% of WON vs total outcomes)
- Pipeline value (sum of estimated values)

**Row 2: Pipeline Overview**
- Prospect status funnel chart (LEAD → QUALIFIED → PURSUING → SUBMITTED)
- Click a stage → navigate to pipeline filtered by that status

**Row 3: Two-column layout**
- **Left: Due This Week** (table of opportunities with deadlines in next 7 days)
  - Title, deadline (countdown), assigned user, status
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
- Actions per row: Run, Edit, Delete
- "New Saved Search" button

**Create/Edit Saved Search Dialog:**
- Search name
- Description
- Filter criteria (same filter components as opportunity search):
  - NAICS, set-aside, keyword, agency, state, days out
- Enable notifications toggle
- Save → `POST /api/v1/saved-searches`

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
- Click notification → navigate to relevant entity (opportunity, prospect, etc.)
- "Mark all as read" button
- Filter: unread only, by type

**Top Bar Integration:**
- Bell icon in top bar with unread count badge
- Dropdown shows last 5 notifications
- "View all" link → notification center page

---

## Tasks

### 19.1 Dashboard Page
- [ ] Build card-based dashboard layout
- [ ] Key metrics stat cards (open prospects, due this week, win rate, pipeline value)
- [ ] Pipeline funnel chart (Recharts)
- [ ] Due this week table (sortable by deadline)
- [ ] Workload by assignee bar chart
- [ ] Win/loss metrics chart
- [ ] Recent saved searches with result counts
- [ ] Wire to `GET /api/v1/dashboard`
- [ ] Auto-refresh on 5-minute interval

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
- [ ] Pipeline chart clickable → navigates to filtered pipeline
- [ ] Saved search create/run/delete flow works end-to-end
- [ ] Notifications display and mark-as-read works
- [ ] Notification bell shows correct unread count
- [ ] Due this week shows correct opportunities
