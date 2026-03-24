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
from datetime import datetime

from db.connection import get_connection

logger = logging.getLogger("fed_prospector.etl.attachment_ai_analyzer")

# Model mapping
MODELS = {
    "haiku": "claude-haiku-4-5-20251001",
    "sonnet": "claude-sonnet-4-6",
    "opus": "claude-opus-4-6",
}

SYSTEM_PROMPT = """You are an expert federal contracting analyst. Analyze the following government solicitation document and extract structured intelligence.

Return a JSON object with these fields:

{
    "clearance_required": "Y" or "N" or null (if unclear),
    "clearance_level": "TS/SCI" | "Top Secret" | "Secret" | "Confidential" | "Public Trust" | null,
    "clearance_scope": "all_personnel" | "key_personnel" | "some_positions" | null,
    "clearance_details": "Brief explanation of clearance requirements or null",
    "eval_method": "LPTA" | "Best Value" | "Trade-Off" | null,
    "eval_details": "Evaluation factors with weights/priority, e.g. 'Technical (30%), Past Performance (25%), Cost (25%), SB Plan (20%)' or null",
    "vehicle_type": "IDIQ" | "BPA" | "GSA Schedule" | "OASIS" | "OASIS+" | "SEWP" | "CIO-SP3" | "CIO-SP4" | "Alliant" | "VETS 2" | "8(a) STARS" | "GWAC" | "Standalone" | null,
    "vehicle_details": "Contract vehicle details, SIN numbers, pricing structure (FFP/CPFF/T&M), or null",
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

GENERAL:
- The user is a small business owner deciding whether to spend 80+ hours writing a proposal.
  Extract everything that helps them quickly assess: Can we do this? Can we win? Is it worth it?
- Only extract information explicitly stated in the document. Do not infer or guess.
- For fields where the document provides no information, use null (or empty list for arrays).
- Set confidence to "low" for fields where the evidence is ambiguous.
- Pay attention to negation and context — a document mentioning "Secret" in the phrase
  "no Secret clearance required" means clearance_required = "N", not "Y".
- Return ONLY valid JSON, no markdown formatting or explanation."""


class AttachmentAIAnalyzer:
    """Analyzes attachment text using Claude AI for structured intelligence extraction."""

    def __init__(self, model="haiku", dry_run=False):
        self.model_key = model
        self.model_id = MODELS.get(model, MODELS["haiku"])
        self.dry_run = dry_run
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
                    stats["skipped"] += 1
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
            max_tokens=2000,
            system=SYSTEM_PROMPT,
            messages=[{"role": "user", "content": user_message}],
        )

        # Parse JSON from response
        response_text = response.content[0].text.strip()

        # Handle markdown-wrapped JSON
        if response_text.startswith("```"):
            lines = response_text.split("\n")
            # Remove first and last lines (``` markers)
            lines = [l for l in lines if not l.strip().startswith("```")]
            response_text = "\n".join(lines)

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

    def _save_intel(self, doc, result):
        """Upsert AI analysis results into opportunity_attachment_intel."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO opportunity_attachment_intel "
                "(notice_id, attachment_id, extraction_method, source_text_hash, "
                " clearance_required, clearance_level, clearance_scope, clearance_details, "
                " eval_method, eval_details, vehicle_type, vehicle_details, "
                " is_recompete, incumbent_name, recompete_details, "
                " scope_summary, period_of_performance, labor_categories, key_requirements, "
                " overall_confidence, confidence_details, extracted_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s) "
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
                "scope_summary = VALUES(scope_summary), "
                "period_of_performance = VALUES(period_of_performance), "
                "labor_categories = VALUES(labor_categories), "
                "key_requirements = VALUES(key_requirements), "
                "overall_confidence = VALUES(overall_confidence), "
                "confidence_details = VALUES(confidence_details), "
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
                    result.get("is_recompete"),
                    result.get("incumbent_name"),
                    result.get("recompete_details"),
                    result.get("scope_summary"),
                    result.get("period_of_performance"),
                    json.dumps(result.get("labor_categories")) if result.get("labor_categories") else None,
                    json.dumps(result.get("key_requirements")) if result.get("key_requirements") else None,
                    result.get("overall_confidence", "low"),
                    json.dumps(result.get("confidence_details")) if result.get("confidence_details") else None,
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

