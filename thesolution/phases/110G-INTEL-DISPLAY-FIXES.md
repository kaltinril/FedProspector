# Phase 110G: Document Intelligence Display Fixes

**Status:** PLANNED
**Priority:** Critical — AI analysis results are hiding keyword results and showing broken confidence
**Dependencies:** Phase 110C (AI analyzer — complete)

---

## Summary

The Document Intelligence tab should give users a simple two-level experience:

**Level 1 — The Answer:** One clear, high-level value per category (Security Clearance: Y / TS/SCI, Eval Method: Best Value, etc.). This is the aggregated best answer across all attachments and all extraction methods (keyword + AI). The user glances at this and knows the key facts.

**Level 2 — The Evidence:** Drill into any answer to see WHERE it came from and HOW it was determined. Each source shows: which attachment, which extraction method (Keyword vs AI), and the supporting detail. **Keyword sources are the gold standard here** — they show the exact matched text, page number, and character offset in the original document. This is the single most valuable feature of the intel tab: the user can verify any answer without re-reading the full document. AI sources supplement this with explanation paragraphs that interpret what the matches mean. Both must always be visible; AI must NEVER hide or replace keyword sources.

### Current Problems

The tab is broken in seven ways that prevent this experience from working:
1. AI results replace keyword results instead of coexisting
2. Confidence badges show "unknown" instead of actual values
3. AI results have no source provenance (no "View Sources")
4. Attachments not clickable — user can't open the original document on SAM.gov
5. Cross-attachment aggregation picks wrong values (e.g., shows clearance "N" from one doc while 5 others say "Y")
6. AI's rich explanation text (clearance_details, eval_details, etc.) is not displayed anywhere
7. No per-attachment drill-down to see what each document contributed

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

## Problem 4: Attachments Not Clickable

### Root Cause

The attachment list at the bottom of the Document Intelligence tab shows filenames but they are not clickable. Users cannot open the original document to verify intel or read the full solicitation.

### Fix

Make each attachment filename a link to the document on SAM.gov. The `opportunity_attachment` table already stores `url` (the SAM.gov download URL, e.g., `https://sam.gov/api/prod/opps/v3/opportunities/resources/files/.../download`). Render filenames as `<a href={url} target="_blank">` links. If `url` is null, show the filename as plain text (not clickable). The URL is already populated for all attachments.

No need to build a document viewer — just link to SAM.gov where the user can download/read it directly.

---

## Problem 5: Cross-Attachment Aggregation is Broken

### Root Cause

When multiple attachments have AI intel, the UI displays a single merged view — but the merge logic is naive. It picks one attachment's value per field without domain-specific rules.

**Real example (notice 63d402fe...):**
- Security Clearance shows **"N"** — picked up from attachment 21076 (Q&A doc that said "not currently a requirement")
- But **5 other attachments** say "Y" with TS/SCI, Top Secret, or Secret
- The correct answer is "Y" / "TS/SCI" — the highest clearance level from any document

Similarly:
- Period of Performance shows "Not specified in Q&A document" — a doc-specific note that makes no sense as an aggregated value
- Incumbent name shows a long string from one Q&A answer rather than a clean name

### Fix

Implement domain-specific aggregation rules when merging intel across attachments:

| Field | Rule |
|-------|------|
| `clearance_required` | "Y" wins over "N" wins over null |
| `clearance_level` | Highest level wins: TS/SCI > Top Secret > Secret > Confidential > Public Trust > null |
| `eval_method` | Most specific wins; prefer concrete (LPTA, Best Value) over null |
| `vehicle_type` | Most specific wins; prefer named vehicle over generic "IDIQ" |
| `is_recompete` | "Y" wins over "N" wins over null (any evidence of recompete = recompete) |
| `incumbent_name` | Prefer shortest non-null value (likely the clean name, not a sentence) |
| `scope_summary` | Prefer longest non-null value from highest-confidence attachment |
| `period_of_performance` | Prefer values that contain actual durations, not "not specified" |

This aggregation should happen in the C# service when building the `DocumentIntelligenceDto`, not in the UI.

---

## Problem 6: Detail Text Fields Not Displayed

### Root Cause

AI extracts rich explanation fields (`clearance_details`, `eval_details`, `vehicle_details`, `recompete_details`) that provide the actual useful analysis — e.g., "TS FCL required at proposal submission, both JV partners need it, SCI on Day 1." These fields exist in the database but are not included in the DTO or shown in the UI.

The keyword extractor dumps raw pattern matches into these fields (e.g., "clearance_ts_sci: TS/SCI; clearance_ts_sci: TS/SCI" repeated 7 times), which was never useful to display. But the AI versions are concise, human-readable explanations that are the most valuable part of the analysis.

### Fix

1. Add `clearance_details`, `eval_details`, `vehicle_details`, `recompete_details` to `DocumentIntelligenceDto`
2. Only populate from AI intel records (keyword detail fields are raw pattern dumps, not user-facing)
3. Display as expandable text beneath each intel card in the UI — e.g., clicking the "Security Clearance: Y / TS/SCI" card expands to show the AI's explanation
4. This complements Problem 3's source provenance — sources show "where" the info came from, details show "what it means"

---

## Problem 7: No Per-Attachment Drill-Down

### Root Cause

The UI shows one merged view across all attachments. Users cannot see what each individual document contributed to the analysis. For a 12-attachment solicitation like SOFGSD, different documents contain different information (SOW has scope, Section M has eval criteria, Section L has proposal instructions, LCATs doc has labor categories).

### Fix

Add an expandable per-attachment section below the merged summary:
- Collapsible list of attachments that had AI analysis
- Each shows: filename, confidence level, and the key fields that attachment contributed
- Clicking expands to show that attachment's full AI analysis
- This lets users trace any merged field back to its source document

This is lower priority than Problems 4-5 but significantly improves transparency.

---

## Code Touchpoints

### Modified files

| File | What to do |
|------|------------|
| `api/src/FedProspector.Infrastructure/Services/AttachmentIntelService.cs` | Cross-attachment aggregation with domain rules (P5), return sources from ALL methods (P1), add overall_confidence/confidence_details/detail fields to DTO (P2, P6), include attachment URLs (P4) |
| `api/src/FedProspector.Core/DTOs/Intelligence/AttachmentIntelDtos.cs` | Add OverallConfidence, ConfidenceDetails, AvailableMethods, detail text fields, per-attachment breakdown to DTO (P2, P6, P7) |
| `ui/src/pages/opportunities/DocumentIntelligenceTab.tsx` | Use intel-level confidence (P2), clickable attachment links (P4), show detail text fields as expandable content (P6), show sources from all methods (P1), per-attachment drill-down (P7) |
| `ui/src/types/api.ts` | Update DocumentIntelligenceDto type |
| `fed_prospector/etl/attachment_ai_analyzer.py` | Write source rows to opportunity_intel_source after AI analysis (P3) |

---

## Implementation Order

1. **Problem 5 first** (cross-attachment aggregation) — fixes the most visible bug (wrong clearance value). Backend-only change.
2. **Problem 3 next** (AI writes source rows) — Python-only, independent, immediately improves AI results
3. **Problem 2 next** (confidence fix) — DTO + UI change, quick fix
4. **Problem 4 next** (clickable attachments) — quick UI win, link filenames to SAM.gov URLs
5. **Problem 6 next** (detail text fields) — DTO + UI, high value — shows the AI explanations that justify the cost
6. **Problem 1 next** (merged sources from all methods) — backend query + DTO + UI display
7. **Problem 7 last** (per-attachment drill-down) — optional/lower priority, largest UI change

---

## Testing

After implementation, verify with test opportunity `63d402fe5ab14912ac95ac72ae5f639a` (SOFGSD, 12 attachments, both keyword and AI intel):

1. Security Clearance should show "Y" / "TS/SCI" (not "N" from one Q&A doc)
2. Confidence badges show actual values (high/medium/low), not "unknown"
3. Detail text visible — clicking clearance card shows "TS FCL required at proposal submission..."
4. Keyword sources still show exact document locations ("View Sources") — **do not lose this**
5. AI sources show explanation text
6. Attachment filenames are clickable links that open the SAM.gov download URL
7. Re-analyze button still works
8. Header shows both extraction methods
9. Optional: per-attachment view shows what each of the 12 docs contributed
