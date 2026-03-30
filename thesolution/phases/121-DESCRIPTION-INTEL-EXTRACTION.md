# Phase 121: Description Intel Extraction

**Status:** IN PROGRESS
**Priority:** Medium — descriptions contain valuable intel not currently analyzed
**Dependencies:** Phase 112 (Description Backfill)

---

## Summary

Keyword intel extraction and AI analysis currently only process attachment text (`attachment_document.extracted_text`). Opportunity descriptions (`opportunity.description_text`) often contain key intel — set-aside details, NAICS codes, clearance requirements, period of performance, evaluation criteria — that should also feed into the intel pipeline.

This phase extends both the keyword/heuristic extractor and the AI analyzer to include description text as an additional input source.

---

## Task 1: Keyword Intel from Description Text — ALREADY DONE

The keyword/heuristic extractor (`attachment_intel_extractor.py`) already processes `description_text` as a virtual source (document_id=None). This was implemented as part of the original intel extractor. Description-only notices produce `opportunity_attachment_summary` rows with keyword-extracted intel.

No additional work needed.

---

## Task 2: AI Analysis of Description Text — IMPLEMENTED

Extended `AttachmentAIAnalyzer` with a new `analyze_descriptions()` method that:

1. Fetches opportunities with non-empty `description_text` that don't yet have an AI summary row
2. For each notice, gathers description text and any available attachment text
3. Builds a combined prompt: description first (as `=== OPPORTUNITY DESCRIPTION ===`), then any attachment text
4. Sends to Claude (same system prompt as attachment analysis)
5. Saves results to `opportunity_attachment_summary` (same table used by keyword extractor)
6. Logs API usage to `ai_usage_log`

### CLI Command

```
python main.py extract description-ai [OPTIONS]

Options:
  --notice-id TEXT             Process a single opportunity by notice ID
  --batch-size INTEGER         Number of notices to process per batch [default: 50]
  --model [haiku|sonnet|opus]  Claude model to use for analysis [default: haiku]
  --force                      Re-analyze even if already analyzed
  --dry-run                    Run without calling the API
```

### Design Decisions

- **Storage**: AI results go into `opportunity_attachment_summary` (the per-notice rollup table), not `document_intel_summary` (which requires a document_id FK). This is consistent with how the keyword extractor stores description-only intel.
- **Combined context**: When a notice has both description and attachments, all text is sent in a single prompt to give the AI full context. Description text is labeled and prepended.
- **Deduplication**: The `opportunity_attachment_summary` table has a unique index on `(notice_id, extraction_method)`, so re-running with `--force` updates in place.
- **Cost control**: Same 100K character truncation as attachment analysis. Default model is haiku ($1/M input tokens).

---

## Task 3: C# API Fix for Description-Only Intel — IMPLEMENTED

Fixed `AttachmentIntelService.GetDocumentIntelligenceAsync()` to return intel even when a notice has no attachments. Previously, it returned null if `OpportunityAttachments` was empty. Now it checks for `opportunity_attachment_summary` rows (which contain description-derived intel) before returning null.

---

## Task 4: Pipeline Status Enhancement — IMPLEMENTED

Added "STAGE 4B: Description Intel" section to `health pipeline-status` showing:
- Total notices with descriptions
- Keyword extraction completion count
- AI analysis completion count and remaining

---

## Acceptance Criteria

- [x] `extract description-ai` CLI command with --help support
- [x] AI analysis works for description-only notices (no attachments)
- [x] AI analysis includes attachment text when available alongside description
- [x] Results stored in `opportunity_attachment_summary`
- [x] C# API returns description intel for opportunities without attachments
- [x] `health pipeline-status` shows description intel stats
- [x] --dry-run mode works without API key
- [x] --force mode re-analyzes existing records
- [ ] Run backfill on existing descriptions

---

## Files Changed

| File | Change |
|------|--------|
| `fed_prospector/etl/attachment_ai_analyzer.py` | Added `analyze_descriptions()`, `_fetch_eligible_descriptions()`, `_analyze_description_notice()`, `_save_description_intel()` |
| `fed_prospector/cli/attachments.py` | Added `analyze_descriptions` CLI command, added description stats to pipeline-status |
| `fed_prospector/main.py` | Registered `description-ai` command under `extract` group |
| `api/src/FedProspector.Infrastructure/Services/AttachmentIntelService.cs` | Fixed `GetDocumentIntelligenceAsync` to return intel for description-only notices |
| `thesolution/phases/121-DESCRIPTION-INTEL-EXTRACTION.md` | This file — updated with implementation details |
| `thesolution/MASTER-PLAN.md` | Phase 121 status changed to IN PROGRESS |
