# Phase 96: Intelligence-First UI — Surface Automated Matching

## Status: COMPLETE

## Problem
FedProspect has substantial backend intelligence (recommended opportunity scoring, expiring contract detection, auto-prospect generation) that is either invisible in the UI or buried under "Research." The automated intelligence should be front and center; manual research should be secondary.

## Deliverables

### Deliverable 0: Mission Statement Document
- **Created**: `thesolution/MISSION.md`
- Synthesized project purpose from all phase history, MASTER-PLAN.md, and reference docs
- Sections: Mission, Who We Serve, Core Value Proposition, How It Works, Competitive Advantage

### Deliverable 1: Sidebar Restructure — Pipeline First
- **Modified**: `ui/src/components/layout/Sidebar.tsx`
- Moved Pipeline section above Research in navigation
- Added "Recommended" as first Pipeline item → `/opportunities/recommended`
- Moved "Expiring Contracts" from Research to Pipeline
- Pipeline now shows: Recommended, Expiring Contracts, Prospects
- Research now shows: Opportunities, Awards, Entities, Teaming

### Deliverable 2: Recommended Opportunities Page
- **Created**: `ui/src/pages/recommendations/RecommendedOpportunitiesPage.tsx`
- **Modified**: `ui/src/routes.tsx`
- Full page at `/opportunities/recommended` displaying scored, ranked opportunities
- Columns: Title, Agency, NAICS, Set-Aside, Est. Value, Deadline, Days Left, Score, Recompete
- Colored chips for pWin score (green ≥70, warning ≥40, red <40) and days remaining
- Limit selector (10/25/50), responsive columns, empty state with org setup link
- Reuses existing backend: `RecommendedOpportunityService`, `GET /api/v1/opportunities/recommended`

### Deliverable 3: Dashboard Intelligence Widgets
- **Modified**: `ui/src/pages/dashboard/DashboardPage.tsx`
- Added "Top Recommendations" widget (7-col): top 5 scored opportunities with pWin chips
- Added "Expiring Soon" widget (5-col): top 5 expiring contracts with months-remaining chips
- Both have "View All" links to full pages
- Loading skeletons and empty states
- No backend changes — uses existing endpoints via two additional `useQuery` calls

## Files Changed

| Action | File |
|--------|------|
| CREATE | `thesolution/MISSION.md` |
| CREATE | `ui/src/pages/recommendations/RecommendedOpportunitiesPage.tsx` |
| MODIFY | `ui/src/components/layout/Sidebar.tsx` |
| MODIFY | `ui/src/routes.tsx` |
| MODIFY | `ui/src/pages/dashboard/DashboardPage.tsx` |

## Verification
1. Sidebar shows PIPELINE section with Recommended, Expiring Contracts, Prospects
2. `/opportunities/recommended` loads scored opportunities table
3. Dashboard shows Top Recommendations and Expiring Soon widgets
4. Click-through navigation works (row → detail, "View all" → full page)
5. TypeScript compiles cleanly
