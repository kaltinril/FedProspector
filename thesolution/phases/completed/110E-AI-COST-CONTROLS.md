# Phase 110E: AI Analysis Cost Controls & Usage Tracking

**Status:** COMPLETE
**Priority:** High — required before enabling AI analysis for users
**Dependencies:** Phase 110C (AI analyzer module — complete)

---

## Summary

Add cost estimation, confirmation UX, and usage tracking so users can make informed decisions about AI analysis costs and administrators can monitor spending. Three tasks: cost estimation popup, usage tracking, and spending visibility.

---

## Task 1: Cost Estimation & Confirmation Popup

Before running AI analysis, show users the estimated cost and get confirmation.

### Backend: Cost Estimate Endpoint

New endpoint: `GET /opportunities/{noticeId}/analyze/estimate`

Returns estimated cost for analyzing all unanalyzed attachments for that opportunity:

```json
{
    "noticeId": "abc123",
    "attachmentCount": 5,
    "totalChars": 245000,
    "estimatedInputTokens": 61250,
    "estimatedOutputTokens": 2500,
    "estimatedCostUsd": 0.07,
    "model": "haiku",
    "alreadyAnalyzed": 2,
    "remainingToAnalyze": 3
}
```

Logic:
- Query `opportunity_attachment` for extracted text char lengths where no AI intel row exists
- Estimate tokens: chars / 4 (rough approximation)
- Add system prompt tokens (~800) per document
- Calculate cost using model pricing (Haiku: $1/$5 per MTok)
- Cap estimated text at 100K chars per doc (matching analyzer truncation limit)

### C# Implementation

- Add `GetAnalysisEstimateAsync(string noticeId, string model)` to `IAttachmentIntelService`
- Add `AnalysisEstimateDto` to DTOs
- Add controller endpoint in `OpportunitiesController`

### UI: Confirmation Dialog

When user clicks "Enhance with AI":
1. Call the estimate endpoint
2. Show a confirmation dialog:
   - "Analyze {n} documents with Claude Haiku?"
   - "Estimated cost: $0.07"
   - "Estimated tokens: ~61K input, ~2.5K output"
   - [Cancel] [Analyze]
3. Only submit the analysis request if user confirms

If all attachments already have AI intel, show "All documents already analyzed. Re-analyze?" with the same cost estimate.

---

## Task 2: Usage Tracking

Track every AI analysis API call with token counts and costs.

### Database Table

New table: `ai_usage_log`

```sql
CREATE TABLE IF NOT EXISTS ai_usage_log (
    usage_id          INT AUTO_INCREMENT PRIMARY KEY,
    notice_id         VARCHAR(100) NOT NULL,
    attachment_id     INT,
    model             VARCHAR(50) NOT NULL,
    input_tokens      INT NOT NULL,
    output_tokens     INT NOT NULL,
    cache_read_tokens INT DEFAULT 0,
    cache_write_tokens INT DEFAULT 0,
    cost_usd          DECIMAL(10,6) NOT NULL,
    requested_by      INT,
    created_at        DATETIME DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_notice (notice_id),
    INDEX idx_created (created_at),
    INDEX idx_requested_by (requested_by)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

### Python Changes

In `attachment_ai_analyzer.py`, after each successful API call:
- Read `response.usage.input_tokens` and `response.usage.output_tokens`
- Read `response.usage.cache_creation_input_tokens` and `response.usage.cache_read_input_tokens` if present
- Calculate actual cost from token counts and model pricing
- Insert row into `ai_usage_log`

Model pricing constants (per million tokens):

| Model | Input | Output | Cache Read | Cache Write |
|-------|-------|--------|------------|-------------|
| Haiku 4.5 | $1.00 | $5.00 | $0.10 | $1.25 |
| Sonnet 4.6 | $3.00 | $15.00 | $0.30 | $3.75 |

### DDL File

Add table to `fed_prospector/db/schema/tables/` as a new file (e.g., `70_ai_usage.sql`).

---

## Task 3: Spending Visibility

Surface usage data in the app so admins can monitor AI spending.

### Backend: Usage Summary Endpoint

New endpoint: `GET /admin/ai-usage`

Query parameters: `?days=30` (default 30)

Returns:

```json
{
    "period": "last 30 days",
    "totalCostUsd": 12.45,
    "totalInputTokens": 8234000,
    "totalOutputTokens": 456000,
    "totalRequests": 342,
    "totalDocuments": 891,
    "byModel": [
        { "model": "haiku", "costUsd": 10.20, "requests": 330 },
        { "model": "sonnet", "costUsd": 2.25, "requests": 12 }
    ],
    "byDay": [
        { "date": "2026-03-23", "costUsd": 0.45, "requests": 12 },
        ...
    ]
}
```

### UI: AI Usage Panel

Add to an existing admin or settings page (or the health/pipeline-status area):
- Total spend for the period
- Chart of daily spending
- Breakdown by model
- Top opportunities by cost

Keep it simple — a summary card or collapsible section, not a full page.

### CLI: Usage Report

New command: `python main.py health ai-usage [--days=30]`

Prints a summary table of AI analysis spending to the console.

---

## Code Touchpoints

### New files

| File | Purpose |
|------|---------|
| `fed_prospector/db/schema/tables/70_ai_usage.sql` | ai_usage_log table DDL |

### Modified files

| File | What to do |
|------|------------|
| `fed_prospector/etl/attachment_ai_analyzer.py` | Log usage after each API call |
| `api/src/FedProspector.Api/Controllers/OpportunitiesController.cs` | Add estimate endpoint |
| `api/src/FedProspector.Infrastructure/Services/AttachmentIntelService.cs` | Add estimate logic |
| `api/src/FedProspector.Core/Interfaces/IAttachmentIntelService.cs` | Add estimate method |
| `api/src/FedProspector.Core/DTOs/` | Add AnalysisEstimateDto, AiUsageSummaryDto |
| `ui/src/pages/opportunities/DocumentIntelligenceTab.tsx` | Confirmation dialog |
| `ui/src/api/opportunities.ts` | Add estimate API call |

---

## Implementation Notes

- Task 1 (estimate + confirmation) is the most important — prevents accidental spending
- Task 2 (tracking) should be done alongside Task 1 so we have data from the start
- Task 3 (visibility) can be a fast follow since it just reads the usage log
- No Anthropic API endpoint exists for checking remaining credits (open feature request), so we track spend ourselves
- Cost estimates are approximate — actual cost may vary due to prompt caching, tokenizer differences
- Token estimation uses chars/4 as a conservative approximation (typical English prose: 1 token ≈ 3-4 chars)
- UI-triggered analysis uses on-demand (single-message) API at standard pricing; CLI batch uses same API currently (no Batch API discount yet)
- The analyzer truncates text at 100K chars per document — cost estimate must cap per-doc text at the same limit
- `response.usage` is available on every Anthropic response but currently discarded — Task 2 captures it
- Admin usage endpoint: add to existing `AdminController` (no new admin page needed for MVP)
- CLI command location: add `ai-usage` subcommand under existing `health` group in `cli/health.py`

## Completion Notes

- **Task 1 (Cost Estimation & Confirmation)**: New endpoint `GET /opportunities/{noticeId}/analyze/estimate` returns token/cost estimates before analysis. UI shows a confirmation dialog with estimated cost when the user clicks "Enhance with AI", preventing accidental spending.
- **Task 2 (Usage Tracking)**: New `ai_usage_log` table (DDL: `75_ai_usage.sql`) records every AI API call with token counts and calculated cost. `MODEL_PRICING` constants added to the analyzer. `_log_usage()` method in `attachment_ai_analyzer.py` inserts a row after each successful API call. `requested_by` user ID flows through from `demand_loader` for UI-triggered analysis.
- **Task 3 (Spending Visibility)**: CLI command `python main.py health ai-usage [--days=30]` prints a summary table of AI spending. C# endpoint `GET /api/v1/admin/ai-usage?days=30` returns `AiUsageSummaryDto` with totals, per-model breakdown, and daily breakdown.
- **CLI rename**: `analyze attachments` command renamed to `extract attachment-ai` for consistency with the existing `extract attachment-text` and `extract attachment-intel` commands.
