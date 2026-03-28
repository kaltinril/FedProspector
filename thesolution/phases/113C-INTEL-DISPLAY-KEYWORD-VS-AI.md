# Phase 113C: Intel Display — Keyword vs AI Side-by-Side

**Status:** PLANNED
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

## Open Questions

1. **Preferred approach:** Show the "winner" value in large font, and the other method's value smaller below/beside it. When they agree it reinforces confidence; when they differ the user spots it immediately.
2. How to handle cases where keyword found something but AI didn't (or vice versa)?
3. Should the scope summary be per-document or aggregated across all documents?
