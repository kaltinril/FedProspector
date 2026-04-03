"""Federal identifier extraction from attachment text (Phase 128).

Scans attachment_document extracted_text for federal identifiers
(PIIDs, UEIs, CAGE codes, FAR/DFARS clauses, etc.) and stores them
in document_identifier_ref. Cross-references matched identifiers
against known records in fpds_contract, entity, and opportunity tables.

Usage:
    from etl.attachment_identifier_extractor import AttachmentIdentifierExtractor
    extractor = AttachmentIdentifierExtractor()
    stats = extractor.extract_identifiers(batch_size=100)
"""

import logging
import re

from db.connection import get_connection
from etl.load_manager import LoadManager

logger = logging.getLogger("fed_prospector.etl.attachment_identifier_extractor")

# ======================================================================
# Identifier Pattern Definitions
# ======================================================================

# PIID pattern: Agency Activity Code (5-6 chars) + FY (2 digits) + Type (1 letter) + Serial (3-8 chars)
# Matches both dashless (70LGLY21CGLB00003) and dashed (70-LGLY-21-C-GLB00003) formats.
# We use two patterns: dashless (strict) and dashed (allows hyphens between groups).
_PIID_RE = re.compile(
    r"\b([A-HJ-NP-Z0-9]{4,6}\d{2}[A-Z][A-HJ-NP-Z0-9]{3,8})\b"
)
_PIID_DASHED_RE = re.compile(
    r"\b([A-HJ-NP-Z0-9]{2,6}(?:-[A-HJ-NP-Z0-9]{1,8}){2,5})\b"
)

# UEI: 12 alphanumeric, no I/O, first char non-zero
_UEI_RE = re.compile(
    r"\b([A-HJ-NP-Z1-9][A-HJ-NP-Z0-9]{11})\b"
)

# CAGE Code: 5 chars, pattern is digit-alphanum-alphanum-alphanum-digit
_CAGE_RE = re.compile(
    r"\b(\d[A-HJ-NP-Z0-9]{3}\d)\b"
)

# DUNS: 9 digits, must be near "DUNS" keyword
_DUNS_RE = re.compile(r"\b(\d{9})\b")
_DUNS_CONTEXT_RE = re.compile(r"\bDUNS\b", re.IGNORECASE)

# UEI context: require SAM/UEI keyword nearby to reduce false positives
_UEI_CONTEXT_RE = re.compile(
    r"\b(?:UEI|Unique\s+Entity|SAM\.gov|SAM\s+registration)\b",
    re.IGNORECASE,
)

# PIID dashed format context: require contracting keyword nearby
_PIID_CONTEXT_RE = re.compile(
    r"\b(?:contract|solicitation|PIID|award|delivery\s+order|task\s+order|purchase\s+order|requisition|RFP|RFQ|IFB)\b",
    re.IGNORECASE,
)

# FAR Clause: 52.2XX-YY
_FAR_RE = re.compile(r"\b(52\.2\d{2}-\d{1,3})\b")

# DFARS Clause: 252.2XX-7YYY
_DFARS_RE = re.compile(r"\b(252\.2\d{2}-7\d{3})\b")

# Wage Determination: 20YY-NNNN near wage/SCA/DBA keywords
_WAGE_DET_RE = re.compile(r"\b(20\d{2}-\d{4,6})\b")
_WAGE_CONTEXT_RE = re.compile(
    r"\b(?:wage\s+determination|SCA|DBA|Davis.?Bacon|Service\s+Contract\s+Act|WD\s+(?:No|Number|#))\b",
    re.IGNORECASE,
)

# GSA Schedule: GS-XXF-XXXXXZ  (matches dashed GS-02F-1234A and dashless GS02F1234A)
_GSA_SCHEDULE_RE = re.compile(r"\b(GS-?\d{2}F-?\d{4,5}[A-Z]?)\b")

# USASpending Award ID: CONT_AWD_... or CONT_IDV_...
_USASPENDING_RE = re.compile(r"\b(CONT_(?:AWD|IDV)_[A-Z0-9_\-]+)\b")


# Context window for keyword-anchored patterns (chars before/after match)
_CONTEXT_WINDOW = 200

# How many chars of surrounding context to store
_STORED_CONTEXT = 150

# Known false positive PIID-like strings (common header/footer text, etc.)
_PIID_FALSE_POSITIVES = frozenset({
    # Add known false positives here as discovered
})


# Minimum length for PIID to reduce false positives
_PIID_MIN_LENGTH = 12


def _normalize_identifier(value: str, id_type: str) -> str:
    """Normalize an identifier value for dashless storage and matching."""
    val = value.strip().upper()
    if id_type in ("PIID", "SOLICITATION", "GSA_SCHEDULE"):
        val = val.replace("-", "")
    return val


def _get_context(text: str, start: int, end: int, window: int = _STORED_CONTEXT) -> str:
    """Extract surrounding context from text around a match."""
    ctx_start = max(0, start - window)
    ctx_end = min(len(text), end + window)
    return text[ctx_start:ctx_end]


def _is_piid_like(value: str) -> bool:
    """Check if a string looks like a valid PIID/solicitation number."""
    if len(value) < _PIID_MIN_LENGTH:
        return False
    if value in _PIID_FALSE_POSITIVES:
        return False
    # Must contain at least 2 digits
    digit_count = sum(1 for c in value if c.isdigit())
    if digit_count < 2:
        return False
    # Must contain at least 2 letters
    letter_count = sum(1 for c in value if c.isalpha())
    if letter_count < 2:
        return False
    # Validate instrument type code at position 7 or 8
    # (5-char AAC + 2 FY = pos 7, or 6-char AAC + 2 FY = pos 8)
    valid_type_codes = frozenset("ABCDEFGHLMNPQRSTWK")
    has_valid_type = False
    for pos in (7, 8):
        if pos < len(value) and value[pos] in valid_type_codes:
            # Also check that positions before the type code end with 2 digits (FY)
            if pos >= 2 and value[pos - 2:pos].isdigit():
                has_valid_type = True
                break
    if not has_valid_type:
        return False
    return True


def _classify_piid_type(value: str) -> str:
    """Classify a PIID as either PIID or SOLICITATION based on the type character.

    Federal PIID format: {AAC}{FY}{type}{serial}
    AAC can be 5 or 6 characters, so the type char is at position 7 or 8 (0-indexed).
    Type chars R, Q, B indicate solicitation; C, D, F, G, H indicate contract.
    We check both candidate positions to avoid misclassification.
    """
    upper = value.upper()
    solicitation_chars = frozenset("RQB")
    contract_chars = frozenset("CDFGH")
    # Check position 7 (5-char AAC + 2 FY) and position 8 (6-char AAC + 2 FY)
    for pos in (7, 8):
        if len(upper) > pos and upper[pos] in solicitation_chars:
            # Confirm this is likely a type char: the other candidate position
            # should not be a contract-type char (which would contradict)
            other_pos = 8 if pos == 7 else 7
            if len(upper) > other_pos and upper[other_pos] in contract_chars:
                # Ambiguous — the other position looks like a contract type.
                # Trust the contract classification (more conservative).
                continue
            return "SOLICITATION"
    return "PIID"


class AttachmentIdentifierExtractor:
    """Extract federal identifiers from attachment text and cross-reference against DB records."""

    def __init__(self, db_connection=None, load_manager=None):
        self.db_connection = db_connection
        self.load_manager = load_manager or LoadManager()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_identifiers(self, notice_id=None, batch_size=100, force=False):
        """Extract federal identifiers from attachment text.

        Args:
            notice_id: If set, only process this opportunity.
            batch_size: Max documents to process per run.
            force: If True, re-extract even if already processed.

        Returns:
            dict with stats about extraction.
        """
        load_id = self.load_manager.start_load(
            source_system="IDENTIFIER_EXTRACTION",
            load_type="INCREMENTAL",
            parameters={
                "notice_id": notice_id,
                "batch_size": batch_size,
                "force": force,
            },
        )

        stats = {
            "documents_processed": 0,
            "identifiers_found": 0,
            "identifiers_inserted": 0,
            "documents_skipped": 0,
        }

        try:
            documents = self._fetch_eligible_documents(notice_id, batch_size, force)
            total = self._count_eligible_documents(notice_id, force)
            remaining = total - len(documents)
            logger.info(
                "Found %d documents to scan for identifiers (load_id=%d) -- %d total eligible, %d remaining",
                len(documents), load_id, total, remaining,
            )

            from tqdm import tqdm

            pbar = tqdm(
                documents,
                desc="Identifier extraction",
                unit="doc",
                bar_format="{desc}: {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}",
            )
            for doc_id, text in pbar:
                try:
                    found = self._extract_from_document(doc_id, text, load_id)
                    stats["documents_processed"] += 1
                    stats["identifiers_found"] += found["total_found"]
                    stats["identifiers_inserted"] += found["inserted"]
                except Exception as e:
                    stats["documents_processed"] += 1
                    self.load_manager.log_record_error(
                        load_id,
                        record_identifier=str(doc_id),
                        error_type="IDENTIFIER_EXTRACTION_ERROR",
                        error_message=str(e),
                    )
                    logger.error("Identifier extraction failed for doc %d: %s", doc_id, e)
                pbar.set_postfix_str(f"ids={stats['identifiers_inserted']}")
            pbar.close()

            self.load_manager.complete_load(
                load_id,
                records_read=stats["documents_processed"],
                records_inserted=stats["identifiers_inserted"],
                records_updated=0,
                records_unchanged=0,
                records_errored=0,
            )
            logger.info(
                "Identifier extraction complete: %d docs, %d identifiers found, %d inserted",
                stats["documents_processed"],
                stats["identifiers_found"],
                stats["identifiers_inserted"],
            )
        except Exception as e:
            self.load_manager.fail_load(load_id, str(e))
            logger.error("Identifier extraction batch failed: %s", e)
            raise

        return stats

    def cross_reference(self, notice_id=None, batch_size=5000):
        """Cross-reference extracted identifiers against known DB records.

        Updates matched_table, matched_column, matched_id on document_identifier_ref
        rows where the identifier matches a record in fpds_contract, entity, or opportunity.

        Args:
            notice_id: If set, only cross-reference identifiers for this opportunity.
            batch_size: Max identifiers to process per run.

        Returns:
            dict with stats about cross-referencing.
        """
        load_id = self.load_manager.start_load(
            source_system="IDENTIFIER_CROSSREF",
            load_type="INCREMENTAL",
            parameters={"notice_id": notice_id, "batch_size": batch_size},
        )

        stats = {
            "identifiers_checked": 0,
            "matches_found": 0,
        }

        try:
            conn = self.db_connection or get_connection()
            cursor = conn.cursor()

            # Fetch unmatched identifiers
            where_clause = ""
            params = []
            if notice_id:
                where_clause = """
                    AND dir.document_id IN (
                        SELECT ad.document_id FROM attachment_document ad
                        JOIN opportunity_attachment oa ON oa.attachment_id = ad.attachment_id
                        WHERE oa.notice_id = %s
                    )
                """
                params.append(notice_id)

            cursor.execute(f"""
                SELECT ref_id, identifier_type, identifier_value, raw_text
                FROM document_identifier_ref dir
                WHERE matched_table IS NULL
                {where_clause}
                LIMIT %s
            """, params + [batch_size])

            rows = cursor.fetchall()
            logger.info("Cross-referencing %d unmatched identifiers", len(rows))

            # Batch by type for efficient lookups
            # Each item is (ref_id, dashless_value, raw_text)
            by_type = {}
            for ref_id, id_type, id_value, raw_text in rows:
                by_type.setdefault(id_type, []).append((ref_id, id_value, raw_text))
                stats["identifiers_checked"] += 1

            # PIID/SOLICITATION -> fpds_contract.contract_id
            for id_type in ("PIID", "SOLICITATION"):
                if id_type not in by_type:
                    continue
                items = by_type[id_type]
                # Build search set: both dashless identifier_value and original raw_text
                search_values = set()
                for _, dashless_val, raw_val in items:
                    search_values.add(dashless_val)
                    if raw_val and raw_val.upper() != dashless_val:
                        search_values.add(raw_val.upper())
                search_values = list(search_values)
                if not search_values:
                    continue
                # Batch lookup
                placeholders = ",".join(["%s"] * len(search_values))
                cursor.execute(f"""
                    SELECT DISTINCT contract_id FROM fpds_contract
                    WHERE contract_id IN ({placeholders})
                """, search_values)
                matched_contracts = set(r[0] for r in cursor.fetchall())

                # Also check solicitation_number in fpds_contract
                cursor.execute(f"""
                    SELECT DISTINCT solicitation_number FROM fpds_contract
                    WHERE solicitation_number IN ({placeholders})
                    AND solicitation_number IS NOT NULL
                """, search_values)
                matched_sol = set(r[0] for r in cursor.fetchall())

                # Also check opportunity.solicitation_number
                cursor.execute(f"""
                    SELECT DISTINCT solicitation_number FROM opportunity
                    WHERE solicitation_number IN ({placeholders})
                    AND solicitation_number IS NOT NULL
                """, search_values)
                matched_opp_sol = set(r[0] for r in cursor.fetchall())

                for ref_id, dashless_val, raw_val in items:
                    # Check dashless first, then raw (original with dashes)
                    raw_upper = raw_val.upper() if raw_val else None
                    matched = None
                    matched_tbl = None
                    matched_col = None
                    if dashless_val in matched_contracts:
                        matched, matched_tbl, matched_col = dashless_val, 'fpds_contract', 'contract_id'
                    elif raw_upper and raw_upper in matched_contracts:
                        matched, matched_tbl, matched_col = raw_upper, 'fpds_contract', 'contract_id'
                    elif dashless_val in matched_sol:
                        matched, matched_tbl, matched_col = dashless_val, 'fpds_contract', 'solicitation_number'
                    elif raw_upper and raw_upper in matched_sol:
                        matched, matched_tbl, matched_col = raw_upper, 'fpds_contract', 'solicitation_number'
                    elif dashless_val in matched_opp_sol:
                        matched, matched_tbl, matched_col = dashless_val, 'opportunity', 'solicitation_number'
                    elif raw_upper and raw_upper in matched_opp_sol:
                        matched, matched_tbl, matched_col = raw_upper, 'opportunity', 'solicitation_number'

                    if matched:
                        cursor.execute("""
                            UPDATE document_identifier_ref
                            SET matched_table = %s, matched_column = %s, matched_id = %s
                            WHERE ref_id = %s
                        """, (matched_tbl, matched_col, matched, ref_id))
                        stats["matches_found"] += 1

            # UEI -> entity.uei_sam and fpds_contract.vendor_uei
            if "UEI" in by_type:
                items = by_type["UEI"]
                values = list(set(v for _, v, _ in items))
                if values:
                    placeholders = ",".join(["%s"] * len(values))
                    cursor.execute(f"""
                        SELECT DISTINCT uei_sam FROM entity
                        WHERE uei_sam IN ({placeholders})
                    """, values)
                    matched_uei = set(r[0] for r in cursor.fetchall())

                    cursor.execute(f"""
                        SELECT DISTINCT vendor_uei FROM fpds_contract
                        WHERE vendor_uei IN ({placeholders})
                    """, values)
                    matched_vendor_uei = set(r[0] for r in cursor.fetchall())

                    for ref_id, val, _ in items:
                        if val in matched_uei:
                            cursor.execute("""
                                UPDATE document_identifier_ref
                                SET matched_table = 'entity', matched_column = 'uei_sam', matched_id = %s
                                WHERE ref_id = %s
                            """, (val, ref_id))
                            stats["matches_found"] += 1
                        elif val in matched_vendor_uei:
                            cursor.execute("""
                                UPDATE document_identifier_ref
                                SET matched_table = 'fpds_contract', matched_column = 'vendor_uei', matched_id = %s
                                WHERE ref_id = %s
                            """, (val, ref_id))
                            stats["matches_found"] += 1

            # CAGE -> entity.cage_code
            if "CAGE" in by_type:
                items = by_type["CAGE"]
                values = list(set(v for _, v, _ in items))
                if values:
                    placeholders = ",".join(["%s"] * len(values))
                    cursor.execute(f"""
                        SELECT DISTINCT cage_code FROM entity
                        WHERE cage_code IN ({placeholders})
                    """, values)
                    matched_cage = set(r[0] for r in cursor.fetchall())

                    for ref_id, val, _ in items:
                        if val in matched_cage:
                            cursor.execute("""
                                UPDATE document_identifier_ref
                                SET matched_table = 'entity', matched_column = 'cage_code', matched_id = %s
                                WHERE ref_id = %s
                            """, (val, ref_id))
                            stats["matches_found"] += 1

            # GSA_SCHEDULE -> fpds_contract.idv_piid
            if "GSA_SCHEDULE" in by_type:
                items = by_type["GSA_SCHEDULE"]
                # Build search set: both dashless and original raw_text
                search_values = set()
                for _, dashless_val, raw_val in items:
                    search_values.add(dashless_val)
                    if raw_val and raw_val.upper() != dashless_val:
                        search_values.add(raw_val.upper())
                search_values = list(search_values)
                if search_values:
                    placeholders = ",".join(["%s"] * len(search_values))
                    cursor.execute(f"""
                        SELECT DISTINCT idv_piid FROM fpds_contract
                        WHERE idv_piid IN ({placeholders})
                    """, search_values)
                    matched_gsa = set(r[0] for r in cursor.fetchall())

                    for ref_id, dashless_val, raw_val in items:
                        raw_upper = raw_val.upper() if raw_val else None
                        matched = dashless_val if dashless_val in matched_gsa else (
                            raw_upper if raw_upper and raw_upper in matched_gsa else None
                        )
                        if matched:
                            cursor.execute("""
                                UPDATE document_identifier_ref
                                SET matched_table = 'fpds_contract', matched_column = 'idv_piid', matched_id = %s
                                WHERE ref_id = %s
                            """, (matched, ref_id))
                            stats["matches_found"] += 1

            conn.commit()
            cursor.close()
            if not self.db_connection:
                conn.close()

            self.load_manager.complete_load(
                load_id,
                records_read=stats["identifiers_checked"],
                records_inserted=stats["matches_found"],
                records_updated=0,
                records_unchanged=stats["identifiers_checked"] - stats["matches_found"],
                records_errored=0,
            )
            logger.info(
                "Cross-reference complete: %d checked, %d matches found",
                stats["identifiers_checked"],
                stats["matches_found"],
            )
        except Exception as e:
            self.load_manager.fail_load(load_id, str(e))
            logger.error("Cross-reference failed: %s", e)
            raise

        return stats

    def search_identifier(self, identifier_type=None, identifier_value=None, limit=50):
        """Search for documents/opportunities referencing a given identifier.

        Args:
            identifier_type: Filter by type (PIID, UEI, CAGE, etc.)
            identifier_value: Filter by value (exact or prefix match)
            limit: Max results to return.

        Returns:
            List of dicts with identifier info and opportunity context.
        """
        conn = self.db_connection or get_connection()
        cursor = conn.cursor(dictionary=True)

        where_parts = []
        params = []

        if identifier_type:
            where_parts.append("dir.identifier_type = %s")
            params.append(identifier_type.upper())
        if identifier_value:
            normalized = _normalize_identifier(identifier_value, identifier_type or "PIID")
            where_parts.append("dir.identifier_value LIKE %s")
            params.append(f"{normalized}%")

        where_clause = "WHERE " + " AND ".join(where_parts) if where_parts else ""

        cursor.execute(f"""
            SELECT
                dir.ref_id,
                dir.identifier_type,
                dir.identifier_value,
                dir.raw_text,
                dir.confidence,
                dir.matched_table,
                dir.matched_column,
                dir.matched_id,
                oa.notice_id,
                ad.filename,
                o.title AS opportunity_title
            FROM document_identifier_ref dir
            JOIN attachment_document ad ON ad.document_id = dir.document_id
            JOIN opportunity_attachment oa ON oa.attachment_id = ad.attachment_id
            LEFT JOIN opportunity o ON o.notice_id = oa.notice_id
            {where_clause}
            ORDER BY dir.identifier_type, dir.identifier_value
            LIMIT %s
        """, params + [limit])

        results = cursor.fetchall()
        cursor.close()
        if not self.db_connection:
            conn.close()

        return results

    # ------------------------------------------------------------------
    # Internal: fetch eligible documents
    # ------------------------------------------------------------------

    def _fetch_eligible_documents(self, notice_id, batch_size, force):
        """Return list of (document_id, extracted_text) for documents to scan."""
        conn = self.db_connection or get_connection()
        cursor = conn.cursor()

        where_parts = ["ad.extraction_status = 'extracted'", "ad.extracted_text IS NOT NULL"]
        params = []

        if notice_id:
            where_parts.append("""
                ad.attachment_id IN (
                    SELECT attachment_id FROM opportunity_attachment WHERE notice_id = %s
                )
            """)
            params.append(notice_id)

        if not force:
            where_parts.append("ad.identifier_scanned_at IS NULL")

        where_clause = " AND ".join(where_parts)

        cursor.execute(f"""
            SELECT ad.document_id, ad.extracted_text
            FROM attachment_document ad
            WHERE {where_clause}
            ORDER BY ad.document_id
            LIMIT %s
        """, params + [batch_size])

        results = cursor.fetchall()
        cursor.close()
        if not self.db_connection:
            conn.close()

        return results

    def _count_eligible_documents(self, notice_id, force):
        """Count total eligible documents (for progress reporting)."""
        conn = self.db_connection or get_connection()
        cursor = conn.cursor()

        where_parts = ["ad.extraction_status = 'extracted'", "ad.extracted_text IS NOT NULL"]
        params = []

        if notice_id:
            where_parts.append("""
                ad.attachment_id IN (
                    SELECT attachment_id FROM opportunity_attachment WHERE notice_id = %s
                )
            """)
            params.append(notice_id)

        if not force:
            where_parts.append("ad.identifier_scanned_at IS NULL")

        where_clause = " AND ".join(where_parts)

        cursor.execute(f"""
            SELECT COUNT(*) FROM attachment_document ad
            WHERE {where_clause}
        """, params)

        count = cursor.fetchone()[0]
        cursor.close()
        if not self.db_connection:
            conn.close()

        return count

    # ------------------------------------------------------------------
    # Internal: extract identifiers from a single document
    # ------------------------------------------------------------------

    def _extract_from_document(self, document_id: int, text: str, load_id: int) -> dict:
        """Scan one document's text for all identifier patterns."""
        if not text:
            return {"total_found": 0, "inserted": 0}

        # Collect all matches: (identifier_type, identifier_value, raw_text, context, start, end, confidence)
        matches = []

        # --- PIID / Solicitation ---
        # Track normalized values already found so dashed variant doesn't duplicate
        seen_piid_normalized = set()
        for m in _PIID_RE.finditer(text):
            raw = m.group(1)
            if not _is_piid_like(raw):
                continue
            normalized = _normalize_identifier(raw, "PIID")
            id_type = _classify_piid_type(normalized)
            context = _get_context(text, m.start(), m.end())
            matches.append((id_type, normalized, raw, context, m.start(), m.end(), "medium"))
            seen_piid_normalized.add(normalized)

        # Also scan for dashed PIIDs (e.g. 70-LGLY-21-C-GLB00003)
        for m in _PIID_DASHED_RE.finditer(text):
            raw = m.group(1)
            # Must contain at least one dash to be a dashed variant
            if "-" not in raw:
                continue
            normalized = _normalize_identifier(raw, "PIID")
            if not _is_piid_like(normalized):
                continue
            if normalized in seen_piid_normalized:
                continue
            # Dashed format requires nearby contracting keyword to reduce part-number noise
            ctx_start = max(0, m.start() - _CONTEXT_WINDOW)
            ctx_end = min(len(text), m.end() + _CONTEXT_WINDOW)
            nearby = text[ctx_start:ctx_end]
            if not _PIID_CONTEXT_RE.search(nearby):
                continue
            id_type = _classify_piid_type(normalized)
            context = _get_context(text, m.start(), m.end())
            matches.append((id_type, normalized, raw, context, m.start(), m.end(), "medium"))
            seen_piid_normalized.add(normalized)

        # Cap PIID matches per document to avoid parts catalogs flooding the table
        piid_matches = [m for m in matches if m[0] in ("PIID", "SOLICITATION")]
        if len(piid_matches) > 100:
            logger.warning(
                "Document %d has %d PIID-like matches (likely parts catalog) — capping at 0",
                document_id, len(piid_matches),
            )
            matches = [m for m in matches if m[0] not in ("PIID", "SOLICITATION")]

        # --- UEI ---
        for m in _UEI_RE.finditer(text):
            raw = m.group(1)
            normalized = raw.upper()
            # UEI must not look like a PIID (already captured above)
            if _is_piid_like(raw):
                continue
            # Real UEIs always contain both letters and digits
            has_digit = any(c.isdigit() for c in normalized)
            has_alpha = any(c.isalpha() for c in normalized)
            if not has_digit or not has_alpha:
                continue
            # Require UEI-related keyword nearby
            ctx_start = max(0, m.start() - _CONTEXT_WINDOW)
            ctx_end = min(len(text), m.end() + _CONTEXT_WINDOW)
            nearby = text[ctx_start:ctx_end]
            if not _UEI_CONTEXT_RE.search(nearby):
                continue
            context = _get_context(text, m.start(), m.end())
            matches.append(("UEI", normalized, raw, context, m.start(), m.end(), "medium"))

        # --- CAGE Code ---
        for m in _CAGE_RE.finditer(text):
            raw = m.group(1)
            # Must be near "CAGE" keyword to reduce false positives
            ctx_start = max(0, m.start() - _CONTEXT_WINDOW)
            ctx_end = min(len(text), m.end() + _CONTEXT_WINDOW)
            nearby = text[ctx_start:ctx_end]
            if not re.search(r"\bCAGE\b", nearby, re.IGNORECASE):
                continue
            context = _get_context(text, m.start(), m.end())
            matches.append(("CAGE", raw.upper(), raw, context, m.start(), m.end(), "high"))

        # --- DUNS (context-dependent) ---
        for m in _DUNS_RE.finditer(text):
            raw = m.group(1)
            ctx_start = max(0, m.start() - _CONTEXT_WINDOW)
            ctx_end = min(len(text), m.end() + _CONTEXT_WINDOW)
            nearby = text[ctx_start:ctx_end]
            if not _DUNS_CONTEXT_RE.search(nearby):
                continue
            context = _get_context(text, m.start(), m.end())
            matches.append(("DUNS", raw, raw, context, m.start(), m.end(), "medium"))

        # --- FAR / DFARS Clause extraction removed ---
        # Every solicitation lists the same 50-100 boilerplate clause references
        # with zero discriminating value. Produces ~268K rows of noise.

        # --- Wage Determination (context-dependent) ---
        for m in _WAGE_DET_RE.finditer(text):
            raw = m.group(1)
            ctx_start = max(0, m.start() - _CONTEXT_WINDOW)
            ctx_end = min(len(text), m.end() + _CONTEXT_WINDOW)
            nearby = text[ctx_start:ctx_end]
            if not _WAGE_CONTEXT_RE.search(nearby):
                continue
            context = _get_context(text, m.start(), m.end())
            matches.append(("WAGE_DET", raw, raw, context, m.start(), m.end(), "medium"))

        # --- GSA Schedule ---
        for m in _GSA_SCHEDULE_RE.finditer(text):
            raw = m.group(1)
            normalized = _normalize_identifier(raw, "GSA_SCHEDULE")
            context = _get_context(text, m.start(), m.end())
            matches.append(("GSA_SCHEDULE", normalized, raw, context, m.start(), m.end(), "high"))

        # --- USASpending Award ID ---
        for m in _USASPENDING_RE.finditer(text):
            raw = m.group(1)
            context = _get_context(text, m.start(), m.end())
            matches.append(("USASPENDING_ID", raw, raw, context, m.start(), m.end(), "high"))

        # Deduplicate: keep first occurrence of each (type, value) pair
        seen = set()
        unique_matches = []
        for match in matches:
            key = (match[0], match[1])  # (identifier_type, identifier_value)
            if key not in seen:
                seen.add(key)
                unique_matches.append(match)

        # Insert into database
        conn = self.db_connection or get_connection()
        cursor = conn.cursor()

        # Delete existing rows for this document if force re-extraction
        cursor.execute(
            "DELETE FROM document_identifier_ref WHERE document_id = %s",
            (document_id,),
        )

        if not unique_matches:
            cursor.execute(
                "UPDATE attachment_document SET identifier_scanned_at = NOW() WHERE document_id = %s",
                (document_id,),
            )
            conn.commit()
            cursor.close()
            if not self.db_connection:
                conn.close()
            return {"total_found": 0, "inserted": 0}

        insert_sql = """
            INSERT INTO document_identifier_ref
            (document_id, identifier_type, identifier_value, raw_text, context,
             char_offset_start, char_offset_end, confidence, last_load_id)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
        """
        for id_type, id_value, raw, context, start, end, confidence in unique_matches:
            cursor.execute(insert_sql, (
                document_id, id_type, id_value, raw[:500], context[:5000],
                start, end, confidence, load_id,
            ))

        cursor.execute(
            "UPDATE attachment_document SET identifier_scanned_at = NOW() WHERE document_id = %s",
            (document_id,),
        )
        conn.commit()
        cursor.close()
        if not self.db_connection:
            conn.close()

        return {"total_found": len(matches), "inserted": len(unique_matches)}
