# Federal Contract Prospecting System - Master Plan

## Mission

B2B SaaS platform helping companies discover, evaluate, and win federal contracts — focused on WOSB and 8(a) set-aside opportunities. Gathers data from 10+ government APIs, normalizes into MySQL, and provides web-based search, competitive intelligence, and pipeline management.

## Background

Replaces a prior Salesforce CRM approach that hit CPU/transaction limits at 1M+ entity records. This system uses Python ETL + MySQL + C# ASP.NET Core API + React UI, with per-organization data isolation for multi-tenant SaaS.

## Key Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Database | MySQL 8.0+ (local) | No licensing cost. Full SQL capability. |
| Data Gathering | Python 3.14 | Rich ecosystem for REST/SOAP/CSV/JSON. |
| Bulk Loads | DAT + LOAD DATA INFILE | Fastest MySQL loading path. |
| Change Detection | SHA-256 record hashing | Compare one hash instead of 100+ fields. |
| Rate Limit Strategy | Bulk extracts first, API for incremental | Monthly extract = 1 call for all entities. |
| Credentials | `.env` + python-dotenv | Never hardcode. |
| Web API | ASP.NET Core (.NET 10) | Type-safe, high-perf backend. EF Core for MySQL. |
| Frontend | Vite 7 + React 19 + TypeScript + MUI v7 | Modern stack, enterprise component library. |
| Multi-Tenancy | Shared public data + org-isolated capture data | Government data shared; prospects/proposals private per company. |

## Phase Roadmap

> Completed phase docs are in `phases/completed/`. Only load them for historical research.

| Phase | Name | Status | Document |
|-------|------|--------|----------|
| 1 | Foundation | COMPLETE | [01-FOUNDATION.md](phases/completed/01-FOUNDATION.md) |
| 2 | Entity Data Pipeline | COMPLETE | [02-ENTITY-PIPELINE.md](phases/completed/02-ENTITY-PIPELINE.md) |
| 3 | Opportunities Pipeline | COMPLETE | [03-OPPORTUNITIES-PIPELINE.md](phases/completed/03-OPPORTUNITIES-PIPELINE.md) |
| 4 | Sales/Prospecting Pipeline | COMPLETE | [04-SALES-PROSPECTING.md](phases/completed/04-SALES-PROSPECTING.md) |
| 5 | Extended Data Sources | COMPLETE | [05-EXTENDED-SOURCES.md](phases/completed/05-EXTENDED-SOURCES.md) |
| 6 | Automation & Monitoring | COMPLETE | [06-AUTOMATION.md](phases/completed/06-AUTOMATION.md) |
| 7 | Reference Data Enrichment | COMPLETE | [07-REFERENCE-ENRICHMENT.md](phases/completed/07-REFERENCE-ENRICHMENT.md) |
| 8 | Web/API Readiness | COMPLETE | [08-WEB-API-READINESS.md](phases/completed/08-WEB-API-READINESS.md) |
| 9 | Schema Evolution | COMPLETE | [09-SCHEMA-EVOLUTION.md](phases/completed/09-SCHEMA-EVOLUTION.md) |
| 10 | C# API Foundation | COMPLETE | [10-API-FOUNDATION.md](phases/completed/10-API-FOUNDATION.md) |
| 11 | Read-Only Query Endpoints | COMPLETE | [11-READ-ENDPOINTS.md](phases/completed/11-READ-ENDPOINTS.md) |
| 12 | Capture Management API | COMPLETE | [12-CAPTURE-MANAGEMENT-API.md](phases/completed/12-CAPTURE-MANAGEMENT-API.md) |
| 13 | Auth, Notifications & Production | COMPLETE | [13-AUTH-AND-PRODUCTION.md](phases/completed/13-AUTH-AND-PRODUCTION.md) |
| 14 | Testing Strategy | COMPLETE | [14-TESTING.md](phases/completed/14-TESTING.md) |
| 14.5 | Multi-Tenancy & Security | COMPLETE | [14.5-MULTI-TENANCY-SECURITY.md](phases/completed/14.5-MULTI-TENANCY-SECURITY.md) |
| 14.6 | Admin Operability | COMPLETE | [14.6-ADMIN-OPERABILITY.md](phases/completed/14.6-ADMIN-OPERABILITY.md) |
| 14.7 | CLI Command Hierarchy | COMPLETE | [14.7-CLI-HIERARCHY.md](phases/completed/14.7-CLI-HIERARCHY.md) |
| 14.8 | Architecture Compliance | COMPLETE | [14.8-ARCHITECTURE-COMPLIANCE.md](phases/completed/14.8-ARCHITECTURE-COMPLIANCE.md) |
| 14.9 | Raw Staging for All Loaders | COMPLETE | [14.9-RAW-STAGING.md](phases/completed/14.9-RAW-STAGING.md) |
| 14.10 | ETL Loader DRY Refactor | COMPLETE | [14.10-ETL-REFACTOR-DRY.md](phases/completed/14.10-ETL-REFACTOR-DRY.md) |
| 14.11 | CLI DRY Refactor + Bug Fixes | COMPLETE | [14.11-CLI-REFACTOR-DRY.md](phases/completed/14.11-CLI-REFACTOR-DRY.md) |
| 14.12 | API Client DRY Refactor | COMPLETE | [14.12-API-CLIENTS-REFACTOR-DRY.md](phases/completed/14.12-API-CLIENTS-REFACTOR-DRY.md) |
| 14.13 | ETL Loader Bug Fixes | COMPLETE | [14.13-ETL-BUG-FIXES.md](phases/completed/14.13-ETL-BUG-FIXES.md) |
| 14.14 | Schema Fixes | COMPLETE | [14.14-SCHEMA-FIXES.md](phases/completed/14.14-SCHEMA-FIXES.md) |
| 14.15 | C# API Bug Fixes | COMPLETE | [14.15-CSHARP-API-BUG-FIXES.md](phases/completed/14.15-CSHARP-API-BUG-FIXES.md) |
| 14.16 | Test Coverage Gaps | COMPLETE | [14.16-TEST-COVERAGE.md](phases/completed/14.16-TEST-COVERAGE.md) |
| 14.20 | Code Fixes & Doc Sweep | COMPLETE | [14.20-CODE-FIXES-AND-DOC-SWEEP.md](phases/completed/14.20-CODE-FIXES-AND-DOC-SWEEP.md) |
| 14.22 | Security Hardening | COMPLETE | [14.22-SECURITY-HARDENING.md](phases/completed/14.22-SECURITY-HARDENING.md) |
| 14.24 | DDL Consolidation | COMPLETE | [14.24-DDL-CONSOLIDATION.md](phases/completed/14.24-DDL-CONSOLIDATION.md) |
| 14.25 | Vendor API Loader Audit | COMPLETE | [14.25-LOADER-AUDIT-FIXES.md](phases/completed/14.25-LOADER-AUDIT-FIXES.md) |
| 14.26 | Resumable Paginated Loads | COMPLETE | [14.26-RESUMABLE-PAGINATED-LOADS.md](phases/completed/14.26-RESUMABLE-PAGINATED-LOADS.md) |
| 15 | Subaward Data Strategy | COMPLETE | [15-SUBAWARD-STRATEGY.md](phases/completed/15-SUBAWARD-STRATEGY.md) |
| 16 | Stabilization | COMPLETE | [16-STABILIZATION.md](phases/completed/16-STABILIZATION.md) |
| 19 | UI Phase Review | COMPLETE | [19-UI-PHASE-REVIEW.md](phases/completed/19-UI-PHASE-REVIEW.md) |
| 20 | UI Foundation & Layout | COMPLETE | [20-UI-FOUNDATION.md](phases/completed/20-UI-FOUNDATION.md) |
| 20.1 | Tech Stack Upgrade | COMPLETE | [20.1-TECH-STACK-UPGRADE.md](phases/completed/20.1-TECH-STACK-UPGRADE.md) |
| 30 | Search & Discovery | COMPLETE | [30-SEARCH-DISCOVERY.md](phases/completed/30-SEARCH-DISCOVERY.md) |
| 31 | Security Audit | COMPLETE | [31-SECURITY-AUDIT.md](phases/completed/31-SECURITY-AUDIT.md) |
| 40 | Detail Views & Intelligence | COMPLETE | [40-DETAIL-INTELLIGENCE.md](phases/completed/40-DETAIL-INTELLIGENCE.md) |
| 41 | Detail View Fixes | COMPLETE | [41-DETAIL-VIEW-FIXES.md](phases/completed/41-DETAIL-VIEW-FIXES.md) |
| 42 | CLI/API Query Standardization | COMPLETE | [42-CLI-API-STANDARDIZATION.md](phases/completed/42-CLI-API-STANDARDIZATION.md) |
| 43 | On-Demand Award Loading | COMPLETE | [43-ON-DEMAND-AWARD-LOADING.md](phases/completed/43-ON-DEMAND-AWARD-LOADING.md) |
| 44 | USASpending-First Loading | COMPLETE | [44-USASPENDING-FIRST-LOADING-STRATEGY.md](phases/completed/44-USASPENDING-FIRST-LOADING-STRATEGY.md) |
| 44.1 | EF Core Column Mapping Fixes | COMPLETE | [44.1-EF-CORE-COLUMN-MAPPING-FIXES.md](phases/completed/44.1-EF-CORE-COLUMN-MAPPING-FIXES.md) |
| 44.2 | Resource Link Metadata | COMPLETE | [44.2-RESOURCE-LINK-METADATA.md](phases/completed/44.2-RESOURCE-LINK-METADATA.md) |
| 44.3 | Data Enrichment Opportunities | COMPLETE | [44.3-DATA-ENRICHMENT-OPPORTUNITIES.md](phases/completed/44.3-DATA-ENRICHMENT-OPPORTUNITIES.md) |
| 44.4 | USASpending Bulk Loader Fixes | COMPLETE | [44.4-USASPENDING-BULK-LOADER-FIXES.md](phases/completed/44.4-USASPENDING-BULK-LOADER-FIXES.md) |
| 44.6 | Schema Drift Remediation | COMPLETE | [44.6-SCHEMA-DRIFT-REMEDIATION.md](phases/completed/44.6-SCHEMA-DRIFT-REMEDIATION.md) |
| 44.7 | Doc Cleanup & Phase Reorg | COMPLETE | [44.7-DOC-CLEANUP-PHASE-REORG.md](phases/completed/44.7-DOC-CLEANUP-PHASE-REORG.md) |
| 44.8 | View Efficiency Fixes | COMPLETE | [44.8-VIEW-EFFICIENCY-FIXES.md](phases/completed/44.8-VIEW-EFFICIENCY-FIXES.md) |
| 44.9 | Multi-Tenancy Code Fixes | COMPLETE | [44.9-MULTI-TENANCY-CODE-FIXES.md](phases/completed/44.9-MULTI-TENANCY-CODE-FIXES.md) |
| 45 | Opportunity Intelligence | COMPLETE | [45-OPPORTUNITY-INTELLIGENCE.md](phases/completed/45-OPPORTUNITY-INTELLIGENCE.md) |
| 50 | Capture Management & Pipeline | COMPLETE | [50-CAPTURE-MANAGEMENT.md](phases/completed/50-CAPTURE-MANAGEMENT.md) |
| 60 | Dashboard & Notifications | COMPLETE | [60-DASHBOARD-NOTIFICATIONS.md](phases/completed/60-DASHBOARD-NOTIFICATIONS.md) |
| 61 | Daily Load CLI | COMPLETE | [61-DAILY-LOAD-CLI.md](phases/completed/61-DAILY-LOAD-CLI.md) |
| 70 | Admin & Organization | NOT STARTED | [70-ADMIN-POLISH.md](phases/70-ADMIN-POLISH.md) |
| 75 | Production Polish | NOT STARTED | [75-PRODUCTION-POLISH.md](phases/75-PRODUCTION-POLISH.md) |
| 80 | Security Hardening | DEFERRED | [80-SECURITY-HARDENING.md](phases/80-SECURITY-HARDENING.md) |
| 500 | Deferred Items | BACKLOG | [500-DEFERRED-ITEMS.md](phases/500-DEFERRED-ITEMS.md) |

## Success Criteria

### Data & ETL
1. Find all active WOSB/8(a) opportunities matching target NAICS codes within seconds
2. Daily opportunity refresh runs automatically via scheduler
3. 500K+ contractor entities available for competitive analysis
4. Change history tracks what changed and when
5. Data quality issues caught and cleaned automatically during load
6. API rate limits never exceeded

### SaaS Product
7. Multiple companies use the system with complete data isolation
8. Company admins can invite team members and manage roles
9. Invite-only registration prevents unauthorized access
10. Competitive intelligence (incumbent analysis, burn rate, market share) unavailable on free government sites
11. Sub-second search across 100K+ opportunities with advanced filtering
12. Team members track prospects through a Kanban pipeline
13. Secure auth with httpOnly cookies, token refresh, and CSRF protection
