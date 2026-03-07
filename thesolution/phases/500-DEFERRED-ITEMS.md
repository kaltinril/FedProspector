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
