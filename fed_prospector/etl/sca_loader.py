"""Load SCA wage determinations from SAM.gov into sca_wage_determination + sca_wage_rate.

Downloads WD text files via the SCAWDClient, parses fixed-width DOL format,
and upserts into the database with SHA-256 change detection.

CLI: python main.py load sca [--full-refresh] [--wd-number WD]
"""

import hashlib
import logging
import re
from datetime import datetime
from decimal import Decimal, InvalidOperation

from db.connection import get_connection
from etl.change_detector import ChangeDetector
from etl.load_manager import LoadManager
from utils.hashing import compute_record_hash

logger = logging.getLogger("fed_prospector.etl.sca_loader")

# Fields used for change detection hashing
WD_HASH_FIELDS = [
    "wd_number", "revision", "area_name", "state_code", "county_name",
    "effective_date", "status", "title",
]
RATE_HASH_FIELDS = [
    "occupation_code", "occupation_title", "hourly_rate",
    "health_welfare", "vacation", "holiday",
]

# US state abbreviations for validation
_STATE_ABBREVS = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR",
    "CALIFORNIA": "CA", "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE",
    "DISTRICT OF COLUMBIA": "DC", "FLORIDA": "FL", "GEORGIA": "GA", "HAWAII": "HI",
    "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME",
    "MARYLAND": "MD", "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN",
    "MISSISSIPPI": "MS", "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE",
    "NEVADA": "NV", "NEW HAMPSHIRE": "NH", "NEW JERSEY": "NJ", "NEW MEXICO": "NM",
    "NEW YORK": "NY", "NORTH CAROLINA": "NC", "NORTH DAKOTA": "ND", "OHIO": "OH",
    "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA", "RHODE ISLAND": "RI",
    "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN", "TEXAS": "TX",
    "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
    "PUERTO RICO": "PR", "GUAM": "GU", "VIRGIN ISLANDS": "VI",
    "AMERICAN SAMOA": "AS", "NORTHERN MARIANA ISLANDS": "MP",
}


class SCALoader:
    """Load SCA wage determinations from SAM.gov."""

    def __init__(self, load_manager=None, change_detector=None):
        self.load_manager = load_manager or LoadManager()
        self.change_detector = change_detector or ChangeDetector()
        self.logger = logger

    def load(self, client, full_refresh=False, single_wd=None):
        """Main entry point for SCA wage determination loading.

        Args:
            client: SCAWDClient instance.
            full_refresh: If True, re-download all WDs regardless of existing data.
            single_wd: If set, load only this WD number (for testing).

        Returns:
            dict with load statistics.
        """
        load_type = "FULL" if full_refresh else "INCREMENTAL"
        load_id = self.load_manager.start_load(
            source_system="SCA_WD",
            load_type=load_type,
            parameters={"full_refresh": full_refresh, "single_wd": single_wd},
        )
        self.logger.info("Starting SCA WD load (load_id=%d, type=%s)", load_id, load_type)

        stats = {
            "records_read": 0,
            "records_inserted": 0,
            "records_updated": 0,
            "records_unchanged": 0,
            "records_errored": 0,
            "wds_processed": 0,
            "rates_inserted": 0,
            "rates_updated": 0,
        }

        try:
            # Step 1: Get list of WD numbers + known revisions
            # known_revisions: {wd_number: revision} from reference file or DB
            known_revisions = {}
            if single_wd:
                wd_numbers = [single_wd]
                self.logger.info("Single WD mode: %s", single_wd)
            else:
                # Primary source: reference file (data/sca_active_wds.tsv)
                active_wds = client.load_active_wd_list()
                if active_wds:
                    wd_numbers = [w["wd_number"] for w in active_wds]
                    known_revisions = {w["wd_number"]: w["revision"] for w in active_wds}
                    self.logger.info(
                        "Loaded %d WDs from reference file (revisions known)",
                        len(wd_numbers),
                    )
                else:
                    # No reference file — use DB as source (incremental check for new revisions)
                    db_wds = self._get_existing_revisions()
                    if db_wds:
                        wd_numbers = sorted(db_wds.keys())
                        self.logger.info(
                            "No reference file found. Using %d WDs from database, "
                            "will check each for new revisions.",
                            len(wd_numbers),
                        )
                    else:
                        self.logger.error(
                            "No reference file and no WDs in database. "
                            "Run: python main.py update sca-list --file <path> first."
                        )
                        raise RuntimeError("No WD source available. See 'update sca-list --help'.")

            # Step 2: Load existing hashes for change detection
            existing_wd_hashes = {}
            existing_revisions = {}
            if not full_refresh:
                existing_wd_hashes = self.change_detector.get_existing_hashes(
                    "sca_wage_determination", "wd_number"
                )
                existing_revisions = self._get_existing_revisions()
                self.logger.info(
                    "Loaded %d existing WD hashes, %d existing revisions",
                    len(existing_wd_hashes), len(existing_revisions),
                )

            # Step 3: Process each WD number
            for i, wd_number in enumerate(wd_numbers):
                if (i + 1) % 50 == 0 or i == 0:
                    self.logger.info(
                        "Processing WD %d/%d: %s", i + 1, len(wd_numbers), wd_number
                    )

                try:
                    stats["records_read"] += 1

                    # If we know the revision from the reference file, download directly
                    ref_rev = known_revisions.get(wd_number)
                    if ref_rev and not full_refresh:
                        db_rev = existing_revisions.get(wd_number)
                        if db_rev and db_rev >= ref_rev:
                            # Already have this revision — skip
                            stats["records_unchanged"] += 1
                            stats["wds_processed"] += 1
                            continue
                        # Download the known revision directly (no probing)
                        text, status = client.download_wd(wd_number, ref_rev)
                        revision = ref_rev if text else -1
                    else:
                        # Probe for latest revision (fallback / full-refresh)
                        start_rev = existing_revisions.get(wd_number, 1) if not full_refresh else 1
                        text, revision = client.find_latest_revision(wd_number, start_revision=start_rev)

                    if text is None or revision < 0:
                        self.logger.debug("WD %s: no valid revision found", wd_number)
                        stats["records_errored"] += 1
                        continue

                    # Stage raw text
                    self._stage_raw(load_id, wd_number, revision, text)

                    # Parse the WD text
                    parsed = self._parse_wd_text(text)
                    if not parsed:
                        self.logger.warning("WD %s rev %d: parse returned empty", wd_number, revision)
                        stats["records_errored"] += 1
                        continue

                    # Override with known values
                    parsed["wd_number"] = wd_number
                    parsed["revision"] = revision

                    # Normalize and upsert determination
                    det = self._normalize_determination(parsed)
                    det["wd_type"] = "STANDARD" if wd_number.startswith("2015-") else "NON_STANDARD"
                    det_hash = compute_record_hash(det, WD_HASH_FIELDS)

                    if not full_refresh and existing_wd_hashes.get(wd_number) == det_hash:
                        stats["records_unchanged"] += 1
                    else:
                        wd_id = self._upsert_determination(det, det_hash, load_id)
                        if wd_id:
                            if wd_number in existing_wd_hashes:
                                stats["records_updated"] += 1
                            else:
                                stats["records_inserted"] += 1

                            # Normalize and upsert rates
                            rates = self._normalize_rates(parsed, wd_id)
                            r_ins, r_upd = self._upsert_rates(rates, load_id)
                            stats["rates_inserted"] += r_ins
                            stats["rates_updated"] += r_upd
                        else:
                            stats["records_errored"] += 1

                    stats["wds_processed"] += 1

                except Exception as exc:
                    stats["records_errored"] += 1
                    self.logger.warning("Error processing WD %s: %s", wd_number, exc)
                    self.load_manager.log_record_error(
                        load_id, wd_number, "PARSE_ERROR", str(exc)
                    )

            # Step 4: Mark older revisions as not current
            self._update_is_current()

            # Step 5: Normalize SCA occupation titles → canonical categories
            if stats["rates_inserted"] > 0 or stats["rates_updated"] > 0:
                try:
                    from etl.labor_normalizer import LaborNormalizer
                    normalizer = LaborNormalizer()
                    norm_stats = normalizer.normalize_sca()
                    self.logger.info(
                        "SCA occupation mapping: %d mapped (%d exact, %d fuzzy, %d unmapped)",
                        norm_stats.get("mapped", 0),
                        norm_stats.get("exact", 0),
                        norm_stats.get("fuzzy", 0),
                        norm_stats.get("unmapped", 0),
                    )
                except Exception as exc:
                    self.logger.warning("SCA occupation mapping failed (non-fatal): %s", exc)

            self.load_manager.complete_load(
                load_id,
                records_read=stats["records_read"],
                records_inserted=stats["records_inserted"],
                records_updated=stats["records_updated"],
                records_unchanged=stats["records_unchanged"],
                records_errored=stats["records_errored"],
            )
            self.logger.info("SCA WD load complete (load_id=%d): %s", load_id, stats)
            return stats

        except Exception as exc:
            self.load_manager.fail_load(load_id, str(exc))
            self.logger.exception("SCA WD load failed (load_id=%d)", load_id)
            raise

    # ------------------------------------------------------------------
    # Text parsing
    # ------------------------------------------------------------------

    def _parse_wd_text(self, text: str) -> dict | None:
        """Parse a DOL wage determination fixed-width text file.

        Returns a dict with:
            wd_number, revision, effective_date, state, area_name,
            occupations: list of {occupation_code, occupation_title, hourly_rate}
            health_welfare, vacation, holiday (fringe benefit rates)
        """
        if not text or len(text) < 100:
            return None

        # Strip surrounding quotes — SAM.gov wraps the response in double quotes
        text = text.strip()
        if text.startswith('"') and text.endswith('"'):
            text = text[1:-1]

        result = {
            "wd_number": None,
            "revision": None,
            "effective_date": None,
            "state": None,
            "state_code": None,
            "area_name": None,
            "title": None,
            "occupations": [],
            "health_welfare": None,
            "vacation": None,
            "holiday": None,
            "eo_minimum_wage": None,
        }

        lines = text.splitlines()

        # === Extract metadata from header section ===
        for i, line in enumerate(lines):
            stripped = line.strip()
            upper = stripped.upper()

            # WD Number: "Wage Determination No: 2015-4001" or "Wage Determination No.: 2015-4001"
            if "WAGE DETERMINATION NO" in upper:
                match = re.search(r'(\d{4}-\d{4,5})', stripped)
                if match:
                    result["wd_number"] = match.group(1)

            # Revision: "Revision No: 32" or "Revision No.: 32"
            elif "REVISION NO" in upper:
                match = re.search(r'(\d+)', stripped)
                if match:
                    result["revision"] = int(match.group(1))

            # Date of Last Revision: "Date Of Last Revision: 12/22/2024"
            elif "DATE OF LAST REVISION" in upper or "DATE OF REVISION" in upper:
                match = re.search(r'(\d{1,2}/\d{1,2}/\d{4})', stripped)
                if match:
                    try:
                        result["effective_date"] = datetime.strptime(
                            match.group(1), "%m/%d/%Y"
                        ).strftime("%Y-%m-%d")
                    except ValueError:
                        pass

            # State: "State: Maine" or "States: Maine, New Hampshire"
            elif re.match(r'^STATES?\s*:', upper):
                state_text = re.sub(r'^States?\s*:\s*', '', stripped, flags=re.IGNORECASE).strip()
                result["state"] = state_text
                # Handle comma-separated states — use first one for state_code
                first_state = state_text.split(",")[0].strip().upper()
                if first_state in _STATE_ABBREVS:
                    result["state_code"] = _STATE_ABBREVS[first_state]
                elif len(first_state) == 2 and first_state.isalpha():
                    result["state_code"] = first_state

            # Area: "Area: Penobscot County" or multi-line
            # Continuation lines may not be indented (e.g., multi-state WDs)
            elif re.match(r'^AREA\s*:', upper):
                area_text = re.sub(r'^Area\s*:\s*', '', stripped, flags=re.IGNORECASE).strip()
                j = i + 1
                while j < len(lines):
                    next_line = lines[j].strip()
                    # Stop on blank line, separator, or known section header
                    if not next_line or re.match(r'^(OCCUPATION|_{4,}|-{4,}|\*\*|Fringe)', next_line, re.IGNORECASE):
                        break
                    area_text += " " + next_line
                    j += 1
                result["area_name"] = area_text.strip()

        # Build title from state + area
        if result["state"] and result["area_name"]:
            result["title"] = f"{result['state']} - {result['area_name']}"
        elif result["area_name"]:
            result["title"] = result["area_name"]

        # === Extract occupation rates ===
        # Look for lines matching: NNNNN - Title    $XX.XX
        # Occupation codes are typically 5-digit (e.g. 01011)
        occ_pattern = re.compile(
            r'^\s*(\d{5})\s*-\s*(.+?)\s{2,}'  # code - title (2+ spaces separate title from rate)
            r'\$?\s*([\d,]+\.\d{2})\s*$'        # optional $ + XX.XX rate at end of line
        )
        # Alternate pattern with ** or footnote markers
        occ_pattern_note = re.compile(
            r'^\s*(\d{5})\s*-\s*(.+?)\s+'
            r'(?:\*+\s*)?'                    # optional asterisks
            r'(?:see note|varies|negotiated)',  # non-numeric rate
            re.IGNORECASE
        )

        in_occupation_section = False
        for line in lines:
            stripped = line.strip()
            upper = stripped.upper()

            # Detect start of occupation section
            if "OCCUPATION CODE" in upper and ("TITLE" in upper or "RATE" in upper):
                in_occupation_section = True
                continue

            # Detect end of occupation section (fringe benefits section)
            if in_occupation_section and (
                upper.startswith("__") or upper.startswith("--")
                or "HEALTH & WELFARE" in upper or "HEALTH AND WELFARE" in upper
                or "FRINGE BENEFITS" in upper
                or "THE APPLICABLE" in upper
            ):
                in_occupation_section = False
                # Don't break — still need fringe benefits parsing below

            if in_occupation_section or occ_pattern.search(stripped):
                match = occ_pattern.search(stripped)
                if match:
                    code = match.group(1)
                    title = match.group(2).strip().rstrip("-").strip()
                    rate_str = match.group(3).replace(",", "")
                    try:
                        rate = float(rate_str)
                    except ValueError:
                        rate = None
                    result["occupations"].append({
                        "occupation_code": code,
                        "occupation_title": title,
                        "hourly_rate": rate,
                    })
                else:
                    # Check for "see note" type entries
                    note_match = occ_pattern_note.search(stripped)
                    if note_match:
                        result["occupations"].append({
                            "occupation_code": note_match.group(1),
                            "occupation_title": note_match.group(2).strip().rstrip("-").strip(),
                            "hourly_rate": None,
                        })

            # === Extract fringe benefits ===
            # "HEALTH & WELFARE: $5.36 per hour" or "HEALTH & WELFARE: $4.60/hour"
            if "HEALTH" in upper and ("WELFARE" in upper or "H&W" in upper):
                hw_match = re.search(r'\$\s*([\d,]+\.\d{2})', stripped)
                if hw_match:
                    try:
                        result["health_welfare"] = float(hw_match.group(1).replace(",", ""))
                    except ValueError:
                        pass

            # Vacation rate — often stated as weeks, but sometimes a dollar amount
            if upper.startswith("VACATION") and ":" in stripped:
                vac_match = re.search(r'\$\s*([\d,]+\.\d{2})', stripped)
                if vac_match:
                    try:
                        result["vacation"] = float(vac_match.group(1).replace(",", ""))
                    except ValueError:
                        pass

            # Holiday rate
            if upper.startswith("HOLIDAY") and ":" in stripped:
                hol_match = re.search(r'\$\s*([\d,]+\.\d{2})', stripped)
                if hol_match:
                    try:
                        result["holiday"] = float(hol_match.group(1).replace(",", ""))
                    except ValueError:
                        pass

            # Executive Order minimum wage line
            if "EXECUTIVE ORDER" in upper and "MINIMUM WAGE" in upper:
                eo_match = re.search(r'\$\s*([\d,]+\.\d{2})', stripped)
                if eo_match:
                    try:
                        result["eo_minimum_wage"] = float(eo_match.group(1).replace(",", ""))
                    except ValueError:
                        pass

        return result

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def _normalize_determination(self, parsed: dict) -> dict:
        """Normalize parsed WD data for sca_wage_determination table."""
        area = parsed.get("area_name") or ""
        county = None
        is_statewide = 0

        # Extract county/parish/borough/municipio names from area description
        # Counties (most states), Parishes (Louisiana), Boroughs (Alaska),
        # Municipios (Puerto Rico)
        counties_of = re.search(
            r'(?:Counties|County|Parishes|Parish|Boroughs|Borough|Municipios|Municipio)\s+(?:of|de)\s+(.+?)(?:\s*$)',
            area, re.IGNORECASE
        )
        single_county = re.search(
            r'^(\w[\w\s]*?)\s+(?:County|Parish|Borough)\s*$', area, re.IGNORECASE
        )
        if counties_of:
            county = counties_of.group(1).strip()[:500]
        elif single_county:
            county = single_county.group(1).strip()[:500]

        # Detect statewide WDs
        if "statewide" in area.lower():
            is_statewide = 1
        elif not county:
            is_statewide = 0  # Unknown, not necessarily statewide

        return {
            "wd_number": parsed["wd_number"],
            "revision": parsed["revision"],
            "title": (parsed.get("title") or "")[:500],
            "area_name": area[:500] if area else "Unknown",
            "state_code": parsed.get("state_code"),
            "county_name": county[:500] if county else None,
            "is_statewide": is_statewide,
            "effective_date": parsed.get("effective_date"),
            "status": "ACTIVE",  # Assume active; _update_is_current handles superseded
        }

    def _normalize_rates(self, parsed: dict, wd_id: int) -> list[dict]:
        """Normalize parsed occupation rates for sca_wage_rate table."""
        rates = []
        hw = parsed.get("health_welfare")
        vac = parsed.get("vacation")
        hol = parsed.get("holiday")

        # Compute total fringe as sum of components
        fringe = None
        components = [v for v in [hw, vac, hol] if v is not None]
        if components:
            fringe = sum(components)

        for occ in parsed.get("occupations", []):
            rates.append({
                "wd_id": wd_id,
                "occupation_code": occ["occupation_code"],
                "occupation_title": (occ.get("occupation_title") or "")[:200],
                "hourly_rate": occ.get("hourly_rate"),
                "fringe_rate": fringe,
                "health_welfare": hw,
                "vacation": vac,
                "holiday": hol,
            })

        return rates

    # ------------------------------------------------------------------
    # Database operations
    # ------------------------------------------------------------------

    def _stage_raw(self, load_id: int, wd_number: str, revision: int, text: str):
        """Insert raw WD text into stg_sca_wd_raw."""
        raw_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO stg_sca_wd_raw (load_id, wd_number, revision, raw_text, raw_record_hash) "
                "VALUES (%s, %s, %s, %s, %s)",
                (load_id, wd_number, revision, text, raw_hash),
            )
            conn.commit()
        except Exception as exc:
            self.logger.warning("Staging insert failed for WD %s rev %d: %s", wd_number, revision, exc)
        finally:
            cursor.close()
            conn.close()

    def _upsert_determination(self, det: dict, record_hash: str, load_id: int) -> int | None:
        """Upsert a row into sca_wage_determination. Returns the row id."""
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "INSERT INTO sca_wage_determination "
                "(wd_number, revision, title, area_name, state_code, county_name, "
                " is_statewide, effective_date, status, is_current, wd_type, "
                " record_hash, last_load_id) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s, %s, %s) AS new_row "
                "ON DUPLICATE KEY UPDATE "
                "title = new_row.title, "
                "area_name = new_row.area_name, "
                "state_code = new_row.state_code, "
                "county_name = new_row.county_name, "
                "is_statewide = new_row.is_statewide, "
                "effective_date = new_row.effective_date, "
                "status = new_row.status, "
                "is_current = 1, "
                "wd_type = new_row.wd_type, "
                "record_hash = new_row.record_hash, "
                "last_load_id = new_row.last_load_id",
                (
                    det["wd_number"], det["revision"], det["title"],
                    det["area_name"], det["state_code"], det["county_name"],
                    det["is_statewide"], det["effective_date"], det["status"],
                    det.get("wd_type", "STANDARD"),
                    record_hash, load_id,
                ),
            )
            conn.commit()

            # Get the row id (works for both insert and update)
            cursor.execute(
                "SELECT id FROM sca_wage_determination WHERE wd_number = %s AND revision = %s",
                (det["wd_number"], det["revision"]),
            )
            row = cursor.fetchone()
            return row[0] if row else None
        except Exception as exc:
            self.logger.warning("Upsert failed for WD %s rev %d: %s", det["wd_number"], det["revision"], exc)
            conn.rollback()
            return None
        finally:
            cursor.close()
            conn.close()

    def _upsert_rates(self, rates: list[dict], load_id: int) -> tuple[int, int]:
        """Upsert occupation rates into sca_wage_rate. Returns (inserted, updated)."""
        if not rates:
            return 0, 0

        sql = (
            "INSERT INTO sca_wage_rate "
            "(wd_id, occupation_code, occupation_title, hourly_rate, fringe_rate, "
            " health_welfare, vacation, holiday, record_hash, last_load_id) "
            "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s) AS new_row "
            "ON DUPLICATE KEY UPDATE "
            "occupation_title = new_row.occupation_title, "
            "hourly_rate = new_row.hourly_rate, "
            "fringe_rate = new_row.fringe_rate, "
            "health_welfare = new_row.health_welfare, "
            "vacation = new_row.vacation, "
            "holiday = new_row.holiday, "
            "record_hash = new_row.record_hash, "
            "last_load_id = new_row.last_load_id"
        )

        conn = get_connection()
        cursor = conn.cursor()
        try:
            batch = []
            for r in rates:
                rate_hash = compute_record_hash(r, RATE_HASH_FIELDS)
                batch.append((
                    r["wd_id"], r["occupation_code"], r["occupation_title"],
                    r["hourly_rate"], r["fringe_rate"],
                    r["health_welfare"], r["vacation"], r["holiday"],
                    rate_hash, load_id,
                ))
            cursor.executemany(sql, batch)
            conn.commit()

            # MySQL ON DUPLICATE KEY: 1 per insert, 2 per update
            affected = cursor.rowcount
            updated = max(0, affected - len(batch))
            inserted = len(batch) - updated
            return inserted, updated
        except Exception as exc:
            self.logger.warning("Rate upsert failed: %s", exc)
            conn.rollback()
            return 0, 0
        finally:
            cursor.close()
            conn.close()

    def _get_existing_revisions(self) -> dict[str, int]:
        """Get the latest revision number for each WD number in the database.

        Returns:
            Dict of {wd_number: max_revision}.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            cursor.execute(
                "SELECT wd_number, MAX(revision) FROM sca_wage_determination GROUP BY wd_number"
            )
            return {row[0]: row[1] for row in cursor.fetchall()}
        finally:
            cursor.close()
            conn.close()

    def _update_is_current(self):
        """Mark older revisions as not current (is_current=0).

        For each wd_number, only the row with the highest revision should have
        is_current=1.
        """
        conn = get_connection()
        cursor = conn.cursor()
        try:
            # Set all to not current first, then mark the latest
            cursor.execute(
                "UPDATE sca_wage_determination d "
                "INNER JOIN ( "
                "    SELECT wd_number, MAX(revision) AS max_rev "
                "    FROM sca_wage_determination "
                "    GROUP BY wd_number "
                ") latest ON d.wd_number = latest.wd_number "
                "SET d.is_current = CASE "
                "    WHEN d.revision = latest.max_rev THEN 1 "
                "    ELSE 0 "
                "END "
                "WHERE d.is_current != (CASE WHEN d.revision = latest.max_rev THEN 1 ELSE 0 END)"
            )
            affected = cursor.rowcount
            conn.commit()
            if affected:
                self.logger.info("Updated is_current flag on %d WD rows", affected)
        finally:
            cursor.close()
            conn.close()
