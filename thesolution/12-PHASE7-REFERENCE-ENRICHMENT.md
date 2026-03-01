# Phase 7: Reference Data Enrichment

**Status**: COMPLETE (2026-02-28)
**Dependencies**: Phase 1 (reference tables exist), Phase 2 (entity data loaded for code discovery)
**Deliverable**: All reference/lookup tables enriched with human-readable details, hierarchy metadata, and complete code coverage. Reload process is repeatable via `load-lookups`.

---

## Overview

Phase 1 loaded reference tables with minimal data -- codes and basic descriptions. This phase enriches every reference table so that queries produce human-readable output without requiring tribal knowledge of code meanings.

**Key gaps discovered:**
- `ref_entity_structure` -- table exists in DDL but **was never loaded** (no loader method exists)
- `ref_business_type` -- `classification` column is "Business Type Code" for every row (useless)
- `ref_set_aside_type` -- only 14 hardcoded Python entries; SAM.gov uses many more
- `ref_naics_code` -- no hierarchy info (Sector vs Subsector vs Industry)
- `ref_country_code` -- missing SAM.gov-specific territory codes (XQZ, etc.)
- No `ref_sba_type` table -- SBA certification codes have no lookup
- SBA type codes in `entity_sba_certification` are still concatenated code+date (known issue from Phase 2, documented in CLAUDE.md item #11)

**Data discovery from loaded database (865K entities):**

Entity structure codes (8 distinct):
| Code | Count | Description (from SAM.gov docs) |
|------|-------|--------------------------------|
| 2L | 369,453 | Corporate Entity (Not Tax Exempt) |
| 8H | 137,066 | Joint Venture |
| 2K | 120,104 | Partnership or Limited Liability Partnership |
| 2J | 105,753 | Sole Proprietorship |
| 2A | 70,567 | U.S. Government Entity |
| ZZ | 53,106 | Other |
| X6 | 7,216 | International Organization |
| CY | 1,303 | Foreign Government |

SBA type codes (5 distinct base codes, all with `sba_type_desc = NULL`):
| Code | Description | Records |
|------|-------------|---------|
| A6 | 8(a) Program Participant | ~18K (most with appended dates) |
| A9 | 8(a) Joint Venture (Mentor-Protege) | 14,705 |
| A0 | 8(a) Joint Venture (non Mentor-Protege) | 4,496 |
| XX | SBA Certified HUBZone | ~4,500 |
| JT | 8(a) Joint Venture | ~1,200 |

Set-aside codes from loaded opportunities (4 so far, more will come):
| Code | Description | Count |
|------|-------------|-------|
| 8A | 8a Competed | 26 |
| WOSB | Women-Owned Small Business | 19 |
| 8AN | 8(a) Sole Source | 10 |
| EDWOSB | SBA Certified EDWOSB Program Set-Aside | 2 |

---

## Task 7.1: Enrich `ref_business_type`

**Problem**: 75 rows with `classification` = "Business Type Code" for every row. No way to filter by category (Woman-Owned, Veteran, Government, etc.) or know which codes are socioeconomic designations relevant to WOSB/8(a) prospecting.

**Changes**:

Schema (`01_reference_tables.sql`):
```sql
ALTER TABLE ref_business_type
  ADD COLUMN category VARCHAR(50) AFTER classification,
  ADD COLUMN is_socioeconomic CHAR(1) DEFAULT 'N',
  ADD COLUMN is_small_business_related CHAR(1) DEFAULT 'N';
```

Drop the useless `classification` column (always "Business Type Code") or repurpose it.

Category assignments:
| Category | Codes |
|----------|-------|
| Government | 2R, 2F, 12, 3I, CY, NG |
| Ownership/Ethnicity | 20, OW, FR, QZ, OY, PI, NB, 05, XY, 8U, 1B, 1E, 1S |
| Woman-Owned | A2, 8W, 8E, 8C, 8D |
| Veteran | A5, QF |
| Small Business | 27, 1D, A3, HQ, JX |
| Non-Profit/Foundation | A7, A8, 2U, BZ, H2, 6D |
| Education | M8, G6, G7, G8, HB, 1A, 1R, ZW, GW, OH, HS, QU, G3, G5 |
| Organization Type | LJ, XS, MF, 2X, HK, QW |
| Local Government | C8, C7, ZR, MG, C6, H6, TW, UD, 8B, 86, KM, T4, FO, TR |
| Healthcare | 80, FY |
| Other | G9 |

Socioeconomic flags (`is_socioeconomic = 'Y'`): A2, 8W, 8E, 8C, 8D, A5, QF, 27, 23, FR, QZ, OY, PI, NB, OW, HQ, JX, 1E, 1S, 05, XY, 8U, 1B, A3, A7
Small business flags (`is_small_business_related = 'Y'`): 8W, 8E, 8C, 8D, 27, 1D, A3, QF, HQ, JX, 1E, 1S

**Loader**: Update `load_business_types()` in `reference_loader.py` to populate new columns from enriched CSV or inline mapping.

**Source**: `OLD_RESOURCES/BusTypes.csv` (76 rows) + category mapping above

**Files to modify**:
- [x] `fed_prospector/db/schema/01_reference_tables.sql`
- [x] `fed_prospector/etl/reference_loader.py`

---

## Task 7.2: Load `ref_entity_structure` (Currently Empty)

**Problem**: Table exists in DDL but `reference_loader.py` has no `load_entity_structures()` method. Not included in `load_all()`. The `entity.entity_structure_code` column references this table but it's empty.

**Changes**: Add `load_entity_structures()` to `reference_loader.py` with seed data discovered from loaded entity data (8 codes).

Seed data:
| Code | Description |
|------|-------------|
| 2J | Sole Proprietorship |
| 2K | Partnership or Limited Liability Partnership |
| 2L | Corporate Entity (Not Tax Exempt) |
| 2A | U.S. Government Entity |
| 8H | Joint Venture |
| CY | Foreign Government |
| X6 | International Organization |
| ZZ | Other |

Add to `load_all()` list.

**Files to modify**:
- [x] `fed_prospector/etl/reference_loader.py`

---

## Task 7.3: Enrich `ref_country_code` with SAM.gov Territory Codes

**Problem**: Current 252 rows cover ISO 3166-1 standard countries plus 3 special territories (XKS, XWB, XGZ). SAM.gov uses additional codes from `GG-Updated-Country-and-State-Lists - Countries.csv` (262 rows) including non-ISO entries like XQZ (Akrotiri) that appear in entity addresses.

**Changes**:

Schema (`01_reference_tables.sql`):
```sql
ALTER TABLE ref_country_code
  ADD COLUMN is_iso_standard CHAR(1) DEFAULT 'Y',
  ADD COLUMN sam_gov_recognized CHAR(1) DEFAULT 'Y';
```

Update `load_country_codes()` to:
1. Load ISO 3166-1 data from `country_codes_combined.csv` (primary, 252 rows)
2. Merge SAM.gov-specific entries from `GG-Updated-Country-and-State-Lists - Countries.csv`
3. Mark non-ISO entries as `is_iso_standard = 'N'`
4. Keep existing XKS, XWB, XGZ special territory handling

**Sources**:
- `workdir/converted/country_codes_combined.csv` -- ISO 3166-1 (alpha-2, alpha-3, numeric)
- `workdir/converted/GG-Updated-Country-and-State-Lists - Countries.csv` -- SAM.gov country list
- Wikipedia ISO 3166-1 pages for validation: https://en.wikipedia.org/wiki/ISO_3166-1_alpha-3, https://en.wikipedia.org/wiki/ISO_3166-1

**Files to modify**:
- [x] `fed_prospector/db/schema/01_reference_tables.sql`
- [x] `fed_prospector/etl/reference_loader.py`

---

## Task 7.4: Enrich `ref_naics_code` with Hierarchy Metadata

**Problem**: 2,264 NAICS codes with description only. No hierarchy info. A 2-digit code is a "Sector", 3-digit is "Subsector", etc. Roll-up reporting (e.g., "all IT contracts" = sector 54) requires this.

**Changes**:

Schema (`01_reference_tables.sql`):
```sql
ALTER TABLE ref_naics_code
  ADD COLUMN code_level TINYINT AFTER description,
  ADD COLUMN level_name VARCHAR(30) AFTER code_level,
  ADD COLUMN parent_code VARCHAR(11) AFTER level_name;
```

Level mapping (computed from code length):
| Code Length | Level | Name |
|-------------|-------|------|
| 2 | 1 | Sector |
| 3 | 2 | Subsector |
| 4 | 3 | Industry Group |
| 5 | 4 | NAICS Industry |
| 6 | 5 | National Industry |

`parent_code` = left(naics_code, len-1) for codes > 2 digits. 2-digit sectors have NULL parent.

**Loader**: Update `load_naics_codes()` to compute `code_level`, `level_name`, and `parent_code` during the INSERT. These are derived from the code length, no new CSV needed.

**Files to modify**:
- [x] `fed_prospector/db/schema/01_reference_tables.sql`
- [x] `fed_prospector/etl/reference_loader.py`

---

## Task 7.5: Expand `ref_set_aside_type` to Comprehensive CSV-Driven Load

**Problem**: Only 14 entries, hardcoded in Python source code. Federal procurement uses many more set-aside types. SAM.gov Opportunities API returns codes not in our table (e.g., full competition codes, tribal/Indian set-asides).

**Changes**:

Schema (`01_reference_tables.sql`):
```sql
ALTER TABLE ref_set_aside_type
  ADD COLUMN category VARCHAR(50) AFTER is_small_business;
```

Create new CSV: `workdir/converted/local database/data_to_import/set_aside_types.csv`

Categories: WOSB, 8(a), HUBZone, SDVOSB, Veteran, General Small Business, Tribal/Indian, Full Competition, Other.

Comprehensive set-aside codes (from SAM.gov Opportunities API documentation):
| Code | Description | SB? | Category |
|------|-------------|-----|----------|
| SBA | Total Small Business Set-Aside | Y | General Small Business |
| SBP | Partial Small Business Set-Aside | Y | General Small Business |
| 8A | 8(a) Set-Aside (Competed) | Y | 8(a) |
| 8AN | 8(a) Sole Source | Y | 8(a) |
| WOSB | Women-Owned Small Business Set-Aside | Y | WOSB |
| WOSBSS | WOSB Sole Source | Y | WOSB |
| EDWOSB | Economically Disadvantaged WOSB Set-Aside | Y | WOSB |
| EDWOSBSS | EDWOSB Sole Source | Y | WOSB |
| HZC | HUBZone Set-Aside | Y | HUBZone |
| HZS | HUBZone Sole Source | Y | HUBZone |
| SDVOSBC | Service-Disabled Veteran-Owned SB Set-Aside | Y | SDVOSB |
| SDVOSBS | SDVOSB Sole Source | Y | SDVOSB |
| VSA | Veteran-Owned Small Business Set-Aside | Y | Veteran |
| VSB | Veteran-Owned Small Business Sole Source | Y | Veteran |
| BICiv | Buy Indian Set-Aside (Civilian) | Y | Tribal/Indian |
| ISBEE | Indian Small Business Economic Enterprise Set-Aside | Y | Tribal/Indian |
| IEE | Indian Economic Enterprise Set-Aside | Y | Tribal/Indian |
| RSB | Reserved for Small Business (FAR 19.5) | Y | General Small Business |
| NONE | No Set-Aside Used | N | Full Competition |
| FSS | Full and Open Competition | N | Full Competition |
| ... | (expand from SAM.gov API reference as needed) | | |

**Loader**: Replace `seed_set_aside_types()` with `load_set_aside_types()` that reads from CSV.

**Files to modify**:
- [x] `fed_prospector/db/schema/01_reference_tables.sql`
- [x] `fed_prospector/etl/reference_loader.py`
- [x] NEW: `workdir/converted/local database/data_to_import/set_aside_types.csv`

---

## Task 7.6: Add `ref_sba_type` Lookup Table

**Problem**: `entity_sba_certification.sba_type_code` stores codes like "A6", "XX", "JT" but there's no reference table. The `sba_type_desc` column is NULL for all 23K+ records (descriptions aren't being loaded from DAT file).

> **Note**: The SBA type concatenated code+date parsing issue (CLAUDE.md item #11) is a separate Phase 2 bug. This task creates the reference lookup; fixing the parser is out of scope here but should be addressed.

**Changes**:

Schema (`01_reference_tables.sql`):
```sql
CREATE TABLE IF NOT EXISTS ref_sba_type (
    sba_type_code   VARCHAR(10) NOT NULL,
    description     VARCHAR(200) NOT NULL,
    program_name    VARCHAR(100),
    PRIMARY KEY (sba_type_code)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
```

Seed data (from SAM.gov documentation + database discovery):
| Code | Description | Program |
|------|-------------|---------|
| A6 | 8(a) Program Participant | 8(a) |
| A9 | 8(a) Joint Venture (Mentor-Protege) | 8(a) |
| A0 | 8(a) Joint Venture (Non Mentor-Protege) | 8(a) |
| JT | 8(a) Joint Venture | 8(a) |
| XX | SBA Certified HUBZone | HUBZone |

**Loader**: Add `load_sba_types()` to `reference_loader.py` and include in `load_all()`.

**Files to modify**:
- [x] `fed_prospector/db/schema/01_reference_tables.sql`
- [x] `fed_prospector/etl/reference_loader.py`

---

## Task 7.7: Update Views with Enriched JOINs

**Problem**: Current views (`v_target_opportunities`, `v_competitor_analysis`) don't leverage the enriched reference tables for human-readable output.

**Changes** to `07_views.sql`:

`v_competitor_analysis`:
- JOIN `ref_business_type` to show business type descriptions and categories instead of raw codes
- JOIN `ref_naics_code` to show NAICS description and sector name
- Add `ref_entity_structure` JOIN for entity structure description

`v_target_opportunities`:
- Add `ref_set_aside_type.category` to output
- Already JOINs `ref_naics_code` -- add `level_name` and sector parent description

**Files to modify**:
- [x] `fed_prospector/db/schema/07_views.sql`

---

## Task 7.8: Update CLI `load-lookups` Command

**Problem**: CLI doesn't know about `ref_entity_structure` or `ref_sba_type` tables.

**Changes** to `main.py`:
- Add `entity_structure` and `sba_type` to `--table` choices
- Update `load-lookups` to call new loader methods
- Update `status` command to include new table row counts

**Files to modify**:
- [x] `fed_prospector/cli/database.py`

---

## Task 7.9: Update FPDS Documentation and Settings

**Finding**: FPDS.gov is being decommissioned:
- **Feb 24, 2026**: ezSearch on FPDS.gov shuts down
- **Later FY2026**: ATOM feed (`https://www.fpds.gov/dbsight/FEEDS/ATOM`) sunsets entirely
- **Replacement**: SAM.gov Contract Awards API at `https://api.sam.gov/contract-awards/v1/search`

The SAM.gov Contract Awards API uses the same API key, returns the same underlying FPDS data in JSON format, and supports 80+ filter parameters. This is what Phase 5A should target.

**Changes**:

`settings.py`:
```python
# SAM.gov Contract Awards API (replacement for FPDS)
SAM_CONTRACT_AWARDS_URL = "https://api.sam.gov/contract-awards/v1/search"

# FPDS ATOM Feed - DEPRECATED: ezSearch decommissioned Feb 24, 2026;
# ATOM feed sunsetting later FY2026. Use SAM_CONTRACT_AWARDS_URL instead.
FPDS_ATOM_BASE_URL = "https://www.fpds.gov/dbsight/FEEDS/ATOM"
```

`08-PHASE5-EXTENDED-SOURCES.md`:
- Update Phase 5F to note FPDS is deprecated
- Add recommendation to prioritize Phase 5A (SAM.gov Contract Awards API) instead
- Note that building a new FPDS ATOM client is inadvisable

**Files to modify**:
- [x] `fed_prospector/config/settings.py`
- [x] `thesolution/08-PHASE5-EXTENDED-SOURCES.md`

---

## Task 7.10: Update All Project Documentation

Update the following docs to reflect Phase 7 changes:
- [ ] `thesolution/00-MASTER-PLAN.md` -- add Phase 7 entry
- [ ] `thesolution/02-DATABASE-SCHEMA.md` -- update table definitions for altered/new tables
- [ ] `thesolution/QUICKSTART.md` -- update reference table counts and `load-lookups` output
- [ ] `CLAUDE.md` -- update table counts, file references, add `ref_sba_type` to references

---

## Acceptance Criteria

- [ ] `ref_business_type` has `category`, `is_socioeconomic`, `is_small_business_related` populated for all rows
- [ ] `ref_entity_structure` has 8 rows matching all codes found in loaded entity data
- [ ] `ref_country_code` includes SAM.gov territory codes with `is_iso_standard` flag
- [ ] `ref_naics_code` has `code_level`, `level_name`, `parent_code` for all rows
- [ ] `ref_set_aside_type` loaded from CSV with 20+ entries and `category` column
- [ ] `ref_sba_type` has 5+ rows covering all codes in `entity_sba_certification`
- [ ] Views produce human-readable output (business type names, NAICS sectors, etc.)
- [ ] `python main.py load-lookups` reloads all enriched tables idempotently
- [ ] `python main.py status` shows updated row counts for all reference tables
- [ ] FPDS deprecation documented, SAM Contract Awards URL in settings.py

---

## Verification

```bash
# Rebuild and reload everything
python main.py build-database --drop-first
python main.py load-lookups
python main.py status

# Spot-check enriched data
mysql -u fed_app -p fed_contracts -e "
  SELECT business_type_code, description, category, is_socioeconomic
  FROM ref_business_type WHERE category = 'Woman-Owned';
"

mysql -u fed_app -p fed_contracts -e "
  SELECT * FROM ref_entity_structure;
"

mysql -u fed_app -p fed_contracts -e "
  SELECT naics_code, description, level_name, parent_code
  FROM ref_naics_code WHERE code_level = 1;
"

mysql -u fed_app -p fed_contracts -e "
  SELECT * FROM ref_country_code WHERE is_iso_standard = 'N';
"

mysql -u fed_app -p fed_contracts -e "
  SELECT * FROM ref_sba_type;
"

# Verify views work with enriched data
mysql -u fed_app -p fed_contracts -e "
  SELECT * FROM v_competitor_analysis LIMIT 5;
"
```
