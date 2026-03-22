"""Regex/keyword intelligence extraction from opportunity attachment text (Phase 110).

Scans extracted attachment text (annotated Markdown) and opportunity description_text
for security clearance, evaluation method, contract vehicle, and recompete signals.
Stores structured intel in opportunity_attachment_intel with full provenance tracking
in opportunity_intel_source.

Usage:
    from etl.attachment_intel_extractor import AttachmentIntelExtractor
    extractor = AttachmentIntelExtractor()
    stats = extractor.extract_intel(batch_size=100)
"""

import hashlib
import json
import logging
import re
from datetime import datetime

from db.connection import get_connection
from etl.load_manager import LoadManager

logger = logging.getLogger("fed_prospector.etl.attachment_intel_extractor")

# ======================================================================
# Regex Pattern Library
# ======================================================================

# Heading keywords per category — used for structure-aware confidence boosting
_HEADING_KEYWORDS = {
    "clearance_level": {"security", "clearance", "personnel security", "access"},
    "eval_method": {"evaluation", "criteria", "factor", "scoring", "selection"},
    "vehicle_type": {"vehicle", "contract type", "ordering", "schedule", "gwac"},
    "recompete": {"incumbent", "background", "current contract", "transition"},
}

# Raw pattern definitions — compiled at module load
_RAW_PATTERNS = {
    "clearance_level": [
        {"pattern": r"\bTS/SCI\b", "value": "TS/SCI", "confidence": "high", "name": "clearance_ts_sci"},
        {"pattern": r"\bTop\s+Secret\b", "value": "Top Secret", "confidence": "high", "name": "clearance_top_secret"},
        {"pattern": r"(?<!Secretary )\bSecret\b(?!ary|ariat| Service| of)", "value": "Secret", "confidence": "medium", "name": "clearance_secret"},
        {"pattern": r"\b(?:Public\s+Trust|Moderate\s+Risk|High\s+Risk)\b", "value": "Public Trust", "confidence": "medium", "name": "clearance_public_trust"},
        {"pattern": r"\b(?:SF-86|e-?QIP|SF-312|DCSA|SCIF)\b", "value": None, "confidence": "medium", "name": "clearance_indicator"},
        {"pattern": r"\b(?:FCL|facility\s+clearance)\b", "value": None, "confidence": "medium", "name": "clearance_facility", "scope": "facility"},
        {"pattern": r"\b(?:PCL|personnel\s+clearance)\b", "value": None, "confidence": "medium", "name": "clearance_personnel", "scope": "personnel"},
    ],
    "eval_method": [
        {"pattern": r"\b(?:lowest\s+price\s+technically\s+acceptable|LPTA)\b", "value": "LPTA", "confidence": "high", "name": "eval_lpta"},
        {"pattern": r"\b(?:best\s+value|trade-?off)\b", "value": "Best Value", "confidence": "high", "name": "eval_best_value"},
        {"pattern": r"\bFAR\s+15\.101-1\b", "value": "Best Value", "confidence": "high", "name": "eval_far_tradeoff"},
        {"pattern": r"\bFAR\s+15\.101-2\b", "value": "LPTA", "confidence": "high", "name": "eval_far_lpta"},
        {"pattern": r"\b(?:evaluation\s+(?:factor|criteria))\b", "value": None, "confidence": "low", "name": "eval_indicator"},
    ],
    "vehicle_type": [
        {"pattern": r"\bOASIS\+?\s*(?:SB|Small\s+Business)?\b", "value": "OASIS", "confidence": "high", "name": "vehicle_oasis"},
        {"pattern": r"\b(?:GSA\s+(?:Schedule|MAS)|Federal\s+Supply\s+Schedule|FSS)\b", "value": "GSA MAS", "confidence": "high", "name": "vehicle_gsa"},
        {"pattern": r"\b(?:BPA|Blanket\s+Purchase\s+Agreement)\b", "value": "BPA", "confidence": "high", "name": "vehicle_bpa"},
        {"pattern": r"\bIDIQ\b", "value": "IDIQ", "confidence": "high", "name": "vehicle_idiq"},
        {"pattern": r"\b(?:GWAC|SEWP|CIO-SP[34]|Alliant|VETS\s*2|8\(a\)\s*STARS)\b", "value": None, "confidence": "high", "name": "vehicle_gwac"},
        {"pattern": r"\bSIN\s+\d{6}", "value": "GSA MAS", "confidence": "medium", "name": "vehicle_sin"},
    ],
    "recompete": [
        {"pattern": r"\b(?:incumbent|current\s+contractor|currently\s+performed\s+by)\b", "value": "Y", "confidence": "high", "name": "recompete_incumbent"},
        {"pattern": r"\b(?:follow-?on|recompete|re-compete)\b", "value": "Y", "confidence": "high", "name": "recompete_followon"},
        {"pattern": r"\b(?:new\s+requirement|new\s+start)\b", "value": "N", "confidence": "medium", "name": "recompete_new"},
        {"pattern": r"\b(?:bridge\s+contract|bridge\s+extension|successor\s+contract)\b", "value": "Y", "confidence": "high", "name": "recompete_bridge"},
        {"pattern": r"\b(?:transition\s+plan|transition\s+period)\b", "value": "Y", "confidence": "medium", "name": "recompete_transition"},
    ],
}

# Compiled patterns: category -> list of {regex, value, confidence, name, ...}
PATTERNS = {}
for _cat, _defs in _RAW_PATTERNS.items():
    PATTERNS[_cat] = []
    for _d in _defs:
        entry = dict(_d)
        entry["regex"] = re.compile(_d["pattern"], re.IGNORECASE)
        PATTERNS[_cat].append(entry)

# Incumbent name extraction patterns (applied near recompete matches)
# These require explicit linking syntax (colon, "is", "performed by", etc.)
# to avoid false positives from generic recompete mentions.
_INCUMBENT_NAME_PATTERNS = [
    # "incumbent: Name" / "incumbent is Name" / "incumbent contractor: Name"
    re.compile(
        r"(?:incumbent(?:\s+contractor)?|current\s+contractor)"
        r"\s+(?:is|was)\s+"
        r"([A-Z][A-Za-z0-9&\-']+(?:\s+[A-Z][A-Za-z0-9&\-']+)*(?:,\s*(?:Inc|LLC|Corp|Ltd|LP|LLP|Co)\.?)?)",
    ),
    re.compile(
        r"(?:incumbent(?:\s+contractor)?|current\s+contractor)"
        r"\s*[:=\u2013\u2014]\s*"
        r"([A-Z][A-Za-z0-9&\-']+(?:\s+[A-Z][A-Za-z0-9&\-']+)*(?:,\s*(?:Inc|LLC|Corp|Ltd|LP|LLP|Co)\.?)?)",
    ),
    # "currently performed by Name"
    re.compile(
        r"currently\s+performed\s+by\s+"
        r"([A-Z][A-Za-z0-9&\-']+(?:\s+[A-Z][A-Za-z0-9&\-']+)*(?:,\s*(?:Inc|LLC|Corp|Ltd|LP|LLP|Co)\.?)?)",
    ),
    # "awarded to Name"
    re.compile(
        r"awarded\s+to\s+"
        r"([A-Z][A-Za-z0-9&\-']+(?:\s+[A-Z][A-Za-z0-9&\-']+)*(?:,\s*(?:Inc|LLC|Corp|Ltd|LP|LLP|Co)\.?)?)",
    ),
    # "contract held by Name"
    re.compile(
        r"contract\s+held\s+by\s+"
        r"([A-Z][A-Za-z0-9&\-']+(?:\s+[A-Z][A-Za-z0-9&\-']+)*(?:,\s*(?:Inc|LLC|Corp|Ltd|LP|LLP|Co)\.?)?)",
    ),
]

# Common words that should NOT be accepted as incumbent names (or name starts)
_INCUMBENT_FALSE_POSITIVES = frozenset({
    "the", "this", "that", "will", "shall", "must", "may", "can", "should",
    "a", "an", "all", "any", "each", "every", "no", "not", "are", "is",
    "was", "were", "has", "have", "had", "been", "being", "do", "does",
    "did", "if", "or", "and", "but", "for", "with", "from", "into",
    "upon", "about", "after", "before", "during", "between", "through",
    "under", "over", "above", "below", "detail", "details", "provide",
    "ensure", "submit", "include", "includes", "required", "responsible",
    "expected", "proposed", "able", "also", "only", "such", "other",
})

# Confidence ranking for comparisons
_CONF_RANK = {"high": 3, "medium": 2, "low": 1}

# ======================================================================
# Negation Detection
# ======================================================================
# Phrases in the ~80 chars BEFORE a match that negate its meaning.
# "does not require security clearance" → should NOT trigger clearance_required=Y
# "no security clearance is needed"     → same
# We check a window of text before the match for these patterns.

_NEGATION_PHRASES = re.compile(
    r"\b(?:"
    r"(?:does\s+not|do\s+not|will\s+not|shall\s+not|is\s+not|are\s+not|not)\s+(?:require|need|necessitate|involve|include|apply)|"
    r"no\s+(?:requirement\s+for|need\s+for)|"
    r"(?:without|waive[sd]?|exempt(?:ed|ion)?(?:\s+from)?|not\s+(?:required|needed|applicable|necessary))|"
    r"(?:does\s+not|will\s+not|shall\s+not)\s+apply|"
    r"n/?a\s+(?:for|regarding)|"
    r"(?:there\s+is\s+no|there\s+are\s+no)\b"
    r")\b",
    re.IGNORECASE,
)

# Additional negation phrases that come AFTER the match
# e.g., "security clearance is not required", "clearance: N/A"
_NEGATION_PHRASES_AFTER = re.compile(
    r"\b(?:"
    r"(?:is|are)\s+not\s+(?:required|needed|necessary|applicable)|"
    r"(?:not\s+(?:required|needed|necessary|applicable))|"
    r":\s*(?:N/?A|None|No)\b|"
    r"(?:is|are)\s+(?:waived|exempt(?:ed)?)"
    r")",
    re.IGNORECASE,
)


class AttachmentIntelExtractor:
    """Extract structured intelligence from opportunity attachment text using regex patterns."""

    def __init__(self, db_connection=None, load_manager=None):
        self.db_connection = db_connection
        self.load_manager = load_manager or LoadManager()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def extract_intel(self, notice_id=None, batch_size=100, method="keyword", force=False):
        """Extract intelligence from attachment text and opportunity descriptions.

        Args:
            notice_id: If set, only process this opportunity.
            batch_size: Max notices to process per run.
            method: Extraction method label (default 'keyword').
            force: If True, re-extract even if already processed.

        Returns:
            dict with keys: notices_processed, intel_rows_upserted,
                            source_rows_inserted, opportunities_updated
        """
        load_id = self.load_manager.start_load(
            source_system="ATTACHMENT_INTEL",
            load_type="INCREMENTAL",
            parameters={
                "notice_id": notice_id,
                "batch_size": batch_size,
                "method": method,
                "force": force,
            },
        )

        stats = {
            "notices_processed": 0,
            "intel_rows_upserted": 0,
            "source_rows_inserted": 0,
            "opportunities_updated": 0,
        }

        try:
            notice_ids = self._fetch_eligible_notices(notice_id, batch_size, method, force)
            logger.info("Found %d notices to extract intel from (load_id=%d)", len(notice_ids), load_id)

            from tqdm import tqdm

            pbar = tqdm(
                notice_ids,
                desc="Intel extraction",
                unit="notice",
                bar_format="{desc}: {n_fmt}/{total_fmt} [{elapsed}<{remaining}] {postfix}",
            )
            for nid in pbar:
                try:
                    result = self._process_notice(nid, method, load_id)
                    stats["notices_processed"] += 1
                    stats["intel_rows_upserted"] += result["intel_upserted"]
                    stats["source_rows_inserted"] += result["sources_inserted"]
                    if result["opportunity_updated"]:
                        stats["opportunities_updated"] += 1
                except Exception as e:
                    stats["notices_processed"] += 1
                    self.load_manager.log_record_error(
                        load_id,
                        record_identifier=nid,
                        error_type="INTEL_EXTRACTION_ERROR",
                        error_message=str(e),
                    )
                    logger.error("Intel extraction failed for %s: %s", nid, e)
                pbar.set_postfix_str(
                    f"intel={stats['intel_rows_upserted']} opps={stats['opportunities_updated']}"
                )
            pbar.close()

            self.load_manager.complete_load(
                load_id,
                records_read=stats["notices_processed"],
                records_inserted=stats["intel_rows_upserted"],
                records_updated=stats["opportunities_updated"],
                records_unchanged=0,
                records_errored=0,
            )
            logger.info(
                "Intel extraction complete: %d notices, %d intel rows, %d sources, %d opportunities updated",
                stats["notices_processed"],
                stats["intel_rows_upserted"],
                stats["source_rows_inserted"],
                stats["opportunities_updated"],
            )
        except Exception as e:
            self.load_manager.fail_load(load_id, str(e))
            logger.error("Intel extraction batch failed: %s", e)
            raise

        return stats

    # ------------------------------------------------------------------
    # Internal: query eligible notices
    # ------------------------------------------------------------------

    def _fetch_eligible_notices(self, notice_id, batch_size, method, force):
        """Return list of notice_ids that have extractable text.

        A notice is eligible if it has at least one attachment with
        extraction_status='extracted' OR has description_text.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            if notice_id:
                return [notice_id]

            # Find notices with extracted attachments or descriptions
            if force:
                sql = (
                    "SELECT DISTINCT n.notice_id FROM ("
                    "  SELECT notice_id FROM opportunity_attachment "
                    "  WHERE extraction_status = 'extracted' AND extracted_text IS NOT NULL "
                    "  UNION "
                    "  SELECT notice_id FROM opportunity "
                    "  WHERE description_text IS NOT NULL AND description_text != ''"
                    ") n "
                    "ORDER BY n.notice_id "
                    "LIMIT %s"
                )
            else:
                # Exclude notices that already have keyword intel
                sql = (
                    "SELECT DISTINCT n.notice_id FROM ("
                    "  SELECT notice_id FROM opportunity_attachment "
                    "  WHERE extraction_status = 'extracted' AND extracted_text IS NOT NULL "
                    "  UNION "
                    "  SELECT notice_id FROM opportunity "
                    "  WHERE description_text IS NOT NULL AND description_text != ''"
                    ") n "
                    "LEFT JOIN opportunity_attachment_intel i "
                    "  ON n.notice_id = i.notice_id AND i.extraction_method = %s "
                    "WHERE i.intel_id IS NULL "
                    "ORDER BY n.notice_id "
                    "LIMIT %s"
                )
            params = [batch_size] if force else [method, batch_size]
            cursor.execute(sql, params)
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

    # ------------------------------------------------------------------
    # Internal: process one notice
    # ------------------------------------------------------------------

    def _process_notice(self, notice_id, method, load_id):
        """Process all text sources for a single notice.

        Returns dict: {intel_upserted, sources_inserted, opportunity_updated}
        """
        result = {"intel_upserted": 0, "sources_inserted": 0, "opportunity_updated": False}

        # Gather text sources: (attachment_id, filename, text)
        sources = self._gather_text_sources(notice_id)
        if not sources:
            logger.debug("No text sources for %s", notice_id)
            return result

        # Run patterns across all sources, collecting matches
        all_matches = []  # list of (category, match_info_dict)
        for attachment_id, filename, text in sources:
            text_matches = self._run_patterns(text, attachment_id, filename)
            all_matches.extend(text_matches)

        # Consolidate into intel row
        intel = self._consolidate_matches(all_matches)
        text_hash = self._compute_combined_hash(sources)

        # Upsert per-source intel rows (one per attachment_id)
        attachment_ids_seen = set()
        for attachment_id, filename, text in sources:
            source_matches = [m for m in all_matches if m[1]["attachment_id"] == attachment_id]
            if not source_matches:
                continue
            attachment_ids_seen.add(attachment_id)
            source_intel = self._consolidate_matches(source_matches)
            source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

            intel_id = self._upsert_intel_row(
                notice_id, attachment_id, method, source_hash, source_intel, load_id,
            )
            result["intel_upserted"] += 1

            # Replace source provenance rows
            source_count = self._replace_source_rows(
                intel_id, source_matches, method,
            )
            result["sources_inserted"] += source_count

        # Also upsert a consolidated row with attachment_id=NULL if multiple sources
        if len(sources) > 1 or (len(sources) == 1 and sources[0][0] is not None):
            # Always create a NULL-attachment consolidated row for the notice
            consolidated_id = self._upsert_intel_row(
                notice_id, None, method, text_hash, intel, load_id,
            )
            result["intel_upserted"] += 1
            source_count = self._replace_source_rows(
                consolidated_id, all_matches, method,
            )
            result["sources_inserted"] += source_count

        # If only one source and it was description_text (attachment_id=None),
        # the per-source loop already created the NULL row
        if len(sources) == 1 and sources[0][0] is None and not attachment_ids_seen:
            consolidated_id = self._upsert_intel_row(
                notice_id, None, method, text_hash, intel, load_id,
            )
            result["intel_upserted"] += 1
            source_count = self._replace_source_rows(
                consolidated_id, all_matches, method,
            )
            result["sources_inserted"] += source_count

        # Update reserved opportunity columns with best intel
        updated = self._update_opportunity_columns(notice_id, intel)
        result["opportunity_updated"] = updated

        return result

    def _gather_text_sources(self, notice_id):
        """Gather all text sources for a notice.

        Returns list of (attachment_id_or_None, filename, text).
        """
        sources = []
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Extracted attachments
            cursor.execute(
                "SELECT attachment_id, filename, extracted_text "
                "FROM opportunity_attachment "
                "WHERE notice_id = %s AND extraction_status = 'extracted' "
                "AND extracted_text IS NOT NULL",
                (notice_id,),
            )
            for row in cursor.fetchall():
                sources.append((row["attachment_id"], row["filename"] or "unknown", row["extracted_text"]))

            # Opportunity description_text as virtual attachment
            cursor.execute(
                "SELECT description_text FROM opportunity WHERE notice_id = %s",
                (notice_id,),
            )
            opp = cursor.fetchone()
            if opp and opp.get("description_text") and opp["description_text"].strip():
                sources.append((None, "description_text", opp["description_text"]))
        finally:
            cursor.close()
            conn.close()

        return sources

    # ------------------------------------------------------------------
    # Pattern matching engine
    # ------------------------------------------------------------------

    def _run_patterns(self, text, attachment_id, filename):
        """Run all regex patterns against text.

        Returns list of (category, match_info) tuples.
        """
        matches = []
        for category, patterns in PATTERNS.items():
            for pdef in patterns:
                for m in pdef["regex"].finditer(text):
                    # --- Negation detection ---
                    # Check if surrounding context negates this match.
                    # e.g., "does not require security clearance" should NOT
                    # trigger a positive clearance finding.
                    if self._is_negated(text, m.start(), m.end()):
                        logger.debug(
                            "Negated match skipped: %s (%s) in %s at offset %d",
                            pdef["name"], m.group(), filename, m.start(),
                        )
                        continue

                    confidence = pdef["confidence"]

                    # Structure-aware confidence boosting
                    confidence = self._boost_confidence(text, m.start(), category, confidence)

                    context_start = max(0, m.start() - 150)
                    context_end = min(len(text), m.end() + 150)

                    match_info = {
                        "attachment_id": attachment_id,
                        "filename": filename,
                        "matched_text": m.group()[:500],
                        "surrounding_context": text[context_start:context_end],
                        "pattern_name": pdef["name"],
                        "value": pdef.get("value"),
                        "confidence": confidence,
                        "char_offset_start": m.start(),
                        "char_offset_end": m.end(),
                        "scope": pdef.get("scope"),
                    }
                    matches.append((category, match_info))

                    # Try incumbent name extraction for recompete matches
                    if category == "recompete" and pdef["name"] in ("recompete_incumbent",):
                        incumbent = self._extract_incumbent_name(text, m.start(), m.end())
                        if incumbent:
                            inc_info = {
                                "attachment_id": attachment_id,
                                "filename": filename,
                                "matched_text": incumbent[:500],
                                "surrounding_context": text[context_start:context_end],
                                "pattern_name": "incumbent_name_extracted",
                                "value": incumbent,
                                "confidence": confidence,
                                "char_offset_start": m.start(),
                                "char_offset_end": m.end(),
                                "scope": None,
                            }
                            matches.append(("incumbent_name", inc_info))

        return matches

    @staticmethod
    def _is_negated(text, match_start, match_end):
        """Check if a regex match is negated by surrounding context.

        Looks for negation phrases in the 80 chars before and 60 chars after
        the match. For example:
            "does not require security clearance"  → negated
            "no security clearance is needed"      → negated
            "security clearance is not required"   → negated
            "Active Secret Security Clearance"     → NOT negated

        Returns True if the match appears to be negated.
        """
        # Check text BEFORE the match (up to 80 chars)
        before_start = max(0, match_start - 80)
        before_text = text[before_start:match_start]
        if _NEGATION_PHRASES.search(before_text):
            return True

        # Check text AFTER the match (up to 60 chars)
        after_end = min(len(text), match_end + 60)
        after_text = text[match_end:after_end]
        if _NEGATION_PHRASES_AFTER.search(after_text):
            return True

        return False

    def _boost_confidence(self, text, match_pos, category, base_confidence):
        """Boost confidence based on structural context (headings, bold)."""
        confidence = base_confidence

        # Check if match is within bold markers
        # Look backwards up to 5 chars for **
        prefix = text[max(0, match_pos - 5):match_pos]
        if "**" in prefix:
            confidence = _upgrade_confidence(confidence)

        # Check nearest heading for relevant keywords
        heading_keywords = _HEADING_KEYWORDS.get(category, set())
        if heading_keywords:
            heading = self._find_nearest_heading(text, match_pos)
            if heading:
                heading_lower = heading.lower()
                if any(kw in heading_lower for kw in heading_keywords):
                    confidence = "high"

        return confidence

    @staticmethod
    def _find_nearest_heading(text, pos):
        """Find the nearest ## heading above the given position."""
        # Scan backwards for a line starting with ##
        search_start = max(0, pos - 2000)
        chunk = text[search_start:pos]
        # Find all headings in chunk
        heading_matches = list(re.finditer(r"^#{1,4}\s+(.+)$", chunk, re.MULTILINE))
        if heading_matches:
            return heading_matches[-1].group(1).strip()
        return None

    @staticmethod
    def _extract_incumbent_name(text, match_start, match_end):
        """Try to extract an incumbent company name from context around a recompete match.

        Only returns a name when an explicit linking pattern is found
        (e.g. "incumbent is Acme Corp", "current contractor: SAIC").
        Returns None rather than guessing when no clear pattern matches.
        """
        # Look at text from match through next 300 chars
        context = text[match_start:min(len(text), match_end + 300)]
        for pat in _INCUMBENT_NAME_PATTERNS:
            m = pat.search(context)
            if m:
                name = m.group(1).strip().rstrip(".,;:")
                # Validate: 2-100 chars, starts with capital, not a common word
                if len(name) < 2 or len(name) > 100:
                    continue
                if not name[0].isupper():
                    continue
                # Reject if the entire name is a single common false-positive word
                if name.lower() in _INCUMBENT_FALSE_POSITIVES:
                    continue
                # Reject if the first word is a common false-positive
                first_word = name.split()[0].lower() if name.split() else ""
                if first_word in _INCUMBENT_FALSE_POSITIVES:
                    continue
                return name
        return None

    # ------------------------------------------------------------------
    # Consolidation
    # ------------------------------------------------------------------

    def _consolidate_matches(self, matches):
        """Consolidate pattern matches into a single intel dict.

        Picks highest-confidence value for each field.
        """
        intel = {
            "clearance_required": None,
            "clearance_level": None,
            "clearance_scope": None,
            "clearance_details": [],
            "eval_method": None,
            "eval_details": [],
            "vehicle_type": None,
            "vehicle_details": [],
            "is_recompete": None,
            "incumbent_name": None,
            "recompete_details": [],
            "overall_confidence": "low",
            "confidence_details": {},
        }

        best = {}  # category -> (confidence_rank, value, scope)

        for category, info in matches:
            conf_rank = _CONF_RANK.get(info["confidence"], 0)
            value = info.get("value")
            scope = info.get("scope")

            # Track best per category
            prev = best.get(category, (0, None, None))
            if conf_rank > prev[0] or (conf_rank == prev[0] and value and not prev[1]):
                best[category] = (conf_rank, value, scope)

            # Collect details
            if category == "clearance_level":
                intel["clearance_details"].append(f"{info['pattern_name']}: {info['matched_text']}")
            elif category == "eval_method":
                intel["eval_details"].append(f"{info['pattern_name']}: {info['matched_text']}")
            elif category == "vehicle_type":
                intel["vehicle_details"].append(f"{info['pattern_name']}: {info['matched_text']}")
            elif category == "recompete":
                intel["recompete_details"].append(f"{info['pattern_name']}: {info['matched_text']}")
            elif category == "incumbent_name":
                if value and (not intel["incumbent_name"] or conf_rank > _CONF_RANK.get("medium", 0)):
                    intel["incumbent_name"] = value

        # Apply best values
        if "clearance_level" in best:
            rank, value, scope = best["clearance_level"]
            if value:
                intel["clearance_level"] = value
            intel["clearance_required"] = "Y"
            if scope:
                intel["clearance_scope"] = scope
            intel["confidence_details"]["clearance_level"] = _rank_to_conf(rank)

        if "eval_method" in best:
            rank, value, _ = best["eval_method"]
            if value:
                intel["eval_method"] = value
            intel["confidence_details"]["eval_method"] = _rank_to_conf(rank)

        if "vehicle_type" in best:
            rank, value, _ = best["vehicle_type"]
            if value:
                intel["vehicle_type"] = value
            intel["confidence_details"]["vehicle_type"] = _rank_to_conf(rank)

        if "recompete" in best:
            rank, value, _ = best["recompete"]
            if value:
                intel["is_recompete"] = value
            intel["confidence_details"]["recompete"] = _rank_to_conf(rank)

        # Overall confidence
        all_ranks = [r for r, _, _ in best.values()]
        if any(r >= 3 for r in all_ranks):
            intel["overall_confidence"] = "high"
        elif any(r >= 2 for r in all_ranks):
            intel["overall_confidence"] = "medium"
        else:
            intel["overall_confidence"] = "low"

        # Convert detail lists to text
        intel["clearance_details"] = "; ".join(intel["clearance_details"]) if intel["clearance_details"] else None
        intel["eval_details"] = "; ".join(intel["eval_details"]) if intel["eval_details"] else None
        intel["vehicle_details"] = "; ".join(intel["vehicle_details"]) if intel["vehicle_details"] else None
        intel["recompete_details"] = "; ".join(intel["recompete_details"]) if intel["recompete_details"] else None

        return intel

    @staticmethod
    def _compute_combined_hash(sources):
        """Compute SHA-256 over all text sources combined."""
        h = hashlib.sha256()
        for _, _, text in sources:
            h.update(text.encode("utf-8"))
        return h.hexdigest()

    # ------------------------------------------------------------------
    # DB persistence
    # ------------------------------------------------------------------

    def _upsert_intel_row(self, notice_id, attachment_id, method, text_hash, intel, load_id):
        """Upsert a row into opportunity_attachment_intel. Returns intel_id."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO opportunity_attachment_intel "
                "(notice_id, attachment_id, extraction_method, source_text_hash, "
                " clearance_required, clearance_level, clearance_scope, clearance_details, "
                " eval_method, eval_details, vehicle_type, vehicle_details, "
                " is_recompete, incumbent_name, recompete_details, "
                " overall_confidence, confidence_details, last_load_id, extracted_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
                "ON DUPLICATE KEY UPDATE "
                "source_text_hash = VALUES(source_text_hash), "
                "clearance_required = VALUES(clearance_required), "
                "clearance_level = VALUES(clearance_level), "
                "clearance_scope = VALUES(clearance_scope), "
                "clearance_details = VALUES(clearance_details), "
                "eval_method = VALUES(eval_method), "
                "eval_details = VALUES(eval_details), "
                "vehicle_type = VALUES(vehicle_type), "
                "vehicle_details = VALUES(vehicle_details), "
                "is_recompete = VALUES(is_recompete), "
                "incumbent_name = VALUES(incumbent_name), "
                "recompete_details = VALUES(recompete_details), "
                "overall_confidence = VALUES(overall_confidence), "
                "confidence_details = VALUES(confidence_details), "
                "last_load_id = VALUES(last_load_id), "
                "extracted_at = VALUES(extracted_at)",
                (
                    notice_id,
                    attachment_id,
                    method,
                    text_hash,
                    intel["clearance_required"],
                    intel["clearance_level"],
                    intel.get("clearance_scope"),
                    intel["clearance_details"],
                    intel["eval_method"],
                    intel["eval_details"],
                    intel["vehicle_type"],
                    intel["vehicle_details"],
                    intel["is_recompete"],
                    intel["incumbent_name"],
                    intel["recompete_details"],
                    intel["overall_confidence"],
                    json.dumps(intel["confidence_details"]) if intel["confidence_details"] else None,
                    load_id,
                    datetime.now(),
                ),
            )
            conn.commit()

            # Get the intel_id (either from insert or existing row)
            if cursor.lastrowid:
                intel_id = cursor.lastrowid
            else:
                # ON DUPLICATE KEY UPDATE doesn't set lastrowid reliably; query it
                cursor.execute(
                    "SELECT intel_id FROM opportunity_attachment_intel "
                    "WHERE notice_id = %s AND attachment_id <=> %s AND extraction_method = %s",
                    (notice_id, attachment_id, method),
                )
                row = cursor.fetchone()
                intel_id = row[0] if row else None

            return intel_id
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def _replace_source_rows(self, intel_id, matches, method):
        """Delete old source rows and insert new ones for an intel_id.

        Returns count of rows inserted.
        """
        if not intel_id or not matches:
            return 0

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Delete existing source rows for this intel_id
            cursor.execute(
                "DELETE FROM opportunity_intel_source WHERE intel_id = %s",
                (intel_id,),
            )

            count = 0
            for category, info in matches:
                # Map category to field_name
                field_name = category
                if category == "recompete":
                    field_name = "is_recompete"
                elif category == "incumbent_name":
                    field_name = "incumbent_name"

                cursor.execute(
                    "INSERT INTO opportunity_intel_source "
                    "(intel_id, field_name, attachment_id, source_filename, "
                    " char_offset_start, char_offset_end, matched_text, "
                    " surrounding_context, pattern_name, extraction_method, confidence) "
                    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)",
                    (
                        intel_id,
                        field_name,
                        info["attachment_id"],
                        info["filename"][:500] if info["filename"] else None,
                        info["char_offset_start"],
                        info["char_offset_end"],
                        info["matched_text"][:500],
                        info["surrounding_context"][:5000] if info["surrounding_context"] else None,
                        info["pattern_name"][:100],
                        method,
                        info["confidence"],
                    ),
                )
                count += 1

            conn.commit()
            return count
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def _update_opportunity_columns(self, notice_id, intel):
        """Update reserved opportunity columns with best intel values.

        Returns True if any column was updated.
        """
        updates = []
        params = []

        if intel.get("clearance_required"):
            updates.append("security_clearance_required = %s")
            params.append(intel["clearance_required"])

        if intel.get("incumbent_name"):
            updates.append("incumbent_name = %s")
            params.append(intel["incumbent_name"][:200])

        if intel.get("vehicle_type"):
            updates.append("contract_vehicle_type = LEFT(%s, 50)")
            params.append(intel["vehicle_type"])

        if not updates:
            return False

        params.append(notice_id)
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                f"UPDATE opportunity SET {', '.join(updates)} WHERE notice_id = %s",
                params,
            )
            conn.commit()
            updated = cursor.rowcount > 0
            if updated:
                logger.debug("Updated opportunity columns for %s", notice_id)
            return updated
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()


# ======================================================================
# Module-level helpers
# ======================================================================

def _upgrade_confidence(level):
    """Upgrade confidence by one level."""
    if level == "low":
        return "medium"
    if level == "medium":
        return "high"
    return "high"


def _rank_to_conf(rank):
    """Convert numeric rank back to confidence string."""
    if rank >= 3:
        return "high"
    if rank >= 2:
        return "medium"
    return "low"
