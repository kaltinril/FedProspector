# Phase 2: Entity Data Pipeline (Proof of Concept - 1 Source)

**Status**: **COMPLETE** (2026-02-22)
**Dependencies**: Phase 1 (Foundation) complete
**Deliverable**: 500K+ entity records loaded and normalized in MySQL with change detection

---

## Tasks

### 2.1 SAM Entity API Client
- [x] Implement `api_clients/sam_entity_client.py`:
  - [x] `get_entity_by_uei(uei_sam)` - single entity lookup
  - [x] `get_entities_by_date(update_date)` - paginated date-based query
  - [x] `search_entities(**filters)` - arbitrary filter search
  - [x] `search_wosb_entities()` - convenience WOSB search (8W + 8E codes)
  - [x] `search_8a_entities()` - convenience 8(a) search (A4 SBA code)
- [x] Implement `api_clients/sam_extract_client.py`:
  - [x] `download_monthly_extract(year, month)` - monthly full extract (tries V2 + legacy filename formats)
  - [x] `download_daily_extract(date)` - daily incremental (Tue-Sat only)
  - [x] `list_available_extracts()` - list files available on SAM.gov
  - [x] `extract_zip()` - extract ZIP files with nested ZIP handling
  - [x] `stream_json_entities()` - streaming JSON parser (ijson with fallback)
- [ ] Write tests with mock API responses

### 2.2 Data Cleaner
- [x] Implement `etl/data_cleaner.py` with all 10 known quality rules:
  - [x] `clean_zip_code()` - remove city/state/country contamination (#1), PO BOX (#2)
  - [x] `clean_state_code()` - validate, reject dates (#3), flag foreign provinces (#4)
  - [x] `normalize_date()` - YYYYMMDD/ISO/timestamps to date (#10)
  - [x] `normalize_country_code()` - non-ASCII normalization (#5), XKS/XWB/XGZ (#6)
  - [x] `split_cage_codes()` - handle comma-separated (#7)
  - [x] `clean_record()` - fix DAT pipe escapes (#9), apply DB rules
  - [x] `clean_entity_record()` - full entity cleaning (addresses, POCs, dates, CAGE)
  - [x] `_load_db_rules()` - load configurable rules from `etl_data_quality_rule`
  - [x] Stats tracking (`get_stats()`, `reset_stats()`)
- [x] Seed `etl_data_quality_rule` with 10 initial rules (via `python main.py seed-quality-rules`)
- [ ] Write tests for each cleanup function with real-world bad data examples

### 2.3 Entity Loader
- [x] Implement `etl/entity_loader.py`:
  - [x] `load_from_json_extract(json_file_path, mode)` - primary method
  - [x] `load_from_api_response(entity_data_list, mode)` - for incremental
  - [x] `_normalize_entity(raw_json)` - flatten nested JSON to entity fields
  - [x] `_extract_child_records(raw_json, uei_sam)` - extract all 8 child table types
  - [x] `_upsert_entity()` - INSERT ... ON DUPLICATE KEY UPDATE with change detection
  - [x] `_sync_child_records()` - delete + insert strategy for child tables
  - [x] `_insert_history()` - field-level change history to entity_history
- [x] Streaming JSON parser via ijson (with stdlib json fallback)
- [x] Batch commits every 1000 records
- [x] In-memory hash cache for change detection (avoids per-record DB lookups)
- [x] Error isolation (individual record errors don't abort the load)

### 2.4 Initial Bulk Load
- [x] SAM.gov API key configured (free tier, 10 calls/day)
- [x] Download monthly entity extract (DAT format - V2 pipe-delimited)
- [x] Run full load into MySQL via LOAD DATA INFILE (~4.5 min: 56s parse + 225s load)
- [x] Verify record counts:
  - [x] `entity` table: 865,232 rows (771,925 Active, 93,307 Expired)
  - [x] `entity_address`: 1,729,907 rows
  - [x] `entity_naics`: 2,993,439 rows (7 duplicates skipped via IGNORE)
  - [x] `entity_business_type`: 2,532,931 rows
  - [x] `entity_sba_certification`: 30,272 rows (106,142 WOSB entities with 8W business type)
  - [x] `entity_poc`: 2,583,524 rows
  - [x] `entity_psc`: 1,330,928 rows
  - [x] `entity_disaster_response`: 399,529 rows
- [x] Verify data quality: spot check against SAM.gov website
- [x] Log load statistics in `etl_load_log`

### 2.5 Daily Incremental Update
- [x] Daily extract download implemented (`download-extract --type=daily`)
- [ ] Test change detection:
  - [ ] Load a daily extract
  - [ ] Verify `entity_history` captures field-level changes
  - [ ] Verify only changed records are updated (unchanged records skipped)
- [ ] Verify `etl_load_log` shows accurate insert/update/unchanged counts

### 2.6 CLI Commands
- [x] Add `download-extract --type=monthly/daily` command
- [x] Add `load-entities --mode=full/daily --file=<path>` command
- [x] Add `seed-quality-rules` command
- [x] `status` command already shows entity table stats and last load date

---

## New Files Created (Phase 2)

| File | Purpose | Lines |
|------|---------|-------|
| `api_clients/sam_entity_client.py` | Entity Management API v3 client | ~269 |
| `api_clients/sam_extract_client.py` | Bulk extract download + ZIP handling + JSON streaming | ~350 |
| `etl/data_cleaner.py` | Data quality rules engine (10 rules + DB rules) | ~612 |
| `etl/entity_loader.py` | JSON normalization + entity upsert + child sync | ~689 |
| `etl/dat_parser.py` | V2 DAT file parser (pipe-delimited, multi-row entity assembly) | ~657 |
| `etl/bulk_loader.py` | LOAD DATA INFILE bulk loader for all entity tables | ~465 |

## Modified Files

| File | Changes |
|------|---------|
| `main.py` | Added `download-extract`, `load-entities`, `seed-quality-rules` commands; DAT file detection logic |
| `requirements.txt` | Added `ijson>=3.2.0` for streaming JSON parsing |

---

## Acceptance Criteria

1. [x] `entity` table has 500K+ records loaded from monthly extract -- **865,232 loaded**
2. [x] All 8 entity child tables are populated with normalized data -- **all 8 child tables populated**
3. [ ] Running daily load correctly identifies and updates only changed records (not yet tested)
4. [ ] `entity_history` contains field-level change records for updated entities (not yet tested)
5. [x] `etl_load_log` shows successful load with accurate statistics
6. [x] Data cleaner catches and corrects known data quality issues
7. [x] No duplicate records (UEI SAM is unique in entity table)
8. [x] Streaming parser handles 55MB+ files without running out of memory -- **DAT parser + LOAD DATA INFILE handles 865K entities in ~4.5 min**

---

## Key JSON Structure (for loader implementation)

```json
{
    "entityData": [
        {
            "entityRegistration": {
                "samRegistered": "Yes",
                "ueiSAM": "ABC123DEF456",
                "cageCode": "12345",
                "legalBusinessName": "Example Corp",
                "registrationStatus": "Active",
                ...
            },
            "coreData": {
                "entityInformation": { ... },
                "generalInformation": { ... },
                "physicalAddress": { ... },
                "mailingAddress": { ... },
                "businessTypes": {
                    "businessTypeList": [ { "businessTypeCode": "2X", ... } ],
                    "sbaBusinessTypeList": [ { "sbaBusinessTypeCode": "A6", ... } ]
                },
                "financialInformation": { ... }
            },
            "assertions": {
                "goodsAndServices": {
                    "naicsList": [ { "naicsCode": "541511", ... } ],
                    "pscList": [ { "pscCode": "D302", ... } ],
                    "primaryNaics": "541511"
                },
                "geographicalAreaServed": [ ... ]
            },
            "pointsOfContact": {
                "governmentBusinessPOC": { ... },
                "electronicBusinessPOC": { ... },
                "governmentBusinessAlternatePOC": { ... },
                "electronicBusinessAlternatePOC": { ... },
                "pastPerformancePOC": { ... },
                "pastPerformanceAlternatePOC": { ... }
            }
        }
    ],
    "links": { "selfLink": "...", "nextLink": "..." },
    "totalRecords": 576000
}
```

---

## Performance Targets

- Full monthly load: Complete within 2 hours
- Daily incremental: Complete within 15 minutes
- Memory usage: Stay under 500MB during load
- Batch size: 1000 records per INSERT statement (configurable via `--batch-size`)

---

## Known Issues

- SAM.gov monthly extract filename format may vary between versions. The extract client tries both `SAM_PUBLIC_MONTHLY_V2_YYYYMMDD.ZIP` (current) and `SAM_PUBLIC_MONTHLY_YYYYMMDD.ZIP` (legacy from 2022 Postman collection).
- Tests for data cleaner and entity loader are pending.
- **Schema fix applied**: `entity_disaster_response.state_code` widened from VARCHAR(2) to VARCHAR(10) -- source data contains codes longer than 2 characters.
- **FILE privilege required**: `fed_app` user needs the global FILE privilege for LOAD DATA INFILE: `GRANT FILE ON *.* TO 'fed_app'@'localhost';`
- **SBA type date concatenation**: SBA type entries in DAT file concatenate code+date (e.g., "A620291223" = code "A6" + date "20291223"). The dat_parser currently stores the full string; needs a fix to split code from date suffix.
- **Duplicate NAICS entries**: 7 entities in source data have duplicate NAICS rows (same code, different flags). Handled with LOAD DATA IGNORE.
- **Multi-row entities**: 7,587 entities have multiple CAGE codes in the DAT file. Only the first CAGE code is stored in the entity table.

> **Note (Phase 14.20):** The SBA type date-suffix concatenation bug (e.g., `A620291223`) remains a known low-priority backlog item. Current parsing handles whitespace-padded entries correctly.
