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
from collections import Counter
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
    "pricing_structure": {"pricing", "price", "cost", "contract type", "compensation"},
    "compliance_certs": {"certification", "compliance", "qualifications", "requirements"},
    "bonding_insurance": {"bonding", "insurance", "surety", "liability"},
    "subcontracting_oci": {"subcontracting", "small business", "conflict of interest", "oci"},
    "place_of_performance": {"place of performance", "location", "work site", "telework"},
    "set_aside_type": {"set-aside", "set aside", "small business", "socioeconomic"},
}

# Raw pattern definitions — compiled at module load
_RAW_PATTERNS = {
    "clearance_level": [
        {"pattern": r"\bTS/SCI\b", "value": "TS/SCI", "confidence": "high", "name": "clearance_ts_sci"},
        {"pattern": r"\bTop[\s\-]+Secret\b", "value": "Top Secret", "confidence": "high", "name": "clearance_top_secret"},
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
    "pricing_structure": [
        {"pattern": r"\b(?:Firm[- ]Fixed[- ]Price|FFP)\b", "value": "FFP", "confidence": "high", "name": "pricing_ffp"},
        {"pattern": r"\b(?:Cost[- ]Plus[- ]Fixed[- ]Fee|CPFF)\b", "value": "CPFF", "confidence": "high", "name": "pricing_cpff"},
        {"pattern": r"\b(?:Cost[- ]Plus[- ]Award[- ]Fee|CPAF)\b", "value": "CPAF", "confidence": "high", "name": "pricing_cpaf"},
        {"pattern": r"\b(?:Cost[- ]Plus[- ]Incentive[- ]Fee|CPIF)\b", "value": "CPIF", "confidence": "high", "name": "pricing_cpif"},
        {"pattern": r"\b(?:Time[- ]and[- ]Materials?|T&M|T & M)\b", "value": "T&M", "confidence": "high", "name": "pricing_tm"},
        {"pattern": r"\b(?:Labor[- ]Hour|LH)\b", "value": "LH", "confidence": "high", "name": "pricing_lh"},
    ],
    "compliance_certs": [
        {"pattern": r"\bCMMI\s*(?:Level|Lvl|ML|-)?\s*[2-5]\b", "value": None, "confidence": "high", "name": "cert_cmmi"},
        {"pattern": r"\bFedRAMP\b", "value": "FedRAMP", "confidence": "high", "name": "cert_fedramp"},
        {"pattern": r"\bISO\s*27001\b", "value": "ISO 27001", "confidence": "high", "name": "cert_iso27001"},
        {"pattern": r"\bISO\s*9001\b", "value": "ISO 9001", "confidence": "high", "name": "cert_iso9001"},
        {"pattern": r"\bSOC\s*2(?:\s*Type\s*(?:I{1,2}|1|2))?\b", "value": "SOC 2", "confidence": "high", "name": "cert_soc2"},
        {"pattern": r"\b(?:PMP|Project\s+Management\s+Professional)\b", "value": "PMP", "confidence": "medium", "name": "cert_pmp"},
        {"pattern": r"\bITIL\b", "value": "ITIL", "confidence": "medium", "name": "cert_itil"},
        {"pattern": r"\bCISSP\b", "value": "CISSP", "confidence": "high", "name": "cert_cissp"},
        {"pattern": r"\bCompTIA\s+(?:Security\+|Network\+|A\+|CASP)(?=\s|$|[,;.])", "value": None, "confidence": "medium", "name": "cert_comptia"},
    ],
    "bonding_insurance": [
        {"pattern": r"\b(?:performance\s+bond)\b", "value": "Performance Bond", "confidence": "high", "name": "bond_performance"},
        {"pattern": r"\b(?:bid\s+bond)\b", "value": "Bid Bond", "confidence": "high", "name": "bond_bid"},
        {"pattern": r"\b(?:payment\s+bond)\b", "value": "Payment Bond", "confidence": "high", "name": "bond_payment"},
        {"pattern": r"\b(?:professional\s+liability|errors\s+and\s+omissions|E&O)\b", "value": "Professional Liability", "confidence": "high", "name": "insurance_professional"},
        {"pattern": r"\b(?:general\s+liability)\b", "value": "General Liability", "confidence": "medium", "name": "insurance_general"},
        {"pattern": r"\b(?:workers.?\s*compensation)\b", "value": "Workers Compensation", "confidence": "medium", "name": "insurance_workers_comp"},
    ],
    "subcontracting_oci": [
        {"pattern": r"\bFAR\s+52\.219-9\b", "value": "SB Subcontracting Plan Required", "confidence": "high", "name": "sub_far_clause"},
        {"pattern": r"\b(?:small\s+business\s+)?subcontracting\s+(?:plan|goals?)\b", "value": "SB Subcontracting Plan Required", "confidence": "medium", "name": "sub_plan"},
        {"pattern": r"\b(?:organizational\s+conflict\s+of\s+interest|OCI)\b", "value": "OCI Restriction", "confidence": "high", "name": "oci_restriction"},
        {"pattern": r"\bFAR\s+(?:9\.5|3\.104)\b", "value": "OCI Restriction", "confidence": "high", "name": "oci_far_clause"},
    ],
    "place_of_performance": [
        {"pattern": r"\b(?:on[- ]site|onsite)\b", "value": "On-Site", "confidence": "medium", "name": "pop_onsite"},
        {"pattern": r"\b(?:remote\s+work|telework|work\s+from\s+home)\b", "value": "Remote", "confidence": "medium", "name": "pop_remote"},
        {"pattern": r"\bhybrid\b", "value": "Hybrid", "confidence": "low", "name": "pop_hybrid"},
        {"pattern": r"\b(?:contractor\s+facilit(?:y|ies))\b", "value": "Contractor Facility", "confidence": "medium", "name": "pop_contractor"},
        {"pattern": r"\b(?:government\s+facilit(?:y|ies)|government\s+site)\b", "value": "Government Facility", "confidence": "medium", "name": "pop_government"},
        {"pattern": r"\bCONUS\b", "value": "CONUS", "confidence": "high", "name": "pop_conus"},
        {"pattern": r"\bOCONUS\b", "value": "OCONUS", "confidence": "high", "name": "pop_oconus"},
    ],
    "set_aside_type": [
        {"pattern": r"\b(?:WOSB|Women[- ]Owned\s+Small\s+Business)\b", "value": "WOSB", "confidence": "high", "name": "setaside_wosb"},
        {"pattern": r"\b(?:EDWOSB|Economically\s+Disadvantaged\s+Women[- ]Owned)\b", "value": "EDWOSB", "confidence": "high", "name": "setaside_edwosb"},
        {"pattern": r"\b8\(a\)\b", "value": "8(a)", "confidence": "high", "name": "setaside_8a"},
        {"pattern": r"\b(?:SDVOSB|Service[- ]Disabled\s+Veteran[- ]Owned)\b", "value": "SDVOSB", "confidence": "high", "name": "setaside_sdvosb"},
        {"pattern": r"\bHUBZone\b", "value": "HUBZone", "confidence": "high", "name": "setaside_hubzone"},
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
    # Gov-doc words (Phase 110D)
    "question", "response", "tasked", "performing", "providing", "currently",
    "unknown", "tbd", "n/a", "na", "none", "section", "paragraph",
    "reference", "see", "per", "how", "what", "when", "where", "who",
    "which", "why",
})

# Broader set of common English words used for the all-words check.
# If EVERY word in a candidate name is in this set, it cannot be a company name.
# Covers verbs, nouns, adjectives, adverbs, prepositions common in gov documents.
_COMMON_ENGLISH_WORDS = _INCUMBENT_FALSE_POSITIVES | frozenset({
    # Additional verbs
    "accept", "accomplish", "achieve", "acquire", "address", "administer",
    "apply", "approve", "arrange", "assess", "assign", "assist", "assume",
    "attain", "authorize", "award", "begin", "brief", "build", "carry",
    "certify", "change", "check", "close", "collect", "combine", "come",
    "communicate", "compare", "complete", "comply", "conduct", "configure",
    "confirm", "consider", "construct", "consult", "contain", "continue",
    "contract", "contribute", "control", "coordinate", "correct", "create",
    "define", "deliver", "demonstrate", "deploy", "describe", "design",
    "determine", "develop", "direct", "discuss", "distribute", "document",
    "draft", "drive", "edit", "employ", "enable", "enforce", "engage",
    "enhance", "enter", "establish", "evaluate", "examine", "exceed",
    "execute", "exercise", "exhibit", "expand", "facilitate", "file",
    "fill", "find", "follow", "form", "fulfill", "function", "fund",
    "furnish", "gather", "generate", "get", "give", "go", "govern",
    "grant", "guide", "handle", "help", "hold", "host", "identify",
    "implement", "improve", "incorporate", "increase", "indicate",
    "inform", "initiate", "inspect", "install", "integrate", "intend",
    "interface", "interpret", "introduce", "investigate", "issue", "justify",
    "keep", "know", "lead", "learn", "leave", "let", "level", "limit",
    "list", "locate", "look", "maintain", "make", "manage", "maximize",
    "measure", "meet", "minimize", "modify", "monitor", "move", "need",
    "note", "notify", "obtain", "occur", "offer", "open", "operate",
    "order", "organize", "outline", "own", "participate", "pay", "perform",
    "permit", "place", "plan", "post", "practice", "prepare", "present",
    "prevent", "prioritize", "process", "procure", "produce", "program",
    "prohibit", "promote", "protect", "prove", "publish", "purchase",
    "put", "qualify", "range", "rate", "reach", "read", "receive",
    "recognize", "recommend", "record", "reduce", "relate", "release",
    "remain", "remove", "replace", "report", "represent", "request",
    "require", "research", "resolve", "respond", "restore", "result",
    "retain", "return", "review", "revise", "run", "satisfy", "save",
    "schedule", "secure", "seek", "select", "send", "separate", "serve",
    "set", "show", "sign", "specify", "staff", "start", "state", "stop",
    "store", "study", "support", "take", "teach", "tell", "terminate",
    "test", "track", "train", "transfer", "transmit", "treat", "turn",
    "understand", "update", "use", "utilize", "validate", "verify",
    "view", "work", "write",
    # Additional nouns common in gov documents
    "access", "account", "action", "activity", "addition", "agency",
    "agreement", "amount", "analysis", "annual", "application", "approach",
    "approval", "area", "assessment", "assistance", "basis", "benefit",
    "budget", "capability", "capacity", "case", "category", "center",
    "change", "clause", "code", "command", "comment", "committee",
    "company", "compliance", "component", "condition", "conference",
    "contractor", "cost", "country", "course", "coverage", "criteria",
    "data", "date", "day", "decision", "deliverable", "delivery",
    "department", "description", "development", "direction", "director",
    "division", "document", "duty", "effort", "element", "employee",
    "end", "entity", "entry", "environment", "equipment", "estimate",
    "event", "evidence", "example", "exception", "experience", "extent",
    "facility", "fact", "failure", "feature", "federal", "field",
    "final", "firm", "fiscal", "force", "format", "frequency",
    "full", "future", "general", "goal", "government", "group",
    "guidance", "headquarters", "hour", "impact", "individual",
    "information", "inspection", "instruction", "interest", "interim",
    "item", "job", "key", "labor", "language", "law", "level",
    "line", "location", "loss", "major", "management", "manner",
    "material", "matter", "means", "method", "military", "minimum",
    "mission", "month", "name", "national", "nature", "number",
    "objective", "office", "official", "operation", "option",
    "organization", "output", "oversight", "part", "party", "past",
    "payment", "people", "percent", "performance", "period", "person",
    "personnel", "phase", "point", "policy", "position", "possible",
    "potential", "primary", "prior", "priority", "problem", "procedure",
    "product", "project", "property", "proposal", "provision", "public",
    "purpose", "quality", "quantity", "question", "reason", "record",
    "region", "regulation", "related", "relationship", "report",
    "requirement", "resource", "response", "responsibility", "result",
    "risk", "role", "rule", "safety", "scope", "security", "service",
    "site", "situation", "size", "solution", "source", "space",
    "special", "standard", "statement", "status", "step", "strategy",
    "structure", "subject", "summary", "supply", "system", "task",
    "team", "technical", "technology", "term", "time", "title",
    "total", "training", "travel", "type", "unit", "value", "vendor",
    "volume", "week", "work", "year",
    # Additional adjectives / adverbs
    "additional", "adequate", "appropriate", "associated", "available",
    "basic", "best", "certain", "clear", "common", "consistent",
    "critical", "current", "direct", "effective", "entire", "equal",
    "essential", "existing", "first", "following", "former", "good",
    "great", "high", "important", "initial", "large", "last", "late",
    "least", "likely", "limited", "local", "long", "low", "main",
    "maximum", "minor", "more", "most", "multiple", "necessary", "new",
    "next", "normal", "official", "original", "overall", "own", "particular",
    "permanent", "physical", "possible", "present", "previous", "primary",
    "proper", "reasonable", "recent", "regular", "relevant", "second",
    "significant", "similar", "single", "small", "specific", "sufficient",
    "third", "timely", "total", "various", "written",
    # Prepositions / conjunctions / misc
    "according", "across", "against", "along", "among", "around",
    "as", "at", "because", "both", "by", "either", "else", "even",
    "except", "further", "however", "in", "instead", "neither", "nor",
    "now", "of", "off", "on", "once", "otherwise", "out", "rather",
    "since", "so", "still", "than", "then", "therefore", "though",
    "thus", "to", "too", "toward", "towards", "unless", "until",
    "up", "very", "well", "whereas", "whether", "while", "within",
    "without", "would", "could", "might", "yet",
})

# Regex to detect Q&A format: name followed by (number)
_QA_PAREN_NUMBER = re.compile(r"\s*\(\d")

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
    r"(?:there\s+is\s+no|there\s+are\s+no)\b|"
    r"e\.g\.\s*,?"
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
                            source_rows_inserted
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
                    result = self._process_notice(nid, method, load_id, force=force)
                    stats["notices_processed"] += 1
                    stats["intel_rows_upserted"] += result["intel_upserted"]
                    stats["source_rows_inserted"] += result["sources_inserted"]
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
                    f"intel={stats['intel_rows_upserted']}"
                )
            pbar.close()

            self.load_manager.complete_load(
                load_id,
                records_read=stats["notices_processed"],
                records_inserted=stats["intel_rows_upserted"],
                records_updated=0,
                records_unchanged=0,
                records_errored=0,
            )
            logger.info(
                "Intel extraction complete: %d notices, %d intel rows, %d sources",
                stats["notices_processed"],
                stats["intel_rows_upserted"],
                stats["source_rows_inserted"],
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

    def _process_notice(self, notice_id, method, load_id, force=False):
        """Process all text sources for a single notice.

        Returns dict: {intel_upserted, sources_inserted}
        """
        result = {"intel_upserted": 0, "sources_inserted": 0}

        # Task 4 (Phase 110D): When force=True, clean up stale consolidated
        # intel rows (attachment_id IS NULL) before re-extraction.
        if force:
            self._cleanup_stale_intel_rows(notice_id)

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

        # Inline backfill removed in Phase 110H — opportunity columns are now
        # updated exclusively by `backfill opportunity-intel` (per-field ranking).

        # Inline incumbent resolution removed in Phase 110H — incumbent_name
        # and incumbent_uei are now resolved by `backfill opportunity-intel`.

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
            # Sort patterns longest-first so longer phrases claim their
            # character range before shorter substrings can match inside them.
            sorted_patterns = sorted(patterns, key=lambda p: len(p.get("value") or ""), reverse=True)

            # Track claimed character ranges per category so shorter patterns
            # (e.g., "Secret") don't match inside already-found longer phrases
            # (e.g., "Top Secret").
            claimed_ranges = []  # list of (start, end) tuples

            for pdef in sorted_patterns:
                for m in pdef["regex"].finditer(text):
                    # Skip if this match falls inside an already-claimed range
                    if any(cs <= m.start() and ce >= m.end() for cs, ce in claimed_ranges):
                        continue

                    # --- Negation detection ---
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
                    claimed_ranges.append((m.start(), m.end()))

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

        # Q&A pattern: match sits inside a question answered with "No"
        # e.g., "does the Government require... Secret... ? | No, the standard..."
        qa_end = min(len(text), match_end + 200)
        qa_text = text[match_end:qa_end]
        q_mark = qa_text.find("?")
        if q_mark != -1:
            answer = qa_text[q_mark:q_mark + 40]
            if re.search(r"\?\s*\|?\s*No\b", answer, re.IGNORECASE):
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

        Filters (Phase 110D):
        1. Basic false-positive word check (existing)
        2. Reject names followed by (number) -- Q&A format indicator
        3. All-words common-English check -- rejects "must detail", "shall provide"
        4. Single-word name skepticism -- requires acronym pattern or digits
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

                # --- Phase 110D filters ---

                # Filter: Reject names followed by (number) -- Q&A format
                # e.g. "incumbent: Question(1) Will the Government..."
                after_name_start = m.end()
                after_text = text[match_start + after_name_start:match_start + after_name_start + 10] if match_start + after_name_start < len(text) else ""
                if _QA_PAREN_NUMBER.match(after_text):
                    continue

                # Filter: All-words common-English check
                # If every word in the name is a common English word, reject it.
                # Catches "Must Detail", "Shall Provide", etc.
                words = name.split()
                if words and all(w.lower() in _COMMON_ENGLISH_WORDS for w in words):
                    continue

                # Filter: Government org indicator
                # If the word immediately after the name is "staff", "personnel",
                # "employees", etc., it's a government agency, not a contractor.
                # e.g. "currently performed by BOP staff" — BOP = Bureau of Prisons
                _GOV_ORG_SUFFIXES = {"staff", "personnel", "employees", "office",
                                     "agency", "department", "officials", "team"}
                post_name_text = context[m.end():m.end() + 20].strip().lower()
                post_first_word = post_name_text.split()[0].rstrip(".,;:!?)") if post_name_text.split() else ""
                if post_first_word in _GOV_ORG_SUFFIXES:
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
            "pricing_structure": None,
            "place_of_performance": None,
            "key_requirements": [],
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
                # Collect for occurrence-based consolidation (Phase 110D)
                pass  # handled below after loop
            # --- Phase 110F: JSON array categories ---
            elif category == "compliance_certs":
                tag_value = value if value else info["matched_text"]
                tagged = f"[CERT] {tag_value}"
                if tagged not in intel["key_requirements"]:
                    intel["key_requirements"].append(tagged)
            elif category == "bonding_insurance":
                tag_value = value if value else info["matched_text"]
                tagged = f"[BOND] {tag_value}"
                if tagged not in intel["key_requirements"]:
                    intel["key_requirements"].append(tagged)
            elif category == "subcontracting_oci":
                tag_value = value if value else info["matched_text"]
                tag_prefix = "[OCI]" if "oci" in info["pattern_name"] else "[SUB]"
                tagged = f"{tag_prefix} {tag_value}"
                if tagged not in intel["key_requirements"]:
                    intel["key_requirements"].append(tagged)
            elif category == "set_aside_type":
                tag_value = value if value else info["matched_text"]
                tagged = f"[SET-ASIDE] {tag_value}"
                if tagged not in intel["key_requirements"]:
                    intel["key_requirements"].append(tagged)

        # --- Occurrence-based incumbent name consolidation (Phase 110D) ---
        # Count occurrences and track max confidence per name.
        incumbent_counts = Counter()
        incumbent_max_conf = {}  # name -> max confidence rank
        for category, info in matches:
            if category == "incumbent_name" and info.get("value"):
                name = info["value"]
                incumbent_counts[name] += 1
                conf_rank = _CONF_RANK.get(info["confidence"], 0)
                if conf_rank > incumbent_max_conf.get(name, 0):
                    incumbent_max_conf[name] = conf_rank

        if incumbent_counts:
            # Pick name with highest count; break ties by highest confidence
            best_name = max(
                incumbent_counts,
                key=lambda n: (incumbent_counts[n], incumbent_max_conf.get(n, 0)),
            )
            intel["incumbent_name"] = best_name
            intel["incumbent_name_count"] = incumbent_counts[best_name]

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

        # --- Phase 110F: direct column categories ---
        if "pricing_structure" in best:
            rank, value, _ = best["pricing_structure"]
            if value:
                intel["pricing_structure"] = value
            intel["confidence_details"]["pricing_structure"] = _rank_to_conf(rank)

        if "place_of_performance" in best:
            rank, value, _ = best["place_of_performance"]
            if value:
                intel["place_of_performance"] = value
            intel["confidence_details"]["place_of_performance"] = _rank_to_conf(rank)

        # Track confidence for JSON array categories
        for json_cat in ("compliance_certs", "bonding_insurance", "subcontracting_oci", "set_aside_type"):
            if json_cat in best:
                rank, _, _ = best[json_cat]
                intel["confidence_details"][json_cat] = _rank_to_conf(rank)

        # Store incumbent name occurrence count for transparency (Phase 110D)
        if intel.get("incumbent_name_count"):
            intel["confidence_details"]["incumbent_name_count"] = intel["incumbent_name_count"]
            if intel["incumbent_name"] and incumbent_max_conf:
                intel["confidence_details"]["incumbent_name"] = _rank_to_conf(
                    incumbent_max_conf.get(intel["incumbent_name"], 0)
                )

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

        # Convert key_requirements list to JSON (or None if empty)
        intel["key_requirements"] = intel["key_requirements"] if intel["key_requirements"] else None

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
                " pricing_structure, place_of_performance, key_requirements, "
                " overall_confidence, confidence_details, last_load_id, extracted_at) "
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
                "pricing_structure = VALUES(pricing_structure), "
                "place_of_performance = VALUES(place_of_performance), "
                "key_requirements = VALUES(key_requirements), "
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
                    intel["pricing_structure"],
                    intel["place_of_performance"],
                    json.dumps(intel["key_requirements"]) if intel["key_requirements"] else None,
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

    # ------------------------------------------------------------------
    # Cross-attachment incumbent resolution (Task 3, Phase 110D)
    # ------------------------------------------------------------------

    # Document-type weights for tie-breaking incumbent name conflicts.
    # Higher weight = more authoritative source for incumbent information.
    _FILENAME_WEIGHTS = [
        (re.compile(r"(?:SOW|PWS|statement.of.work)", re.IGNORECASE), 3),
        (re.compile(r"(?:J&A|J\s*&\s*A|justification)", re.IGNORECASE), 2),
        (re.compile(r"(?:RFP|solicitation)", re.IGNORECASE), 2),
        (re.compile(r"(?:Q&A|Q\s*&\s*A|question)", re.IGNORECASE), 1),
    ]

    def _resolve_incumbent_for_opportunity(self, notice_id, load_id):
        """Resolve incumbent name across all attachment intel rows for a notice.

        Queries all opportunity_attachment_intel rows for the notice_id where
        incumbent_name IS NOT NULL. If all agree, uses that name. If they
        disagree, picks the name with the highest occurrence count. Ties are
        broken by document-type weighting based on filename heuristics.

        After resolving the name, attempts UEI lookup via _resolve_incumbent_uei().
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT i.incumbent_name, a.filename "
                "FROM opportunity_attachment_intel i "
                "LEFT JOIN opportunity_attachment a ON i.attachment_id = a.attachment_id "
                "WHERE i.notice_id = %s AND i.incumbent_name IS NOT NULL",
                (notice_id,),
            )
            rows = cursor.fetchall()

            if not rows:
                return

            # Group names case-insensitively
            # names_dict: normalized_lower_name -> {original_name, count, weighted_score}
            names_dict = {}
            for row in rows:
                name = row["incumbent_name"]
                name_lower = name.strip().lower()
                filename = row.get("filename") or ""

                # Compute document-type weight for this row
                weight = 1  # default weight
                for pattern, w in self._FILENAME_WEIGHTS:
                    if pattern.search(filename):
                        weight = w
                        break

                if name_lower not in names_dict:
                    names_dict[name_lower] = {
                        "original": name,
                        "count": 0,
                        "weighted_score": 0,
                    }
                names_dict[name_lower]["count"] += 1
                names_dict[name_lower]["weighted_score"] += weight

            # If all rows agree (only one unique name), use it directly
            if len(names_dict) == 1:
                winning_name = next(iter(names_dict.values()))["original"]
            else:
                # Multiple different names -- log a warning
                logger.warning(
                    "Incumbent name conflict for %s: %s",
                    notice_id,
                    {k: v["count"] for k, v in names_dict.items()},
                )

                # Pick by highest occurrence count, then by weighted score for ties
                sorted_names = sorted(
                    names_dict.values(),
                    key=lambda v: (v["count"], v["weighted_score"]),
                    reverse=True,
                )
                winning_name = sorted_names[0]["original"]

            # Update opportunity.incumbent_name with the resolved winner
            update_cursor = conn.cursor()
            try:
                update_cursor.execute(
                    "UPDATE opportunity SET incumbent_name = %s WHERE notice_id = %s",
                    (winning_name[:200], notice_id),
                )
                conn.commit()
            except Exception:
                conn.rollback()
                raise
            finally:
                update_cursor.close()

            logger.debug(
                "Resolved incumbent for %s: %s", notice_id, winning_name
            )

            # Attempt UEI resolution (Task 5)
            self._resolve_incumbent_uei(notice_id, winning_name)

        finally:
            cursor.close()
            conn.close()

    # ------------------------------------------------------------------
    # Incumbent UEI resolution via entity table (Task 5, Phase 110D)
    # ------------------------------------------------------------------

    def _resolve_incumbent_uei(self, notice_id, incumbent_name):
        """Look up the incumbent's UEI in the entity table by name match.

        Uses a LIKE query against entity.legal_business_name. Sets
        opportunity.incumbent_uei only when exactly one entity matches.
        Multiple matches are logged as ambiguous and left NULL.

        Returns the UEI string or None.
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT uei_sam, legal_business_name FROM entity "
                "WHERE legal_business_name LIKE %s",
                (f"%{incumbent_name}%",),
            )
            matches = cursor.fetchall()

            if len(matches) == 1:
                uei = matches[0]["uei_sam"]
                update_cursor = conn.cursor()
                try:
                    update_cursor.execute(
                        "UPDATE opportunity SET incumbent_uei = %s WHERE notice_id = %s",
                        (uei, notice_id),
                    )
                    conn.commit()
                except Exception:
                    conn.rollback()
                    raise
                finally:
                    update_cursor.close()
                logger.debug(
                    "Resolved incumbent UEI for %s: %s (%s)",
                    notice_id, uei, matches[0]["legal_business_name"],
                )
                return uei
            elif len(matches) > 1:
                logger.info(
                    "Ambiguous UEI lookup for %s incumbent '%s': %d entity matches",
                    notice_id, incumbent_name, len(matches),
                )
                return None
            else:
                return None
        finally:
            cursor.close()
            conn.close()

    # ------------------------------------------------------------------
    # Stale intel cleanup for force mode (Task 4, Phase 110D)
    # ------------------------------------------------------------------

    def _cleanup_stale_intel_rows(self, notice_id):
        """Delete stale intel rows with attachment_id=NULL for a notice.

        When --force is used, old consolidated intel rows (attachment_id IS NULL)
        from previous runs may persist. This removes them before re-extraction
        so they don't interfere with fresh results.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "DELETE FROM opportunity_attachment_intel "
                "WHERE notice_id = %s AND attachment_id IS NULL",
                (notice_id,),
            )
            deleted = cursor.rowcount
            conn.commit()
            if deleted > 0:
                logger.debug(
                    "Cleaned up %d stale intel rows for %s", deleted, notice_id
                )
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

        # NOTE: incumbent_name is NOT set here. It is resolved across all
        # attachments by _resolve_incumbent_for_opportunity() after all
        # per-attachment processing completes (Task 3, Phase 110D).

        if intel.get("vehicle_type"):
            updates.append("contract_vehicle_type = LEFT(%s, 50)")
            params.append(intel["vehicle_type"])

        if intel.get("pricing_structure"):
            updates.append("pricing_structure = LEFT(%s, 50)")
            params.append(intel["pricing_structure"])

        if intel.get("place_of_performance"):
            updates.append("place_of_performance_detail = LEFT(%s, 200)")
            params.append(intel["place_of_performance"])

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
