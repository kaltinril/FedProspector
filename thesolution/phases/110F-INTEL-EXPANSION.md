# Phase 110F: Intelligence Extraction Expansion

**Status:** PLANNED
**Priority:** High — fills critical gaps in bid/no-bid decision intelligence
**Dependencies:** Phase 110C (AI analyzer — complete), Phase 110 (keyword extractor — complete)

---

## Summary

Expand both the keyword extractor and AI analyzer to capture intelligence fields that directly affect bid/no-bid decisions for a WOSB/8(a) small business. The keyword extractor gets new free regex patterns for structured terms; the AI prompt improvements (already done in 110C) handle the nuanced fields. Two new database columns are added for commonly-filtered intelligence.

The goal: a small business owner should be able to look at an opportunity in FedProspect and immediately know — can we bid this? Can we win? Is it worth the proposal effort? — without reading 500 pages of solicitation documents.

---

## What's Changing

### Tier 1: Keyword Extractor Expansion (FREE — all 24K docs)

New regex patterns added to `attachment_intel_extractor.py` for terms that are exact-match friendly:

| Category | Patterns to Match | Storage |
|----------|-------------------|---------|
| **Pricing structure** | `Firm Fixed Price`, `FFP`, `CPFF`, `Cost Plus Fixed Fee`, `CPAF`, `Cost Plus Award Fee`, `T&M`, `Time and Materials`, `Labor Hour`, `LH`, `CPIF` | New column: `pricing_structure` |
| **Compliance certs** | `CMMI Level 3`, `CMMI Level 5`, `FedRAMP`, `ISO 27001`, `ISO 9001`, `SOC 2`, `SOC 2 Type II`, `PMP`, `ITIL`, `CompTIA`, `CISSP` | `key_requirements` JSON |
| **Set-aside type** | `WOSB`, `EDWOSB`, `8(a)`, `SDVOSB`, `HUBZone`, `Small Business`, `Women-Owned`, `Service-Disabled Veteran` | `key_requirements` JSON |
| **Bonding/insurance** | `performance bond`, `bid bond`, `payment bond`, `professional liability`, `errors and omissions`, `workers compensation`, `general liability` | `key_requirements` JSON |
| **Subcontracting plan** | `FAR 52.219-9`, `subcontracting plan`, `subcontracting goals`, `small business subcontracting` | `key_requirements` JSON |
| **OCI restrictions** | `organizational conflict of interest`, `OCI`, `FAR 9.5`, `FAR 3.104`, `mitigation plan` | `key_requirements` JSON |
| **Place of performance** | `on-site`, `on site`, `remote work`, `telework`, `hybrid`, `contractor facility`, `government facility`, `CONUS`, `OCONUS` | New column: `place_of_performance` |
| **Past performance minimums** | `minimum of X contracts`, `at least X years experience`, `demonstrated experience`, `relevant experience` | `key_requirements` JSON |

### Tier 2: AI Analyzer (ON-DEMAND — per opportunity, costs money)

The AI prompt was already updated in Phase 110C to extract these richer fields. No additional prompt changes needed — this phase is about the keyword side and database schema.

AI adds value beyond keyword extraction for:
- **Evaluation factor weights** — "Technical (30%), Past Performance (25%), Cost (25%)" requires understanding paragraph/table context
- **Structured labor categories** — Parsing tables with category, clearance, experience, quantity per role
- **Scope summary** — 2-3 sentence plain-English explanation of what the contractor will do
- **Nuanced clearance analysis** — Understanding context around clearance mentions (negation, conditional, per-role)
- **Incumbent details** — Extracting company names from complex sentence structures

---

## Task 1: Database Schema Changes

### New columns on `opportunity_attachment_intel`

```sql
ALTER TABLE opportunity_attachment_intel
    ADD COLUMN pricing_structure VARCHAR(50) AFTER recompete_details,
    ADD COLUMN place_of_performance VARCHAR(200) AFTER pricing_structure;
```

### New columns on `opportunity` (backfill targets)

```sql
ALTER TABLE opportunity
    ADD COLUMN pricing_structure VARCHAR(50) AFTER contract_vehicle_type,
    ADD COLUMN place_of_performance_detail VARCHAR(200) AFTER pricing_structure;
```

These are commonly-filtered fields that justify their own columns rather than being buried in JSON.

### Update DDL files

- `fed_prospector/db/schema/tables/36_attachment.sql` — add columns to `opportunity_attachment_intel`
- `fed_prospector/db/schema/tables/01_opportunity.sql` — add columns to `opportunity` (check exact file name)

---

## Task 2: Keyword Extractor — New Pattern Categories

Add new pattern groups to `_RAW_PATTERNS` in `attachment_intel_extractor.py`:

### Pricing Structure Patterns

```python
"pricing_structure": [
    {"pattern": r"\b(?:Firm[- ]Fixed[- ]Price|FFP)\b", "value": "FFP", "confidence": "high", "name": "pricing_ffp"},
    {"pattern": r"\b(?:Cost[- ]Plus[- ]Fixed[- ]Fee|CPFF)\b", "value": "CPFF", "confidence": "high", "name": "pricing_cpff"},
    {"pattern": r"\b(?:Cost[- ]Plus[- ]Award[- ]Fee|CPAF)\b", "value": "CPAF", "confidence": "high", "name": "pricing_cpaf"},
    {"pattern": r"\b(?:Cost[- ]Plus[- ]Incentive[- ]Fee|CPIF)\b", "value": "CPIF", "confidence": "high", "name": "pricing_cpif"},
    {"pattern": r"\b(?:Time[- ]and[- ]Materials?|T&M|T & M)\b", "value": "T&M", "confidence": "high", "name": "pricing_tm"},
    {"pattern": r"\b(?:Labor[- ]Hour|LH)\b", "value": "LH", "confidence": "high", "name": "pricing_lh"},
],
```

### Compliance/Certification Patterns

```python
"compliance_certs": [
    {"pattern": r"\bCMMI\s*(?:Level|Lvl|ML|-)?\s*[2-5]\b", "value": None, "confidence": "high", "name": "cert_cmmi"},
    {"pattern": r"\bFedRAMP\b", "value": "FedRAMP", "confidence": "high", "name": "cert_fedramp"},
    {"pattern": r"\bISO\s*27001\b", "value": "ISO 27001", "confidence": "high", "name": "cert_iso27001"},
    {"pattern": r"\bISO\s*9001\b", "value": "ISO 9001", "confidence": "high", "name": "cert_iso9001"},
    {"pattern": r"\bSOC\s*2(?:\s*Type\s*(?:I{1,2}|1|2))?\b", "value": "SOC 2", "confidence": "high", "name": "cert_soc2"},
    {"pattern": r"\b(?:PMP|Project\s+Management\s+Professional)\b", "value": "PMP", "confidence": "medium", "name": "cert_pmp"},
    {"pattern": r"\bITIL\b", "value": "ITIL", "confidence": "medium", "name": "cert_itil"},
    {"pattern": r"\bCISSP\b", "value": "CISSP", "confidence": "high", "name": "cert_cissp"},
    {"pattern": r"\bCompTIA\s+(?:Security\+|Network\+|A\+|CASP)\b", "value": None, "confidence": "medium", "name": "cert_comptia"},
],
```

### Bonding/Insurance Patterns

```python
"bonding_insurance": [
    {"pattern": r"\b(?:performance\s+bond)\b", "value": "Performance Bond", "confidence": "high", "name": "bond_performance"},
    {"pattern": r"\b(?:bid\s+bond)\b", "value": "Bid Bond", "confidence": "high", "name": "bond_bid"},
    {"pattern": r"\b(?:payment\s+bond)\b", "value": "Payment Bond", "confidence": "high", "name": "bond_payment"},
    {"pattern": r"\b(?:professional\s+liability|errors\s+and\s+omissions|E&O)\b", "value": "Professional Liability", "confidence": "high", "name": "insurance_professional"},
    {"pattern": r"\b(?:general\s+liability)\b", "value": "General Liability", "confidence": "medium", "name": "insurance_general"},
    {"pattern": r"\b(?:workers.?\s*compensation)\b", "value": "Workers Compensation", "confidence": "medium", "name": "insurance_workers_comp"},
],
```

### Subcontracting/OCI Patterns

```python
"subcontracting_oci": [
    {"pattern": r"\bFAR\s+52\.219-9\b", "value": "SB Subcontracting Plan Required", "confidence": "high", "name": "sub_far_clause"},
    {"pattern": r"\b(?:small\s+business\s+)?subcontracting\s+(?:plan|goals?)\b", "value": "SB Subcontracting Plan Required", "confidence": "medium", "name": "sub_plan"},
    {"pattern": r"\b(?:organizational\s+conflict\s+of\s+interest|OCI)\b", "value": "OCI Restriction", "confidence": "high", "name": "oci_restriction"},
    {"pattern": r"\bFAR\s+(?:9\.5|3\.104)\b", "value": "OCI Restriction", "confidence": "high", "name": "oci_far_clause"},
],
```

### Place of Performance Patterns

```python
"place_of_performance": [
    {"pattern": r"\b(?:on[- ]site|onsite)\b", "value": "On-Site", "confidence": "medium", "name": "pop_onsite"},
    {"pattern": r"\b(?:remote\s+work|telework|work\s+from\s+home)\b", "value": "Remote", "confidence": "medium", "name": "pop_remote"},
    {"pattern": r"\bhybrid\b", "value": "Hybrid", "confidence": "low", "name": "pop_hybrid"},
    {"pattern": r"\b(?:contractor\s+facilit(?:y|ies))\b", "value": "Contractor Facility", "confidence": "medium", "name": "pop_contractor"},
    {"pattern": r"\b(?:government\s+facilit(?:y|ies)|government\s+site)\b", "value": "Government Facility", "confidence": "medium", "name": "pop_government"},
    {"pattern": r"\bCONUS\b", "value": "CONUS", "confidence": "high", "name": "pop_conus"},
    {"pattern": r"\bOCONUS\b", "value": "OCONUS", "confidence": "high", "name": "pop_oconus"},
],
```

### Set-Aside Patterns

```python
"set_aside_type": [
    {"pattern": r"\b(?:WOSB|Women[- ]Owned\s+Small\s+Business)\b", "value": "WOSB", "confidence": "high", "name": "setaside_wosb"},
    {"pattern": r"\b(?:EDWOSB|Economically\s+Disadvantaged\s+Women[- ]Owned)\b", "value": "EDWOSB", "confidence": "high", "name": "setaside_edwosb"},
    {"pattern": r"\b8\(a\)\b", "value": "8(a)", "confidence": "high", "name": "setaside_8a"},
    {"pattern": r"\b(?:SDVOSB|Service[- ]Disabled\s+Veteran[- ]Owned)\b", "value": "SDVOSB", "confidence": "high", "name": "setaside_sdvosb"},
    {"pattern": r"\bHUBZone\b", "value": "HUBZone", "confidence": "high", "name": "setaside_hubzone"},
],
```

---

## Task 3: Keyword Extractor — Processing Logic

The new pattern categories need to be wired into the extraction pipeline. For each new category:

1. **Match patterns** against extracted text (same as existing categories)
2. **Store results** in `opportunity_attachment_intel`:
   - `pricing_structure` -> new column (best match value)
   - `place_of_performance` -> new column (best match value)
   - `compliance_certs`, `bonding_insurance`, `subcontracting_oci`, `set_aside_type` -> append to `key_requirements` JSON array
3. **Track provenance** in `opportunity_intel_source` (same pattern as existing categories)

### key_requirements JSON Structure

Currently `key_requirements` is an unstructured JSON array of strings. The new patterns should append tagged entries:

```json
[
    "SAM registration required",
    "[CERT] CMMI Level 3",
    "[CERT] FedRAMP",
    "[BOND] Performance Bond",
    "[SUB] SB Subcontracting Plan Required",
    "[OCI] OCI Restriction",
    "[SET-ASIDE] WOSB"
]
```

Tags make it easy for the UI to group and display these by type.

---

## Task 4: Backfill Integration

Update `_update_opportunity_columns()` in `attachment_intel_extractor.py` to also backfill:
- `opportunity.pricing_structure` <- from `pricing_structure`
- `opportunity.place_of_performance_detail` <- from `place_of_performance`

Update `cli/backfill.py` to include the new columns in the standalone backfill command.

---

## Task 5: AI Analyzer Schema Alignment

Update the `_save_intel()` method in `attachment_ai_analyzer.py` to also save:
- `pricing_structure` — parse from `vehicle_details` text where the AI includes pricing type
- `place_of_performance` — parse from `key_requirements` where AI includes place of performance

This ensures both keyword and AI results populate the same columns.

---

## Scope / Out of Scope

### In scope
- New keyword patterns (Task 2)
- Wiring into extraction pipeline (Task 3)
- Schema changes: 2 new columns each on `opportunity_attachment_intel` and `opportunity` (Task 1)
- Backfill integration (Task 4)
- AI analyzer alignment (Task 5)

### Out of scope (handled elsewhere)
- AI prompt improvements — already done in Phase 110C
- UI changes to display new fields — separate phase
- Re-running keyword extraction on all 24K docs — operator decision, run `extract attachment-intel --force`
- QualificationService/PWinService using attachment intel — separate phase (see Implementation Notes)

---

## Code Touchpoints

### Modified files

| File | What to do |
|------|------------|
| `fed_prospector/etl/attachment_intel_extractor.py` | Add 6 new pattern groups, wire into processing, update `_update_opportunity_columns()` |
| `fed_prospector/etl/attachment_ai_analyzer.py` | Save `pricing_structure` and `place_of_performance` columns |
| `fed_prospector/cli/backfill.py` | Add new columns to backfill query |
| `fed_prospector/db/schema/tables/36_attachment.sql` | Add columns to `opportunity_attachment_intel` |
| `fed_prospector/db/schema/tables/01_opportunity.sql` | Add columns to `opportunity` (verify filename) |

---

## Implementation Notes

### Running the new extraction

After implementation, the new patterns can be applied to all existing documents:

```bash
python main.py extract attachment-intel --force
```

This re-runs keyword extraction on all 24K docs with the expanded patterns. Free, takes a few minutes.

### Future phases should address

1. **QualificationService should query attachment intel** — Currently `CheckSecurityClearance()` only searches `opportunity.title` and `description_text`. It should also check `opportunity_attachment_intel.clearance_required`. Same for new compliance/bonding requirements.

2. **PWinService incumbent factor** — `opportunity.incumbent_name` is populated by backfill but `opportunity.incumbent_uei` is not resolved. PWinService checks `incumbent_uei` for "is our org the incumbent?" scoring. Phase 110D resolved UEI lookup but it may need backfill.

3. **UI display of expanded intel** — The Document Intelligence tab should display pricing structure, place of performance, compliance certs, bonding, and OCI as distinct sections (not buried in key_requirements JSON).

---

## Cost Impact

- **Keyword extraction**: FREE — runs locally, no API calls
- **AI analysis**: No change — same per-doc cost as Phase 110C
- **Net effect**: More intelligence gathered for free, reducing the need for AI analysis on routine checks. AI becomes the "deep dive" for ambiguous or high-priority opportunities.
