# SAM.gov Federal Hierarchy API v1

## Quick Facts

| Property | Value |
|----------|-------|
| **Endpoint** | `https://api.sam.gov/prod/federalorganizations/v1/orgs` |
| **Auth** | `api_key` query parameter |
| **Rate Limit** | 10/day (free, no role), 1,000/day (personal with role or system account) |
| **Pagination** | `limit`/`offset` (record offset), max 100 per page |
| **Data Format** | JSON |
| **Update Frequency** | Weekly refresh (Sunday only in our schedule) |
| **Our CLI Command** | `python main.py load fedhier` |
| **Client File** | `fed_prospector/api_clients/sam_fedhier_client.py` |
| **Loader File** | `fed_prospector/etl/fedhier_loader.py` |
| **OpenAPI Spec** | `thesolution/sam_gov_api/fh-public-hierarchy.yml`, `thesolution/sam_gov_api/fh-public-org.yml` |

> **Address data is NOT available via this API.** Verified by inspecting 544,501 raw responses cached in `stg_fedhier_raw`. Every record contains only: `aacofficecode, agencycode, cgaclist, createdby, createddate, fhagencyorgname, fhdeptindagencyorgid, fhorgid, fhorgname, fhorgnamehistory, fhorgofficetypelist, fhorgparenthistory, fhorgtype, lastupdateddate, links, oldfpdsofficecode, status, updatedby`. No street, city, state, zip, postal, or address fields appear in any response. Linking federal offices to physical addresses requires a different data source (not currently identified).

## Purpose & Prospecting Value

The Federal Hierarchy API provides the authoritative organizational structure of the U.S. federal government, from top-level departments and independent agencies down through sub-tier agencies and contracting offices. This three-level hierarchy (Department/Ind. Agency -> Sub-Tier -> Office) is the canonical reference for how federal procurement is organized.

For WOSB and 8(a) contract prospecting, this data enables agency-level targeting. By mapping which offices within agencies historically issue set-aside contracts (cross-referenced with award data from SAM.gov Contract Awards and USASpending.gov), you can identify the most promising contracting offices to monitor. Without this hierarchy, opportunity and award records contain agency names as flat strings that are difficult to aggregate or navigate.

The hierarchy also powers filter dropdowns in the FedProspect UI, giving users a structured way to browse agencies, sub-tiers, and offices. The parent-child relationships (tracked via `fhfullparentpathid` in the API response and `parent_org_id` in our DB) enable drill-down navigation from department to sub-tier to individual contracting office.

## Query Parameters

### Working Filters

| Parameter | Type | Example | Notes |
|-----------|------|---------|-------|
| `fhorgid` | string | `100000000` | Unique org ID in Federal Hierarchy |
| `fhorgname` | string | `Defense` | Partial match on organization name |
| `fhorgtype` | string | `Department/Ind. Agency` | Also: `Sub-Tier`. OpenAPI says `Department/Ind-agency` but live API uses `Department/Ind. Agency` |
| `status` | string | `Active` | `Active`, `Inactive`, or `all`. Default is `Active` |
| `agencycode` | string | `3600` | FPDS agency code |
| `cgac` | string | `097` | Common Government-wide Accounting Classification code |
| `oldfpdsofficecode` | string | | Legacy FPDS office code |
| `updateddatefrom` | string | `2026-01-01` | Start of updated date range (YYYY-MM-DD) |
| `updateddateto` | string | `2026-03-01` | End of updated date range (YYYY-MM-DD) |
| `createdby` | string | | Filter by creator (rarely used) |
| `createddatefrom` | string | | Created date range start |
| `createddateto` | string | | Created date range end |
| `updatedby` | string | | Filter by updater (rarely used) |

### Pagination

Pagination uses `limit` and `offset` as **record offsets** (not page indices):
- `limit`: Records per page. Default 10, max **100**.
- `offset`: 0-based record offset. Example: offset=0 returns records 1-100, offset=100 returns records 101-200.

The response includes `totalrecords` (note: **lowercase**, unlike every other SAM API which uses `totalRecords`). Our client passes `total_key="totalrecords"` to the base paginator to handle this inconsistency.

Example pagination sequence:
```
offset=0,   limit=100  ->  records 1-100
offset=100, limit=100  ->  records 101-200
offset=200, limit=100  ->  records 201-300
```

Stop when `offset + 100 >= totalrecords`.

## Response Structure

```json
{
  "totalrecords": 8542,
  "orglist": [
    {
      "fhorgid": 100000000,
      "fhorgname": "DEPARTMENT OF DEFENSE",
      "fhorgtype": "Department/Ind. Agency",
      "description": "...",
      "status": "Active",
      "agencycode": "9700",
      "oldfpdsofficecode": null,
      "cgaclist": [
        { "cgac": "097" }
      ],
      "fhdeptindagencyorgid": null,
      "fhorgparenthistory": [
        {
          "fhfullparentpathid": "100000000",
          "fhfullparentpathname": "DEPARTMENT OF DEFENSE",
          "effectivedate": "2020-01-01"
        }
      ],
      "createddate": "2020-01-01",
      "lastupdateddate": "2025-06-15"
    }
  ]
}
```

### Key Response Fields

| Field | Type | Notes |
|-------|------|-------|
| `totalrecords` | int | Total matching records (lowercase -- API inconsistency) |
| `orglist` | array | List of org dicts for this page |
| `fhorgid` | int/string | Unique Federal Hierarchy org ID |
| `fhorgname` | string | Organization name |
| `fhorgtype` | string | `Department/Ind. Agency`, `Sub-Tier`, or `Office` |
| `status` | string | `Active` or `Inactive` |
| `agencycode` | string | FPDS agency code |
| `cgaclist` | array | List of `{cgac: "..."}` objects; first entry used |
| `fhorgparenthistory` | array | Parent path history, sorted by `effectivedate` |
| `fhfullparentpathid` | string | Dot-separated org IDs from root to parent (e.g., `100000000.100123456`) |
| `fhdeptindagencyorgid` | string | Department-level parent ID for sub-tiers |
| `createddate` | string | Creation date |
| `lastupdateddate` | string | Last update date |

### Parent-Child Resolution

The loader extracts `parent_org_id` from the response using this logic:
1. **Department/Ind. Agency** orgs have no parent (`parent_org_id = NULL`).
2. For sub-tiers and offices, sort `fhorgparenthistory` by `effectivedate` descending.
3. Take the most recent entry's `fhfullparentpathid` and split on `.`.
4. The **last segment** is the immediate parent org ID.
5. Fallback: use `fhdeptindagencyorgid` for sub-tier orgs.

### Hierarchy Levels

| `fhorgtype` Value | Level |
|-------------------|-------|
| `Department/Ind. Agency` | 1 |
| `Sub-Tier` | 2 |
| `Office` | 3 |

## Known Issues & Quirks

1. **`totalrecords` is lowercase** -- Every other SAM API uses `totalRecords` (camelCase). The Federal Hierarchy API uses `totalrecords`. Our client explicitly passes `total_key="totalrecords"` to the paginator.

2. **`fhorgtype` values differ from OpenAPI spec** -- The spec says `Department/Ind-agency` but the live API returns `Department/Ind. Agency`. Always validate against live responses, not the spec.

3. **CGAC is nested in an array** -- The `cgac` value is not a simple string. It is inside `cgaclist[0].cgac`. Our loader extracts the first entry.

4. **Parent history can have multiple entries** -- An org can move in the hierarchy over time. The loader sorts by `effectivedate` descending and takes the most recent parent path.

5. **Rate limits are shared** -- This API shares the same daily quota with all other SAM.gov APIs (Opportunities, Awards, Exclusions, Subawards, Entity). Budget accordingly.

6. **OpenAPI spec defines response as bare `type: object`** -- No field definitions in the spec. Response structure is discovered from live API calls.

## Our Loading Strategy

### Initial Load
Full pagination through all active organizations. At ~8,500 records and 100/page, this requires ~85 API calls. Feasible in a single session with the 1,000/day tier.

### Ongoing Refresh
- **Frequency**: Weekly (Sunday), allocated 10 calls/week from the 1,000/day budget.
- **Method**: Resumable page-by-page loading (`iter_organization_pages()`) with progress saved after each page. If rate limits are hit mid-load, the next run resumes from the last saved offset.
- **Change detection**: SHA-256 hashing on 10 business-meaningful fields. Only records with changed hashes are updated in the database.

### Budget Impact
- Initial load: ~85 API calls (one-time)
- Weekly refresh: ~85 API calls (can be spread across days if needed)
- With 1,000/day tier and 10 calls/week allocation, full weekly refresh fits easily

### Full Refresh
The `full_refresh()` method uses `DELETE FROM` (not `TRUNCATE TABLE`) for transactional safety -- if the reload fails mid-load, the delete is rolled back and previous data is preserved.

## Data Quality Issues

No major data quality issues have been discovered specific to the Federal Hierarchy API. The data is clean and well-structured compared to other SAM.gov APIs. The main challenges are:
- Understanding the nested response structure (CGAC arrays, parent history arrays)
- Handling the `totalrecords` casing inconsistency
- Mapping `fhorgtype` strings to numeric levels for the hierarchy

## Cross-References

- **Related tables**: `federal_organization` (primary), `fpds_contract` (joined via `agency_code`), `opportunity` (joined via contracting office)
- **Linking fields**: `fh_org_id` (PK), `agency_code` (links to FPDS), `cgac` (links to USASpending agency data), `parent_org_id` (self-referencing FK for hierarchy navigation)
- **Alternative sources**: USASpending agency endpoints provide some agency data, but SAM.gov Federal Hierarchy is the authoritative source with full parent-child relationships

## Troubleshooting

| Error | Cause | Fix |
|-------|-------|-----|
| `401 Unauthorized` | Invalid or expired API key | Regenerate key at SAM.gov. Keys expire every 90 days. |
| `429 Too Many Requests` | Daily rate limit exceeded | Wait until midnight ET for reset. Use `etl_rate_limit` table to track usage. |
| Rate limit hit mid-pagination | Used too many calls across all SAM APIs | Use `iter_organization_pages()` with `max_pages` parameter to cap calls. Resume next day. |
| `totalrecords` not found in response | Using wrong response key | Verify you are reading `totalrecords` (lowercase), not `totalRecords`. |
| Parent org ID missing for sub-tier | Empty `fhorgparenthistory` | Loader falls back to `fhdeptindagencyorgid`. Some orgs genuinely have no mapped parent. |
| Stale data after load | Weekly refresh not running | Check `etl_load_log` for last successful `SAM_FEDHIER` load. Re-run `python main.py load fedhier`. |
