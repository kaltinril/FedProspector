# Phase 110ZZ: Keyword Intelligence Extraction Enhancements

**Status:** PLANNED
**Priority:** Medium — improves bid-decision intelligence without API costs
**Dependencies:** Phase 110F (current keyword extractor)

---

## Summary

The keyword intelligence extractor (`attachment_intel_extractor.py`) has 60 regex patterns across 10 categories, but analysis of 19 real solicitation documents reveals significant gaps. The `period_of_performance`, `labor_categories`, and `scope_summary` columns exist in the schema but are only populated by the AI analyzer — never by keyword extraction.

This phase broadens existing patterns and adds new categories to improve keyword-based intelligence extraction without requiring AI API calls.

## Constraints

- **Must not break, reduce, or diminish existing extraction** — all changes are additive
- **No schema changes** — use existing columns (`period_of_performance`, `labor_categories`, `key_requirements`)
- **Regex-only** — patterns must be reliably extractable without NLP/context understanding
- **Low false-positive rate** — prefer missing a match over a wrong match

---

## Current State

### Categories with patterns (10):
| Category | Patterns | Maps to Column |
|----------|----------|----------------|
| clearance_level | 7 | clearance_level, clearance_required, clearance_scope |
| eval_method | 5 | eval_method |
| vehicle_type | 6 | vehicle_type |
| recompete | 5 | is_recompete, incumbent_name |
| pricing_structure | 6 | pricing_structure |
| compliance_certs | 9 | key_requirements (JSON) |
| bonding_insurance | 6 | key_requirements (JSON) |
| subcontracting_oci | 4 | key_requirements (JSON) |
| place_of_performance | 7 | place_of_performance |
| set_aside_type | 5 | key_requirements (JSON) |

### Columns with NO keyword patterns (AI-only):
| Column | Type | Purpose |
|--------|------|---------|
| scope_summary | TEXT | Narrative summary |
| period_of_performance | VARCHAR(200) | Duration/dates |
| labor_categories | JSON | Job titles/CLINs |
| citation_offsets | JSON | Character offsets |

---

## Enhancements

### Task 1: Fix Existing Pattern Gaps

**1a. Place of Performance — broaden contractor patterns**

Current `pop_contractor` only matches "contractor facilit(y|ies)". Documents commonly use:
- "contractor's site" / "contractor site" / "contractor location" / "contractor premises"
- "off-site" / "offsite"

Add patterns:
```python
{"pattern": r"\bcontractor'?s?\s+(?:site|location|premises)\b", "value": "Contractor Facility", "confidence": "medium", "name": "pop_contractor_site"},
{"pattern": r"\b(?:off[- ]site|offsite)\b", "value": "Off-Site", "confidence": "medium", "name": "pop_offsite"},
{"pattern": r"\b(?:government\s+premises)\b", "value": "Government Facility", "confidence": "medium", "name": "pop_gov_premises"},
{"pattern": r"\bmultiple\s+(?:locations|sites)\b", "value": "Multiple Locations", "confidence": "medium", "name": "pop_multiple"},
```

**1b. Vehicle Type — add order types and missing vehicles**

Add:
```python
{"pattern": r"\btask\s+order\b", "value": "IDIQ", "confidence": "medium", "name": "vehicle_task_order"},
{"pattern": r"\bdelivery\s+order\b", "value": "IDIQ", "confidence": "medium", "name": "vehicle_delivery_order"},
{"pattern": r"\b(?:indefinite[- ]delivery(?:[- ]indefinite[- ]quantity)?)\b", "value": "IDIQ", "confidence": "high", "name": "vehicle_id_iq_spelled"},
{"pattern": r"\b(?:BOA|Basic\s+Ordering\s+Agreement)\b", "value": "BOA", "confidence": "high", "name": "vehicle_boa"},
{"pattern": r"\b(?:SBIR|STTR)\b", "value": None, "confidence": "high", "name": "vehicle_sbir"},
{"pattern": r"\bPolaris\b", "value": "Polaris", "confidence": "high", "name": "vehicle_polaris"},
```

**1c. Set-Aside — add common types the current patterns miss**

Current patterns only cover WOSB, EDWOSB, 8(a), SDVOSB, HUBZone. Missing the most common types:
```python
{"pattern": r"\b(?:Total\s+Small\s+Business|Total\s+SB)\s*(?:Set[- ]?Aside)?\b", "value": "Total SB", "confidence": "high", "name": "setaside_total_sb"},
{"pattern": r"\bSmall\s+Business\s+Set[- ]?Aside\b", "value": "SB Set-Aside", "confidence": "high", "name": "setaside_sb"},
{"pattern": r"\b(?:Unrestricted|Full\s+and\s+Open(?:\s+Competition)?)\b", "value": "Unrestricted", "confidence": "high", "name": "setaside_unrestricted"},
{"pattern": r"\b(?:VOSB|Veteran[- ]Owned\s+Small\s+Business)\b", "value": "VOSB", "confidence": "high", "name": "setaside_vosb"},
{"pattern": r"\b(?:sole[- ]source)\b", "value": "Sole Source", "confidence": "high", "name": "setaside_sole_source"},
```

**1d. Pricing Structure — add missing types**

```python
{"pattern": r"\b(?:Fixed[- ]Price[- ]Incentive|FPI(?:F|S)?)\b", "value": "FPI", "confidence": "high", "name": "pricing_fpi"},
{"pattern": r"\b(?:Cost[- ]Reimbursement|Cost[- ]Type)\b", "value": "Cost Reimbursement", "confidence": "medium", "name": "pricing_cr"},
{"pattern": r"\baward\s+(?:term|fee)\b", "value": None, "confidence": "medium", "name": "pricing_award_fee"},
```

### Task 2: New Category — Period of Performance

Add `period_of_performance` category mapping to the existing `period_of_performance` column.

Patterns:
```python
"period_of_performance": [
    {"pattern": r"\b(?:one|two|three|four|five|six|seven|1|2|3|4|5|6)\s*\(?\d*\)?\s*base\s+(?:year|period)", "value": None, "confidence": "high", "name": "pop_base_year"},
    {"pattern": r"\bbase\s+(?:year|period)\s*(?:plus|and|\+|with)\s*(?:\w+\s+)?\(?\d+\)?\s*option\s+(?:year|period)s?", "value": None, "confidence": "high", "name": "pop_base_plus_option"},
    {"pattern": r"\bperiod\s+of\s+performance\s+(?:is|shall\s+be|:)\s*(?:approximately\s+)?(\d+)\s*(?:month|year|day)s?", "value": None, "confidence": "high", "name": "pop_duration"},
    {"pattern": r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)[- ]year\s+(?:contract|IDIQ|ordering\s+period|effort|period)", "value": None, "confidence": "high", "name": "pop_x_year"},
    {"pattern": r"\bordering\s+period\b", "value": None, "confidence": "medium", "name": "pop_ordering_period"},
    {"pattern": r"\boption\s+(?:year|period)s?\b", "value": None, "confidence": "medium", "name": "pop_option"},
],
```

**Consolidation logic**: Extract the matched text as-is and store in `period_of_performance` column. Use the highest-confidence match's surrounding context (±100 chars) as the value.

### Task 3: New Category — NAICS Code

Add `naics_code` category. Store in `key_requirements` JSON with `[NAICS]` tag prefix.

```python
"naics_code": [
    {"pattern": r"\bNAICS\s*(?:Code)?[:\s]*(\d{6})\b", "value": None, "confidence": "high", "name": "naics_code"},
    {"pattern": r"\bsize\s+standard\s+(?:of\s+|is\s+)?\$[\d,.]+\s*(?:million|M)?\b", "value": None, "confidence": "medium", "name": "naics_size_standard"},
    {"pattern": r"\b(?:PSC|Product\s+Service\s+Code)[:\s]*([A-Z]\d{3})\b", "value": None, "confidence": "high", "name": "psc_code"},
],
```

### Task 4: New Category — Wage Determination

Add `wage_determination` category. Store in `key_requirements` JSON with `[WAGE]` tag prefix.

```python
"wage_determination": [
    {"pattern": r"\b(?:Service\s+Contract\s+(?:Act|Labor\s+Standards)|SCA)\b", "value": "SCA", "confidence": "high", "name": "wage_sca"},
    {"pattern": r"\b(?:Davis[- ]Bacon(?:\s+Act)?|DBA)\b", "value": "Davis-Bacon", "confidence": "high", "name": "wage_dba"},
    {"pattern": r"\bWage\s+Determination\s*(?:No\.?|Number|#)?[:\s]*\d{4}[-]\d{4}\b", "value": None, "confidence": "high", "name": "wage_wd_number"},
    {"pattern": r"\bFAR\s+52\.222-41\b", "value": "SCA", "confidence": "high", "name": "wage_far_sca"},
    {"pattern": r"\bFAR\s+52\.222-6\b", "value": "Davis-Bacon", "confidence": "high", "name": "wage_far_dba"},
    {"pattern": r"\bprevailing\s+wage\b", "value": None, "confidence": "medium", "name": "wage_prevailing"},
],
```

### Task 5: New Category — Contract Value

Add `contract_value` category. Store in `key_requirements` JSON with `[VALUE]` tag prefix.

```python
"contract_value": [
    {"pattern": r"\$\s*\d{1,3}(?:,\d{3}){2,}(?:\.\d{2})?", "value": None, "confidence": "high", "name": "value_dollar_amount"},
    {"pattern": r"\$\s*\d+(?:\.\d+)?\s*(?:M|B|million|billion)\b", "value": None, "confidence": "high", "name": "value_shorthand"},
    {"pattern": r"\b(?:ceiling|maximum)\s+(?:value|price|amount|contract\s+value)\b", "value": None, "confidence": "medium", "name": "value_ceiling"},
    {"pattern": r"\b(?:estimated|total|aggregate)\s+(?:value|amount|price|cost)\b", "value": None, "confidence": "medium", "name": "value_estimated"},
    {"pattern": r"\bnot[- ]to[- ]exceed\b", "value": None, "confidence": "medium", "name": "value_nte"},
],
```

### Task 6: New Category — Cybersecurity / CMMC

Add to `compliance_certs` (existing category, no new column needed):

```python
{"pattern": r"\bCMMC\s*(?:Level\s*)?[1-5]\b", "value": "CMMC", "confidence": "high", "name": "cert_cmmc_level"},
{"pattern": r"\bNIST\s+(?:SP\s+)?800-171\b", "value": "NIST 800-171", "confidence": "high", "name": "cert_nist_171"},
{"pattern": r"\bDFARS?\s+252\.204-7012\b", "value": "DFARS CUI", "confidence": "high", "name": "cert_dfars_cui"},
```

### Task 7: Scan Filenames for Vehicle Type

Currently, patterns only scan `extracted_text`. The filename often contains vehicle identifiers (e.g., "BPA Logistical Support.pdf"). Modify `_gather_text_sources` to prepend the filename to the text source so patterns can match filename content.

This is a small code change in the source-gathering logic, not a new pattern.

---

## Implementation Notes

### Column Mapping for New Categories

| New Category | Store In | Prefix Tag |
|---|---|---|
| period_of_performance | `period_of_performance` column | N/A (direct) |
| naics_code | `key_requirements` JSON | `[NAICS]` |
| wage_determination | `key_requirements` JSON | `[WAGE]` |
| contract_value | `key_requirements` JSON | `[VALUE]` |

### Categories NOT Added (and why)

| Category | Reason |
|----------|--------|
| Labor Categories | Too many false positives — job titles vary enormously. Better left to AI. |
| Solicitation Number | Already captured from SAM.gov opportunity data. |
| Response Deadline | Already in SAM.gov `response_deadline` field. |
| Key Personnel (contacts) | Names are too variable for regex; email addresses could be added but limited value. |
| FAR/DFARS clause listing | Would generate hundreds of matches per document. Better as a count/indicator than individual extraction. |
| Response Format (page limits) | Low bid-decision value. |

### Re-extraction Strategy

After implementing, run:
```
python main.py extract attachment-intel --force
```
This re-processes all attachments with the expanded patterns. Existing AI-generated intel rows are not affected (different `extraction_method`).

### Testing

1. Run extraction on the test notice (`59b4c6430b1045968ce6b8c4eb172d83`) — should now find vehicle_type (BPA from filename) and period_of_performance
2. Sample 20 random notices before/after and compare intel yield
3. Verify no regressions in existing pattern matches

---

## False Positive Risks (from validation of 30+ documents)

Patterns were tested against 30 randomly sampled real documents. Findings:

### CRITICAL — Must Fix Before Implementing

| Pattern | Risk | Issue | Fix |
|---------|------|-------|-----|
| `Full and Open Competition` | **CRITICAL** | Matches "other than full and open competition" in every sole-source J&A — tags them as "Unrestricted" (exact opposite) | Add negative lookbehind: `(?<!other\s+than\s+)(?<!without\s+)(?<!not\s+)` |
| `DBA` (for Davis-Bacon) | **HIGH** | "DBA" commonly means "Doing Business As" (e.g., "ABC Corp DBA XYZ Services") | Remove `DBA` standalone; require full phrase "Davis-Bacon" |
| `$` standalone amounts | **HIGH** | Matches bonding, insurance, liquidated damages, size standards — not contract value | Gate on qualifying words within ±100 chars (ceiling, maximum, estimated, NTE) |
| `task order` / `delivery order` | **HIGH** | Matches blank form labels in Past Performance questionnaires ("Delivery/Task Order Number (if applicable)") and T&C boilerplate | Require NOT preceded by "Number", not inside parenthetical labels |
| `not-to-exceed` | **HIGH** | Matches time limits ("not to exceed 8 business hours") — not just dollar amounts | Require `$` or numeric dollar context within ±30 chars |

### Should Fix

| Pattern | Risk | Issue | Fix |
|---------|------|-------|-----|
| `SCA` standalone | **MEDIUM** | "SCA" is ambiguous (SCA Health, etc.) | Require full "Service Contract Act" or nearby "wage" context |
| `Polaris` | **MEDIUM** | Could match Polaris Industries, Polaris vehicles in equipment solicitations | Require context: "Polaris GWAC" or "Polaris contract" or "GSA Polaris" |
| `sole-source` | **MEDIUM** | No negation handling — matches "this is NOT a sole-source" | Add negative lookbehind for "not a" |
| `task order` | **MEDIUM** | Matches past-performance narratives, staffing discussions, not just vehicle type | Lower to "low" confidence |
| `Unrestricted` bare word | **MEDIUM** | Appears in SF-1449 checkbox boilerplate even when NOT selected | Require context near "set-aside" or "competition type" |

### Acceptable Risk

| Pattern | Risk | Notes |
|---------|------|-------|
| `ordering period` | LOW | Almost always POP-related in federal contracting |
| `offsite` / `off-site` | LOW | Could match "offsite backup" but rare in solicitations |
| `delivery order` | LOW | True positive confirmed — correctly signals IDIQ context |
| `contractor site/location` | LOW | Specific enough to avoid false positives |
| `award fee/term` | LOW | Specific contracting terminology |

### Additional Findings

- **Case sensitivity**: Confirmed `re.IGNORECASE` is set (line 134 of `attachment_intel_extractor.py`). All patterns are case-insensitive. No action needed.
- **Wage Determination number format**: Proposed pattern `\d{4}[-]\d{4}` is wrong. Real WD numbers are like `NY20260003`. Fix pattern to: `(?:[A-Z]{2})?\d{7,}` or remove.
- **"Limited sources"**: Sole-source J&As often use "limited sources" instead of "sole source" — the pattern would miss these. Consider adding `\blimited\s+source\b` as an additional pattern.
- **Past Performance questionnaires**: Multiple patterns (pricing, POP, task/delivery order) fire on blank form templates. Consider a document-type heuristic: if filename or first 200 chars contain "Past Performance Questionnaire" or "PPQ", lower confidence on all extractions.
- **Existing pattern risk**: The current `Firm Fixed Price` / `FFP` pattern also matches PPQ checkbox labels describing past contracts, not the current procurement. This is a pre-existing issue, not introduced by this phase.

---

## Files to Modify

| File | Change |
|------|--------|
| `fed_prospector/etl/attachment_intel_extractor.py` | Add new patterns, new categories, consolidation logic, filename scanning |

## Documents Analyzed

19 randomly sampled solicitation attachments were analyzed across document types (SOWs, RFQs, RFIs, solicitations, amendments, specifications) to identify common patterns. Current patterns found matches in only ~30% of documents; the enhancements target the most common gaps.
