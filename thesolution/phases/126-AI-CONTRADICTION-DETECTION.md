# Phase 126: AI Contradiction Detection

**Status:** PLANNED
**Priority:** Medium — catches real-world copy-paste errors in solicitations
**Dependencies:** Phase 110 (Attachment Intelligence), Phase 121 (Description Intel Extraction)

---

## Summary

Contracting officers frequently copy-paste from previous solicitations when renewing or recompeting contracts. This leads to contradictions in the documents — the SOW says one thing, the description says another, or the NAICS code doesn't match the actual work described. These copy-paste errors are common and can waste bidders' time or create protest opportunities.

### Real-World Example

A contract renewal for "refrigerator replacement" was copied from a prior "housekeeping/cleaning" solicitation. The SOW described the new work, but boilerplate sections still referenced cleaning services. A bidder reading only the boilerplate would misunderstand the scope entirely.

---

## What to Detect

### Cross-Document Contradictions
- SOW describes different work than the description or title
- NAICS code doesn't match the described services (e.g., NAICS says cleaning but SOW says equipment installation)
- Set-aside type in the description doesn't match the classification
- Period of performance differs between documents
- Different dollar amounts or quantities across sections
- Conflicting evaluation criteria

### Within-Document Contradictions
- Scope section says one thing, requirements section says another
- References to prior contract numbers or incumbent names that don't match the current solicitation
- Boilerplate referencing services/products not mentioned in the SOW
- Inconsistent terminology (e.g., "janitorial services" in one section, "equipment maintenance" in another)

### Stale Reference Detection
- References to expired regulations or FAR clauses
- Dates that don't make sense (e.g., past dates for future deliverables)
- References to organizational units that may have been reorganized

---

## Implementation Approach

### AI Prompt Enhancement
- Update the AI analysis prompt to include a "contradictions and inconsistencies" section
- Feed the AI both the description text AND all attachment texts for cross-referencing
- Ask the AI to flag confidence level: HIGH (clear contradiction), MEDIUM (possible inconsistency), LOW (minor discrepancy)

### Output
- New intel category for contradictions/inconsistencies
- Each finding should include: what contradicts what, where each piece is found, severity
- Surface in the UI as a distinct section (e.g., "Potential Issues" or "Solicitation Alerts")

---

## Open Questions

1. Should this run as part of the existing AI analysis pass or as a separate analysis step?
2. How to present contradictions in the UI — warnings on the overview, separate tab section, or integrated into Document Intel?
3. Should keyword/heuristic extraction also look for simple contradiction patterns (e.g., NAICS mismatch with title keywords)?
   **Resolved (2026-04-28, post-Phase-125 pattern audit):** No. Keyword/heuristic extraction is too literal for contradiction detection — generic FAR/DFARS clause patterns hit 40% of docs (mostly boilerplate, no signal), and structural Q&A detection produced unicode-garbage matches. NAICS-vs-title mismatch is best computed structurally from the `ref_naics_code` reference table (Phase 129 territory), not regex against attachment text. Contradiction detection stays AI-only.
4. Token cost implications — cross-referencing multiple documents in one prompt is more expensive
