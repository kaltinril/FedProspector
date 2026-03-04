"""DAT parser for SAM.gov V2 monthly entity extract files.

Parses pipe-delimited DAT files (142 fields per row) into structured entity
dicts suitable for loading via EntityLoader.  Handles multi-row entities
(same UEI with multiple CAGE codes), tilde-separated multi-value fields,
YYYYMMDD date conversion, and padded SBA/NAICS exception entries.

File format:
  - First line: BOF header  (e.g. ``BOF PUBLIC V2 00000000 20260201 0872819 0008169``)
  - Last line:  EOF footer   (same format with ``EOF`` prefix)
  - Data lines: 142 pipe-delimited fields, field [141] == ``!end``
"""

import logging
from pathlib import Path

from utils.parsing import fix_pipe_escapes, split_tilde_values

logger = logging.getLogger("fed_prospector.etl.dat_parser")

# ---------------------------------------------------------------------------
# Field position constants (0-based)
# ---------------------------------------------------------------------------
F_UEI_SAM = 0
F_UEI_DUNS = 1  # always empty in V2
F_EFT_INDICATOR = 2
F_CAGE_CODE = 3
F_DODAAC = 4
F_REG_STATUS = 5
F_PURPOSE_OF_REG = 6
F_INITIAL_REG_DATE = 7
F_REG_EXPIRATION_DATE = 8
F_LAST_UPDATE_DATE = 9
F_ACTIVATION_DATE = 10
F_LEGAL_BUSINESS_NAME = 11
F_DBA_NAME = 12
F_ENTITY_DIVISION = 13
F_ENTITY_DIVISION_NUMBER = 14
F_PHYS_ADDR_LINE_1 = 15
F_PHYS_ADDR_LINE_2 = 16
F_PHYS_ADDR_CITY = 17
F_PHYS_ADDR_STATE = 18
F_PHYS_ADDR_ZIP = 19
F_PHYS_ADDR_ZIP4 = 20
F_PHYS_ADDR_COUNTRY = 21
F_CONGRESSIONAL_DISTRICT = 22
F_DNB_OPEN_DATA = 23
F_ENTITY_START_DATE = 24
F_FISCAL_YEAR_END = 25
F_ENTITY_URL = 26
F_ENTITY_STRUCTURE_CODE = 27
F_STATE_OF_INCORP = 28
F_COUNTRY_OF_INCORP = 29
F_BIZ_TYPE_COUNTER = 30
F_BIZ_TYPE_STRING = 31
F_PRIMARY_NAICS = 32
F_NAICS_COUNTER = 33
F_NAICS_STRING = 34
F_PSC_COUNTER = 35
F_PSC_STRING = 36
F_CREDIT_CARD_USAGE = 37
F_CORRESPONDENCE_FLAG = 38
F_MAIL_ADDR_LINE_1 = 39
F_MAIL_ADDR_LINE_2 = 40
F_MAIL_ADDR_CITY = 41
F_MAIL_ADDR_ZIP = 42
F_MAIL_ADDR_ZIP4 = 43
F_MAIL_ADDR_COUNTRY = 44
F_MAIL_ADDR_STATE = 45
# POC blocks: 6 POCs x 11 fields each (positions 46-111)
F_GOV_BIZ_POC = 46
F_ALT_GOV_BIZ_POC = 57
F_PAST_PERF_POC = 68
F_ALT_PAST_PERF_POC = 79
F_ELEC_BIZ_POC = 90
F_ALT_ELEC_BIZ_POC = 101
F_NAICS_EXCEPTION_COUNTER = 112
F_NAICS_EXCEPTION_STRING = 113
F_DEBT_SUBJECT_TO_OFFSET = 114
F_EXCLUSION_STATUS_FLAG = 115
F_SBA_TYPE_COUNTER = 116
F_SBA_TYPE_STRING = 117
F_NO_PUBLIC_DISPLAY = 118
F_DISASTER_COUNTER = 119
F_DISASTER_STRING = 120
F_EVS_SOURCE = 121
# 122-140: reserved (always empty)
F_END_MARKER = 141

EXPECTED_FIELD_COUNT = 142

# POC field sub-structure (11 consecutive fields per POC)
_POC_FIELDS = [
    "first_name", "middle_initial", "last_name", "title",
    "address_line_1", "address_line_2", "city",
    "zip_code", "zip_code_plus4", "country_code", "state_or_province",
]

_POC_OFFSETS = {
    "governmentBusinessPOC":          F_GOV_BIZ_POC,
    "governmentBusinessAlternatePOC": F_ALT_GOV_BIZ_POC,
    "pastPerformancePOC":             F_PAST_PERF_POC,
    "pastPerformanceAlternatePOC":    F_ALT_PAST_PERF_POC,
    "electronicBusinessPOC":          F_ELEC_BIZ_POC,
    "electronicBusinessAlternatePOC": F_ALT_ELEC_BIZ_POC,
}

# Progress logging interval (number of lines)
_PROGRESS_INTERVAL = 100_000


# =====================================================================
# Public API
# =====================================================================

def get_dat_record_count(file_path):
    """Read the BOF header line and extract the record count.

    The BOF header format is::

        BOF PUBLIC V2 00000000 20260201 0872819 0008169

    The 6th space-separated token (index 5) is the total entity record count.

    Args:
        file_path: Path to the DAT file.

    Returns:
        int: Record count from the header.

    Raises:
        ValueError: If the first line is not a valid BOF header.
    """
    path = Path(file_path)
    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        first_line = fh.readline().strip()

    if not first_line.startswith("BOF"):
        raise ValueError(
            f"Expected BOF header, got: {first_line[:80]!r}"
        )

    parts = first_line.split()
    if len(parts) < 6:
        raise ValueError(
            f"BOF header has only {len(parts)} fields, expected at least 6: "
            f"{first_line[:80]!r}"
        )

    try:
        return int(parts[5])
    except ValueError:
        raise ValueError(
            f"Cannot parse record count from BOF header field: {parts[5]!r}"
        )


def parse_dat_file(file_path):
    """Generator that yields parsed entity dicts from a V2 DAT file.

    Groups consecutive rows with the same UEI SAM (multi-CAGE entities)
    and merges them into a single output dict.  Uses the first row for
    all entity data; additional rows contribute only their CAGE code
    (field 3) and EFT indicator (field 2).

    Yields:
        dict with keys:

        - ``entity``:  dict matching entity table columns
        - ``addresses``:  list of address dicts (physical + mailing)
        - ``naics``:  list of NAICS dicts
        - ``pscs``:  list of PSC code dicts
        - ``business_types``:  list of business type dicts
        - ``sba_certifications``:  list of SBA certification dicts
        - ``pocs``:  list of POC dicts
        - ``disaster_response``:  list of disaster response dicts
    """
    path = Path(file_path)
    logger.info("Opening DAT file: %s", path)

    lines_read = 0
    entities_yielded = 0

    # Accumulator for multi-row grouping
    current_parsed = None       # _parse_dat_line result for first row of group
    current_uei = None          # UEI SAM of current group
    extra_cage_codes = []       # CAGE codes from additional rows
    extra_eft_indicators = []   # EFT indicators from additional rows

    with open(path, "r", encoding="utf-8", errors="replace") as fh:
        for raw_line in fh:
            line = raw_line.rstrip("\n\r")

            # Skip BOF / EOF headers
            if line.startswith("BOF") or line.startswith("EOF"):
                continue

            # Fix escaped pipes before splitting
            line = fix_pipe_escapes(line)
            fields = line.split("|")

            if len(fields) < EXPECTED_FIELD_COUNT:
                lines_read += 1
                logger.warning(
                    "Line %d: expected %d fields, got %d -- skipping",
                    lines_read, EXPECTED_FIELD_COUNT, len(fields),
                )
                continue

            lines_read += 1
            uei = _field_or_none(fields[F_UEI_SAM])

            if uei is None:
                logger.warning("Line %d: missing UEI SAM -- skipping", lines_read)
                continue

            # Same entity as previous line -> collect CAGE code only
            if uei == current_uei:
                cage = _field_or_none(fields[F_CAGE_CODE])
                eft = _field_or_none(fields[F_EFT_INDICATOR])
                if cage:
                    extra_cage_codes.append(cage)
                if eft:
                    extra_eft_indicators.append(eft)
            else:
                # New entity -- yield the previous group (if any)
                if current_parsed is not None:
                    _merge_extra_cage_codes(
                        current_parsed, extra_cage_codes, extra_eft_indicators,
                    )
                    yield current_parsed
                    entities_yielded += 1

                # Start a new group
                current_parsed = _parse_dat_line(fields)
                current_uei = uei
                extra_cage_codes = []
                extra_eft_indicators = []

            # Progress logging
            if lines_read % _PROGRESS_INTERVAL == 0:
                logger.info(
                    "Progress: %d lines read, %d entities yielded",
                    lines_read, entities_yielded,
                )

    # Yield the final group
    if current_parsed is not None:
        _merge_extra_cage_codes(
            current_parsed, extra_cage_codes, extra_eft_indicators,
        )
        yield current_parsed
        entities_yielded += 1

    logger.info(
        "DAT parse complete: %d lines read, %d entities yielded",
        lines_read, entities_yielded,
    )


# =====================================================================
# Internal parsing functions
# =====================================================================

def _parse_dat_line(fields):
    """Parse a single DAT line (already split by ``|``) into structured data.

    Args:
        fields: List of string values from splitting on ``|``.

    Returns:
        dict with keys: entity, addresses, naics, pscs, business_types,
        sba_certifications, pocs, disaster_response.
    """
    uei_sam = _field_or_none(fields[F_UEI_SAM])
    primary_naics = _field_or_none(fields[F_PRIMARY_NAICS])

    entity = {
        "uei_sam":                      uei_sam,
        "cage_code":                    _field_or_none(fields[F_CAGE_CODE]),
        "dodaac":                       _field_or_none(fields[F_DODAAC]),
        "registration_status":          _field_or_none(fields[F_REG_STATUS]),
        "purpose_of_registration":      _field_or_none(fields[F_PURPOSE_OF_REG]),
        "initial_registration_date":    _norm_date(fields[F_INITIAL_REG_DATE]),
        "registration_expiration_date": _norm_date(fields[F_REG_EXPIRATION_DATE]),
        "last_update_date":             _norm_date(fields[F_LAST_UPDATE_DATE]),
        "activation_date":              _norm_date(fields[F_ACTIVATION_DATE]),
        "legal_business_name":          _field_or_none(fields[F_LEGAL_BUSINESS_NAME]),
        "dba_name":                     _field_or_none(fields[F_DBA_NAME]),
        "entity_division":              _field_or_none(fields[F_ENTITY_DIVISION]),
        "entity_division_number":       _field_or_none(fields[F_ENTITY_DIVISION_NUMBER]),
        "dnb_open_data_flag":           _field_or_none(fields[F_DNB_OPEN_DATA]),
        "entity_start_date":            _norm_date(fields[F_ENTITY_START_DATE]),
        "fiscal_year_end_close":        _field_or_none(fields[F_FISCAL_YEAR_END]),
        "entity_url":                   _field_or_none(fields[F_ENTITY_URL]),
        "entity_structure_code":        _field_or_none(fields[F_ENTITY_STRUCTURE_CODE]),
        "state_of_incorporation":       _field_or_none(fields[F_STATE_OF_INCORP]),
        "country_of_incorporation":     _field_or_none(fields[F_COUNTRY_OF_INCORP]),
        "primary_naics":                primary_naics,
        "credit_card_usage":            _field_or_none(fields[F_CREDIT_CARD_USAGE]),
        "correspondence_flag":          _field_or_none(fields[F_CORRESPONDENCE_FLAG]),
        "debt_subject_to_offset":       _field_or_none(fields[F_DEBT_SUBJECT_TO_OFFSET]),
        "exclusion_status_flag":        _field_or_none(fields[F_EXCLUSION_STATUS_FLAG]),
        "no_public_display_flag":       _field_or_none(fields[F_NO_PUBLIC_DISPLAY]),
        "evs_source":                   _field_or_none(fields[F_EVS_SOURCE]),
        "eft_indicator":                _field_or_none(fields[F_EFT_INDICATOR]),
    }

    # --- Addresses --------------------------------------------------------
    addresses = []
    phys_addr = _build_address(
        uei_sam, "PHYSICAL", fields,
        F_PHYS_ADDR_LINE_1, F_PHYS_ADDR_LINE_2,
        F_PHYS_ADDR_CITY, F_PHYS_ADDR_STATE,
        F_PHYS_ADDR_ZIP, F_PHYS_ADDR_ZIP4,
        F_PHYS_ADDR_COUNTRY,
        congressional_district_idx=F_CONGRESSIONAL_DISTRICT,
    )
    if phys_addr:
        addresses.append(phys_addr)

    mail_addr = _build_address(
        uei_sam, "MAILING", fields,
        F_MAIL_ADDR_LINE_1, F_MAIL_ADDR_LINE_2,
        F_MAIL_ADDR_CITY, F_MAIL_ADDR_STATE,
        F_MAIL_ADDR_ZIP, F_MAIL_ADDR_ZIP4,
        F_MAIL_ADDR_COUNTRY,
    )
    if mail_addr:
        addresses.append(mail_addr)

    # --- NAICS codes ------------------------------------------------------
    naics_exception_map = _parse_naics_exception_string(
        _field_or_none(fields[F_NAICS_EXCEPTION_STRING])
    )
    naics_list = _parse_naics_string(
        _field_or_none(fields[F_NAICS_STRING]),
        primary_naics,
    )
    # Attach exception data if present
    for entry in naics_list:
        exc_val = naics_exception_map.get(entry["naics_code"])
        if exc_val:
            entry["naics_exception"] = exc_val
        entry["uei_sam"] = uei_sam

    # --- PSC codes --------------------------------------------------------
    psc_list = _parse_psc_string(_field_or_none(fields[F_PSC_STRING]))
    pscs = [{"uei_sam": uei_sam, "psc_code": code} for code in psc_list]

    # --- Business types ---------------------------------------------------
    bt_list = _parse_business_type_string(
        _field_or_none(fields[F_BIZ_TYPE_STRING])
    )
    business_types = [
        {"uei_sam": uei_sam, "business_type_code": code} for code in bt_list
    ]

    # --- SBA certifications -----------------------------------------------
    sba_list = _parse_sba_string(
        _field_or_none(fields[F_SBA_TYPE_STRING])
    )
    sba_certifications = [
        {"uei_sam": uei_sam, **entry} for entry in sba_list
    ]

    # --- POCs -------------------------------------------------------------
    pocs = []
    for poc_type, offset in _POC_OFFSETS.items():
        poc = _extract_poc(fields, offset)
        if poc is not None:
            poc["uei_sam"] = uei_sam
            poc["poc_type"] = poc_type
            pocs.append(poc)

    # --- Disaster response ------------------------------------------------
    dr_list = _parse_disaster_string(
        _field_or_none(fields[F_DISASTER_STRING])
    )
    disaster_response = [
        {"uei_sam": uei_sam, "state_code": code} for code in dr_list
    ]

    return {
        "entity": entity,
        "addresses": addresses,
        "naics": naics_list,
        "pscs": pscs,
        "business_types": business_types,
        "sba_certifications": sba_certifications,
        "pocs": pocs,
        "disaster_response": disaster_response,
    }


def _merge_extra_cage_codes(parsed, extra_cage_codes, extra_eft_indicators):
    """Merge additional CAGE codes from multi-row entities.

    The entity table cage_code column is VARCHAR(5) so only the first row's
    CAGE code is used.  Extra CAGE codes are noted in a comment field but
    not stored in the entity dict.  This function exists so the grouping
    logic is explicit and can be extended later if needed.
    """
    if extra_cage_codes:
        # Log for visibility -- entity table stores only the first CAGE code
        logger.debug(
            "Entity %s has %d additional CAGE code(s): %s",
            parsed["entity"].get("uei_sam"),
            len(extra_cage_codes),
            ", ".join(extra_cage_codes),
        )


# =====================================================================
# Field value helpers
# =====================================================================

def _field_or_none(value):
    """Return stripped value or None if empty/whitespace."""
    if value is None:
        return None
    s = value.strip()
    return s if s else None


def _norm_date(value):
    """Convert YYYYMMDD to YYYY-MM-DD, or return None for empty/invalid.

    Args:
        value: Raw date string from a DAT field (e.g. ``"20260201"``).

    Returns:
        ISO date string (``"2026-02-01"``) or None.
    """
    if not value or not value.strip():
        return None
    s = value.strip()
    if len(s) == 8 and s.isdigit():
        return f"{s[:4]}-{s[4:6]}-{s[6:8]}"
    logger.warning("dat_parser: unrecognized date format %r — stored as NULL", s)
    return None


# =====================================================================
# Address builder
# =====================================================================

def _build_address(uei_sam, address_type, fields,
                   line1_idx, line2_idx, city_idx, state_idx,
                   zip_idx, zip4_idx, country_idx,
                   congressional_district_idx=None):
    """Build an address dict from field positions, or None if fully empty.

    Args:
        uei_sam: Parent entity key.
        address_type: ``"PHYSICAL"`` or ``"MAILING"``.
        fields: Full list of pipe-split field values.
        line1_idx..country_idx: Field index positions.
        congressional_district_idx: Optional index for congressional district
            (only applicable to physical addresses).

    Returns:
        dict matching entity_address table columns, or None if no data.
    """
    addr = {
        "uei_sam":                uei_sam,
        "address_type":           address_type,
        "address_line_1":         _field_or_none(fields[line1_idx]),
        "address_line_2":         _field_or_none(fields[line2_idx]),
        "city":                   _field_or_none(fields[city_idx]),
        "state_or_province":      _field_or_none(fields[state_idx]),
        "zip_code":               _field_or_none(fields[zip_idx]),
        "zip_code_plus4":         _field_or_none(fields[zip4_idx]),
        "country_code":           _field_or_none(fields[country_idx]),
        "congressional_district": (
            _field_or_none(fields[congressional_district_idx])
            if congressional_district_idx is not None else None
        ),
    }

    # Only return the address if at least one substantive field has data
    has_data = any(
        addr[k] for k in (
            "address_line_1", "city", "state_or_province",
            "zip_code", "country_code",
        )
    )
    return addr if has_data else None


# =====================================================================
# Multi-value field parsers
# =====================================================================

def _parse_naics_string(naics_str, primary_naics):
    """Parse tilde-separated NAICS string into structured dicts.

    Each entry is formatted as the NAICS code followed by a single-character
    SBA small business flag.  For example ``"541511Y"`` means
    naics_code=541511, sba_small_business=Y.  Codes may vary in length
    (2-6 digits), so the last character is always the flag.

    Args:
        naics_str: Tilde-separated NAICS string from the DAT file, or None.
        primary_naics: Primary NAICS code string for is_primary comparison.

    Returns:
        list of dicts: ``{naics_code, is_primary, sba_small_business}``.
        Does not yet include ``uei_sam`` (caller adds it).
    """
    if not naics_str:
        return []

    entries = split_tilde_values(naics_str)
    results = []

    for raw_entry in entries:
        entry = raw_entry.strip()
        if not entry:
            continue

        if len(entry) < 2:
            logger.debug("NAICS entry too short to parse: %r", entry)
            continue

        # Last character is the SBA small business flag (Y/N/E/etc.)
        naics_code = entry[:-1]
        sba_flag = entry[-1]

        is_primary = "Y" if naics_code == primary_naics else "N"

        results.append({
            "naics_code":        naics_code,
            "is_primary":        is_primary,
            "sba_small_business": sba_flag,
        })

    return results


def _parse_naics_exception_string(exception_str):
    """Parse tilde-separated NAICS exception string.

    Each entry is padded to 10 characters, e.g. ``"541519YY  "``.
    Format: 6-digit NAICS code + exception chars (remaining after strip).

    Args:
        exception_str: Tilde-separated exception string, or None.

    Returns:
        dict mapping naics_code -> exception_value (stripped).
    """
    if not exception_str:
        return {}

    entries = split_tilde_values(exception_str)
    result = {}

    for raw_entry in entries:
        entry = raw_entry.strip()
        if not entry or len(entry) < 7:
            # Need at least 6-digit code + 1 exception char
            if entry:
                logger.debug("NAICS exception entry too short: %r", raw_entry)
            continue

        naics_code = entry[:6]
        exception_value = entry[6:].strip()
        if exception_value:
            result[naics_code] = exception_value

    return result


def _parse_psc_string(psc_str):
    """Parse tilde-separated PSC codes.

    Args:
        psc_str: Tilde-separated PSC string, or None.

    Returns:
        list of PSC code strings.
    """
    return split_tilde_values(psc_str) if psc_str else []


def _parse_business_type_string(bt_str):
    """Parse tilde-separated business type codes.

    Args:
        bt_str: Tilde-separated business type string (e.g. ``"2X~8W~A2"``),
            or None.

    Returns:
        list of business type code strings.
    """
    return split_tilde_values(bt_str) if bt_str else []


def _parse_sba_string(sba_str):
    """Parse tilde-separated SBA business type string.

    Each entry is a 10-character token: 2-char SBA type code + 8-digit
    exit date (YYYYMMDD).  For example ``"A420260101"`` means
    sba_type_code="A4", certification_exit_date="2026-01-01".
    Entries are padded with spaces if the exit date is absent.

    Args:
        sba_str: Tilde-separated SBA string, or None.

    Returns:
        list of dicts with keys: sba_type_code, certification_exit_date.
    """
    if not sba_str:
        return []

    entries = split_tilde_values(sba_str)
    results = []
    for raw_entry in entries:
        entry = raw_entry.strip()
        if not entry:
            continue

        sba_type_code = entry[:2]
        exit_date_raw = entry[2:10].strip() if len(entry) >= 10 else ""
        exit_date = _norm_date(exit_date_raw) if exit_date_raw else None

        results.append({
            "sba_type_code": sba_type_code,
            "certification_exit_date": exit_date,
        })

    return results


def _parse_disaster_string(dr_str):
    """Parse tilde-separated disaster response state codes.

    Each entry is a state code (e.g. ``"STANC"``) or ``"ANY"``.

    Args:
        dr_str: Tilde-separated disaster response string, or None.

    Returns:
        list of state code strings.
    """
    return split_tilde_values(dr_str) if dr_str else []


# =====================================================================
# POC extraction
# =====================================================================

def _extract_poc(fields, offset):
    """Extract a single POC from 11 consecutive fields starting at *offset*.

    Returns a dict with POC fields, or None if no first_name or last_name
    is present (indicating no real POC data in this slot).

    Args:
        fields: Full list of pipe-split field values.
        offset: Starting index of the 11-field POC block.

    Returns:
        dict with POC field names as keys, or None.
    """
    poc = {}
    for i, field_name in enumerate(_POC_FIELDS):
        poc[field_name] = _field_or_none(fields[offset + i])

    # Only include POCs that have at least a first_name or last_name
    if not poc.get("first_name") and not poc.get("last_name"):
        return None

    return poc
