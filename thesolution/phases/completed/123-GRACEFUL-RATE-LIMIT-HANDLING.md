# Phase 123: Graceful Rate Limit Handling

**Status:** COMPLETE (2026-05-28)
**Priority:** Medium — UX improvement, prevents wasted API calls
**Dependencies:** Phase 112 (Description Backfill), Phase 110Y (Request Poller)

## Implementation Summary

Implemented in 5 units (commits `58a6594`, `02477f3`, `5eabdc4`, `c72ece9`, `a00c2bb`):

- **Unit A — Schema**: `data_load_request.retry_after DATETIME NULL` + composite index `(status, retry_after)`. New `PENDING_RETRY` status documented (free-form `VARCHAR(20)`, no CHECK constraint). EF Core model updated. Live DB ALTER applied. Table is Python-DDL-owned per CLAUDE.md — no EF migration.
- **Unit B — Python client**: `fed_prospector/api_clients/sam_opportunities_client.py` — `SamOpportunitiesClient.fetch_description_text(notice_id)` ports the C# `FetchDescriptionAsync` + `StripHtmlTags` semantics. Surfaces 429 via new `DescriptionFetchRateLimited(RateLimitExceeded)` with `reset_at` populated from SAM `nextAccessTime` body field (fallback: next UTC midnight). `base_client.py` intentionally untouched (10 downstream consumers).
- **Unit C — Python poller**: `_process_description_fetch` handler in `DemandLoader` — on success writes `opportunity.description_text` and COMPLETED; on `DescriptionFetchRateLimited` transitions row to `PENDING_RETRY` with `retry_after = exc.reset_at` instead of FAILED. Row-selection SQL now picks up both `PENDING` and `PENDING_RETRY AND retry_after <= UTC_TIMESTAMP()`.
- **Unit D — C# endpoint**: `OpportunityService.FetchDescriptionAsync` now explicitly detects `HttpStatusCode.TooManyRequests`, enqueues a `DataLoadRequest(RequestType=DESCRIPTION_FETCH, LookupKey=noticeId, LookupKeyType=NOTICE_ID, Status=PENDING)` deduped against existing `PENDING | PENDING_RETRY`, and returns a new `FetchDescriptionResult` record. Controller maps `Queued=true` to HTTP 202 with `{ noticeId, queued, message }`. 6 new service tests + 4 new controller tests.
- **Unit E — UI**: `OpportunityDetailPage` mutation `onSuccess` branches on `data.queued` — info-severity `notistack` snackbar on 202 (with server-provided message), unchanged behavior on 200. `FetchDescriptionResponse` type extended with optional `queued` and `message`.

### End-to-end flow (verified via unit tests, live test deferred to avoid burning SAM Key 2 quota)

1. UI POSTs to `/opportunities/{noticeId}/fetch-description`.
2. C# attempts SAM call. On 429: row inserted, returns 202; on 200: returns description.
3. UI shows blue info snackbar on 202.
4. Next time `DemandLoader.process_pending_requests` runs (cron or manual): row is picked up if `retry_after` has passed, description fetched, written to `opportunity.description_text`, row marked COMPLETED. If SAM still 429s, row deferred again with updated `retry_after`.

### Decisions (from planner's flagged ambiguities)

1. Retry strategy: `PENDING_RETRY` + `retry_after` column (option 2 from the plan's "research needed" list).
2. Parameters: mapped `notice_id` to `lookup_key` with `lookup_key_type='NOTICE_ID'`, consistent with `FPDS_AWARD` / `PIID` convention.
3. Reset-time fallback: SAM `nextAccessTime` if present, else next UTC midnight (Key 2's documented reset).
4. New Python client file (`sam_opportunities_client.py`) rather than retrofitting into `sam_awards_client.py`.
5. Scoped to description fetch only; no premature generic `IRateLimitQueueService` abstraction.

### Pattern reusable for Phase 130

`DESCRIPTION_FETCH` is the first user of `PENDING_RETRY`. When Phase 130 (Early Attachment Cleanup & Re-Analyze) needs to queue attachment re-downloads behind SAM rate limits, it can mirror this shape: typed exception with `reset_at` → poller handler catches it → row transitions to `PENDING_RETRY`. Generalize at the second use site, not pre-emptively.

---

---

## Summary

When the SAM.gov API key daily limit is reached, on-demand actions (like "Fetch Description from SAM.gov") fail with a generic 502 error. The user has no idea why it failed or what to do. This phase adds graceful handling: try the call, and if rate-limited, queue it for the poller to process after the daily reset.

This pattern applies to any on-demand SAM.gov API call, not just descriptions.

---

## Flow

1. User clicks "Fetch Description from SAM.gov" on the UI
2. C# API attempts the SAM.gov call directly
3. If successful: return description (existing behavior)
4. If 429 (rate limited):
   a. Insert a `data_load_request` with `request_type='DESCRIPTION_FETCH'`
   b. Return 202 Accepted with message: "Daily API limit reached — queued for automatic fetch tomorrow"
5. UI shows an info/blue snackbar with the queued message (not a red error)
6. Poller picks it up after the daily reset

---

## Task 1: C# API — Detect 429 and Queue

**Endpoint:** `POST /opportunities/{noticeId}/fetch-description`

- Catch `HttpRequestException` with 429 status from the SAM.gov call
- Insert `data_load_request` row: `request_type='DESCRIPTION_FETCH'`, `parameters={"notice_id": "..."}`
- Return 202 Accepted with body: `{ "queued": true, "message": "Daily API limit reached — queued for automatic fetch" }`

## Task 2: Demand Loader — DESCRIPTION_FETCH Handler

**File:** `fed_prospector/etl/demand_loader.py`

- New handler for `request_type='DESCRIPTION_FETCH'`
- Calls `fetch_description_text()` for the queued notice_id
- Saves result to `opportunity.description_text`
- Marks request COMPLETED or FAILED

## Task 3: Poller Rate Limit Awareness

**Problem:** If the poller tries to process `DESCRIPTION_FETCH` requests while the key is still maxed, it'll fail every one and mark them all as permanently FAILED.

**Solution options (research needed):**
- Track last 429 timestamp. Skip DESCRIPTION_FETCH requests until after the reset window (SAM.gov Key 2 resets at 4pm AKT / midnight UTC)
- Or: on 429 failure, set request status to `PENDING_RETRY` instead of `FAILED`, with a `retry_after` timestamp
- Or: poller does a lightweight SAM.gov health check before processing queued description fetches

## Task 4: UI — Handle 202 Response

- On 202: show info/blue snackbar "Daily API limit reached — queued for automatic fetch tomorrow"
- On 200: existing success behavior (show description)
- On other errors: existing red error snackbar

---

## Broader Applicability

This rate-limit-then-queue pattern could apply to any on-demand SAM.gov call:
- Fetch description (this phase)
- Re-download attachments (Phase 130)
- Any future on-demand API action

Consider making the queue-on-429 logic reusable.

---

## SAM.gov Key 2 Reset Time

Key 2 (1,000/day) resets at **4:00 PM AKT** (midnight UTC). The poller should be aware of this window.
