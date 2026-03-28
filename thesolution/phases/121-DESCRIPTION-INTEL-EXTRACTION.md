# Phase 121: Description Intel Extraction

**Status:** PLANNED
**Priority:** Medium — descriptions contain valuable intel not currently analyzed
**Dependencies:** Phase 112 (Description Backfill)

---

## Summary

Keyword intel extraction and AI analysis currently only process attachment text (`attachment_document.extracted_text`). Opportunity descriptions (`opportunity.description_text`) often contain key intel — set-aside details, NAICS codes, clearance requirements, period of performance, evaluation criteria — that should also feed into the intel pipeline.

This phase extends both the keyword/heuristic extractor and the AI analyzer to include description text as an additional input source.

---

## Task 1: Keyword Intel from Description Text

Extend the keyword/heuristic intel extractor to analyze `description_text` in addition to attachment text.

### Considerations

- **Source tracking:** Intel extracted from descriptions needs a distinct `extraction_method` or source marker so it's distinguishable from attachment-derived intel (e.g., `keyword_description` vs `keyword`).
- **Deduplication:** If an attachment repeats what the description says, the same intel patterns will match both. The summary dedup (pattern + count) already handles this at the evidence level, but decide whether description intel should merge into existing `document_intel_summary` rows or get their own.
- **Schema impact:** `document_intel_summary` and `document_intel_evidence` are keyed on `document_id` (from `attachment_document`). Descriptions are not documents — need to decide: (a) create a virtual `attachment_document` row for the description, (b) add a parallel `opportunity_description_intel` table, or (c) add nullable `notice_id` to `document_intel_summary` as an alternative to `document_id`.
- **Backfill:** Needs a CLI command or flag to run extraction on existing descriptions, not just newly fetched ones.

---

## Task 2: AI Analysis of Description Text

Extend the AI analyzer to include `description_text` as context alongside attachment text.

### Considerations

- The description is typically shorter than attachment text (1-5KB vs 10-500KB). It could be prepended to the attachment text as additional context for the AI prompt.
- Alternatively, if an opportunity has no attachments but has a description, AI analysis could still run on the description alone.
- Cost: running AI analysis on descriptions-only opportunities adds API cost. Should be opt-in or gated.

---

## Task 3: Backfill Existing Descriptions

Run keyword intel extraction on the ~880+ opportunities that already have `description_text` populated (plus any new ones from Phase 112 backfill).

---

## Open Questions

1. Should description intel be stored in the same `document_intel_summary` table (with a virtual document) or a separate table?
2. Should description intel extraction run as part of the existing `extract attachment-intel` command or as a separate command?
3. For AI analysis, should description text be concatenated with attachment text or analyzed separately?
