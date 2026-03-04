# SAM.gov Bulk Entity Extracts API

## Quick Facts

| Property | Value |
|----------|-------|
| **Endpoint** | `https://api.sam.gov/data-services/v1/extracts` |
| **Auth** | `api_key` query parameter |
| **Rate Limit** | 10/day (free tier), 1,000/day (with role). One download = one API call. |
| **Pagination** | N/A (single file download per call) |
| **Data Format** | ZIP containing pipe-delimited DAT (V1) or JSON (V2) |
| **Update Frequency** | Monthly (first Sunday of month), Daily (Tuesday-Saturday) |
| **Our CLI Command** | `python main.py load entities --bulk` |
| **Client File** | `fed_prospector/api_clients/sam_extract_client.py` |
| **Loader File** | `fed_prospector/etl/bulk_loader.py`, `fed_prospector/etl/dat_parser.py` |
| **OpenAPI Spec** | `thesolution/sam_gov_api/sam-entity-extracts-api.yaml` |

## Purpose & Prospecting Value

The SAM.gov Bulk Extract API is the primary mechanism for loading entity registration data into FedProspect. While the Entity Management API (v3) limits you to 10 records per page and 10,000 records per query, a single extract download retrieves the complete dataset of all ~1.3 million registered entities (~576K active) in one API call. This makes it by far the most efficient way to build and maintain the entity database.

For WOSB and 8(a) prospecting, the monthly extract provides the foundation for all competitor analysis, teaming partner discovery, and market intelligence. Every entity's business type codes (WOSB: A2/8W/8E/8C/8D), SBA certifications (8(a): A4/A6 with entry/exit dates), NAICS codes, PSC codes, physical addresses, CAGE codes, and points of contact are included. Loading this data once a month and applying daily incremental updates keeps the entity database current without consuming significant API budget.

The extract files also include data not easily retrievable via the Entity API due to pagination limits: the complete NAICS code list for each entity (not just primary), all PSC codes, all business type codes, and SBA certification dates. This comprehensive view enables aggregate analysis such as "how many active WOSB firms in Virginia have NAICS 541511 as a primary code" -- queries that would be impossible to answer through the paginated API alone.

## Query Parameters

### Download Parameters

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `api_key` | string | (your key) | Required. |
| `fileName` | string | `SAM_PUBLIC_MONTHLY_V2_20260201.ZIP` | Exact filename to download. |
| `sensitivity` | string | `PUBLIC` | `PUBLIC` or `FOUO`. |
| `fileType` | string | `ENTITY` | Domain filter for listing available files. |
| `frequency` | string | `MONTHLY` | `MONTHLY` or `DAILY`. |
| `charset` | string | `UTF-8` | Character set variant. |
| `date` | string | `20260201` | Specific file date (YYYYMMDD). |
| `version` | string | `V2` | `V1` (DAT) or `V2` (JSON). |

### File Naming Conventions

| Type | Pattern | Schedule |
|------|---------|----------|
| Monthly (V2) | `SAM_PUBLIC_MONTHLY_V2_YYYYMMDD.ZIP` | First Sunday of each month |
| Monthly (legacy) | `SAM_PUBLIC_MONTHLY_YYYYMMDD.ZIP` | First Sunday of each month |
| Daily (V2) | `SAM_PUBLIC_DAILY_V2_YYYYMMDD.ZIP` | Tuesday through Saturday |
| UTF-8 variants | `SAM_PUBLIC_UTF-8_MONTHLY_V2_YYYYMMDD.ZIP` | Same schedule |

### Date Availability

- **Monthly**: Published on the first Sunday of each month. The exact date varies (could be the 1st through the 7th). Our client tries dates 1-7, prioritizing Sundays first.
- **Daily**: Published Tuesday through Saturday only. No files on Sunday or Monday.
- **No retroactive files**: If you miss a daily file, it may no longer be available after a few weeks.

## Response Structure

### Listing Available Files

When called without `fileName`, the API returns a list of available extract files:

```json
{
  "availableFiles": [
    {
      "fileName": "SAM_PUBLIC_MONTHLY_V2_20260201.ZIP",
      "fileSize": "892345678",
      "datePublished": "2026-02-01"
    }
  ]
}
```

### Downloaded File Contents

#### V2 JSON Format (Preferred)

The V2 ZIP contains a JSON file with the structure:

```json
{
  "entityData": [
    {
      "entityRegistration": {
        "ueiSAM": "ABC123DEF456",
        "cageCode": "1ABC2",
        "legalBusinessName": "Acme Solutions LLC",
        "registrationStatus": "Active",
        ...
      },
      "coreData": {
        "physicalAddress": { ... },
        "businessTypes": {
          "businessTypeList": [ ... ],
          "sbaBusinessTypeList": [ ... ]
        },
        "naicsList": [ ... ],
        "pscList": [ ... ]
      },
      ...
    }
  ]
}
```

JSON files can be 55MB+ and are streamed using `ijson` for memory efficiency. Falls back to full `json.load()` if `ijson` is not installed.

#### V1 DAT Format (Pipe-Delimited)

The V1 ZIP contains a pipe-delimited DAT file with 142 fields per row:

```
BOF PUBLIC V2 00000000 20260201 0872819 0008169
ABC123DEF456||1ABC2||A||Z2|20200115|20260601|20251215|20250601|Acme Solutions LLC|||...!end
...
EOF PUBLIC V2 00000000 20260201 0872819 0008169
```

**DAT file structure**:
- First line: BOF header with record counts
- Last line: EOF footer (same format)
- Data lines: 142 pipe-delimited fields, each line ends with `!end`
- Multi-row entities: Same UEI with multiple CAGE codes appears as separate rows

### Key DAT Field Positions (0-Based)

| Position | Field | Notes |
|----------|-------|-------|
| 0 | UEI SAM | 12-digit identifier |
| 1 | UEI DUNS | Always empty in V2 |
| 2 | EFT Indicator | |
| 3 | CAGE Code | |
| 4 | DoDAAC | |
| 5 | Registration Status | A=Active, E=Expired |
| 6 | Purpose of Registration | |
| 7-10 | Dates | Initial reg, expiration, last update, activation (YYYYMMDD) |
| 11-12 | Business Name, DBA | |
| 15-22 | Physical Address | Line1, Line2, City, State, ZIP, ZIP+4, Country, Congressional District |
| 30-31 | Business Types | Counter + tilde-separated codes |
| 32 | Primary NAICS | 6-digit code |
| 33-34 | NAICS List | Counter + tilde-separated entries |
| 35-36 | PSC List | Counter + tilde-separated codes |
| 39-45 | Mailing Address | |
| 46-111 | Points of Contact | 6 POCs x 11 fields each |
| 112-113 | NAICS Exceptions | Counter + tilde-separated entries |
| 114 | Debt Subject to Offset | |
| 115 | Exclusion Status Flag | |

## Known Issues & Quirks

1. **Escaped pipe characters in DAT files**: Pipes within data values are escaped as `|\|`. These must be converted to `||` (empty field) or the actual value extracted. Our `fix_pipe_escapes()` utility handles this.

2. **NULL representation**: Empty fields in DAT files appear as `||` (two consecutive pipes). The parser treats these as `None`/`NULL`.

3. **Multi-value fields use tildes**: NAICS codes, PSC codes, business types, and NAICS exceptions are stored as tilde-separated (`~`) values within a single pipe-delimited field. The `split_tilde_values()` utility parses these.

4. **SBA type entries concatenate code and date**: SBA business type entries in the DAT file concatenate the 2-character code with an 8-digit date (e.g., `A620291223` = code `A6` + certification exit date `2029-12-23`). The parser must split these.

5. **Dates in YYYYMMDD format**: All dates in DAT files use `YYYYMMDD` format (e.g., `20260201`), not ISO 8601 with separators. Must be converted to `DATE` type during load.

6. **Monthly file date varies**: The first-Sunday-of-month convention means the file date could be the 1st through the 7th. Our client tries all 7 dates, prioritizing Sundays, and handles 404s gracefully.

7. **Multi-row entities**: An entity with multiple CAGE codes appears as multiple rows in the DAT file (same UEI, different CAGE code in field 3). The parser and loader must handle deduplication/merging.

8. **File size**: Monthly PUBLIC extracts are typically 800MB-1GB as ZIP, expanding to several GB when extracted. Ensure sufficient disk space.

9. **No daily files on Sunday/Monday**: Daily extracts are only published Tuesday through Saturday. The client raises `ValueError` if you request a Sunday or Monday file.

10. **Duplicate NAICS entries**: Some entities have the same NAICS code listed multiple times with different `sba_small_business` flags (7 occurrences found in monthly extract). Deduplicated during load.

## Our Loading Strategy

### Initial Load (Monthly Extract)

1. **Download**: `SAMExtractClient.download_monthly_extract(year, month)` -- 1 API call
2. **Extract**: ZIP is automatically extracted (handles nested ZIPs)
3. **Parse**: `DATParser` reads the pipe-delimited file, yields entity dicts
4. **Load**: `BulkLoader` writes temp TSV files, uses `LOAD DATA INFILE` for maximum MySQL throughput
5. **Time**: 1-2 hours for download + parse + load of ~576K active entities
6. **Frequency**: Once per month, on the first week of the month

### Daily Incremental Updates

1. **Download**: `SAMExtractClient.download_daily_extract(date_obj)` -- 1 API call
2. **Parse**: Same pipeline as monthly
3. **Load**: Same pipeline, but with change detection (SHA-256 hashing) to identify inserts, updates, and unchanged records
4. **Time**: Minutes (daily files are much smaller, typically a few thousand entities)
5. **Frequency**: Tuesday through Saturday
6. **Schedule**: `Entity Incremental` in refresh schedule, 1 call/day

### Budget Impact

The extract download approach is remarkably budget-efficient:

| Operation | API Calls | Records Loaded |
|-----------|-----------|----------------|
| Monthly full extract | 1 | ~576K active entities |
| Daily incremental | 1 | Hundreds to low thousands |
| Full month (monthly + 5 dailies) | 6 | All entity updates |

Compare this to the Entity Management API, which would need 57,600+ calls to load the same data at 10 records per page.

### File Cache

Downloaded files are cached locally under `data/downloads/sam_entity/`:
- Keep last 3 monthly extracts
- Keep last 30 daily extracts
- The client skips re-downloading if a local file matches the remote file size

### JSON vs DAT

- **V2 JSON** is preferred for Python processing (preserves nested structure, no pipe-escape headaches)
- **V1 DAT** is supported as a fallback and was the original format
- Both are loaded through the same pipeline; `DATParser` handles V1, `stream_json_entities()` handles V2

## Data Quality Issues

- **Issue #1**: ZIP codes containing city/state/country names (9,294 records). ETL cleaner truncates/fixes.
- **Issue #2**: ZIP codes containing PO BOX data (27 records). ETL cleaner handles.
- **Issue #3**: State fields containing dates (e.g., "05/03/1963"). ETL cleaner detects and nullifies.
- **Issue #4**: Foreign addresses with province names > 2 chars in state field. Column accommodates.
- **Issue #5**: Non-ASCII characters in country names (Reunion, Cote d'Ivoire). UTF-8 encoding handles.
- **Issue #6**: Missing 3-letter country codes (XKS=Kosovo, XWB=West Bank, XGZ=Gaza). Custom lookup table.
- **Issue #7**: CAGE codes with multiple values separated by comma+space. Parsed by loader.
- **Issue #8**: NAICS codes from retired vintages not in current lookup tables. Logged, loaded as-is.
- **Issue #9**: Escaped pipe characters (`|\|`) in DAT files. `fix_pipe_escapes()` cleans these.
- **Issue #10**: Dates in YYYYMMDD format. Converted to DATE type during parse.
- **Issue #11**: SBA type entries concatenate code+date (e.g., "A620291223"). Parsed into separate fields.
- **Issue #12**: Duplicate NAICS entries -- same code, different flags. Deduplicated during load.

## Cross-References

- **Related tables**: `entity` (main), `entity_address`, `entity_naics`, `entity_psc`, `entity_business_type`, `entity_sba_certification`, `entity_poc`
- **Linking fields**: `uei_sam` (primary key for entity, links to `opportunity.awardee_uei` and `award.awardee_uei`), `cage_code`, `naics_code`, `psc_code`
- **Alternative sources**: SAM.gov Entity Management API v3 (for targeted lookups of individual entities by UEI -- see `SAM-ENTITY-API.md`)
- **Downstream consumers**: Competitor analysis, teaming partner discovery, go/no-go scoring, entity profile views in UI

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `FileNotFoundError`: No monthly extract found | Wrong date range or file not yet published | Verify first Sunday of target month; file may publish late |
| `ValueError`: Daily extracts only available Tue-Sat | Requested a Sunday or Monday date | Use the next available weekday |
| HTTP 404 | File does not exist for the specified date | Try adjacent dates; monthly files vary by 1-7 days |
| `RateLimitExceeded` | Hit daily API call limit | Wait until next day; each download is 1 call |
| ZIP extraction fails | Corrupted download (network interrupt) | Delete the local file and re-download |
| `MemoryError` during JSON parsing | File too large for `json.load()` | Install `ijson` for streaming parse: `pip install ijson` |
| DAT parse error: wrong field count | File format mismatch or pipe-escape issue | Verify `fix_pipe_escapes()` ran; check for V1 vs V2 mismatch |
| Duplicate UEI rows in DAT file | Entity has multiple CAGE codes | Normal -- parser merges rows with same UEI |
| Download skipped (file exists) | Local file matches remote size | Delete local file to force re-download, or this is expected caching behavior |
