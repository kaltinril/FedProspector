"""Structure-aware text extraction from opportunity attachments (Phase 110).

Downloads are already on disk (Phase 110 download step). This module extracts
text content from PDF, Word, Excel, and plain-text attachments, converting to
annotated Markdown with heading hierarchy, bold markers, and table formatting.

Usage:
    from etl.attachment_text_extractor import AttachmentTextExtractor
    extractor = AttachmentTextExtractor()
    stats = extractor.extract_text(batch_size=50)
"""

import hashlib
import logging
import os
from datetime import datetime
from pathlib import Path

from db.connection import get_connection
from etl.load_manager import LoadManager

_DEFAULT_ATTACHMENT_DIR = Path(__file__).resolve().parent.parent / "data" / "attachments"

logger = logging.getLogger("fed_prospector.etl.attachment_text_extractor")

# Content type / extension mappings
PDF_TYPES = {"application/pdf"}
WORD_TYPES = {
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
}
EXCEL_TYPES = {
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
}
TEXT_TYPES = {"text/plain", "text/csv", "text/html"}

PDF_EXTENSIONS = {".pdf"}
WORD_EXTENSIONS = {".docx", ".doc"}
EXCEL_EXTENSIONS = {".xlsx", ".xls"}
TEXT_EXTENSIONS = {".txt", ".csv", ".html", ".htm"}

# PyMuPDF font flag bitmask for bold
BOLD_FLAG = 16

# Minimum text chars per page before considering it scanned/image-only
SCANNED_THRESHOLD = 50


class AttachmentTextExtractor:
    """Extracts text from downloaded opportunity attachments.

    Produces annotated Markdown with heading hierarchy, bold markers,
    and table formatting. Stores results back in the opportunity_attachment
    table.
    """

    def __init__(self, db_connection=None, load_manager=None, attachment_dir=None):
        self.db_connection = db_connection
        self.load_manager = load_manager or LoadManager()
        self.attachment_dir = Path(attachment_dir) if attachment_dir else _DEFAULT_ATTACHMENT_DIR

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_text(self, notice_id=None, batch_size=100, force=False):
        """Extract text from pending downloaded attachments.

        Args:
            notice_id: If set, only process attachments for this notice.
            batch_size: Max attachments to process per run.
            force: If True, re-extract even if already extracted.

        Returns:
            dict with keys: processed, extracted, failed, unsupported, skipped
        """
        load_id = self.load_manager.start_load(
            source_system="ATTACHMENT_TEXT",
            load_type="INCREMENTAL",
            parameters={"notice_id": notice_id, "batch_size": batch_size, "force": force},
        )

        stats = {
            "processed": 0,
            "extracted": 0,
            "failed": 0,
            "unsupported": 0,
            "skipped": 0,
        }

        try:
            rows = self._fetch_pending(notice_id, batch_size, force)
            logger.info("Found %d attachments to extract", len(rows))

            for row in rows:
                stats["processed"] += 1
                try:
                    self._extract_one(row, load_id)
                    stats["extracted"] += 1
                except _UnsupportedType:
                    stats["unsupported"] += 1
                except _SkippedAttachment:
                    stats["skipped"] += 1
                except Exception as e:
                    stats["failed"] += 1
                    self._mark_failed(row["attachment_id"], load_id, str(e))
                    self.load_manager.log_record_error(
                        load_id,
                        record_identifier=str(row["attachment_id"]),
                        error_type="EXTRACTION_ERROR",
                        error_message=str(e),
                    )
                    logger.error(
                        "Extraction failed for attachment %s (%s): %s",
                        row["attachment_id"],
                        row.get("filename"),
                        e,
                    )

            self.load_manager.complete_load(
                load_id,
                records_read=stats["processed"],
                records_inserted=stats["extracted"],
                records_updated=0,
                records_unchanged=stats["skipped"],
                records_errored=stats["failed"] + stats["unsupported"],
            )
            logger.info(
                "Extraction complete: %d extracted, %d failed, %d unsupported, %d skipped",
                stats["extracted"],
                stats["failed"],
                stats["unsupported"],
                stats["skipped"],
            )
        except Exception as e:
            self.load_manager.fail_load(load_id, str(e))
            logger.error("Extraction batch failed: %s", e)
            raise

        return stats

    # ------------------------------------------------------------------
    # Internal: query and dispatch
    # ------------------------------------------------------------------

    def _fetch_pending(self, notice_id, batch_size, force):
        """Fetch attachments eligible for extraction."""
        conn = self.db_connection or get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conditions = ["download_status = 'downloaded'"]
            params = []

            if force:
                conditions.append("extraction_status IN ('pending', 'extracted', 'failed', 'unsupported')")
            else:
                conditions.append("extraction_status = 'pending'")

            if notice_id:
                conditions.append("notice_id = %s")
                params.append(notice_id)

            sql = (
                "SELECT attachment_id, notice_id, filename, content_type, file_path "
                "FROM opportunity_attachment "
                f"WHERE {' AND '.join(conditions)} "
                "ORDER BY attachment_id "
                "LIMIT %s"
            )
            params.append(batch_size)
            cursor.execute(sql, params)
            return cursor.fetchall()
        finally:
            cursor.close()
            if not self.db_connection:
                conn.close()

    def _extract_one(self, row, load_id):
        """Extract text from a single attachment and update the DB."""
        attachment_id = row["attachment_id"]
        file_path = row.get("file_path")
        filename = row.get("filename") or ""
        content_type = (row.get("content_type") or "").lower()

        # file_path is relative to attachment_dir (e.g. "notice_id/filename.pdf")
        if not file_path:
            raise FileNotFoundError(f"File not found: {file_path}")
        full_path = self.attachment_dir / file_path
        if not full_path.is_file():
            raise FileNotFoundError(f"File not found: {full_path}")
        file_path = str(full_path)

        ext = os.path.splitext(filename)[1].lower() if filename else ""
        handler = self._resolve_handler(content_type, ext)

        if handler is None:
            self._mark_unsupported(attachment_id, load_id)
            raise _UnsupportedType(f"Unsupported: content_type={content_type}, ext={ext}")

        text, page_count, is_scanned = handler(file_path)

        if not text or not text.strip():
            # Empty extraction — mark as scanned/image-only
            text = "[No extractable text content]"
            is_scanned = True

        text_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

        self._save_extraction(
            attachment_id=attachment_id,
            text=text,
            text_hash=text_hash,
            page_count=page_count,
            is_scanned=is_scanned,
            load_id=load_id,
        )

    def _resolve_handler(self, content_type, ext):
        """Return the appropriate extraction function, or None if unsupported."""
        if content_type in PDF_TYPES or ext in PDF_EXTENSIONS:
            return self._extract_pdf
        if content_type in WORD_TYPES or ext in WORD_EXTENSIONS:
            if ext == ".doc":
                # Legacy .doc format not supported by python-docx
                return None
            return self._extract_docx
        if content_type in EXCEL_TYPES or ext in EXCEL_EXTENSIONS:
            if ext == ".xls":
                # Legacy .xls format not supported by openpyxl
                return None
            return self._extract_xlsx
        if content_type in TEXT_TYPES or ext in TEXT_EXTENSIONS:
            return self._extract_plain_text
        return None

    # ------------------------------------------------------------------
    # PDF extraction (PyMuPDF / fitz)
    # ------------------------------------------------------------------

    def _extract_pdf(self, file_path):
        """Extract text from PDF with structure-aware Markdown formatting.

        Returns:
            (markdown_text, page_count, is_scanned)
        """
        import pymupdf as fitz  # PyMuPDF 1.27+

        try:
            doc = fitz.open(file_path)
        except Exception as e:
            if "encrypted" in str(e).lower() or "password" in str(e).lower():
                raise RuntimeError(f"Password-protected PDF: {e}") from e
            raise

        pages = []
        is_scanned = False

        try:
            for page_num, page in enumerate(doc, 1):
                # Extract tables first (if PyMuPDF supports find_tables)
                table_rects = []
                table_md = ""
                if hasattr(page, "find_tables"):
                    try:
                        tables = page.find_tables()
                        for table in tables:
                            table_rects.append(table.bbox)
                            table_md += self._pdf_table_to_markdown(table) + "\n\n"
                    except Exception:
                        pass  # Table extraction is best-effort

                # Get text blocks with formatting info
                try:
                    blocks = page.get_text("dict", sort=True)["blocks"]
                except Exception:
                    blocks = []

                page_text = self._process_pdf_blocks(blocks, table_rects)

                # Append tables after text blocks
                if table_md:
                    page_text = page_text.rstrip() + "\n\n" + table_md

                # Detect scanned page
                if len(page_text.strip()) < SCANNED_THRESHOLD:
                    is_scanned = True
                    page_text = f"[Page {page_num}: scanned/image-only — OCR not available]\n"

                pages.append(page_text)
        finally:
            doc.close()

        return "\n\n---\n\n".join(pages), len(pages), is_scanned

    def _process_pdf_blocks(self, blocks, table_rects=None):
        """Convert PDF dict blocks to Markdown text.

        Uses font size to detect headings and font flags for bold.
        Skips blocks that overlap with already-extracted table regions.
        """
        table_rects = table_rects or []
        lines_out = []

        for block in blocks:
            # Skip image blocks
            if block.get("type") != 0:
                continue

            # Skip blocks inside table regions
            bx0, by0, bx1, by1 = block["bbox"]
            if self._rect_overlaps_any(bx0, by0, bx1, by1, table_rects):
                continue

            for line in block.get("lines", []):
                spans = line.get("spans", [])
                if not spans:
                    continue

                # Determine dominant font properties from first span
                first_span = spans[0]
                font_size = first_span.get("size", 11)
                is_bold = bool(first_span.get("flags", 0) & BOLD_FLAG)

                # Build line text from all spans
                line_text = ""
                for span in spans:
                    text = span.get("text", "")
                    if not text.strip():
                        line_text += text
                        continue
                    span_bold = bool(span.get("flags", 0) & BOLD_FLAG)
                    if span_bold and not (font_size >= 14 or (font_size >= 12 and is_bold)):
                        # Inline bold (not already a heading)
                        line_text += f"**{text.strip()}** " if text.strip() else text
                    else:
                        line_text += text

                line_text = line_text.rstrip()
                if not line_text.strip():
                    continue

                # Heading detection based on font size
                if font_size >= 14:
                    lines_out.append(f"\n## {line_text.strip()}\n")
                elif font_size >= 12 and is_bold:
                    lines_out.append(f"\n### {line_text.strip()}\n")
                else:
                    lines_out.append(line_text)

        return "\n".join(lines_out)

    def _pdf_table_to_markdown(self, table):
        """Convert a PyMuPDF table object to Markdown table format."""
        try:
            data = table.extract()
        except Exception:
            return ""

        if not data or not data[0]:
            return ""

        # First row as header
        header = data[0]
        col_count = len(header)
        lines = []
        lines.append("| " + " | ".join(self._cell_str(c) for c in header) + " |")
        lines.append("| " + " | ".join("---" for _ in range(col_count)) + " |")

        for row in data[1:]:
            # Pad or trim to match header column count
            cells = list(row) + [""] * max(0, col_count - len(row))
            lines.append("| " + " | ".join(self._cell_str(c) for c in cells[:col_count]) + " |")

        return "\n".join(lines)

    @staticmethod
    def _rect_overlaps_any(x0, y0, x1, y1, rects):
        """Check if a bounding box overlaps with any rect in the list."""
        for rx0, ry0, rx1, ry1 in rects:
            if x0 < rx1 and x1 > rx0 and y0 < ry1 and y1 > ry0:
                return True
        return False

    # ------------------------------------------------------------------
    # Word extraction (python-docx)
    # ------------------------------------------------------------------

    def _extract_docx(self, file_path):
        """Extract text from .docx with heading and bold detection.

        Returns:
            (markdown_text, page_count=0, is_scanned=False)
        """
        from docx import Document
        from docx.oxml.ns import qn

        doc = Document(file_path)
        parts = []

        # Iterate body children to maintain paragraph/table ordering
        for element in doc.element.body:
            tag = element.tag.split("}")[-1] if "}" in element.tag else element.tag

            if tag == "p":
                para = self._find_paragraph_by_element(doc, element)
                if para is not None:
                    md = self._docx_paragraph_to_md(para)
                    if md:
                        parts.append(md)

            elif tag == "tbl":
                table = self._find_table_by_element(doc, element)
                if table is not None:
                    md = self._docx_table_to_md(table)
                    if md:
                        parts.append(md)

        text = "\n".join(parts)
        # python-docx has no page count concept
        return text, 0, False

    def _find_paragraph_by_element(self, doc, element):
        """Find the Paragraph object matching a body element."""
        for para in doc.paragraphs:
            if para._element is element:
                return para
        return None

    def _find_table_by_element(self, doc, element):
        """Find the Table object matching a body element."""
        for table in doc.tables:
            if table._element is element:
                return table
        return None

    def _docx_paragraph_to_md(self, para):
        """Convert a python-docx Paragraph to Markdown."""
        style_name = (para.style.name or "").lower()

        # Build text with bold markers
        text_parts = []
        for run in para.runs:
            t = run.text
            if not t:
                continue
            if run.bold:
                text_parts.append(f"**{t.strip()}**" if t.strip() else t)
            else:
                text_parts.append(t)

        text = "".join(text_parts).strip()
        if not text:
            return ""

        # Heading detection from style
        if "heading 1" in style_name:
            return f"\n# {text}\n"
        if "heading 2" in style_name:
            return f"\n## {text}\n"
        if "heading 3" in style_name or "heading 4" in style_name:
            return f"\n### {text}\n"
        if "title" in style_name:
            return f"\n# {text}\n"

        return text

    def _docx_table_to_md(self, table):
        """Convert a python-docx Table to Markdown."""
        rows = table.rows
        if not rows:
            return ""

        md_rows = []
        col_count = len(rows[0].cells)

        for i, row in enumerate(rows):
            cells = [self._cell_str(cell.text) for cell in row.cells[:col_count]]
            md_rows.append("| " + " | ".join(cells) + " |")
            if i == 0:
                md_rows.append("| " + " | ".join("---" for _ in range(col_count)) + " |")

        return "\n".join(md_rows)

    # ------------------------------------------------------------------
    # Excel extraction (openpyxl)
    # ------------------------------------------------------------------

    def _extract_xlsx(self, file_path):
        """Extract text from .xlsx with sheet and table structure.

        Returns:
            (markdown_text, page_count=0, is_scanned=False)
        """
        from openpyxl import load_workbook

        wb = load_workbook(file_path, read_only=True, data_only=True)
        parts = []

        for sheet_name in wb.sheetnames:
            ws = wb[sheet_name]
            rows = list(ws.iter_rows(values_only=True))

            # Skip empty sheets
            if not rows or all(all(c is None for c in row) for row in rows):
                continue

            parts.append(f"\n## {sheet_name}\n")

            # Filter out completely empty rows
            data_rows = [row for row in rows if any(c is not None for c in row)]
            if not data_rows:
                continue

            # Determine column count from first row
            col_count = len(data_rows[0])

            # First row as header
            header = data_rows[0]
            parts.append("| " + " | ".join(self._cell_str(c) for c in header) + " |")
            parts.append("| " + " | ".join("---" for _ in range(col_count)) + " |")

            for row in data_rows[1:]:
                cells = list(row) + [None] * max(0, col_count - len(row))
                parts.append("| " + " | ".join(self._cell_str(c) for c in cells[:col_count]) + " |")

        wb.close()
        return "\n".join(parts), 0, False

    # ------------------------------------------------------------------
    # Plain text extraction
    # ------------------------------------------------------------------

    def _extract_plain_text(self, file_path):
        """Read plain text files directly.

        Returns:
            (text, page_count=0, is_scanned=False)
        """
        encodings = ["utf-8", "latin-1", "cp1252"]
        for enc in encodings:
            try:
                with open(file_path, "r", encoding=enc) as f:
                    text = f.read()
                return text, 0, False
            except (UnicodeDecodeError, UnicodeError):
                continue

        # Last resort: read as bytes and decode lossy
        with open(file_path, "rb") as f:
            raw = f.read()
        return raw.decode("utf-8", errors="replace"), 0, False

    # ------------------------------------------------------------------
    # DB persistence
    # ------------------------------------------------------------------

    def _save_extraction(self, attachment_id, text, text_hash, page_count, is_scanned, load_id):
        """Write extraction results to opportunity_attachment."""
        conn = self.db_connection or get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE opportunity_attachment SET "
                "extracted_text = %s, text_hash = %s, page_count = %s, "
                "is_scanned = %s, extraction_status = 'extracted', "
                "extracted_at = %s, last_load_id = %s "
                "WHERE attachment_id = %s",
                (
                    text,
                    text_hash,
                    page_count if page_count else None,
                    1 if is_scanned else 0,
                    datetime.now(),
                    load_id,
                    attachment_id,
                ),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            if not self.db_connection:
                conn.close()

    def _mark_failed(self, attachment_id, load_id, error_msg):
        """Mark attachment extraction as failed."""
        conn = self.db_connection or get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE opportunity_attachment SET "
                "extraction_status = 'failed', extracted_at = %s, last_load_id = %s "
                "WHERE attachment_id = %s",
                (datetime.now(), load_id, attachment_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            if not self.db_connection:
                conn.close()

    def _mark_unsupported(self, attachment_id, load_id):
        """Mark attachment content type as unsupported."""
        conn = self.db_connection or get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "UPDATE opportunity_attachment SET "
                "extraction_status = 'unsupported', extracted_at = %s, last_load_id = %s "
                "WHERE attachment_id = %s",
                (datetime.now(), load_id, attachment_id),
            )
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            if not self.db_connection:
                conn.close()

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _cell_str(value):
        """Convert a cell value to a clean string for Markdown tables."""
        if value is None:
            return ""
        s = str(value).replace("|", "\\|").replace("\n", " ").strip()
        return s


# ------------------------------------------------------------------
# Internal exception types (not exported)
# ------------------------------------------------------------------

class _UnsupportedType(Exception):
    """Raised when the attachment content type is not supported."""


class _SkippedAttachment(Exception):
    """Raised when an attachment is skipped (e.g., already extracted)."""
