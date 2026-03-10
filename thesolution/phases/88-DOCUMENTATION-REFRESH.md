# Phase 88 — Documentation Refresh

## Status: PLANNED

**Priority**: LOW
**Depends on**: None (can be done anytime)

---

## Context

Review identified stale references, broken links, outdated counts, and documentation gaps. Fixing these improves developer onboarding and reduces confusion.

---

## Items to Address

### CRITICAL

**88-1 — Broken Phase Link in 500-DEFERRED-ITEMS.md**
File: `thesolution/phases/500-DEFERRED-ITEMS.md:36-41`
Section 500C references `80-SECURITY-HARDENING.md` which doesn't exist. Actual file is `100-SECURITY-HARDENING.md`. Replace `80-SECURITY-HARDENING.md` with `100-SECURITY-HARDENING.md`. Update "Original phase: 80" to "Original phase: 100".

---

### HIGH

**88-2 — Stale "Next Up" in QUICKSTART.md**
File: `thesolution/QUICKSTART.md:193`
States "Next up: Phase 45 (Opportunity Intelligence)" — Phase 45 is COMPLETE. Latest completed: Phase 78. Update to: "See MASTER-PLAN.md for current phase status. Recent: Phases 77-78 complete. Next: Phases 80-88 (review findings)."

**88-3 — credentials.yml Not Gitignored**
File: `thesolution/credentials.yml`
Contains real-format credentials in VCS. Should be example-only. Rename to `credentials.example.yml` with masked values. Add original name to `.gitignore`. Update CLAUDE.md reference.

---

### MEDIUM

**88-4 — Outdated Table Count in 07-DATA-ARCHITECTURE.md**
File: `thesolution/reference/07-DATA-ARCHITECTURE.md:11-16`
Says "40 current tables (growing to 54 in Phase 9)". Phase 9 is COMPLETE. Count may be wrong. Run `SELECT COUNT(*) FROM information_schema.TABLES WHERE TABLE_SCHEMA='fed_contracts'` and update doc.

**88-5 — Contradictory Phase Numbering in 500-DEFERRED-ITEMS.md**
File: `thesolution/phases/500-DEFERRED-ITEMS.md`
References "Original phase: 44.5", "44.10" etc. — no corresponding files exist. Update references to point to correct completed phase docs (e.g., "from Phase 44").

**88-6 — Inconsistent File Path Format in Reference Docs**
Files: `thesolution/reference/03-PYTHON-ARCHITECTURE.md`, `02-DATABASE-SCHEMA.md`
Mix of relative paths (`etl/`), full paths (`fed_prospector/etl/`), and incomplete table lists. Standardize on paths from project root (`fed_prospector/etl/...`).

**88-7 — 02-DATABASE-SCHEMA.md Incomplete**
File: `thesolution/reference/02-DATABASE-SCHEMA.md`
Only documents subset of ref_* tables. Doesn't cover all 35+ actual tables. Add comprehensive table inventory with owner (Python DDL vs EF Core) and status.

---

### LOW

**88-8 — Missing Reference Doc: Backup & Recovery**
No document covers backup procedures, restore steps, or disaster recovery. Create `thesolution/reference/11-BACKUP-AND-RECOVERY.md` after Phase 87 implements backup strategy.

**88-9 — Missing Reference Doc: Authentication & Multi-Tenancy**
No standalone reference doc for auth flow, multi-tenancy model, or RBAC. Covered in completed phase docs (13, 14.5) but not consolidated. Create `thesolution/reference/12-AUTHENTICATION-AND-TENANCY.md` with overview.

**88-10 — CLAUDE.md Missing Phase 100/200 Guidance**
File: `CLAUDE.md:25-39`
"When Working on This Project" doesn't mention that Phases 100/200 are deferred/planned with special handling. Add note: "Phases 100 (Security) and 200 (Normalization) are deferred/planned. Do not start without explicit instruction."

**88-11 — Update MASTER-PLAN.md Phase Table**
File: `thesolution/MASTER-PLAN.md`
Phase table needs to include new phases 80-88 from this review. Add rows for phases 80-88 with PLANNED status.

---

## Verification Checklist

- [ ] 88-1: All internal links resolve — `grep -r "\.md)" thesolution/phases/ | grep -v completed` shows no broken links
- [ ] 88-2: QUICKSTART.md references current phases
- [ ] 88-3: `credentials.yml` in `.gitignore`, renamed to `credentials.example.yml`
- [ ] 88-4: Table counts match reality
- [ ] 88-5: No references to non-existent phase numbers
- [ ] 88-6: All file paths use project-root format
- [ ] 88-7: Database schema doc covers all tables
- [ ] 88-10: CLAUDE.md mentions Phase 100/200 as deferred
- [ ] 88-11: MASTER-PLAN.md phase table includes 80-88
