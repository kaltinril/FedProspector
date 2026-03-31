# Phase 121B: Description Keyword Intel Extraction

## Status: COMPLETE

## Context

Phase 121 added AI-based description intel extraction (`extract description-ai`), but that costs Anthropic API tokens per opportunity. The existing keyword extraction (`extract attachment-intel`) already processes description_text as a source, but only for opportunities that also have attachments.

Phase 121B fills the gap: keyword-only intel extraction for `description_text`, independent of attachments.

## What Was Built

### CLI Command
- `python main.py extract description-intel [--notice-id X] [--batch-size N] [--force]`
- Runs the same keyword patterns as `extract attachment-intel` but only against `opportunity.description_text`
- No AI, no API costs — pure regex/keyword extraction

### Implementation
- Extended `AttachmentIntelExtractor` with `description_only` flag
- When `description_only=True`:
  - `_fetch_eligible_notices()` only selects notices with `description_text`
  - `_gather_text_sources()` only returns description text, skips attachments
- Results stored in `opportunity_attachment_summary` with `extraction_method='description_keyword'`
- Added `'description_keyword'` to ENUM in `document_intel_summary`, `document_intel_evidence`, and `opportunity_attachment_summary`

### Daily Load
- Added as step 11/17 in `daily_load.bat`
- Runs after attachment-intel (step 10), before identifier extraction (step 12)
- Skips already-processed notices (idempotent)

## Files Modified

- `fed_prospector/db/schema/tables/36_attachment.sql` — ENUM update
- `fed_prospector/etl/attachment_intel_extractor.py` — description_only flag
- `fed_prospector/cli/attachments.py` — new CLI command
- `fed_prospector/main.py` — command registration
- `daily_load.bat` — added step 11/17

## Dependencies

- Phase 112 (Description Backfill) — provides `description_text` data
- Phase 110 (Attachment Intelligence) — provides the keyword extraction engine
