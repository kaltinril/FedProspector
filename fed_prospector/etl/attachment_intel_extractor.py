"""Regex/keyword intelligence extraction from opportunity attachment text (Phase 110).

Scans extracted attachment text (annotated Markdown) and opportunity description_text
for security clearance, evaluation method, contract vehicle, and recompete signals.
Stores structured intel in document_intel_summary with full provenance tracking
in document_intel_evidence. Per-opportunity rollup in opportunity_attachment_summary.

Usage:
    from etl.attachment_intel_extractor import AttachmentIntelExtractor
    extractor = AttachmentIntelExtractor()
    stats = extractor.extract_intel(batch_size=100)
"""

import hashlib
import json
import logging
import os
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
    "period_of_performance": {"period of performance", "duration", "term", "ordering period", "option"},
    "naics_code": {"naics", "size standard", "product service code", "psc", "classification"},
    "wage_determination": {"wage", "labor", "compensation", "service contract act", "davis-bacon"},
    "contract_value": {"value", "ceiling", "estimated", "price", "cost", "budget", "funding"},
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
        {"pattern": r"(?<!Number )\btask\s+order\b(?!\s*(?:Number|\())", "value": "IDIQ", "confidence": "low", "name": "vehicle_task_order"},
        {"pattern": r"(?<!Number )\bdelivery\s+order\b(?!\s*(?:Number|\())", "value": "IDIQ", "confidence": "low", "name": "vehicle_delivery_order"},
        {"pattern": r"\b(?:indefinite[- ]delivery(?:[- ]indefinite[- ]quantity)?)\b", "value": "IDIQ", "confidence": "high", "name": "vehicle_id_iq_spelled"},
        {"pattern": r"\b(?:BOA|Basic\s+Ordering\s+Agreement)\b", "value": "BOA", "confidence": "high", "name": "vehicle_boa"},
        {"pattern": r"\b(?:SBIR|STTR)\b", "value": None, "confidence": "high", "name": "vehicle_sbir"},
        {"pattern": r"\bPolaris\s+(?:GWAC|contract)\b|GSA\s+Polaris\b", "value": "Polaris", "confidence": "high", "name": "vehicle_polaris"},
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
        {"pattern": r"\b(?:Fixed[- ]Price[- ]Incentive|FPI(?:F|S)?)\b", "value": "FPI", "confidence": "high", "name": "pricing_fpi"},
        {"pattern": r"\b(?:Cost[- ]Reimbursement|Cost[- ]Type)\b", "value": "Cost Reimbursement", "confidence": "medium", "name": "pricing_cr"},
        {"pattern": r"\baward\s+(?:term|fee)\b", "value": None, "confidence": "medium", "name": "pricing_award_fee"},
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
        {"pattern": r"\bCMMC\s*(?:Level\s*)?[1-5]\b", "value": "CMMC", "confidence": "high", "name": "cert_cmmc_level"},
        {"pattern": r"\bNIST\s+(?:SP\s+)?800-171\b", "value": "NIST 800-171", "confidence": "high", "name": "cert_nist_171"},
        {"pattern": r"\bDFARS?\s+252\.204-7012\b", "value": "DFARS CUI", "confidence": "high", "name": "cert_dfars_cui"},
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
        {"pattern": r"\bcontractor'?s?\s+(?:site|location|premises)\b", "value": "Contractor Facility", "confidence": "medium", "name": "pop_contractor_site"},
        {"pattern": r"\b(?:off[- ]?site|offsite)\b", "value": "Off-Site", "confidence": "medium", "name": "pop_offsite"},
        {"pattern": r"\bgovernment\s+premises\b", "value": "Government Facility", "confidence": "medium", "name": "pop_gov_premises"},
        {"pattern": r"\bmultiple\s+(?:locations|sites)\b", "value": "Multiple Locations", "confidence": "medium", "name": "pop_multiple"},
    ],
    "set_aside_type": [
        {"pattern": r"\b(?:WOSB|Women[- ]Owned\s+Small\s+Business)\b", "value": "WOSB", "confidence": "high", "name": "setaside_wosb"},
        {"pattern": r"\b(?:EDWOSB|Economically\s+Disadvantaged\s+Women[- ]Owned)\b", "value": "EDWOSB", "confidence": "high", "name": "setaside_edwosb"},
        {"pattern": r"\b8\(a\)\b", "value": "8(a)", "confidence": "high", "name": "setaside_8a"},
        {"pattern": r"\b(?:SDVOSB|Service[- ]Disabled\s+Veteran[- ]Owned)\b", "value": "SDVOSB", "confidence": "high", "name": "setaside_sdvosb"},
        {"pattern": r"\bHUBZone\b", "value": "HUBZone", "confidence": "high", "name": "setaside_hubzone"},
        {"pattern": r"\b(?:Total\s+Small\s+Business|Total\s+SB)\s*(?:Set[- ]?Aside)?\b", "value": "Total SB", "confidence": "high", "name": "setaside_total_sb"},
        {"pattern": r"\bSmall\s+Business\s+Set[- ]?Aside\b", "value": "SB Set-Aside", "confidence": "high", "name": "setaside_sb"},
        {"pattern": r"\b(?:VOSB|Veteran[- ]Owned\s+Small\s+Business)\b", "value": "VOSB", "confidence": "high", "name": "setaside_vosb"},
        {"pattern": r"\bsole[- ]source\b", "value": "Sole Source", "confidence": "high", "name": "setaside_sole_source"},
        {"pattern": r"\bFull\s+and\s+Open\s+Competition\b", "value": "Unrestricted", "confidence": "high", "name": "setaside_unrestricted_fao", "_needs_context_check": "no_other_than"},
        {"pattern": r"\bUnrestricted\b", "value": "Unrestricted", "confidence": "medium", "name": "setaside_unrestricted", "_needs_context_check": "near_set_aside"},
    ],
    "period_of_performance": [
        {"pattern": r"\b(?:one|two|three|four|five|six|seven|1|2|3|4|5|6|7)\s*\(?\d*\)?\s*base\s+(?:year|period)", "value": None, "confidence": "high", "name": "pop_base_year"},
        {"pattern": r"\bbase\s+(?:year|period)\s*(?:plus|and|\+|with)\s*(?:\w+\s+)?\(?\d+\)?\s*option\s+(?:year|period)s?", "value": None, "confidence": "high", "name": "pop_base_plus_option"},
        {"pattern": r"\bperiod\s+of\s+performance\s+(?:is|shall\s+be|:)\s*(?:approximately\s+)?(\d+)\s*(?:month|year|day)s?", "value": None, "confidence": "high", "name": "pop_duration"},
        {"pattern": r"\b(?:one|two|three|four|five|six|seven|eight|nine|ten|\d+)[- ]year\s+(?:contract|IDIQ|ordering\s+period|effort|period)", "value": None, "confidence": "high", "name": "pop_x_year"},
        {"pattern": r"\bordering\s+period\b", "value": None, "confidence": "medium", "name": "pop_ordering_period"},
        {"pattern": r"\boption\s+(?:year|period)s?\b", "value": None, "confidence": "medium", "name": "pop_option"},
    ],
    "naics_code": [
        {"pattern": r"\bNAICS\s*(?:Code)?[:\s]*(\d{6})\b", "value": None, "confidence": "high", "name": "naics_code"},
        {"pattern": r"\bsize\s+standard\s+(?:of\s+|is\s+)?\$[\d,.]+\s*(?:million|M)?\b", "value": None, "confidence": "medium", "name": "naics_size_standard"},
        {"pattern": r"\b(?:PSC|Product\s+Service\s+Code)[:\s]*([A-Z]\d{3})\b", "value": None, "confidence": "high", "name": "psc_code"},
    ],
    "wage_determination": [
        {"pattern": r"\bService\s+Contract\s+(?:Act|Labor\s+Standards)\b", "value": "SCA", "confidence": "high", "name": "wage_sca"},
        {"pattern": r"\bDavis[- ]Bacon(?:\s+Act)?\b", "value": "Davis-Bacon", "confidence": "high", "name": "wage_dba"},
        {"pattern": r"\bWage\s+Determination\s*(?:No\.?|Number|#)?[:\s]*(?:[A-Z]{2})?\d{7,}\b", "value": None, "confidence": "high", "name": "wage_wd_number"},
        {"pattern": r"\bFAR\s+52\.222-41\b", "value": "SCA", "confidence": "high", "name": "wage_far_sca"},
        {"pattern": r"\bFAR\s+52\.222-6\b", "value": "Davis-Bacon", "confidence": "high", "name": "wage_far_dba"},
        {"pattern": r"\bprevailing\s+wage\b", "value": None, "confidence": "medium", "name": "wage_prevailing"},
    ],
    "contract_value": [
        {"pattern": r"\$\s*\d+(?:\.\d+)?\s*(?:million|billion|M|B)\b", "value": None, "confidence": "high", "name": "value_shorthand"},
        {"pattern": r"\b(?:ceiling|maximum)\s+(?:value|price|amount|contract\s+value)\b", "value": None, "confidence": "medium", "name": "value_ceiling"},
        {"pattern": r"\b(?:estimated|total|aggregate)\s+(?:value|amount|price|cost)\b", "value": None, "confidence": "medium", "name": "value_estimated"},
        {"pattern": r"\bnot[- ]to[- ]exceed\b(?=.{0,30}\$)", "value": None, "confidence": "medium", "name": "value_nte"},
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

# PPQ / Past Performance document detection (Phase 110ZZ Task 8)
# Documents matching this pattern describe past contracts, not the current procurement.
# All confidence levels are downgraded by one level for matches in these documents.
_PPQ_DOCUMENT_PATTERN = re.compile(
    r"\b(?:Past\s+Performance\s+(?:Questionnaire|Information|Survey|Evaluation)|PPQ)\b",
    re.IGNORECASE,
)

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

    def __init__(self, db_connection=None, load_manager=None, dump_on_error: bool = False):
        self.db_connection = db_connection
        self.load_manager = load_manager or LoadManager()
        self.dump_on_error = dump_on_error

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
            total_eligible = self._count_eligible_notices(notice_id, method, force)
            remaining = total_eligible - len(notice_ids)
            logger.info(
                "Found %d notices to extract intel from (load_id=%d) — %d total eligible, %d remaining after this batch",
                len(notice_ids), load_id, total_eligible, remaining,
            )

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
                    if self.dump_on_error:
                        raise
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
                    "  SELECT m.notice_id FROM opportunity_attachment m "
                    "  JOIN attachment_document ad ON ad.attachment_id = m.attachment_id "
                    "  WHERE ad.extraction_status = 'extracted' AND ad.extracted_text IS NOT NULL "
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
                    "  SELECT m.notice_id FROM opportunity_attachment m "
                    "  JOIN attachment_document ad ON ad.attachment_id = m.attachment_id "
                    "  WHERE ad.extraction_status = 'extracted' AND ad.extracted_text IS NOT NULL "
                    "  UNION "
                    "  SELECT notice_id FROM opportunity "
                    "  WHERE description_text IS NOT NULL AND description_text != ''"
                    ") n "
                    "LEFT JOIN opportunity_attachment_summary s "
                    "  ON n.notice_id = s.notice_id AND s.extraction_method = %s "
                    "WHERE s.summary_id IS NULL "
                    "ORDER BY n.notice_id "
                    "LIMIT %s"
                )
            params = [batch_size] if force else [method, batch_size]
            cursor.execute(sql, params)
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()
            conn.close()

    def _count_eligible_notices(self, notice_id, method, force):
        """Count total eligible notices (without LIMIT) for progress reporting."""
        if notice_id:
            return 1

        conn = get_connection()
        cursor = conn.cursor()
        try:
            if force:
                sql = (
                    "SELECT COUNT(DISTINCT n.notice_id) FROM ("
                    "  SELECT m.notice_id FROM opportunity_attachment m "
                    "  JOIN attachment_document ad ON ad.attachment_id = m.attachment_id "
                    "  WHERE ad.extraction_status = 'extracted' AND ad.extracted_text IS NOT NULL "
                    "  UNION "
                    "  SELECT notice_id FROM opportunity "
                    "  WHERE description_text IS NOT NULL AND description_text != ''"
                    ") n"
                )
                cursor.execute(sql)
            else:
                sql = (
                    "SELECT COUNT(DISTINCT n.notice_id) FROM ("
                    "  SELECT m.notice_id FROM opportunity_attachment m "
                    "  JOIN attachment_document ad ON ad.attachment_id = m.attachment_id "
                    "  WHERE ad.extraction_status = 'extracted' AND ad.extracted_text IS NOT NULL "
                    "  UNION "
                    "  SELECT notice_id FROM opportunity "
                    "  WHERE description_text IS NOT NULL AND description_text != ''"
                    ") n "
                    "LEFT JOIN opportunity_attachment_summary s "
                    "  ON n.notice_id = s.notice_id AND s.extraction_method = %s "
                    "WHERE s.summary_id IS NULL"
                )
                cursor.execute(sql, [method])
            return cursor.fetchone()[0]
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

        # Upsert per-source intel rows (one per document_id)
        document_ids_seen = set()
        for document_id, filename, text in sources:
            source_matches = [m for m in all_matches if m[1]["attachment_id"] == document_id]
            if not source_matches:
                continue
            document_ids_seen.add(document_id)
            source_intel = self._consolidate_matches(source_matches)
            source_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()

            intel_id = self._upsert_intel_row(
                notice_id, document_id, method, source_hash, source_intel, load_id,
            )
            if intel_id:
                result["intel_upserted"] += 1

                # Replace evidence provenance rows
                source_count = self._replace_source_rows(
                    intel_id, source_matches, method,
                )
                result["sources_inserted"] += source_count

        # Upsert opportunity-level summary row in opportunity_attachment_summary
        self._upsert_summary_row(notice_id, method, text_hash, intel, load_id)

        # Inline backfill removed in Phase 110H — opportunity columns are now
        # updated exclusively by `backfill opportunity-intel` (per-field ranking).

        # Inline incumbent resolution removed in Phase 110H — incumbent_name
        # and incumbent_uei are now resolved by `backfill opportunity-intel`.

        return result

    def _gather_text_sources(self, notice_id):
        """Gather all text sources for a notice.

        Returns list of (document_id_or_None, filename, text).
        Joins through opportunity_attachment map to find documents for this notice.
        """
        sources = []
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            # Extracted attachments via map table
            cursor.execute(
                "SELECT ad.document_id, COALESCE(ad.filename, sa.filename) AS filename, "
                "ad.extracted_text "
                "FROM opportunity_attachment m "
                "JOIN attachment_document ad ON ad.attachment_id = m.attachment_id "
                "JOIN sam_attachment sa ON sa.attachment_id = m.attachment_id "
                "WHERE m.notice_id = %s AND ad.extraction_status = 'extracted' "
                "AND ad.extracted_text IS NOT NULL",
                (notice_id,),
            )
            for row in cursor.fetchall():
                fname = row["filename"] or "unknown"
                sources.append((row["document_id"], fname, row["extracted_text"]))

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

        # PPQ heuristic: detect past-performance documents (Phase 110ZZ Task 8)
        is_ppq = bool(
            _PPQ_DOCUMENT_PATTERN.search(filename)
            or _PPQ_DOCUMENT_PATTERN.search(text[:200])
        )

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

                    # --- Context checks for high-FP patterns (Phase 110ZZ) ---
                    context_check = pdef.get("_needs_context_check")
                    if context_check == "no_other_than":
                        # "Full and Open Competition" — skip if preceded by "other than" within 60 chars
                        pre_text = text[max(0, m.start() - 60):m.start()].lower()
                        if "other than" in pre_text:
                            logger.debug("Context check failed (other than): %s in %s", pdef["name"], filename)
                            continue
                    elif context_check == "near_set_aside":
                        # "Unrestricted" — require near "set-aside" or "competition" heading/context
                        window = text[max(0, m.start() - 200):min(len(text), m.end() + 200)].lower()
                        if not any(kw in window for kw in ("set-aside", "set aside", "competition type", "competition:")):
                            logger.debug("Context check failed (no set-aside context): %s in %s", pdef["name"], filename)
                            continue

                    confidence = pdef["confidence"]

                    # Structure-aware confidence boosting
                    confidence = self._boost_confidence(text, m.start(), category, confidence)

                    # PPQ downgrade: past-performance docs describe old contracts (Phase 110ZZ Task 8)
                    if is_ppq:
                        if confidence == "high":
                            confidence = "medium"
                        elif confidence == "medium":
                            confidence = "low"

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

        # --- Filename-only scan (no char offsets) ---
        if attachment_id is not None and filename and filename != "unknown":
            for category, patterns in PATTERNS.items():
                sorted_patterns = sorted(patterns, key=lambda p: len(p.get("value") or ""), reverse=True)
                fname_claimed = []
                for pdef in sorted_patterns:
                    if pdef.get("_needs_context_check"):
                        continue
                    for m in pdef["regex"].finditer(filename):
                        if any(cs <= m.start() and ce >= m.end() for cs, ce in fname_claimed):
                            continue
                        match_info = {
                            "attachment_id": attachment_id,
                            "filename": filename,
                            "matched_text": m.group()[:500],
                            "surrounding_context": filename,
                            "pattern_name": pdef["name"],
                            "value": pdef.get("value"),
                            "confidence": pdef["confidence"],
                            "char_offset_start": None,
                            "char_offset_end": None,
                            "scope": pdef.get("scope"),
                        }
                        matches.append((category, match_info))
                        fname_claimed.append((m.start(), m.end()))

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
            "clearance_details": {},
            "eval_method": None,
            "eval_details": {},
            "vehicle_type": None,
            "vehicle_details": {},
            "is_recompete": None,
            "incumbent_name": None,
            "recompete_details": {},
            "pricing_structure": None,
            "place_of_performance": None,
            "period_of_performance": None,
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

            # Collect details (deduplicated with occurrence counts)
            detail_key = f"{info['pattern_name']}: {info['matched_text']}"
            if category == "clearance_level":
                intel["clearance_details"][detail_key] = intel["clearance_details"].get(detail_key, 0) + 1
            elif category == "eval_method":
                intel["eval_details"][detail_key] = intel["eval_details"].get(detail_key, 0) + 1
            elif category == "vehicle_type":
                intel["vehicle_details"][detail_key] = intel["vehicle_details"].get(detail_key, 0) + 1
            elif category == "recompete":
                intel["recompete_details"][detail_key] = intel["recompete_details"].get(detail_key, 0) + 1
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
            elif category == "period_of_performance":
                tag_value = info["matched_text"]
                # Store the matched text with surrounding context as the value
                context = info.get("surrounding_context", tag_value)
                if tag_value not in str(intel.get("period_of_performance") or ""):
                    if intel["period_of_performance"]:
                        intel["period_of_performance"] += "; " + tag_value
                    else:
                        intel["period_of_performance"] = tag_value
            elif category == "naics_code":
                tag_value = value if value else info["matched_text"]
                tagged = f"[NAICS] {tag_value}"
                if tagged not in intel["key_requirements"]:
                    intel["key_requirements"].append(tagged)
            elif category == "wage_determination":
                tag_value = value if value else info["matched_text"]
                tagged = f"[WAGE] {tag_value}"
                if tagged not in intel["key_requirements"]:
                    intel["key_requirements"].append(tagged)
            elif category == "contract_value":
                tag_value = value if value else info["matched_text"]
                tagged = f"[VALUE] {tag_value}"
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

        if "period_of_performance" in best:
            rank, _, _ = best["period_of_performance"]
            intel["confidence_details"]["period_of_performance"] = _rank_to_conf(rank)

        # Track confidence for JSON array categories
        for json_cat in ("compliance_certs", "bonding_insurance", "subcontracting_oci", "set_aside_type", "naics_code", "wage_determination", "contract_value"):
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

        # Convert detail dicts to "pattern: text (count)" format
        def _format_details(detail_dict):
            if not detail_dict:
                return None
            return "; ".join(f"{k} ({v})" for k, v in detail_dict.items())

        intel["clearance_details"] = _format_details(intel["clearance_details"])
        intel["eval_details"] = _format_details(intel["eval_details"])
        intel["vehicle_details"] = _format_details(intel["vehicle_details"])
        intel["recompete_details"] = _format_details(intel["recompete_details"])

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

    # Fields that hold potentially large text in intel dicts
    _TEXT_FIELDS = [
        "clearance_details", "eval_details", "vehicle_details", "recompete_details",
        "clearance_level", "clearance_scope", "eval_method", "vehicle_type",
        "incumbent_name", "pricing_structure", "place_of_performance",
        "period_of_performance", "overall_confidence",
    ]

    def _handle_db_insert_error(self, e, table_name, notice_id, method, intel, document_id=None):
        """Build enhanced error message for DB insert failures and optionally dump to file.

        Args:
            e: The exception from the DB insert.
            table_name: Table being written to (document_intel_summary or opportunity_attachment_summary).
            notice_id: The opportunity notice ID.
            method: Extraction method label.
            intel: The intel dict being inserted.
            document_id: The document ID (None for summary rows).

        Returns:
            Enhanced error message string.

        Raises:
            The original exception if dump_on_error is True (after writing dump file).
        """
        err_str = str(e)

        # Try to extract column name from MySQL error like "Data too long for column 'X'"
        import re as _re
        col_match = _re.search(r"Data too long for column '(\w+)'", err_str)
        col_name = col_match.group(1) if col_match else None

        # Build field-length summary
        field_lengths = {}
        for field in self._TEXT_FIELDS:
            val = intel.get(field)
            if val is not None:
                field_lengths[field] = len(str(val).encode("utf-8"))

        # Also check JSON-serialized fields
        for field in ("key_requirements", "confidence_details"):
            val = intel.get(field)
            if val is not None:
                serialized = json.dumps(val)
                field_lengths[field] = len(serialized.encode("utf-8"))

        if col_name and col_name in field_lengths:
            enhanced_msg = (
                f"Data too long for column '{col_name}' on {table_name} "
                f"(attempted {field_lengths[col_name]:,} bytes, column max ~65535 bytes)"
            )
        else:
            enhanced_msg = f"DB insert error on {table_name}: {err_str}"

        if self.dump_on_error:
            # Write dump file
            dump_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "logs")
            os.makedirs(dump_dir, exist_ok=True)
            ts = datetime.now().strftime("%Y%m%d_%H%M%S")
            dump_filename = f"intel_dump_{notice_id}_{ts}.json"
            dump_path = os.path.join(dump_dir, dump_filename)

            # Build serializable dump
            dump_data = {
                "notice_id": notice_id,
                "document_id": document_id,
                "extraction_method": method,
                "table_name": table_name,
                "field_lengths_bytes": field_lengths,
                "intel": {},
            }
            for k, v in intel.items():
                try:
                    json.dumps(v)
                    dump_data["intel"][k] = v
                except (TypeError, ValueError):
                    dump_data["intel"][k] = str(v)

            with open(dump_path, "w", encoding="utf-8") as f:
                json.dump(dump_data, f, indent=2, default=str)

            logger.error(
                "Intel extraction failed for %s: %s — dump written to %s",
                notice_id, enhanced_msg, dump_path,
            )
            raise

        return enhanced_msg

    def _upsert_intel_row(self, notice_id, document_id, method, text_hash, intel, load_id):
        """Upsert a per-document intel row into document_intel_summary. Returns intel_id.

        For document_id=None (description_text source), this is skipped — those go
        to the summary table only.
        """
        if document_id is None:
            # Description-text-only sources don't get per-document intel rows
            return None

        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO document_intel_summary "
                "(document_id, extraction_method, source_text_hash, "
                " clearance_required, clearance_level, clearance_scope, clearance_details, "
                " eval_method, eval_details, vehicle_type, vehicle_details, "
                " is_recompete, incumbent_name, recompete_details, "
                " pricing_structure, place_of_performance, period_of_performance, key_requirements, "
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
                "period_of_performance = VALUES(period_of_performance), "
                "key_requirements = VALUES(key_requirements), "
                "overall_confidence = VALUES(overall_confidence), "
                "confidence_details = VALUES(confidence_details), "
                "last_load_id = VALUES(last_load_id), "
                "extracted_at = VALUES(extracted_at)",
                (
                    document_id,
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
                    intel["period_of_performance"],
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
                    "SELECT intel_id FROM document_intel_summary "
                    "WHERE document_id = %s AND extraction_method = %s",
                    (document_id, method),
                )
                row = cursor.fetchone()
                intel_id = row[0] if row else None

            return intel_id
        except Exception as e:
            conn.rollback()
            enhanced = self._handle_db_insert_error(
                e, "document_intel_summary", notice_id, method, intel,
                document_id=document_id,
            )
            # If dump_on_error is True, _handle_db_insert_error already raised.
            # Otherwise, raise with the enhanced message.
            raise type(e)(enhanced) from e
        finally:
            cursor.close()
            conn.close()

    def _upsert_summary_row(self, notice_id, method, text_hash, intel, load_id):
        """Upsert a per-opportunity rollup row into opportunity_attachment_summary."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO opportunity_attachment_summary "
                "(notice_id, extraction_method, source_text_hash, "
                " clearance_required, clearance_level, clearance_scope, clearance_details, "
                " eval_method, eval_details, vehicle_type, vehicle_details, "
                " is_recompete, incumbent_name, recompete_details, "
                " pricing_structure, place_of_performance, period_of_performance, key_requirements, "
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
                "period_of_performance = VALUES(period_of_performance), "
                "key_requirements = VALUES(key_requirements), "
                "overall_confidence = VALUES(overall_confidence), "
                "confidence_details = VALUES(confidence_details), "
                "last_load_id = VALUES(last_load_id), "
                "extracted_at = VALUES(extracted_at)",
                (
                    notice_id,
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
                    intel["period_of_performance"],
                    json.dumps(intel["key_requirements"]) if intel["key_requirements"] else None,
                    intel["overall_confidence"],
                    json.dumps(intel["confidence_details"]) if intel["confidence_details"] else None,
                    load_id,
                    datetime.now(),
                ),
            )
            conn.commit()
        except Exception as e:
            conn.rollback()
            enhanced = self._handle_db_insert_error(
                e, "opportunity_attachment_summary", notice_id, method, intel,
            )
            # If dump_on_error is True, _handle_db_insert_error already raised.
            # Otherwise, raise with the enhanced message.
            raise type(e)(enhanced) from e
        finally:
            cursor.close()
            conn.close()

    def _replace_source_rows(self, intel_id, matches, method):
        """Delete old evidence rows and insert new ones for an intel_id.

        Returns count of rows inserted.
        """
        if not intel_id or not matches:
            return 0

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Delete existing evidence rows for this intel_id
            cursor.execute(
                "DELETE FROM document_intel_evidence WHERE intel_id = %s",
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
                    "INSERT INTO document_intel_evidence "
                    "(intel_id, field_name, document_id, source_filename, "
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
        """Resolve incumbent name across all document intel rows for a notice.

        Queries all document_intel_summary rows for the notice_id (via map table)
        where incumbent_name IS NOT NULL. If all agree, uses that name. If they
        disagree, picks the name with the highest occurrence count. Ties are
        broken by document-type weighting based on filename heuristics.

        After resolving the name, attempts UEI lookup via _resolve_incumbent_uei().
        """
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT dis.incumbent_name, COALESCE(ad.filename, sa.filename) AS filename "
                "FROM document_intel_summary dis "
                "JOIN attachment_document ad ON ad.document_id = dis.document_id "
                "JOIN sam_attachment sa ON sa.attachment_id = ad.attachment_id "
                "JOIN opportunity_attachment m ON m.attachment_id = sa.attachment_id "
                "WHERE m.notice_id = %s AND dis.incumbent_name IS NOT NULL",
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
        """Delete stale summary rows for a notice before re-extraction.

        When --force is used, old consolidated summary rows from previous runs
        may persist. This removes them before re-extraction so they don't
        interfere with fresh results.

        Also cleans up per-document intel+evidence for documents mapped to this notice.
        Deletes evidence rows BEFORE intel rows (evidence references intel_id).
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # 1. Delete stale opportunity_attachment_summary rows for this notice
            #    Only keyword/heuristic rows — leave AI rows intact
            cursor.execute(
                "DELETE FROM opportunity_attachment_summary "
                "WHERE notice_id = %s AND extraction_method IN ('keyword', 'heuristic')",
                (notice_id,),
            )
            summary_deleted = cursor.rowcount

            # 2. Delete per-document evidence + intel for documents mapped to this notice
            #    Only keyword/heuristic rows — leave AI rows intact
            # First find intel_ids for documents on this notice
            cursor.execute(
                "SELECT dis.intel_id FROM document_intel_summary dis "
                "JOIN attachment_document ad ON ad.document_id = dis.document_id "
                "JOIN opportunity_attachment m ON m.attachment_id = ad.attachment_id "
                "WHERE m.notice_id = %s AND dis.extraction_method IN ('keyword', 'heuristic')",
                (notice_id,),
            )
            intel_ids = [row[0] for row in cursor.fetchall()]

            evidence_deleted = 0
            intel_deleted = 0
            if intel_ids:
                # Delete evidence BEFORE intel (evidence references intel_id)
                placeholders = ", ".join(["%s"] * len(intel_ids))
                cursor.execute(
                    f"DELETE FROM document_intel_evidence WHERE intel_id IN ({placeholders})",
                    intel_ids,
                )
                evidence_deleted = cursor.rowcount

                cursor.execute(
                    f"DELETE FROM document_intel_summary WHERE intel_id IN ({placeholders})",
                    intel_ids,
                )
                intel_deleted = cursor.rowcount

            conn.commit()
            total = summary_deleted + evidence_deleted + intel_deleted
            if total > 0:
                logger.debug(
                    "Cleaned up stale intel for %s: %d summary, %d intel, %d evidence rows",
                    notice_id, summary_deleted, intel_deleted, evidence_deleted,
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
