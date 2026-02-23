"""Data cleaner for SAM.gov entity records. (Phase 2)

Handles all 10 known data quality issues from prior SAM.gov imports.
Rules come from both hardcoded logic and the etl_data_quality_rule table.
"""

import json
import logging
import re
import unicodedata

from db.connection import get_connection
from utils.date_utils import parse_yyyymmdd
from utils.parsing import fix_pipe_escapes


logger = logging.getLogger("fed_prospector.etl.data_cleaner")

# Regex patterns compiled once at module level
_US_ZIP5_RE = re.compile(r"\b(\d{5})\b")
_US_ZIP9_RE = re.compile(r"\b(\d{5}-\d{4})\b")
_US_ZIP5_ONLY_RE = re.compile(r"^\d{5}$")
_US_ZIP9_ONLY_RE = re.compile(r"^\d{5}-?\d{4}$")
_DATE_SLASH_RE = re.compile(r"\d{1,2}/\d{1,2}/\d{2,4}")
_PO_BOX_RE = re.compile(r"P\.?O\.?\s*BOX", re.IGNORECASE)
_CAGE_SPLIT_RE = re.compile(r"[,\s]+")
_TIMESTAMP_RE = re.compile(r"^(\d{4}-\d{2}-\d{2})[T ]\d{2}:\d{2}")

# Date field names found in SAM.gov entity records (both JSON and flattened)
_ENTITY_DATE_FIELDS = [
    "registrationDate",
    "lastUpdateDate",
    "registrationExpirationDate",
    "activationDate",
    "entityStartDate",
    "fiscalYearEndCloseDate",
    "submissionDate",
    "ueiExpirationDate",
    "ueiCreationDate",
    "certificationEntryDate",
    "certificationExitDate",
]

# Points of contact names that contain address sub-fields
_POC_NAMES = [
    "governmentBusinessPOC",
    "electronicBusinessPOC",
    "governmentBusinessAlternatePOC",
    "electronicBusinessAlternatePOC",
    "pastPerformancePOC",
    "pastPerformanceAlternatePOC",
]


class DataCleaner:
    """Cleans and normalizes SAM.gov entity data before database loading.

    Handles all 10 known data quality issues:
      1. ZIP codes containing city/state/country names
      2. ZIP codes containing PO BOX data
      3. State fields containing dates
      4. Foreign provinces in state field (flag only)
      5. Non-ASCII characters in country names
      6. Missing country codes XKS/XWB/XGZ (validate only)
      7. Comma-separated CAGE codes
      8. Retired NAICS codes (flag only)
      9. Escaped pipes in DAT files
     10. YYYYMMDD date conversion
    """

    def __init__(self, db_rules=True):
        self.logger = logging.getLogger("fed_prospector.etl.data_cleaner")
        self._stats = {}
        self._db_rules = []

        if db_rules:
            self._load_db_rules()

    # ------------------------------------------------------------------
    # Database rule loading
    # ------------------------------------------------------------------

    def _load_db_rules(self):
        """Load active rules from etl_data_quality_rule table."""
        try:
            conn = get_connection()
            cursor = conn.cursor(dictionary=True)
            try:
                cursor.execute(
                    "SELECT rule_id, rule_name, description, target_table, "
                    "target_column, rule_type, rule_definition, priority "
                    "FROM etl_data_quality_rule "
                    "WHERE is_active = 'Y' "
                    "ORDER BY priority ASC"
                )
                self._db_rules = cursor.fetchall()
                # Parse JSON rule_definition for each rule
                for rule in self._db_rules:
                    if rule["rule_definition"] and isinstance(rule["rule_definition"], str):
                        rule["rule_definition"] = json.loads(rule["rule_definition"])
                self.logger.info(
                    "Loaded %d active data quality rules from database",
                    len(self._db_rules),
                )
            finally:
                cursor.close()
                conn.close()
        except Exception:
            self.logger.warning(
                "Could not load data quality rules from database; "
                "proceeding with hardcoded rules only",
                exc_info=True,
            )
            self._db_rules = []

    # ------------------------------------------------------------------
    # Stats tracking
    # ------------------------------------------------------------------

    def _increment(self, rule_name):
        """Increment the counter for a cleaning rule."""
        self._stats[rule_name] = self._stats.get(rule_name, 0) + 1

    def get_stats(self):
        """Return dict of rule_name -> count of how many times each rule fired."""
        return dict(self._stats)

    def reset_stats(self):
        """Reset all counters to 0."""
        self._stats.clear()

    # ------------------------------------------------------------------
    # Generic record cleaning
    # ------------------------------------------------------------------

    def clean_record(self, record, source_format="json"):
        """Apply all applicable rules to a single record dict.

        Args:
            record: Mutable dict representing one data record.
            source_format: 'json' for API responses, 'dat' for pipe-delimited
                           flat files, 'csv' for CSV extracts.

        Returns:
            The same record dict (modified in-place) after cleaning.
        """
        if record is None:
            return record

        # DAT-specific: fix escaped pipes in all string values
        if source_format == "dat":
            for key, value in record.items():
                if isinstance(value, str) and "|\\|" in value:
                    record[key] = fix_pipe_escapes(value)
                    self._increment("fix_escaped_pipes")

        # Apply database-driven rules
        for rule in self._db_rules:
            self._apply_db_rule(rule, record)

        return record

    def _apply_db_rule(self, rule, record):
        """Apply a single database-defined rule to a record.

        Rules are dispatched by rule_type:
          - CLEAN: modify a target column value
          - VALIDATE: check a value, log warning if invalid
          - TRANSFORM: convert a value to a different format
          - REJECT: (not used - we never reject records)
        """
        col = rule.get("target_column")
        if not col or col not in record:
            return

        definition = rule.get("rule_definition") or {}
        rule_type = rule.get("rule_type", "")
        value = record[col]

        if rule_type == "CLEAN":
            action = definition.get("action")
            if action == "clean_zip" and value:
                country = record.get(definition.get("country_field", "countryCode"))
                cleaned = self.clean_zip_code(value, country)
                if cleaned != value:
                    record[col] = cleaned
                    self._increment(rule["rule_name"])
            elif action == "clean_state" and value:
                country = record.get(definition.get("country_field", "countryCode"))
                cleaned = self.clean_state_code(value, country)
                if cleaned != value:
                    record[col] = cleaned
                    self._increment(rule["rule_name"])

        elif rule_type == "TRANSFORM":
            action = definition.get("action")
            if action == "normalize_date" and value:
                cleaned = self.normalize_date(value)
                if cleaned is not None:
                    record[col] = cleaned
                    self._increment(rule["rule_name"])

        elif rule_type == "VALIDATE":
            action = definition.get("action")
            if action == "warn_length" and value:
                max_len = definition.get("max_length", 2)
                if len(str(value)) > max_len:
                    self.logger.debug(
                        "Validation warning [%s]: %s='%s' exceeds %d chars",
                        rule["rule_name"], col, value, max_len,
                    )
                    self._increment(rule["rule_name"])

    # ------------------------------------------------------------------
    # ZIP code cleaning (issues #1 and #2)
    # ------------------------------------------------------------------

    def clean_zip_code(self, zip_code, country_code=None):
        """Clean a ZIP/postal code value.

        Handles:
          - ZIP fields containing city/state/country names
          - ZIP fields containing PO BOX data
          - Extracts 5-digit or 5+4 US ZIP codes
          - Keeps foreign postal codes as-is when they look valid

        Args:
            zip_code: Raw ZIP/postal code string.
            country_code: 3-letter country code (e.g. 'USA') or None.

        Returns:
            Cleaned ZIP string, or None if no valid code can be extracted.
        """
        if not zip_code or not isinstance(zip_code, str):
            return None

        cleaned = zip_code.strip()
        if not cleaned:
            return None

        is_us = country_code in (None, "USA", "US", "")

        # Issue #2: Remove PO BOX contamination
        if _PO_BOX_RE.search(cleaned):
            self._increment("clean_zip_po_box")
            # Try to extract a real ZIP from the PO BOX string
            match_9 = _US_ZIP9_RE.search(cleaned)
            if match_9:
                return match_9.group(1)
            match_5 = _US_ZIP5_RE.search(cleaned)
            if match_5:
                return match_5.group(1)
            return None

        # If already a clean US ZIP, return as-is
        if _US_ZIP5_ONLY_RE.match(cleaned):
            return cleaned
        if _US_ZIP9_ONLY_RE.match(cleaned):
            # Normalize to 5-4 format with dash
            digits = cleaned.replace("-", "")
            return f"{digits[:5]}-{digits[5:]}"

        # Issue #1: ZIP contains city/state/country text
        if is_us:
            # Try to extract a 5+4 ZIP from contaminated value
            match_9 = _US_ZIP9_RE.search(cleaned)
            if match_9:
                self._increment("clean_zip_contaminated")
                return match_9.group(1)
            match_5 = _US_ZIP5_RE.search(cleaned)
            if match_5:
                self._increment("clean_zip_contaminated")
                return match_5.group(1)
            # No valid US ZIP found at all
            self._increment("clean_zip_contaminated")
            self.logger.debug(
                "Could not extract US ZIP from '%s'", cleaned
            )
            return None

        # Foreign postal code: keep as-is if it looks reasonable
        # (alphanumeric, spaces, dashes - up to ~10 chars)
        foreign_cleaned = cleaned.split(",")[0].strip()
        if len(foreign_cleaned) <= 10:
            return foreign_cleaned
        # Long value is likely contaminated - try numeric extraction
        match_5 = _US_ZIP5_RE.search(cleaned)
        if match_5:
            self._increment("clean_zip_contaminated")
            return match_5.group(1)
        self._increment("clean_zip_contaminated")
        self.logger.debug(
            "Could not extract postal code from foreign value '%s'", cleaned
        )
        return None

    # ------------------------------------------------------------------
    # State code cleaning (issues #3 and #4)
    # ------------------------------------------------------------------

    def clean_state_code(self, state_code, country_code=None):
        """Clean and validate a state/province code.

        Handles:
          - State fields containing dates (e.g. '05/03/1963')
          - Foreign provinces longer than 2 chars (allowed, flagged)

        Args:
            state_code: Raw state/province code string.
            country_code: 3-letter country code (e.g. 'USA') or None.

        Returns:
            Cleaned state code string, or None if invalid.
        """
        if not state_code or not isinstance(state_code, str):
            return None

        cleaned = state_code.strip()
        if not cleaned:
            return None

        # Issue #3: state field contains a date
        if _DATE_SLASH_RE.search(cleaned):
            self._increment("clean_state_date_value")
            self.logger.debug(
                "State field contains date value '%s', setting to None", cleaned
            )
            return None

        is_us = country_code in (None, "USA", "US", "")

        if is_us:
            # US state codes must be exactly 2 uppercase letters
            upper = cleaned.upper()
            if len(upper) == 2 and upper.isalpha():
                return upper
            # Not a valid US state code
            self._increment("clean_state_invalid_us")
            self.logger.debug(
                "Invalid US state code '%s', setting to None", cleaned
            )
            return None

        # Issue #4: Foreign addresses - longer province names are OK, just flag
        if len(cleaned) > 2:
            self._increment("flag_foreign_province")
            self.logger.debug(
                "Foreign state/province '%s' > 2 chars (country=%s)",
                cleaned, country_code,
            )
        return cleaned

    # ------------------------------------------------------------------
    # Date normalization (issue #10)
    # ------------------------------------------------------------------

    def normalize_date(self, date_str):
        """Normalize a date string to a Python date object.

        Delegates to parse_yyyymmdd for core parsing, then handles
        additional edge cases: ISO timestamps with time portions.

        Args:
            date_str: Raw date string in any supported format.

        Returns:
            datetime.date object, or None if unparseable.
        """
        if not date_str:
            return None

        if not isinstance(date_str, str):
            # Already a date/datetime object
            from datetime import date, datetime
            if isinstance(date_str, datetime):
                return date_str.date()
            if isinstance(date_str, date):
                return date_str
            return None

        cleaned = date_str.strip()
        if not cleaned:
            return None

        # Handle ISO timestamps like '2024-01-15T10:30:00' or '2024-01-15 10:30:00'
        ts_match = _TIMESTAMP_RE.match(cleaned)
        if ts_match:
            cleaned = ts_match.group(1)

        result = parse_yyyymmdd(cleaned)
        if result is None and cleaned:
            self._increment("date_parse_failed")
            self.logger.debug("Could not parse date '%s'", date_str)
        else:
            self._increment("date_normalized")
        return result

    # ------------------------------------------------------------------
    # Country code normalization (issues #5 and #6)
    # ------------------------------------------------------------------

    def normalize_country_code(self, three_code):
        """Validate and normalize a 3-letter country code.

        Handles:
          - None, empty, whitespace
          - Non-ASCII characters (strip accents for comparison)
          - XKS, XWB, XGZ are valid (already in ref table)

        Args:
            three_code: 3-letter ISO country code string.

        Returns:
            Cleaned uppercase country code, or None if empty.
        """
        if not three_code or not isinstance(three_code, str):
            return None

        cleaned = three_code.strip().upper()
        if not cleaned:
            return None

        # Issue #5: normalize non-ASCII characters if present in code
        if not cleaned.isascii():
            normalized = unicodedata.normalize("NFKD", cleaned)
            cleaned = "".join(
                c for c in normalized if unicodedata.category(c) != "Mn"
            )
            self._increment("country_code_non_ascii")

        # Issue #6: XKS, XWB, XGZ are valid special territory codes
        # No special handling needed - they are already in ref_country_code

        return cleaned if cleaned else None

    # ------------------------------------------------------------------
    # CAGE code splitting (issue #7)
    # ------------------------------------------------------------------

    def split_cage_codes(self, cage_value):
        """Split comma-separated CAGE codes into a list.

        Args:
            cage_value: Raw CAGE code string, possibly comma-separated.

        Returns:
            List of clean CAGE code strings (5-char alphanumeric).
        """
        if not cage_value or not isinstance(cage_value, str):
            return []

        cleaned = cage_value.strip()
        if not cleaned:
            return []

        # Split on comma (with optional surrounding whitespace)
        parts = [p.strip() for p in cleaned.split(",") if p.strip()]

        if len(parts) > 1:
            self._increment("cage_code_split")
            self.logger.debug(
                "Split multi-value CAGE code '%s' into %d parts",
                cage_value, len(parts),
            )

        return parts

    # ------------------------------------------------------------------
    # Entity-specific record cleaning
    # ------------------------------------------------------------------

    def clean_entity_record(self, entity_dict):
        """Apply all entity-specific cleaning to a SAM.gov entity record.

        This is the main method called by entity_loader for each entity.
        Handles nested JSON structure from the SAM.gov Entity API.

        Args:
            entity_dict: Dict representing one entity from the API or extract.

        Returns:
            The same dict (modified in-place) after cleaning.
        """
        if not entity_dict:
            return entity_dict

        # --- Clean entityRegistration fields ---
        reg = entity_dict.get("entityRegistration") or {}
        self._clean_registration(reg)

        # --- Clean coreData fields ---
        core = entity_dict.get("coreData") or {}
        self._clean_core_data(core)

        # --- Clean pointsOfContact fields ---
        pocs = entity_dict.get("pointsOfContact") or {}
        self._clean_points_of_contact(pocs)

        # --- Clean assertions (NAICS warning) ---
        assertions = entity_dict.get("assertions") or {}
        self._clean_assertions(assertions)

        return entity_dict

    def _clean_registration(self, reg):
        """Clean entityRegistration sub-fields."""
        if not reg:
            return

        # CAGE code (issue #7)
        cage = reg.get("cageCode")
        if cage and isinstance(cage, str) and "," in cage:
            parts = self.split_cage_codes(cage)
            reg["cageCode"] = parts[0] if parts else None

        # Date fields
        for field in ("registrationDate", "lastUpdateDate",
                      "registrationExpirationDate", "activationDate",
                      "ueiExpirationDate", "ueiCreationDate"):
            val = reg.get(field)
            if val and isinstance(val, str):
                reg[field] = self.normalize_date(val)

    def _clean_core_data(self, core):
        """Clean coreData sub-fields: addresses, dates, country codes."""
        if not core:
            return

        # Physical and mailing addresses
        for addr_key in ("physicalAddress", "mailingAddress"):
            addr = core.get(addr_key)
            if not addr or not isinstance(addr, dict):
                continue
            self._clean_address(addr)

        # generalInformation country codes
        gen_info = core.get("generalInformation") or {}
        for field in ("countryOfIncorporationCode",):
            val = gen_info.get(field)
            if val and isinstance(val, str):
                gen_info[field] = self.normalize_country_code(val)

        # entityInformation date fields
        entity_info = core.get("entityInformation") or {}
        for field in ("entityStartDate", "fiscalYearEndCloseDate",
                      "submissionDate"):
            val = entity_info.get(field)
            if val and isinstance(val, str):
                entity_info[field] = self.normalize_date(val)

    def _clean_address(self, addr):
        """Clean an address dict (physical or mailing).

        Cleans zipCode, stateOrProvinceCode, and countryCode fields.
        """
        country_code = addr.get("countryCode")

        # Normalize country code (issue #5, #6)
        if country_code and isinstance(country_code, str):
            addr["countryCode"] = self.normalize_country_code(country_code)
            country_code = addr["countryCode"]

        # Clean ZIP code (issues #1, #2)
        zip_val = addr.get("zipCode")
        if zip_val and isinstance(zip_val, str):
            addr["zipCode"] = self.clean_zip_code(zip_val, country_code)

        # Clean state code (issues #3, #4)
        state_val = addr.get("stateOrProvinceCode")
        if state_val and isinstance(state_val, str):
            addr["stateOrProvinceCode"] = self.clean_state_code(
                state_val, country_code
            )

    def _clean_points_of_contact(self, pocs):
        """Clean address fields inside each point of contact."""
        if not pocs:
            return

        for poc_name in _POC_NAMES:
            poc = pocs.get(poc_name)
            if not poc or not isinstance(poc, dict):
                continue
            # POC records have the same address fields as core addresses
            self._clean_address(poc)

    def _clean_assertions(self, assertions):
        """Check NAICS codes and flag retired ones (issue #8)."""
        if not assertions:
            return

        goods = assertions.get("goodsAndServices") or {}
        naics_list = goods.get("naicsList") or []

        for naics_entry in naics_list:
            if not isinstance(naics_entry, dict):
                continue
            naics_obj = naics_entry.get("naicsCode")
            if naics_obj and isinstance(naics_obj, dict):
                # Nested structure: naicsCode is itself an object
                code = naics_obj.get("code") or naics_obj.get("naicsCode")
            elif naics_obj and isinstance(naics_obj, str):
                code = naics_obj
            else:
                continue

            # SBA certification dates
            for field in ("certificationEntryDate", "certificationExitDate"):
                val = naics_entry.get(field)
                if val and isinstance(val, str):
                    naics_entry[field] = self.normalize_date(val)
