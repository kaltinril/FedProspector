# Phase 110C: AI Document Analysis & Opportunity Column Backfill

**Status:** PLANNED
**Priority:** Medium — completes the AI tier of the hybrid extraction pipeline
**Dependencies:** Phase 110 (attachment download, text extraction, keyword intel — all complete)

---

## Summary

Two remaining items from Phase 110 that were deferred to ship the keyword extraction pipeline first.

---

## Task 1: Populate Reserved Opportunity Columns (Backfill)

After keyword intel extraction runs, backfill the reserved columns on the `opportunity` table from the best-available intel in `opportunity_attachment_intel`:

- `security_clearance_required` <- from `clearance_required`
- `incumbent_uei` / `incumbent_name` <- from recompete analysis
- `contract_vehicle_type` <- from vehicle detection

This makes intel available in existing opportunity queries and grid columns without joining to the intel tables. Should run as a post-extraction step (add to keyword extractor or as a separate CLI command).

**Source:** Phase 110, Task 5

---

## Task 2: Claude Batch API Integration (AI Tier)

New module: `fed_prospector/etl/attachment_ai_analyzer.py`

- Build structured extraction prompt (system prompt + document text + JSON schema)
- Submit documents to Claude Haiku 4.5 via Anthropic Batch API
- Process batch results and merge with keyword-extracted intel
- AI results override keyword results when confidence is higher
- Track API usage and costs in `etl_load_log`
- CLI: `python main.py analyze attachments [--notice-id=X] [--batch-size=50] [--model=haiku] [--force]`

Cost estimates (Haiku 4.5 via Batch API — 50% discount):
- 1,000 docs/month: ~$3-5/month with prompt caching
- 5,000 docs/month: ~$15/month with prompt caching

The UI already supports this — the "Enhance with AI" button on the Document Intelligence tab queues a `data_load_request` with type `ATTACHMENT_ANALYSIS`. The Python CLI poller needs to handle this request type by running the AI analyzer.

**Source:** Phase 110, Task 6

---

## Implementation Notes

- Task 1 is straightforward SQL UPDATE from intel tables -> opportunity columns
- Task 2 requires Anthropic SDK integration and prompt engineering
- Both tasks are independent and can be done in either order
- The Document Intelligence UI tab already handles all states (Phase 111, Issue 5)
