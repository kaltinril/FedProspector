# Phase 110C: AI Document Analysis & Opportunity Column Backfill

**Status:** COMPLETE
**Priority:** Medium — completes the AI tier of the hybrid extraction pipeline
**Dependencies:** Phase 110 (attachment download, text extraction, keyword intel — all complete)

---

## Summary

Add AI-powered document analysis to the attachment pipeline and backfill opportunity columns from extracted intel. Two independent workstreams: column backfill (Task 1) and AI analysis (Tasks 2–4).

---

## Task 1: Populate Reserved Opportunity Columns (Backfill)

New CLI command: `python main.py backfill opportunity-intel [--notice-id=X]`

Backfill the reserved columns on the `opportunity` table from the best-available intel in `opportunity_attachment_intel`:

- `security_clearance_required` <- from `clearance_required`
- `incumbent_name` <- from recompete analysis (already done in Phase 110)
- `incumbent_uei` <- **moved to Phase 110D** (resolved via entity table lookup, not document extraction — UEIs don't appear in solicitation documents)
- `contract_vehicle_type` <- from vehicle detection

This makes intel available in existing opportunity queries and grid columns without joining to the intel tables.

**Existing code note:** `_update_opportunity_columns()` in `attachment_intel_extractor.py` (lines 1195–1236) already does this inline during extraction, but only for the opportunity being processed. Task 1 creates a standalone command that can backfill all opportunities at once (or re-run after AI analysis upgrades intel).

**Source:** Phase 110, Task 5

---

## Task 2: AI Analyzer Module (Python)

New module: `fed_prospector/etl/attachment_ai_analyzer.py`

Sends extracted document text to Claude for structured analysis. Extracts insights that help the user evaluate the opportunity: incumbent info, risk signals, contract vehicle, clearance requirements, evaluation criteria, labor categories, key requirements, scope summary, etc.

### How it works

1. Query attachments that have `extraction_status = 'extracted'` and extracted text but no AI intel row yet
2. Build a structured prompt: system prompt + document text + JSON output schema
3. Submit to Claude Haiku 4.5 via Anthropic Batch API (or single-message API for on-demand)
4. Parse the structured JSON response
5. Upsert into `opportunity_attachment_intel` with `extraction_method = 'ai_haiku'` (or `'ai_sonnet'`)
6. AI results override keyword results when confidence is higher
7. After AI analysis, run the column backfill (Task 1 logic) to update opportunity-level columns

### Intel fields to extract

Same fields as keyword extraction, but with higher accuracy:
- Clearance required (Y/N), level, scope, details
- Evaluation method and criteria
- Contract vehicle type and details
- Recompete status and incumbent name
- Scope summary
- Period of performance
- Labor categories (JSON list)
- Key requirements (JSON list)
- Overall confidence + per-field confidence

### Cost estimates (Haiku 4.5 via Batch API — 50% discount)

- 1,000 docs/month: ~$3-5/month with prompt caching
- 5,000 docs/month: ~$15/month with prompt caching

**Source:** Phase 110, Task 6

---

## Task 3: CLI Integration (Daily Batch)

CLI command: `python main.py analyze attachments [--notice-id=X] [--batch-size=50] [--model=haiku] [--force] [--dry-run]`

This is for daily batch processing — run as part of the regular data loading pipeline. Analyzes all documents that have extracted text but no AI intel yet.

The placeholder already exists in `cli/attachments.py` (lines 173–195) — just prints "not yet implemented."

---

## Task 4: UI-Triggered Analysis (On-Demand)

The `data_load_request` table is a generic job queue (Phase 43). Award on-demand loading (`USASPENDING_AWARD`, `FPDS_AWARD`) and attachment AI analysis (`ATTACHMENT_ANALYSIS`) are separate features that share this queue — don't conflate them.

The UI "Enhance with AI" button is already wired end-to-end:
- UI calls `POST /opportunities/{noticeId}/analyze?tier=haiku`
- C# `AttachmentIntelService.RequestAnalysisAsync()` inserts a `data_load_request` row with type `ATTACHMENT_ANALYSIS`
- Python `demand_loader.py` polls `data_load_request` for PENDING rows

Currently `demand_loader.py` only handles `USASPENDING_AWARD` and `FPDS_AWARD`. Add `ATTACHMENT_ANALYSIS` case in `_process_request()` to route to the AI analyzer for that specific opportunity's documents.

### Future UI consideration

Currently the "Enhance with AI" button is per-opportunity. Could also add per-document analyze buttons in the attachment list table — but this can be a follow-up since the per-opportunity button already covers the main use case.

---

## Dry-Run Safety

**Critical:** The attachment cleanup stage (`attachment_cleanup.py` lines 155–158) checks for `extraction_method IN ('ai_haiku', 'ai_sonnet')` before allowing file deletion. If dry-run wrote intel rows with `ai_haiku`, cleanup would think the pipeline is complete and delete attachment files — leaving nothing for real AI analysis later.

**Solution:** `--dry-run` mode must:
- Use `extraction_method = 'ai_dry_run'` (NOT `'ai_haiku'` or `'ai_sonnet'`)
- This value is NOT in the cleanup eligibility check, so files are preserved
- Run the full pipeline end-to-end: prompt building, (mock) response parsing, intel merging, confidence scoring
- Log what would be sent to the API and what results would look like
- When the user later adds an `ANTHROPIC_API_KEY` and runs without `--dry-run`, real `ai_haiku` rows replace the dry-run rows and cleanup can proceed normally

**Schema change:** The `extraction_method` ENUM on `opportunity_attachment_intel` currently allows `('keyword','heuristic','ai_haiku','ai_sonnet')`. Must ALTER TABLE to add `'ai_dry_run'`.

---

## API Key & Dependencies

- Requires `ANTHROPIC_API_KEY` in `fed_prospector/.env`
- Add `anthropic` package to `requirements.txt`
- Without a key, only `--dry-run` mode is available (graceful error message if key missing and no `--dry-run`)

---

## Cleanup Integration

Once a document has a real AI intel row (`ai_haiku` or `ai_sonnet`), the existing cleanup pipeline (`attachment_cleanup.py`) considers it fully analyzed and eligible for physical file deletion. This saves disk space — the extracted text and intel are preserved in the database; only the original file is removed.

No changes needed to cleanup — it already checks for AI extraction_method values.

---

## Request Poller & Scheduling

The request poller (`demand process-requests --watch`) and scheduling (daily batch runs, automation) are out of scope for this phase. See:
- **Phase 110X** — Scheduled & Automated Analysis (cron-style recurring jobs)
- **Phase 110Y** — Request Poller Service (add poller to `fed_prospector.py start/stop`)

For now, AI analysis is triggered via CLI (`analyze attachments`) or by manually running `demand process-requests` to pick up UI button requests.

---

## Code Touchpoints

### New files

| File | Purpose |
|------|---------|
| `fed_prospector/etl/attachment_ai_analyzer.py` | Core AI analyzer module (Task 2) |
| `fed_prospector/cli/backfill.py` | Backfill CLI commands (Task 1) |

### Modified files

| File | What to do |
|------|------------|
| `fed_prospector/cli/attachments.py:173–195` | Replace placeholder `analyze_attachments` with real implementation (Task 3) |
| `fed_prospector/etl/demand_loader.py:66–74` | Add `ATTACHMENT_ANALYSIS` request routing (Task 4) |
| `fed_prospector/db/schema/tables/36_attachment.sql` | ALTER ENUM to add `'ai_dry_run'` |
| `fed_prospector/requirements.txt` | Add `anthropic` package |
| `fed_prospector/main.py` | Register `backfill` command group |

### Reference files (read, don't modify)

| File | What to reference |
|------|-------------------|
| `fed_prospector/etl/attachment_intel_extractor.py:871–944` | `_upsert_intel_row()` — pattern for writing intel rows |
| `fed_prospector/etl/attachment_intel_extractor.py:1195–1236` | `_update_opportunity_columns()` — backfill logic to reuse |

## Implementation Notes

- Task 1 is standalone — straightforward SQL UPDATE from intel tables -> opportunity columns
- Tasks 2–4 share the same analyzer module, just different entry points (CLI batch vs on-demand request)
- The `analyze_attachments` CLI command already exists as a placeholder
- The Document Intelligence UI tab already handles all states (Phase 111, Issue 5)

## Completion Notes

- **AI prompt tuned with domain knowledge**: Public Trust/suitability as clearance, FAR 15.101-1/2 for eval methods, all known GWACs, recompete signals (bridge/successor/transition), structured labor categories with clearance/experience, compliance certs (CMMI/FedRAMP/ISO), pricing structure, place of performance, and set-aside detection. Prompt instructs AI to focus on bid/no-bid decision factors for a WOSB owner.
- **Backfill is separate**: AI analyzer writes only to `opportunity_attachment_intel`. It does NOT update `opportunity` columns inline. Backfill is a separate, re-runnable command (`python main.py backfill opportunity-intel`).
- **Cost discovery**: Analyzing all 24K extracted docs would cost ~$523 at Haiku pricing. Bulk analysis is impractical — designed for on-demand per-opportunity use via the UI "Enhance with AI" button.
- **API key setup**: Anthropic free tier still requires a $5 minimum credit purchase. Key goes in `fed_prospector/.env` as `ANTHROPIC_API_KEY`.
- **Three UI issues discovered**: AI results replace keyword results, confidence shows "unknown", AI has no source provenance. Tracked in Phase 110G.
