"""AI-powered document analysis for attachment intelligence (Phase 110C).

Sends extracted document text to Claude for structured analysis. Extracts
insights that keyword/regex extraction cannot reliably identify: nuanced
clearance requirements, evaluation criteria, labor categories, scope
summaries, etc.

Uses Anthropic Batch API for daily batch processing (50% cost reduction)
and single-message API for on-demand UI-triggered analysis.
"""

import json
import hashlib
import logging
import os
import re
from datetime import datetime

from db.connection import get_connection

logger = logging.getLogger("fed_prospector.etl.attachment_ai_analyzer")

# Model mapping
MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
}

# Per-million-token pricing by model family
MODEL_PRICING = {
    "haiku": {"input": 1.00, "output": 5.00, "cache_read": 0.10, "cache_write": 1.25},
    "sonnet": {"input": 3.00, "output": 15.00, "cache_read": 0.30, "cache_write": 3.75},
    "opus": {"input": 15.00, "output": 75.00, "cache_read": 1.50, "cache_write": 18.75},
}

SYSTEM_PROMPT = """You are an expert federal contracting analyst. Analyze the following government solicitation document and extract structured intelligence.

Respond with ONLY a valid JSON object — no markdown, no explanation, no text before or after the JSON.

Return a JSON object with these fields:

{
    "clearance_required": "Y" or "N" or null (if unclear),
    "clearance_level": "TS/SCI" | "Top Secret" | "Secret" | "Confidential" | "Public Trust" | null,
    "clearance_scope": "all_personnel" | "key_personnel" | "some_positions" | null,
    "clearance_details": "Brief explanation of clearance requirements, or null",
    "eval_method": "LPTA" | "Best Value" | "Trade-Off" | null,
    "eval_details": "Evaluation factors with weights/priority, e.g. 'Technical (30%), Past Performance (25%), Cost (25%), SB Plan (20%)', or null",
    "vehicle_type": "IDIQ" | "BPA" | "GSA Schedule" | "OASIS" | "OASIS+" | "SEWP" | "CIO-SP3" | "CIO-SP4" | "Alliant" | "VETS 2" | "8(a) STARS" | "GWAC" | "Standalone" | null,
    "vehicle_details": "Contract vehicle details, SIN numbers, pricing structure (FFP/CPFF/T&M), or null",
    "pricing_structure": "FFP" | "CPFF" | "CPAF" | "CPIF" | "T&M" | "LH" | null,
    "place_of_performance": "Description of where work is performed, e.g. 'On-site at Fort Bragg, NC', 'Remote/telework', 'Contractor facility, CONUS', 'Hybrid - government facility Washington DC', or null",
    "is_recompete": "Y" or "N" or null (if unclear),
    "incumbent_name": "Name of incumbent contractor or null",
    "recompete_details": "Details about prior contract, transition requirements, or null",
    "scope_summary": "2-3 sentence summary of what the contractor will actually do. Focus on deliverables and work type, not boilerplate.",
    "period_of_performance": "Base period + options, e.g. '1 year base + 4 option years' or null",
    "labor_categories": [{"category": "Program Manager", "clearance": "Secret", "min_experience": "10 years", "quantity": 1}] or [],
    "key_requirements": ["list of dealbreaker requirements: certifications (CMMI, FedRAMP, ISO 27001), registrations (SAM, CAGE), insurance/bonding, SB subcontracting goals, place of performance, set-aside eligibility (WOSB, 8(a), SDVOSB, HUBZone), or other hard requirements that would disqualify a bidder"] or [],
    "overall_confidence": "high" | "medium" | "low",
    "confidence_details": {
        "clearance": "high" | "medium" | "low",
        "evaluation": "high" | "medium" | "low",
        "vehicle": "high" | "medium" | "low",
        "recompete": "high" | "medium" | "low",
        "scope": "high" | "medium" | "low"
    },
    "citations": {
        "clearance": "short verbatim quote (10-20 words) copied exactly from the document, or null",
        "evaluation": "short verbatim quote (10-20 words) copied exactly from the document, or null",
        "vehicle": "short verbatim quote (10-20 words) copied exactly from the document, or null",
        "recompete": "short verbatim quote (10-20 words) copied exactly from the document, or null",
        "scope": "short verbatim quote (10-20 words) copied exactly from the document, or null"
    }
}

Field-specific guidance:

SECURITY CLEARANCE:
- In federal contracting, "clearance" includes BOTH security clearances (Secret, Top Secret, TS/SCI)
  AND suitability/background investigations (Public Trust, Moderate Risk, High Risk).
- Set clearance_required to "Y" if the document mentions ANY of the following:
    - Security clearance levels: TS/SCI, Top Secret, Secret, Confidential
    - Suitability determinations: Public Trust, Moderate Risk, High Risk, Background Investigation (BI),
      Moderate-Risk Background Investigation (MBI)
    - Security forms/systems: SF-86, SF-85P, SF-312, e-QIP, DCSA
    - Access requirements: SCIF access, Facility Clearance (FCL), Personnel Clearance (PCL),
      Controlled Unclassified Information (CUI)
    - Agency-specific processes: FEMA PSD, DHS suitability, DOD CAF adjudication
- Use "Public Trust" as the clearance_level for all suitability/background investigation requirements.
- "N" means the document explicitly states no clearance or investigation is needed.
- null means the document doesn't mention clearance or personnel security at all.
- Watch for negation: "no clearance required" or "clearance is NOT required" means "N".

EVALUATION METHOD:
- "LPTA" = Lowest Price Technically Acceptable. Also indicated by FAR 15.101-2.
- "Best Value" = Best Value Trade-Off. Also indicated by FAR 15.101-1.
- For eval_details, extract the SPECIFIC evaluation factors and their weights/priorities.
  Example: "Technical Approach (30%), Past Performance (25%), Cost (25%), SB Subcontracting Plan (20%)"
  or "Technical is significantly more important than cost" or "All factors are equal."
- If the document describes evaluation factors but doesn't name the method, infer from context:
  price/technical tradeoff = "Best Value", lowest price wins if technically acceptable = "LPTA".

CONTRACT VEHICLE & PRICING:
- A BPA (Blanket Purchase Agreement) issued under a GSA Schedule is "BPA", not "GSA Schedule".
- A Task Order under a GWAC/IDIQ is the parent vehicle (e.g., "OASIS", "SEWP", "CIO-SP3").
- SIN numbers (e.g., SIN 541611) indicate GSA Schedule.
- "Standalone" means a standalone contract not under any vehicle/schedule.
- Known GWACs: OASIS, OASIS+, SEWP, CIO-SP3, CIO-SP4, Alliant, VETS 2, 8(a) STARS.
- In vehicle_details, include the pricing structure if mentioned:
  FFP (Firm Fixed Price), CPFF (Cost Plus Fixed Fee), CPAF (Cost Plus Award Fee),
  T&M (Time and Materials), LH (Labor Hour). This affects pricing strategy.

PRICING STRUCTURE:
- Return the contract pricing type as one of: "FFP", "CPFF", "CPAF", "CPIF", "T&M", "LH".
- Synonyms: "Firm Fixed Price" or "Firm-Fixed-Price" = "FFP", "Cost Plus Fixed Fee" = "CPFF",
  "Cost Plus Award Fee" = "CPAF", "Cost Plus Incentive Fee" = "CPIF",
  "Time and Materials" or "Time & Materials" = "T&M", "Labor Hour" = "LH".
- If the document specifies multiple CLINs with different pricing types, return the primary/dominant type.
- null if not mentioned.

PLACE OF PERFORMANCE:
- Where the work will be performed. Include city/state/installation if specified.
- Examples: "On-site at Pentagon, Arlington VA", "Remote/telework", "Contractor facility",
  "Government facility, Washington DC", "OCONUS - Ramstein AB, Germany", "Hybrid".
- If the document says "on-site" or "government facility" without a specific location, just say that.
- null if not mentioned.

RECOMPETE / INCUMBENT:
- Set is_recompete to "Y" if ANY of these appear: incumbent contractor named, "follow-on",
  "recompete"/"re-compete", "bridge contract"/"bridge extension", "successor contract",
  "transition plan"/"transition period", "currently performed by".
- Set is_recompete to "N" if "new requirement" or "new start" with no incumbent references.
- For incumbent_name, extract the company name (e.g., "Booz Allen Hamilton", "SAIC, Inc.").
  Do NOT return generic words like "the contractor" or "incumbent" as the name.

LABOR CATEGORIES:
- Extract as structured objects, not just names. For each labor category found, include:
  category (title), clearance (if specified per role), min_experience (years), quantity (if stated).
- Example: [{"category": "Program Manager", "clearance": "Secret", "min_experience": "10 years", "quantity": 1}]
- These often appear in Section C, labor category matrices, or QASP documents.
- If only category names are listed without detail, return simple objects: [{"category": "Project Manager"}]

KEY REQUIREMENTS (DEALBREAKERS):
- Focus on requirements that would DISQUALIFY a bidder who doesn't have them:
  - Certifications: CMMI Level 3/5, FedRAMP, ISO 27001, ISO 9001, SOC 2, PMP, ITIL
  - Registrations: SAM.gov, CAGE code, specific GSA Schedule holder
  - Set-aside eligibility: WOSB, EDWOSB, 8(a), SDVOSB, HUBZone, Small Business
  - Insurance/bonding: performance bond, bid bond, professional liability minimums
  - Small business subcontracting plan requirements (FAR 52.219-9)
  - Place of performance: on-site at government facility, specific city/state, remote allowed
  - Organizational Conflict of Interest (OCI) restrictions
  - Past performance: minimum number of similar contracts, minimum dollar value
  - Facility requirements: CONUS only, OCONUS, specific military installation
- Do NOT include generic boilerplate (e.g., "comply with all applicable laws").

SCOPE SUMMARY:
- Write 2-3 sentences explaining what the contractor will actually DO — deliverables, services,
  work type. A WOSB owner should read this and immediately know if their company does this kind of work.
- Focus on specifics, not boilerplate. "Provide IT help desk support for 500 users at Fort Bragg"
  is better than "Provide services in accordance with the PWS."

CITATIONS — prove your findings:
- For each non-null finding (clearance, evaluation, vehicle, recompete, scope), include a short
  VERBATIM quote from the document in the "citations" object.
- The quote MUST be copied EXACTLY character-for-character from the source text. Do not paraphrase,
  reword, fix typos, or change capitalization. We will search for this exact string in the document.
- Keep quotes to 10-20 words — just enough to uniquely identify the passage.
- Pick the single most decisive sentence fragment for each finding.
- If a field is null, its citation should also be null.
- Example: "clearance": "must possess a minimum Top Secret Facility Clearance (TS FCL)"

RESPONSE LENGTH LIMITS — keep the JSON compact to avoid truncation:
- "clearance_details": max 2 sentences. State what's required, not every paragraph reference.
- "eval_details": max 1-2 sentences. List factors and weights concisely.
- "vehicle_details": max 1 sentence.
- "recompete_details": max 1-2 sentences.
- "scope_summary": max 2-3 sentences.
- "period_of_performance": max 1 sentence, e.g. "1 year base + 4 option years". Do NOT elaborate.
- "labor_categories": max 15 entries. If more exist, include the most senior/critical ones.
- "key_requirements": max 10 items. Prioritize true dealbreakers.

GENERAL:
- The user is a small business owner deciding whether to spend 80+ hours writing a proposal.
  Extract everything that helps them quickly assess: Can we do this? Can we win? Is it worth it?
- Only extract information explicitly stated in the document. Do not infer or guess.
- For fields where the document provides no information, use null (or empty list for arrays).
- Confidence levels measure how clearly the document states the information:
  "high" = document explicitly states the value (e.g., "Top Secret clearance required")
  "medium" = value is implied or partially stated (e.g., references DD Form 254 but doesn't name a level)
  "low" = value is inferred from context or ambiguous (e.g., mentions "secure facility" but unclear if clearance needed)
- Pay attention to negation and context — a document mentioning "Secret" in the phrase
  "no Secret clearance required" means clearance_required = "N", not "Y".
- Return ONLY valid JSON, no markdown formatting or explanation."""


class AttachmentAIAnalyzer:
    """Analyzes attachment text using Claude AI for structured intelligence extraction."""

    def __init__(self, model="haiku", dry_run=False, requested_by=None):
        self.model_key = model
        self.model_id = MODELS.get(model, MODELS["haiku"])
        self.dry_run = dry_run
        self.requested_by = requested_by
        self.extraction_method = f"ai_dry_run" if dry_run else f"ai_{model}"
        self._client = None

    @property
    def client(self):
        """Lazy-init Anthropic client."""
        if self._client is None:
            api_key = os.environ.get("ANTHROPIC_API_KEY")
            if not api_key:
                from config.settings import Settings
                settings = Settings()
                api_key = getattr(settings, "ANTHROPIC_API_KEY", None)
            if not api_key:
                raise RuntimeError(
                    "ANTHROPIC_API_KEY not set. Add it to fed_prospector/.env or set "
                    "the environment variable. Use --dry-run to test without an API key."
                )
            import anthropic
            self._client = anthropic.Anthropic(api_key=api_key)
        return self._client

    def analyze(self, notice_id=None, batch_size=50, force=False):
        """Analyze attachments that have extracted text but no AI intel yet.

        Args:
            notice_id: Optional single notice to analyze.
            batch_size: Max documents to process in one run.
            force: Re-analyze even if AI intel already exists.

        Returns:
            dict with keys: processed, analyzed, skipped, failed, dry_run
        """
        stats = {"processed": 0, "analyzed": 0, "skipped": 0, "failed": 0, "dry_run": self.dry_run}

        docs = self._fetch_eligible_documents(notice_id, batch_size, force)
        if not docs:
            logger.info("No eligible documents found for AI analysis")
            return stats

        logger.info("Found %d documents eligible for AI analysis", len(docs))

        for doc in docs:
            stats["processed"] += 1
            try:
                result = self._analyze_document(doc)
                if result:
                    self._save_intel(doc, result)
                    stats["analyzed"] += 1
                    logger.info(
                        "Analyzed %s attachment_id=%s (%s confidence)",
                        doc["notice_id"], doc["attachment_id"],
                        result.get("overall_confidence", "unknown"),
                    )
                else:
                    stats["failed"] += 1
            except Exception as e:
                stats["failed"] += 1
                logger.error(
                    "Failed to analyze %s attachment_id=%s: %s",
                    doc["notice_id"], doc["attachment_id"], e,
                )

        logger.info(
            "AI analysis complete: %d processed, %d analyzed, %d skipped, %d failed",
            stats["processed"], stats["analyzed"], stats["skipped"], stats["failed"],
        )
        return stats

    def analyze_notice(self, notice_id, force=False):
        """Analyze all attachments for a single notice (on-demand).

        Used by the demand loader for UI-triggered "Enhance with AI" requests.

        Returns:
            dict with analysis stats
        """
        return self.analyze(notice_id=notice_id, batch_size=1000, force=force)

    def _fetch_eligible_documents(self, notice_id, batch_size, force):
        """Fetch documents that have extracted text but no AI intel row yet."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            conditions = ["oa.extraction_status = 'extracted'", "oa.extracted_text IS NOT NULL"]
            params = []

            if notice_id:
                conditions.append("oa.notice_id = %s")
                params.append(notice_id)

            if not force:
                # Exclude documents that already have an AI intel row (real, not dry_run)
                conditions.append("""
                    NOT EXISTS (
                        SELECT 1 FROM opportunity_attachment_intel oai
                        WHERE oai.attachment_id = oa.attachment_id
                          AND oai.extraction_method IN ('ai_haiku', 'ai_sonnet')
                    )
                """)

            where = " AND ".join(conditions)
            cursor.execute(f"""
                SELECT oa.attachment_id, oa.notice_id, oa.filename,
                       oa.extracted_text, oa.text_hash
                FROM opportunity_attachment oa
                WHERE {where}
                ORDER BY oa.attachment_id
                LIMIT %s
            """, params + [batch_size])

            return cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

    def _analyze_document(self, doc):
        """Send document text to Claude and parse structured response.

        In dry-run mode, builds the prompt but returns a mock response.
        """
        text = doc["extracted_text"]

        # Truncate very long documents to avoid excessive costs
        max_chars = 100_000  # ~25k tokens
        if len(text) > max_chars:
            text = text[:max_chars] + "\n\n[Document truncated at 100,000 characters]"
            logger.debug(
                "Truncated document %s from %d to %d chars",
                doc["attachment_id"], len(doc["extracted_text"]), max_chars,
            )

        user_message = f"Analyze this federal solicitation document:\n\n{text}"

        if self.dry_run:
            # Log what would be sent
            logger.info(
                "DRY RUN: Would send %d chars to %s for attachment_id=%s (%s)",
                len(user_message), self.model_id, doc["attachment_id"], doc["filename"],
            )
            # Return a mock response to exercise the full pipeline
            return {
                "clearance_required": None,
                "clearance_level": None,
                "clearance_scope": None,
                "clearance_details": None,
                "eval_method": None,
                "eval_details": None,
                "vehicle_type": None,
                "vehicle_details": None,
                "pricing_structure": None,
                "place_of_performance": None,
                "is_recompete": None,
                "incumbent_name": None,
                "recompete_details": None,
                "scope_summary": "[DRY RUN] No actual analysis performed",
                "period_of_performance": None,
                "labor_categories": [],
                "key_requirements": [],
                "overall_confidence": "low",
                "confidence_details": {
                    "clearance": "low",
                    "evaluation": "low",
                    "vehicle": "low",
                    "recompete": "low",
                    "scope": "low",
                },
            }

        # Real API call
        response = self.client.messages.create(
            model=self.model_id,
            max_tokens=4096,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        # Log token usage and cost
        self._log_usage(doc["notice_id"], doc["attachment_id"], response.usage)

        # Parse JSON from response
        response_text = response.content[0].text.strip()

        # Handle markdown-wrapped JSON
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (``` markers)
            lines = [l for l in lines if not l.strip().startswith("```")]
            response_text = "\n".join(lines)

        # Extract JSON object if model added extra text before/after
        brace_start = response_text.find("{")
        brace_end = response_text.rfind("}")
        if brace_start != -1 and brace_end != -1:
            response_text = response_text[brace_start:brace_end + 1]

        try:
            result = json.loads(response_text)
        except json.JSONDecodeError as e:
            logger.error(
                "Failed to parse JSON response for attachment_id=%s: %s\nResponse: %s",
                doc["attachment_id"], e, response_text[:500],
            )
            return None

        # Validate required fields
        if "overall_confidence" not in result:
            result["overall_confidence"] = "low"
        if result["overall_confidence"] not in ("high", "medium", "low"):
            result["overall_confidence"] = "low"

        return result

    def _calculate_cost(self, model_key, input_tokens, output_tokens,
                        cache_read_tokens=0, cache_write_tokens=0):
        """Calculate USD cost from token counts using per-million-token pricing."""
        pricing = MODEL_PRICING.get(model_key, MODEL_PRICING["haiku"])
        cost = (
            input_tokens * pricing["input"] / 1_000_000
            + output_tokens * pricing["output"] / 1_000_000
            + cache_read_tokens * pricing["cache_read"] / 1_000_000
            + cache_write_tokens * pricing["cache_write"] / 1_000_000
        )
        return round(cost, 6)

    def _log_usage(self, notice_id, attachment_id, response_usage):
        """Log AI API usage to ai_usage_log table."""
        input_tokens = response_usage.input_tokens
        output_tokens = response_usage.output_tokens
        cache_read = getattr(response_usage, 'cache_read_input_tokens', 0) or 0
        cache_write = getattr(response_usage, 'cache_creation_input_tokens', 0) or 0
        cost = self._calculate_cost(
            self.model_key, input_tokens, output_tokens, cache_read, cache_write
        )

        conn = None
        cursor = None
        try:
            conn = get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ai_usage_log
                (notice_id, attachment_id, model, input_tokens, output_tokens,
                 cache_read_tokens, cache_write_tokens, cost_usd, requested_by)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, (notice_id, attachment_id, self.model_key, input_tokens, output_tokens,
                  cache_read, cache_write, cost, self.requested_by))
            conn.commit()
            logger.debug(
                "Logged AI usage: %s attachment_id=%s model=%s in=%d out=%d cost=$%.6f",
                notice_id, attachment_id, self.model_key,
                input_tokens, output_tokens, cost,
            )
        except Exception as e:
            logger.warning("Failed to log AI usage: %s", e)
        finally:
            if cursor:
                cursor.close()
            if conn:
                conn.close()

    def _resolve_citations(self, doc, result):
        """Resolve verbatim citation quotes to character offsets in the source text.

        Returns a dict like {"clearance": 5313, "evaluation": null, ...}
        where each value is the char offset where the quote was found, or null.
        """
        citations = result.get("citations")
        if not citations or not isinstance(citations, dict):
            return None

        text = doc.get("extracted_text", "")
        if not text:
            return None

        # Pre-compute normalized versions for fallback matching
        text_lower = text.lower()
        text_ws_norm = re.sub(r"\s+", " ", text)
        text_ws_norm_lower = text_ws_norm.lower()

        offsets = {}
        for field, quote in citations.items():
            if not quote or not isinstance(quote, str):
                offsets[field] = None
                continue

            # 1. Exact match
            pos = text.find(quote)
            if pos >= 0:
                offsets[field] = pos
                logger.debug("Citation exact match for %s at offset %d", field, pos)
                continue

            # 2. Case-insensitive
            pos = text_lower.find(quote.lower())
            if pos >= 0:
                offsets[field] = pos
                logger.debug("Citation case-insensitive match for %s at offset %d", field, pos)
                continue

            # 3. Whitespace-normalized (handles newlines/tabs in extracted text)
            quote_ws = re.sub(r"\s+", " ", quote)
            pos = text_ws_norm.find(quote_ws)
            if pos >= 0:
                offsets[field] = pos
                logger.debug("Citation whitespace-normalized match for %s at offset %d", field, pos)
                continue

            pos = text_ws_norm_lower.find(quote_ws.lower())
            if pos >= 0:
                offsets[field] = pos
                logger.debug("Citation ws-norm+case-insensitive match for %s at offset %d", field, pos)
                continue

            # 4. Partial match on first 40 chars (Claude sometimes adds to the end)
            if len(quote) > 40:
                short = quote[:40]
                pos = text.find(short)
                if pos >= 0:
                    offsets[field] = pos
                    logger.debug("Citation partial-40 match for %s at offset %d", field, pos)
                    continue
                pos = text_lower.find(short.lower())
                if pos >= 0:
                    offsets[field] = pos
                    logger.debug("Citation partial-40 case-insensitive match for %s at offset %d", field, pos)
                    continue

            offsets[field] = None
            logger.debug("Citation NOT found for %s: %s", field, quote[:60])

        # Only return if at least one offset was found
        if any(v is not None for v in offsets.values()):
            return offsets
        return None

    # Canonical pricing type abbreviations and their synonyms
    _PRICING_TYPES = {
        "FFP": re.compile(r"\bFFP\b|Firm[\s-]Fixed[\s-]Price", re.IGNORECASE),
        "CPFF": re.compile(r"\bCPFF\b|Cost[\s-]Plus[\s-]Fixed[\s-]Fee", re.IGNORECASE),
        "CPAF": re.compile(r"\bCPAF\b|Cost[\s-]Plus[\s-]Award[\s-]Fee", re.IGNORECASE),
        "CPIF": re.compile(r"\bCPIF\b|Cost[\s-]Plus[\s-]Incentive[\s-]Fee", re.IGNORECASE),
        "T&M": re.compile(r"\bT&M\b|\bT\s*&\s*M\b|Time\s+and\s+Materials?|Time\s*&\s*Materials?", re.IGNORECASE),
        "LH": re.compile(r"\bLH\b|Labor[\s-]Hour", re.IGNORECASE),
    }

    # Place of performance keywords to look for in text fields
    _POP_PATTERNS = re.compile(
        r"\b(?:on[\s-]site|remote|telework|hybrid|CONUS|OCONUS|"
        r"contractor\s+facility|government\s+facility)\b",
        re.IGNORECASE,
    )

    def _extract_pricing_structure(self, result):
        """Extract pricing_structure from AI response.

        First checks the explicit 'pricing_structure' field from the AI.
        Falls back to scanning 'vehicle_details' and 'key_requirements' for
        known pricing type terms. Returns a short abbreviation (max 50 chars)
        like 'FFP', 'CPFF', 'T&M', etc., or None.
        """
        # 1. Check explicit AI field first
        explicit = result.get("pricing_structure")
        if explicit and isinstance(explicit, str):
            val = explicit.strip().upper()
            # Normalize common full names to abbreviations
            for abbrev, pattern in self._PRICING_TYPES.items():
                if pattern.search(val):
                    return abbrev
            # If AI returned something we don't recognize, return it truncated
            if len(val) <= 50:
                return explicit.strip()

        # 2. Scan vehicle_details and key_requirements for pricing terms
        texts_to_scan = []
        vd = result.get("vehicle_details")
        if vd and isinstance(vd, str):
            texts_to_scan.append(vd)
        kr = result.get("key_requirements")
        if kr and isinstance(kr, list):
            texts_to_scan.extend(str(item) for item in kr)

        combined = " ".join(texts_to_scan)
        if combined:
            for abbrev, pattern in self._PRICING_TYPES.items():
                if pattern.search(combined):
                    return abbrev

        return None

    def _extract_place_of_performance(self, result):
        """Extract place_of_performance from AI response.

        First checks the explicit 'place_of_performance' field from the AI.
        Falls back to scanning 'key_requirements' for place-of-performance
        keywords. Returns a descriptive string (max 200 chars) or None.
        """
        # 1. Check explicit AI field first
        explicit = result.get("place_of_performance")
        if explicit and isinstance(explicit, str) and explicit.strip():
            return explicit.strip()[:200]

        # 2. Scan key_requirements for place of performance mentions
        kr = result.get("key_requirements")
        if kr and isinstance(kr, list):
            for item in kr:
                item_str = str(item)
                if self._POP_PATTERNS.search(item_str):
                    return item_str[:200]
                # Also check for explicit "place of performance" phrase
                if re.search(r"place\s+of\s+performance", item_str, re.IGNORECASE):
                    return item_str[:200]

        return None

    def _save_intel(self, doc, result):
        """Upsert AI analysis results into opportunity_attachment_intel."""
        # Resolve citation quotes to character offsets before saving
        citation_offsets = self._resolve_citations(doc, result)

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Extract pricing_structure from AI response, or fall back to parsing vehicle_details/key_requirements
            pricing_structure = self._extract_pricing_structure(result)
            # Extract place_of_performance from AI response, or fall back to parsing key_requirements
            place_of_performance = self._extract_place_of_performance(result)

            cursor.execute(
                "INSERT INTO opportunity_attachment_intel "
                "(notice_id, attachment_id, extraction_method, source_text_hash, "
                " clearance_required, clearance_level, clearance_scope, clearance_details, "
                " eval_method, eval_details, vehicle_type, vehicle_details, "
                " pricing_structure, place_of_performance, "
                " is_recompete, incumbent_name, recompete_details, "
                " scope_summary, period_of_performance, labor_categories, key_requirements, "
                " overall_confidence, confidence_details, citation_offsets, extracted_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
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
                "pricing_structure = VALUES(pricing_structure), "
                "place_of_performance = VALUES(place_of_performance), "
                "is_recompete = VALUES(is_recompete), "
                "incumbent_name = VALUES(incumbent_name), "
                "recompete_details = VALUES(recompete_details), "
                "scope_summary = VALUES(scope_summary), "
                "period_of_performance = VALUES(period_of_performance), "
                "labor_categories = VALUES(labor_categories), "
                "key_requirements = VALUES(key_requirements), "
                "overall_confidence = VALUES(overall_confidence), "
                "confidence_details = VALUES(confidence_details), "
                "citation_offsets = VALUES(citation_offsets), "
                "extracted_at = VALUES(extracted_at)",
                (
                    doc["notice_id"],
                    doc["attachment_id"],
                    self.extraction_method,
                    doc.get("text_hash"),
                    result.get("clearance_required"),
                    result.get("clearance_level"),
                    result.get("clearance_scope"),
                    result.get("clearance_details"),
                    result.get("eval_method"),
                    result.get("eval_details"),
                    result.get("vehicle_type"),
                    result.get("vehicle_details"),
                    pricing_structure,
                    (place_of_performance or "")[:200] or None,
                    result.get("is_recompete"),
                    (result.get("incumbent_name") or "")[:200] or None,
                    result.get("recompete_details"),
                    result.get("scope_summary"),
                    (result.get("period_of_performance") or "")[:200] or None,
                    json.dumps(result.get("labor_categories")) if result.get("labor_categories") else None,
                    json.dumps(result.get("key_requirements")) if result.get("key_requirements") else None,
                    result.get("overall_confidence", "low"),
                    json.dumps(result.get("confidence_details")) if result.get("confidence_details") else None,
                    json.dumps(citation_offsets) if citation_offsets else None,
                    datetime.now(),
                ),
            )
            conn.commit()
            logger.debug(
                "Saved AI intel for %s attachment_id=%s (method=%s)",
                doc["notice_id"], doc["attachment_id"], self.extraction_method,
            )
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

