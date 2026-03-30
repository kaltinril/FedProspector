# Phase 113C: Intel Display — Keyword vs AI Side-by-Side

**Status:** IN PROGRESS
**Priority:** Medium — AI analysis results exist but aren't visually distinguished from keyword results
**Dependencies:** Phase 110ZZZ (table merge complete)

---

## Summary

After Phase 110ZZZ merged keyword and AI intel into `document_intel_summary`, the UI shows merged badges (Keyword + AI Haiku) but doesn't visually separate the two methods' results. The AI produces richer content (scope summaries, narrative analysis) that gets lost.

## Problem

- Intel cards show a single value (e.g., "Top Secret") with both badges, but the user can't see what each method found independently
- AI `scope_summary` (full paragraph narrative) is never displayed anywhere
- The "Enhance with AI" button still shows even when AI analysis is already complete

## Proposed UX

### Side-by-Side Values in Intel Cards

Show keyword and AI results next to each other in the same card:

```
┌─────────────────────────────────────────────────────┐
│ Security Clearance         [Keyword] [AI Haiku] high│
│                                                     │
│ Top Secret                    AI: Top Secret        │
│                                                     │
│ View Sources (47 from 81 matches)                 ▼ │
└─────────────────────────────────────────────────────┘
```

When values agree, it reinforces confidence. When they differ, it flags something worth investigating.

### AI Scope Summary

Display the AI's `scope_summary` field prominently — it's a narrative paragraph summarizing the opportunity scope. Could be:
- A dedicated card at the top of the Document Intel tab
- An expandable section above the per-field cards

### "Enhance with AI" Button State

- If AI intel exists for all documents: hide the button or change to "Re-analyze with AI"
- If AI intel exists for some: show "Enhance remaining with AI (N left)"
- If no AI intel: current "Enhance with AI" behavior

### Per-Attachment Breakdown

In the per-attachment accordion, show keyword and AI as separate rows/sections so the user can see each method's findings per document.

---

## Data Available

The `document_intel_summary` table has `extraction_method` (keyword vs ai_haiku vs ai_sonnet) so the API can return grouped results. Key AI-only fields:
- `scope_summary` — narrative paragraph (not populated by keyword extraction)
- `labor_categories` — JSON array (AI extracts structured labor cat data)
- Richer detail text in clearance_details, eval_details, etc.

## Decisions

1. **Side-by-side approach:** Show the aggregated "winner" value as primary. Below it, show per-method values in a compact row (e.g., `Keyword: Secret | AI: Top Secret`). When they agree, show a single value with a green checkmark. When they differ, show both with amber highlight.
2. **Missing method:** Show "—" for the method that didn't find a value. This makes gaps visible.
3. **Scope summary:** Show aggregated (longest from best confidence) at the top as a dedicated card. Per-document scope summaries available in the per-attachment accordion.

## Implementation Plan

### API Changes (C#)

1. **New DTO**: `MethodIntelDto` — per-method field values (clearance, eval, vehicle, etc. + scopeSummary, laborCategories)
2. **Add to `DocumentIntelligenceDto`**: `Dictionary<string, MethodIntelDto> MethodBreakdown` — keyed by extraction_method
3. **Update `AttachmentIntelService`**: Group intel records by method, aggregate within each group, populate `MethodBreakdown`
4. **Update `AttachmentIntelBreakdownDto`**: Add `scopeSummary` field; return one entry per attachment+method combo so UI can group

### UI Changes (React/TypeScript)

1. **Types**: Add `MethodIntelDto` interface, update `DocumentIntelligenceDto` and `AttachmentIntelBreakdownDto`
2. **Scope Summary Card**: New card at top of intel section showing aggregated scope summary with AI badge
3. **IntelCard enhancement**: Below primary value, add per-method comparison row; highlight agreement/disagreement
4. **Enhance button**: Use `analyzedCount` vs `attachmentCount` + `availableMethods` to show smart state
5. **Per-Attachment accordion**: Group entries by filename, show method rows within each group
