"""Load reference data from CSV files in workdir into ref_* tables. (Phase 1 - Task 1.3, Phase 7 enrichment)"""

import csv
import logging
import re

import mysql.connector

from db.connection import get_connection
from config import settings


class ReferenceLoader:
    """Loads CSV reference data files into MySQL ref_* tables.

    Each load method truncates the target table first for idempotent reloads,
    then bulk-inserts rows using executemany.
    """

    BATCH_SIZE = 500

    # ------------------------------------------------------------------
    # Category and flag mappings for ref_business_type (Task 7.1)
    # ------------------------------------------------------------------

    BUSINESS_TYPE_CATEGORIES = {
        "Government": {"2R", "2F", "12", "3I", "CY", "NG"},
        "Ownership/Ethnicity": {"20", "OW", "FR", "QZ", "OY", "PI", "NB", "05", "XY", "8U", "1B", "1E", "1S"},
        "Woman-Owned": {"A2", "8W", "8E", "8C", "8D"},
        "Veteran": {"A5", "QF"},
        "Small Business": {"27", "1D", "A3", "HQ", "JX"},
        "Non-Profit/Foundation": {"A7", "A8", "2U", "BZ", "H2", "6D"},
        "Education": {"M8", "G6", "G7", "G8", "HB", "1A", "1R", "ZW", "GW", "OH", "HS", "QU", "G3", "G5"},
        "Organization Type": {"LJ", "XS", "MF", "2X", "HK", "QW"},
        "Local Government": {"C8", "C7", "ZR", "MG", "C6", "H6", "TW", "UD", "8B", "86", "KM", "T4", "FO", "TR"},
        "Healthcare": {"80", "FY"},
        "Other": {"G9"},
    }

    SOCIOECONOMIC_CODES = {
        "A2", "8W", "8E", "8C", "8D", "A5", "QF", "27", "23", "FR", "QZ",
        "OY", "PI", "NB", "OW", "HQ", "JX", "1E", "1S", "05", "XY", "8U",
        "1B", "A3", "A7",
    }

    SMALL_BUSINESS_CODES = {
        "8W", "8E", "8C", "8D", "27", "1D", "A3", "QF", "HQ", "JX", "1E", "1S",
    }

    # ------------------------------------------------------------------
    # NAICS hierarchy level mapping (Task 7.4)
    # ------------------------------------------------------------------

    NAICS_LEVEL_MAP = {
        2: (1, "Sector"),
        3: (2, "Subsector"),
        4: (3, "Industry Group"),
        5: (4, "NAICS Industry"),
        6: (5, "National Industry"),
    }

    def __init__(self):
        self.logger = logging.getLogger("fed_prospector.etl.reference_loader")

    # ------------------------------------------------------------------
    # Public orchestrator
    # ------------------------------------------------------------------

    def load_all(self):
        """Load all reference tables. Returns dict of table_name: row_count."""
        results = {}
        loaders = [
            ("ref_naics_footnote", self.load_footnotes),
            ("ref_naics_code", self.load_naics_codes),
            ("ref_sba_size_standard", self.load_size_standards),
            ("ref_psc_code", self.load_psc_codes),
            ("ref_country_code", self.load_country_codes),
            ("ref_state_code", self.load_state_codes),
            ("ref_fips_county", self.load_fips_counties),
            ("ref_business_type", self.load_business_types),
            ("ref_entity_structure", self.load_entity_structures),
            ("ref_set_aside_type", self.load_set_aside_types),
            ("ref_sba_type", self.load_sba_types),
        ]
        for table_name, loader in loaders:
            try:
                count = loader()
                results[table_name] = count
                self.logger.info("Loaded %s: %d rows", table_name, count)
            except (OSError, ValueError, KeyError, mysql.connector.Error) as e:
                self.logger.error("Failed to load %s: %s", table_name, e)
                results[table_name] = -1
        return results

    # ------------------------------------------------------------------
    # Helper: resolve category for a business type code
    # ------------------------------------------------------------------

    def _get_business_type_category(self, code):
        """Return the category name for a given business type code."""
        for category, codes in self.BUSINESS_TYPE_CATEGORIES.items():
            if code in codes:
                return category
        return None

    # ------------------------------------------------------------------
    # Helper: compute NAICS hierarchy fields
    # ------------------------------------------------------------------

    def _naics_hierarchy(self, code):
        """Return (code_level, level_name, parent_code) for a NAICS code."""
        # Strip any non-digit suffix (exception codes like '115310e1')
        digits_only = code.rstrip("abcdefghijklmnopqrstuvwxyz")
        code_len = len(digits_only)
        level_info = self.NAICS_LEVEL_MAP.get(code_len)
        if level_info is None:
            return (None, None, None)
        code_level, level_name = level_info
        parent_code = digits_only[:-1] if code_len > 2 else None
        return (code_level, level_name, parent_code)

    # ------------------------------------------------------------------
    # Individual loaders
    # ------------------------------------------------------------------

    def load_naics_codes(self):
        """Load 2022 and 2017 NAICS codes into ref_naics_code with hierarchy metadata."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            cursor.execute("TRUNCATE TABLE ref_naics_code")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            total = 0

            # --- 2022 codes (primary) ---
            file_2022 = settings.REF_DATA_DIR / "2-6 digit_2022_Codes.csv"
            rows = []
            with open(file_2022, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = (row.get("2022 NAICS US   Code") or "").strip()
                    title = (row.get("2022 NAICS US Title") or "").strip()
                    if not code:
                        self.logger.warning("Skipping NAICS 2022 record with empty code (title=%s)", title)
                        continue
                    code_level, level_name, parent_code = self._naics_hierarchy(code)
                    rows.append((code, title, code_level, level_name, parent_code, "2022", "Y"))

            sql = (
                "INSERT INTO ref_naics_code "
                "(naics_code, description, code_level, level_name, parent_code, "
                "year_version, is_active) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            )
            for batch_start in range(0, len(rows), self.BATCH_SIZE):
                batch = rows[batch_start : batch_start + self.BATCH_SIZE]
                cursor.executemany(sql, batch)
            total += len(rows)
            self.logger.info("Loaded %d NAICS 2022 codes", len(rows))

            # --- 2017 codes (INSERT IGNORE for overlapping codes) ---
            file_2017 = settings.REF_DATA_DIR / "6-digit_2017_Codes.csv"
            rows_2017 = []
            with open(file_2017, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = (row.get("2017 NAICS Code") or "").strip()
                    title = (row.get("2017 NAICS Title") or "").rstrip()
                    if not code:
                        self.logger.warning("Skipping NAICS 2017 record with empty code (title=%s)", title)
                        continue
                    code_level, level_name, parent_code = self._naics_hierarchy(code)
                    rows_2017.append((code, title, code_level, level_name, parent_code, "2017", "Y"))

            sql_ignore = (
                "INSERT IGNORE INTO ref_naics_code "
                "(naics_code, description, code_level, level_name, parent_code, "
                "year_version, is_active) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            )
            inserted_2017 = 0
            for batch_start in range(0, len(rows_2017), self.BATCH_SIZE):
                batch = rows_2017[batch_start : batch_start + self.BATCH_SIZE]
                cursor.executemany(sql_ignore, batch)
                inserted_2017 += cursor.rowcount
            self.logger.info(
                "Loaded %d new NAICS 2017 codes (%d total in file, overlaps ignored)",
                inserted_2017,
                len(rows_2017),
            )
            total += inserted_2017

            conn.commit()
            return total
        except (OSError, ValueError, KeyError, mysql.connector.Error) as e:
            self.logger.error("Failed to load NAICS codes: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_size_standards(self):
        """Load SBA size standards into ref_sba_size_standard."""
        file_path = settings.REF_DATA_DIR / "naics_size_standards.csv"
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            cursor.execute("TRUNCATE TABLE ref_sba_size_standard")
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")

            # Read existing NAICS codes for FK validation
            cursor.execute("SELECT naics_code FROM ref_naics_code")
            valid_naics = {r[0] for r in cursor.fetchall()}

            rows = []
            skipped = 0
            with open(file_path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    naics_code = (row.get("NAICS Codes") or "").strip()
                    if not naics_code:
                        self.logger.warning("Skipping size standard record with empty NAICS code")
                        continue
                    if naics_code not in valid_naics:
                        self.logger.warning(
                            "Skipping size standard - NAICS code %s not in ref_naics_code",
                            naics_code,
                        )
                        skipped += 1
                        continue
                    description = (row.get("NAICS Industry Description") or "").strip()
                    size_std = (row.get("Size_standard") or "").strip()
                    size_type = (row.get("TYPE") or "").strip() or None
                    footnote = (row.get("Footnote") or "").strip() or None
                    rows.append((
                        naics_code,
                        description,
                        size_std if size_std else None,
                        size_type,
                        footnote,
                    ))

            sql = (
                "INSERT INTO ref_sba_size_standard "
                "(naics_code, industry_description, size_standard, size_type, footnote_id) "
                "VALUES (%s, %s, %s, %s, %s)"
            )
            for batch_start in range(0, len(rows), self.BATCH_SIZE):
                batch = rows[batch_start : batch_start + self.BATCH_SIZE]
                cursor.executemany(sql, batch)

            conn.commit()
            if skipped:
                self.logger.warning("Skipped %d size standard rows (missing NAICS FK)", skipped)
            return len(rows)
        except (OSError, ValueError, KeyError, mysql.connector.Error) as e:
            self.logger.error("Failed to load SBA size standards: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_footnotes(self):
        """Load NAICS footnotes into ref_naics_footnote."""
        file_path = settings.REF_DATA_DIR / "footnotes.csv"
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE ref_naics_footnote")

            rows = []
            with open(file_path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    footnote_id = (row.get("ID") or "").strip()
                    section = (row.get("section") or "").strip()
                    description = (row.get("Description") or "").strip()
                    if not footnote_id:
                        self.logger.warning("Skipping footnote record with empty ID")
                        continue
                    rows.append((footnote_id, section, description))

            sql = (
                "INSERT INTO ref_naics_footnote "
                "(footnote_id, section, description) "
                "VALUES (%s, %s, %s)"
            )
            for batch_start in range(0, len(rows), self.BATCH_SIZE):
                batch = rows[batch_start : batch_start + self.BATCH_SIZE]
                cursor.executemany(sql, batch)

            conn.commit()
            return len(rows)
        except (OSError, ValueError, KeyError, mysql.connector.Error) as e:
            self.logger.error("Failed to load NAICS footnotes: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_psc_codes(self):
        """Load PSC codes into ref_psc_code."""
        file_path = (
            settings.WORKDIR / "local database" / "PSC April 2022 - PSC for 042022.csv"
        )
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE ref_psc_code")

            rows = []
            with open(file_path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    psc_code = (row.get("PSC CODE") or "").strip()
                    if not psc_code:
                        self.logger.warning("Skipping PSC record with empty code")
                        continue

                    psc_name = (row.get("PRODUCT AND SERVICE CODE NAME") or "").strip() or None

                    # Parse start_date (YYYY-MM-DD HH:MM:SS -> date only)
                    raw_start = (row.get("START DATE") or "").strip()
                    if raw_start:
                        start_date = raw_start[:10]  # YYYY-MM-DD portion
                    else:
                        start_date = "1900-01-01"

                    # Parse end_date
                    raw_end = (row.get("END DATE") or "").strip()
                    end_date = raw_end[:10] if raw_end else None

                    full_desc = (
                        row.get("PRODUCT AND SERVICE CODE FULL NAME (DESCRIPTION)") or ""
                    ).strip() or None
                    psc_includes = (
                        row.get("PRODUCT AND SERVICE CODE INCLUDES") or ""
                    ).strip() or None
                    psc_excludes = (
                        row.get("PRODUCT AND SERVICE CODE EXCLUDES") or ""
                    ).strip() or None
                    psc_notes = (
                        row.get("PRODUCT AND SERVICE CODE NOTES") or ""
                    ).strip() or None
                    parent_psc = (row.get("Parent PSC Code") or "").strip() or None

                    # Extract S or P from category column
                    raw_cat = (
                        row.get("PSC Category: Service (S)/Product (P)") or ""
                    ).strip()
                    category_type = raw_cat[0] if raw_cat and raw_cat[0] in ("S", "P") else None

                    l1_code = (row.get("Level 1 Category Code") or "").strip() or None
                    l1_cat = (row.get("Level 1 Category") or "").strip() or None
                    l2_code = (row.get("Level 2 Category Code") or "").strip() or None
                    l2_cat = (row.get("Level 2 Category") or "").strip() or None

                    rows.append((
                        psc_code, psc_name, start_date, end_date,
                        full_desc, psc_includes, psc_excludes, psc_notes,
                        parent_psc, category_type,
                        l1_code, l1_cat, l2_code, l2_cat,
                    ))

            sql = (
                "INSERT INTO ref_psc_code "
                "(psc_code, psc_name, start_date, end_date, "
                "full_description, psc_includes, psc_excludes, psc_notes, "
                "parent_psc_code, category_type, "
                "level1_category_code, level1_category, "
                "level2_category_code, level2_category) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
            )
            for batch_start in range(0, len(rows), self.BATCH_SIZE):
                batch = rows[batch_start : batch_start + self.BATCH_SIZE]
                cursor.executemany(sql, batch)

            conn.commit()
            return len(rows)
        except (OSError, ValueError, KeyError, mysql.connector.Error) as e:
            self.logger.error("Failed to load PSC codes: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_country_codes(self):
        """Load country codes into ref_country_code with SAM.gov territory enrichment."""
        iso_file = settings.WORKDIR / "country_codes_combined.csv"
        sam_file = settings.WORKDIR / "GG-Updated-Country-and-State-Lists - Countries.csv"
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE ref_country_code")

            # Regex to strip footnote markers like [b], [a][c], etc.
            footnote_re = re.compile(r"\[[\w]+\]")

            # Step 1: Load ISO 3166-1 data (primary source)
            iso_codes = set()
            rows = []
            with open(iso_file, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_name = (row.get("COUNTRY_NAME") or "").strip()
                    country_name = footnote_re.sub("", raw_name).strip()
                    two_code = (row.get("TWO_CODE") or "").strip()
                    three_code = (row.get("THREE_CODE") or "").strip()
                    numeric_code = (row.get("NUMERIC_CODE") or "").strip() or None
                    independent = (row.get("INDEPENDENT") or "").strip() or None
                    if not three_code:
                        self.logger.warning(
                            "Skipping country record with empty three_code (name=%s)", country_name
                        )
                        continue
                    iso_codes.add(three_code)
                    # is_iso_standard='Y', sam_gov_recognized='Y' (defaults)
                    rows.append((
                        country_name, two_code, three_code, numeric_code,
                        independent, "Y", "Y",
                    ))

            sql = (
                "INSERT INTO ref_country_code "
                "(country_name, two_code, three_code, numeric_code, "
                "independent, is_iso_standard, sam_gov_recognized) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            )
            for batch_start in range(0, len(rows), self.BATCH_SIZE):
                batch = rows[batch_start : batch_start + self.BATCH_SIZE]
                cursor.executemany(sql, batch)
            iso_count = len(rows)

            # Step 2: Insert special territories (XKS, XWB, XGZ) if not in ISO
            special_territories = [
                ("Kosovo", "XK", "XKS", None, None, "N", "Y"),
                ("West Bank", "XW", "XWB", None, None, "N", "Y"),
                ("Gaza Strip", "XG", "XGZ", None, None, "N", "Y"),
            ]
            sql_ignore = (
                "INSERT IGNORE INTO ref_country_code "
                "(country_name, two_code, three_code, numeric_code, "
                "independent, is_iso_standard, sam_gov_recognized) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)"
            )
            cursor.executemany(sql_ignore, special_territories)
            special_count = cursor.rowcount
            # Track which codes we have now
            loaded_codes = iso_codes | {"XKS", "XWB", "XGZ"}

            # Step 3: Merge SAM.gov territory codes not already loaded
            sam_extra = []
            with open(sam_file, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    three_code = (row.get("Country Code") or "").strip()
                    country_name = (row.get("Country") or "").strip()
                    if not three_code or three_code in loaded_codes:
                        continue
                    # SAM.gov-only codes: non-ISO, but SAM recognized
                    # two_code not available in this file, use first 2 chars
                    two_code = three_code[:2]
                    sam_extra.append((
                        country_name.title(), two_code, three_code, None,
                        None, "N", "Y",
                    ))
                    loaded_codes.add(three_code)

            if sam_extra:
                cursor.executemany(sql_ignore, sam_extra)
                self.logger.info(
                    "Added %d SAM.gov-specific territory codes (non-ISO)",
                    len(sam_extra),
                )

            conn.commit()
            total = iso_count + special_count + len(sam_extra)
            if special_count:
                self.logger.info(
                    "Added %d special territory codes (XKS, XWB, XGZ)", special_count
                )
            return total
        except (OSError, ValueError, KeyError, mysql.connector.Error) as e:
            self.logger.error("Failed to load country codes: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_state_codes(self):
        """Load state codes into ref_state_code."""
        file_path = settings.WORKDIR / "GG-Updated-Country-and-State-Lists - States.csv"
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE ref_state_code")

            rows = []
            with open(file_path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    state_code = (row.get("State Code") or "").strip()
                    state_name = (row.get("State") or "").strip()
                    if not state_code:
                        self.logger.warning(
                            "Skipping state record with empty code (name=%s)", state_name
                        )
                        continue
                    rows.append((state_code, state_name, "USA"))

            sql = (
                "INSERT INTO ref_state_code "
                "(state_code, state_name, country_code) "
                "VALUES (%s, %s, %s)"
            )
            for batch_start in range(0, len(rows), self.BATCH_SIZE):
                batch = rows[batch_start : batch_start + self.BATCH_SIZE]
                cursor.executemany(sql, batch)

            conn.commit()
            return len(rows)
        except (OSError, ValueError, KeyError, mysql.connector.Error) as e:
            self.logger.error("Failed to load state codes: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_fips_counties(self):
        """Load FIPS county codes into ref_fips_county.

        The state column is only populated for the first county of each state
        group, so we carry forward the last seen state value.
        """
        file_path = settings.WORKDIR / "local database" / "FIPS COUNTY CODES.csv"
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE ref_fips_county")

            # Regex to strip footnote markers like [a], [b], [c] from county names
            footnote_re = re.compile(r"\[[\w]+\]")

            rows = []
            current_state = None
            with open(file_path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_fips = (row.get("FIPS") or "").strip()
                    if not raw_fips:
                        self.logger.warning("Skipping FIPS record with empty code")
                        continue
                    fips_code = raw_fips.zfill(5)

                    raw_county = (row.get("County or equivalent") or "").strip()
                    county_name = footnote_re.sub("", raw_county).strip()

                    raw_state = (row.get("State or equivalent") or "").strip()
                    if raw_state:
                        current_state = raw_state
                    rows.append((fips_code, county_name, current_state))

            sql = (
                "INSERT INTO ref_fips_county "
                "(fips_code, county_name, state_name) "
                "VALUES (%s, %s, %s)"
            )
            for batch_start in range(0, len(rows), self.BATCH_SIZE):
                batch = rows[batch_start : batch_start + self.BATCH_SIZE]
                cursor.executemany(sql, batch)

            conn.commit()
            return len(rows)
        except (OSError, ValueError, KeyError, mysql.connector.Error) as e:
            self.logger.error("Failed to load FIPS counties: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_business_types(self):
        """Load business type codes into ref_business_type with category and flag enrichment."""
        file_path = settings.OLD_RESOURCES / "BusTypes.csv"
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE ref_business_type")

            rows = []
            with open(file_path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = (row.get("SamEntityType Name") or "").strip()
                    description = (row.get("Description") or "").strip()
                    classification = (row.get("Classification") or "").strip() or None
                    if not code:
                        self.logger.warning(
                            "Skipping business type record with empty code (desc=%s)", description
                        )
                        continue
                    category = self._get_business_type_category(code)
                    is_socioeconomic = "Y" if code in self.SOCIOECONOMIC_CODES else "N"
                    is_small_business = "Y" if code in self.SMALL_BUSINESS_CODES else "N"
                    rows.append((
                        code, description, classification,
                        category, is_socioeconomic, is_small_business,
                    ))

            sql = (
                "INSERT INTO ref_business_type "
                "(business_type_code, description, classification, "
                "category, is_socioeconomic, is_small_business_related) "
                "VALUES (%s, %s, %s, %s, %s, %s)"
            )
            for batch_start in range(0, len(rows), self.BATCH_SIZE):
                batch = rows[batch_start : batch_start + self.BATCH_SIZE]
                cursor.executemany(sql, batch)

            conn.commit()
            return len(rows)
        except (OSError, ValueError, KeyError, mysql.connector.Error) as e:
            self.logger.error("Failed to load business types: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_entity_structures(self):
        """Load entity structure codes into ref_entity_structure.

        Seed data from SAM.gov documentation and database discovery (15 codes).
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE ref_entity_structure")

            seed_data = [
                ("2J", "Corporate Entity (Not Tax Exempt)"),
                ("2K", "Corporate Entity (Tax Exempt)"),
                ("2L", "Partnership or Limited Liability Partnership"),
                ("2A", "U.S. Government Entity"),
                ("8H", "Limited Liability Company (LLC)"),
                ("CY", "Country"),
                ("X6", "International Organization"),
                ("ZZ", "Other"),
                ("2U", "Sole Proprietorship"),
                ("2V", "Municipality"),
                ("2W", "County"),
                ("2X", "Township"),
                ("2R", "Joint Venture"),
                ("2F", "Business or Organization"),
                ("2B", "Indian Tribe (Federally Recognized)"),
            ]

            sql = (
                "INSERT INTO ref_entity_structure "
                "(structure_code, description) "
                "VALUES (%s, %s)"
            )
            cursor.executemany(sql, seed_data)

            conn.commit()
            return len(seed_data)
        except mysql.connector.Error as e:
            self.logger.error("Failed to load entity structures: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_set_aside_types(self):
        """Load set-aside types from CSV into ref_set_aside_type.

        Replaces the previous seed_set_aside_types() hardcoded approach
        with a CSV-driven load supporting category enrichment.
        """
        file_path = settings.REF_DATA_DIR / "set_aside_types.csv"
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE ref_set_aside_type")

            rows = []
            with open(file_path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = (row.get("set_aside_code") or "").strip()
                    description = (row.get("description") or "").strip()
                    is_sb = (row.get("is_small_business") or "Y").strip()
                    category = (row.get("category") or "").strip() or None
                    if not code:
                        self.logger.warning(
                            "Skipping set-aside type record with empty code (desc=%s)", description
                        )
                        continue
                    rows.append((code, description, is_sb, category))

            sql = (
                "INSERT INTO ref_set_aside_type "
                "(set_aside_code, description, is_small_business, category) "
                "VALUES (%s, %s, %s, %s)"
            )
            cursor.executemany(sql, rows)

            conn.commit()
            return len(rows)
        except (OSError, ValueError, KeyError, mysql.connector.Error) as e:
            self.logger.error("Failed to load set-aside types: %s", e)
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    # Keep old name as alias for backward compatibility with CLI
    seed_set_aside_types = load_set_aside_types

    def load_sba_types(self):
        """Load SBA certification type codes into ref_sba_type.

        Seed data from SAM.gov documentation and database discovery (7 codes).
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE ref_sba_type")

            seed_data = [
                ("A4", "8(a) Program Participant (Disadvantaged)", "8(a)"),
                ("A6", "8(a) Joint Venture", "8(a)"),
                ("XX", "HUBZone Certified", "HUBZone"),
                ("27", "WOSB Program Participant", "WOSB"),
                ("A2", "EDWOSB Program Participant", "EDWOSB"),
                ("JT", "SBA Certified Small Disadvantaged Business", "SDB"),
                ("QF", "Community Development Corporation (CDC)", "CDC"),
            ]

            sql = (
                "INSERT INTO ref_sba_type "
                "(sba_type_code, description, program_name) "
                "VALUES (%s, %s, %s)"
            )
            cursor.executemany(sql, seed_data)

            conn.commit()
            return len(seed_data)
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()
