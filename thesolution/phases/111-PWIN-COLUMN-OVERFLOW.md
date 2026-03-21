# Phase 111: pWin Column Overflow Fix

**Status:** PLANNED
**Priority:** Medium — visual bug affecting the opportunity search/list grid
**Dependencies:** None

## Problem

The pWin circular gauge in the opportunity list/grid overflows its row cell. The animated circle graphic is too large for the table row height, causing it to bleed into adjacent rows. This is visible on the main opportunity search results page.

Screenshot evidence: the pWin column shows circular progress indicators (54%, 51%, 62%, etc.) that extend beyond the row boundaries, overlapping with rows above and below.

## Options

1. **Shrink the circular gauge** — reduce the diameter to fit within the standard row height
2. **Replace with a colored number** — remove the circle entirely, show just the percentage with a color indicator (green >=60%, orange 40-59%, red <40%). Simpler, more compact, better for dense data grids.
3. **Replace with a small colored chip** — MUI Chip with colored background showing the percentage (similar to qScore column)
4. **Hybrid** — small inline progress bar or mini gauge that fits in the row

## Recommendation

Option 2 or 3 — match the qScore column's chip style for visual consistency. The circular gauge is cool for the detail page but too bulky for a dense list view.

## Files to Investigate

- The pWin column renderer in the opportunity list/grid component
- The `PWinGauge` component (likely in `ui/src/components/shared/`)
- The grid/table column definitions

## Tasks

| # | Task | Complexity |
|---|------|-----------|
| 1 | Identify the pWin column renderer in the opportunity list grid | Low |
| 2 | Create a compact pWin display (colored number or chip) for list view | Low |
| 3 | Keep the full circular gauge on the detail page only | Low |
