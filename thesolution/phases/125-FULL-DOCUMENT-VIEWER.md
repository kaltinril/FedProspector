# Phase 125: Full Document Viewer with Keyword Highlights

**Status:** PLANNED
**Priority:** Medium
**Depends on:** Phase 110ZZZ (Attachment Deduplication — provides corrected char offsets)

## Goal

Allow users to view the full extracted text of an attachment document with all keyword highlights rendered inline. Triggered by double-clicking the filename in the Document Intelligence tab.

## Background

The Document Intelligence tab currently shows keyword matches as merged passages — short text slices (±150 chars) around clustered hits. Users want to see the full document with all highlights to understand context and read surrounding content without switching to the original PDF.

Phase 110ZZZ corrected a bug where `char_offset_start`/`char_offset_end` values in `document_intel_evidence` were shifted by the filename length. Offsets are now accurate 0-based positions into `attachment_document.extracted_text`.

## Design

### Trigger
- Double-click on the **filename** in a `MergedSourceBlock` component
- Future: could also trigger from a keyword chip or the text block itself

### Display
- Full-screen MUI `Dialog` (`maxWidth="xl"`, `fullWidth`)
- Scrollable monospace text with all keyword highlights rendered inline
- Single highlight color (orange/warning — same as existing passages)
- Auto-scroll to the passage location the user clicked from
- Header showing filename, page count, document size
- Close button (top-right X and Escape key)

### API

**New endpoint:**
```
GET /api/v1/opportunities/documents/{documentId}/full-text
```

**Response DTO:**
```csharp
public class FullDocumentTextDto
{
    public int DocumentId { get; set; }
    public string Filename { get; set; }
    public string ExtractedText { get; set; }
    public int TextLength { get; set; }
    public List<HighlightSpan> Highlights { get; set; }  // All keyword evidence positions
}
```

- Reuses existing `HighlightSpan` (start, end, matchedText)
- Highlights are 0-based absolute positions in ExtractedText
- Sorted by start position, overlaps pre-merged server-side

### UI Component

**New file:** `ui/src/components/shared/FullDocumentViewerModal.tsx`

**Props:**
```typescript
interface FullDocumentViewerModalProps {
    open: boolean;
    onClose: () => void;
    documentId: number;
    scrollToOffset?: number;  // char offset to auto-scroll to on open
}
```

**Rendering approach:**
- Fetch full text + highlights from API on open
- Build text fragments (plain text interspersed with highlighted `<mark>` spans)
- Use a ref + `scrollIntoView` to jump to the passage nearest `scrollToOffset`
- Virtualization may be needed for very large documents (100K+ chars) — evaluate during implementation

### Highlight Merging
- Server returns all keyword evidence positions for the document
- Merge overlapping/adjacent spans before rendering (same logic as existing `MergedSourceBlock`)
- Tooltip on hover shows: matched keyword, field name, confidence

## Tasks

- [ ] **Task 1:** Add `FullDocumentTextDto` to C# DTOs
- [ ] **Task 2:** Add `GetFullDocumentTextAsync` to `AttachmentIntelService`
- [ ] **Task 3:** Add controller endpoint `GET /opportunities/documents/{documentId}/full-text`
- [ ] **Task 4:** Add TypeScript types and API function in `ui/src/api/opportunities.ts`
- [ ] **Task 5:** Build `FullDocumentViewerModal` component
- [ ] **Task 6:** Wire double-click on filename in `MergedSourceBlock` to open modal
- [ ] **Task 7:** Auto-scroll to clicked passage offset on modal open
- [ ] **Task 8:** Test with large documents (performance, rendering)

## Future Enhancements (not in this phase)
- Color-code highlights by intel category (clearance=red, set-aside=blue, etc.)
- Click on a keyword chip to open full doc scrolled to that match
- Search/filter within the full document view
- Side-by-side view with original PDF
- Double-click on text block to open at that specific passage
