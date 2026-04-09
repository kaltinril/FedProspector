"""Agency name to CGAC code resolution utility.

Resolves free-text agency names from different data sources to standardized
CGAC codes using the federal_organization table as the authoritative source.

Multi-pass matching strategy:
1. Exact match (case-insensitive) against federal_organization.fh_org_name
2. Variant normalization (comma inversion, abbreviation expansion)
3. Fuzzy match using rapidfuzz token_sort_ratio (threshold >= 90)
"""

import logging
import re

from db.connection import get_connection


logger = logging.getLogger("fed_prospector.etl.agency_resolver")

# Fuzzy match threshold — stricter than labor normalizer (85) because
# agency names are shorter and false positives are more costly.
_FUZZY_THRESHOLD = 90


class AgencyResolver:
    """Resolve agency names to CGAC codes using federal_organization table.

    Multi-pass matching:
    1. Direct exact match (case-insensitive) against fh_org_name
    2. Variant normalization ("X, DEPARTMENT OF" <-> "DEPARTMENT OF X",
       abbreviation expansion)
    3. Fuzzy match using rapidfuzz token_sort_ratio (threshold >= 90)
    """

    def __init__(self):
        # Lookup dicts built from federal_organization
        self._name_to_cgac = {}   # {UPPER(fh_org_name): cgac}
        self._code_to_cgac = {}   # {agency_code: cgac}

        # Dept-level names only — used for fuzzy matching to avoid false positives
        self._dept_names = {}     # {UPPER(fh_org_name): cgac}

        # Resolution cache — avoids re-resolving the same name
        self._cache = {}

        # Stats counters — reset on each bulk call
        self._stats = {"total": 0, "exact": 0, "variant": 0, "fuzzy": 0, "unresolved": 0}

        self._load_organizations()

    def _load_organizations(self):
        """Load federal_organization rows into memory lookup dicts."""
        conn = get_connection()
        cursor = conn.cursor(dictionary=True)
        try:
            cursor.execute(
                "SELECT fh_org_name, cgac, agency_code, fh_org_type "
                "FROM federal_organization "
                "WHERE cgac IS NOT NULL AND cgac != ''"
            )
            rows = cursor.fetchall()
        finally:
            cursor.close()
            conn.close()

        for row in rows:
            name = row["fh_org_name"]
            cgac = row["cgac"]
            agency_code = row["agency_code"]
            org_type = row["fh_org_type"]

            if name:
                upper_name = name.strip().upper()
                self._name_to_cgac[upper_name] = cgac

                if org_type == "Department/Ind. Agency":
                    self._dept_names[upper_name] = cgac

            if agency_code:
                self._code_to_cgac[agency_code.strip()] = cgac

        logger.info(
            "Loaded %d agency names (%d dept-level) from federal_organization",
            len(self._name_to_cgac),
            len(self._dept_names),
        )

    def _normalize(self, name: str) -> str:
        """Normalize agency name for matching."""
        s = name.strip().upper()
        s = re.sub(r"\s+", " ", s)  # collapse whitespace
        return s

    def _variants(self, name: str) -> list[str]:
        """Generate name variants for matching."""
        normalized = self._normalize(name)
        variants = [normalized]

        # Comma inversion: "STATE, DEPARTMENT OF" -> "DEPARTMENT OF STATE"
        if "," in normalized:
            parts = normalized.split(",", 1)
            variants.append(f"{parts[1].strip()} {parts[0].strip()}")

        # Reverse: "DEPARTMENT OF STATE" -> "STATE, DEPARTMENT OF"
        for prefix in ["DEPARTMENT OF ", "DEPT OF ", "OFFICE OF "]:
            if normalized.startswith(prefix):
                remainder = normalized[len(prefix):]
                variants.append(f"{remainder}, {prefix.strip()}")

        # Abbreviation expansion/contraction
        for v in list(variants):
            if "DEPARTMENT" in v:
                variants.append(v.replace("DEPARTMENT", "DEPT"))
            if "DEPT" in v and "DEPARTMENT" not in v:
                variants.append(v.replace("DEPT", "DEPARTMENT"))

        # Also handle "DEPT." -> "DEPARTMENT"
        for v in list(variants):
            if "DEPT." in v:
                variants.append(v.replace("DEPT.", "DEPARTMENT"))

        return variants

    def _resolve_single(self, name: str) -> tuple[str | None, str]:
        """Resolve a single name. Returns (cgac, match_type).

        match_type is one of: 'exact', 'variant', 'fuzzy', 'unresolved'.
        """
        if not name or not name.strip():
            return None, "unresolved"

        # Pass 1: exact match
        normalized = self._normalize(name)
        if normalized in self._name_to_cgac:
            return self._name_to_cgac[normalized], "exact"

        # Pass 2: variant matching
        for variant in self._variants(name):
            if variant in self._name_to_cgac:
                return self._name_to_cgac[variant], "variant"

        # Pass 3: fuzzy match against dept-level orgs only
        if self._dept_names:
            from rapidfuzz import fuzz

            best_score = 0
            best_cgac = None
            for dept_name, cgac in self._dept_names.items():
                score = fuzz.token_sort_ratio(normalized, dept_name)
                if score > best_score:
                    best_score = score
                    best_cgac = cgac

            if best_score >= _FUZZY_THRESHOLD:
                logger.debug(
                    "Fuzzy matched '%s' -> CGAC %s (score=%.1f)",
                    name, best_cgac, best_score,
                )
                return best_cgac, "fuzzy"

        logger.debug("Unresolved agency name: '%s'", name)
        return None, "unresolved"

    def resolve_agency(self, name: str) -> str | None:
        """Resolve an agency name to its CGAC code.

        Args:
            name: Agency name from any data source.

        Returns:
            CGAC code (e.g. "019") or None if unresolved.
        """
        if name in self._cache:
            return self._cache[name]

        cgac, match_type = self._resolve_single(name)
        self._cache[name] = cgac
        self._stats["total"] += 1
        self._stats[match_type] += 1
        return cgac

    def resolve_bulk(self, names: list[str]) -> dict[str, str | None]:
        """Resolve a batch of agency names to CGAC codes.

        Resets stats counters before processing. Results are cached so
        repeated names within the batch are only resolved once.

        Args:
            names: List of agency name strings.

        Returns:
            Dict mapping each input name to its CGAC code or None.
        """
        self._stats = {"total": 0, "exact": 0, "variant": 0, "fuzzy": 0, "unresolved": 0}
        result = {}
        for name in names:
            result[name] = self.resolve_agency(name)

        logger.info(
            "Bulk resolve: %d names — %d exact, %d variant, %d fuzzy, %d unresolved",
            self._stats["total"],
            self._stats["exact"],
            self._stats["variant"],
            self._stats["fuzzy"],
            self._stats["unresolved"],
        )
        return result

    def get_stats(self) -> dict:
        """Return resolution statistics.

        Returns:
            Dict with keys: total, exact, variant, fuzzy, unresolved.
        """
        return dict(self._stats)
