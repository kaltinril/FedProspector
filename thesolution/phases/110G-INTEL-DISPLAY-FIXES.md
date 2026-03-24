# Phase 110G: Document Intelligence Display Fixes

**Status:** PLANNED
**Priority:** Critical — AI analysis results are hiding keyword results and showing broken confidence
**Dependencies:** Phase 110C (AI analyzer — complete)

---

## Summary

When AI analysis runs on an opportunity, it breaks the Document Intelligence tab in three ways: keyword results disappear, confidence badges show "unknown", and AI results have no source provenance. This phase fixes all three issues so keyword and AI results coexist and both display correctly.

---

## Problem 1: AI Results Replace Keyword Results

### Root Cause

`AttachmentIntelService.GetDocumentIntelligenceAsync()` selects only ONE intel record — the "best" by extraction method priority:

```csharp
// api/src/FedProspector.Infrastructure/Services/AttachmentIntelService.cs:47-51
var bestIntel = intelRecords
    .OrderByDescending(i => ExtractionMethodPriority.GetValueOrDefault(i.ExtractionMethod ?? "", 0))
    .ThenByDescending(i => i.ExtractedAt)
    .FirstOrDefault();
```

Priority hierarchy (lines 18-24):
```csharp
private static readonly Dictionary<string, int> ExtractionMethodPriority = new()
{
    ["ai_sonnet"] = 4,
    ["ai_haiku"] = 3,
    ["heuristic"] = 2,
    ["keyword"] = 1  // <-- lowest
};
```

When AI analysis completes (priority 3 or 4), keyword results (priority 1) are never returned. The keyword data still exists in the database but is completely hidden from the UI.

### Impact

- User loses "View Sources (4)" with exact document locations — the most useful part of keyword extraction
- The before/after experience is: 3 intel cards with source evidence → 6 intel cards with no sources and "unknown" confidence
- User perceives AI as making things worse, not better

### Fix

Change the backend to return **both** keyword and AI results. Two approaches:

**Option A: Merged view with source attribution** (recommended)
- For each intelligence field (clearance, eval_method, vehicle, etc.), return the best value but include sources from ALL methods
- If AI and keyword agree, show one value with combined sources
- If they disagree, show the AI value as primary with keyword value noted as an alternative
- Always include keyword sources (document locations) even when AI is the primary

**Option B: Side-by-side methods**
- Return all extraction methods as separate objects in the DTO
- UI shows a toggle or tabs: "Keyword" | "AI (Haiku)"
- User can switch between views
- The existing "Keyword" / "AI (Haiku)" chip in the header already hints at this pattern

### Implementation (Option A — Merged)

#### DTO Changes

Update `DocumentIntelligenceDto` to include sources from all methods:

```csharp
// Current: sources only from best intel record
// New: sources from ALL intel records for this notice

public class DocumentIntelligenceDto
{
    // ... existing fields stay the same ...

    // NEW: which extraction methods contributed
    public string LatestExtractionMethod { get; set; }  // existing
    public List<string> AvailableMethods { get; set; } = new();  // NEW

    // Sources already includes field_name — just need to include from all methods
    public List<IntelSourceDto> Sources { get; set; } = new();
}
```

#### Service Changes

In `AttachmentIntelService.GetDocumentIntelligenceAsync()`:

1. Still pick the "best" intel record for field values (AI > keyword)
2. But fetch sources from ALL intel records for the notice, not just the best one:

```csharp
// Current (line 57-59):
sources = await _context.OpportunityIntelSources.AsNoTracking()
    .Where(s => s.IntelId == bestIntel.IntelId)
    .ToListAsync();

// New:
var allIntelIds = intelRecords.Select(i => i.IntelId).ToList();
sources = await _context.OpportunityIntelSources.AsNoTracking()
    .Where(s => allIntelIds.Contains(s.IntelId))
    .ToListAsync();
```

3. Populate `AvailableMethods` from the distinct extraction methods found.

#### UI Changes

- Show sources from both keyword and AI grouped by extraction method
- Keyword sources show document location (filename, page, matched text) — these are the "proof"
- AI sources show the AI's explanation (from confidence_details or clearance_details)
- The header chip should show both methods: "Keyword" + "AI (Haiku)" instead of just one

---

## Problem 2: Confidence Shows "unknown"

### Root Cause

Two issues combine:

**Issue A:** The UI gets confidence from individual source rows, not from the intel record itself:

```typescript
// ui/src/pages/opportunities/DocumentIntelligenceTab.tsx:78
const confidence = topSource?.confidence ?? 'unknown';
```

For AI results, there are NO source rows in `opportunity_intel_source` (the AI analyzer doesn't write them). So `topSource` is undefined → confidence = "unknown".

**Issue B:** Even for keyword results, the C# service maps null confidence to empty string:

```csharp
// AttachmentIntelService.cs:92
Confidence = s.Confidence ?? ""
```

Empty string (`""`) passes through the `??` operator in TypeScript (it's not null/undefined), so the fallback to "unknown" never triggers. An empty string renders as a blank chip.

### Fix

1. **Use `overall_confidence` from the intel record** as the primary confidence display, not from individual source rows
2. Add `overall_confidence` to the `DocumentIntelligenceDto` (it's already in the database but not returned to the UI)
3. Per-field confidence should come from `confidence_details` JSON on the intel record (already stored by both keyword and AI)
4. Source-level confidence is supplementary — show it in the expanded source list, not as the main badge

#### DTO Changes

```csharp
public class DocumentIntelligenceDto
{
    // ... existing fields ...
    public string OverallConfidence { get; set; } = "";  // NEW — from intel record
    public Dictionary<string, string>? ConfidenceDetails { get; set; }  // NEW — per-field confidence
}
```

#### Service Changes

Map from the best intel record:

```csharp
OverallConfidence = bestIntel.OverallConfidence ?? "low",
ConfidenceDetails = bestIntel.ConfidenceDetails != null
    ? JsonSerializer.Deserialize<Dictionary<string, string>>(bestIntel.ConfidenceDetails)
    : null,
```

#### UI Changes

```typescript
// Instead of deriving confidence from sources:
const confidence = intel.confidenceDetails?.[fieldKey] ?? intel.overallConfidence ?? 'unknown';
```

---

## Problem 3: AI Results Have No Source Provenance

### Root Cause

The keyword extractor writes detailed provenance to `opportunity_intel_source`:
- Which file the match was found in
- Page number
- Character offset
- Exact matched text
- Surrounding context

The AI analyzer (`attachment_ai_analyzer.py`) does NOT write to `opportunity_intel_source` at all. It only writes the structured result to `opportunity_attachment_intel`. So when the UI queries sources for AI results, it gets zero rows.

### Why This Matters

The "View Sources (4)" feature with exact document locations is the most valuable part of the Document Intelligence tab. It lets the user verify the extraction without reading the full document. Losing this when AI runs is a significant UX regression.

### Fix Options

**Option A: AI writes explanation-based sources** (recommended)
- After AI analysis, write one `opportunity_intel_source` row per non-null field
- `matched_text` = the AI's explanation (e.g., clearance_details, eval_details, recompete_details)
- `source_filename` = the attachment filename that was analyzed
- `extraction_method` = 'ai_haiku' or 'ai_sonnet'
- `confidence` = per-field confidence from confidence_details JSON
- No char_offset (AI doesn't track exact positions) — that's fine, keyword sources still have them

This means:
- Keyword sources show: "Found 'Moderate Risk' on page 12 of SOW.pdf" (exact location)
- AI sources show: "Document references FAR Part 40 safeguarding requirements..." (explanation)
- Both appear in the "View Sources" panel, grouped by method

**Option B: Return AI explanation fields directly in the DTO**
- Add clearance_details, eval_details, vehicle_details, recompete_details to the DTO
- UI shows these as "AI Analysis" text blocks alongside keyword sources
- Doesn't require writing to opportunity_intel_source

Option A is better because it uses the existing source display infrastructure without DTO changes.

#### Python Changes (attachment_ai_analyzer.py)

After saving the intel row in `_save_intel()`, write source rows:

```python
def _save_ai_sources(self, doc, intel_id, result):
    """Write explanation-based source rows for AI analysis results."""
    conn = get_connection()
    cursor = conn.cursor()
    try:
        # Delete any existing AI source rows for this intel_id
        cursor.execute(
            "DELETE FROM opportunity_intel_source WHERE intel_id = %s",
            (intel_id,)
        )

        # Map fields to their detail/explanation text
        field_details = {
            "clearance_level": result.get("clearance_details"),
            "eval_method": result.get("eval_details"),
            "vehicle_type": result.get("vehicle_details"),
            "is_recompete": result.get("recompete_details"),
        }

        confidence_details = result.get("confidence_details") or {}
        confidence_map = {
            "clearance_level": confidence_details.get("clearance", "medium"),
            "eval_method": confidence_details.get("evaluation", "medium"),
            "vehicle_type": confidence_details.get("vehicle", "medium"),
            "is_recompete": confidence_details.get("recompete", "medium"),
        }

        rows_inserted = 0
        for field_name, detail_text in field_details.items():
            if not detail_text:
                continue
            cursor.execute(
                "INSERT INTO opportunity_intel_source "
                "(intel_id, field_name, attachment_id, source_filename, "
                " matched_text, extraction_method, confidence) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                (
                    intel_id,
                    field_name,
                    doc["attachment_id"],
                    doc.get("filename"),
                    detail_text[:500],
                    self.extraction_method,
                    confidence_map.get(field_name, "medium"),
                ),
            )
            rows_inserted += 1

        conn.commit()
        return rows_inserted
    except Exception:
        conn.rollback()
        raise
    finally:
        cursor.close()
        conn.close()
```

This requires `_save_intel()` to return the `intel_id` so it can be passed to `_save_ai_sources()`.

---

## Code Touchpoints

### Modified files

| File | What to do |
|------|------------|
| `api/src/FedProspector.Infrastructure/Services/AttachmentIntelService.cs` | Return sources from ALL methods, add overall_confidence and confidence_details to DTO |
| `api/src/FedProspector.Core/DTOs/Intelligence/AttachmentIntelDtos.cs` | Add OverallConfidence, ConfidenceDetails, AvailableMethods to DTO |
| `ui/src/pages/opportunities/DocumentIntelligenceTab.tsx` | Use intel-level confidence instead of source-level, show sources from all methods |
| `ui/src/types/api.ts` | Update DocumentIntelligenceDto type |
| `fed_prospector/etl/attachment_ai_analyzer.py` | Write source rows to opportunity_intel_source after AI analysis |

---

## Implementation Order

1. **Problem 3 first** (Python: AI writes source rows) — can be done independently, immediately improves AI results
2. **Problem 2 next** (confidence fix) — DTO + UI change, quick fix
3. **Problem 1 last** (merged sources from all methods) — largest change, touches backend query + DTO + UI display

---

## Testing

After implementation, verify with the test opportunity `53753e7b3c214d2d948b246c2e04aea5`:

1. Before AI: keyword results show with confidence badges and "View Sources"
2. After AI: both keyword AND AI results visible, confidence badges correct
3. Keyword sources still show exact document locations
4. AI sources show explanation text
5. Re-analyze button still works
6. Header shows both extraction methods
