# Phase 500: Deferred Items

**Status**: BACKLOG
**Purpose**: Parking lot for work that was scoped but intentionally deferred. Pick up as needed.

## Items

### 500A: Auto-FPDS Enrichment (from Phase 44B)

**Original phase**: 44B
**Deferred because**: On-demand FPDS loading via Phase 43 demand_loader is sufficient for current usage.

**Scope**:
1. Extend demand_loader to process FPDS requests in batches (not just single awards)
2. Add a priority queue: awards viewed by users get enriched first
3. Background nightly job: enrich remaining awards within daily rate budget
4. Add `fpds_enriched_at` timestamp tracking (column already exists on `usaspending_award`)

**Estimated effort**: ~1 day

---

### 500B: Rate Budget Reallocation (from Phase 44D)

**Original phase**: 44D
**Deferred because**: Config-only change, no urgency until load volumes increase.

**Scope**:
1. Define new daily call budgets: Opportunities 500/day, Entity updates 200/day, Subaward analysis 200/day, On-demand FPDS 100/day
2. Update rate budget configuration to enforce the new allocations

**Estimated effort**: ~0.5 days

---

### 500C: Security Hardening for Production (from Phase 80)

**Original phase**: 80
**Deferred because**: Single-developer local-dev setup. Not needed until staging/production prep.

See [80-SECURITY-HARDENING.md](80-SECURITY-HARDENING.md) for full details. Items include:
- Production AllowedHosts configuration
- JWT secret replacement
- Token lifetime tuning
- HTTPS enforcement
- CORS lockdown

---

### 500D: EF Core Navigation Properties (from Phase 44.5)

**Original phase**: 44.5
**Deferred because**: Pure internal refactor. `.Include()` is nicer than manual joins but changes zero user behavior. Do when touching these services for feature work.

**Scope**:
1. **Vendor/Recipient Entity navigations** (4 nav props): `FpdsContract.VendorUei`, `UsaspendingAward.RecipientUei`, `SamSubaward.SubUei`, `SamSubaward.PrimeUei` -> `Entity`
2. **Reference table navigations** (4 ref tables, ~12 models): NAICS, SetAside, BusinessType, CountryCode. PSC and State stay manual (composite PKs).
3. **Opportunity-to-Award chain**: `SolicitationNumber` joins — may keep manual due to non-key joins and filtering requirements.
4. **Award-to-Subaward chain**: `PrimePiid` -> `ContractId` — needs alternate key investigation.
5. **Contracting Office to Fed Hierarchy**: Blocked until office-level orgs loaded and code matching investigated.

**What NOT to change**: No DB-level FK constraints on ETL tables, no EF migrations for ETL tables, no `[ForeignKey]` annotations (Fluent API only), no inverse collection navigations unless needed, PSC/State lookups stay manual.

**Estimated effort**: ~3 days

---

### 500E: Entity POC Normalization (from Phase 44.10)

**Original phase**: 44.10
**Deferred because**: Data bloat and maintenance issue, not blocking any features.

**Problem**: `entity_poc` table stores denormalized POC data — same person (e.g., "Teri Hamilton") duplicated across hundreds of rows (one per entity+poc_type). Table is larger than `entity` itself (~750K+ rows).

**Proposed fix**: Normalize into `contact` (one row per unique person) + `entity_contact` (M:M junction with poc_type). Massive dedup, single update point, enables contact-level features.

**Key risks**: Stale link detection harder with normalized data, natural key ambiguity for NULL-email contacts, migration complexity for 750K+ existing rows, loader complexity increase.

**Research needed before starting**:
- Actual dedup ratio (unique contacts vs total rows)
- Best natural key for dedup
- C# API / view dependencies on entity_poc
- Orphaned contact strategy

**Files affected**: DDL (new tables), `entity_loader.py` (rewrite POC loading), C# API (any entity_poc reads), migration script.

**Estimated effort**: ~2-3 days

---

### 500F: Entity Search Performance (from Phase 44.11)

**Original phase**: 44.11
**Deferred because**: Bundled into Phase 45 work or pick up standalone when search perf becomes a priority.

**Problem**: Entity search uses `LIKE '%term%'` (leading wildcard) against 700K+ rows — full table scan, runs twice (COUNT + paginated results).

**Fixes**:
1. Add `FULLTEXT INDEX ft_entity_name (legal_business_name)` on `entity` table
2. Switch `EntityService.SearchAsync()` to `MATCH ... AGAINST` for 3+ char terms, LIKE fallback for short terms
3. Eliminate double scan with `COUNT(*) OVER()` window function

**Files**: `20_entity.sql` (DDL), `EntityService.cs` (query), live DB ALTER.

**Estimated effort**: ~0.5 days

---

### 500H: Database Denormalization Audit & Efficiency Pass

**Original phase**: Ongoing observation
**Deferred because**: Not blocking features, but storage/perf debt is growing.

**Problem**: Multiple tables store heavily duplicated data because ETL loads denormalize everything for simplicity. Examples:
- **entity_poc** (500E above): Same person duplicated hundreds of times across entities
- **opportunity amendments**: Same solicitation stored as N separate full rows instead of one canonical record + lightweight amendment deltas
- **opportunity_poc**: Likely same duplication pattern as entity_poc
- **Department/agency/office strings**: Repeated verbatim on every opportunity and award row instead of FK to a fed_hierarchy lookup
- **NAICS descriptions, set-aside descriptions**: Stored inline on every record instead of joined from ref tables at query time

**Proposed approach**:
1. Audit all tables for row counts vs unique logical entities
2. Identify top 5 worst offenders by wasted storage
3. Normalize iteratively: contacts first (500E), then agency strings, then opportunity amendments
4. Update loaders to upsert into normalized structure
5. Update C# API queries to join instead of reading denormalized columns

**Key constraint**: ETL tables have no EF migrations — DDL is owned by Python. C# reads via raw model mappings.

**Estimated effort**: ~5-7 days total (spread across multiple iterations)

---

### 500G: Wire Qualification Checklist to Org Profile (from Phase 45/50)

**Original phase**: Gap between Phase 20 (org profile setup), Phase 45 (intelligence endpoints), and Overview tab
**Deferred because**: Tab 2 (Qualification & pWin) already calls the real endpoint. Overview tab still has hardcoded placeholder.

**Scope**:
1. Replace hardcoded `QualificationChecklist` in `OpportunityDetailPage.tsx` Overview tab with a call to `GET /opportunities/{noticeId}/qualification`
2. Show loading/error states inline while the endpoint responds
3. Investigate whether org profile data (NAICS, certifications, past performance from setup wizard) is actually being used by the qualification endpoint or if it's also returning placeholder data

**Files**: `ui/src/pages/opportunities/OpportunityDetailPage.tsx` (Overview tab), qualification endpoint in C# backend.

**Estimated effort**: ~0.5 days
