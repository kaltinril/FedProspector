"""Normalize GSA CALC+ labor categories to canonical categories.

Multi-pass matching strategy:
1. Exact match (case-insensitive) against canonical_labor_category
2. Pattern match using regex for common abbreviations and level mappings
3. Fuzzy match using rapidfuzz token_sort_ratio (threshold >= 85)

After normalization, refreshes labor_rate_summary with aggregated statistics.
"""

import csv
import logging
import re
from pathlib import Path

from db.connection import get_connection
from etl.load_manager import LoadManager


logger = logging.getLogger("fed_prospector.etl.labor_normalizer")

# Path to canonical categories CSV (relative to fed_prospector/)
_CSV_PATH = Path(__file__).parent.parent / "data" / "canonical_labor_categories.csv"

# Common abbreviation patterns for normalization before matching
_ABBREVIATION_PATTERNS = [
    (re.compile(r"\bSr\.?\b", re.IGNORECASE), "Senior"),
    (re.compile(r"\bJr\.?\b", re.IGNORECASE), "Junior"),
    (re.compile(r"\bEngr\.?\b", re.IGNORECASE), "Engineer"),
    (re.compile(r"\bMgr\.?\b", re.IGNORECASE), "Manager"),
    (re.compile(r"\bMgmt\.?\b", re.IGNORECASE), "Management"),
    (re.compile(r"\bAdmin\.?\b", re.IGNORECASE), "Administrative"),
    (re.compile(r"\bAsst\.?\b", re.IGNORECASE), "Assistant"),
    (re.compile(r"\bSpec\.?\b", re.IGNORECASE), "Specialist"),
    (re.compile(r"\bTech\.?\b", re.IGNORECASE), "Technician"),
    (re.compile(r"\bDev\.?\b", re.IGNORECASE), "Developer"),
    (re.compile(r"\bArch\.?\b", re.IGNORECASE), "Architect"),
    (re.compile(r"\bAnalst\.?\b", re.IGNORECASE), "Analyst"),
    (re.compile(r"\bSys\.?\b", re.IGNORECASE), "Systems"),
    (re.compile(r"\bSW\b", re.IGNORECASE), "Software"),
    (re.compile(r"\bHW\b", re.IGNORECASE), "Hardware"),
    (re.compile(r"\bDB\b", re.IGNORECASE), "Database"),
    (re.compile(r"\bPM\b", re.IGNORECASE), "Project Manager"),
    (re.compile(r"\bSME\b", re.IGNORECASE), "Subject Matter Expert"),
    (re.compile(r"\bISSO\b", re.IGNORECASE), "Information System Security Officer"),
    (re.compile(r"\bISSM\b", re.IGNORECASE), "Information System Security Manager"),
    (re.compile(r"\bCISO\b", re.IGNORECASE), "Chief Information Security Officer"),
    (re.compile(r"\bCIO\b", re.IGNORECASE), "Chief Information Officer"),
    (re.compile(r"\bCTO\b", re.IGNORECASE), "Chief Technology Officer"),
    (re.compile(r"\bQA\b", re.IGNORECASE), "Quality Assurance"),
    (re.compile(r"\bUI/UX\b", re.IGNORECASE), "UX Designer"),
    (re.compile(r"\bDevOps\b", re.IGNORECASE), "DevOps"),
    (re.compile(r"\bSRE\b", re.IGNORECASE), "Site Reliability Engineer"),
    (re.compile(r"\bDBA\b", re.IGNORECASE), "Database Administrator"),
    (re.compile(r"\bBI\b", re.IGNORECASE), "Business Intelligence"),
]

# Roman numeral / level to seniority mapping
# Order matters: check IV before III before II before I to avoid partial matches
_LEVEL_PATTERNS = [
    (re.compile(r"\b(?:Lvl|Level)\s*IV\b", re.IGNORECASE), "Principal"),
    (re.compile(r"\b(?:Lvl|Level)\s*III\b", re.IGNORECASE), "Senior"),
    (re.compile(r"\b(?:Lvl|Level)\s*II\b", re.IGNORECASE), ""),  # mid-level, no prefix
    (re.compile(r"\b(?:Lvl|Level)\s*I\b", re.IGNORECASE), "Junior"),
    # Standalone Roman numerals (without "Level" prefix) — IV/III/II are safe
    (re.compile(r"\bIV\b"), "Principal"),
    (re.compile(r"\bIII\b"), "Senior"),
    (re.compile(r"\bII\b"), ""),  # mid-level, no prefix
]

# Batch size for DB operations
_BATCH_SIZE = 500

# Fuzzy match threshold (0-100)
_FUZZY_THRESHOLD = 85


class LaborNormalizer:
    """Normalize labor categories from gsa_labor_rate to canonical categories."""

    def __init__(self, load_manager=None):
        self.load_manager = load_manager or LoadManager()
        self.logger = logger
        try:
            import rapidfuzz  # noqa: F401
            self._rapidfuzz_available = True
        except ImportError:
            self._rapidfuzz_available = False
            self.logger.warning(
                "rapidfuzz not installed — fuzzy matching disabled. "
                "Install with: pip install rapidfuzz"
            )

    # =================================================================
    # Public entry points
    # =================================================================

    def seed_canonical_categories(self):
        """Read canonical_labor_categories.csv and upsert into canonical_labor_category table.

        Returns:
            dict with insert/update counts.
        """
        self.logger.info("Seeding canonical labor categories from %s", _CSV_PATH)

        if not _CSV_PATH.exists():
            raise FileNotFoundError(f"Canonical categories CSV not found: {_CSV_PATH}")

        rows = []
        with open(_CSV_PATH, "r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        self.logger.info("Read %d canonical categories from CSV", len(rows))

        sql = (
            "INSERT INTO canonical_labor_category "
            "(canonical_name, category_group, onet_code, description) "
            "VALUES (%s, %s, %s, %s) AS new_row "
            "ON DUPLICATE KEY UPDATE "
            "category_group = new_row.category_group, "
            "onet_code = new_row.onet_code, "
            "description = new_row.description"
        )

        conn = get_connection()
        cursor = conn.cursor()
        try:
            batch = []
            for row in rows:
                batch.append((
                    row["canonical_name"].strip(),
                    row["category_group"].strip(),
                    row.get("onet_code", "").strip() or None,
                    row.get("description", "").strip() or None,
                ))

            cursor.executemany(sql, batch)
            conn.commit()
            affected = cursor.rowcount
            self.logger.info(
                "Seeded canonical categories: %d rows affected", affected,
            )
            return {"rows_affected": affected, "rows_read": len(rows)}
        finally:
            cursor.close()
            conn.close()

    def normalize(self):
        """Run full normalization pipeline.

        1. Seed canonical categories
        2. Load canonical names for matching
        3. Find unmapped labor categories from gsa_labor_rate
        4. Multi-pass matching: exact, pattern, fuzzy
        5. Insert mappings into labor_category_mapping

        Returns:
            dict with match statistics.
        """
        load_id = self.load_manager.start_load(
            source_system="LABOR_NORMALIZE",
            load_type="FULL",
            parameters={"method": "multi_pass"},
        )
        self.logger.info("Starting labor category normalization (load_id=%d)", load_id)

        try:
            # Step 1: Seed canonical categories
            self.seed_canonical_categories()

            # Step 2-3: Load canonical names and get unmapped categories
            # using a single shared connection
            conn = get_connection()
            try:
                canonicals = self._load_canonical_categories(conn)
                self.logger.info("Loaded %d canonical categories for matching", len(canonicals))

                unmapped = self._get_unmapped_categories(conn)
                self.logger.info("Found %d unmapped labor categories", len(unmapped))

                if not unmapped:
                    self.logger.info("All labor categories are already mapped")
                    self.load_manager.complete_load(
                        load_id, records_read=0, records_inserted=0,
                    )
                    return {"exact": 0, "pattern": 0, "fuzzy": 0, "unmapped": 0, "total": 0}

                # Build lookup structures
                canonical_by_name_lower = {
                    name.lower(): (cid, name) for cid, name in canonicals
                }
                canonical_list = [(cid, name) for cid, name in canonicals]

                # Step 4: Multi-pass matching
                stats = {"exact": 0, "pattern": 0, "fuzzy": 0, "unmapped": 0, "total": len(unmapped)}
                mappings = []

                for raw_cat in unmapped:
                    mapping = self._match_category(
                        raw_cat, canonical_by_name_lower, canonical_list,
                    )
                    mappings.append(mapping)

                    if mapping["match_method"] == "EXACT":
                        stats["exact"] += 1
                    elif mapping["match_method"] == "PATTERN":
                        stats["pattern"] += 1
                    elif mapping["match_method"] == "FUZZY":
                        stats["fuzzy"] += 1
                    else:
                        stats["unmapped"] += 1

                    if len(mappings) >= _BATCH_SIZE:
                        self._insert_mappings(conn, mappings)
                        mappings = []

                # Final partial batch
                if mappings:
                    self._insert_mappings(conn, mappings)

            finally:
                conn.close()

            self.logger.info(
                "Normalization complete: exact=%d pattern=%d fuzzy=%d unmapped=%d (total=%d)",
                stats["exact"], stats["pattern"], stats["fuzzy"],
                stats["unmapped"], stats["total"],
            )

            self.load_manager.complete_load(
                load_id,
                records_read=stats["total"],
                records_inserted=stats["exact"] + stats["pattern"] + stats["fuzzy"],
                records_unchanged=stats["unmapped"],
            )
            return stats

        except Exception as exc:
            self.load_manager.fail_load(load_id, str(exc))
            self.logger.exception("Labor normalization failed (load_id=%d)", load_id)
            raise

    def refresh_summary(self):
        """Refresh labor_rate_summary table with aggregated rate statistics.

        TRUNCATE + INSERT pattern for full refresh. Computes count, min, avg,
        max, p25, median, p75 per canonical category / worksite / education level.
        """
        self.logger.info("Refreshing labor_rate_summary table")

        load_id = self.load_manager.start_load(
            source_system="LABOR_SUMMARY",
            load_type="FULL",
            parameters={"method": "truncate_reload"},
        )

        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Truncate the summary table
            cursor.execute("TRUNCATE TABLE labor_rate_summary")
            conn.commit()

            # Get grouped rate data for percentile computation
            # We compute min/avg/max in SQL but need Python for percentiles
            cursor.execute("""
                SELECT
                    clc.id AS canonical_id,
                    clc.category_group,
                    glr.worksite,
                    glr.education_level,
                    glr.current_price
                FROM gsa_labor_rate glr
                JOIN labor_category_mapping lcm
                    ON glr.labor_category = lcm.raw_labor_category
                JOIN canonical_labor_category clc
                    ON lcm.canonical_id = clc.id
                WHERE lcm.match_method != 'UNMAPPED'
                    AND glr.current_price IS NOT NULL
                    AND glr.current_price > 0
                ORDER BY clc.id, glr.worksite, glr.education_level, glr.current_price
            """)

            rows = cursor.fetchall()
            self.logger.info("Fetched %d rate rows for summary computation", len(rows))

            if not rows:
                self.logger.warning("No mapped rates found for summary")
                self.load_manager.complete_load(
                    load_id, records_read=0, records_inserted=0,
                )
                return {"summary_rows": 0}

            # Group by (canonical_id, category_group, worksite, education_level)
            groups = {}
            for canonical_id, category_group, worksite, education_level, price in rows:
                key = (canonical_id, category_group, worksite, education_level)
                if key not in groups:
                    groups[key] = []
                groups[key].append(float(price))

            # Compute statistics and insert
            insert_sql = (
                "INSERT INTO labor_rate_summary "
                "(canonical_id, category_group, worksite, education_level, "
                "rate_count, min_rate, avg_rate, max_rate, p25_rate, median_rate, p75_rate) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            )

            batch = []
            for (canonical_id, category_group, worksite, edu_level), prices in groups.items():
                prices.sort()
                n = len(prices)
                batch.append((
                    canonical_id,
                    category_group,
                    worksite,
                    edu_level,
                    n,
                    round(prices[0], 2),
                    round(sum(prices) / n, 2),
                    round(prices[-1], 2),
                    round(self._percentile(prices, 25), 2),
                    round(self._percentile(prices, 50), 2),
                    round(self._percentile(prices, 75), 2),
                ))

                if len(batch) >= _BATCH_SIZE:
                    cursor.executemany(insert_sql, batch)
                    conn.commit()
                    batch = []

            if batch:
                cursor.executemany(insert_sql, batch)
                conn.commit()

            total_rows = len(groups)
            self.logger.info("Refreshed labor_rate_summary: %d rows", total_rows)

            self.load_manager.complete_load(
                load_id,
                records_read=len(rows),
                records_inserted=total_rows,
            )
            return {"summary_rows": total_rows}

        except Exception as exc:
            conn.rollback()
            self.load_manager.fail_load(load_id, str(exc))
            raise
        finally:
            cursor.close()
            conn.close()

    # =================================================================
    # Matching logic
    # =================================================================

    def _match_category(self, raw_category, canonical_by_name_lower, canonical_list):
        """Match a raw labor category string to a canonical category.

        Tries exact, pattern, then fuzzy matching in order.

        Args:
            raw_category: Raw labor category string from gsa_labor_rate.
            canonical_by_name_lower: Dict of lowercase canonical name -> (id, name).
            canonical_list: List of (id, name) tuples for fuzzy matching.

        Returns:
            dict with keys: raw_labor_category, canonical_id, match_method, confidence
        """
        # Pass 1: Exact match (case-insensitive)
        lower = raw_category.strip().lower()
        if lower in canonical_by_name_lower:
            cid, _ = canonical_by_name_lower[lower]
            return {
                "raw_labor_category": raw_category,
                "canonical_id": cid,
                "match_method": "EXACT",
                "confidence": 100.0,
            }

        # Pass 2: Pattern match — expand abbreviations + level mapping, then try exact match
        expanded = self._expand_abbreviations(raw_category)
        expanded = self._apply_level_mapping(expanded)
        expanded_lower = expanded.strip().lower()
        if expanded_lower != lower and expanded_lower in canonical_by_name_lower:
            cid, _ = canonical_by_name_lower[expanded_lower]
            return {
                "raw_labor_category": raw_category,
                "canonical_id": cid,
                "match_method": "PATTERN",
                "confidence": 95.0,
            }

        # Pass 3: Fuzzy match using rapidfuzz
        best_match = self._fuzzy_match(expanded, canonical_list)
        if best_match:
            return {
                "raw_labor_category": raw_category,
                "canonical_id": best_match["canonical_id"],
                "match_method": "FUZZY",
                "confidence": best_match["score"],
            }

        # No match found
        return {
            "raw_labor_category": raw_category,
            "canonical_id": None,
            "match_method": "UNMAPPED",
            "confidence": 0.0,
        }

    def _expand_abbreviations(self, text):
        """Expand common abbreviations in a labor category string.

        Args:
            text: Raw labor category string.

        Returns:
            str with abbreviations expanded.
        """
        result = text
        for pattern, replacement in _ABBREVIATION_PATTERNS:
            result = pattern.sub(replacement, result)
        # Clean up extra whitespace
        result = re.sub(r"\s+", " ", result).strip()
        return result

    def _apply_level_mapping(self, text):
        """Replace level/Roman numeral indicators with seniority prefixes.

        E.g., "Software Engineer III" -> "Senior Software Engineer"
             "Analyst Level II" -> "Analyst" (mid-level, no prefix)

        Args:
            text: Labor category string (after abbreviation expansion).

        Returns:
            str with level indicators replaced by seniority prefix.
        """
        for pattern, prefix in _LEVEL_PATTERNS:
            match = pattern.search(text)
            if match:
                # Remove the level indicator from the string
                text = pattern.sub("", text).strip()
                text = re.sub(r"\s+", " ", text).strip()
                # Prepend seniority prefix if non-empty
                if prefix:
                    text = f"{prefix} {text}"
                # Only apply the first matching pattern
                break
        return text

    def _fuzzy_match(self, text, canonical_list):
        """Find the best fuzzy match for a labor category string.

        Args:
            text: Expanded labor category string.
            canonical_list: List of (id, name) tuples.

        Returns:
            dict with canonical_id and score, or None if below threshold.
        """
        if not self._rapidfuzz_available:
            return None

        from rapidfuzz import process, fuzz

        # Build a mapping from canonical name to id for extractOne lookup
        name_to_id = {name: cid for cid, name in canonical_list}
        canonical_names = list(name_to_id.keys())

        result = process.extractOne(
            text, canonical_names,
            scorer=fuzz.token_sort_ratio,
            score_cutoff=_FUZZY_THRESHOLD,
        )

        if result is not None:
            matched_name, score, _index = result
            return {"canonical_id": name_to_id[matched_name], "score": round(score, 2)}

        return None

    # =================================================================
    # Database operations
    # =================================================================

    def _load_canonical_categories(self, conn):
        """Load all canonical categories from the database.

        Args:
            conn: Active DB connection.

        Returns:
            List of (id, canonical_name) tuples.
        """
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT id, canonical_name FROM canonical_labor_category "
                "ORDER BY id"
            )
            return cursor.fetchall()
        finally:
            cursor.close()

    def _get_unmapped_categories(self, conn):
        """Get distinct labor categories from gsa_labor_rate not yet in labor_category_mapping.

        Args:
            conn: Active DB connection.

        Returns:
            List of raw labor category strings.
        """
        cursor = conn.cursor()
        try:
            cursor.execute("""
                SELECT DISTINCT glr.labor_category
                FROM gsa_labor_rate glr
                LEFT JOIN labor_category_mapping lcm
                    ON glr.labor_category = lcm.raw_labor_category
                WHERE lcm.id IS NULL
                    AND glr.labor_category IS NOT NULL
                    AND glr.labor_category != ''
                ORDER BY glr.labor_category
            """)
            return [row[0] for row in cursor.fetchall()]
        finally:
            cursor.close()

    def _insert_mappings(self, conn, mappings):
        """Batch insert labor category mappings.

        Args:
            conn: Active DB connection.
            mappings: List of mapping dicts.
        """
        if not mappings:
            return

        sql = (
            "INSERT INTO labor_category_mapping "
            "(raw_labor_category, canonical_id, match_method, confidence) "
            "VALUES (%s, %s, %s, %s) AS new_row "
            "ON DUPLICATE KEY UPDATE "
            "canonical_id = new_row.canonical_id, "
            "match_method = new_row.match_method, "
            "confidence = new_row.confidence"
        )

        cursor = conn.cursor()
        try:
            rows = []
            for m in mappings:
                rows.append((
                    m["raw_labor_category"][:200],
                    m["canonical_id"],
                    m["match_method"],
                    m["confidence"],
                ))
            cursor.executemany(sql, rows)
            conn.commit()
            self.logger.debug("Inserted %d mappings", len(rows))
        finally:
            cursor.close()

    # =================================================================
    # Utility
    # =================================================================

    @staticmethod
    def _percentile(sorted_values, pct):
        """Compute percentile from a sorted list of values.

        Args:
            sorted_values: Already-sorted list of numeric values.
            pct: Percentile (0-100).

        Returns:
            float: Interpolated percentile value.
        """
        n = len(sorted_values)
        if n == 0:
            return 0.0
        if n == 1:
            return sorted_values[0]

        k = (pct / 100.0) * (n - 1)
        f = int(k)
        c = f + 1
        if c >= n:
            return sorted_values[-1]

        d = k - f
        return sorted_values[f] + d * (sorted_values[c] - sorted_values[f])
