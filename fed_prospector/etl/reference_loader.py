"""Load reference data from CSV files in workdir into ref_* tables. (Phase 1 - Task 1.3)"""

import csv
import logging
import re

from db.connection import get_connection
from config import settings


class ReferenceLoader:
    """Loads CSV reference data files into MySQL ref_* tables.

    Each load method truncates the target table first for idempotent reloads,
    then bulk-inserts rows using executemany.
    """

    BATCH_SIZE = 500

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
            ("ref_set_aside_type", self.seed_set_aside_types),
        ]
        for table_name, loader in loaders:
            try:
                count = loader()
                results[table_name] = count
                self.logger.info("Loaded %s: %d rows", table_name, count)
            except Exception:
                self.logger.exception("Failed to load %s", table_name)
                results[table_name] = -1
        return results

    # ------------------------------------------------------------------
    # Individual loaders
    # ------------------------------------------------------------------

    def load_naics_codes(self):
        """Load 2022 and 2017 NAICS codes into ref_naics_code."""
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
                        continue
                    rows.append((code, title, "2022", "Y"))

            sql = (
                "INSERT INTO ref_naics_code "
                "(naics_code, description, year_version, is_active) "
                "VALUES (%s, %s, %s, %s)"
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
                        continue
                    rows_2017.append((code, title, "2017", "Y"))

            sql_ignore = (
                "INSERT IGNORE INTO ref_naics_code "
                "(naics_code, description, year_version, is_active) "
                "VALUES (%s, %s, %s, %s)"
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
        except Exception:
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
        except Exception:
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
        except Exception:
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
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_country_codes(self):
        """Load country codes into ref_country_code."""
        file_path = settings.WORKDIR / "country_codes_combined.csv"
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE ref_country_code")

            # Regex to strip footnote markers like [b], [a][c], etc.
            footnote_re = re.compile(r"\[[\w]+\]")

            rows = []
            with open(file_path, encoding="utf-8-sig", newline="") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    raw_name = (row.get("COUNTRY_NAME") or "").strip()
                    country_name = footnote_re.sub("", raw_name).strip()
                    two_code = (row.get("TWO_CODE") or "").strip()
                    three_code = (row.get("THREE_CODE") or "").strip()
                    numeric_code = (row.get("NUMERIC_CODE") or "").strip() or None
                    independent = (row.get("INDEPENDENT") or "").strip() or None
                    if not three_code:
                        continue
                    rows.append((
                        country_name, two_code, three_code, numeric_code, independent,
                    ))

            sql = (
                "INSERT INTO ref_country_code "
                "(country_name, two_code, three_code, numeric_code, independent) "
                "VALUES (%s, %s, %s, %s, %s)"
            )
            for batch_start in range(0, len(rows), self.BATCH_SIZE):
                batch = rows[batch_start : batch_start + self.BATCH_SIZE]
                cursor.executemany(sql, batch)

            # Insert missing special territories
            special_territories = [
                ("Kosovo", "XK", "XKS", None, None),
                ("West Bank", "XW", "XWB", None, None),
                ("Gaza Strip", "XG", "XGZ", None, None),
            ]
            sql_ignore = (
                "INSERT IGNORE INTO ref_country_code "
                "(country_name, two_code, three_code, numeric_code, independent) "
                "VALUES (%s, %s, %s, %s, %s)"
            )
            cursor.executemany(sql_ignore, special_territories)
            extra = cursor.rowcount

            conn.commit()
            total = len(rows) + extra
            if extra:
                self.logger.info(
                    "Added %d special territory codes (XKS, XWB, XGZ)", extra
                )
            return total
        except Exception:
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
        except Exception:
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
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def load_business_types(self):
        """Load business type codes into ref_business_type."""
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
                        continue
                    rows.append((code, description, classification))

            sql = (
                "INSERT INTO ref_business_type "
                "(business_type_code, description, classification) "
                "VALUES (%s, %s, %s)"
            )
            for batch_start in range(0, len(rows), self.BATCH_SIZE):
                batch = rows[batch_start : batch_start + self.BATCH_SIZE]
                cursor.executemany(sql, batch)

            conn.commit()
            return len(rows)
        except Exception:
            conn.rollback()
            raise
        finally:
            cursor.close()
            conn.close()

    def seed_set_aside_types(self):
        """Insert hardcoded set-aside type seed data into ref_set_aside_type."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute("TRUNCATE TABLE ref_set_aside_type")

            seed_data = [
                ("WOSB", "Women-Owned Small Business Program Set-Aside", "Y"),
                ("WOSBSS", "WOSB Program Sole Source", "Y"),
                ("EDWOSB", "Economically Disadvantaged WOSB Set-Aside", "Y"),
                ("EDWOSBSS", "EDWOSB Program Sole Source", "Y"),
                ("8A", "8(a) Set-Aside", "Y"),
                ("8AN", "8(a) Sole Source", "Y"),
                ("SBA", "Total Small Business Set-Aside", "Y"),
                ("SBP", "Partial Small Business Set-Aside", "Y"),
                ("HZC", "HUBZone Set-Aside", "Y"),
                ("HZS", "HUBZone Sole Source", "Y"),
                ("SDVOSBC", "Service-Disabled Veteran-Owned SB Set-Aside", "Y"),
                ("SDVOSBS", "SDVOSB Sole Source", "Y"),
                ("VSA", "Veteran-Owned Small Business Set-Aside", "Y"),
                ("VSB", "Veteran-Owned Small Business Sole Source", "Y"),
            ]

            sql = (
                "INSERT INTO ref_set_aside_type "
                "(set_aside_code, description, is_small_business) "
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
