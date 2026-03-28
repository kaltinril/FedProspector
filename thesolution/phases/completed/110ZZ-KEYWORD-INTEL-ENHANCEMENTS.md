# Phase 110ZZ: Keyword Intelligence Extraction Enhancements

**Status:** COMPLETE
**Priority:** Medium — improves bid-decision intelligence without API costs
**Dependencies:** Phase 110F (current keyword extractor)

---

## Summary

The keyword intelligence extractor (`attachment_intel_extractor.py`) has 60 regex patterns across 10 categories, but analysis of 19 real solicitation documents reveals significant gaps. The `period_of_performance`, `labor_categories`, and `scope_summary` columns exist in the schema but are only populated by the AI analyzer — never by keyword extraction.

**Validation (2026-03-25):** Tested proposed patterns against 4,926 opportunities with keyword-extracted intel. Period of performance matches 71.6% of all docs, NAICS 54.9%, wage determination 37.0%, contract value 43.1%, CMMC/NIST 8.4%. The new categories would elevate ~400–600 currently-low-confidence opportunities to medium or high.

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

`_gather_text_sources` already returns `(attachment_id, filename, text)` tuples and filenames are tracked in match_info, but `_run_patterns` only scans the `extracted_text` — filenames are never pattern-matched. The filename often contains vehicle identifiers (e.g., "BPA Logistical Support.pdf").

**Fix:** Prepend `filename + "\n"` to the text before passing to pattern scanning in `_run_patterns`. Adjust `char_offset_start`/`char_offset_end` in source provenance by the filename length offset.

### Task 8: PPQ / Past Performance Document-Type Heuristic

585 documents (12% of the corpus) are Past Performance Questionnaires or similar forms. Patterns for pricing, period of performance, task/delivery orders, and vehicle type fire on blank form templates that describe *past* contract characteristics, not the current procurement.

**Implementation:**
1. In `_gather_text_sources`, tag each source with a `is_ppq` flag:
   - Check if filename matches `(?i)(?:past\s+performance|PPQ)`
   - Check if first 200 chars of extracted_text match the same pattern
2. In `_run_patterns`, if `is_ppq` is True, downgrade all match confidence by one level (high→medium, medium→low, low→low)
3. Store the PPQ flag in match_info so consolidation can use it for tie-breaking

This is a cross-cutting concern that mitigates false positives in Tasks 1b, 1d, 2, and 5.

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
| `Full and Open Competition` | **CRITICAL** | 71% false-positive rate: 708 of 995 corpus matches are "other than full and open competition" in sole-source J&As — tags them as "Unrestricted" (exact opposite) | Negative lookbehind alone is insufficient — "other than" can appear many words before "full and open". Require proximity to a `set-aside` or `competition type` heading, or require the phrase NOT preceded by "other than" within 60 chars |
| `DBA` (for Davis-Bacon) | **HIGH** | "DBA" commonly means "Doing Business As" (e.g., "ABC Corp DBA XYZ Services") | Remove `DBA` standalone; require full phrase "Davis-Bacon" |
| `$` standalone amounts | **HIGH** | Matches bonding, insurance, liquidated damages, size standards — not contract value | Gate on qualifying words within ±100 chars (ceiling, maximum, estimated, NTE) |
| `task order` / `delivery order` | **HIGH** | Matches blank form labels in Past Performance questionnaires ("Delivery/Task Order Number (if applicable)") and T&C boilerplate | Require NOT preceded by "Number", not inside parenthetical labels |
| `not-to-exceed` | **HIGH** | Matches time limits ("not to exceed 8 business hours") — not just dollar amounts | Require `$` or numeric dollar context within ±30 chars |
| PPQ / Past Performance forms | **CRITICAL** | 585 documents (12% of corpus) contain PPQ content. Multiple categories (pricing, POP, task/delivery order) fire on blank form templates describing *past* contracts, not the current procurement | Add document-type heuristic: if filename or first 200 chars contain "Past Performance Questionnaire", "PPQ", or "Past Performance Information", lower confidence on all extractions by one level (high→medium, medium→low) |

### Should Fix

| Pattern | Risk | Issue | Fix |
|---------|------|-------|-----|
| `SCA` standalone | **MEDIUM** | "SCA" is ambiguous (SCA Health, etc.) | Require full "Service Contract Act" or nearby "wage" context |
| `Polaris` | **MEDIUM** | Could match Polaris Industries, Polaris vehicles in equipment solicitations | Require context: "Polaris GWAC" or "Polaris contract" or "GSA Polaris" |
| `sole-source` | **MEDIUM** | No negation handling — matches "this is NOT a sole-source" | Add negative lookbehind for "not a" |
| `task order` | **MEDIUM** | 13.4% of task/delivery order matches (351 of 2,618) appear inside PPQ documents describing past contract types, not current opportunity structure | Lower to "low" confidence; also gated by Task 8 PPQ heuristic |
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
- **Existing pattern risk**: The current `Firm Fixed Price` / `FFP` pattern also matches PPQ checkbox labels describing past contracts, not the current procurement. This is a pre-existing issue, not introduced by this phase.

---

## Files to Modify

| File | Change |
|------|--------|
| `fed_prospector/etl/attachment_intel_extractor.py` | Add new patterns, new categories, consolidation logic, filename scanning |

## Documents Analyzed

19 randomly sampled solicitation attachments were analyzed across document types (SOWs, RFQs, RFIs, solicitations, amendments, specifications) to identify common patterns. Current patterns found matches in only ~30% of documents; the enhancements target the most common gaps.

**Corpus-wide validation (2026-03-25):** Proposed patterns tested against 4,926 opportunities (8,466 distinct notice_ids in intel table, 18,275 total intel records). False positive rates validated quantitatively — see "False Positive Risks" section for counts. PPQ heuristic promoted to Task 8 based on 12% corpus prevalence.

## Validation Results (2026-03-25)

Before/after comparison on 30 randomly sampled opportunities:

| Metric | Before | After | Delta |
|--------|--------|-------|-------|
| Total intel rows | 93 | 135 | +42 (+45%) |
| High confidence | 73 | 110 | +37 |
| Medium confidence | 11 | 22 | +11 |
| Low confidence | 9 | 3 | -6 (upgraded) |
| has_vehicle | 34 | 73 | +39 (+115%) |
| has_pricing | 7 | 59 | +52 (+743%) |
| has_pop_place | 18 | 76 | +58 (+322%) |
| has_pop_time | 0 | 39 | +39 (new category) |
| has_key_req | 11 | 103 | +92 (+836%) |
| has_clearance | 16 | 16 | unchanged |
| has_eval | 30 | 30 | unchanged |
| has_recompete | 26 | 26 | unchanged |

**Bug found during implementation:** `period_of_performance` column was missing from the `_upsert_intel_row` INSERT/UPDATE SQL — the column existed in the schema but was never included in the keyword extractor's persistence query (it was AI-only). Fixed as part of this phase.

**Pattern count:** 60 → 101 patterns across 10 → 14 categories.

**Re-extraction required:** Run `python main.py extract attachment-intel --force` to apply new patterns to all existing attachments.
