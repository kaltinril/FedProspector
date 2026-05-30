# Phase 126: AI Contradiction Detection

**Status:** COMPLETE
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

## Resolved Design Decisions

1. **Separate AI step vs. existing pass?** — Resolved: contradiction detection runs as a **separate AI step** (its own Claude call, re-feeding the description text + all attachment texts), NOT integrated into the existing AI analysis pass. This keeps the existing per-document analysis prompt focused and lets contradiction detection cross-reference all documents in one dedicated call.
2. **UI presentation?** — Resolved: findings surface as a new **"Potential Issues" section inside the existing Document Intelligence UI tab** (a `ContradictionsCard`), NOT as an overview banner or separate tab.
3. **Keyword/heuristic contradiction patterns?** — Resolved (2026-04-28, post-Phase-125 pattern audit): No. Keyword/heuristic extraction is too literal for contradiction detection — generic FAR/DFARS clause patterns hit 40% of docs (mostly boilerplate, no signal), and structural Q&A detection produced unicode-garbage matches. NAICS-vs-title mismatch is best computed structurally from the `ref_naics_code` reference table (Phase 129 territory), not regex against attachment text. Contradiction detection stays AI-only.
4. **Token cost of multi-document cross-referencing?** — Resolved: detection is **on-demand only** (triggered per opportunity via CLI / demand loader hook). No daily-batch step was added, so the multi-document prompt cost is incurred only when a user requests analysis rather than across all opportunities every day.

---

## Implementation

### Unit A — Python ETL & CLI -- DONE
- `fed_prospector/etl/attachment_ai_analyzer.py`: new `CONTRADICTION_SYSTEM_PROMPT` and `detect_contradictions()` method (separate Claude call, re-feeds description + all attachment texts).
- New CLI command `python main.py extract contradictions` — registered in `main.py`, defined in `fed_prospector/cli/attachments.py`.
- On-demand hook added in `demand_loader.py` `_process_attachment_analysis`.
- Detection is AI-only and on-demand; no daily-batch step added.

### Storage / Schema -- DONE
- New `contradictions JSON` column on `opportunity_attachment_summary`.
- New `ai_contradiction` value in the shared `extraction_method` ENUM, kept in lockstep across `opportunity_attachment_summary`, `document_intel_summary`, and `document_intel_evidence`.
- DDL: `fed_prospector/db/schema/tables/36_attachment.sql`.
- Migration: `fed_prospector/db/schema/migrations/132_contradiction_detection.sql` (idempotent) — already applied to the live DB.

### Unit B — C# API -- DONE
- New `ContradictionDto` and `Contradictions` list on `DocumentIntelligenceDto`.
- New `OpportunityAttachmentSummary.Contradictions` model property.
- `AttachmentIntelService.GetDocumentIntelligenceAsync` deserializes the `ai_contradiction` row (snake_case → camelCase) and excludes it from existing aggregation / confidence / method-chip logic.
- Surfaced on the existing `/document-intelligence` endpoint — no new endpoint added.

### Unit C — UI -- DONE
- New `ContradictionDto` type and `ContradictionsCard` component in `ui/src/pages/opportunities/DocumentIntelligenceTab.tsx`.
- Rendered between the Scope Summary and the intel cards, sorted high-severity-first.
