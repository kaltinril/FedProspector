# Phase 112: Opportunity Description Backfill

**Status:** COMPLETE
**Priority:** High — ~45,371 opportunities had no description text, only a SAM.gov URL
**Dependencies:** None

---

## Summary

Most opportunities in the database had `description_url` (a SAM.gov API endpoint) but null `description_text`. The description is valuable context for bid/no-bid decisions and keyword intel extraction. This phase addressed the gap with three tasks: research batch alternatives, improve the existing CLI backfill with priority filtering, and add on-demand UI fetching.

---

## Task 1: Research Batch Description Fetching — COMPLETE

**Finding: No bulk path exists.** The SAM.gov `noticedesc` endpoint is strictly one call per notice_id. Research confirmed:

- No batch endpoint, no bulk download, no GraphQL, no data.gov mirror includes description text
- The search API returns description as a URL, never inline text
- Each call counts against the daily quota (Key 2: 1,000/day)
- SAM.gov returns 404 for notices that genuinely have no description AND for invalid API keys, but valid-but-exhausted keys get 429 — so 404s reliably mean "no description exists"

Proceeded with per-opportunity fetching in Tasks 2 and 3.

---

## Task 2: CLI Description Backfill — COMPLETE

Implemented `python ./fed_prospector/main.py update fetch-descriptions` with prioritized two-pass fetching.

### CLI options

| Flag | Purpose |
|------|---------|
| `--days-back N` | Filter by posted_date |
| `--notice-id <ID>` | Single opportunity fetch |
| `--key 1\|2` | Which API key (default 2) |
| `--naics <codes>` | Comma-separated NAICS codes for priority filtering |
| `--set-aside <codes>` | Comma-separated set-aside codes for priority filtering |
| `--limit N` | Max total descriptions to fetch |

### Two-pass priority logic

1. **First half of budget:** NAICS + set-aside filtered, active only (response_deadline >= CURDATE()), all-time, newest first
2. **Remaining budget:** Everything else, newest first
3. If priority pass uses fewer than half, remainder rolls to general pass

### Added to daily_load.bat (step 2/13)

```
python ./fed_prospector/main.py update fetch-descriptions --key 2 --limit 100 --naics %NAICS% --set-aside WOSB,8A,SBA
```

### Data findings

| Metric | Count |
|--------|-------|
| Total opportunities missing descriptions | ~45,371 |
| All new opportunities/day (weekday avg) | ~1,450 |
| WOSB+8A+SBA set-asides/day | ~420 |
| Target NAICS codes/day | ~104 |
| Target NAICS + set-asides/day | ~27 |

At 100/day limit with priority filtering, the backlog will catch up over time with high-value opportunities fetched first.

---

## Task 3: On-Demand UI Fetch — COMPLETE

### Backend

- `POST /api/v1/opportunities/{noticeId}/fetch-description` endpoint
- Returns cached description if already fetched; otherwise calls SAM.gov live
- SSRF protection, HTML tag stripping, saves to DB

### UI

- "Fetch Description from SAM.gov" button on Overview tab when description is missing
- Loading spinner during fetch, success/error snackbar
- Cache invalidation on success to refresh the page

---

## Known Issues Deferred to Other Phases

| Issue | Phase |
|-------|-------|
| Queue on 429 instead of red error in UI | 123 (Graceful Rate Limit Handling) |
| Contact data in raw JSON never extracted | 122 (Opportunity POC Extraction) |
| Run keyword/AI analysis on fetched description text | 121 (Description Intel Extraction) |
