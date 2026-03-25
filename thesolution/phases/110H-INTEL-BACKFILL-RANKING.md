# Phase 110H: Intel Backfill Ranking — Frequency-Weighted, Per-Field Selection

**Status:** IN PROGRESS
**Priority:** High — current backfill picks one winner row, ignoring corroborating evidence
**Dependencies:** Phase 110F (expanded patterns — complete)

---

## Summary

Rework the backfill logic so that it selects the best value **per field** rather than picking one winner row per opportunity. Incorporate frequency (how many documents corroborate a finding) as a ranking signal alongside extraction method and confidence.

Currently: backfill picks the single highest-ranked `opportunity_attachment_intel` row (AI > keyword, high > low confidence) and copies all fields from that one row. This means if keyword extraction found "FFP" in 15/20 documents but the AI row (which analyzed 1 doc) has NULL for pricing, pricing doesn't get backfilled.

After: each field is resolved independently using the best available evidence.

---

## Problem

1. **One-row-wins-all** — The current `FIELD(extraction_method) * 100 + FIELD(confidence)` ranking picks a single row. Fields that are NULL on the winning row get skipped even if other rows have good data.

2. **AI isn't always more trustworthy** — For structured/exact fields (pricing_structure, clearance_level, vehicle_type, set-aside type), keyword extraction is pattern-matching against literal text. AI can hallucinate or misinterpret. A keyword match for "FFP" found verbatim in 15 documents is stronger signal than AI analyzing 1 document.

3. **Frequency is ignored** — If keyword extraction found "Secret" clearance in 12 out of 20 documents, that corroboration is a powerful confidence signal. Currently it's treated the same as finding it in 1 document.

---

## Design

### Per-Field Resolution

For each backfill target field on `opportunity`, resolve independently:

| Field | Best Source Logic |
|-------|-------------------|
| `security_clearance_required` | Keyword frequency > AI (literal term matching is reliable) |
| `contract_vehicle_type` | Keyword frequency > AI (acronyms like IDIQ, BPA are exact matches) |
| `pricing_structure` | Keyword frequency > AI (FFP, CPFF, T&M are exact terms) |
| `place_of_performance_detail` | Keyword frequency > AI (on-site, remote, CONUS are exact) |
| `incumbent_name` | AI > keyword (requires sentence parsing, context understanding) |
| `estimated_contract_value` | AI only (requires parsing dollar amounts from context) |

### Frequency-Based Scoring for Keyword Fields

Use `opportunity_intel_source` provenance table to count corroborating matches:

```sql
-- Example: find the most-corroborated pricing_structure value
SELECT field_value, COUNT(DISTINCT attachment_id) as doc_count
FROM opportunity_intel_source
WHERE notice_id = %s AND field_name = 'pricing_structure'
GROUP BY field_value
ORDER BY doc_count DESC
LIMIT 1
```

A value found in 15 documents beats a value found in 1, regardless of whether the 1 came from AI.

### Conflict Resolution

When keyword and AI disagree:
- **Both agree** → strongest signal, use that value
- **Keyword has N>3 corroborations, AI disagrees** → use keyword (volume of evidence)
- **Keyword has 1 match, AI disagrees** → use AI (nuanced analysis beats single pattern match)
- **Only one source has a value** → use whatever is available

### Where to Implement

The ranking logic belongs in `cli/backfill.py` (the bulk backfill command). The inline `_update_opportunity_columns()` calls in the extractor and analyzer should be **removed** per existing project convention (analyzers write to intel tables only; backfill is separate and re-runnable).

---

## Tasks

### Task 1: Remove inline backfill from extractor
- Remove `_update_opportunity_columns()` call (line 558) from `_process_notice()` in `attachment_intel_extractor.py`
- Remove `_resolve_incumbent_for_opportunity()` call (line 564) — this also directly updates `opportunity.incumbent_name` and `incumbent_uei`, which is inline backfill
- Keep the methods intact (don't delete them) but stop calling them from the extraction pipeline
- Note: `attachment_ai_analyzer.py` does NOT have inline opportunity UPDATEs — no changes needed there

### Task 2: Rework backfill query to per-field resolution
- Replace single-row ranking with per-field queries
- For keyword-preferred fields (`clearance_required`, `vehicle_type`, `pricing_structure`, `place_of_performance`): query `opportunity_intel_source` for frequency counting, prefer keyword matches with high corroboration
- For AI-preferred fields (`incumbent_name`): prefer AI rows, fall back to keyword occurrence counting (reuse logic from `_resolve_incumbent_for_opportunity`)
- For AI-only fields (`estimated_contract_value`): use AI rows only
- Implement conflict resolution: keyword N>3 beats AI; keyword N=1 loses to AI; agreement is strongest signal
- Include incumbent UEI resolution (moved from extractor)

### Task 3: CLI improvements
- `--dry-run` should show per-field resolution decisions with reasoning
- `--verbose` should show why each field value was chosen (e.g., "pricing_structure=FFP: keyword found in 15/20 docs")
- Summary stats at end: fields updated by keyword frequency vs AI vs fallback

---

## Code Touchpoints

| File | What to do |
|------|------------|
| `fed_prospector/cli/backfill.py` | Rewrite ranking logic to per-field, frequency-weighted |
| `fed_prospector/etl/attachment_intel_extractor.py` | Remove `_update_opportunity_columns()` and `_resolve_incumbent_for_opportunity()` calls from `_process_notice()` |

---

## Out of Scope

- Changing how intel is extracted or stored (110F handles that)
- UI display changes (110G handles that)
- Merging key_requirements JSON across rows (future consideration)
