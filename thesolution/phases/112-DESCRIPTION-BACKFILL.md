# Phase 112: Opportunity Description Backfill

**Status:** PLANNED
**Priority:** High — 98% of opportunities (38,402 of 39,282) have no description text, only a SAM.gov URL
**Dependencies:** None

---

## Summary

Most opportunities in the database have `description_url` (a SAM.gov API endpoint) but null `description_text`. The description is valuable context for bid/no-bid decisions and keyword intel extraction. This phase addresses the gap with three tasks: research batch alternatives, improve the existing CLI backfill, and add on-demand UI fetching.

---

## Task 1: Research Batch Description Fetching

Investigate whether there's any way to fetch descriptions in bulk instead of 1 API call per opportunity.

Research areas:
- SAM.gov bulk data downloads (does the bulk extract include description HTML?)
- SAM.gov GraphQL or v2/v3 API endpoints that might return description inline with search results
- The `description` field in the search API response — is it always a URL, or does it sometimes contain inline text for shorter descriptions?
- SAM.gov data.gov datasets or other government open data sources
- Whether the description HTML is available through the beta.sam.gov public site without API key (scraping as last resort)

Document findings in this phase file. If a batch method exists, implement it. If not, document why and proceed with Tasks 2-3.

Current state:
- `opportunity_loader.py` already has `fetch_description_text()` and `backfill_descriptions()` methods
- Each call hits `https://api.sam.gov/prod/opportunities/v1/noticedesc?noticeid=...&api_key=...`
- Requires API key, counts against 1,000/day rate limit (Key 2)
- Returns JSON with HTML description that needs tag stripping

---

## Task 2: Improve CLI Description Backfill

The existing `backfill_descriptions()` method fetches all missing descriptions. Update it to prioritize future-dated (active) opportunities by default.

### CLI changes

Update the existing CLI command (find it in the codebase) or add one:

```
python main.py load descriptions                    # Only future-dated opportunities (default)
python main.py load descriptions --include-expired   # All opportunities including expired
python main.py load descriptions --notice-id <ID>    # Single opportunity
```

### Logic changes in `opportunity_loader.py`

- Default: `WHERE description_text IS NULL AND description_url IS NOT NULL AND response_date >= CURDATE()`
- With `--include-expired`: `WHERE description_text IS NULL AND description_url IS NOT NULL`
- With `--notice-id`: single opportunity regardless of date
- Log progress: "Fetching description 42/1,234..."
- Respect rate limits — the existing loader already handles 429s
- Count and report: "Done. Fetched 234 descriptions, 5 failed, 12 rate-limited (retry tomorrow)"

### Scope check

Count how many active (future-dated) opportunities need descriptions vs total:
```sql
SELECT
  COUNT(*) as total_missing,
  SUM(CASE WHEN response_date >= CURDATE() THEN 1 ELSE 0 END) as active_missing
FROM opportunity
WHERE description_text IS NULL AND description_url IS NOT NULL
```

This determines whether the active-only default is practical within the 1,000/day limit.

---

## Task 3: On-Demand UI Fetch

Add a button on the opportunity detail page to fetch a missing description on demand.

### Backend

New endpoint: `POST /opportunities/{noticeId}/fetch-description`

- Check if `description_text` is already populated — if so, return it immediately
- If null, call SAM.gov `noticedesc` endpoint to fetch it
- Strip HTML tags, store in `description_text`
- Return the description text in the response

This uses the same `fetch_description_text()` method from the opportunity loader.

### UI

On the Overview tab of the opportunity detail page:
- If `description_text` is populated, show it
- If null but `description_url` exists, show a button: "Fetch Description from SAM.gov"
- Button calls the endpoint, shows loading spinner, then displays the fetched description
- If fetch fails (rate limit, network error), show error message

### Rate limit consideration

Single on-demand fetches are fine — a user won't trigger 1,000 of these. The daily limit is only a concern for the batch backfill in Task 2.

---

## Code Touchpoints

### Existing files to modify

| File | What to do |
|------|------------|
| `fed_prospector/etl/opportunity_loader.py` | Update `backfill_descriptions()` to filter by response_date, add --include-expired support |
| `fed_prospector/cli/` (find the right file) | Update CLI command with new flags |
| `api/src/FedProspector.Api/Controllers/OpportunitiesController.cs` | Add POST {noticeId}/fetch-description endpoint |
| `api/src/FedProspector.Infrastructure/Services/` | Add description fetch service method |
| `ui/src/pages/opportunities/` | Add fetch button on Overview tab |
| `ui/src/api/opportunities.ts` | Add fetchDescription API call |

### Potentially new files

| File | Purpose |
|------|---------|
| None expected — all changes fit in existing files |

---

## Implementation Order

1. Task 1 first (research) — may change the approach for Task 2
2. Task 2 next (CLI backfill improvements) — backend-only, quick
3. Task 3 last (UI button) — fullstack, depends on Task 2's loader method

---

## Current Data

- 39,282 total opportunities
- 880 have description_text (2%)
- 38,402 have description_url but no text (98%)
- Active opportunities needing descriptions: TBD (run query in Task 2)
- API rate limit: 1,000/day on Key 2
