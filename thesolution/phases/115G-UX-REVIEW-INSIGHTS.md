# Phase 115G: UX & Review Insights (Brainstorm Gap Analysis)

**Status:** IDEA — from brainstorm analysis, not yet prioritized
**Priority:** TBD
**Source:** C:\git\brainstorm\docs\reviews\ (ux-review, project-manager-review, qa-review)

---

## Summary

The brainstorm project included several professional reviews (UX, QA, project management, security). These are the non-tech-stack findings that apply to FedProspect.

---

## Overlap with Existing Features

| Idea | Status | What Exists |
|------|--------|-------------|
| Score Proliferation Risk | **APPLICABLE** | Currently have pWin (0-100) and qScore/Go-No-Go (0-40). Adding more scores from 115A would compound this. |
| Onboarding → First Pipeline | **PARTIAL** | `CompanySetupWizard` exists. `RecommendedOpportunitiesPage` shows top matches. Missing: guided bridge from setup completion to adding first prospect. |
| Navigation Footprint | **APPLICABLE** | Current sidebar has ~10 items grouped into Pipeline and Research sections. Will grow as features are added. |
| "More Like This" | **PARTIAL** | `RecommendedOpportunityService` scores by org profile match (set-aside + NAICS + time + value). Not similarity-based from a specific opportunity. |
| Multi-Client Consultant | **PARTIAL** | Multi-tenancy works, users can be invited to multiple orgs. Roles: member, admin, SYSTEM_ADMIN. Missing: consultant role, cross-org dashboard, client switching UX. |
| Inline Competitor on Cards | **NEW** | Kanban cards show title, status, deadline, value, pWin. Competitive data only on detail page `CompetitiveIntelTab`. |
| Cross-Source Validation | **NEW** | ETL has per-source data quality rules (`etl_data_quality_rule`). No cross-source reconciliation (SAM↔FPDS↔USASpending). |
| Notification Simplification | **APPLICABLE** | Current system is already simple (4 types, in-app only). Good baseline — keep it simple as we add features. |

---

## UX Insights

### 1. Score Proliferation Risk

The brainstorm defined 9 distinct 0-100 scores. Even with fewer, the risk applies to us:
- **Recommendation:** pWin is the headline metric. qScore is the gate. Everything else should be supporting detail, not a separate number on the grid.
- Don't let scoring become confusing — users want "what should I pursue?" not "here are 7 numbers to interpret."

### 2. Bridge Onboarding to First Pipeline Entry

After onboarding, don't just dump users on the search page. Guide them:
- "Here are your top 5 recommended opportunities — add one to your pipeline to get started"
- Reduce time-to-value from signup to first meaningful action

### 3. Navigation Footprint

The brainstorm ended up with 10+ top-level nav items. Review noted this is too many for non-technical users.
- Our current sidebar is reasonable but will grow as we add features
- Consider grouping: Research (Opportunities, Awards, Entities, Teaming) | Pipeline (Prospects, Recommended, Expiring) | Intelligence (new features) | Admin

### 4. "More Like This" Discovery

On any opportunity, a "More Like This" button that finds similar opportunities by NAICS, agency, scope, and keywords.
- Simple to implement with existing search infrastructure
- High engagement feature — users discover opportunities they wouldn't have searched for

### 5. Multi-Client Consultant Workflow

The brainstorm identified a user persona (Sarah Martinez) who is a proposal consultant managing 3 clients. Our current multi-tenant model supports one org per user.
- Consider: can a user belong to multiple organizations?
- Or: a "consultant" role that can switch between client orgs?
- This is a market segment decision, not just a feature decision

### 6. Inline Competitor Data on Pipeline Cards

Don't make users navigate away from their pipeline to see competitor info. Surface key competitive data directly on pipeline cards:
- Who's the likely incumbent?
- How many competitors are expected?
- What's the incumbent's vulnerability score?

---

## Data Quality Insights

### 7. Cross-Source Validation

The brainstorm designed 10 specific cross-source validation rules (XSV-001 through XSV-010):
- Entity count consistency between SAM.gov API and bulk extract
- Opportunity count alignment between API and database
- Award count alignment between FPDS and USASpending
- Orphan detection (awards referencing non-existent entities)

We have ETL data quality rules but not cross-source validation specifically.

### 8. Data Freshness Dashboard

Beyond our current health check:
- Per-source, per-field completeness metrics
- Anomaly detection: record count changes, volume anomalies, distribution shifts, null rate increases
- Useful for catching data quality issues before they affect users

---

## Review Findings Worth Noting

### 9. Morning Brief Ownership Clarity

The brainstorm had a conflict: both Phase 15 (Saved Searches) and Phase 51 (Notifications) claimed ownership of the Morning Brief email.
- **For us:** If we build Morning Brief (115E #4), decide upfront whether it's part of saved searches or notifications.

### 10. Notification Simplification

The brainstorm designed 20 notification types, 4 priority tiers, 5 channels. The UX review flagged this as overbuilt for small firms.
- **For us:** Start simple. In-app + email is enough. SMS, webhooks, and calendar are power-user features for later.

---

## Implementation Notes

- Items 1-3 are design principles to apply to ALL future work, not standalone features
- "More Like This" (#4) is a quick win
- Multi-client support (#5) is a business/architecture decision — worth discussing before building
- Cross-source validation (#7) strengthens our data quality story
