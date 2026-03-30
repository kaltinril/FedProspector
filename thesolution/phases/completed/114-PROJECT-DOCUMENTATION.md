# Phase 114: Project Documentation Suite

**Status:** COMPLETE (2026-03-29) — all 10 deliverables generated and regenerated with Phase 112–113 content
**Priority:** Medium — essential for onboarding, maintenance, and eventual handoff
**Dependencies:** None (documents current state)

---

## Goal

Produce a complete set of professional documentation covering every layer of the FedProspect system: API reference, user guides, admin guides, database schema, and ETL pipeline documentation. Deliverables are polished Word/PDF/PowerPoint documents suitable for distribution, not just markdown files in the repo.

---

## Deliverable 1: API Reference Documentation

### 1A: OpenAPI Specification (machine-readable)
- **Format:** OpenAPI 3.1 YAML (`docs/api/openapi.yaml`)
- **Content:**
  - All REST endpoints from the C# API controllers
  - Request/response schemas with examples
  - Authentication (httpOnly cookie auth, CSRF)
  - Error response formats (400, 401, 403, 404, 500)
  - Query parameter documentation (pagination, filtering, sorting)
- **Source:** Scan all controllers in `api/src/FedProspector.Api/Controllers/`
- **Auto-generation:** Consider Swashbuckle/NSwag output as starting point, then hand-curate

### 1B: API Engineer's Guide (.docx)
- **Format:** Word document (`docs/api/FedProspect-API-Guide.docx`)
- **Audience:** Developers integrating with or maintaining the API
- **Content:**
  - Architecture overview (ASP.NET Core, EF Core, MySQL, multi-tenancy)
  - Authentication flow (login, cookie lifecycle, CSRF tokens)
  - Multi-tenancy model (shared public data vs org-isolated capture data)
  - Endpoint reference organized by domain:
    - Opportunities (search, detail, pWin, qualification, competitive intel)
    - Awards (search, detail, burn rate, market share, expiring contracts)
    - Entities (search, detail, competitor profile)
    - Prospects (CRUD, pipeline stages, notes, Kanban)
    - Dashboard (stats, notifications, recommended opportunities)
    - Document Intelligence (attachment intel, analysis requests)
    - Admin (orgs, users, invites, roles)
    - Health (status, data freshness)
  - Request/response examples for each endpoint
  - Pagination patterns (offset-based, cursor-based)
  - Error handling conventions
  - Rate limiting and performance considerations
  - Service layer architecture (Controller → Service → EF Core → MySQL)

---

## Deliverable 2: User Guide (.docx)

- **Format:** Word document (`docs/user/FedProspect-User-Guide.docx`)
- **Audience:** End users (business development / capture managers)
- **Content:**
  - Getting started: first login, password change, navigation overview
  - Dashboard: understanding stats cards, recent activity, recommended opportunities
  - Opportunity Search:
    - Search filters (keyword, NAICS, set-aside, date range, agency, etc.)
    - Understanding search results grid (columns, sorting, inline scores)
    - Saving and managing saved searches
    - URL sharing (search state in URL)
  - Opportunity Detail:
    - Overview tab (key fields, resource links, description)
    - Qualification & pWin tab (pWin gauge, qualification checklist, scoring)
    - Competitive Intelligence tab (incumbent analysis, market share, vulnerability signals)
    - Document Intelligence tab (attachment analysis, extracted intel, AI enhancement)
    - History tab (modification tracking)
    - Actions tab (prospect management, notes)
  - Award Search & Detail:
    - Finding past awards, understanding award data
    - Burn rate analysis
    - Expiring contracts view
  - Entity Search & Detail:
    - Looking up contractors/vendors
    - Competitor profiles
  - Prospect Pipeline:
    - Adding opportunities to pipeline
    - Kanban board (pipeline stages)
    - Notes and status tracking
  - Notifications:
    - Types of notifications
    - Notification preferences
  - Tips & Best Practices:
    - Effective search strategies for WOSB/8(a) opportunities
    - Using competitive intelligence to improve win probability
    - Building a prospect pipeline workflow

---

## Deliverable 3: Admin Guide (.docx)

- **Format:** Word document (`docs/admin/FedProspect-Admin-Guide.docx`)
- **Audience:** System administrators and organization admins
- **Content:**
  - Organization Management:
    - Creating organizations
    - Organization settings (NAICS codes, set-aside eligibility, capabilities)
    - Managing org entity links (linking org to SAM.gov entity records)
  - User Management:
    - Inviting users to an organization
    - Role management (sysadmin, org_admin, member)
    - Disabling/enabling user accounts
    - Password resets and forced password changes
  - System Administration (CLI):
    - Starting/stopping services (`fed_prospector.bat start|stop|restart|status all|db|api|ui`)
    - Daily data load (`daily_load.bat`)
    - Manual data loads (opportunities, awards, entities, USASpending)
    - Attachment pipeline management
    - Health checks and monitoring (`health check`, `health status`)
    - Database maintenance (`health maintain-db`)
  - Data Management:
    - Understanding data sources (SAM.gov, USASpending, GSA CALC+, Federal Hierarchy)
    - Data freshness and update schedules
    - API key management (SAM.gov key 1 vs key 2, rate limits)
    - Troubleshooting data quality issues
  - Monitoring & Troubleshooting:
    - ETL load logs and error tracking
    - Common issues and resolutions
    - Log file locations and interpretation

---

## Deliverable 4: Database Documentation

### 4A: Schema Reference (.xlsx)
- **Format:** Excel workbook (`docs/database/FedProspect-Schema-Reference.xlsx`)
- **Content (one sheet per logical group):**
  - **Opportunity Tables:** opportunity, opportunity_attachment (lean join: notice_id, attachment_id, url), sam_attachment, attachment_document, document_intel_summary, document_intel_evidence, opportunity_attachment_summary, opportunity_modification
  - **Award Tables:** award, subaward
  - **Entity Tables:** entity, entity_exclusion, entity_poi
  - **Reference Tables:** naics_code, psc_code, set_aside_type, sba_type, fips_state, fips_county, federal_hierarchy
  - **ETL Tables:** etl_load_log, etl_load_error, etl_data_quality_rule, data_load_request
  - **Application Tables:** app_user, organization, org_member, org_naics, org_set_aside, org_entity_link, prospect, prospect_note, saved_search, notification, user_invite
  - **Views:** List all database views with their purpose and source tables
  - Each sheet has columns: Column Name, Data Type, Nullable, Default, Description, Index, Notes
- **Source:** Parse DDL files in `fed_prospector/db/schema/` and EF Core models in `api/src/FedProspector.Core/Models/`

### 4B: Entity Relationship Diagram (.pptx)
- **Format:** PowerPoint (`docs/database/FedProspect-ERD.pptx`)
- **Content:**
  - Slide 1: High-level domain overview (Opportunities <-> Awards <-> Entities, with Application tables)
  - Slide 2: Opportunity domain (opportunity + attachments + intel + modifications)
  - Slide 3: Award domain (award + subaward)
  - Slide 4: Entity domain (entity + exclusions + POIs)
  - Slide 5: Application domain (users, orgs, prospects, saved searches)
  - Slide 6: ETL/operational tables (load logs, quality rules, data load requests)
  - Slide 7: Reference data tables
  - Use boxes for tables, lines for relationships, color-coding by domain
  - Include cardinality annotations (1:N, M:N)
- **Note:** Diagrams will be text-based layouts in PowerPoint — not auto-generated ER diagrams

### 4C: Data Dictionary (.docx)
- **Format:** Word document (`docs/database/FedProspect-Data-Dictionary.docx`)
- **Content:**
  - Table-by-table documentation with:
    - Purpose and description
    - Ownership (Python DDL vs EF Core)
    - Key columns and their business meaning
    - Relationships to other tables
    - Data source (which API/loader populates it)
    - Row count ranges and growth expectations
    - Change detection strategy (hash-based? timestamp-based?)

---

## Deliverable 5: ETL Pipeline Documentation

### 5A: Pipeline Architecture (.pptx)
- **Format:** PowerPoint (`docs/etl/FedProspect-ETL-Architecture.pptx`)
- **Content:**
  - Slide 1: System overview — data sources -> Python ETL -> MySQL -> C# API -> React UI
  - Slide 2: Data source inventory (SAM.gov Opportunities, SAM.gov Awards, SAM.gov Entities, USASpending Bulk, USASpending API, GSA CALC+, Federal Hierarchy, SAM.gov Exclusions)
  - Slide 3: Daily load pipeline flowchart (all 10 steps from daily_load.bat)
  - Slide 4: Attachment intelligence pipeline (download -> extract text -> keyword intel -> AI analysis -> cleanup)
  - Slide 5: Change detection strategy (SHA-256 hashing, staging tables, upsert logic)
  - Slide 6: Rate limiting and API key strategy
  - Slide 7: Error handling and recovery (load logs, resumable loads, retry logic)
  - Slide 8: Data quality rules engine
  - Slide 9: Bulk loading strategy (LOAD DATA INFILE, DAT files, staging tables)
  - Slide 10: On-demand loading (data_load_request table, demand processing)

### 5B: Loader Reference (.docx)
- **Format:** Word document (`docs/etl/FedProspect-Loader-Reference.docx`)
- **Content per loader:**
  - Loader name and CLI command
  - Data source and API endpoint
  - Tables populated
  - Load strategy (full vs incremental, bulk vs API)
  - Rate limits and API key requirements
  - Staging table usage
  - Change detection method
  - CLI options and examples
  - Common issues and troubleshooting
- **Loaders to document:**
  - Opportunity loader (SAM.gov)
  - Award loader (SAM.gov)
  - Entity loader (SAM.gov)
  - USASpending bulk loader
  - USASpending API loader
  - GSA CALC+ loader
  - Federal hierarchy loader
  - Exclusion loader
  - Subaward loader
  - Attachment downloader
  - Attachment text extractor
  - Attachment intel extractor
  - Resource link resolver
  - On-demand award loader

### 5C: Data Flow Diagrams (.pptx)
- **Format:** PowerPoint (`docs/etl/FedProspect-Data-Flows.pptx`)
- **Content:**
  - One slide per major data flow:
    - SAM.gov Opportunity: API -> raw staging -> opportunity table -> resource links -> attachments
    - SAM.gov Awards: API -> raw staging -> award table
    - SAM.gov Entities: Bulk extract -> DAT file -> LOAD DATA INFILE -> entity table
    - USASpending Bulk: Download ZIP -> CSV -> LOAD DATA INFILE -> staging -> award table
    - Attachment Pipeline: URL -> HEAD enrichment -> download -> text extract -> keyword intel -> AI analysis
    - On-Demand Loading: UI request -> data_load_request -> Python poller -> targeted API call -> DB update
  - Show data transformations, staging tables, and final destinations
  - Include volume estimates and timing

---

## Deliverable Summary

| # | Deliverable | Format | Output Path |
|---|------------|--------|-------------|
| 1A | OpenAPI Specification | YAML | `docs/api/openapi.yaml` |
| 1B | API Engineer's Guide | .docx | `docs/api/FedProspect-API-Guide.docx` |
| 2 | User Guide | .docx | `docs/user/FedProspect-User-Guide.docx` |
| 3 | Admin Guide | .docx | `docs/admin/FedProspect-Admin-Guide.docx` |
| 4A | Schema Reference | .xlsx | `docs/database/FedProspect-Schema-Reference.xlsx` |
| 4B | Entity Relationship Diagram | .pptx | `docs/database/FedProspect-ERD.pptx` |
| 4C | Data Dictionary | .docx | `docs/database/FedProspect-Data-Dictionary.docx` |
| 5A | Pipeline Architecture | .pptx | `docs/etl/FedProspect-ETL-Architecture.pptx` |
| 5B | Loader Reference | .docx | `docs/etl/FedProspect-Loader-Reference.docx` |
| 5C | Data Flow Diagrams | .pptx | `docs/etl/FedProspect-Data-Flows.pptx` |

---

## Current State (as of 2026-03-29)

All 10 deliverables were initially generated on **March 22, 2026** with Python generator scripts in each `docs/` subdirectory. However, Phases 112 and 113 landed after generation:

### Gaps to Address in Regeneration

**Phase 112 — Opportunity Description Backfill (March 28):**
- **API Guide (1B):** Add `POST /api/v1/opportunities/{noticeId}/fetch-description` endpoint
- **OpenAPI (1A):** Add fetch-description endpoint schema
- **User Guide (2):** Add "Fetch Description from SAM.gov" button on Opportunity Detail Overview tab
- **Admin Guide (3):** Add `update fetch-descriptions` CLI command, daily_load.bat integration
- **Loader Reference (5B):** Add description backfill loader documentation

**Phase 113 — Federal Hierarchy Browser (March 29):**
- **API Guide (1B):** Add all `FederalHierarchyController` endpoints (search, detail, children, tree, opportunities, refresh, refresh/status)
- **OpenAPI (1A):** Add hierarchy endpoint schemas
- **User Guide (2):** Add Federal Hierarchy Browse page, Organization Detail page, tree navigation, search
- **Admin Guide (3):** Add hierarchy refresh panel (admin-only), API key selection, refresh status monitoring
- **Schema Reference (4A):** Verify `federal_hierarchy` and `data_load_request` tables documented
- **Data Dictionary (4C):** Add `data_load_request` table documentation if missing
- **ERD (4B):** Verify hierarchy relationships shown
- **ETL Architecture (5A):** Add on-demand refresh flow (data_load_request → poller → hierarchy API)
- **Data Flows (5C):** Add hierarchy refresh data flow slide

### Regeneration Strategy

For each deliverable:
1. Update the generator script (`generate_*.py`) to include new content
2. Re-run the generator to produce updated output file
3. Verify the output includes Phase 112/113 content

## Implementation Notes

- All output goes to `docs/` at project root (not in `thesolution/`)
- Use Claude Code skills for document generation: `/docx`, `/pptx`, `/xlsx`, `/pdf`
- Documents should be professional quality — suitable for client/stakeholder distribution
- Each deliverable can be produced independently (no ordering dependency)
- Source all content from actual code, not assumptions — read controllers, models, CLI commands, DDL files
- Include screenshots or placeholder references for UI documentation where relevant
- Version-stamp each document with generation date
- Generator scripts live alongside their output in `docs/` subdirectories

---

## Task Summary

| # | Task | Complexity | Format |
|---|------|-----------|--------|
| 1A | OpenAPI Specification | Medium | YAML |
| 1B | API Engineer's Guide | High | .docx |
| 2 | User Guide | High | .docx |
| 3 | Admin Guide | Medium | .docx |
| 4A | Schema Reference | Medium | .xlsx |
| 4B | Entity Relationship Diagram | Medium | .pptx |
| 4C | Data Dictionary | High | .docx |
| 5A | Pipeline Architecture | Medium | .pptx |
| 5B | Loader Reference | High | .docx |
| 5C | Data Flow Diagrams | Medium | .pptx |
