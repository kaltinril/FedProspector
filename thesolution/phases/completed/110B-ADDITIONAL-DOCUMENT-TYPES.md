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

### Task 6: Post-Analysis File Cleanup

Files progress through a 4-stage pipeline (state machine). Cleanup is only allowed after the final stage:

```
downloaded → text extracted → keyword intel → AI analyzed → [cleanup eligible]
```

- **Command:** `python main.py cleanup attachment-files [--notice-id=X] [--dry-run] [--batch-size=1000]`
- **Safety:** Only deletes files that completed ALL 4 pipeline stages:
  1. `download_status = 'downloaded'` (file on disk)
  2. `extraction_status = 'extracted'` (text stored in DB)
  3. Has keyword/heuristic intel record in `opportunity_attachment_intel`
  4. Has AI analysis record (`extraction_method IN ('ai_haiku', 'ai_sonnet')`) — Phase 110C
- **Behavior:**
  - Deletes the physical file from `ATTACHMENT_DIR/{notice_id}/` (default `E:\fedprospector\attachments\`)
  - Sets `file_path = NULL` in `opportunity_attachment` to indicate file removed
  - Preserves all DB data: `extracted_text`, `text_hash`, `content_hash`, intel records
  - `--dry-run` shows what would be deleted with total size reclaimed
  - Cleans up empty `{notice_id}/` directories after file removal
- **Rationale:** Extracted text is stored in DB (`extracted_text` LONGTEXT column). Original files only needed for re-extraction. Saves ~90% disk space.
- **Note:** Until Phase 110C (AI analysis) is implemented, no files will be eligible for cleanup — this is intentional. The gate ensures files are never deleted before the full pipeline runs.

### Task 7: MuPDF Warning Suppression

- Suppress non-fatal MuPDF stderr warnings about malformed PDF structure trees (common in government PDFs)
- Module-level call to `fitz.TOOLS.mupdf_display_errors(False)` at import time
- Text extraction succeeds despite these warnings — they are cosmetic noise

### Task 8: PDF Table Detection Performance

- **Problem:** PyMuPDF's `find_tables()` is a C extension call that averages ~0.4s/page on text docs but 1-2s/page on CAD/drawing content. On a 584-page technical spec it took 240+ seconds. On a 43-page drawing set it took 70 seconds. The C extension cannot be cancelled once started — Python thread timeouts only control when the caller gives up, but the underlying C code keeps running.
- **Solution:** Page-count-based threshold:
  - **≤30 pages:** `find_tables()` runs with 10s per-page timeout (full table detection for solicitation docs with pricing/eval tables)
  - **>30 pages:** `find_tables()` skipped entirely (text content still fully extracted via `get_text("dict")`)
- **Rationale:** Short solicitation docs (5-20 pages) are where tables matter most (pricing schedules, eval criteria, wage determinations). Large technical specs and drawing sets don't have tables that are useful for intel extraction. Text within table cells is still captured by `get_text()` — only the markdown table formatting is lost.
- **5-30 page PDFs:** Processed in parallel (4 workers, each opens its own doc handle for thread safety)
- **Performance results:**
  - 584-page spec: hung indefinitely → **5.7s**
  - 43-page drawings: 70s → **1.6s**
  - 38-page solicitation: 4.3s → **0.2s**
  - 7-page wage determination: 0.3s → **0.3s** (unchanged, tables still detected)

### Task 9: IRM/DRM Protection Detection

- **Problem:** Some government attachments are IRM-protected (Microsoft Information Rights Management). These are OLE2 files with encrypted content that LibreOffice and python-docx cannot read. Without early detection, LibreOffice hangs or silently fails.
- **Solution:** Check OLE2 files for `EncryptedPackage` and `DataSpaces` streams using `olefile` before attempting extraction. Fails fast with a clear error message.
- **Library:** `olefile==0.47` (pure Python, lightweight)

### Task 10: .doc Extraction via LibreOffice

- **Problem:** Legacy `.doc` (Word 97-2003) format has no good pure Python extraction library. `antiword` requires a system binary.
- **Solution:** Convert `.doc → .docx` via LibreOffice headless mode (`soffice --headless --convert-to docx`), then pass to existing `_extract_docx` handler for full structure-aware extraction.
- **Dependency:** LibreOffice 25.8+ installed at `C:\Program Files\LibreOffice\program\soffice.exe`
- **Edge case:** OLE2 files with `.docx` extension (mislabeled) — copied to temp file with `.doc` extension before conversion, as LibreOffice refuses to convert OLE2 content with a `.docx` extension.
- **Environment:** Python env vars (`PYTHONPATH`, `PYTHONHOME`, `VIRTUAL_ENV`) stripped from subprocess to prevent conflict with LibreOffice's bundled Python.

### Task 11: Magic Byte File Type Detection

- **Problem:** Some attachments have incorrect file extensions (e.g., a PDF saved as `.docx`)
- **Solution:** Fall back to magic byte signature detection when extension-based handler fails
- **Signatures detected:**
  - `%PDF` → PDF
  - `PK\x03\x04` → ZIP-based (docx/pptx/xlsx/odt — distinguished by examining ZIP directory entries)
  - `\xD0\xCF\x11\xE0` → OLE2 (legacy .doc/.xls)
  - `{\rtf` → Rich Text Format
- **Behavior:** Two fallback paths:
  1. If extension/content-type gives no handler, try magic bytes before marking unsupported
  2. If extension-based handler throws an exception, detect real type via magic bytes and retry

---

## Testing Checklist

- [ ] .doc file extracts text via LibreOffice conversion
- [ ] .pptx file extracts slide text with slide number headings
- [ ] .pptx speaker notes are included in extraction
- [ ] .pptx tables are extracted as markdown tables
- [ ] .xls file extracts cell data as markdown tables
- [ ] .rtf file extracts plain text content
- [ ] .odt file extracts text with heading preservation
- [ ] All 5 types update extraction_status correctly
- [ ] Hash tracking works (text_hash computed for all new types)
- [ ] Corrupted/password-protected files fail gracefully
- [ ] Cleanup only targets fully-analyzed files (all 4 pipeline stages complete, including AI)
- [ ] Cleanup with --dry-run shows files and size without deleting
- [ ] After cleanup, file_path is NULL but extracted_text and intel records remain
- [ ] Empty notice_id directories are removed after cleanup
- [ ] MuPDF warnings suppressed (no stderr noise from malformed PDFs)
- [ ] Magic bytes detect PDF saved with wrong extension
- [ ] Magic bytes detect DOCX/PPTX/XLSX/ODT via ZIP directory inspection
- [ ] Magic bytes detect OLE2 (.doc/.xls) format
- [ ] Magic bytes detect RTF format
- [ ] Handler retry works when extension-based handler fails but magic bytes succeed
- [ ] IRM/DRM-protected files detected early via OLE2 stream inspection
- [ ] .doc files with .docx extension handled (copy to .doc, convert via LibreOffice)
- [ ] PDFs ≤30 pages extract tables; >30 pages skip find_tables()
- [ ] Large PDFs (>4 pages) processed with parallel page workers
- [ ] Per-file 120s timeout prevents batch from hanging

---

## Task Summary

| # | Task | Complexity | Depends On |
|---|------|-----------|------------|
| 1 | Legacy Word .doc extraction | Low-Medium | LibreOffice headless |
| 2 | PowerPoint .pptx extraction | Medium | python-pptx |
| 3 | Legacy Excel .xls extraction | Low | xlrd |
| 4 | RTF extraction | Low | striprtf |
| 5 | OpenDocument .odt extraction | Low-Medium | odfpy |
| 6 | Post-analysis file cleanup | Low | download + extraction + intel complete |
| 7 | MuPDF warning suppression | Low | pymupdf |
| 8 | PDF table detection performance | Medium | pymupdf find_tables() |
| 9 | IRM/DRM protection detection | Low | olefile |
| 10 | .doc extraction via LibreOffice | Medium | LibreOffice 25.8+ |
| 11 | Magic byte file type detection | Medium | Built-in (zipfile) |
