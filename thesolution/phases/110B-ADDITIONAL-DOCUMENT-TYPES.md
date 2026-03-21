# Phase 110B: Additional Document Type Extraction

**Status:** PLANNED
**Priority:** Medium — adds coverage for 508 more attachments (doc: 250, pptx: 140, xls: 98, rtf: 17, odt: 3), raising pipeline coverage from 97.8% to 98.8%
**Dependencies:** Phase 110 (attachment text extraction pipeline must exist)

---

## Goal

Add text extraction support for the 5 remaining document types found in SAM.gov opportunity attachments that contain real solicitation content: legacy Word (.doc), PowerPoint (.pptx), legacy Excel (.xls), Rich Text Format (.rtf), and OpenDocument Text (.odt).

## What We Found (from Phase 110 Analysis)

| Extension | Count | % of 51,279 | Content | Currently |
|-----------|-------|-------------|---------|-----------|
| .doc | 250 | 0.49% | SOWs, solicitation docs in legacy Word binary format | Recognized but marked unsupported |
| .pptx | 140 | 0.27% | Pre-RFI presentations, site visit slides, industry day briefs | Not handled |
| .xls | 98 | 0.19% | Pricing schedules, wage determinations, data tables | Recognized but marked unsupported |
| .rtf | 17 | 0.03% | Specifications, SOWs in Rich Text Format | Not handled |
| .odt | 3 | 0.01% | OpenDocument Text (LibreOffice equivalent of .docx) | Not handled |

---

## Implementation

All changes are in ONE file: `fed_prospector/etl/attachment_text_extractor.py`

### Task 1: Legacy Word (.doc) Extraction

- **Library:** `antiword` system binary (most reliable for .doc) OR `textract` Python package
- **Alternative:** `python-docx` cannot read .doc (only .docx). The `doc2txt` approach or calling LibreOffice in headless mode (`soffice --headless --convert-to docx`) are fallback options.
- **Recommended:** Try `antiword` first (simple, fast, widely available). If not installed, fall back to marking as unsupported with a clear log message suggesting antiword installation.
- **Output:** Plain text (no structure-aware extraction — .doc format doesn't expose formatting easily via CLI tools)
- Add `application/msword` content type and `.doc` extension to handler routing

### Task 2: PowerPoint (.pptx) Extraction

- **Library:** `python-pptx`
- **Approach:**
  - Iterate slides in order
  - Extract text from each shape's `text_frame`
  - Slide numbers as markdown headings: `## Slide 1`, `## Slide 2`
  - Extract table contents from table shapes → markdown tables
  - Extract speaker notes from `slide.notes_slide.notes_text_frame` (often contain important context)
  - Skip image-only shapes
- Add content type: `application/vnd.openxmlformats-officedocument.presentationml.presentation`
- Add extension: `.pptx`

### Task 3: Legacy Excel (.xls) Extraction

- **Library:** `xlrd` (reads .xls binary format)
- **Approach:** Same as .xlsx handler but using xlrd API instead of openpyxl
  - Sheet names as `## SheetName` headings
  - Detect header rows → markdown table headers
  - Extract cell values as markdown tables
  - Skip empty rows/sheets
- Add content type: `application/vnd.ms-excel` (already in EXCEL_TYPES constant but handler returns None)
- Add extension: `.xls` (already in EXCEL_EXTENSIONS but handler returns None)

### Task 4: Rich Text Format (.rtf) Extraction

- **Library:** `striprtf` (lightweight, pure Python)
- **Approach:**
  - Read .rtf file bytes
  - Use `striprtf.rtf_to_text()` to convert to plain text
  - No structure-aware extraction (RTF formatting is complex to parse for headings)
- Add content type: `application/rtf`, `text/rtf`
- Add extension: `.rtf`

### Task 5: OpenDocument Text (.odt) Extraction

- **Library:** `odfpy`
- **Approach:**
  - Load with `odf.opendocument.load()`
  - Iterate paragraphs, extract text
  - Detect heading styles → markdown headings
  - Extract tables → markdown tables
  - Similar to .docx handler but using ODF API
- Add content type: `application/vnd.oasis.opendocument.text`
- Add extension: `.odt`

---

## Python Dependencies

```
python-pptx>=1.0.0      # PowerPoint .pptx extraction
xlrd>=2.0.0              # Legacy Excel .xls extraction
striprtf>=0.0.26         # Rich Text Format extraction
odfpy>=1.4.0             # OpenDocument .odt extraction
```

For .doc files: `antiword` system binary (Windows: download from web; Linux: `apt install antiword`)

---

## Testing Checklist

- [ ] .doc file extracts text (if antiword installed) or is marked unsupported with helpful message
- [ ] .pptx file extracts slide text with slide number headings
- [ ] .pptx speaker notes are included in extraction
- [ ] .pptx tables are extracted as markdown tables
- [ ] .xls file extracts cell data as markdown tables
- [ ] .rtf file extracts plain text content
- [ ] .odt file extracts text with heading preservation
- [ ] All 5 types update extraction_status correctly
- [ ] Hash tracking works (text_hash computed for all new types)
- [ ] Corrupted/password-protected files fail gracefully

---

## Task Summary

| # | Task | Complexity | Depends On |
|---|------|-----------|------------|
| 1 | Legacy Word .doc extraction | Low-Medium | antiword binary |
| 2 | PowerPoint .pptx extraction | Medium | python-pptx |
| 3 | Legacy Excel .xls extraction | Low | xlrd |
| 4 | RTF extraction | Low | striprtf |
| 5 | OpenDocument .odt extraction | Low-Medium | odfpy |
